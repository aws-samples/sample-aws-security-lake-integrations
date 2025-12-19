# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
OpenSearch Workspace Creator Lambda Handler

This Lambda function handles CloudFormation custom resource events to create,
update, and delete OpenSearch workspaces via the Workspaces API.

The handler supports Create, Update, and Delete operations:
- Create: Creates a new workspace with the specified configuration
- Update: Updates an existing workspace
- Delete: Deletes the workspace
"""

import json
import logging
import os
import urllib.request
from typing import Any, Dict, List, Optional

from helpers.opensearch_client import OpenSearchClient, WorkspaceResult

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# CloudFormation response status constants
SUCCESS = "SUCCESS"
FAILED = "FAILED"


def send_cfn_response(
    event: Dict[str, Any],
    context: Any,
    status: str,
    data: Optional[Dict[str, Any]] = None,
    physical_resource_id: Optional[str] = None,
    reason: Optional[str] = None
) -> None:
    """
    Send response to CloudFormation via the pre-signed S3 URL.
    
    This function uses urllib (standard library) to avoid external dependencies
    for the CloudFormation response mechanism.
    
    Args:
        event: CloudFormation custom resource event containing ResponseURL
        context: Lambda execution context
        status: Response status (SUCCESS or FAILED)
        data: Optional response data dictionary
        physical_resource_id: Physical resource identifier for CloudFormation
        reason: Optional reason string for failures
    """
    response_url = event.get("ResponseURL")
    if not response_url:
        logger.error("No ResponseURL found in event - cannot send response to CloudFormation")
        return
    
    # Build response body
    response_body = {
        "Status": status,
        "Reason": reason or f"See CloudWatch Log Stream: {context.log_stream_name}",
        "PhysicalResourceId": physical_resource_id or context.log_stream_name,
        "StackId": event.get("StackId"),
        "RequestId": event.get("RequestId"),
        "LogicalResourceId": event.get("LogicalResourceId"),
        "Data": data or {}
    }
    
    json_body = json.dumps(response_body).encode("utf-8")
    
    logger.info(
        "Sending CloudFormation response: status=%s, physical_resource_id=%s",
        status,
        response_body["PhysicalResourceId"]
    )
    logger.debug("Response body: %s", json.dumps(response_body, indent=2))
    
    try:
        request = urllib.request.Request(
            response_url,
            data=json_body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(json_body))
            },
            method="PUT"
        )
        
        with urllib.request.urlopen(request, timeout=30) as response:
            logger.info(
                "CloudFormation response sent successfully: status_code=%d",
                response.status
            )
            
    except urllib.error.URLError as e:
        logger.error("Failed to send CloudFormation response: %s", str(e))
    except Exception as e:
        logger.exception("Unexpected error sending CloudFormation response: %s", str(e))


def get_physical_resource_id(workspace_name: str, workspace_id: Optional[str] = None) -> str:
    """
    Generate a stable physical resource ID for the custom resource.
    
    Args:
        workspace_name: Name of the workspace
        workspace_id: Optional workspace ID if already created
        
    Returns:
        str: Physical resource ID
    """
    if workspace_id:
        return f"workspace-{workspace_id}"
    
    # Sanitize workspace name for use in resource ID
    sanitized_name = workspace_name.replace(" ", "-").lower()[:50]
    return f"workspace-{sanitized_name}"


def parse_list_property(value: Any) -> Optional[List[str]]:
    """
    Parse a list property from CloudFormation.
    
    CloudFormation may pass lists as actual lists, JSON array strings, or
    comma-separated strings.
    
    Args:
        value: Value from ResourceProperties (list, string, or None)
        
    Returns:
        List[str] or None: Parsed list of strings
    """
    logger.info(
        "parse_list_property called with value=%s (type=%s)",
        value,
        type(value).__name__
    )
    
    if value is None:
        logger.info("parse_list_property: value is None, returning None")
        return None
    if isinstance(value, list):
        # If it's already a list, return it
        logger.info("parse_list_property: value is already a list: %s", value)
        return value
    if isinstance(value, str):
        # First, try to parse as JSON array (CDK passes arrays as JSON strings)
        value_stripped = value.strip()
        logger.info(
            "parse_list_property: value is string, stripped=%s, starts_with_bracket=%s",
            value_stripped[:100] if len(value_stripped) > 100 else value_stripped,
            value_stripped.startswith("[")
        )
        if value_stripped.startswith("["):
            try:
                parsed = json.loads(value_stripped)
                if isinstance(parsed, list):
                    logger.info(
                        "parse_list_property: Successfully parsed JSON array: %s -> %s (type=%s)",
                        value,
                        parsed,
                        type(parsed).__name__
                    )
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning(
                    "parse_list_property: Failed to parse as JSON: %s, error: %s",
                    value,
                    str(e)
                )
        
        # Fall back to comma-separated string parsing
        result = [item.strip() for item in value.split(",") if item.strip()]
        logger.info(
            "parse_list_property: Parsed as comma-separated: %s -> %s",
            value,
            result
        )
        return result
    
    logger.warning(
        "parse_list_property: Unexpected type %s for value: %s",
        type(value).__name__,
        value
    )
    return None


def normalize_feature_name(feature: Optional[str]) -> Optional[str]:
    """
    Normalize a single feature name for OpenSearch Workspace API.
    
    OpenSearch Dashboards expects feature names with hyphens (e.g., 'use-case-observability')
    but users might provide them with underscores (e.g., 'use_case_observability').
    
    This function converts underscores to hyphens.
    
    Valid feature names:
    - use-case-all
    - use-case-observability
    - use-case-security-analytics
    - use-case-essentials
    - use-case-search
    
    Args:
        feature: Single feature name (may have underscores or hyphens)
        
    Returns:
        str or None: Normalized feature name with hyphens
    """
    if feature is None:
        return None
    
    # Convert underscores to hyphens
    normalized_feature = feature.replace("_", "-")
    
    if normalized_feature != feature:
        logger.info(
            "Normalized feature name: %s -> %s",
            feature,
            normalized_feature
        )
    
    logger.info("normalize_feature_name: input=%s, output=%s", feature, normalized_feature)
    return normalized_feature


def feature_to_list(feature: Optional[str]) -> Optional[List[str]]:
    """
    Convert a single feature string to a list for the OpenSearch API.
    
    OpenSearch Workspaces API only allows ONE feature/use-case per workspace,
    but expects it as an array with a single element.
    
    Args:
        feature: Single feature name (already normalized)
        
    Returns:
        List[str] or None: Single-element list containing the feature
    """
    if feature is None:
        return None
    
    return [feature]


def parse_dict_property(value: Any) -> Optional[Dict[str, Any]]:
    """
    Parse a dictionary property from CloudFormation.
    
    CloudFormation may pass dicts as actual dicts or as JSON strings.
    
    Args:
        value: Value from ResourceProperties (dict, string, or None)
        
    Returns:
        Dict or None: Parsed dictionary
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON string: %s", value)
            return None
    return None


def resolve_data_source_ids(
    properties: Dict[str, Any],
    opensearch_client: OpenSearchClient
) -> Optional[List[str]]:
    """
    Resolve data source IDs from properties.
    
    This function handles the data source resolution logic with priority:
    1. If DataSourceIds is explicitly provided, use those (highest priority)
    2. If CollectionArn is provided, query the data sources API to find matching UUID
       - If found, return it (do not fall back to title)
       - If not found, fall back to DataSourceTitle if provided
    3. If only DataSourceTitle is provided, query data sources API by title
    
    Args:
        properties: CloudFormation ResourceProperties
        opensearch_client: OpenSearch client instance
        
    Returns:
        List[str] or None: List of resolved data source IDs
    """
    # Check if DataSourceIds are explicitly provided (highest priority)
    data_source_ids = parse_list_property(properties.get("DataSourceIds"))
    if data_source_ids:
        logger.info("Using explicitly provided DataSourceIds: %s", data_source_ids)
        return data_source_ids
    
    # Check if CollectionArn is provided for lookup (second priority)
    collection_arn = properties.get("CollectionArn")
    data_source_title = properties.get("DataSourceTitle")
    
    if collection_arn:
        logger.info(
            "DataSourceIds not provided, looking up data source by CollectionArn: %s",
            collection_arn
        )
        
        result = opensearch_client.find_data_source_by_collection_arn(collection_arn)
        
        if result.success and result.workspace_id:
            logger.info(
                "Found data source ID from collection ARN: %s -> %s",
                collection_arn,
                result.workspace_id
            )
            # CollectionArn lookup succeeded - return without trying title
            return [result.workspace_id]
        else:
            logger.warning(
                "Could not find data source for CollectionArn: %s - %s",
                collection_arn,
                result.message
            )
            # CollectionArn lookup failed - fall through to DataSourceTitle if provided
    
    # Check if DataSourceTitle is provided for lookup (fallback or standalone)
    if data_source_title:
        logger.info(
            "Looking up data source by title: %s",
            data_source_title
        )
        
        result = opensearch_client.find_data_source_by_title(data_source_title)
        
        if result.success and result.workspace_id:
            logger.info(
                "Found data source ID from title: %s -> %s",
                data_source_title,
                result.workspace_id
            )
            return [result.workspace_id]
        else:
            logger.warning(
                "Could not find data source with title: %s - %s",
                data_source_title,
                result.message
            )
    
    return None


def handle_create(
    properties: Dict[str, Any],
    opensearch_client: OpenSearchClient
) -> Dict[str, Any]:
    """
    Handle Create operation by creating a new workspace.
    
    Args:
        properties: CloudFormation ResourceProperties
        opensearch_client: OpenSearch client instance
        
    Returns:
        Dict containing workspace details for CloudFormation response Data
        
    Raises:
        ValueError: If required properties are missing
        RuntimeError: If workspace creation fails
    """
    # Extract required properties
    workspace_name = properties.get("WorkspaceName")
    
    # Validate required properties
    if not workspace_name:
        raise ValueError("Missing required property: WorkspaceName")
    
    # Extract optional properties
    workspace_description = properties.get("WorkspaceDescription")
    workspace_color = properties.get("WorkspaceColor", "#54B399")
    
    # Handle feature - OpenSearch only allows ONE feature per workspace
    # Accept single Feature string from CDK
    workspace_feature_raw = properties.get("Feature")
    workspace_feature = normalize_feature_name(workspace_feature_raw)
    # Convert single feature to list for API (API still expects array with one element)
    workspace_features = feature_to_list(workspace_feature)
    
    permissions = parse_dict_property(properties.get("Permissions"))
    
    # Resolve data source IDs (from explicit IDs, collection ARN, or title lookup)
    data_source_ids = resolve_data_source_ids(properties, opensearch_client)
    
    logger.info(
        "Creating workspace: name=%s, color=%s, feature=%s, features_list=%s, data_sources=%s",
        workspace_name,
        workspace_color,
        workspace_feature,
        workspace_features,
        data_source_ids
    )
    
    # Create workspace
    result = opensearch_client.create_workspace(
        name=workspace_name,
        description=workspace_description,
        color=workspace_color,
        features=workspace_features,
        data_source_ids=data_source_ids,
        permissions=permissions
    )
    
    if not result.success:
        raise RuntimeError(f"Failed to create workspace: {result.message}")
    
    # The create API may return the workspace ID, but we'll verify by looking it up
    # This ensures we get the definitive short ID (e.g., "uGSk2y") from the list API
    workspace_id = result.workspace_id
    
    logger.info(
        "Workspace creation returned: workspace_id=%s, message=%s, response_data=%s",
        workspace_id,
        result.message,
        result.response_data
    )
    
    # Look up the workspace by name to get the definitive workspace ID
    logger.info("Looking up created workspace by name to get definitive ID: %s", workspace_name)
    lookup_result = opensearch_client.find_workspace_by_name(workspace_name)
    
    if lookup_result.success and lookup_result.workspace_id:
        workspace_id = lookup_result.workspace_id
        logger.info(
            "Found workspace ID from lookup: name=%s, id=%s",
            workspace_name,
            workspace_id
        )
    else:
        logger.warning(
            "Could not find workspace by name after creation: name=%s, using create result id=%s, lookup_message=%s",
            workspace_name,
            workspace_id,
            lookup_result.message
        )
    
    # Validate that we have a workspace ID - CloudFormation requires this attribute
    if not workspace_id:
        raise RuntimeError(
            f"Workspace creation succeeded but no workspace ID was returned. "
            f"Create result: {result.response_data}, Lookup result: {lookup_result.message}"
        )
    
    # Build response data
    physical_resource_id = get_physical_resource_id(workspace_name, workspace_id)
    
    response_data = {
        "WorkspaceId": workspace_id,
        "WorkspaceName": workspace_name,
        "Message": result.message,
        "PhysicalResourceId": physical_resource_id,
        "DataSourceIds": data_source_ids or []
    }
    
    logger.info(
        "Workspace created successfully: workspace_id=%s, data_source_ids=%s",
        workspace_id,
        data_source_ids
    )
    
    return response_data


def handle_update(
    properties: Dict[str, Any],
    physical_resource_id: str,
    opensearch_client: OpenSearchClient
) -> Dict[str, Any]:
    """
    Handle Update operation by updating an existing workspace.
    
    Args:
        properties: CloudFormation ResourceProperties
        physical_resource_id: Existing physical resource ID
        opensearch_client: OpenSearch client instance
        
    Returns:
        Dict containing workspace details for CloudFormation response Data
        
    Raises:
        ValueError: If required properties are missing
        RuntimeError: If workspace update fails
    """
    # Extract workspace name first - we'll need it for lookup
    workspace_name = properties.get("WorkspaceName")
    
    # Extract workspace ID from physical resource ID
    workspace_id = None
    if physical_resource_id.startswith("workspace-"):
        potential_id = physical_resource_id[10:]  # Remove "workspace-" prefix
        # Check if it looks like a short workspace ID (6 alphanumeric chars like "uGSk2y")
        # Short IDs don't have hyphens, unlike workspace names which often do
        if potential_id and len(potential_id) <= 10 and "-" not in potential_id:
            workspace_id = potential_id
            logger.info(
                "Extracted short workspace ID from physical resource ID: %s -> %s",
                physical_resource_id,
                workspace_id
            )
    
    if not workspace_id:
        # Try to get workspace ID from properties
        workspace_id = properties.get("WorkspaceId")
        if workspace_id:
            logger.info("Got workspace ID from properties: %s", workspace_id)
    
    if not workspace_id and workspace_name:
        # Look up workspace by name to get the real workspace ID
        logger.info(
            "Workspace ID not found in physical resource ID or properties, looking up by name: %s",
            workspace_name
        )
        lookup_result = opensearch_client.find_workspace_by_name(workspace_name)
        if lookup_result.success and lookup_result.workspace_id:
            workspace_id = lookup_result.workspace_id
            logger.info(
                "Found workspace ID from name lookup: name=%s, id=%s",
                workspace_name,
                workspace_id
            )
        else:
            logger.warning(
                "Could not find workspace by name: %s - %s",
                workspace_name,
                lookup_result.message
            )
    
    if not workspace_id:
        raise ValueError(
            f"Cannot determine workspace ID from physical resource ID ({physical_resource_id}), "
            f"properties, or name lookup ({workspace_name})"
        )
    
    # Extract properties to update
    workspace_description = properties.get("WorkspaceDescription")
    workspace_color = properties.get("WorkspaceColor")
    
    # Handle feature - OpenSearch only allows ONE feature per workspace
    # Accept single Feature string from CDK
    workspace_feature_raw = properties.get("Feature")
    workspace_feature = normalize_feature_name(workspace_feature_raw)
    # Convert single feature to list for API (API still expects array with one element)
    workspace_features = feature_to_list(workspace_feature)
    
    permissions = parse_dict_property(properties.get("Permissions"))
    
    logger.info(
        "Parsed feature for update: raw=%s, normalized=%s, features_list=%s",
        workspace_feature_raw,
        workspace_feature,
        workspace_features
    )
    
    # Resolve data source IDs (from explicit IDs, collection ARN, or title lookup)
    data_source_ids = resolve_data_source_ids(properties, opensearch_client)
    
    logger.info(
        "Updating workspace: workspace_id=%s, name=%s, features=%s, data_sources=%s",
        workspace_id,
        workspace_name,
        workspace_features,
        data_source_ids
    )
    
    # Update workspace
    result = opensearch_client.update_workspace(
        workspace_id=workspace_id,
        name=workspace_name,
        description=workspace_description,
        color=workspace_color,
        features=workspace_features,
        data_source_ids=data_source_ids,
        permissions=permissions
    )
    
    if not result.success:
        raise RuntimeError(f"Failed to update workspace: {result.message}")
    
    # Build response data with corrected physical resource ID using the real workspace ID
    new_physical_resource_id = get_physical_resource_id(workspace_name or "workspace", workspace_id)
    
    response_data = {
        "WorkspaceId": workspace_id,
        "WorkspaceName": workspace_name or "",
        "Message": result.message,
        "PhysicalResourceId": new_physical_resource_id,
        "DataSourceIds": data_source_ids or []
    }
    
    logger.info(
        "Workspace updated successfully: workspace_id=%s, physical_resource_id=%s, data_source_ids=%s",
        workspace_id,
        new_physical_resource_id,
        data_source_ids
    )
    
    return response_data


def handle_delete(
    properties: Dict[str, Any],
    physical_resource_id: str,
    opensearch_client: OpenSearchClient
) -> Dict[str, Any]:
    """
    Handle Delete operation by deleting an existing workspace.
    
    Args:
        properties: CloudFormation ResourceProperties
        physical_resource_id: Physical resource ID of the workspace
        opensearch_client: OpenSearch client instance
        
    Returns:
        Dict containing deletion acknowledgment for CloudFormation response Data
    """
    # Extract workspace ID from physical resource ID
    workspace_id = None
    if physical_resource_id.startswith("workspace-"):
        potential_id = physical_resource_id[10:]  # Remove "workspace-" prefix
        # Check if it looks like a UUID (workspace IDs are typically UUIDs)
        if len(potential_id) > 10 and "-" in potential_id:
            workspace_id = potential_id
    
    if not workspace_id:
        # Try to get workspace ID from properties
        workspace_id = properties.get("WorkspaceId")
    
    if not workspace_id:
        # Cannot delete without workspace ID - but don't fail
        # This allows CloudFormation to clean up resources that may not have been fully created
        logger.warning(
            "Cannot determine workspace ID for deletion - treating as no-op: "
            "physical_resource_id=%s",
            physical_resource_id
        )
        return {
            "Message": "Delete operation completed (no workspace ID found)",
            "PhysicalResourceId": physical_resource_id
        }
    
    logger.info(
        "Deleting workspace: workspace_id=%s, physical_resource_id=%s",
        workspace_id,
        physical_resource_id
    )
    
    # Delete workspace
    result = opensearch_client.delete_workspace(workspace_id=workspace_id)
    
    # Don't fail on delete errors - CloudFormation needs to complete cleanup
    if not result.success:
        logger.warning(
            "Workspace deletion returned error (continuing anyway): %s",
            result.message
        )
    
    return {
        "WorkspaceId": workspace_id,
        "Message": result.message,
        "PhysicalResourceId": physical_resource_id
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for CloudFormation custom resource.
    
    This handler processes CloudFormation Create, Update, and Delete events
    to manage OpenSearch workspaces.
    
    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context
        
    Returns:
        Dict containing the operation result (for direct Lambda invocation testing)
    """
    # Log the full event for debugging and graceful termination support
    logger.info("Received CloudFormation custom resource event")
    logger.info("Event: %s", json.dumps(event, default=str, indent=2))
    
    # Extract event details
    request_type = event.get("RequestType", "Unknown")
    properties = event.get("ResourceProperties", {})
    workspace_name = properties.get("WorkspaceName", "default")
    
    # Debug logging for Feature property (single feature - OpenSearch only allows one per workspace)
    feature_raw = properties.get("Feature")
    logger.info(
        "DEBUG Feature property - raw value: %s (type: %s, repr: %s)",
        feature_raw,
        type(feature_raw).__name__,
        repr(feature_raw)
    )
    
    # Generate stable physical resource ID
    existing_physical_id = event.get("PhysicalResourceId")
    physical_resource_id = existing_physical_id or get_physical_resource_id(workspace_name)
    
    logger.info(
        "Processing request: type=%s, workspace_name=%s, physical_resource_id=%s",
        request_type,
        workspace_name,
        physical_resource_id
    )
    
    response_data = {}
    status = SUCCESS
    reason = None
    
    try:
        # Get OpenSearch endpoint from environment or properties
        opensearch_endpoint = properties.get("OpenSearchEndpoint") or os.environ.get("OPENSEARCH_ENDPOINT")
        if not opensearch_endpoint:
            raise ValueError(
                "OpenSearch endpoint not provided. Set OPENSEARCH_ENDPOINT environment variable "
                "or provide OpenSearchEndpoint in ResourceProperties"
            )
        
        # Initialize OpenSearch client
        opensearch_client = OpenSearchClient(endpoint=opensearch_endpoint)
        
        if request_type == "Delete":
            response_data = handle_delete(properties, physical_resource_id, opensearch_client)
            # Update physical_resource_id from response if provided
            physical_resource_id = response_data.get("PhysicalResourceId", physical_resource_id)
            
        elif request_type == "Create":
            response_data = handle_create(properties, opensearch_client)
            # Update physical_resource_id from response
            physical_resource_id = response_data.get("PhysicalResourceId", physical_resource_id)
            
        elif request_type == "Update":
            response_data = handle_update(properties, physical_resource_id, opensearch_client)
            
        else:
            # Unknown request type
            raise ValueError(f"Unknown RequestType: {request_type}")
        
        logger.info(
            "Operation completed successfully: request_type=%s, workspace_name=%s",
            request_type,
            workspace_name
        )
        
    except ValueError as e:
        logger.error(
            "Validation error during %s operation: %s",
            request_type,
            str(e)
        )
        status = FAILED
        reason = f"Validation error: {str(e)}"
        response_data = {
            "Error": str(e),
            "ErrorType": "ValidationError"
        }
        
    except RuntimeError as e:
        logger.error(
            "Runtime error during %s operation: %s",
            request_type,
            str(e)
        )
        status = FAILED
        reason = f"Runtime error: {str(e)}"
        response_data = {
            "Error": str(e),
            "ErrorType": "RuntimeError"
        }
        
    except Exception as e:
        logger.exception(
            "Unexpected error during %s operation: %s",
            request_type,
            str(e)
        )
        status = FAILED
        reason = f"Unexpected error: {str(e)}"
        response_data = {
            "Error": str(e),
            "ErrorType": type(e).__name__
        }
    
    # Send response to CloudFormation
    send_cfn_response(
        event=event,
        context=context,
        status=status,
        data=response_data,
        physical_resource_id=physical_resource_id,
        reason=reason
    )
    
    # Return result for direct Lambda invocation testing
    return {
        "Status": status,
        "PhysicalResourceId": physical_resource_id,
        "Data": response_data,
        "Reason": reason
    }
