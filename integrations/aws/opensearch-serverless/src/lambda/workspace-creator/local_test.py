#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Local testing script for the OpenSearch Workspace Creator Lambda function.

This script allows testing the Lambda handler locally without AWS credentials.
It uses mocks to simulate AWS services and demonstrates expected behavior.

Usage:
    python local_test.py
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Set environment variables BEFORE importing the handler
os.environ["OPENSEARCH_ENDPOINT"] = "https://test-app.us-east-1.es.amazonaws.com"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Test Data
# =============================================================================


def create_cfn_event(request_type: str = "Create") -> Dict[str, Any]:
    """Create a CloudFormation custom resource event."""
    base_event = {
        "ResponseURL": "https://cloudformation-custom-resource-response.s3.amazonaws.com/test-url",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/guid",
        "RequestId": f"test-request-{request_type.lower()}",
        "ResourceType": "Custom::OpenSearchWorkspace",
        "LogicalResourceId": "SecurityWorkspace",
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:workspace-creator",
            "OpenSearchEndpoint": "https://test-app.us-east-1.es.amazonaws.com",
            "WorkspaceName": "Security Analytics",
            "WorkspaceDescription": "Workspace for security analytics dashboards",
            "WorkspaceColor": "#54B399",
            "WorkspaceFeatures": ["use-case-observability"],
            "DataSourceIds": ["19ea4b89-1719-3af6-8aca-6a671bdf1021"]
        }
    }
    
    base_event["RequestType"] = request_type
    
    if request_type in ("Update", "Delete"):
        base_event["PhysicalResourceId"] = "workspace-abc12345-def6-7890-ghij-klmnopqrstuv"
    
    return base_event


def create_mock_context() -> MagicMock:
    """Create a mock Lambda context object."""
    context = MagicMock()
    context.function_name = "workspace-creator"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:workspace-creator"
    context.memory_limit_in_mb = 256
    context.aws_request_id = "local-test-request-id"
    context.log_group_name = "/aws/lambda/workspace-creator"
    context.log_stream_name = "local/test/stream"
    context.get_remaining_time_in_millis = MagicMock(return_value=300000)
    return context


# =============================================================================
# Test Functions
# =============================================================================


def test_create_workspace_success():
    """Test successful Create event handling."""
    logger.info("=" * 60)
    logger.info("TEST: Create Workspace - Successful Creation")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import WorkspaceResult
    
    # Create mocks
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.create_workspace.return_value = WorkspaceResult(
        success=True,
        workspace_id="abc12345-def6-7890-ghij-klmnopqrstuv",
        message="Workspace create completed successfully: id=abc12345-def6-7890-ghij-klmnopqrstuv"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    # Patch and test
    with patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Create")
        context = create_mock_context()
        
        logger.info("Input Event:")
        logger.info(json.dumps(event, indent=2))
        
        result = handler(event, context)
        
        logger.info("Handler Result:")
        logger.info(json.dumps(result, indent=2))
        
        # Validate result
        if result["Status"] == "SUCCESS":
            logger.info("[PASS] Create event returned SUCCESS")
            logger.info("  - Workspace ID: %s", result["Data"].get("WorkspaceId"))
            logger.info("  - Physical Resource ID: %s", result["PhysicalResourceId"])
            return True
        else:
            logger.error("[FAIL] Create event returned FAILED: %s", result.get("Reason"))
            return False


def test_update_workspace_success():
    """Test successful Update event handling."""
    logger.info("=" * 60)
    logger.info("TEST: Update Workspace - Successful Update")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import WorkspaceResult
    
    # Create mocks
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.update_workspace.return_value = WorkspaceResult(
        success=True,
        workspace_id="abc12345-def6-7890-ghij-klmnopqrstuv",
        message="Workspace update completed successfully"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    # Patch and test
    with patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Update")
        context = create_mock_context()
        
        result = handler(event, context)
        
        if result["Status"] == "SUCCESS":
            logger.info("[PASS] Update event returned SUCCESS")
            logger.info("  - PhysicalResourceId preserved: %s", result["PhysicalResourceId"])
            return True
        else:
            logger.error("[FAIL] Update event returned FAILED: %s", result.get("Reason"))
            return False


def test_delete_workspace_success():
    """Test successful Delete event handling."""
    logger.info("=" * 60)
    logger.info("TEST: Delete Workspace - Successful Deletion")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import WorkspaceResult
    
    # Create mocks
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.delete_workspace.return_value = WorkspaceResult(
        success=True,
        workspace_id="abc12345-def6-7890-ghij-klmnopqrstuv",
        message="Workspace deleted successfully"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    # Patch and test
    with patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Delete")
        context = create_mock_context()
        
        result = handler(event, context)
        
        if result["Status"] == "SUCCESS":
            logger.info("[PASS] Delete event returned SUCCESS")
            logger.info("  - Message: %s", result["Data"].get("Message"))
            return True
        else:
            logger.error("[FAIL] Delete event returned FAILED: %s", result.get("Reason"))
            return False


def test_missing_workspace_name():
    """Test error handling when WorkspaceName is missing."""
    logger.info("=" * 60)
    logger.info("TEST: Missing WorkspaceName Property")
    logger.info("=" * 60)
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    with patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Create")
        del event["ResourceProperties"]["WorkspaceName"]
        context = create_mock_context()
        
        result = handler(event, context)
        
        if result["Status"] == "FAILED" and "WorkspaceName" in result.get("Reason", ""):
            logger.info("[PASS] Handler correctly reported missing WorkspaceName")
            return True
        else:
            logger.error("[FAIL] Handler did not properly handle missing WorkspaceName")
            return False


def test_missing_opensearch_endpoint():
    """Test error handling when OpenSearch endpoint is not provided."""
    logger.info("=" * 60)
    logger.info("TEST: Missing OpenSearch Endpoint")
    logger.info("=" * 60)
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    # Remove environment variable
    original_endpoint = os.environ.get("OPENSEARCH_ENDPOINT")
    os.environ.pop("OPENSEARCH_ENDPOINT", None)
    
    try:
        with patch("urllib.request.urlopen", mock_urlopen):
            
            from app import handler
            
            event = create_cfn_event("Create")
            del event["ResourceProperties"]["OpenSearchEndpoint"]
            context = create_mock_context()
            
            result = handler(event, context)
            
            if result["Status"] == "FAILED" and "endpoint" in result.get("Reason", "").lower():
                logger.info("[PASS] Handler correctly reported missing endpoint")
                return True
            else:
                logger.error("[FAIL] Handler did not properly handle missing endpoint")
                return False
    finally:
        # Restore environment variable
        if original_endpoint:
            os.environ["OPENSEARCH_ENDPOINT"] = original_endpoint


def test_create_workspace_api_error():
    """Test error handling when workspace creation fails."""
    logger.info("=" * 60)
    logger.info("TEST: Workspace Creation API Error")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import WorkspaceResult
    
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.create_workspace.return_value = WorkspaceResult(
        success=False,
        message="HTTP error 403: Access denied",
        error_code="HTTP_403"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    with patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Create")
        context = create_mock_context()
        
        result = handler(event, context)
        
        if result["Status"] == "FAILED":
            logger.info("[PASS] Handler correctly reported API error")
            return True
        else:
            logger.error("[FAIL] Handler did not properly handle API error")
            return False


def test_delete_workspace_not_found():
    """Test that delete succeeds even when workspace not found."""
    logger.info("=" * 60)
    logger.info("TEST: Delete Workspace - Not Found (should succeed)")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import WorkspaceResult
    
    # Simulate workspace already deleted (404 treated as success by client)
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.delete_workspace.return_value = WorkspaceResult(
        success=True,
        workspace_id="abc12345-def6-7890-ghij-klmnopqrstuv",
        message="Workspace not found (already deleted)"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    with patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Delete")
        context = create_mock_context()
        
        result = handler(event, context)
        
        # Delete should still succeed
        if result["Status"] == "SUCCESS":
            logger.info("[PASS] Handler returned SUCCESS for already deleted workspace")
            return True
        else:
            logger.error("[FAIL] Handler returned FAILED for already deleted workspace")
            return False


def test_list_property_parsing():
    """Test that list properties are parsed correctly."""
    logger.info("=" * 60)
    logger.info("TEST: List Property Parsing")
    logger.info("=" * 60)
    
    from app import parse_list_property
    
    # Test actual list
    result1 = parse_list_property(["item1", "item2"])
    assert result1 == ["item1", "item2"], f"Expected list, got {result1}"
    
    # Test comma-separated string
    result2 = parse_list_property("item1, item2, item3")
    assert result2 == ["item1", "item2", "item3"], f"Expected parsed list, got {result2}"
    
    # Test None
    result3 = parse_list_property(None)
    assert result3 is None, f"Expected None, got {result3}"
    
    logger.info("[PASS] List property parsing works correctly")
    return True


def test_dict_property_parsing():
    """Test that dict properties are parsed correctly."""
    logger.info("=" * 60)
    logger.info("TEST: Dict Property Parsing")
    logger.info("=" * 60)
    
    from app import parse_dict_property
    
    # Test actual dict
    input_dict = {"key": "value"}
    result1 = parse_dict_property(input_dict)
    assert result1 == input_dict, f"Expected dict, got {result1}"
    
    # Test JSON string
    json_str = '{"key": "value"}'
    result2 = parse_dict_property(json_str)
    assert result2 == {"key": "value"}, f"Expected parsed dict, got {result2}"
    
    # Test None
    result3 = parse_dict_property(None)
    assert result3 is None, f"Expected None, got {result3}"
    
    logger.info("[PASS] Dict property parsing works correctly")
    return True


def test_helper_modules_import():
    """Test that all helper modules can be imported successfully."""
    logger.info("=" * 60)
    logger.info("TEST: Helper Modules Import Check")
    logger.info("=" * 60)
    
    try:
        from helpers.opensearch_client import OpenSearchClient, WorkspaceResult
        
        logger.info("[PASS] All helper modules imported successfully")
        logger.info("  - OpenSearchClient: %s", OpenSearchClient)
        logger.info("  - WorkspaceResult: %s", WorkspaceResult)
        return True
    except ImportError as e:
        logger.error("[FAIL] Failed to import helper modules: %s", e)
        return False


def test_workspace_result_dataclass():
    """Test WorkspaceResult dataclass functionality."""
    logger.info("=" * 60)
    logger.info("TEST: WorkspaceResult Dataclass")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import WorkspaceResult
    
    # Test creating WorkspaceResult
    result = WorkspaceResult(
        success=True,
        workspace_id="test-id-123",
        message="Test message"
    )
    
    # Test to_dict method
    result_dict = result.to_dict()
    
    if all([
        result_dict["success"] is True,
        result_dict["workspaceId"] == "test-id-123",
        result_dict["message"] == "Test message"
    ]):
        logger.info("[PASS] WorkspaceResult dataclass works correctly")
        logger.info("  - to_dict output: %s", result_dict)
        return True
    else:
        logger.error("[FAIL] WorkspaceResult dataclass has issues")
        return False


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run all local tests."""
    logger.info("Starting OpenSearch Workspace Creator Local Tests")
    logger.info("OpenSearch Endpoint: %s", os.environ.get("OPENSEARCH_ENDPOINT"))
    logger.info("AWS Region: %s", os.environ.get("AWS_REGION"))
    logger.info("")
    
    tests = [
        ("Helper Modules Import", test_helper_modules_import),
        ("WorkspaceResult Dataclass", test_workspace_result_dataclass),
        ("List Property Parsing", test_list_property_parsing),
        ("Dict Property Parsing", test_dict_property_parsing),
        ("Create Workspace Success", test_create_workspace_success),
        ("Update Workspace Success", test_update_workspace_success),
        ("Delete Workspace Success", test_delete_workspace_success),
        ("Delete Workspace Not Found", test_delete_workspace_not_found),
        ("Missing WorkspaceName", test_missing_workspace_name),
        ("Missing OpenSearch Endpoint", test_missing_opensearch_endpoint),
        ("Create Workspace API Error", test_create_workspace_api_error),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.exception("Exception in test '%s': %s", test_name, e)
            failed += 1
        logger.info("")
    
    # Print summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info("Total Tests: %d", len(tests))
    logger.info("Passed: %d", passed)
    logger.info("Failed: %d", failed)
    logger.info("")
    
    if failed == 0:
        logger.info("ALL TESTS PASSED - Lambda handler is working correctly")
        return 0
    else:
        logger.error("SOME TESTS FAILED - Please review the logs above")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
