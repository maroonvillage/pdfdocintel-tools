import os
import re
import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError
from io import BytesIO
from typing import Union, BinaryIO
from pathlib import Path
import hashlib

# Optional: directory to cache remote files
DEFAULT_CACHE_DIR = Path(".cache/files")


def is_s3_uri(uri: str) -> bool:
    return uri.startswith("s3://")


def parse_s3_uri(uri: str) -> tuple[str, str]:
    match = re.match(r"s3://([^/]+)/(.+)", uri)
    if not match:
        raise ValueError(f"Invalid S3 URI format: {uri}")
    return match.group(1), match.group(2)


def hash_uri(uri: str) -> str:
    return hashlib.sha256(uri.encode()).hexdigest()


def get_cached_path(uri: str, cache_dir: Union[str, Path] = DEFAULT_CACHE_DIR) -> Path:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / hash_uri(uri)


def open_file_from_path_or_s3(uri: str, use_cache: bool = True) -> BinaryIO:
    """
    Open a file from local path or S3. If use_cache is True, downloads are cached locally.
    Returns a file-like BinaryIO stream.
    """
    if is_s3_uri(uri):
        return _open_s3_file(uri, use_cache)
    else:
        if not os.path.exists(uri):
            raise FileNotFoundError(f"Local file not found: {uri}")
        return open(uri, "rb")


def _open_s3_file(uri: str, use_cache: bool) -> BinaryIO:
    bucket, key = parse_s3_uri(uri)
    cache_path = get_cached_path(uri)

    if use_cache and cache_path.exists():
        return open(cache_path, "rb")

    try:
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=bucket, Key=key)
        data = response['Body'].read()

        if use_cache:
            cache_path.write_bytes(data)

        return BytesIO(data)
    except (BotoCoreError, NoCredentialsError) as e:
        raise RuntimeError(f"Failed to load S3 file: {uri}") from e
