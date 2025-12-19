# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
OpenSearch Serverless Client Helper for Workspace Operations

This module handles creating, updating, and deleting OpenSearch workspaces
via the Workspaces API using AWS SigV4 authentication.

OpenSearch Serverless uses 'aoss' as the service name for SigV4 signing.
Endpoint format: https://{application-id}.{region}.es.amazonaws.com
Workspace API: /api/workspaces

This implementation uses the opensearch-py library with AWSV4SignerAuth
for AWS SigV4 authentication support with OpenSearch Serverless.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import requests
from requests_aws4auth import AWS4Auth
import boto3
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
class WorkspaceResult:
    """Result of a workspace operation."""
    
    success: bool
    workspace_id: Optional[str] = None
    message: str = ""
    error_code: Optional[str] = None
    response_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "workspaceId": self.workspace_id,
            "message": self.message,
            "errorCode": self.error_code,
            "responseData": self.response_data
        }


class OpenSearchClient:
    """
    OpenSearch Serverless client for workspace operations.
    
    This client uses the opensearch-py library with AWSV4SignerAuth
    for AWS SigV4 authentication with OpenSearch Serverless and provides
    methods to create, update, delete, and get workspaces via the Workspaces API.
    
    Attributes:
        endpoint: OpenSearch Serverless application endpoint URL
        region: AWS region for SigV4 signing
        client: OpenSearch client instance with SigV4 authentication
    """
    
    # Service name for OpenSearch Serverless SigV4 signing
    # Use 'es' for OpenSearch managed/application endpoints
    ES_SERVICE_NAME = "opensearch"
    
    # Workspace API endpoint path
    WORKSPACE_API_PATH = "/api/workspaces"
    
    # Request timeout in seconds
    REQUEST_TIMEOUT = 300
    
    def __init__(
        self,
        endpoint: str,
        region: Optional[str] = None
    ) -> None:
        """
        Initialize OpenSearch Serverless client with opensearch-py and AWSV4SignerAuth.
        
        Args:
            endpoint: OpenSearch application endpoint URL
                      (e.g., https://<application-id>.<region>.es.amazonaws.com)
            region: AWS region for SigV4 signing. If not provided,
                    uses AWS_REGION environment variable.
        """
        # Normalize endpoint URL (remove trailing slash and protocol)
        self.endpoint = endpoint.rstrip("/")
        
        # Extract host from endpoint URL for OpenSearch client
        if self.endpoint.startswith("https://"):
            self.host = self.endpoint[8:]  # Remove https://
        elif self.endpoint.startswith("http://"):
            self.host = self.endpoint[7:]  # Remove http://
        else:
            self.host = self.endpoint
        
        logger.info("OpenSearch Serverless endpoint: %s", self.endpoint)
        logger.info("OpenSearch Serverless host: %s", self.host)

        # Determine region from parameter or environment
        self.region = region or os.environ.get("AWS_REGION", "ca-central-1")
        
        # Get boto3 session for credentials (reused across invocations)
        self._session = get_boto3_session()
        
        # Get credentials
        credentials = self._session.get_credentials()
        if credentials is None:
            raise RuntimeError("Failed to obtain AWS credentials")
        
        # Create AWSV4SignerAuth for opensearch-py client
        awsauth = AWSV4SignerAuth(credentials, self.region, self.ES_SERVICE_NAME)
        
        # Create AWS4Auth for requests library (used for import API calls)
        # This is needed because the import API requires multipart form-data
        # which opensearch-py's transport.perform_request doesn't support
        self.awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            self.region,
            self.ES_SERVICE_NAME,
            session_token=credentials.token
        )
        logger.info(f"Signed request with service name: {self.ES_SERVICE_NAME}")
        # Initialize OpenSearch client with AWSV4SignerAuth authentication
        self.client = OpenSearch(
            hosts = [{'host': self.host, 'port': 443}],
            http_auth = awsauth,
            use_ssl = True,
            verify_certs = True,
            connection_class = RequestsHttpConnection,
            pool_maxsize = 20
        )
        
        logger.info(
            "Initialized OpenSearch client with AWSV4SignerAuth: "
            "endpoint=%s, host=%s, region=%s",
            self.endpoint,
            self.host,
            self.region
        )
    
    def _build_workspace_request_body(
        self,
        name: str,
        description: Optional[str] = None,
        color: str = "#54B399",
        features: Optional[List[str]] = None,
        data_source_ids: Optional[List[str]] = None,
        permissions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build the workspace request body for create/update operations.
        
        Args:
            name: Workspace name
            description: Workspace description (optional)
            color: Workspace color code (default: "#54B399")
            features: List of features (e.g., ["use-case-observability"])
            data_source_ids: List of data source IDs to connect
            permissions: Permission settings (optional)
            
        Returns:
            Dict containing the workspace request body
        """
        # Build attributes section
        attributes = {
            "name": name,
            "color": color
        }
        
        if description:
            attributes["description"] = description
        
        # Always include features as an array (required by workspace API)
        # Default to empty array if not provided
        attributes["features"] = features if features else [ "use-case-all" ]
        
        # Build settings section
        settings: Dict[str, Any] = {
            "dataConnections": []
        }
        
        if data_source_ids:
            settings["dataSources"] = data_source_ids
        else:
            settings["dataSources"] = []
            
        if permissions:
            settings["permissions"] = permissions
        else:
            # Default permissions - current user has write access
            settings["permissions"] = {
                "library_write": {
                    "users": ["%me%"]
                },
                "write": {
                    "users": ["%me%"]
                }
            }
        
        return {
            "attributes": attributes,
            "settings": settings
        }
    
    def _perform_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform an HTTP request using opensearch-py client's transport.
        
        This method uses the OpenSearch client's transport layer which handles
        AWS SigV4 authentication via AWSV4SignerAuth automatically.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., /api/workspaces)
            body: Request body as dictionary (optional)
            params: Query parameters (optional)
            
        Returns:
            Dict containing the JSON response
            
        Raises:
            TransportError: On HTTP errors
            ConnectionTimeout: On timeout
            OSConnectionError: On connection issues
        """
        logger.debug(
            "Performing %s request to %s with body: %s",
            method,
            path,
            json.dumps(body, indent=2) if body else "None"
        )
        
        logger.info("Performing %s request to: %s%s", method, self.endpoint, path)
        
        # Build headers for OpenSearch Dashboards API
        headers = {
            "osd-xsrf": "true"
        }
        
        # Use opensearch-py client's transport.perform_request()
        # The transport handles AWS SigV4 authentication automatically
        response = self.client.transport.perform_request(
            method=method.upper(),
            url=path,
            body=body,
            params=params,
            headers=headers,
            timeout=self.REQUEST_TIMEOUT
        )
        
        logger.debug(
            "Received response from OpenSearch: %s",
            str(response)[:500] if len(str(response)) > 500 else str(response)
        )
        
        logger.info(f"response {response}")
        return response
        
        # -------------------------------------------------------------------
        # COMMENTED OUT: Previous implementation using requests library
        # -------------------------------------------------------------------
        # # Build headers for OpenSearch Dashboards API
        # headers = {
        #     "osd-xsrf": "true",
        #     "Content-Type": "application/json"
        # }
        #
        # # Build the full URL
        # url = self.endpoint + path
        # logger.info("Performing %s request to: %s", method, url)
        #
        # # Select the appropriate requests method based on HTTP method
        # method_upper = method.upper()
        #
        # if method_upper == "GET":
        #     response = requests.get(
        #         url,
        #         params=params,
        #         headers=headers,
        #         auth=self.awsauth,
        #         timeout=self.REQUEST_TIMEOUT
        #     )
        # elif method_upper == "POST":
        #     response = requests.post(
        #         url,
        #         json=body,
        #         params=params,
        #         headers=headers,
        #         auth=self.awsauth,
        #         timeout=self.REQUEST_TIMEOUT
        #     )
        # elif method_upper == "PUT":
        #     response = requests.put(
        #         url,
        #         json=body,
        #         params=params,
        #         headers=headers,
        #         auth=self.awsauth,
        #         timeout=self.REQUEST_TIMEOUT
        #     )
        # elif method_upper == "DELETE":
        #     response = requests.delete(
        #         url,
        #         params=params,
        #         headers=headers,
        #         auth=self.awsauth,
        #         timeout=self.REQUEST_TIMEOUT
        #     )
        # else:
        #     raise ValueError(f"Unsupported HTTP method: {method}")
        #
        # logger.debug(
        #     "Received response from OpenSearch: status_code=%d, body=%s",
        #     response.status_code,
        #     response.text[:500] if len(response.text) > 500 else response.text
        # )
        #
        # # Check for HTTP errors and return JSON response
        # if not response.ok:
        #     logger.error(
        #         "HTTP error %d: %s",
        #         response.status_code,
        #         response.text
        #     )
        #     # Raise a TransportError-like exception for consistent handling
        #     raise TransportError(
        #         response.status_code,
        #         response.text,
        #         {"response": response.text}
        #     )
        #
        # # Parse and return JSON response
        # try:
        #     logger.info(f"response {response.text}")
        #     return response.json()
        # except json.JSONDecodeError:
        #     # If response is not JSON, return it as a dict with text content
        #     return {"text": response.text, "status_code": response.status_code}
    
    def create_workspace(
        self,
        name: str,
        description: Optional[str] = None,
        color: str = "#54B399",
        features: Optional[List[str]] = None,
        data_source_ids: Optional[List[str]] = None,
        permissions: Optional[Dict[str, Any]] = None
    ) -> WorkspaceResult:
        """
        Create a new workspace in OpenSearch Dashboards.
        
        Args:
            name: Workspace name
            description: Workspace description (optional)
            color: Workspace color code (default: "#54B399")
            features: List of features (e.g., ["use-case-observability"])
            data_source_ids: List of data source IDs to connect
            permissions: Permission settings (optional)
            
        Returns:
            WorkspaceResult: Result containing workspace ID on success
        """
        logger.info(
            "Creating workspace: name=%s, endpoint=%s",
            name,
            self.endpoint
        )
        
        # Build request body
        request_body = self._build_workspace_request_body(
            name=name,
            description=description,
            color=color,
            features=features,
            data_source_ids=data_source_ids,
            permissions=permissions
        )
        
        try:
            response = self._perform_request(
                method="POST",
                path=self.WORKSPACE_API_PATH,
                body=request_body
            )
            
            return self._parse_workspace_response(response, "create")
            
        except ConnectionTimeout as e:
            error_msg = f"Request timed out after {self.REQUEST_TIMEOUT} seconds: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="TIMEOUT"
            )
            
        except OSConnectionError as e:
            error_msg = f"Connection error to OpenSearch endpoint: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="CONNECTION_ERROR"
            )
            
        except TransportError as e:
            error_msg = f"HTTP error {e.status_code}: {str(e.info) if e.info else str(e)}"
            logger.error("Create workspace request failed: %s", error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code=f"HTTP_{e.status_code}",
                response_data={"status_code": e.status_code, "body": str(e.info) if e.info else str(e)}
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during workspace creation: {str(e)}"
            logger.exception(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="UNEXPECTED_ERROR"
            )
    
    def update_workspace(
        self,
        workspace_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        features: Optional[List[str]] = None,
        data_source_ids: Optional[List[str]] = None,
        permissions: Optional[Dict[str, Any]] = None
    ) -> WorkspaceResult:
        """
        Update an existing workspace in OpenSearch Dashboards.
        
        Args:
            workspace_id: ID of the workspace to update
            name: New workspace name (optional)
            description: New workspace description (optional)
            color: New workspace color code (optional)
            features: New list of features (optional)
            data_source_ids: New list of data source IDs (optional)
            permissions: New permission settings (optional)
            
        Returns:
            WorkspaceResult: Result of the update operation
        """
        logger.info(
            "Updating workspace: workspace_id=%s, endpoint=%s",
            workspace_id,
            self.endpoint
        )
        
        # Build attributes section with only provided values
        attributes: Dict[str, Any] = {}
        if name is not None:
            attributes["name"] = name
        if description is not None:
            attributes["description"] = description
        if color is not None:
            attributes["color"] = color
        if features is not None:
            attributes["features"] = features
        
        # Build settings section with only provided values
        settings: Dict[str, Any] = {}
        if data_source_ids is not None:
            settings["dataSources"] = data_source_ids
        if permissions is not None:
            settings["permissions"] = permissions
        
        # Build request body
        request_body: Dict[str, Any] = {}
        if attributes:
            request_body["attributes"] = attributes
        if settings:
            request_body["settings"] = settings
        
        # Build the path for the workspace API
        path = f"{self.WORKSPACE_API_PATH}/{workspace_id}"
        
        try:
            response = self._perform_request(
                method="PUT",
                path=path,
                body=request_body
            )
            
            result = self._parse_workspace_response(response, "update")
            result.workspace_id = workspace_id
            return result
            
        except ConnectionTimeout as e:
            error_msg = f"Request timed out after {self.REQUEST_TIMEOUT} seconds: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="TIMEOUT"
            )
            
        except OSConnectionError as e:
            error_msg = f"Connection error to OpenSearch endpoint: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="CONNECTION_ERROR"
            )
            
        except TransportError as e:
            error_msg = f"HTTP error {e.status_code}: {str(e.info) if e.info else str(e)}"
            logger.error("Update workspace request failed: %s", error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code=f"HTTP_{e.status_code}",
                response_data={"status_code": e.status_code, "body": str(e.info) if e.info else str(e)}
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during workspace update: {str(e)}"
            logger.exception(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="UNEXPECTED_ERROR"
            )
    
    def delete_workspace(self, workspace_id: str) -> WorkspaceResult:
        """
        Delete a workspace from OpenSearch Dashboards.
        
        Args:
            workspace_id: ID of the workspace to delete
            
        Returns:
            WorkspaceResult: Result of the delete operation
        """
        logger.info(
            "Deleting workspace: workspace_id=%s, endpoint=%s",
            workspace_id,
            self.endpoint
        )
        
        # Build the path for the workspace API
        path = f"{self.WORKSPACE_API_PATH}/{workspace_id}"
        
        try:
            response = self._perform_request(
                method="DELETE",
                path=path
            )
            
            result = self._parse_workspace_response(response, "delete")
            result.workspace_id = workspace_id
            return result
            
        except TransportError as e:
            # 404 on delete is acceptable - workspace already deleted
            if e.status_code == 404:
                logger.info(
                    "Workspace %s not found (already deleted), treating as success",
                    workspace_id
                )
                return WorkspaceResult(
                    success=True,
                    workspace_id=workspace_id,
                    message=f"Workspace {workspace_id} not found (already deleted)"
                )
                
            error_msg = f"HTTP error {e.status_code}: {str(e.info) if e.info else str(e)}"
            logger.error("Delete workspace request failed: %s", error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code=f"HTTP_{e.status_code}",
                response_data={"status_code": e.status_code, "body": str(e.info) if e.info else str(e)}
            )
            
        except ConnectionTimeout as e:
            error_msg = f"Request timed out after {self.REQUEST_TIMEOUT} seconds: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="TIMEOUT"
            )
            
        except OSConnectionError as e:
            error_msg = f"Connection error to OpenSearch endpoint: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="CONNECTION_ERROR"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during workspace deletion: {str(e)}"
            logger.exception(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="UNEXPECTED_ERROR"
            )
    
    def get_workspace(self, workspace_id: str) -> WorkspaceResult:
        """
        Get details of an existing workspace.
        
        Args:
            workspace_id: ID of the workspace to retrieve
            
        Returns:
            WorkspaceResult: Result containing workspace details on success
        """
        logger.info(
            "Getting workspace: workspace_id=%s, endpoint=%s",
            workspace_id,
            self.endpoint
        )
        
        # Build the path for the workspace API
        path = f"{self.WORKSPACE_API_PATH}/{workspace_id}"
        
        try:
            response = self._perform_request(
                method="GET",
                path=path
            )
            
            result = self._parse_workspace_response(response, "get")
            result.workspace_id = workspace_id
            return result
            
        except TransportError as e:
            error_msg = f"HTTP error {e.status_code}: {str(e.info) if e.info else str(e)}"
            logger.error("Get workspace request failed: %s", error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code=f"HTTP_{e.status_code}",
                response_data={"status_code": e.status_code, "body": str(e.info) if e.info else str(e)}
            )
            
        except ConnectionTimeout as e:
            error_msg = f"Request timed out after {self.REQUEST_TIMEOUT} seconds: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="TIMEOUT"
            )
            
        except OSConnectionError as e:
            error_msg = f"Connection error to OpenSearch endpoint: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="CONNECTION_ERROR"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during workspace retrieval: {str(e)}"
            logger.exception(error_msg)
            return WorkspaceResult(
                success=False,
                workspace_id=workspace_id,
                message=error_msg,
                error_code="UNEXPECTED_ERROR"
            )
    
    def list_workspaces(
        self,
        per_page: int = 100,
        page: int = 1
    ) -> WorkspaceResult:
        """
        List all workspaces in OpenSearch Dashboards.
        
        Uses the GET /api/workspaces/_list endpoint to retrieve workspaces.
        
        Args:
            per_page: Number of workspaces per page (default: 100)
            page: Page number for pagination (default: 1)
            
        Returns:
            WorkspaceResult: Result containing list of workspaces in response_data
        """
        logger.info(
            "Listing workspaces: endpoint=%s, per_page=%d, page=%d",
            self.endpoint,
            per_page,
            page
        )
        
        # Build the path for the workspace list API
        path = f"{self.WORKSPACE_API_PATH}/_list"
        
        # Set query parameters
        params = {
            "perPage": per_page,
        }
        
        try:
            response = self._perform_request(
                method="POST",
                path=path,
                params=params,
                body={}
            )
            
            return self._parse_list_response(response)
            
        except TransportError as e:
            error_msg = f"HTTP error {e.status_code}: {str(e.info) if e.info else str(e)}"
            logger.error("List workspaces request failed: %s", error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code=f"HTTP_{e.status_code}",
                response_data={"status_code": e.status_code, "body": str(e.info) if e.info else str(e)}
            )
            
        except ConnectionTimeout as e:
            error_msg = f"Request timed out after {self.REQUEST_TIMEOUT} seconds: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="TIMEOUT"
            )
            
        except OSConnectionError as e:
            error_msg = f"Connection error to OpenSearch endpoint: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="CONNECTION_ERROR"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during workspace listing: {str(e)}"
            logger.exception(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="UNEXPECTED_ERROR"
            )
    
    def find_workspace_by_name(self, name: str) -> WorkspaceResult:
        """
        Find a workspace by its name.
        
        This method lists all workspaces and searches for one matching the given name.
        Useful for finding workspace IDs when only the name is known.
        
        Args:
            name: Name of the workspace to find
            
        Returns:
            WorkspaceResult: Result containing workspace details if found,
                            or failure if not found
        """
        logger.info("Finding workspace by name: %s", name)
        
        # List all workspaces
        list_result = self.list_workspaces(per_page=1000)
        
        if not list_result.success:
            return list_result
        
        # Search for workspace by name
        workspaces = list_result.response_data.get("result", {}).get("workspaces", [])
        
        for workspace in workspaces:
            if workspace.get("name") == name:
                workspace_id = workspace.get("id")
                logger.info(
                    "Found workspace: name=%s, id=%s",
                    name,
                    workspace_id
                )
                return WorkspaceResult(
                    success=True,
                    workspace_id=workspace_id,
                    message=f"Found workspace: {name}",
                    response_data=workspace
                )
        
        # Workspace not found
        logger.info("Workspace not found: name=%s", name)
        return WorkspaceResult(
            success=False,
            message=f"Workspace not found: {name}",
            error_code="NOT_FOUND"
        )
    
    def _parse_list_response(self, data: Dict[str, Any]) -> WorkspaceResult:
        """
        Parse the workspace list API response.
        
        The workspace list API returns JSON with the following structure on success:
        {
            "success": true,
            "result": {
                "workspaces": [
                    {"id": "...", "name": "...", ...},
                    ...
                ],
                "total": 10
            }
        }
        
        Args:
            data: Parsed JSON response from the workspace list API
            
        Returns:
            WorkspaceResult: Parsed result containing workspace list
        """
        # Check if the API response indicates success
        api_success = data.get("success", False)
        
        if api_success:
            result = data.get("result", {})
            workspaces = result.get("workspaces", [])
            total = result.get("total", len(workspaces))
            
            message = f"Listed {len(workspaces)} workspaces (total: {total})"
            logger.info(message)
            
            return WorkspaceResult(
                success=True,
                message=message,
                response_data=data
            )
        else:
            # Extract error information
            error_msg = data.get("error", "Unknown error during workspace listing")
            logger.error("Workspace listing failed: %s", error_msg)
            
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="API_ERROR",
                response_data=data
            )
    
    def _parse_workspace_response(
        self,
        data: Dict[str, Any],
        operation: str
    ) -> WorkspaceResult:
        """
        Parse the workspace API response.
        
        The workspace API returns JSON with the following structure on success:
        {
            "success": true,
            "result": {
                "id": "workspace-id"
            }
        }
        
        On error:
        {
            "success": false,
            "error": "error message"
        }
        
        Args:
            data: Parsed JSON response from the workspace API
            operation: The operation being performed (create, update, delete, get)
            
        Returns:
            WorkspaceResult: Parsed result
        """
        # Check if the API response indicates success
        api_success = data.get("success", False)
        
        if api_success:
            # Extract workspace ID from result if present
            result = data.get("result", {})
            workspace_id = result.get("id") if isinstance(result, dict) else None
            
            message = f"Workspace {operation} completed successfully"
            if workspace_id:
                message = f"Workspace {operation} completed successfully: id={workspace_id}"
                
            logger.info(message)
            
            return WorkspaceResult(
                success=True,
                workspace_id=workspace_id,
                message=message,
                response_data=data
            )
        else:
            # Extract error information
            error_msg = data.get("error", f"Unknown error during {operation}")
            
            logger.error("Workspace %s failed: %s", operation, error_msg)
            
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="API_ERROR",
                response_data=data
            )
    
    # Data sources API endpoint for saved_objects/_find query
    # Query parameters to find both data-source and data-connection objects
    SAVED_OBJECTS_FIND_PATH = "/api/saved_objects/_find"

    def list_data_sources(self) -> WorkspaceResult:
        """
        List all data sources registered in OpenSearch Dashboards.
        
        Uses the GET /api/saved_objects/_find endpoint to retrieve all registered
        data sources and data connections including their UUIDs, titles, and metadata.
        
        The query finds saved objects of type 'data-source' and 'data-connection'
        with relevant fields: id, title, auth, description, dataSourceEngineType,
        type, and connectionId.
        
        Returns:
            WorkspaceResult: Result containing list of data sources in response_data
                            with structure: {"data_sources": [{"id": "uuid", "attributes": {...}, ...}, ...]}
        """
        logger.info("Listing data sources via saved_objects/_find: endpoint=%s", self.endpoint)
        
        # Build query parameters for data source search
        # Note: We need to build the URL with multiple same-named parameters
        # since perform_request doesn't handle this well
        params_list = [
            ("per_page", "10000"),
            ("fields", "id"),
            ("fields", "title"),
            ("type", "data-source"),
            ("type", "data-connection")
        ]
        
        # Build query string manually for multiple same-named params
        query_string = "&".join([f"{k}={v}" for k, v in params_list])
        path_with_params = f"{self.SAVED_OBJECTS_FIND_PATH}?{query_string}"
        
        try:
            response = self._perform_request(
                method="GET",
                path=path_with_params
            )
            logger.info(f"response {response}")
            # Extract saved_objects array from response
            if isinstance(response, dict) and "saved_objects" in response:
                data_sources = response["saved_objects"]
                total = response.get("total", len(data_sources))
            elif isinstance(response, list):
                # Fallback if API returns array directly
                data_sources = response
                total = len(data_sources)
            else:
                data_sources = []
                total = 0
            
            logger.info(
                "Listed %d data sources (total: %d)",
                len(data_sources),
                total
            )
            
            return WorkspaceResult(
                success=True,
                message=f"Listed {len(data_sources)} data sources (total: {total})",
                response_data={"data_sources": data_sources, "total": total}
            )
            
        except TransportError as e:
            error_msg = f"HTTP error {e.status_code}: {str(e.info) if e.info else str(e)}"
            logger.error("List data sources request failed: %s", error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code=f"HTTP_{e.status_code}",
                response_data={"status_code": e.status_code, "body": str(e.info) if e.info else str(e)}
            )
            
        except ConnectionTimeout as e:
            error_msg = f"Request timed out after {self.REQUEST_TIMEOUT} seconds: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="TIMEOUT"
            )
            
        except OSConnectionError as e:
            error_msg = f"Connection error to OpenSearch endpoint: {str(e)}"
            logger.error(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="CONNECTION_ERROR"
            )
            
        except Exception as e:
            error_msg = f"Unexpected error during data sources listing: {str(e)}"
            logger.exception(error_msg)
            return WorkspaceResult(
                success=False,
                message=error_msg,
                error_code="UNEXPECTED_ERROR"
            )
    
    def find_data_source_by_collection_arn(self, collection_arn: str) -> WorkspaceResult:
        """
        Find a data source by its associated OpenSearch collection ARN.
        
        This method lists all data sources and searches for one whose endpoint
        or reference matches the given collection ARN. The data source ID (UUID)
        is generated by OpenSearch when the collection is registered and cannot
        be derived from the collection attributes directly.
        
        Args:
            collection_arn: ARN of the OpenSearch collection
                           (e.g., arn:aws:aoss:region:account:collection/id)
            
        Returns:
            WorkspaceResult: Result containing data source details if found,
                            with workspace_id set to the data source UUID,
                            or failure if not found
        """
        logger.info("Finding data source by collection ARN: %s", collection_arn)
        
        # List all data sources
        list_result = self.list_data_sources()
        
        if not list_result.success:
            return list_result
        
        # Get data sources list
        data_sources = list_result.response_data.get("data_sources", [])
        
        if not isinstance(data_sources, list):
            logger.warning("Unexpected data sources format: %s", type(data_sources))
            return WorkspaceResult(
                success=False,
                message="Unexpected data sources response format",
                error_code="INVALID_RESPONSE"
            )
        
        # Extract collection ID from ARN for matching
        # ARN format: arn:aws:aoss:region:account:collection/collection-id
        collection_id = None
        if "/" in collection_arn:
            collection_id = collection_arn.split("/")[-1]
        
        logger.debug(
            "Searching %d data sources for collection: arn=%s, id=%s",
            len(data_sources),
            collection_arn,
            collection_id
        )
        
        # Search for matching data source
        for data_source in data_sources:
            ds_id = data_source.get("id")
            ds_title = data_source.get("title", "")
            ds_attributes = data_source.get("attributes", {})
            ds_endpoint = ds_attributes.get("endpoint", data_source.get("endpoint", ""))
            ds_description = ds_attributes.get(
                "description", data_source.get("description", "")
            )
            
            logger.debug(
                "Checking data source: id=%s, title=%s, endpoint=%s",
                ds_id,
                ds_title,
                ds_endpoint
            )
            
            # Match by ARN in various fields
            match_found = False
            match_reason = ""
            
            # Check if ARN is in the endpoint
            if collection_arn in str(ds_endpoint):
                match_found = True
                match_reason = "ARN found in endpoint"
            
            # Check if ARN is in the description
            elif collection_arn in str(ds_description):
                match_found = True
                match_reason = "ARN found in description"
            
            # Check if collection ID is in the endpoint URL
            elif collection_id and collection_id in str(ds_endpoint):
                match_found = True
                match_reason = "Collection ID found in endpoint"
            
            # Check if ARN is stored directly as a reference
            elif data_source.get("dataSourceArn") == collection_arn:
                match_found = True
                match_reason = "ARN matches dataSourceArn"
            
            # Check references array if present
            elif "references" in data_source:
                for ref in data_source.get("references", []):
                    if collection_arn in str(ref) or (
                        collection_id and collection_id in str(ref)
                    ):
                        match_found = True
                        match_reason = "ARN/ID found in references"
                        break
            
            if match_found:
                logger.info(
                    "Found matching data source: id=%s, title=%s, reason=%s",
                    ds_id,
                    ds_title,
                    match_reason
                )
                return WorkspaceResult(
                    success=True,
                    workspace_id=ds_id,  # Reusing workspace_id field for data source ID
                    message=f"Found data source: {ds_title} ({match_reason})",
                    response_data=data_source
                )
        
        # Data source not found
        logger.warning(
            "Data source not found for collection ARN: %s (searched %d data sources)",
            collection_arn,
            len(data_sources)
        )
        return WorkspaceResult(
            success=False,
            message=f"Data source not found for collection ARN: {collection_arn}",
            error_code="NOT_FOUND"
        )
    
    def find_data_source_by_title(self, title: str) -> WorkspaceResult:
        """
        Find a data source by its title/name.
        
        This method lists all data sources and searches for one matching
        the given title. Useful when you know the display name of the
        data source but need its UUID.
        
        Args:
            title: Title/name of the data source to find
            
        Returns:
            WorkspaceResult: Result containing data source details if found,
                            with workspace_id set to the data source UUID,
                            or failure if not found
        """
        logger.info("Finding data source by title: %s", title)
        
        # List all data sources
        list_result = self.list_data_sources()
        
        if not list_result.success:
            return list_result
        
        # Get data sources list
        data_sources = list_result.response_data.get("data_sources", [])
        
        if not isinstance(data_sources, list):
            logger.warning("Unexpected data sources format: %s", type(data_sources))
            return WorkspaceResult(
                success=False,
                message="Unexpected data sources response format",
                error_code="INVALID_RESPONSE"
            )
        
        # Search for matching data source by title
        for data_source in data_sources:
            ds_id = data_source.get("id")
            ds_title = data_source.get("title", "")
            ds_attributes = data_source.get("attributes", {})
            ds_attr_title = ds_attributes.get("title", "")
            
            # Check both top-level title and attributes.title
            if ds_title == title or ds_attr_title == title:
                logger.info(
                    "Found data source by title: id=%s, title=%s",
                    ds_id,
                    title
                )
                return WorkspaceResult(
                    success=True,
                    workspace_id=ds_id,  # Reusing workspace_id field for data source ID
                    message=f"Found data source: {title}",
                    response_data=data_source
                )
        
        # Data source not found
        logger.warning(
            "Data source not found with title: %s (searched %d data sources)",
            title,
            len(data_sources)
        )
        return WorkspaceResult(
            success=False,
            message=f"Data source not found with title: {title}",
            error_code="NOT_FOUND"
        )
    
    def health_check(self) -> bool:
        """
        Perform a health check on the OpenSearch endpoint.
        
        This method uses the OpenSearch client's info() method to verify
        connectivity and authentication to the OpenSearch endpoint.
        
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
