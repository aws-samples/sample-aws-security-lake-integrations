# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for the Saved Objects Importer Lambda function.

These tests use pytest and mocking to test the Lambda handler and helper functions
without requiring actual AWS services.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, Mock
from io import BytesIO
from typing import Any, Dict


# Set environment variables before importing the handler
os.environ["OPENSEARCH_ENDPOINT"] = "https://test-collection.us-east-1.aoss.amazonaws.com"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


# Import after setting environment variables
from app import (
    handler,
    send_cfn_response,
    get_physical_resource_id,
    parse_overwrite_property,
    handle_create_update,
    handle_delete,
    SUCCESS,
    FAILED,
)
from helpers.opensearch_client import OpenSearchClient, ImportResult
from helpers.s3_client import S3Client, S3ClientError


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_context():
    """Create a mock Lambda context object."""
    context = MagicMock()
    context.function_name = "saved-objects-importer"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:saved-objects-importer"
    context.memory_limit_in_mb = 256
    context.aws_request_id = "test-request-id-12345"
    context.log_group_name = "/aws/lambda/saved-objects-importer"
    context.log_stream_name = "2024/01/01/[$LATEST]abcdef123456"
    context.get_remaining_time_in_millis = MagicMock(return_value=300000)
    return context


@pytest.fixture
def sample_ndjson_content():
    """Sample NDJSON content for saved objects."""
    objects = [
        {"id": "index-pattern-1", "type": "index-pattern", "attributes": {"title": "security-*"}},
        {"id": "visualization-1", "type": "visualization", "attributes": {"title": "Security Dashboard"}},
        {"id": "dashboard-1", "type": "dashboard", "attributes": {"title": "Security Overview"}},
    ]
    ndjson_lines = [json.dumps(obj) for obj in objects]
    return "\n".join(ndjson_lines).encode("utf-8")


@pytest.fixture
def create_event():
    """Sample CloudFormation Create event."""
    return {
        "RequestType": "Create",
        "ResponseURL": "https://cloudformation-custom-resource-response.s3.amazonaws.com/test-response-url",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/guid-12345",
        "RequestId": "unique-request-id-create",
        "ResourceType": "Custom::SavedObjectsImporter",
        "LogicalResourceId": "ImportIndexPatterns",
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:saved-objects-importer",
            "S3Bucket": "test-assets-bucket",
            "S3Key": "index-patterns.ndjson",
            "Overwrite": "true",
            "ImportName": "IndexPatterns"
        }
    }


@pytest.fixture
def update_event():
    """Sample CloudFormation Update event."""
    return {
        "RequestType": "Update",
        "ResponseURL": "https://cloudformation-custom-resource-response.s3.amazonaws.com/test-response-url",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/guid-12345",
        "RequestId": "unique-request-id-update",
        "ResourceType": "Custom::SavedObjectsImporter",
        "LogicalResourceId": "ImportIndexPatterns",
        "PhysicalResourceId": "saved-objects-indexpatterns",
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:saved-objects-importer",
            "S3Bucket": "test-assets-bucket",
            "S3Key": "index-patterns.ndjson",
            "Overwrite": "true",
            "ImportName": "IndexPatterns"
        },
        "OldResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:saved-objects-importer",
            "S3Bucket": "test-assets-bucket",
            "S3Key": "old-index-patterns.ndjson",
            "Overwrite": "true",
            "ImportName": "IndexPatterns"
        }
    }


@pytest.fixture
def delete_event():
    """Sample CloudFormation Delete event."""
    return {
        "RequestType": "Delete",
        "ResponseURL": "https://cloudformation-custom-resource-response.s3.amazonaws.com/test-response-url",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/guid-12345",
        "RequestId": "unique-request-id-delete",
        "ResourceType": "Custom::SavedObjectsImporter",
        "LogicalResourceId": "ImportIndexPatterns",
        "PhysicalResourceId": "saved-objects-indexpatterns",
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:saved-objects-importer",
            "S3Bucket": "test-assets-bucket",
            "S3Key": "index-patterns.ndjson",
            "Overwrite": "true",
            "ImportName": "IndexPatterns"
        }
    }


@pytest.fixture
def success_import_result():
    """Mock successful import result."""
    return ImportResult(
        success=True,
        success_count=3,
        error_count=0,
        errors=[],
        message="Successfully imported 3 saved object(s)"
    )


@pytest.fixture
def partial_import_result():
    """Mock partial success import result."""
    return ImportResult(
        success=False,
        success_count=2,
        error_count=1,
        errors=[{"id": "viz-1", "type": "visualization", "error": {"type": "conflict"}}],
        message="Partial import: 2 succeeded, 1 failed"
    )


@pytest.fixture
def failed_import_result():
    """Mock failed import result."""
    return ImportResult(
        success=False,
        success_count=0,
        error_count=3,
        errors=[
            {"id": "obj-1", "type": "dashboard", "error": {"type": "unknown"}},
            {"id": "obj-2", "type": "visualization", "error": {"type": "unknown"}},
            {"id": "obj-3", "type": "index-pattern", "error": {"type": "unknown"}}
        ],
        message="Import failed with 3 error(s)"
    )


# =============================================================================
# Unit Tests - Helper Functions
# =============================================================================


class TestParseOverwriteProperty:
    """Tests for parse_overwrite_property function."""
    
    def test_parse_overwrite_string_true(self):
        """Test parsing string 'true'."""
        assert parse_overwrite_property("true") is True
        assert parse_overwrite_property("True") is True
        assert parse_overwrite_property("TRUE") is True
    
    def test_parse_overwrite_string_false(self):
        """Test parsing string 'false'."""
        assert parse_overwrite_property("false") is False
        assert parse_overwrite_property("False") is False
        assert parse_overwrite_property("FALSE") is False
    
    def test_parse_overwrite_boolean_true(self):
        """Test parsing boolean True."""
        assert parse_overwrite_property(True) is True
    
    def test_parse_overwrite_boolean_false(self):
        """Test parsing boolean False."""
        assert parse_overwrite_property(False) is False
    
    def test_parse_overwrite_default_value(self):
        """Test that None defaults to True and invalid strings default to False."""
        assert parse_overwrite_property(None) is True
        # Non-boolean strings that aren't "true" should return False
        assert parse_overwrite_property("invalid") is False
        assert parse_overwrite_property("yes") is False


class TestGetPhysicalResourceId:
    """Tests for get_physical_resource_id function."""
    
    def test_basic_import_name(self):
        """Test with basic import name."""
        result = get_physical_resource_id("IndexPatterns")
        assert result == "saved-objects-indexpatterns"
    
    def test_import_name_with_spaces(self):
        """Test with spaces in import name."""
        result = get_physical_resource_id("Security Dashboards")
        assert result == "saved-objects-security-dashboards"
    
    def test_long_import_name_truncation(self):
        """Test that long import names are truncated."""
        long_name = "A" * 100
        result = get_physical_resource_id(long_name)
        # Should start with prefix and be limited in length
        assert result.startswith("saved-objects-")
        assert len(result) <= 64  # 14 (prefix) + 50 (max name)


# =============================================================================
# Unit Tests - send_cfn_response
# =============================================================================


class TestSendCfnResponse:
    """Tests for send_cfn_response function."""
    
    @patch("urllib.request.urlopen")
    def test_send_response_success(self, mock_urlopen, create_event, mock_context):
        """Test successful response to CloudFormation."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        send_cfn_response(
            event=create_event,
            context=mock_context,
            status=SUCCESS,
            data={"ImportCount": "3"},
            physical_resource_id="test-resource-id"
        )
        
        # Verify urlopen was called
        assert mock_urlopen.called
        call_args = mock_urlopen.call_args[0][0]
        assert call_args.method == "PUT"
        # HTTP headers are case-insensitive, check with lowercase
        headers_lower = {k.lower(): v for k, v in call_args.headers.items()}
        assert "content-type" in headers_lower
        
        # Verify request body contains expected fields
        body = json.loads(call_args.data.decode("utf-8"))
        assert body["Status"] == SUCCESS
        assert body["PhysicalResourceId"] == "test-resource-id"
        assert body["StackId"] == create_event["StackId"]
        assert body["RequestId"] == create_event["RequestId"]
    
    @patch("urllib.request.urlopen")
    def test_send_response_failed(self, mock_urlopen, create_event, mock_context):
        """Test sending FAILED response to CloudFormation."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        send_cfn_response(
            event=create_event,
            context=mock_context,
            status=FAILED,
            reason="Test failure reason"
        )
        
        call_args = mock_urlopen.call_args[0][0]
        body = json.loads(call_args.data.decode("utf-8"))
        assert body["Status"] == FAILED
        assert body["Reason"] == "Test failure reason"
    
    def test_send_response_no_url(self, mock_context):
        """Test handling when ResponseURL is missing."""
        event_without_url = {"RequestType": "Create"}
        
        # Should not raise exception, just log error
        send_cfn_response(
            event=event_without_url,
            context=mock_context,
            status=SUCCESS
        )


# =============================================================================
# Unit Tests - Handler Create Success
# =============================================================================


class TestHandlerCreateSuccess:
    """Tests for successful Create operations."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    @patch("app.S3Client")
    def test_handler_create_success(
        self,
        mock_s3_client_class,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        sample_ndjson_content,
        success_import_result
    ):
        """Test successful Create event handling."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.return_value = sample_ndjson_content
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.import_saved_objects.return_value = success_import_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result
        assert result["Status"] == SUCCESS
        assert "PhysicalResourceId" in result
        assert result["Data"]["SuccessCount"] == "3"
        assert result["Data"]["ErrorCount"] == "0"
        
        # Verify S3 client was called correctly
        mock_s3_client_class.assert_called_once_with(bucket="test-assets-bucket")
        mock_s3_client.download_file.assert_called_once_with(key="index-patterns.ndjson")
        
        # Verify OpenSearch client was called correctly
        mock_opensearch_client.import_saved_objects.assert_called_once_with(
            ndjson_content=sample_ndjson_content,
            overwrite=True
        )


# =============================================================================
# Unit Tests - Handler Update Success
# =============================================================================


class TestHandlerUpdateSuccess:
    """Tests for successful Update operations."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    @patch("app.S3Client")
    def test_handler_update_success(
        self,
        mock_s3_client_class,
        mock_opensearch_client_class,
        mock_urlopen,
        update_event,
        mock_context,
        sample_ndjson_content,
        success_import_result
    ):
        """Test successful Update event handling."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.return_value = sample_ndjson_content
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.import_saved_objects.return_value = success_import_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute handler
        result = handler(update_event, mock_context)
        
        # Verify result
        assert result["Status"] == SUCCESS
        # Update should preserve the existing PhysicalResourceId
        assert result["PhysicalResourceId"] == "saved-objects-indexpatterns"


# =============================================================================
# Unit Tests - Handler Delete No-Op
# =============================================================================


class TestHandlerDeleteNoop:
    """Tests for Delete operations (no-op)."""
    
    @patch("urllib.request.urlopen")
    def test_handler_delete_noop(
        self,
        mock_urlopen,
        delete_event,
        mock_context
    ):
        """Test Delete event does nothing and returns SUCCESS."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute handler
        result = handler(delete_event, mock_context)
        
        # Verify result
        assert result["Status"] == SUCCESS
        assert result["PhysicalResourceId"] == "saved-objects-indexpatterns"
        assert "Delete operation completed" in result["Data"]["Message"]


# =============================================================================
# Unit Tests - Handler Missing Properties
# =============================================================================


class TestHandlerMissingProperties:
    """Tests for missing required properties."""
    
    @patch("urllib.request.urlopen")
    def test_handler_missing_s3_bucket(
        self,
        mock_urlopen,
        create_event,
        mock_context
    ):
        """Test handler fails when S3Bucket is missing."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Remove S3Bucket from properties
        del create_event["ResourceProperties"]["S3Bucket"]
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result
        assert result["Status"] == FAILED
        assert "S3Bucket" in result["Reason"]
    
    @patch("urllib.request.urlopen")
    def test_handler_missing_s3_key(
        self,
        mock_urlopen,
        create_event,
        mock_context
    ):
        """Test handler fails when S3Key is missing."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Remove S3Key from properties
        del create_event["ResourceProperties"]["S3Key"]
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result
        assert result["Status"] == FAILED
        assert "S3Key" in result["Reason"]
    
    @patch("urllib.request.urlopen")
    def test_handler_missing_both_properties(
        self,
        mock_urlopen,
        create_event,
        mock_context
    ):
        """Test handler fails when both S3Bucket and S3Key are missing."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Remove both properties
        del create_event["ResourceProperties"]["S3Bucket"]
        del create_event["ResourceProperties"]["S3Key"]
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result
        assert result["Status"] == FAILED
        assert "S3Bucket" in result["Reason"]
        assert "S3Key" in result["Reason"]


# =============================================================================
# Unit Tests - Handler S3 Errors
# =============================================================================


class TestHandlerS3Errors:
    """Tests for S3 download errors."""
    
    @patch("urllib.request.urlopen")
    @patch("app.S3Client")
    def test_handler_s3_download_error_not_found(
        self,
        mock_s3_client_class,
        mock_urlopen,
        create_event,
        mock_context
    ):
        """Test handler fails when S3 file not found."""
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.side_effect = S3ClientError(
            message="File not found: s3://test-assets-bucket/index-patterns.ndjson",
            bucket="test-assets-bucket",
            key="index-patterns.ndjson"
        )
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result
        assert result["Status"] == FAILED
        assert "S3 error" in result["Reason"]
        assert result["Data"]["ErrorType"] == "S3ClientError"
    
    @patch("urllib.request.urlopen")
    @patch("app.S3Client")
    def test_handler_s3_access_denied(
        self,
        mock_s3_client_class,
        mock_urlopen,
        create_event,
        mock_context
    ):
        """Test handler fails when S3 access denied."""
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.side_effect = S3ClientError(
            message="Access denied to s3://test-assets-bucket/index-patterns.ndjson",
            bucket="test-assets-bucket",
            key="index-patterns.ndjson"
        )
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result
        assert result["Status"] == FAILED
        assert "S3 error" in result["Reason"]


# =============================================================================
# Unit Tests - Handler OpenSearch Errors
# =============================================================================


class TestHandlerOpenSearchErrors:
    """Tests for OpenSearch import errors."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    @patch("app.S3Client")
    def test_handler_opensearch_connection_error(
        self,
        mock_s3_client_class,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        sample_ndjson_content
    ):
        """Test handler fails when OpenSearch connection fails."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.return_value = sample_ndjson_content
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.import_saved_objects.return_value = ImportResult(
            success=False,
            success_count=0,
            error_count=1,
            errors=[{"type": "connection_error", "message": "Connection refused"}],
            message="Connection error to OpenSearch endpoint: Connection refused"
        )
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result - total failure with 0 success count raises RuntimeError
        assert result["Status"] == FAILED
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    @patch("app.S3Client")
    def test_handler_opensearch_total_failure(
        self,
        mock_s3_client_class,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        sample_ndjson_content,
        failed_import_result
    ):
        """Test handler fails when all imports fail."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.return_value = sample_ndjson_content
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.import_saved_objects.return_value = failed_import_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result
        assert result["Status"] == FAILED
        assert "RuntimeError" in result["Data"]["ErrorType"]


# =============================================================================
# Unit Tests - Handler Partial Import Success
# =============================================================================


class TestHandlerPartialImportSuccess:
    """Tests for partial import success scenarios."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    @patch("app.S3Client")
    def test_handler_partial_import_success(
        self,
        mock_s3_client_class,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        sample_ndjson_content,
        partial_import_result
    ):
        """Test handler returns SUCCESS when some objects import successfully."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.return_value = sample_ndjson_content
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.import_saved_objects.return_value = partial_import_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result - partial success still returns SUCCESS
        assert result["Status"] == SUCCESS
        assert result["Data"]["SuccessCount"] == "2"
        assert result["Data"]["ErrorCount"] == "1"


# =============================================================================
# Unit Tests - Unknown Request Type
# =============================================================================


class TestHandlerUnknownRequestType:
    """Tests for unknown request types."""
    
    @patch("urllib.request.urlopen")
    def test_handler_unknown_request_type(
        self,
        mock_urlopen,
        create_event,
        mock_context
    ):
        """Test handler fails for unknown request type."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Change to unknown request type
        create_event["RequestType"] = "Unknown"
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify result
        assert result["Status"] == FAILED
        assert "Unknown RequestType" in result["Reason"]


# =============================================================================
# Unit Tests - Overwrite Parameter Handling
# =============================================================================


class TestOverwriteParameterHandling:
    """Tests for Overwrite parameter handling."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    @patch("app.S3Client")
    def test_handler_overwrite_false(
        self,
        mock_s3_client_class,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        sample_ndjson_content,
        success_import_result
    ):
        """Test handler passes overwrite=false correctly."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.return_value = sample_ndjson_content
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.import_saved_objects.return_value = success_import_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Set overwrite to false
        create_event["ResourceProperties"]["Overwrite"] = "false"
        
        # Execute handler
        result = handler(create_event, mock_context)
        
        # Verify OpenSearch client was called with overwrite=False
        mock_opensearch_client.import_saved_objects.assert_called_once_with(
            ndjson_content=sample_ndjson_content,
            overwrite=False
        )
        assert result["Data"]["Overwrite"] == "false"


# =============================================================================
# Unit Tests - Missing OpenSearch Endpoint
# =============================================================================


class TestMissingOpenSearchEndpoint:
    """Tests for missing OPENSEARCH_ENDPOINT environment variable."""
    
    @patch("urllib.request.urlopen")
    @patch("app.S3Client")
    def test_handler_missing_opensearch_endpoint(
        self,
        mock_s3_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        sample_ndjson_content
    ):
        """Test handler fails when OPENSEARCH_ENDPOINT is not set."""
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_s3_client.download_file.return_value = sample_ndjson_content
        mock_s3_client_class.return_value = mock_s3_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Remove OPENSEARCH_ENDPOINT
        original_endpoint = os.environ.get("OPENSEARCH_ENDPOINT")
        os.environ.pop("OPENSEARCH_ENDPOINT", None)
        
        try:
            # Execute handler
            result = handler(create_event, mock_context)
            
            # Verify result
            assert result["Status"] == FAILED
            assert "OPENSEARCH_ENDPOINT" in result["Reason"]
        finally:
            # Restore environment variable
            if original_endpoint:
                os.environ["OPENSEARCH_ENDPOINT"] = original_endpoint


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])