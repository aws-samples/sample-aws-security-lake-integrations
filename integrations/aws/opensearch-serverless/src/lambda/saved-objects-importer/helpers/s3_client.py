# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
S3 Client Helper

This module handles downloading NDJSON saved object files from S3 buckets
for import into OpenSearch Dashboards.
"""

import logging
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Global S3 client for Lambda warm start optimization
_s3_client: Optional[boto3.client] = None


def get_s3_client() -> boto3.client:
    """
    Get or create a global S3 client for reuse across Lambda invocations.
    
    This pattern prevents cold start penalties by reusing the client
    connection across invocations.
    
    Returns:
        boto3.client: Reusable S3 client
    """
    global _s3_client
    if _s3_client is None:
        # Configure client with retry settings
        config = Config(
            retries={
                "max_attempts": 3,
                "mode": "standard"
            },
            connect_timeout=5,
            read_timeout=30
        )
        _s3_client = boto3.client("s3", config=config)
        logger.info("Created new S3 client for saved objects importer")
    return _s3_client


class S3ClientError(Exception):
    """Custom exception for S3 client errors."""
    
    def __init__(self, message: str, bucket: str = "", key: str = "", cause: Optional[Exception] = None):
        super().__init__(message)
        self.bucket = bucket
        self.key = key
        self.cause = cause


class S3Client:
    """
    S3 client for downloading saved object NDJSON files.
    
    This client provides methods to download files from S3 with
    proper error handling and logging.
    
    Attributes:
        bucket: Default S3 bucket name for operations
    """
    
    def __init__(self, bucket: Optional[str] = None) -> None:
        """
        Initialize S3 client.
        
        Args:
            bucket: Default S3 bucket name. Can be overridden per operation.
        """
        self.bucket = bucket
        self._client = get_s3_client()
        
        if bucket:
            logger.info("Initialized S3 client with default bucket: %s", bucket)
        else:
            logger.info("Initialized S3 client (no default bucket)")
    
    def download_file(
        self,
        key: str,
        bucket: Optional[str] = None
    ) -> bytes:
        """
        Download a file from S3 and return its content as bytes.
        
        Args:
            key: S3 object key (path to the file)
            bucket: S3 bucket name. Uses default bucket if not provided.
            
        Returns:
            bytes: File content as raw bytes
            
        Raises:
            S3ClientError: If the file cannot be downloaded
            
        Example:
            >>> client = S3Client(bucket="my-bucket")
            >>> content = client.download_file("dashboards/security.ndjson")
            >>> print(f"Downloaded {len(content)} bytes")
        """
        target_bucket = bucket or self.bucket
        if not target_bucket:
            raise S3ClientError(
                message="No bucket specified and no default bucket configured",
                key=key
            )
        
        logger.info(
            "Downloading file from S3: bucket=%s, key=%s",
            target_bucket,
            key
        )
        
        try:
            response = self._client.get_object(
                Bucket=target_bucket,
                Key=key
            )
            
            # Read the entire file content
            content = response["Body"].read()
            
            content_length = response.get("ContentLength", len(content))
            content_type = response.get("ContentType", "unknown")
            
            logger.info(
                "Successfully downloaded file: bucket=%s, key=%s, size=%d bytes, content_type=%s",
                target_bucket,
                key,
                content_length,
                content_type
            )
            
            return content
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            
            if error_code == "NoSuchKey":
                logger.error(
                    "File not found in S3: bucket=%s, key=%s",
                    target_bucket,
                    key
                )
                raise S3ClientError(
                    message=f"File not found: s3://{target_bucket}/{key}",
                    bucket=target_bucket,
                    key=key,
                    cause=e
                )
            
            elif error_code == "NoSuchBucket":
                logger.error(
                    "Bucket not found: bucket=%s",
                    target_bucket
                )
                raise S3ClientError(
                    message=f"Bucket not found: {target_bucket}",
                    bucket=target_bucket,
                    key=key,
                    cause=e
                )
            
            elif error_code == "AccessDenied":
                logger.error(
                    "Access denied to S3 object: bucket=%s, key=%s",
                    target_bucket,
                    key
                )
                raise S3ClientError(
                    message=f"Access denied to s3://{target_bucket}/{key}",
                    bucket=target_bucket,
                    key=key,
                    cause=e
                )
            
            else:
                logger.error(
                    "S3 error downloading file: bucket=%s, key=%s, code=%s, message=%s",
                    target_bucket,
                    key,
                    error_code,
                    error_message
                )
                raise S3ClientError(
                    message=f"S3 error ({error_code}): {error_message}",
                    bucket=target_bucket,
                    key=key,
                    cause=e
                )
                
        except Exception as e:
            logger.exception(
                "Unexpected error downloading file from S3: bucket=%s, key=%s",
                target_bucket,
                key
            )
            raise S3ClientError(
                message=f"Unexpected error: {str(e)}",
                bucket=target_bucket,
                key=key,
                cause=e
            )
    
    def file_exists(
        self,
        key: str,
        bucket: Optional[str] = None
    ) -> bool:
        """
        Check if a file exists in S3.
        
        Args:
            key: S3 object key (path to the file)
            bucket: S3 bucket name. Uses default bucket if not provided.
            
        Returns:
            bool: True if the file exists, False otherwise
            
        Example:
            >>> client = S3Client(bucket="my-bucket")
            >>> if client.file_exists("dashboards/security.ndjson"):
            ...     content = client.download_file("dashboards/security.ndjson")
        """
        target_bucket = bucket or self.bucket
        if not target_bucket:
            logger.warning("No bucket specified for file existence check")
            return False
        
        try:
            self._client.head_object(
                Bucket=target_bucket,
                Key=key
            )
            logger.debug(
                "File exists: bucket=%s, key=%s",
                target_bucket,
                key
            )
            return True
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                logger.debug(
                    "File does not exist: bucket=%s, key=%s",
                    target_bucket,
                    key
                )
                return False
            
            # For other errors, log and return False
            logger.warning(
                "Error checking file existence: bucket=%s, key=%s, error=%s",
                target_bucket,
                key,
                str(e)
            )
            return False
            
        except Exception as e:
            logger.warning(
                "Unexpected error checking file existence: bucket=%s, key=%s, error=%s",
                target_bucket,
                key,
                str(e)
            )
            return False
    
    def get_file_metadata(
        self,
        key: str,
        bucket: Optional[str] = None
    ) -> dict:
        """
        Get metadata for a file in S3.
        
        Args:
            key: S3 object key (path to the file)
            bucket: S3 bucket name. Uses default bucket if not provided.
            
        Returns:
            dict: File metadata including ContentLength, ContentType,
                  LastModified, and custom metadata
                  
        Raises:
            S3ClientError: If metadata cannot be retrieved
        """
        target_bucket = bucket or self.bucket
        if not target_bucket:
            raise S3ClientError(
                message="No bucket specified and no default bucket configured",
                key=key
            )
        
        try:
            response = self._client.head_object(
                Bucket=target_bucket,
                Key=key
            )
            
            metadata = {
                "content_length": response.get("ContentLength", 0),
                "content_type": response.get("ContentType", ""),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag", "").strip('"'),
                "metadata": response.get("Metadata", {})
            }
            
            logger.debug(
                "Retrieved metadata: bucket=%s, key=%s, size=%d bytes",
                target_bucket,
                key,
                metadata["content_length"]
            )
            
            return metadata
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            
            if error_code == "404":
                raise S3ClientError(
                    message=f"File not found: s3://{target_bucket}/{key}",
                    bucket=target_bucket,
                    key=key,
                    cause=e
                )
            
            raise S3ClientError(
                message=f"Error retrieving metadata: {str(e)}",
                bucket=target_bucket,
                key=key,
                cause=e
            )