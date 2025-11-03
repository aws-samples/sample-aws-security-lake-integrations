"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Local testing script for Google SCC Pub/Sub Poller Lambda
"""

import json
import os
from app import lambda_handler


def test_local():
    """Run Lambda locally with mock event"""
    
    # Set required environment variables for local testing
    os.environ['MODULE_ID'] = 'google-scc'
    os.environ['SQS_QUEUE_URL'] = 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue'
    os.environ['GCP_CREDENTIALS_SECRET_NAME'] = 'gcp-pubsub-credentials'
    os.environ['CHECKPOINT_TABLE_NAME'] = 'google-scc-checkpoint-store'
    os.environ['LOGGING_LEVEL'] = 'DEBUG'
    
    # Mock scheduled event
    event = {
        'version': '0',
        'id': 'test-local-invocation',
        'detail-type': 'Scheduled Event',
        'source': 'aws.events',
        'time': '2025-01-22T12:00:00Z',
        'region': 'us-east-1',
        'resources': []
    }
    
    # Mock Lambda context
    class Context:
        function_name = 'google-scc-pubsub-poller-local'
        memory_limit_in_mb = 512
        invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
        aws_request_id = 'test-request-id-local'
        log_group_name = '/aws/lambda/google-scc-pubsub-poller-local'
        log_stream_name = 'test-stream'
        
        def get_remaining_time_in_millis(self):
            return 300000  # 5 minutes
    
    context = Context()
    
    print("=" * 80)
    print("Google SCC Pub/Sub Poller - Local Test")
    print("=" * 80)
    print(f"\nEvent: {json.dumps(event, indent=2)}")
    print(f"\nContext: {context.function_name}")
    print("\nExecuting Lambda handler...\n")
    
    try:
        result = lambda_handler(event, context)
        print("\n" + "=" * 80)
        print("Lambda execution completed successfully")
        print("=" * 80)
        print(f"\nResult: {json.dumps(result, indent=2)}")
    except Exception as e:
        print("\n" + "=" * 80)
        print("Lambda execution failed")
        print("=" * 80)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_local()