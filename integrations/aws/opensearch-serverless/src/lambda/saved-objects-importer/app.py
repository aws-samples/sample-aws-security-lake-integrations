# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Saved Objects Importer Lambda Handler

This Lambda function handles CloudFormation custom resource events to import
saved objects (dashboards, visualizations, index patterns) from S3 into
OpenSearch Dashboards.

The handler supports Create, Update, and Delete operations:
- Create: Downloads NDJSON from S3 and imports to OpenSearch
- Update: Re-imports saved objects (same as Create)
- Delete: No-op (saved objects remain in OpenSearch after stack deletion)
"""

import json
import logging
import os
import urllib.request
from typing import Any, Dict, Optional

from helpers.opensearch_client import OpenSearchClient
from helpers.s3_client import S3Client, S3ClientError

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


def get_physical_resource_id(import_name: str) -> str:
    """
    Generate a stable physical resource ID for the custom resource.
    
    Args:
        import_name: Name of this import operation
        
    Returns:
        str: Physical resource ID in format 'saved-objects-{ImportName}'
    """
    # Sanitize import name for use in resource ID
    sanitized_name = import_name.replace(" ", "-").lower()[:50]
    return f"saved-objects-{sanitized_name}"


def parse_overwrite_property(overwrite_value: Any) -> bool:
    """
    Parse the Overwrite property from CloudFormation.
    
    CloudFormation passes all properties as strings, so we need to handle
    string 'true'/'false' as well as boolean values.
    
    Args:
        overwrite_value: Value from ResourceProperties (string or bool)
        
    Returns:
        bool: True if overwrite is enabled, False otherwise
    """
    if isinstance(overwrite_value, bool):
        return overwrite_value
    if isinstance(overwrite_value, str):
        return overwrite_value.lower() == "true"
    return True  # Default to overwrite enabled


def handle_create_update(
    properties: Dict[str, Any],
    physical_resource_id: str
) -> Dict[str, Any]:
    """
    Handle Create or Update operations by importing saved objects.
    
    Downloads the NDJSON file from S3 and imports it to OpenSearch Dashboards.
    
    Args:
        properties: CloudFormation ResourceProperties
        physical_resource_id: Physical resource ID for this resource
        
    Returns:
        Dict containing import statistics for CloudFormation response Data
        
    Raises:
        ValueError: If required properties are missing
        S3ClientError: If S3 download fails
        Exception: If OpenSearch import fails
    """
    # Extract required properties
    s3_bucket = properties.get("S3Bucket")
    s3_key = properties.get("S3Key")
    overwrite = parse_overwrite_property(properties.get("Overwrite", "true"))
    import_name = properties.get("ImportName", "default")
    
    # Validate required properties
    missing_properties = []
    if not s3_bucket:
        missing_properties.append("S3Bucket")
    if not s3_key:
        missing_properties.append("S3Key")
    
    if missing_properties:
        raise ValueError(f"Missing required properties: {', '.join(missing_properties)}")
    
    # Get OpenSearch endpoint - property takes precedence over environment variable
    # This allows the CDK to pass a workspace-specific URL via custom resource properties
    # while the Lambda's environment variable can serve as a fallback
    opensearch_endpoint = properties.get("OpenSearchEndpoint") or os.environ.get("OPENSEARCH_ENDPOINT")
    datasource_id = properties.get("DataSourceId") or os.environ.get("DATASOURCE_ID")
    if not opensearch_endpoint:
        raise ValueError("OpenSearchEndpoint property or OPENSEARCH_ENDPOINT environment variable must be set")
    
    logger.info(
        "Starting saved objects import: import_name=%s, s3_bucket=%s, s3_key=%s, overwrite=%s",
        import_name,
        s3_bucket,
        s3_key,
        overwrite
    )
    
    # Download NDJSON file from S3
    logger.info("Downloading NDJSON file from S3")
    s3_client = S3Client(bucket=s3_bucket)
    ndjson_content = s3_client.download_file(key=s3_key)
    
    logger.info(
        "Downloaded NDJSON file: size=%d bytes",
        len(ndjson_content)
    )
    
    # Import saved objects to OpenSearch
    logger.info("Importing saved objects to OpenSearch Dashboards")
    opensearch_client = OpenSearchClient(endpoint=opensearch_endpoint, datasource_id=datasource_id)
    import_result = opensearch_client.import_saved_objects(
        ndjson_content=ndjson_content,
        overwrite=overwrite
    )
    
    # Log import results
    if import_result.success:
        logger.info(
            "Import completed successfully: success_count=%d",
            import_result.success_count
        )
    elif import_result.success_count > 0:
        # Partial success - some objects imported, some failed
        logger.warning(
            "Import completed with errors: success_count=%d, error_count=%d",
            import_result.success_count,
            import_result.error_count
        )
        for error in import_result.errors:
            logger.warning("Import error: %s", json.dumps(error, default=str))
    else:
        # Total failure - no objects imported
        logger.error(
            "Import failed: error_count=%d, message=%s",
            import_result.error_count,
            import_result.message
        )
        raise RuntimeError(f"Failed to import saved objects: {import_result.message}")
    
    # Build response data
    response_data = {
        "ImportName": import_name,
        "S3Bucket": s3_bucket,
        "S3Key": s3_key,
        "Overwrite": str(overwrite).lower(),
        "SuccessCount": str(import_result.success_count),
        "ErrorCount": str(import_result.error_count),
        "Message": import_result.message,
        "PhysicalResourceId": physical_resource_id
    }
    
    return response_data


def handle_delete(
    properties: Dict[str, Any],
    physical_resource_id: str
) -> Dict[str, Any]:
    """
    Handle Delete operation (no-op).
    
    Saved objects are intentionally left in OpenSearch after stack deletion
    to preserve dashboards and visualizations.
    
    Args:
        properties: CloudFormation ResourceProperties
        physical_resource_id: Physical resource ID for this resource
        
    Returns:
        Dict containing deletion acknowledgment for CloudFormation response Data
    """
    import_name = properties.get("ImportName", "default")
    
    logger.info(
        "Delete operation - no action taken. Saved objects remain in OpenSearch: "
        "import_name=%s, physical_resource_id=%s",
        import_name,
        physical_resource_id
    )
    
    return {
        "ImportName": import_name,
        "Message": "Delete operation completed (no-op). Saved objects remain in OpenSearch.",
        "PhysicalResourceId": physical_resource_id
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for CloudFormation custom resource.
    
    This handler processes CloudFormation Create, Update, and Delete events
    to manage saved objects imports to OpenSearch Dashboards.
    
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
    import_name = properties.get("ImportName", "default")
    
    # Generate stable physical resource ID
    existing_physical_id = event.get("PhysicalResourceId")
    physical_resource_id = existing_physical_id or get_physical_resource_id(import_name)
    
    logger.info(
        "Processing request: type=%s, import_name=%s, physical_resource_id=%s",
        request_type,
        import_name,
        physical_resource_id
    )
    
    response_data = {}
    status = SUCCESS
    reason = None
    
    try:
        if request_type == "Delete":
            response_data = handle_delete(properties, physical_resource_id)
            
        elif request_type in ("Create", "Update"):
            response_data = handle_create_update(properties, physical_resource_id)
            
        else:
            # Unknown request type
            raise ValueError(f"Unknown RequestType: {request_type}")
        
        logger.info(
            "Operation completed successfully: request_type=%s, import_name=%s",
            request_type,
            import_name
        )
        
    except S3ClientError as e:
        logger.error(
            "S3 error during %s operation: bucket=%s, key=%s, error=%s",
            request_type,
            e.bucket,
            e.key,
            str(e)
        )
        status = FAILED
        reason = f"S3 error: {str(e)}"
        response_data = {
            "Error": str(e),
            "ErrorType": "S3ClientError"
        }
        
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