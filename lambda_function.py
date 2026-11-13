"""AWS Lambda entry point for FRESH-RAG.

Lambda Handler setting: lambda_function.handler

Two kinds of events arrive here:
  1. HTTP requests from API Gateway (HTTP API, payload v2) -> FastAPI via Mangum
  2. Scheduled events from EventBridge -> the refresh job

For an EventBridge Scheduler schedule, set the target input to:
    {"task": "refresh"}
A classic EventBridge rule ("Schedule") is detected automatically.
"""
from mangum import Mangum

from app.main import app, run_refresh_job

_asgi_handler = Mangum(app, lifespan="off")


def _is_schedule_event(event):
    if not isinstance(event, dict):
        return False
    return event.get("source") == "aws.events" or event.get("task") == "refresh"


def handler(event, context):
    if _is_schedule_event(event):
        return run_refresh_job(trigger="schedule")
    return _asgi_handler(event, context)