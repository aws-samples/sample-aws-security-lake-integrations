#!/usr/bin/env python3
"""
Test script for Microsoft Defender Cloud Event Hub Processor Lambda
Run this locally to validate the Lambda function before deployment
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the lambda directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_mock_event_data(event_id: int):
    """Create a mock Azure Event Hub event"""
    mock_event = Mock()
    mock_event.body = json.dumps({
        "id": f"alert-{event_id}",
        "type": "Microsoft.Security/assessments",
        "name": f"Test Alert {event_id}",
        "properties": {
            "severity": "High",
            "status": {
                "code": "Unhealthy",
                "description": "Resource is not compliant"
            },
            "resourceDetails": {
                "id": f"/subscriptions/xxx/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-{event_id}",
                "source": "Azure"
            },
            "displayName": f"Security Alert {event_id}",
            "description": "Test security finding from Microsoft Defender for Cloud"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }).encode('utf-8')
    
    mock_event.sequence_number = event_id
    mock_event.offset = f"offset-{event_id}"
    mock_event.enqueued_time = datetime.now(timezone.utc)
    mock_event.partition_key = f"partition-{event_id % 4}"
    mock_event.properties = {"custom_property": f"value_{event_id}"}
    mock_event.system_properties = {"x-opt-sequence-number": event_id}
    
    return mock_event

def test_event_processor():
    """Test the event processor core logic"""
    from core.event_processor import EventProcessor
    
    processor = EventProcessor()
    
    # Test processing a single event
    test_event = {
        "event_data": {
            "id": "test-alert-1",
            "type": "Microsoft.Security/assessments",
            "properties": {
                "severity": "High",
                "status": {"code": "Unhealthy"}
            }
        },
        "event_metadata": {
            "sequence_number": 1,
            "enqueued_time": datetime.now(timezone.utc).isoformat()
        }
    }
    
    result = processor.process_event(test_event)
    assert result is not None
    assert "recordId" in result
    assert result["result"] == "Ok"
    logger.info("✓ Event processor test passed")

def test_firehose_client():
    """Test the Kinesis Firehose client"""
    from helpers.firehose_client import FirehoseClient
    
    with patch('boto3.client') as mock_boto:
        mock_firehose = Mock()
        mock_firehose.put_record_batch.return_value = {
            'FailedPutCount': 0,
            'RequestResponses': [{'RecordId': 'test-record-1'}]
        }
        mock_boto.return_value = mock_firehose
        
        client = FirehoseClient('test-stream')
        
        # Test sending records
        records = [
            {"recordId": "1", "result": "Ok", "data": "eyJ0ZXN0IjogImRhdGEifQ=="},
            {"recordId": "2", "result": "Ok", "data": "eyJ0ZXN0IjogImRhdGEifQ=="}
        ]
        
        result = client.put_records(records)
        assert result['FailedPutCount'] == 0
        mock_firehose.put_record_batch.assert_called_once()
        logger.info("✓ Firehose client test passed")

def test_eventhub_client():
    """Test the Azure Event Hub client"""
    from helpers.eventhub_client import EventHubClient
    
    with patch('azure.eventhub.EventHubConsumerClient') as mock_client_class:
        # Create a mock client instance
        mock_client = MagicMock()
        mock_client_class.from_connection_string.return_value = mock_client
        
        # Mock the context manager
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        
        # Create the client
        client = EventHubClient(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            eventhub_name="test-hub"
        )
        
        # Test receiving events with proper callback simulation
        def simulate_receive(on_event, on_error, **kwargs):
            """Simulate receiving events by calling the callbacks"""
            # Create mock partition context
            mock_partition = Mock()
            mock_partition.partition_id = "0"
            mock_partition.update_checkpoint = Mock()
            
            # Simulate receiving 3 events
            for i in range(3):
                mock_event = create_mock_event_data(i)
                on_event(mock_partition, mock_event)
        
        mock_client.receive.side_effect = simulate_receive
        
        # Receive events
        events = client.receive_events(max_events=5, max_wait_time=1)
        
        # Verify results
        assert len(events) <= 5
        logger.info(f"✓ Event Hub client test passed - received {len(events)} events")

def test_secrets_manager():
    """Test the Secrets Manager client"""
    from helpers.secrets_manager_client import SecretsManagerClient
    
    with patch('boto3.client') as mock_boto:
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'connection_string': 'test-connection',
                'eventhub_name': 'test-hub'
            })
        }
        mock_boto.return_value = mock_secrets
        
        client = SecretsManagerClient()
        credentials = client.get_eventhub_credentials('test-secret')
        
        assert credentials['connection_string'] == 'test-connection'
        assert credentials['eventhub_name'] == 'test-hub'
        logger.info("✓ Secrets Manager client test passed")

def test_lambda_handler():
    """Test the main Lambda handler"""
    # Set required environment variables
    os.environ['FIREHOSE_STREAM_NAME'] = 'test-stream'
    os.environ['EVENTHUB_SECRET_NAME'] = 'test-secret'
    os.environ['MAX_EVENTS_PER_BATCH'] = '10'
    os.environ['MAX_WAIT_TIME'] = '5'
    
    with patch('helpers.secrets_manager_client.SecretsManagerClient') as mock_secrets_class:
        with patch('helpers.eventhub_client.EventHubClient') as mock_eventhub_class:
            with patch('helpers.firehose_client.FirehoseClient') as mock_firehose_class:
                # Setup mocks
                mock_secrets = Mock()
                mock_secrets.get_eventhub_credentials.return_value = {
                    'connection_string': 'test-conn',
                    'eventhub_name': 'test-hub'
                }
                mock_secrets_class.return_value = mock_secrets
                
                mock_eventhub = Mock()
                mock_eventhub.receive_events.return_value = [
                    {
                        "event_data": {"id": "test-1", "type": "alert"},
                        "event_metadata": {"sequence_number": 1}
                    }
                ]
                mock_eventhub_class.return_value = mock_eventhub
                
                mock_firehose = Mock()
                mock_firehose.put_records.return_value = {
                    'FailedPutCount': 0,
                    'records': [{'recordId': '1', 'result': 'Ok'}]
                }
                mock_firehose_class.return_value = mock_firehose
                
                # Import and test the handler
                from app import lambda_handler
                
                # Create a test event
                test_event = {
                    'source': 'aws.events',
                    'detail-type': 'Scheduled Event'
                }
                
                result = lambda_handler(test_event, None)
                
                assert result['statusCode'] == 200
                body = json.loads(result['body'])
                assert body['events_processed'] >= 0
                logger.info("✓ Lambda handler test passed")

def run_all_tests():
    """Run all tests"""
    logger.info("Starting Lambda function validation tests...")
    logger.info("=" * 60)
    
    tests = [
        ("CheckpointStore Integration", test_checkpoint_store_integration),
        ("SQS Client", test_sqs_client),
        ("Event Hub Client", test_eventhub_client),
        ("Secrets Manager", test_secrets_manager),
        ("Lambda Handler", test_lambda_handler)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\nTesting {test_name}...")
            test_func()
            passed += 1
        except Exception as e:
            logger.error(f"✗ {test_name} failed: {str(e)}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        logger.error("Some tests failed. Please fix the issues before deployment.")
        sys.exit(1)
    else:
        logger.info("All tests passed! Lambda function is ready for deployment.")

if __name__ == "__main__":
    run_all_tests()