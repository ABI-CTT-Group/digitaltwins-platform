import os
import logging
import mimetypes
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
from typing import List
from app.utils.utils import safe_open

logger = logging.getLogger(__name__)


class MinioClient:
    """Minio client for storing plugin frontend build artfacts and backend origin codes using boto3"""

    def __init__(self, bucket_name):
        self.endpoint = os.getenv('MINIO_ENDPOINT', "localhost:9000")
        self.access_key = os.getenv('MINIO_ACCESS_KEY', "minioadmin")
        self.secret_key = os.getenv('MINIO_SECRET_KEY', "minioadmin")
        self.bucket_name = bucket_name
        self.use_ssl = os.getenv('USE_SSL', "false").lower() == 'true'

        self.client = boto3.client(
            's3',
            endpoint_url=f"http{'s' if self.use_ssl else ''}://{self.endpoint}",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='us-east-1'  # MinIO doesn't require specific region
        )

    def set_bucket_name(self, bucket_name):
        self.bucket_name = bucket_name

    # def upload_directory(self, local_path: str, remote_prefix: str) -> str:
    #     """Upload a directory to minio bucket"""
    #     try:
    #         local_path = Path(local_path)
    #         if not local_path.exists():
    #             raise FileNotFoundError(f"Local path does not exist: {local_path}")
    #         uploaded_files = []
    #
    #         # Walk through the directory
    #         for root, dirs, files in os.walk(local_path):
    #             for file in files:
    #                 file_path = Path(root) / file
    #                 relative_path = file_path.relative_to(local_path).as_posix()
    #                 object_name = f"{remote_prefix}/{relative_path}"
    #
    #                 # Determine MIME type
    #                 extra_args = self._determine_mime_type(str(file_path))
    #                 with open(file_path, 'rb') as f:
    #                     self.client.upload_fileobj(f, self.bucket_name, object_name, ExtraArgs=extra_args)
    #                 uploaded_files.append(object_name)
    #                 logger.info(f"Uploaded file: {object_name}")
    #         return f"s3://{self.bucket_name}/{remote_prefix}"
    #
    #     except Exception as e:
    #         logger.error(f"Failed to upload directory {local_path}: {e}")
    #         raise

    def upload_directory(self, local_path: str, remote_prefix: str) -> str:
        """
        Upload a directory to S3/MinIO bucket.
        Handles Windows long paths and cross-platform.
        """
        try:
            local_path = Path(local_path).resolve()
            if not local_path.exists():
                raise FileNotFoundError(f"Local path does not exist: {local_path}")

            uploaded_files = []

            # Use normal os.walk on absolute path (no \\?\ prefix)
            for root, dirs, files in os.walk(local_path):
                for file in files:
                    file_path = Path(root) / file
                    # Relative path from the base local_path
                    relative_path = file_path.relative_to(local_path).as_posix()
                    object_name = f"{remote_prefix}/{relative_path}"

                    # Determine MIME type
                    extra_args = self._determine_mime_type(str(file_path))

                    # Open file safely (Windows long path safe)
                    with safe_open(file_path, "rb") as f:
                        self.client.upload_fileobj(f, self.bucket_name, object_name, ExtraArgs=extra_args)

                    uploaded_files.append(object_name)
                    logger.info(f"Uploaded file: {object_name}")

            return f"s3://{self.bucket_name}/{remote_prefix}"

        except Exception as e:
            logger.error(f"Failed to upload directory {local_path}: {e}")
            raise

    def upload_file(self, local_path: str, remote_name: str) -> str:
        """Upload a file to minio bucket"""
        try:
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local path does not exist: {local_path}")

            # Determine MIME type
            extra_args = self._determine_mime_type(local_path)
            self.client.upload_file(local_path, self.bucket_name, remote_name, ExtraArgs=extra_args)

            s3_path = f"s3://{self.bucket_name}/{remote_name}"
            logger.info(f"Uploaded file: {s3_path}")
            return s3_path
        except Exception as e:
            logger.error(f"Failed to upload file: {local_path}: {e}")
            raise

    def _determine_mime_type(self, file_path: str) -> dict:
        content_type, _ = mimetypes.guess_type(str(file_path))
        file_path = Path(file_path)
        if content_type is None:
            if file_path.suffix.lower() in ['.js', '.mjs']:
                content_type = 'application/javascript'
            elif file_path.suffix.lower() == '.css':
                content_type = 'text/css'
            else:
                content_type = 'application/octet-stream'
        return {'ContentType': content_type}

    def download_file(self, local_path: str, remote_name: str):
        """Download a file to minio bucket"""
        try:
            self.client.download_file(self.bucket_name, remote_name, local_path)
            logger.info(f"Downloaded: {remote_name} -> {local_path}")
        except Exception as e:
            logger.error(f"Failed to download file: {remote_name}: {e}")
            raise

    def list_objects(self, prefix: str = "") -> list:
        """List objects in the bucket with optional prefix"""
        try:
            response = self.client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if 'Contents' in response:
                return [{"Key": obj["Key"]} for obj in response['Contents']]
            return []
        except Exception as e:
            logger.error(f"Failed to list objects with prefix: {prefix}: {e}")
            raise

    def delete_objects(self, delete_keys: List[str]) -> None:
        """Delete objects in the bucket"""
        try:
            self.client.delete_objects(Bucket=self.bucket_name, Delete={'Objects': delete_keys})
            logger.info(f"Deleted objects: {delete_keys}")
        except Exception as e:
            logger.error(f"Failed to delete objects: {e}")
            raise

    def delete_object(self, object_name: str):
        """Delete an object from minio bucket"""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"Deleted object: {object_name}")
        except Exception as e:
            logger.error(f"Failed to delete object: {object_name}: {e}")
            raise

    def delete_objects_with_prefix(self, prefix: str):
        """Delete all objects with a given prefix"""
        try:
            objects = self.list_objects(prefix)
            for object_name in objects:
                self.delete_object(object_name)
            logger.info(f"Deleted {len(objects)} objects with prefix: {prefix}")
        except Exception as e:
            logger.error(f"Failed to list objects with prefix: {prefix}: {e}")
            raise

    def get_object_url(self, object_name: str, expires: int = 3600) -> str:
        """Get a presigned URL for an object"""
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expires
            )
            return url
        except Exception as e:
            logger.error(f"Failed to get presigned URL for object: {object_name}: {e}")
            raise

    def get_public_url(self, object_name: str) -> str:
        """Get a public URL for an object (no expiration)"""
        protocol = "https" if self.use_ssl else "http"
        return f"{protocol}://{self.endpoint}/{self.bucket_name}/{object_name}"

    def object_exists(self, object_name: str) -> bool:
        """Check if an object exists"""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
        except Exception as e:
            logger.error(f"Failed to check if object exists: {object_name}: {e}")
            raise

    def get_object(self, key: str):
        try:
            return self.client.get_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"Failed to get object {key}: {e}")
                return None
        except Exception as e:
            logger.error(f"Failed to get object {key}: {e}")

# minio_client = None
#
#
# def get_minio_client() -> MinioClient:
#     """Get the global MinioClient instance"""
#     global minio_client
#     if minio_client is None:
#         minio_client = MinioClient()
#     return minio_client

_clients: dict[str, MinioClient] = {}


def get_minio_client(bucket_name: str = None) -> MinioClient:
    bucket = bucket_name or "tools"
    if bucket not in _clients:
        client = MinioClient(bucket)
        _clients[bucket] = client
    return _clients[bucket]
