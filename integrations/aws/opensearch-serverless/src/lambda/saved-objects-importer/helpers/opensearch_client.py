# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
OpenSearch Serverless Client Helper

This module handles importing saved objects (dashboards, visualizations, index patterns)
into OpenSearch Dashboards via the Saved Objects API using AWS SigV4 authentication.

OpenSearch Serverless uses 'aoss' as the service name for SigV4 signing.
Endpoint format: https://{collection-id}.{region}.aoss.amazonaws.com
Import API: POST /_dashboards/api/saved_objects/_import?overwrite=true

This implementation uses the opensearch-py library with AWS4Auth from requests_aws4auth
for explicit SigV4 authentication support with OpenSearch Serverless.
"""

import logging
import os
from dataclasses import dataclass, field
from io import BytesIO
from typing import Dict, List, Any, Optional

import boto3
import requests
from requests_aws4auth import AWS4Auth
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from opensearchpy.exceptions import (
    ConnectionError as OSConnectionError,
    ConnectionTimeout,
    TransportError,
)

logger = logging.getLogger(__name__)

# Global boto3 session for Lambda warm start optimization
_boto3_session: Optional[boto3.Session] = None

# Global OpenSearch client for Lambda warm start optimization
_opensearch_client: Optional["OpenSearchClient"] = None


def get_boto3_session() -> boto3.Session:
    """
    Get or create a global boto3 session for credential reuse.
    
    This pattern prevents cold start penalties by reusing the session
    across Lambda invocations.
    
    Returns:
        boto3.Session: Reusable boto3 session
    """
    global _boto3_session
    if _boto3_session is None:
        _boto3_session = boto3.Session()
        logger.info("Created new boto3 session for OpenSearch client")
    return _boto3_session


@dataclass
class ImportResult:
    """Result of a saved objects import operation."""
    
    success: bool
    success_count: int = 0
    error_count: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "successCount": self.success_count,
            "errorCount": self.error_count,
            "errors": self.errors,
            "message": self.message
        }


class OpenSearchClient:
    """
    OpenSearch Serverless client for importing saved objects.
    
    This client uses the opensearch-py library with AWS4Auth from requests_aws4auth
    for explicit AWS SigV4 authentication with OpenSearch Serverless and provides
    methods to import saved objects via the Dashboards API.
    
    Attributes:
        endpoint: OpenSearch Serverless collection endpoint URL
        region: AWS region for SigV4 signing
        client: OpenSearch client instance with SigV4 authentication
    """
    
    # Service name for OpenSearch Serverless SigV4 signing
    # Use 'aoss' for OpenSearch Serverless (NOT 'es')
    AOSS_SERVICE_NAME = "opensearch"
    # Saved Objects API endpoint path
    IMPORT_API_PATH = "/api/saved_objects/_import"
    # Request timeout in seconds
    REQUEST_TIMEOUT = 300
    
    def __init__(
        self,
        endpoint: str,
        datasource_id: str,
        region: Optional[str] = None
    ) -> None:
        """
        Initialize OpenSearch Serverless client with opensearch-py and AWS4Auth.
        
        Args:
            endpoint: OpenSearch Serverless collection endpoint URL
                      (e.g., https://abc123.us-east-1.aoss.amazonaws.com)
            region: AWS region for SigV4 signing. If not provided,
                    uses AWS_REGION environment variable.
        """
        # Normalize endpoint URL (remove trailing slash)
        self.endpoint = endpoint.rstrip("/")
        
        # Set the datasource id as we are working with workspaces
        self.datasource_id = datasource_id

        # Determine region from parameter or environment
        self.region = region or os.environ.get("AWS_REGION", "ca-central-1")
        
        # Get boto3 session for credentials (reused across invocations)
        self._session = get_boto3_session()

        # Get credentials and extract explicit values for AWS4Auth
        credentials = self._session.get_credentials()
        if credentials is None:
            raise RuntimeError("Failed to obtain AWS credentials")
        
        # Create AWSV4SignerAuth for opensearch-py client
        awsauth = AWSV4SignerAuth(credentials, self.region, self.AOSS_SERVICE_NAME)
        
        # Create AWS4Auth for requests library (used for import API calls)
        # This is needed because the import API requires multipart form-data
        # which opensearch-py's transport.perform_request doesn't support
        self.awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.region,
            self.AOSS_SERVICE_NAME,
            session_token=credentials.token
        )

        # Initialize OpenSearch client with AWSV4SignerAuth authentication
        # Pass endpoint directly to hosts list as string
        self.client = OpenSearch(
            hosts=[{'host': self.endpoint, 'port': 443}],
            http_compress=True,
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=self.REQUEST_TIMEOUT,
            pool_maxsize=20
        )
        
        logger.info(
            "Initialized OpenSearch Serverless client with AWS4Auth: "
            "endpoint=%s, region=%s",
            self.endpoint,
            self.region
        )

    def import_saved_objects(
        self,
        ndjson_content: bytes,
        overwrite: bool = True
    ) -> ImportResult:
        """
        Import saved objects from NDJSON content.
        
        This method POSTs NDJSON content to the OpenSearch Dashboards
        Saved Objects Import API using the opensearch-py transport layer
        with AWS SigV4 authentication.
        
        Args:
            ndjson_content: NDJSON file content as bytes containing
                           saved objects (dashboards, visualizations, etc.)
            overwrite: If True, overwrites existing objects with same IDs.
                      Default is True.
                      
        Returns:
            ImportResult: Result containing success/failure counts and any errors
            
        Example:
            >>> client = OpenSearchClient("https://abc123.us-east-1.aoss.amazonaws.com")
            >>> with open("dashboard.ndjson", "rb") as f:
            ...     result = client.import_saved_objects(f.read())
            >>> print(f"Imported {result.success_count} objects")
        """
        logger.info(
            "Importing saved objects: endpoint=%s, overwrite=%s, content_size=%d bytes",
            self.endpoint,
            overwrite,
            len(ndjson_content)
        )
        
        # Build the full URL for the import API
        # self.endpoint already includes the protocol (e.g., https://abc123.us-east-1.aoss.amazonaws.com)
        url = f"{self.endpoint}{self.IMPORT_API_PATH}"
        logger.info(f"Import url: {url}")
        # Build query parameters
        
        params = {
            "overwrite": "true" if overwrite else "false",
            "dataSourceId": self.datasource_id,
            "dataSourceEnabled": "true"
        }
        logger.info(f"Params: {params}")

        # Set request headers for the Dashboards API
        # osd-xsrf header is required for OpenSearch Dashboards API
        # Note: Content-Type is automatically set by requests when using files=
        headers = {
            "osd-xsrf": "osd-fetch",
            "osd-version": "3.4.0"
        }
        
        # Create multipart form-data with file field
        # The import API expects the NDJSON content as a file upload
        files = {
            "file": ("saved_objects.ndjson", BytesIO(ndjson_content), "application/x-ndjson")
        }
        
        try:
            logger.debug(
                "Sending POST request to %s with requests library (multipart form-data)",
                url
            )
            
            # Use requests library directly for multipart form-data support
            # AWS4Auth handles SigV4 signing for the request
            response = requests.post(
                url,
                params=params,
                files=files,
                headers=headers,
                auth=self.awsauth,
                timeout=self.REQUEST_TIMEOUT
            )
            
            logger.debug(
                "Received response from OpenSearch: status_code=%d",
                response.status_code
            )
            
            # Check for HTTP errors
            if not response.ok:
                error_msg = f"HTTP error {response.status_code}: {response.text}"
                logger.error("Import request failed: %s", error_msg)
                return ImportResult(
                    success=False,
                    error_count=1,
                    errors=[{
                        "type": "http_error",
                        "status_code": response.status_code,
                        "message": response.text
                    }],
                    message=error_msg
                )
            
            # Parse JSON response
            data = response.json()
            return self._parse_import_response(data)
            
        except ConnectionTimeout as e:
            error_msg = f"Request timed out after {self.REQUEST_TIMEOUT} seconds: {str(e)}"
            logger.error(error_msg)
            return ImportResult(
                success=False,
                error_count=1,
                errors=[{"type": "timeout", "message": error_msg}],
                message=error_msg
            )
            
        except OSConnectionError as e:
            error_msg = f"Connection error to OpenSearch endpoint: {str(e)}"
            logger.error(error_msg)
            return ImportResult(
                success=False,
                error_count=1,
                errors=[{"type": "connection_error", "message": str(e)}],
                message=error_msg
            )
            
        except TransportError as e:
            # TransportError includes HTTP errors with status codes
            error_msg = f"Transport error (status={e.status_code}): {str(e)}"
            logger.error("Import request failed: %s", error_msg)
            return ImportResult(
                success=False,
                error_count=1,
                errors=[{
                    "type": "http_error",
                    "status_code": e.status_code,
                    "message": str(e.info) if e.info else str(e)
                }],
                message=error_msg
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during import: {str(e)}"
            logger.exception(error_msg)
            return ImportResult(
                success=False,
                error_count=1,
                errors=[{"type": "unexpected_error", "message": str(e)}],
                message=error_msg
            )
    
    def _parse_import_response(self, data: Dict[str, Any]) -> ImportResult:
        """
        Parse the import API response.
        
        The import API returns JSON with the following structure:
        {
            "success": true/false,
            "successCount": 5,
            "errors": [
                {
                    "id": "object-id",
                    "type": "dashboard",
                    "error": { "type": "conflict", "message": "..." }
                }
            ]
        }
        
        Args:
            data: Parsed JSON response from the import API
            
        Returns:
            ImportResult: Parsed result with success/error counts
        """
        # Extract success count
        success_count = data.get("successCount", 0)
        
        # Extract errors
        errors = data.get("errors", [])
        error_count = len(errors)
        
        # Determine overall success
        # Import is successful if there are no errors and at least one object imported
        success = error_count == 0 and success_count > 0
        
        # Build message
        if success:
            message = f"Successfully imported {success_count} saved object(s)"
            logger.info(message)
        elif success_count > 0 and error_count > 0:
            message = f"Partial import: {success_count} succeeded, {error_count} failed"
            logger.warning(message)
            for error in errors:
                logger.warning(
                    "Import error: id=%s, type=%s, error=%s",
                    error.get("id", "unknown"),
                    error.get("type", "unknown"),
                    error.get("error", {})
                )
        else:
            message = f"Import failed with {error_count} error(s)"
            logger.error(message)
            for error in errors:
                logger.error(
                    "Import error: id=%s, type=%s, error=%s",
                    error.get("id", "unknown"),
                    error.get("type", "unknown"),
                    error.get("error", {})
                )
        
        return ImportResult(
            success=success,
            success_count=success_count,
            error_count=error_count,
            errors=errors,
            message=message
        )
    
    def health_check(self) -> bool:
        """
        Perform a health check on the OpenSearch Serverless endpoint.
        
        This method sends a simple GET request to verify connectivity
        and authentication to the OpenSearch endpoint using the
        opensearch-py client.
        
        Returns:
            bool: True if the endpoint is reachable and authenticated,
                  False otherwise
        """
        try:
            # Use the info() method to check connectivity
            # This calls the root endpoint and returns cluster info
            info = self.client.info()
            
            if info:
                logger.info(
                    "Health check passed for endpoint: %s, cluster_name=%s",
                    self.endpoint,
                    info.get("cluster_name", "unknown")
                )
                return True
            else:
                logger.warning("Health check returned empty response")
                return False
                
        except TransportError as e:
            logger.warning(
                "Health check failed: status_code=%s, error=%s",
                e.status_code,
                str(e)
            )
            return False
            
        except Exception as e:
            logger.error("Health check error: %s", str(e))
            return False