# import os
# import tempfile
# import boto3
# import pytest
# from moto.s3 import mock_s3;



# @pytest.fixture(scope="function")
# def local_file():
#     with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt') as f:
#         f.write("This is a local test file.")
#         f.flush()
#         yield f.name
#     os.unlink(f.name)


# @mock_s3
# @pytest.fixture(scope="function")
# def s3_file():
#     bucket = "test-bucket"
#     key = "docs/test.txt"
#     content = "This is an S3 test file."

#     s3 = boto3.client("s3", region_name="us-east-1")
#     s3.create_bucket(Bucket=bucket)
#     s3.put_object(Bucket=bucket, Key=key, Body=content)

#     s3_path = f"s3://{bucket}/{key}"
#     return s3_path, content


# def test_load_local_file(local_file):
#     loader = FileLoader()
#     stream = loader.load_file(local_file)
#     data = stream.read().decode("utf-8")
#     assert data == "This is a local test file."


# @mock_s3
# def test_load_s3_file(s3_file):
#     s3_path, expected_content = s3_file
#     loader = FileLoader()
#     stream = loader.load_file(s3_path)
#     data = stream.read().decode("utf-8")
#     assert data == expected_content


# @mock_s3
# def test_file_loader_cache(s3_file):
#     s3_path, _ = s3_file
#     loader = FileLoader()
#     # First load (cached)
#     first = loader.load_file(s3_path)
#     # Second load (should hit cache)
#     second = loader.load_file(s3_path)
#     assert first == second  # Object identity, not just content
