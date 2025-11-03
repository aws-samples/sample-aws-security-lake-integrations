"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Local testing script for Flow Log Processor Lambda (STUB VERSION)

This tests the stub version that intentionally fails messages for DLQ testing.

Author: Jeremy Tirrell

Usage:
    python local_test.py
"""

import json
import os
from datetime import datetime

# Set environment variables for local testing
os.environ['AWS_REGION'] = 'ca-central-1'
os.environ['LOGGING_LEVEL'] = 'INFO'

from app import lambda_handler


class MockContext:
    """Mock Lambda context for local testing"""
    aws_request_id = f"local-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    function_name = "flow-log-processor-local"
    invoked_function_arn = "arn:aws:lambda:ca-central-1:123456789012:function:test"
    
    def get_remaining_time_in_millis(self):
        return 300000  # 5 minutes


def create_test_event():
    """Create a test SQS event with Azure Event Grid BlobCreated event"""
    # Real flow log event format from EventHub
    event_grid_event = {
        "event_data": [{
            "id": "005c8947-301e-0024-10e2-41777d065b2e",
            "source": "/subscriptions/39b6331a-1dd5-4c5d-b798-817c39b3d58b/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/testaccount",
            "specversion": "1.0",
            "type": "Microsoft.Storage.BlobCreated",
            "subject": "/blobServices/default/containers/insights-logs-flowlogflowevent/blobs/flowLogResourceID=/TEST_RESOURCE/y=2025/m=10/d=20/h=16/m=00/macAddress=7C1E528C93B6/PT1H.json",
            "time": datetime.now().isoformat(),
            "data": {
                "api": "PutBlockList",
                "requestId": "005c8947-301e-0024-10e2-41777d000000",
                "eTag": "0x8DE0FF995FECCE4",
                "contentType": "application/octet-stream",
                "contentLength": 11093,
                "blobType": "BlockBlob",
                "url": "https://testaccount.blob.core.windows.net/insights-logs-flowlogflowevent/test.json",
                "sequencer": "00000000000000000000000000014413000000000001cd9a"
            }
        }],
        "event_metadata": {
            "sequence_number": 83,
            "offset": "4294975456",
            "enqueued_time": datetime.now().isoformat(),
            "partition_id": "0"
        },
        "processing_metadata": {
            "processed_timestamp": datetime.now().isoformat(),
            "processor_version": "5.0.0",
            "source": "azure-eventhub"
        }
    }
    
    return {
        "Records": [
            {
                "messageId": "test-message-1",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps(event_grid_event),
                "attributes": {
                    "ApproximateReceiveCount": "1",
                    "SentTimestamp": str(int(datetime.now().timestamp() * 1000)),
                    "SenderId": "test-sender",
                    "ApproximateFirstReceiveTimestamp": str(int(datetime.now().timestamp() * 1000))
                },
                "messageAttributes": {},
                "md5OfBody": "test-md5",
                "eventSource": "aws:sqs",
                "eventSourceARN": "arn:aws:sqs:ca-central-1:123456789012:test-queue",
                "awsRegion": "ca-central-1"
            }
        ]
    }


def main():
    """Run local test"""
    print("=" * 80)
    print("Flow Log Processor Lambda - Local Test (STUB VERSION)")
    print("=" * 80)
    print()
    
    print("NOTE: This is a STUB version that intentionally fails all messages")
    print("Purpose: Test DLQ routing and event structure validation")
    print()
    print("Expected behavior:")
    print("  1. Log event details to INFO level")
    print("  2. Return all messages as batch failures")
    print("  3. Messages retry 3 times then go to DLQ")
    print()
    print("-" * 80)
    
    # Create test event
    test_event = create_test_event()
    
    print("Test Event Preview:")
    print(json.dumps(test_event, indent=2, default=str)[:500] + "...")
    print()
    print("-" * 80)
    
    # Run lambda handler
    try:
        result = lambda_handler(test_event, MockContext())
        print()
        print("Result:")
        print(json.dumps(result, indent=2))
        print()
        print("Expected: All messages in batchItemFailures array")
    except Exception as e:
        print()
        print(f"Error: {str(e)}")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()