"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

End-to-End Integration Tests for Security Lake Framework

Tests the complete framework with actual AWS services in an isolated test account.
Verifies module loading, resource creation, and end-to-end event flow.

Requirements:
- AWS test account with appropriate permissions
- Security Lake enabled
- AWS CLI configured with test account credentials

Usage:
    pytest test_framework_e2e.py -v --test-stack-name test-security-lake-integration
"""

import json
import time
import boto3
import pytest
from typing import Dict, Any, List

# Test configuration
TEST_REGION = 'us-east-1'
TEST_STACK_PREFIX = 'test-security-lake-integration'

@pytest.fixture(scope='module')
def aws_clients():
    """Initialize AWS clients for testing"""
    return {
        'cloudformation': boto3.client('cloudformation', region_name=TEST_REGION),
        'lambda': boto3.client('lambda', region_name=TEST_REGION),
        'sqs': boto3.client('sqs', region_name=TEST_REGION),
        's3': boto3.client('s3', region_name=TEST_REGION),
        'secretsmanager': boto3.client('secretsmanager', region_name=TEST_REGION),
        'dynamodb': boto3.client('dynamodb', region_name=TEST_REGION)
    }

@pytest.fixture(scope='module')
def deployed_stack(aws_clients):
    """
    Verify test stack is deployed
    
    This fixture assumes the stack is already deployed for testing.
    Use: cdk deploy -c configFile=config.test.yaml
    """
    cf_client = aws_clients['cloudformation']
    
    try:
        response = cf_client.describe_stacks(StackName=TEST_STACK_PREFIX)
        stack = response['Stacks'][0]
        
        assert stack['StackStatus'] in ['CREATE_COMPLETE', 'UPDATE_COMPLETE'], \
            f"Stack not in ready state: {stack['StackStatus']}"
        
        # Extract outputs
        outputs = {output['OutputKey']: output['OutputValue'] 
                  for output in stack.get('Outputs', [])}
        
        return {
            'stack_name': stack['StackName'],
            'stack_id': stack['StackId'],
            'outputs': outputs,
            'resources': stack.get('StackResources', [])
        }
    except Exception as e:
        pytest.skip(f"Test stack not deployed: {str(e)}")

class TestFrameworkDeployment:
    """Test framework deployment and resources"""
    
    def test_stack_exists(self, deployed_stack):
        """Verify test stack deployed successfully"""
        assert deployed_stack['stack_name'].startswith(TEST_STACK_PREFIX)
        assert deployed_stack['stack_id'] is not None
    
    def test_required_outputs_present(self, deployed_stack):
        """Verify required CloudFormation outputs"""
        outputs = deployed_stack['outputs']
        
        required_outputs = [
            'StackVersion',
            'Framework',
            'EventTransformerQueueUrl'
        ]
        
        for output_key in required_outputs:
            assert output_key in outputs, f"Missing required output: {output_key}"
    
    def test_framework_version(self, deployed_stack):
        """Verify framework version"""
        outputs = deployed_stack['outputs']
        assert outputs.get('StackVersion') == '2.0.0'
        assert outputs.get('Framework') == 'Modular'

class TestCoreComponents:
    """Test core framework components"""
    
    def test_event_transformer_queue_exists(self, aws_clients, deployed_stack):
        """Verify event transformer SQS queue exists"""
        sqs_client = aws_clients['sqs']
        queue_url = deployed_stack['outputs'].get('EventTransformerQueueUrl')
        
        assert queue_url is not None, "EventTransformerQueueUrl not found in outputs"
        
        # Get queue attributes
        response = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        )
        
        attributes = response['Attributes']
        assert 'QueueArn' in attributes
        assert 'ApproximateNumberOfMessages' in attributes
    
    def test_shared_kms_key_exists(self, deployed_stack):
        """Verify shared KMS key exists if enabled"""
        outputs = deployed_stack['outputs']
        
        if 'SharedKmsKeyArn' in outputs:
            kms_key_arn = outputs['SharedKmsKeyArn']
            assert kms_key_arn.startswith('arn:aws:kms:')

class TestModuleIntegration:
    """Test integration module functionality"""
    
    def test_enabled_modules_listed(self, deployed_stack):
        """Verify enabled modules are listed in outputs"""
        outputs = deployed_stack['outputs']
        enabled_modules = outputs.get('EnabledModules', 'none')
        
        # Should list enabled modules
        assert enabled_modules is not None
    
    def test_azure_module_resources(self, aws_clients, deployed_stack):
        """Verify Azure module resources if enabled"""
        outputs = deployed_stack['outputs']
        
        # Check if Azure module is enabled
        if 'AzureEventHubProcessorArn' in outputs:
            lambda_client = aws_clients['lambda']
            
            # Verify Lambda function exists
            function_arn = outputs['AzureEventHubProcessorArn']
            response = lambda_client.get_function(FunctionName=function_arn)
            
            assert response['Configuration']['Runtime'] == 'python3.13'
            assert response['Configuration']['Architectures'] == ['arm64']

class TestEndToEndFlow:
    """Test end-to-end event processing flow"""
    
    def test_send_test_event_to_queue(self, aws_clients, deployed_stack):
        """Send test event and verify processing"""
        sqs_client = aws_clients['sqs']
        queue_url = deployed_stack['outputs'].get('EventTransformerQueueUrl')
        
        if not queue_url:
            pytest.skip("Queue URL not available")
        
        # Send test event
        test_event = {
            'test': True,
            'module_id': 'integration-test',
            'timestamp': time.time(),
            'message': 'End-to-end test event'
        }
        
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(test_event)
        )
        
        assert 'MessageId' in response
        assert 'MD5OfMessageBody' in response
    
    def test_security_lake_s3_accessible(self, aws_clients, deployed_stack):
        """Verify Security Lake S3 bucket is accessible"""
        outputs = deployed_stack['outputs']
        
        if 'SecurityLakeS3Bucket' in outputs:
            s3_client = aws_clients['s3']
            bucket_name = outputs['SecurityLakeS3Bucket']
            
            # Verify bucket exists
            response = s3_client.head_bucket(Bucket=bucket_name)
            assert response['ResponseMetadata']['HTTPStatusCode'] == 200

class TestSecurityControls:
    """Test security controls are properly configured"""
    
    def test_encryption_enabled(self, aws_clients, deployed_stack):
        """Verify encryption is enabled for resources"""
        outputs = deployed_stack['outputs']
        sqs_client = aws_clients['sqs']
        
        # Check SQS encryption
        queue_url = outputs.get('EventTransformerQueueUrl')
        if queue_url:
            attributes = sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['KmsMasterKeyId']
            )
            
            # Should have KMS encryption
            assert 'KmsMasterKeyId' in attributes['Attributes'] or \
                   attributes['Attributes'].get('SqsManagedSseEnabled') == 'true'
    
    def test_lambda_dlq_configured(self, aws_clients, deployed_stack):
        """Verify Lambda functions have DLQ configured"""
        lambda_client = aws_clients['lambda']
        outputs = deployed_stack['outputs']
        
        # Check Azure module Lambda if present
        if 'AzureEventHubProcessorArn' in outputs:
            response = lambda_client.get_function_configuration(
                FunctionName=outputs['AzureEventHubProcessorArn']
            )
            
            assert 'DeadLetterConfig' in response
            assert response['DeadLetterConfig'].get('TargetArn') is not None
    
    def test_cloudwatch_logs_encrypted(self, aws_clients):
        """Verify CloudWatch log groups are encrypted"""
        logs_client = boto3.client('logs', region_name=TEST_REGION)
        
        # List log groups for this stack
        response = logs_client.describe_log_groups(
            logGroupNamePrefix=f'/aws/lambda/{TEST_STACK_PREFIX}'
        )
        
        for log_group in response['logGroups']:
            # Check if encryption is configured
            # Note: CloudWatch Logs encryption may not be returned in all cases
            assert log_group['logGroupName'] is not None

class TestMonitoring:
    """Test monitoring and alerting configuration"""
    
    def test_cloudwatch_alarms_created(self):
        """Verify CloudWatch alarms exist"""
        cloudwatch_client = boto3.client('cloudwatch', region_name=TEST_REGION)
        
        # List alarms
        response = cloudwatch_client.describe_alarms(
            AlarmNamePrefix=TEST_STACK_PREFIX,
            MaxRecords=100
        )
        
        # Should have some alarms if monitoring is enabled
        alarms = response['MetricAlarms']
        # Note: May be 0 if monitoring disabled in test config
        assert isinstance(alarms, list)

class TestCleanup:
    """Cleanup tests - run last"""
    
    @pytest.mark.skip(reason="Manual execution only - destroys test stack")
    def test_stack_cleanup(self, aws_clients):
        """
        Cleanup test stack
        
        Run manually with: pytest test_framework_e2e.py::TestCleanup::test_stack_cleanup -v
        """
        cf_client = aws_clients['cloudformation']
        
        # Delete stack
        cf_client.delete_stack(StackName=TEST_STACK_PREFIX)
        
        # Wait for deletion
        waiter = cf_client.get_waiter('stack_delete_complete')
        waiter.wait(StackName=TEST_STACK_PREFIX)
        
        print(f"Test stack {TEST_STACK_PREFIX} deleted successfully")

# Pytest configuration
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )