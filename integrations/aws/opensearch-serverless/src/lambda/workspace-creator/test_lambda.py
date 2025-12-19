# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for the OpenSearch Workspace Creator Lambda function.

These tests use pytest and mocking to test the Lambda handler and helper functions
without requiring actual AWS services.
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, Mock
from typing import Any, Dict


# Set environment variables before importing the handler
os.environ["OPENSEARCH_ENDPOINT"] = "https://test-app.us-east-1.es.amazonaws.com"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


# Import after setting environment variables
from app import (
    handler,
    send_cfn_response,
    get_physical_resource_id,
    parse_list_property,
    parse_dict_property,
    handle_create,
    handle_update,
    handle_delete,
    SUCCESS,
    FAILED,
)
from helpers.opensearch_client import OpenSearchClient, WorkspaceResult


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_context():
    """Create a mock Lambda context object."""
    context = MagicMock()
    context.function_name = "workspace-creator"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:workspace-creator"
    context.memory_limit_in_mb = 256
    context.aws_request_id = "test-request-id-12345"
    context.log_group_name = "/aws/lambda/workspace-creator"
    context.log_stream_name = "2024/01/01/[$LATEST]abcdef123456"
    context.get_remaining_time_in_millis = MagicMock(return_value=300000)
    return context


@pytest.fixture
def create_event():
    """Sample CloudFormation Create event."""
    return {
        "RequestType": "Create",
        "ResponseURL": "https://cloudformation-custom-resource-response.s3.amazonaws.com/test-response-url",
        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/guid-12345",
        "RequestId": "unique-request-id-create",
        "ResourceType": "Custom::OpenSearchWorkspace",
        "LogicalResourceId": "SecurityWorkspace",
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:workspace-creator",
            "OpenSearchEndpoint": "https://test-app.us-east-1.es.amazonaws.com",
            "WorkspaceName": "Security Analytics",
            "WorkspaceDescription": "Security analytics workspace",
            "WorkspaceColor": "#54B399",
            "WorkspaceFeatures": ["use-case-observability"],
            "DataSourceIds": ["ds-12345-uuid"]
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
        "ResourceType": "Custom::OpenSearchWorkspace",
        "LogicalResourceId": "SecurityWorkspace",
        "PhysicalResourceId": "workspace-abc12345-def6-7890-ghij-klmnopqrstuv",
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:workspace-creator",
            "OpenSearchEndpoint": "https://test-app.us-east-1.es.amazonaws.com",
            "WorkspaceName": "Security Analytics Updated",
            "WorkspaceDescription": "Updated description",
            "WorkspaceColor": "#FF0000"
        },
        "OldResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:workspace-creator",
            "OpenSearchEndpoint": "https://test-app.us-east-1.es.amazonaws.com",
            "WorkspaceName": "Security Analytics",
            "WorkspaceDescription": "Security analytics workspace"
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
        "ResourceType": "Custom::OpenSearchWorkspace",
        "LogicalResourceId": "SecurityWorkspace",
        "PhysicalResourceId": "workspace-abc12345-def6-7890-ghij-klmnopqrstuv",
        "ResourceProperties": {
            "ServiceToken": "arn:aws:lambda:us-east-1:123456789012:function:workspace-creator",
            "OpenSearchEndpoint": "https://test-app.us-east-1.es.amazonaws.com",
            "WorkspaceName": "Security Analytics"
        }
    }


@pytest.fixture
def success_create_result():
    """Mock successful workspace creation result."""
    return WorkspaceResult(
        success=True,
        workspace_id="abc12345-def6-7890-ghij-klmnopqrstuv",
        message="Workspace create completed successfully: id=abc12345-def6-7890-ghij-klmnopqrstuv"
    )


@pytest.fixture
def success_update_result():
    """Mock successful workspace update result."""
    return WorkspaceResult(
        success=True,
        workspace_id="abc12345-def6-7890-ghij-klmnopqrstuv",
        message="Workspace update completed successfully"
    )


@pytest.fixture
def success_delete_result():
    """Mock successful workspace deletion result."""
    return WorkspaceResult(
        success=True,
        workspace_id="abc12345-def6-7890-ghij-klmnopqrstuv",
        message="Workspace deleted successfully"
    )


@pytest.fixture
def failed_result():
    """Mock failed workspace operation result."""
    return WorkspaceResult(
        success=False,
        message="HTTP error 403: Access denied",
        error_code="HTTP_403"
    )


# =============================================================================
# Unit Tests - Helper Functions
# =============================================================================


class TestParseListProperty:
    """Tests for parse_list_property function."""
    
    def test_parse_list_from_list(self):
        """Test parsing an actual list."""
        result = parse_list_property(["item1", "item2"])
        assert result == ["item1", "item2"]
    
    def test_parse_list_from_comma_string(self):
        """Test parsing comma-separated string."""
        result = parse_list_property("item1, item2, item3")
        assert result == ["item1", "item2", "item3"]
    
    def test_parse_list_from_comma_string_no_spaces(self):
        """Test parsing comma-separated string without spaces."""
        result = parse_list_property("item1,item2,item3")
        assert result == ["item1", "item2", "item3"]
    
    def test_parse_list_from_none(self):
        """Test parsing None returns None."""
        assert parse_list_property(None) is None
    
    def test_parse_list_from_empty_string(self):
        """Test parsing empty string."""
        result = parse_list_property("")
        assert result == []
    
    def test_parse_list_single_item(self):
        """Test parsing single item string."""
        result = parse_list_property("single-item")
        assert result == ["single-item"]


class TestParseDictProperty:
    """Tests for parse_dict_property function."""
    
    def test_parse_dict_from_dict(self):
        """Test parsing an actual dict."""
        input_dict = {"key": "value", "nested": {"inner": "data"}}
        result = parse_dict_property(input_dict)
        assert result == input_dict
    
    def test_parse_dict_from_json_string(self):
        """Test parsing JSON string."""
        json_str = '{"key": "value"}'
        result = parse_dict_property(json_str)
        assert result == {"key": "value"}
    
    def test_parse_dict_from_none(self):
        """Test parsing None returns None."""
        assert parse_dict_property(None) is None
    
    def test_parse_dict_from_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        result = parse_dict_property("not valid json")
        assert result is None


class TestGetPhysicalResourceId:
    """Tests for get_physical_resource_id function."""
    
    def test_with_workspace_id(self):
        """Test with workspace ID provided."""
        result = get_physical_resource_id("Test Workspace", "abc123-uuid")
        assert result == "workspace-abc123-uuid"
    
    def test_without_workspace_id(self):
        """Test without workspace ID."""
        result = get_physical_resource_id("Security Analytics")
        assert result == "workspace-security-analytics"
    
    def test_with_spaces(self):
        """Test workspace name with spaces."""
        result = get_physical_resource_id("My Test Workspace")
        assert result == "workspace-my-test-workspace"
    
    def test_long_name_truncation(self):
        """Test that long names are truncated."""
        long_name = "A" * 100
        result = get_physical_resource_id(long_name)
        assert result.startswith("workspace-")
        assert len(result) <= 60  # 10 (prefix) + 50 (max name)


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
            data={"WorkspaceId": "test-id"},
            physical_resource_id="test-resource-id"
        )
        
        # Verify urlopen was called
        assert mock_urlopen.called
        call_args = mock_urlopen.call_args[0][0]
        assert call_args.method == "PUT"
        
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
# Unit Tests - Handler Create
# =============================================================================


class TestHandlerCreate:
    """Tests for Create operation."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_create_success(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test successful Create event handling."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == SUCCESS
        assert "PhysicalResourceId" in result
        assert result["Data"]["WorkspaceId"] == "abc12345-def6-7890-ghij-klmnopqrstuv"
        
        # Verify OpenSearch client was called correctly
        mock_opensearch_client.create_workspace.assert_called_once()
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["name"] == "Security Analytics"
        assert call_kwargs["color"] == "#54B399"
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_create_failure(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        failed_result
    ):
        """Test failed Create event handling."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = failed_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == FAILED
        assert "RuntimeError" in result["Data"]["ErrorType"]
    
    @patch("urllib.request.urlopen")
    def test_handler_create_missing_workspace_name(
        self,
        mock_urlopen,
        create_event,
        mock_context
    ):
        """Test Create fails when WorkspaceName is missing."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        del create_event["ResourceProperties"]["WorkspaceName"]
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == FAILED
        assert "WorkspaceName" in result["Reason"]


# =============================================================================
# Unit Tests - Handler Update
# =============================================================================


class TestHandlerUpdate:
    """Tests for Update operation."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_update_success(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        update_event,
        mock_context,
        success_update_result
    ):
        """Test successful Update event handling."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.update_workspace.return_value = success_update_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = handler(update_event, mock_context)
        
        assert result["Status"] == SUCCESS
        assert result["PhysicalResourceId"] == "workspace-abc12345-def6-7890-ghij-klmnopqrstuv"
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_update_failure(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        update_event,
        mock_context,
        failed_result
    ):
        """Test failed Update event handling."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.update_workspace.return_value = failed_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = handler(update_event, mock_context)
        
        assert result["Status"] == FAILED


# =============================================================================
# Unit Tests - Handler Delete
# =============================================================================


class TestHandlerDelete:
    """Tests for Delete operation."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_delete_success(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        delete_event,
        mock_context,
        success_delete_result
    ):
        """Test successful Delete event handling."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.delete_workspace.return_value = success_delete_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = handler(delete_event, mock_context)
        
        assert result["Status"] == SUCCESS
        assert result["PhysicalResourceId"] == "workspace-abc12345-def6-7890-ghij-klmnopqrstuv"
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_delete_not_found(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        delete_event,
        mock_context
    ):
        """Test Delete succeeds even when workspace not found."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.delete_workspace.return_value = WorkspaceResult(
            success=True,
            workspace_id="abc12345-def6-7890-ghij-klmnopqrstuv",
            message="Workspace not found (already deleted)"
        )
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = handler(delete_event, mock_context)
        
        assert result["Status"] == SUCCESS
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_delete_no_workspace_id(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        delete_event,
        mock_context
    ):
        """Test Delete succeeds when workspace ID cannot be determined."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Set a physical resource ID that doesn't contain a valid workspace ID
        delete_event["PhysicalResourceId"] = "workspace-invalid"
        
        result = handler(delete_event, mock_context)
        
        # Should succeed with a warning
        assert result["Status"] == SUCCESS


# =============================================================================
# Unit Tests - Handler Unknown Request Type
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
        
        create_event["RequestType"] = "Unknown"
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == FAILED
        assert "Unknown RequestType" in result["Reason"]


# =============================================================================
# Unit Tests - Missing OpenSearch Endpoint
# =============================================================================


class TestMissingOpenSearchEndpoint:
    """Tests for missing OPENSEARCH_ENDPOINT."""
    
    @patch("urllib.request.urlopen")
    def test_handler_missing_opensearch_endpoint(
        self,
        mock_urlopen,
        create_event,
        mock_context
    ):
        """Test handler fails when OPENSEARCH_ENDPOINT is not set."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Remove endpoint from both environment and properties
        original_endpoint = os.environ.get("OPENSEARCH_ENDPOINT")
        os.environ.pop("OPENSEARCH_ENDPOINT", None)
        del create_event["ResourceProperties"]["OpenSearchEndpoint"]
        
        try:
            result = handler(create_event, mock_context)
            
            assert result["Status"] == FAILED
            assert "endpoint" in result["Reason"].lower()
        finally:
            if original_endpoint:
                os.environ["OPENSEARCH_ENDPOINT"] = original_endpoint


# =============================================================================
# Unit Tests - WorkspaceResult Dataclass
# =============================================================================


class TestWorkspaceResult:
    """Tests for WorkspaceResult dataclass."""
    
    def test_success_result(self):
        """Test successful result creation."""
        result = WorkspaceResult(
            success=True,
            workspace_id="test-id",
            message="Success"
        )
        
        assert result.success is True
        assert result.workspace_id == "test-id"
        assert result.message == "Success"
    
    def test_failure_result(self):
        """Test failure result creation."""
        result = WorkspaceResult(
            success=False,
            message="Error occurred",
            error_code="HTTP_500"
        )
        
        assert result.success is False
        assert result.workspace_id is None
        assert result.error_code == "HTTP_500"
    
    def test_to_dict(self):
        """Test to_dict method."""
        result = WorkspaceResult(
            success=True,
            workspace_id="test-id",
            message="Success"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["workspaceId"] == "test-id"
        assert result_dict["message"] == "Success"


# =============================================================================
# Unit Tests - Feature and Data Source Handling
# =============================================================================


class TestFeatureAndDataSourceHandling:
    """Tests for handling workspace features and data sources."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_with_features_list(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test Create with features as list."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        create_event["ResourceProperties"]["WorkspaceFeatures"] = ["use-case-observability", "use-case-security"]
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == SUCCESS
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["features"] == ["use-case-observability", "use-case-security"]
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_with_features_string(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test Create with features as comma-separated string."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        create_event["ResourceProperties"]["WorkspaceFeatures"] = "use-case-observability, use-case-security"
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == SUCCESS
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["features"] == ["use-case-observability", "use-case-security"]
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_with_data_sources(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test Create with data source IDs."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        create_event["ResourceProperties"]["DataSourceIds"] = ["ds-1", "ds-2"]
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == SUCCESS
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["data_source_ids"] == ["ds-1", "ds-2"]


# =============================================================================
# Unit Tests - Permissions Handling
# =============================================================================


class TestPermissionsHandling:
    """Tests for handling workspace permissions."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_with_permissions_dict(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test Create with permissions as dict."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        permissions = {
            "library_write": {"users": ["%me%"]},
            "write": {"users": ["%me%"]}
        }
        create_event["ResourceProperties"]["Permissions"] = permissions
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == SUCCESS
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["permissions"] == permissions
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_with_permissions_json_string(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test Create with permissions as JSON string."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        permissions = {
            "library_write": {"users": ["%me%"]},
            "write": {"users": ["%me%"]}
        }
        create_event["ResourceProperties"]["Permissions"] = json.dumps(permissions)
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == SUCCESS
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["permissions"] == permissions


# =============================================================================
# Unit Tests - List Workspaces
# =============================================================================


class TestListWorkspaces:
    """Tests for list_workspaces operation."""
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_list_workspaces_success(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test successful workspace listing."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "workspaces": [
                    {"id": "ws-1", "name": "Workspace 1"},
                    {"id": "ws-2", "name": "Workspace 2"}
                ],
                "total": 2
            }
        }
        mock_response.text = '{"success": true}'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.list_workspaces()
        
        assert result.success is True
        assert "2 workspaces" in result.message
        assert len(result.response_data["result"]["workspaces"]) == 2
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_list_workspaces_empty(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test listing when no workspaces exist."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock empty response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "workspaces": [],
                "total": 0
            }
        }
        mock_response.text = '{"success": true}'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.list_workspaces()
        
        assert result.success is True
        assert "0 workspaces" in result.message
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_list_workspaces_http_error(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test list workspaces with HTTP error."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock error response
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = "Access denied"
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.list_workspaces()
        
        assert result.success is False
        assert result.error_code == "HTTP_403"
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_list_workspaces_with_pagination(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test list workspaces with pagination parameters."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "workspaces": [{"id": "ws-1", "name": "Test"}],
                "total": 50
            }
        }
        mock_response.text = '{"success": true}'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.list_workspaces(per_page=10, page=2)
        
        assert result.success is True
        # Verify the request was made with correct pagination params
        call_kwargs = mock_requests_get.call_args
        assert call_kwargs[1]["params"]["perPage"] == 10
        assert call_kwargs[1]["params"]["page"] == 2


# =============================================================================
# Unit Tests - Find Workspace By Name
# =============================================================================


class TestFindWorkspaceByName:
    """Tests for find_workspace_by_name operation."""
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_find_workspace_found(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test finding an existing workspace by name."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response with matching workspace
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "workspaces": [
                    {"id": "ws-1", "name": "Other Workspace"},
                    {"id": "ws-target", "name": "Target Workspace"},
                    {"id": "ws-3", "name": "Another Workspace"}
                ],
                "total": 3
            }
        }
        mock_response.text = '{"success": true}'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.find_workspace_by_name("Target Workspace")
        
        assert result.success is True
        assert result.workspace_id == "ws-target"
        assert result.response_data["name"] == "Target Workspace"
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_find_workspace_not_found(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test finding a non-existent workspace by name."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response without matching workspace
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "workspaces": [
                    {"id": "ws-1", "name": "Other Workspace"},
                    {"id": "ws-2", "name": "Another Workspace"}
                ],
                "total": 2
            }
        }
        mock_response.text = '{"success": true}'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.find_workspace_by_name("Non-Existent Workspace")
        
        assert result.success is False
        assert result.error_code == "NOT_FOUND"
        assert "not found" in result.message.lower()
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_find_workspace_list_fails(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test find_workspace_by_name when list operation fails."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock error response
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.find_workspace_by_name("Test Workspace")
        
        assert result.success is False
        assert "HTTP_500" in result.error_code


# =============================================================================
# Unit Tests - OpenSearch Client Methods
# =============================================================================


class TestOpenSearchClientMethods:
    """Additional tests for OpenSearchClient methods."""
    
    @patch("helpers.opensearch_client.requests.post")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_create_workspace_api_format(
        self,
        mock_get_session,
        mock_requests_post
    ):
        """Test that create workspace sends correct API format."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {"id": "new-ws-id"}
        }
        mock_response.text = '{"success": true}'
        mock_requests_post.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        client.create_workspace(
            name="Test Workspace",
            description="Test Description",
            color="#FF0000",
            features=["use-case-security"],
            data_source_ids=["ds-1"]
        )
        
        # Verify the request body structure
        call_kwargs = mock_requests_post.call_args
        request_body = call_kwargs[1]["json"]
        
        assert "attributes" in request_body
        assert request_body["attributes"]["name"] == "Test Workspace"
        assert request_body["attributes"]["description"] == "Test Description"
        assert request_body["attributes"]["color"] == "#FF0000"
        assert request_body["attributes"]["features"] == ["use-case-security"]
        
        assert "settings" in request_body
        assert request_body["settings"]["dataSources"] == ["ds-1"]
    
    @patch("helpers.opensearch_client.requests.put")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_update_workspace_api_format(
        self,
        mock_get_session,
        mock_requests_put
    ):
        """Test that update workspace sends correct API format."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": True
        }
        mock_response.text = '{"success": true}'
        mock_requests_put.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        client.update_workspace(
            workspace_id="ws-12345",
            name="Updated Name",
            color="#00FF00"
        )
        
        # Verify URL contains workspace ID
        call_kwargs = mock_requests_put.call_args
        url = call_kwargs[0][0]
        assert "/api/workspaces/ws-12345" in url
        
        # Verify request body structure
        request_body = call_kwargs[1]["json"]
        assert "attributes" in request_body
        assert request_body["attributes"]["name"] == "Updated Name"
        assert request_body["attributes"]["color"] == "#00FF00"
    
    @patch("helpers.opensearch_client.requests.delete")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_delete_workspace_api_format(
        self,
        mock_get_session,
        mock_requests_delete
    ):
        """Test that delete workspace uses correct API endpoint."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": True
        }
        mock_response.text = '{"success": true}'
        mock_requests_delete.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.delete_workspace(workspace_id="ws-to-delete")
        
        assert result.success is True
        
        # Verify URL contains workspace ID
        call_kwargs = mock_requests_delete.call_args
        url = call_kwargs[0][0]
        assert "/api/workspaces/ws-to-delete" in url
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_get_workspace_api_format(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test that get workspace uses correct API endpoint."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "id": "ws-get-test",
                "name": "Test Workspace"
            }
        }
        mock_response.text = '{"success": true}'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.get_workspace(workspace_id="ws-get-test")
        
        assert result.success is True
        assert result.workspace_id == "ws-get-test"
        
        # Verify URL contains workspace ID
        call_kwargs = mock_requests_get.call_args
        url = call_kwargs[0][0]
        assert "/api/workspaces/ws-get-test" in url


# =============================================================================
# Unit Tests - Data Source Lookup Methods
# =============================================================================


class TestListDataSources:
    """Tests for list_data_sources operation."""
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_list_data_sources_success(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test successful data source listing."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock successful response with data sources
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "ds-uuid-1",
                "title": "Security Lake Collection",
                "dataSourceEngineType": "OpenSearch Serverless",
                "references": [
                    {"id": "arn:aws:aoss:us-east-1:123456789012:collection/abc123"}
                ]
            },
            {
                "id": "ds-uuid-2",
                "title": "Analytics Collection",
                "dataSourceEngineType": "OpenSearch Serverless",
                "references": [
                    {"id": "arn:aws:aoss:us-east-1:123456789012:collection/def456"}
                ]
            }
        ]
        mock_response.text = '[...]'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.list_data_sources()
        
        assert result.success is True
        assert "2 data sources" in result.message
        assert len(result.response_data["data_sources"]) == 2
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_list_data_sources_empty(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test listing when no data sources exist."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock empty response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.text = '[]'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.list_data_sources()
        
        assert result.success is True
        assert "0 data sources" in result.message
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_list_data_sources_http_error(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test list data sources with HTTP error."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock error response
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = "Access denied"
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.list_data_sources()
        
        assert result.success is False
        assert result.error_code == "HTTP_403"


class TestFindDataSourceByCollectionArn:
    """Tests for find_data_source_by_collection_arn operation."""
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_find_data_source_by_arn_found(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test finding a data source by collection ARN."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        target_arn = "arn:aws:aoss:us-east-1:123456789012:collection/target123"
        
        # Mock response with matching data source
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "ds-uuid-other",
                "title": "Other Collection",
                "dataSourceEngineType": "OpenSearch Serverless",
                "references": [
                    {"id": "arn:aws:aoss:us-east-1:123456789012:collection/other"}
                ]
            },
            {
                "id": "ds-uuid-target",
                "title": "Target Collection",
                "dataSourceEngineType": "OpenSearch Serverless",
                "references": [
                    {"id": target_arn}
                ]
            }
        ]
        mock_response.text = '[...]'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.find_data_source_by_collection_arn(target_arn)
        
        assert result.success is True
        assert result.workspace_id == "ds-uuid-target"
        assert result.response_data["id"] == "ds-uuid-target"
        assert "Target Collection" in result.message
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_find_data_source_by_arn_not_found(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test when no data source matches the collection ARN."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response without matching data source
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "ds-uuid-1",
                "title": "Other Collection",
                "dataSourceEngineType": "OpenSearch Serverless",
                "references": [
                    {"id": "arn:aws:aoss:us-east-1:123456789012:collection/other"}
                ]
            }
        ]
        mock_response.text = '[...]'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.find_data_source_by_collection_arn(
            "arn:aws:aoss:us-east-1:123456789012:collection/nonexistent"
        )
        
        assert result.success is False
        assert result.error_code == "NOT_FOUND"


class TestFindDataSourceByTitle:
    """Tests for find_data_source_by_title operation."""
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_find_data_source_by_title_found(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test finding a data source by title."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response with matching data source
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "ds-uuid-1",
                "title": "Other Collection",
                "dataSourceEngineType": "OpenSearch Serverless"
            },
            {
                "id": "ds-uuid-target",
                "title": "Security Lake Data",
                "dataSourceEngineType": "OpenSearch Serverless"
            }
        ]
        mock_response.text = '[...]'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.find_data_source_by_title("Security Lake Data")
        
        assert result.success is True
        assert result.workspace_id == "ds-uuid-target"
        assert result.response_data["id"] == "ds-uuid-target"
    
    @patch("helpers.opensearch_client.requests.get")
    @patch("helpers.opensearch_client.get_boto3_session")
    def test_find_data_source_by_title_not_found(
        self,
        mock_get_session,
        mock_requests_get
    ):
        """Test when no data source matches the title."""
        # Mock boto3 session
        mock_session = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-access-key"
        mock_credentials.secret_key = "test-secret-key"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_get_session.return_value = mock_session
        
        # Mock response without matching data source
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "ds-uuid-1",
                "title": "Other Collection",
                "dataSourceEngineType": "OpenSearch Serverless"
            }
        ]
        mock_response.text = '[...]'
        mock_requests_get.return_value = mock_response
        
        client = OpenSearchClient(endpoint="https://test.es.amazonaws.com")
        result = client.find_data_source_by_title("Non-Existent Data Source")
        
        assert result.success is False
        assert result.error_code == "NOT_FOUND"


# =============================================================================
# Unit Tests - resolve_data_source_ids Function
# =============================================================================


class TestResolveDataSourceIds:
    """Tests for resolve_data_source_ids function."""
    
    def test_resolve_explicit_data_source_ids(self):
        """Test resolving when explicit DataSourceIds are provided."""
        from app import resolve_data_source_ids
        
        mock_client = MagicMock()
        properties = {
            "DataSourceIds": ["uuid-1", "uuid-2"]
        }
        
        result = resolve_data_source_ids(properties, mock_client)
        
        assert result == ["uuid-1", "uuid-2"]
        # Should not call any lookup methods
        mock_client.find_data_source_by_collection_arn.assert_not_called()
        mock_client.find_data_source_by_title.assert_not_called()
    
    def test_resolve_by_collection_arn(self):
        """Test resolving data source ID by collection ARN."""
        from app import resolve_data_source_ids
        
        mock_client = MagicMock()
        mock_client.find_data_source_by_collection_arn.return_value = WorkspaceResult(
            success=True,
            workspace_id="resolved-uuid-from-arn",
            message="Found data source",
            response_data={"id": "resolved-uuid-from-arn"}
        )
        
        properties = {
            "CollectionArn": "arn:aws:aoss:us-east-1:123456789012:collection/abc123"
        }
        
        result = resolve_data_source_ids(properties, mock_client)
        
        assert result == ["resolved-uuid-from-arn"]
        mock_client.find_data_source_by_collection_arn.assert_called_once_with(
            "arn:aws:aoss:us-east-1:123456789012:collection/abc123"
        )
    
    def test_resolve_by_data_source_title(self):
        """Test resolving data source ID by title."""
        from app import resolve_data_source_ids
        
        mock_client = MagicMock()
        mock_client.find_data_source_by_title.return_value = WorkspaceResult(
            success=True,
            workspace_id="resolved-uuid-from-title",
            message="Found data source",
            response_data={"id": "resolved-uuid-from-title"}
        )
        
        properties = {
            "DataSourceTitle": "Security Lake Collection"
        }
        
        result = resolve_data_source_ids(properties, mock_client)
        
        assert result == ["resolved-uuid-from-title"]
        mock_client.find_data_source_by_title.assert_called_once_with(
            "Security Lake Collection"
        )
    
    def test_resolve_no_data_source_config(self):
        """Test when no data source configuration is provided."""
        from app import resolve_data_source_ids
        
        mock_client = MagicMock()
        properties = {}
        
        result = resolve_data_source_ids(properties, mock_client)
        
        assert result is None
    
    def test_resolve_collection_arn_lookup_fails(self):
        """Test when collection ARN lookup fails."""
        from app import resolve_data_source_ids
        
        mock_client = MagicMock()
        mock_client.find_data_source_by_collection_arn.return_value = WorkspaceResult(
            success=False,
            message="Data source not found for collection ARN",
            error_code="NOT_FOUND"
        )
        
        properties = {
            "CollectionArn": "arn:aws:aoss:us-east-1:123456789012:collection/missing"
        }
        
        result = resolve_data_source_ids(properties, mock_client)
        
        assert result is None
    
    def test_resolve_explicit_ids_take_priority(self):
        """Test that explicit DataSourceIds take priority over lookup."""
        from app import resolve_data_source_ids
        
        mock_client = MagicMock()
        properties = {
            "DataSourceIds": ["explicit-uuid"],
            "CollectionArn": "arn:aws:aoss:us-east-1:123456789012:collection/abc123",
            "DataSourceTitle": "Some Title"
        }
        
        result = resolve_data_source_ids(properties, mock_client)
        
        assert result == ["explicit-uuid"]
        # Lookup methods should not be called
        mock_client.find_data_source_by_collection_arn.assert_not_called()
        mock_client.find_data_source_by_title.assert_not_called()
    
    def test_resolve_collection_arn_priority_over_title(self):
        """Test that CollectionArn takes priority over DataSourceTitle."""
        from app import resolve_data_source_ids
        
        mock_client = MagicMock()
        mock_client.find_data_source_by_collection_arn.return_value = WorkspaceResult(
            success=True,
            workspace_id="uuid-from-arn",
            message="Found data source",
            response_data={"id": "uuid-from-arn"}
        )
        
        properties = {
            "CollectionArn": "arn:aws:aoss:us-east-1:123456789012:collection/abc123",
            "DataSourceTitle": "Fallback Title"
        }
        
        result = resolve_data_source_ids(properties, mock_client)
        
        assert result == ["uuid-from-arn"]
        mock_client.find_data_source_by_collection_arn.assert_called_once()
        mock_client.find_data_source_by_title.assert_not_called()


# =============================================================================
# Unit Tests - Handler with Data Source Resolution
# =============================================================================


class TestHandlerWithDataSourceResolution:
    """Tests for handler with data source resolution."""
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_create_with_collection_arn(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test Create with data source resolution by CollectionArn."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client.find_data_source_by_collection_arn.return_value = WorkspaceResult(
            success=True,
            workspace_id="resolved-ds-uuid",
            message="Found data source",
            response_data={"id": "resolved-ds-uuid"}
        )
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Use CollectionArn instead of explicit DataSourceIds
        create_event["ResourceProperties"]["CollectionArn"] = (
            "arn:aws:aoss:us-east-1:123456789012:collection/abc123"
        )
        del create_event["ResourceProperties"]["DataSourceIds"]
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == SUCCESS
        # Verify data source resolution was called
        mock_opensearch_client.find_data_source_by_collection_arn.assert_called_once()
        # Verify resolved data source ID was passed to create_workspace
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["data_source_ids"] == ["resolved-ds-uuid"]
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_create_with_data_source_title(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test Create with data source resolution by DataSourceTitle."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client.find_data_source_by_title.return_value = WorkspaceResult(
            success=True,
            workspace_id="title-resolved-uuid",
            message="Found data source",
            response_data={"id": "title-resolved-uuid"}
        )
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Use DataSourceTitle instead of explicit DataSourceIds
        create_event["ResourceProperties"]["DataSourceTitle"] = "Security Lake Data Source"
        del create_event["ResourceProperties"]["DataSourceIds"]
        
        result = handler(create_event, mock_context)
        
        assert result["Status"] == SUCCESS
        # Verify data source resolution was called
        mock_opensearch_client.find_data_source_by_title.assert_called_once_with(
            "Security Lake Data Source"
        )
        # Verify resolved data source ID was passed to create_workspace
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["data_source_ids"] == ["title-resolved-uuid"]
    
    @patch("urllib.request.urlopen")
    @patch("app.OpenSearchClient")
    def test_handler_create_data_source_resolution_fails(
        self,
        mock_opensearch_client_class,
        mock_urlopen,
        create_event,
        mock_context,
        success_create_result
    ):
        """Test Create continues when data source resolution fails (returns None)."""
        mock_opensearch_client = MagicMock()
        mock_opensearch_client.create_workspace.return_value = success_create_result
        mock_opensearch_client.find_data_source_by_collection_arn.return_value = WorkspaceResult(
            success=False,
            message="Data source not found",
            error_code="NOT_FOUND"
        )
        mock_opensearch_client_class.return_value = mock_opensearch_client
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Use CollectionArn that won't be found
        create_event["ResourceProperties"]["CollectionArn"] = (
            "arn:aws:aoss:us-east-1:123456789012:collection/missing"
        )
        del create_event["ResourceProperties"]["DataSourceIds"]
        
        result = handler(create_event, mock_context)
        
        # Should still succeed, just without data sources
        assert result["Status"] == SUCCESS
        # Verify create_workspace was called with None for data_source_ids
        call_kwargs = mock_opensearch_client.create_workspace.call_args[1]
        assert call_kwargs["data_source_ids"] is None


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
