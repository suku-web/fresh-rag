import os
import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

import boto3
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from rag_pipeline.rag_pipeline import (
    load_document,
    search_document,
    calculate_relevance,
    calculate_confidence,
)
from adaptive_engine.engine import make_decision
from adaptive_engine.quality import evaluate_quality
from adaptive_engine.cost import calculate_cost
from app.llm_client import generate_answer as llm_generate_answer

app = FastAPI(title="FRESH-RAG API", version="1.1.0")

# On AWS Lambda the code folder is read-only. Only /tmp can be written to.
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
DASHBOARD = ROOT / "dashboard"
DATA_DIR = Path("/tmp/data") if IS_LAMBDA else ROOT / "data"
HISTORY_FILE = DATA_DIR / "refresh_history.json"
STATE_FILE = DATA_DIR / "sync_state.json"
CHAT_LOG_FILE = DATA_DIR / "chat_history.json"
COMBINED_FILE = DATA_DIR / "_combined.txt"

# If CHAT_TABLE_NAME is set, chat history, refresh history and refresh state
# are stored in this DynamoDB table (partition key: request_id).
CHAT_TABLE_NAME = os.getenv("CHAT_TABLE_NAME")
STATE_ITEM_ID = "state#refresh"

# sample.txt is the old college document and must not be used any more.
SKIP_FILES = {"sample.txt", "_combined.txt"}
S3_SYNC_TTL_SECONDS = 300
ESTIMATED_COST_PER_FILE_USD = 0.0001  # placeholder estimate, not real billing
CURRENCY = "USD"

_last_s3_sync = 0.0
_s3_files = set()  # names of documents downloaded from S3 (the source of truth)
_chat_table = None

if not IS_LAMBDA:
    DASHBOARD.mkdir(exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None


class RefreshRequest(BaseModel):
    document_changed: bool = False
    change_magnitude: float = Field(default=0.5, ge=0, le=1)
    quality_score: float = Field(default=0.9, ge=0, le=1)
    quality_drop: float = Field(default=0.0, ge=0, le=1)
    hours_since_sync: float = Field(default=1.0, ge=0)
    estimated_sync_cost: float = Field(default=0.01, ge=0)
    budget_remaining: float = Field(default=1.0, ge=0)
    urgent: bool = False


class RefreshRunRequest(BaseModel):
    force: bool = False  # force=true behaves like an urgent refresh


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _to_dynamo(value):
    """DynamoDB does not accept Python floats, so convert them to Decimal."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    raise TypeError(f"Not JSON serializable: {type(obj).__name__}")


def _from_dynamo(value):
    return json.loads(json.dumps(value, default=_decimal_default))


def get_chat_table():
    global _chat_table
    if _chat_table is None:
        dynamodb = boto3.resource(
            "dynamodb", region_name=os.getenv("AWS_REGION", "ap-south-1")
        )
        _chat_table = dynamodb.Table(CHAT_TABLE_NAME)
    return _chat_table


def _scan_table():
    table = get_chat_table()
    resp = table.scan()
    items = list(resp.get("Items", []))
    while "LastEvaluatedKey" in resp and len(items) < 2000:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return [_from_dynamo(i) for i in items]


# ----------------------------------------------------------------------------
# Chat history (DynamoDB if configured, otherwise a local file)
# ----------------------------------------------------------------------------
def save_log(record: dict):
    try:
        if CHAT_TABLE_NAME:
            get_chat_table().put_item(Item=_to_dynamo(record))
        else:
            history = read_json(CHAT_LOG_FILE, [])
            if not isinstance(history, list):
                history = []
            history.append(record)
            write_json(CHAT_LOG_FILE, history[-500:])
    except Exception as exc:
        print(f"Could not save chat log: {type(exc).__name__}")


def load_chat_history():
    try:
        if CHAT_TABLE_NAME:
            items = [i for i in _scan_table() if i.get("type", "chat") == "chat"]
            items.sort(key=lambda i: i.get("timestamp", ""))
            return items
        items = read_json(CHAT_LOG_FILE, [])
        return items if isinstance(items, list) else []
    except Exception as exc:
        print(f"Could not read chat history: {type(exc).__name__}")
        return []


# ----------------------------------------------------------------------------
# Refresh state + refresh history
# ----------------------------------------------------------------------------
def load_state() -> dict:
    try:
        if CHAT_TABLE_NAME:
            item = get_chat_table().get_item(Key={"request_id": STATE_ITEM_ID}).get("Item")
            return _from_dynamo(item) if item else {}
        state = read_json(STATE_FILE, {})
        return state if isinstance(state, dict) else {}
    except Exception as exc:
        print(f"Could not read refresh state: {type(exc).__name__}")
        return {}


def save_state(state: dict):
    try:
        if CHAT_TABLE_NAME:
            item = _to_dynamo(state)
            item["request_id"] = STATE_ITEM_ID
            item["type"] = "state"
            get_chat_table().put_item(Item=item)
        else:
            write_json(STATE_FILE, state)
    except Exception as exc:
        print(f"Could not save refresh state: {type(exc).__name__}")


def add_refresh_history(entry: dict):
    try:
        if CHAT_TABLE_NAME:
            get_chat_table().put_item(Item=_to_dynamo(entry))
        else:
            history = read_json(HISTORY_FILE, [])
            if not isinstance(history, list):
                history = []
            history.append(entry)
            write_json(HISTORY_FILE, history[-200:])
    except Exception as exc:
        print(f"Could not save refresh history: {type(exc).__name__}")


def load_refresh_history():
    try:
        if CHAT_TABLE_NAME:
            items = [i for i in _scan_table() if i.get("type") == "refresh"]
            items.sort(key=lambda i: i.get("timestamp", ""))
            return items
        items = read_json(HISTORY_FILE, [])
        return items if isinstance(items, list) else []
    except Exception as exc:
        print(f"Could not read refresh history: {type(exc).__name__}")
        return []


# ----------------------------------------------------------------------------
# Documents (S3 is the source of truth)
# ----------------------------------------------------------------------------
def _s3_client():
    return boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-south-1"))


def list_s3_documents() -> dict:
    """Return {file name: ETag} for the .txt documents in the S3 bucket."""
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME is not set")
    docs = {}
    paginator = _s3_client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if "/" in key or not key.endswith(".txt") or key in SKIP_FILES:
                continue
            docs[key] = obj["ETag"].strip('"')
    return docs


def sync_documents_from_s3(force=False):
    """Download .txt documents from S3 into DATA_DIR (cached for a few minutes).

    Returns True on success, False on failure, None if skipped.
    If S3 is unreachable, the files already in DATA_DIR are used instead.
    """
    global _last_s3_sync, _s3_files
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        return None
    if not force and time.time() - _last_s3_sync < S3_SYNC_TTL_SECONDS:
        return None
    _last_s3_sync = time.time()
    try:
        s3 = _s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        names = set()
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if "/" in key or not key.endswith(".txt") or key in SKIP_FILES:
                    continue
                s3.download_file(bucket, key, str(DATA_DIR / key))
                names.add(key)
        if names:
            _s3_files = names
        return True
    except Exception as exc:
        print(f"S3 sync failed, using local files: {type(exc).__name__}")
        return False


def get_document():
    """Return (document, texts). texts maps file name -> file text."""
    sync_documents_from_s3()
    if _s3_files:
        # S3 is the source of truth: ignore any other old files in the data folder.
        files = sorted(
            DATA_DIR / name for name in _s3_files if (DATA_DIR / name).exists()
        )
    else:
        # S3 not available: fall back to local .txt files.
        files = sorted(
            p for p in DATA_DIR.glob("*.txt") if p.name not in SKIP_FILES
        )
    if not files:
        raise HTTPException(
            status_code=503,
            detail="No knowledge documents found in S3 or in the data folder.",
        )
    texts = {p.name: p.read_text(encoding="utf-8") for p in files}
    # load_document() reads a file path, so combine all documents into one file.
    COMBINED_FILE.write_text("\n".join(texts.values()), encoding="utf-8")
    # rag_pipeline.load_document() calls .exists() on its argument, so pass a Path.
    return load_document(COMBINED_FILE), texts


def find_sources(retrieved_lines, texts):
    bucket = os.getenv("S3_BUCKET_NAME", "fresh-rag-documents")
    names = []
    for line in retrieved_lines:
        line = str(line).strip()
        if not line:
            continue
        for name, text in texts.items():
            if line in text and name not in names:
                names.append(name)
    return [{"document": n, "uri": f"s3://{bucket}/{n}"} for n in names]


# ----------------------------------------------------------------------------
# Refresh policy + refresh job
# ----------------------------------------------------------------------------
def decide_refresh(
    document_changed,
    change_magnitude,
    quality_score,
    quality_drop,
    hours_since_sync,
    estimated_sync_cost,
    budget_remaining,
    urgent,
):
    """Return (decision, reason). Same rules as the original evaluate endpoint."""
    if urgent and budget_remaining >= estimated_sync_cost:
        return "REFRESH_NOW", "Urgent refresh requested and budget is available"
    if budget_remaining < estimated_sync_cost:
        return "DEFER", "Not enough budget for this refresh"
    if document_changed and (change_magnitude >= 0.5 or quality_drop >= 0.2):
        return "REFRESH_NOW", "Large change detected"
    if quality_score < 0.5:
        return "REFRESH_NOW", "Quality score is below 0.5"
    if hours_since_sync >= 24 and document_changed:
        return "REFRESH_NOW", "Documents changed and last sync was 24+ hours ago"
    if document_changed:
        return "SKIP", "Small change, waiting for a larger change or 24 hours"
    return "SKIP", "No change detected"


def _hours_since(iso_time):
    if not iso_time:
        return 24.0
    try:
        then = datetime.fromisoformat(iso_time)
        return max(0.0, (datetime.now(timezone.utc) - then).total_seconds() / 3600)
    except ValueError:
        return 24.0


def run_refresh_job(trigger="manual", force=False):
    """Check S3 for changed documents and refresh them if the policy says so.

    The S3 ETag of every document is compared with the ETags saved at the last
    successful refresh. Used by POST /api/refresh/run and by the EventBridge
    schedule (through lambda_function.handler).
    """
    now = datetime.now(timezone.utc)
    state = load_state()
    previous = state.get("etags", {}) if isinstance(state.get("etags"), dict) else {}
    base = {
        "request_id": f"refresh-{uuid.uuid4()}",
        "type": "refresh",
        "timestamp": now.isoformat(),
        "trigger": trigger,
    }

    try:
        current = list_s3_documents()
    except Exception as exc:
        entry = {
            **base,
            "decision": "ERROR",
            "status": "error",
            "reason": f"S3 check failed: {type(exc).__name__}",
            "changed_files": [],
            "estimated_cost": 0.0,
        }
        add_refresh_history(entry)
        return entry

    changed = sorted(k for k, v in current.items() if previous.get(k) != v)
    removed = sorted(k for k in previous if k not in current)
    total = max(len(current), 1)
    magnitude = min(1.0, (len(changed) + len(removed)) / total)
    cost = round(ESTIMATED_COST_PER_FILE_USD * max(len(changed), 1), 6)
    budget = float(state.get("budget_remaining", 1.0))

    decision, reason = decide_refresh(
        document_changed=bool(changed or removed),
        change_magnitude=magnitude,
        quality_score=0.9,  # placeholder: no live quality signal for the job yet
        quality_drop=0.0,
        hours_since_sync=_hours_since(state.get("last_successful_sync")),
        estimated_sync_cost=cost,
        budget_remaining=budget,
        urgent=force,
    )

    status = "skipped"
    if decision == "REFRESH_NOW":
        ok = sync_documents_from_s3(force=True)
        if ok is False:
            status = "error"
            reason = "Refresh decided, but downloading from S3 failed"
        else:
            status = "refreshed"
            state["etags"] = current
            state["last_successful_sync"] = now.isoformat()
            budget = round(max(0.0, budget - cost), 6)
    elif decision == "DEFER":
        status = "deferred"

    state.update({
        "sync_enabled": True,
        "job_running": False,
        "last_checked": now.isoformat(),
        "last_decision": decision,
        "budget_remaining": budget,
        "currency": CURRENCY,
    })
    save_state(state)

    entry = {
        **base,
        "decision": decision,
        "status": status,
        "reason": reason,
        "changed_files": changed + removed,
        "documents_total": len(current),
        "change_magnitude": round(magnitude, 3),
        "estimated_cost": cost,
        "budget_remaining": budget,
    }
    add_refresh_history(entry)
    print(json.dumps({
        "event": "refresh",
        "trigger": trigger,
        "decision": decision,
        "status": status,
        "changed": len(changed),
    }))
    return entry


# ----------------------------------------------------------------------------
# API routes
# ----------------------------------------------------------------------------
@app.get("/")
def dashboard():
    index = DASHBOARD / "index.html"
    if not index.exists():
        return {
            "message": "FRESH-RAG API is running. Dashboard files are not created yet.",
            "docs": "/docs",
        }
    return FileResponse(index)


if DASHBOARD.exists():
    app.mount("/static", StaticFiles(directory=str(DASHBOARD)), name="static")


@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "FRESH-RAG API"}


@app.post("/api/chat")
def chat(body: ChatRequest):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    document, texts = get_document()
    retrieved_lines = search_document(document, question)
    relevance = calculate_relevance(document, question)
    confidence = calculate_confidence(relevance, retrieved_lines)
    quality_score, quality_level = evaluate_quality(relevance, confidence)

    # Placeholder estimate (unchanged from the original version).
    estimated_cost = calculate_cost(
        len(question.split()), 0, 0.01, 0.02
    )
    decision = make_decision(relevance, confidence, estimated_cost)

    conversation_id = body.conversation_id or str(uuid.uuid4())
    sources = find_sources(retrieved_lines, texts)

    provider = None
    model_id = None
    input_tokens = 0
    output_tokens = 0
    llm_error = None

    if decision == "ABSTAIN" or not retrieved_lines:
        answer = (
            "I couldn't find enough relevant information in the current knowledge "
            "documents to answer reliably."
        )
        mode = "local-policy"
        sources = []
    else:
        result = llm_generate_answer(question, retrieved_lines)
        answer = result["answer"]
        mode = result["mode"]  # "llm", "bedrock" or "fallback"
        provider = result.get("provider")
        model_id = result.get("model_id")
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        llm_error = result.get("error")

    request_id = str(uuid.uuid4())
    record = {
        "request_id": request_id,
        "type": "chat",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
        "question": question,
        "decision": decision,
        "relevance_score": round(relevance, 3),
        "confidence_score": round(confidence, 3),
        "quality_score": round(quality_score, 3),
        "quality_level": quality_level,
        "estimated_cost": round(estimated_cost, 6),
        "mode": mode,
        "provider": provider,
        "model_id": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "sources": [s["document"] for s in sources],
        "error": llm_error,
    }
    save_log(record)
    # One line per request. On Lambda this goes to CloudWatch Logs.
    print(json.dumps({
        "event": "chat",
        "request_id": request_id,
        "decision": decision,
        "mode": mode,
        "provider": provider,
        "relevance": record["relevance_score"],
        "confidence": record["confidence_score"],
        "error": llm_error,
    }))

    return {
        "answer": answer,
        "sources": sources,
        "conversation_id": conversation_id,
        "request_id": request_id,
        "mode": mode,
        "provider": provider,
        "decision": decision,
        "relevance_score": round(relevance, 3),
        "confidence_score": round(confidence, 3),
        "quality_score": round(quality_score, 3),
        "quality_level": quality_level,
        "estimated_cost": round(estimated_cost, 6),
    }


@app.get("/api/chat/history")
def chat_history(limit: int = Query(default=20, ge=0, le=100)):
    items = load_chat_history()
    items = items[-limit:] if limit else []
    return {"items": items, "count": len(items)}


@app.post("/api/refresh/evaluate")
def evaluate_refresh(body: RefreshRequest):
    decision, reason = decide_refresh(
        document_changed=body.document_changed,
        change_magnitude=body.change_magnitude,
        quality_score=body.quality_score,
        quality_drop=body.quality_drop,
        hours_since_sync=body.hours_since_sync,
        estimated_sync_cost=body.estimated_sync_cost,
        budget_remaining=body.budget_remaining,
        urgent=body.urgent,
    )
    return {
        "decision": decision,
        "reason": reason,
        "estimated_sync_cost": body.estimated_sync_cost,
        "budget_remaining": body.budget_remaining,
        "mode": "local-policy",
    }


@app.post("/api/refresh/run")
def run_refresh(body: Optional[RefreshRunRequest] = None):
    """Check S3 for changes and refresh the documents if the policy allows."""
    if not os.getenv("S3_BUCKET_NAME"):
        raise HTTPException(
            status_code=503,
            detail="S3_BUCKET_NAME is not configured, so refresh cannot run.",
        )
    force = bool(body.force) if body else False
    return run_refresh_job(trigger="manual", force=force)


@app.get("/api/refresh/status")
def refresh_status():
    state = load_state()
    bucket = os.getenv("S3_BUCKET_NAME")
    return {
        "sync_enabled": state.get("sync_enabled", bool(bucket)),
        "job_running": state.get("job_running", False),
        "last_successful_sync": state.get("last_successful_sync"),
        "last_checked": state.get("last_checked"),
        "last_decision": state.get("last_decision"),
        "budget_remaining": state.get("budget_remaining", 1.0),
        "currency": state.get("currency", CURRENCY),
        "mode": "aws-s3" if bucket else "local-demo",
    }


@app.get("/api/refresh/history")
def refresh_history(limit: int = Query(default=20, ge=0, le=100)):
    items = load_refresh_history()
    items = items[-limit:] if limit else []
    return {"items": items, "count": len(items)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)