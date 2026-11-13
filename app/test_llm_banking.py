"""Quick LLM test with a real banking document.

Usage (from the project root, venv active):
    python app\\test_llm_banking.py loan_policy.txt

It reads the file from S3 (bucket from S3_BUCKET_NAME, default
fresh-rag-documents). If S3 fails, it tries data/<file> locally.
Then it asks for a question and prints the LLM answer.
"""
import os
import sys

import boto3

try:
    from llm_client import generate_answer
except ImportError:
    from app.llm_client import generate_answer


def load_text(key):
    bucket = os.getenv("S3_BUCKET_NAME", "fresh-rag-documents")
    region = os.getenv("AWS_REGION", "ap-south-1")
    try:
        s3 = boto3.client("s3", region_name=region)
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        print(f"[source] S3: s3://{bucket}/{key}")
        return body.decode("utf-8")
    except Exception as e:
        print(f"[source] S3 failed ({type(e).__name__}), trying local data/{key}")
        with open(os.path.join("data", key), encoding="utf-8") as f:
            return f.read()


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "loan_policy.txt"
    text = load_text(key)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    print(f"[info] {len(lines)} lines loaded from {key}")

    question = input("Question: ").strip()
    result = generate_answer(question, lines)
    print()
    for k, v in result.items():
        print(f"{k}: {v}")
