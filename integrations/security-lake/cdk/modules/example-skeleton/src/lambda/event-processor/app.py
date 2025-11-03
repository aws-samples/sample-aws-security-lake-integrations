"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Example Skeleton Event Processor Lambda

This is a template Lambda function for Security Lake integration modules.
Copy and modify for your specific integration.

TODO: Update this header with your integration name and purpose
"""

import json
import logging
import os
from typing import Dict, Any, List
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# TODO: Import your module-specific helpers
# from helpers.my_service_client import MyServiceClient
# from helpers.sqs_client import SQSClient

# Initialize Powertools
logger = Logger(service="example-skeleton-processor")
tracer = Tracer(service="example-skeleton-processor")

# Global clients for reuse across invocations (prevents cold starts)
# TODO: Initialize your service clients here
service_client = None
sqs_client = None


def get_service_client():
    """
    Get or create service client (lazy initialization)
    
    TODO: Implement your service client initialization
    """
    global service_client
    if service_client is None:
        credentials_secret = os.environ['CREDENTIALS_SECRET_NAME']
        # TODO: Initialize your service client
        # service_client = MyServiceClient(credentials_secret)
        logger.info("Service client initialized")
    return service_client


def get_sqs_client():
    """
    Get or create SQS client (lazy initialization)
    
    TODO: Customize for your SQS usage pattern
    """
    global sqs_client
    if sqs_client is None:
        queue_url = os.environ['SQS_QUEUE_URL']
        # TODO: Initialize SQS client
        # sqs_client = SQSClient(queue_url)
        logger.info("SQS client initialized", extra={"queue_url": queue_url})
    return sqs_client


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler for event processing
    
    This function is invoked either:
    1. On a schedule (EventBridge scheduled event)
    2. Directly (for testing or manual invocation)
    3. From another AWS service (SQS, S3, etc.)
    
    Args:
        event: Lambda event payload
        context: Lambda context with runtime information
        
    Returns:
        Response dictionary with processing results
    """
    try:
        # Log invocation details
        logger.info("Lambda invocation started", extra={
            "module_id": os.environ.get('MODULE_ID'),
            "module_version": os.environ.get('MODULE_VERSION'),
            "event_type": event.get('detail-type', 'unknown'),
            "request_id": context.aws_request_id
        })
        
        # TODO: Implement your event processing logic here
        
        # Step 1: Fetch events from your data source
        # events = get_service_client().fetch_events()
        # logger.info(f"Fetched {len(events)} events")
        
        # Step 2: Transform/validate events as needed
        # processed_events = process_events(events)
        
        # Step 3: Send to core transformer queue
        # if processed_events:
        #     get_sqs_client().send_batch(processed_events)
        #     logger.info(f"Sent {len(processed_events)} events to transformer queue")
        
        # Placeholder response
        events_processed = 0  # TODO: Replace with actual count
        
        logger.info("Lambda execution completed successfully", extra={
            "events_processed": events_processed,
            "status": "success"
        })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'events_processed': events_processed,
                'status': 'success',
                'module_id': os.environ.get('MODULE_ID'),
                'timestamp': context.invoked_function_arn
            })
        }
        
    except Exception as e:
        # Log error with full context
        logger.exception("Error processing events", extra={
            "error_type": type(e).__name__,
            "error_message": str(e)
        })
        
        # Re-raise for Lambda to handle retry logic
        raise


def process_events(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process and transform raw events
    
    TODO: Implement your event transformation logic
    
    Args:
        raw_events: List of raw events from data source
        
    Returns:
        List of processed events ready for transformer
    """
    processed = []
    
    for event in raw_events:
        try:
            # TODO: Transform event to standard format
            processed_event = {
                'sourceModule': os.environ.get('MODULE_ID'),
                'originalEvent': event,
                'processedTimestamp': '2025-01-22T00:00:00Z',  # TODO: Use actual timestamp
                # Add your transformed fields here
            }
            processed.append(processed_event)
            
        except Exception as e:
            logger.warning("Failed to process individual event", extra={
                "error": str(e),
                "event_id": event.get('id', 'unknown')
            })
            # Continue processing other events
            continue
    
    return processed