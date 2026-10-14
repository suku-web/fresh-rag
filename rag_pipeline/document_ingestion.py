import os
from pathlib import Path

import boto3
from dotenv import load_dotenv


# Load AWS configuration from .env
load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

if not AWS_REGION:
    raise ValueError("AWS_REGION is missing from .env")

if not S3_BUCKET_NAME:
    raise ValueError("S3_BUCKET_NAME is missing from .env")


# Create S3 client
s3 = boto3.client("s3", region_name=AWS_REGION)


def upload_document(file_path: str) -> str:
    """
    Upload a local document to the FRESH-RAG S3 bucket.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    object_key = path.name

    s3.upload_file(
        str(path),
        S3_BUCKET_NAME,
        object_key
    )

    return object_key


def download_document(object_key: str, download_path: str) -> str:
    """
    Download a document from the FRESH-RAG S3 bucket.
    """

    download_file = Path(download_path)

    download_file.parent.mkdir(parents=True, exist_ok=True)

    s3.download_file(
        S3_BUCKET_NAME,
        object_key,
        str(download_file)
    )

    return str(download_file)


if __name__ == "__main__":

    # Upload document to S3
    uploaded_file = upload_document("data/sample.txt")
    print(f"Successfully uploaded: {uploaded_file}")

    # Download document from S3
    downloaded_file = download_document(
        uploaded_file,
        "data/downloaded/sample.txt"
    )
    print(f"Successfully downloaded: {downloaded_file}")