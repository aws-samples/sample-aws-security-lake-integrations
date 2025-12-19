#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Local testing script for the Saved Objects Importer Lambda function.

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
os.environ["OPENSEARCH_ENDPOINT"] = "https://test-collection.us-east-1.aoss.amazonaws.com"
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


def get_sample_ndjson_content() -> bytes:
    """Generate sample NDJSON content for saved objects."""
    objects = [
        {
            "id": "security-index-pattern",
            "type": "index-pattern",
            "attributes": {
                "title": "security-*",
                "timeFieldName": "@timestamp"
            }
        },
        {
            "id": "security-visualization-1",
            "type": "visualization",
            "attributes": {
                "title": "Security Events Over Time",
                "visState": "{\"type\":\"line\"}"
            }
        },
        {
            "id": "security-dashboard-1",
            "type": "dashboard",
            "attributes": {
                "title": "Security Overview Dashboard",
                "panelsJSON": "[]"
            }
        }
    ]
    ndjson_lines = [json.dumps(obj) for obj in objects]
    return "\n".join(ndjson_lines).encode("utf-8")


def create_cfn_event(request_type: str = "Create") -> Dict[str, Any]:
    """Create a CloudFormation custom resource event."""
    base_event = {
        "ResponseURL": "https://cloudformation-custom-resource-response.s3.amazonaws.com/test-url",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/guid",
        "RequestId": f"test-request-{request_type.lower()}",
        "ResourceType": "Custom::SavedObjectsImporter",
        "LogicalResourceId": "ImportSecurityDashboards",
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:importer",
            "S3Bucket": "test-assets-bucket",
            "S3Key": "security-dashboards.ndjson",
            "Overwrite": "true",
            "ImportName": "SecurityDashboards"
        }
    }
    
    base_event["RequestType"] = request_type
    
    if request_type in ("Update", "Delete"):
        base_event["PhysicalResourceId"] = "saved-objects-securitydashboards"
    
    return base_event


def create_mock_context() -> MagicMock:
    """Create a mock Lambda context object."""
    context = MagicMock()
    context.function_name = "saved-objects-importer"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:saved-objects-importer"
    context.memory_limit_in_mb = 256
    context.aws_request_id = "local-test-request-id"
    context.log_group_name = "/aws/lambda/saved-objects-importer"
    context.log_stream_name = "local/test/stream"
    context.get_remaining_time_in_millis = MagicMock(return_value=300000)
    return context


# =============================================================================
# Test Functions
# =============================================================================


def test_create_event_success():
    """Test successful Create event handling."""
    logger.info("=" * 60)
    logger.info("TEST: Create Event - Successful Import")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import ImportResult
    
    # Create mocks
    mock_s3_client = MagicMock()
    mock_s3_client.download_file.return_value = get_sample_ndjson_content()
    
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.import_saved_objects.return_value = ImportResult(
        success=True,
        success_count=3,
        error_count=0,
        errors=[],
        message="Successfully imported 3 saved object(s)"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    # Patch and test
    with patch("app.S3Client", return_value=mock_s3_client), \
         patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
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
            logger.info("  - Success Count: %s", result["Data"].get("SuccessCount"))
            logger.info("  - Error Count: %s", result["Data"].get("ErrorCount"))
            return True
        else:
            logger.error("[FAIL] Create event returned FAILED: %s", result.get("Reason"))
            return False


def test_update_event_success():
    """Test successful Update event handling."""
    logger.info("=" * 60)
    logger.info("TEST: Update Event - Successful Re-import")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import ImportResult
    
    # Create mocks
    mock_s3_client = MagicMock()
    mock_s3_client.download_file.return_value = get_sample_ndjson_content()
    
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.import_saved_objects.return_value = ImportResult(
        success=True,
        success_count=3,
        error_count=0,
        errors=[],
        message="Successfully imported 3 saved object(s)"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    # Patch and test
    with patch("app.S3Client", return_value=mock_s3_client), \
         patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
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


def test_delete_event_noop():
    """Test Delete event does nothing (no-op)."""
    logger.info("=" * 60)
    logger.info("TEST: Delete Event - No-Op Behavior")
    logger.info("=" * 60)
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    # Patch and test
    with patch("urllib.request.urlopen", mock_urlopen):
        
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


def test_missing_s3_bucket():
    """Test error handling when S3Bucket is missing."""
    logger.info("=" * 60)
    logger.info("TEST: Missing S3Bucket Property")
    logger.info("=" * 60)
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    with patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Create")
        del event["ResourceProperties"]["S3Bucket"]
        context = create_mock_context()
        
        result = handler(event, context)
        
        if result["Status"] == "FAILED" and "S3Bucket" in result.get("Reason", ""):
            logger.info("[PASS] Handler correctly reported missing S3Bucket")
            return True
        else:
            logger.error("[FAIL] Handler did not properly handle missing S3Bucket")
            return False


def test_s3_download_error():
    """Test error handling when S3 download fails."""
    logger.info("=" * 60)
    logger.info("TEST: S3 Download Error Handling")
    logger.info("=" * 60)
    
    from helpers.s3_client import S3ClientError
    
    mock_s3_client = MagicMock()
    mock_s3_client.download_file.side_effect = S3ClientError(
        message="File not found: s3://test-bucket/missing.ndjson",
        bucket="test-bucket",
        key="missing.ndjson"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    with patch("app.S3Client", return_value=mock_s3_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Create")
        context = create_mock_context()
        
        result = handler(event, context)
        
        if result["Status"] == "FAILED" and "S3 error" in result.get("Reason", ""):
            logger.info("[PASS] Handler correctly handled S3 error")
            return True
        else:
            logger.error("[FAIL] Handler did not properly handle S3 error")
            return False


def test_opensearch_import_error():
    """Test error handling when OpenSearch import fails completely."""
    logger.info("=" * 60)
    logger.info("TEST: OpenSearch Total Import Failure")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import ImportResult
    
    mock_s3_client = MagicMock()
    mock_s3_client.download_file.return_value = get_sample_ndjson_content()
    
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.import_saved_objects.return_value = ImportResult(
        success=False,
        success_count=0,
        error_count=3,
        errors=[{"id": "obj-1", "error": "unknown"}],
        message="Import failed with 3 error(s)"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    with patch("app.S3Client", return_value=mock_s3_client), \
         patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Create")
        context = create_mock_context()
        
        result = handler(event, context)
        
        if result["Status"] == "FAILED":
            logger.info("[PASS] Handler correctly reported total import failure")
            return True
        else:
            logger.error("[FAIL] Handler did not properly handle import failure")
            return False


def test_partial_import_success():
    """Test handling of partial import success (some objects imported, some failed)."""
    logger.info("=" * 60)
    logger.info("TEST: Partial Import Success")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import ImportResult
    
    mock_s3_client = MagicMock()
    mock_s3_client.download_file.return_value = get_sample_ndjson_content()
    
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.import_saved_objects.return_value = ImportResult(
        success=False,
        success_count=2,
        error_count=1,
        errors=[{"id": "obj-3", "type": "visualization", "error": {"type": "conflict"}}],
        message="Partial import: 2 succeeded, 1 failed"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    with patch("app.S3Client", return_value=mock_s3_client), \
         patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Create")
        context = create_mock_context()
        
        result = handler(event, context)
        
        # Partial success should still return SUCCESS
        if result["Status"] == "SUCCESS":
            logger.info("[PASS] Handler returned SUCCESS for partial import")
            logger.info("  - Success Count: %s", result["Data"].get("SuccessCount"))
            logger.info("  - Error Count: %s", result["Data"].get("ErrorCount"))
            return True
        else:
            logger.error("[FAIL] Handler returned FAILED for partial import")
            return False


def test_overwrite_parameter():
    """Test that Overwrite parameter is correctly passed to OpenSearch client."""
    logger.info("=" * 60)
    logger.info("TEST: Overwrite Parameter Handling")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import ImportResult
    
    mock_s3_client = MagicMock()
    mock_s3_client.download_file.return_value = get_sample_ndjson_content()
    
    mock_opensearch_client = MagicMock()
    mock_opensearch_client.import_saved_objects.return_value = ImportResult(
        success=True,
        success_count=3,
        error_count=0,
        errors=[],
        message="Successfully imported 3 saved object(s)"
    )
    
    mock_urlopen = MagicMock()
    mock_urlopen.return_value.__enter__.return_value.status = 200
    
    # Test with overwrite=false
    with patch("app.S3Client", return_value=mock_s3_client), \
         patch("app.OpenSearchClient", return_value=mock_opensearch_client), \
         patch("urllib.request.urlopen", mock_urlopen):
        
        from app import handler
        
        event = create_cfn_event("Create")
        event["ResourceProperties"]["Overwrite"] = "false"
        context = create_mock_context()
        
        result = handler(event, context)
        
        # Verify the call to import_saved_objects
        call_args = mock_opensearch_client.import_saved_objects.call_args
        if call_args and call_args[1].get("overwrite") is False:
            logger.info("[PASS] Overwrite=false was correctly passed to OpenSearch client")
            return True
        else:
            logger.error("[FAIL] Overwrite parameter was not correctly handled")
            return False


def test_helper_modules_import():
    """Test that all helper modules can be imported successfully."""
    logger.info("=" * 60)
    logger.info("TEST: Helper Modules Import Check")
    logger.info("=" * 60)
    
    try:
        from helpers.opensearch_client import OpenSearchClient, ImportResult
        from helpers.s3_client import S3Client, S3ClientError
        
        logger.info("[PASS] All helper modules imported successfully")
        logger.info("  - OpenSearchClient: %s", OpenSearchClient)
        logger.info("  - ImportResult: %s", ImportResult)
        logger.info("  - S3Client: %s", S3Client)
        logger.info("  - S3ClientError: %s", S3ClientError)
        return True
    except ImportError as e:
        logger.error("[FAIL] Failed to import helper modules: %s", e)
        return False


def test_import_result_dataclass():
    """Test ImportResult dataclass functionality."""
    logger.info("=" * 60)
    logger.info("TEST: ImportResult Dataclass")
    logger.info("=" * 60)
    
    from helpers.opensearch_client import ImportResult
    
    # Test creating ImportResult
    result = ImportResult(
        success=True,
        success_count=5,
        error_count=0,
        errors=[],
        message="Test message"
    )
    
    # Test to_dict method
    result_dict = result.to_dict()
    
    if all([
        result_dict["success"] is True,
        result_dict["successCount"] == 5,
        result_dict["errorCount"] == 0,
        result_dict["message"] == "Test message"
    ]):
        logger.info("[PASS] ImportResult dataclass works correctly")
        logger.info("  - to_dict output: %s", result_dict)
        return True
    else:
        logger.error("[FAIL] ImportResult dataclass has issues")
        return False


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run all local tests."""
    logger.info("Starting Saved Objects Importer Local Tests")
    logger.info("OpenSearch Endpoint: %s", os.environ.get("OPENSEARCH_ENDPOINT"))
    logger.info("AWS Region: %s", os.environ.get("AWS_REGION"))
    logger.info("")
    
    tests = [
        ("Helper Modules Import", test_helper_modules_import),
        ("ImportResult Dataclass", test_import_result_dataclass),
        ("Create Event Success", test_create_event_success),
        ("Update Event Success", test_update_event_success),
        ("Delete Event No-Op", test_delete_event_noop),
        ("Missing S3Bucket", test_missing_s3_bucket),
        ("S3 Download Error", test_s3_download_error),
        ("OpenSearch Import Error", test_opensearch_import_error),
        ("Partial Import Success", test_partial_import_success),
        ("Overwrite Parameter", test_overwrite_parameter),
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