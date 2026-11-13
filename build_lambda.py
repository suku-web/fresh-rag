"""Build lambda.zip for FRESH-RAG.

Run from the project root (venv active):
    python build_lambda.py

The zip is built for Linux (what Lambda runs), even though you are on Windows.
boto3 is already included in the Lambda runtime, so it is not packaged.
.env is never copied. Put secrets in the Lambda environment variables.

Files are assembled in a temporary folder (outside OneDrive), so this script
never deletes or changes any folder inside your project. Only lambda.zip is
written to the project root.
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# MUST match the Python version of your Lambda function (Lambda > Code > Runtime settings).
PYTHON_VERSION = "3.14"
# x86_64 is the default Lambda architecture.
PLATFORM = "manylinux2014_x86_64"

PACKAGES = ["fastapi", "mangum", "pydantic", "python-dotenv", "openai"]
FOLDERS = ["app", "rag_pipeline", "adaptive_engine", "dashboard"]
OPTIONAL_FOLDERS = {"dashboard"}
FILES = ["lambda_function.py"]

ROOT = Path(__file__).resolve().parent
ZIP_PATH = ROOT / "lambda.zip"


def main():
    build = Path(tempfile.mkdtemp(prefix="fresh_rag_build_"))
    print(f"Working folder: {build}")

    try:
        print(f"Installing packages for Linux / Python {PYTHON_VERSION} ...")
        subprocess.run(
            [
                sys.executable, "-m", "pip", "install",
                "--target", str(build),
                "--platform", PLATFORM,
                "--implementation", "cp",
                "--python-version", PYTHON_VERSION,
                "--only-binary=:all:",
                "--upgrade",
                *PACKAGES,
            ],
            check=True,
        )

        ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".env", "*.env")
        for folder in FOLDERS:
            src = ROOT / folder
            if not src.exists():
                if folder in OPTIONAL_FOLDERS:
                    print(f"Skipping missing optional folder: {folder}")
                    continue
                sys.exit(f"Missing folder: {folder}. Run this from the project root.")
            shutil.copytree(src, build / folder, ignore=ignore)

        for name in FILES:
            src = ROOT / name
            if not src.exists():
                sys.exit(f"Missing file: {name}")
            shutil.copy2(src, build / name)

        print("Creating lambda.zip ...")
        if ZIP_PATH.exists():
            ZIP_PATH.unlink()
        with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(build.rglob("*")):
                if path.is_file():
                    # as_posix() keeps forward slashes, which Lambda needs.
                    zf.write(path, path.relative_to(build).as_posix())
    finally:
        shutil.rmtree(build, ignore_errors=True)

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"Done: {ZIP_PATH} ({size_mb:.1f} MB)")
    if size_mb > 50:
        print("Warning: over 50 MB. Upload via S3 instead of the console.")


if __name__ == "__main__":
    main()