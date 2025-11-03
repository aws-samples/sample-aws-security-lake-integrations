"""
Google Security Command Center - AWS Lambda Pub/Sub Poller

This Lambda function connects to GCP Pub/Sub to consume Security Command Center
events and forwards them to AWS SQS for CloudTrail transformation processing.

Author: Shishir Jaiswal
Version: 1.0.0 (Initial GCP SCC Integration)
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Import helper classes for GCP Pub/Sub and AWS services
from helpers.secrets_manager_client import SecretsManagerClient
from helpers.pubsub_client import PubSubClient
from helpers.sqs_client import SQSClient

# Configure logging with line numbers for better debugging
logging.basicConfig(
    level=os.getenv('LOGGING_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s'
)
logger = logging.getLogger()
logger.setLevel(os.getenv('LOGGING_LEVEL', 'INFO'))

# Global clients for connection reuse
sqs_client: Optional[SQSClient] = None


def get_sqs_client() -> SQSClient:
    """Get or create SQS client with connection reuse"""
    global sqs_client
    
    if sqs_client is None:
        sqs_client = SQSClient(
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            logger=logger
        )
    
    return sqs_client


def create_event_processor_context(gcp_credentials: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a context for event processing
    
    Args:
        gcp_credentials: GCP Pub/Sub credentials
        stats: Statistics dictionary to track processing
        
    Returns:
        Processing context dictionary
    """
    return {
        'project_id': gcp_credentials.get('projectId'),
        'subscription_id': gcp_credentials.get('subscriptionId'),
        'topic_id': gcp_credentials.get('topicId'),
        'processor_id': str(uuid.uuid4()),  # Unique processor instance ID
        'stats': stats
    }


def is_vpc_flow_log(message_data: Dict[str, Any]) -> bool:
    """
    Detect if a Pub/Sub message contains VPC Flow Log data
    
    Args:
        message_data: The received message data
        
    Returns:
        True if message is a VPC Flow Log, False otherwise
    """
    try:
        # Check for VPC Flow Log structure
        if 'jsonPayload' in message_data and 'resource' in message_data:
            resource_type = message_data.get('resource', {}).get('type', '')
            # VPC Flow Logs have resource.type = 'gce_subnetwork'
            if resource_type == 'gce_subnetwork':
                # Additional validation: check for connection info
                json_payload = message_data.get('jsonPayload', {})
                if 'connection' in json_payload:
                    logger.debug(f"Detected VPC Flow Log with resource type: {resource_type}")
                    return True
        return False
    except Exception as e:
        logger.warning(f"Error detecting VPC Flow Log: {str(e)}")
        return False


def on_message_received(context: Dict[str, Any], message_data: Dict[str, Any],
                        sqs_client: SQSClient, sqs_queue_url: str):
    """
    Message handler for GCP Pub/Sub messages
    
    This function processes each message and forwards to SQS.
    Detects VPC Flow Logs and routes them appropriately.
    No cursor needed - Pub/Sub subscription handles message tracking automatically.
    
    Args:
        context: Processing context with Pub/Sub metadata
        message_data: The received message data
        sqs_client: SQS client for sending messages
        sqs_queue_url: SQS queue URL
    """
    try:
        message_id = message_data.get('message_metadata', {}).get('message_id', 'unknown')
        
        # Check if this is a VPC Flow Log
        if is_vpc_flow_log(message_data.get("event_data",{})):
            logger.info(f"Processing VPC Flow Log message {message_id}")
            context['stats']['vpc_flow_logs_detected'] = context['stats'].get('vpc_flow_logs_detected', 0) + 1
            
            # Enrich with metadata for VPC Flow Logs
            enriched_record = {
                'source': 'gcp-pubsub-vpc-flow-logs',
                'ingestion_time': datetime.now(timezone.utc).isoformat(),
                'pubsub_message_id': message_id,
                'resource_type': message_data.get('resource', {}).get('type', ''),
                'data': message_data
            }
            
            # Remove message_metadata from the data sent to SQS (internal tracking only)
            if 'message_metadata' in enriched_record['data']:
                del enriched_record['data']['message_metadata']
        else:
            logger.debug(f"Processing Security Finding message {message_id}")
            context['stats']['security_findings_detected'] = context['stats'].get('security_findings_detected', 0) + 1
            
            # Use original structure for Security Findings
            enriched_record = message_data
        
        # Create SQS batch entry
        sqs_entries = sqs_client.create_batch_entries([enriched_record], f"gcp_message_{message_id[:8]}")
        
        # Send to SQS
        sqs_response = sqs_client.send_message_batch(sqs_queue_url, sqs_entries)
        
        if sqs_response.get('Successful'):
            context['stats']['events_sent_to_sqs'] += 1
            context['stats']['events_processed'] += 1
            logger.debug(f"Successfully forwarded message {message_id} to SQS")
        else:
            context['stats']['errors'] += 1
            logger.warning(f"Failed to send message {message_id} to SQS: {sqs_response.get('Failed', [])}")
            
    except Exception as e:
        context['stats']['errors'] += 1
        logger.error(f"Error processing message {message_id}: {str(e)}")


def process_pubsub_messages(gcp_credentials: Dict[str, Any], context_lambda, max_processing_time: int, max_messages: int) -> Dict[str, Any]:
    """
    Process Pub/Sub messages with cursor-based acknowledgment
    
    Args:
        gcp_credentials: GCP Pub/Sub credentials
        context_lambda: Lambda context
        max_processing_time: Maximum processing time in seconds
        
    Returns:
        Processing results
    """
    stats = {
        'messages_received': 0,
        'events_processed': 0,
        'events_sent_to_sqs': 0,
        'messages_acknowledged': 0,
        'errors': 0,
        'processing_method': 'pubsub_pull_native_tracking'
    }
    
    # Initialize processing context
    processing_context = create_event_processor_context(gcp_credentials, stats)
    
    # Get clients
    sqs = get_sqs_client()
    sqs_queue_url = os.environ.get('SQS_QUEUE_URL', '')
    
    # Initialize Pub/Sub client
    pubsub_client = None
    try:
        pubsub_client = PubSubClient(
            project_id=gcp_credentials['projectId'],
            subscription_id=gcp_credentials['subscriptionId'],
            credentials_json=gcp_credentials.get('serviceAccountKey'),
            logger=logger
        )
        
        # No cursor needed - Pub/Sub subscription maintains message state automatically
        logger.info(f"Pulling messages from Pub/Sub subscription: {gcp_credentials['subscriptionId']}")
        logger.info(f"Pub/Sub subscription handles message tracking automatically (no client-side cursor needed)")
        
        messages_result = pubsub_client.pull_messages(
            max_messages=max_messages,
            return_immediately=False,
            timeout=min(max_processing_time, 30)
        )
        
        messages = messages_result.get("messages", [])
        stats['messages_received'] = len(messages)
        
        logger.info(f"Received {len(messages)} messages from Pub/Sub")
        
        # Collect ack_ids for batch acknowledgment
        ack_ids_to_acknowledge = []
        
        # Process each message
        for message in messages:
            try:
                # Process message and send to SQS
                on_message_received(processing_context, message, sqs, sqs_queue_url)
                
                # Collect ack_id for batch acknowledgment after successful processing
                ack_id = message.get('message_metadata', {}).get('ack_id')
                if ack_id:
                    ack_ids_to_acknowledge.append(ack_id)
                
            except Exception as e:
                stats['errors'] += 1
                message_id = message.get('message_metadata', {}).get('message_id', 'unknown')
                logger.error(f"Error processing message {message_id}: {str(e)}")
                # Don't acknowledge failed messages - Pub/Sub will redeliver them
        
        # Acknowledge all successfully processed messages in one batch
        if ack_ids_to_acknowledge:
            try:
                pubsub_client.acknowledge_messages(ack_ids_to_acknowledge)
                stats['messages_acknowledged'] = len(ack_ids_to_acknowledge)
                logger.info(f"Acknowledged {len(ack_ids_to_acknowledge)} messages in Pub/Sub")
            except Exception as ack_error:
                logger.error(f"Failed to acknowledge messages: {str(ack_error)}")
                logger.warning("Messages will be redelivered by Pub/Sub")
        
        logger.info(f"Pub/Sub processing completed: {stats['events_processed']} events processed, {stats['messages_acknowledged']} messages acknowledged")
        
        return stats
        
    except Exception as e:
        stats['errors'] += 1
        logger.error(f"Error in Pub/Sub processing: {str(e)}")
        return stats
        
    finally:
        if pubsub_client:
            try:
                pubsub_client.close()
            except Exception as e:
                logger.warning(f"Error closing Pub/Sub client: {str(e)}")


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    AWS Lambda entry point for GCP Security Command Center Pub/Sub polling
    
    Args:
        event: CloudWatch Events rule trigger (scheduled execution) or EventBridge scheduled event
        context: Lambda context object
        
    Returns:
        Dictionary containing processing statistics and results
    """
    start_time = datetime.now(timezone.utc)
    processing_start_ms = int(time.time() * 1000)
    
    # Check if this is an EventBridge scheduled event trigger (expected polling trigger)
    # These events should ALWAYS return success, even if no messages are available
    is_scheduled_event = (event.get('source') == 'aws.events' and
                          event.get('detail-type') == 'Scheduled Event')
    
    if is_scheduled_event:
        logger.info("Received EventBridge scheduled trigger - proceeding with Pub/Sub polling", extra={
            'request_id': context.aws_request_id,
            'event_source': event.get('source'),
            'detail_type': event.get('detail-type')
        })
    
    logger.info("GCP Security Command Center Pub/Sub Poller Lambda started", extra={
        'request_id': context.aws_request_id,
        'function_name': context.function_name,
        'remaining_time_ms': context.get_remaining_time_in_millis(),
        'start_time': start_time.isoformat()
    })
    
    # Initialize result statistics
    result = {
        'messages_received': 0,
        'events_processed': 0,
        'events_sent_to_sqs': 0,
        'messages_acknowledged': 0,
        'errors': 0,
        'start_time': start_time.isoformat(),
        'processing_duration_ms': 0,
        'status': 'started',
        'processing_method': 'pubsub_native_tracking'
    }
    
    try:
        # Get environment variables
        region = os.environ.get('AWS_REGION', 'us-east-1')
        sqs_queue_url = os.environ.get('SQS_QUEUE_URL')
        secrets_name = os.environ.get('GCP_CREDENTIALS_SECRET_NAME')
        gcp_project_id = os.environ.get('GCP_PROJECT_ID')
        gcp_subscription_id = os.environ.get('GCP_SUBSCRIPTION_ID')
        max_messages = os.environ.get('MAX_MESSAGES', 100)

        # Validate required environment variables (no DynamoDB needed - Pub/Sub handles tracking)
        if not all([region, sqs_queue_url, secrets_name, gcp_project_id, gcp_subscription_id]):
            raise ValueError(
                f"Missing required environment variables: "
                f"region={region}, sqs_queue={sqs_queue_url}, secrets={secrets_name}, "
                f"project_id={gcp_project_id}, subscription_id={gcp_subscription_id}"
            )
        
        logger.info("Environment configuration validated", extra={
            'region': region,
            'sqs_queue_url': sqs_queue_url,
            'secrets_name': secrets_name,
            'gcp_project_id': gcp_project_id,
            'gcp_subscription_id': gcp_subscription_id
        })
        logger.info("Using GCP Pub/Sub native message tracking (no client-side cursor required)")
        
        # Initialize AWS clients
        secrets_client = SecretsManagerClient(region)
        
        # Retrieve GCP credentials from Secrets Manager
        logger.info("Retrieving GCP Pub/Sub credentials from Secrets Manager")
        gcp_credentials_raw = secrets_client.get_gcp_credentials(secrets_name)
        
        if not gcp_credentials_raw:
            raise ValueError("Failed to retrieve GCP Pub/Sub credentials from Secrets Manager")
        
        # Build complete credentials structure with environment variables
        # The secret contains the service account JSON directly or in wrapper
        gcp_credentials = {
            'projectId': gcp_credentials_raw.get('project_id') or gcp_project_id,
            'subscriptionId': gcp_subscription_id,  # Always from env var
            'serviceAccountKey': gcp_credentials_raw.get('service_account_json', gcp_credentials_raw),
            'topicId': gcp_credentials_raw.get('topic_id', '')
        }
        
        # DIAGNOSTIC: Log credential validation (without exposing sensitive data)
        logger.info(f"DEBUG: Project ID: {gcp_credentials.get('projectId')}")
        logger.info(f"DEBUG: Subscription ID: {gcp_credentials.get('subscriptionId')}")
        logger.info(f"DEBUG: Service account key type: {type(gcp_credentials.get('serviceAccountKey'))}")
        logger.info(f"DEBUG: Service account has project_id: {'project_id' in gcp_credentials.get('serviceAccountKey', {})}")
        
        # Calculate available processing time (reserve 30 seconds for cleanup)
        remaining_time_ms = context.get_remaining_time_in_millis()
        max_processing_time = max(10, (remaining_time_ms - 30000) // 1000)  # Convert to seconds
        
        logger.info(f"Starting Pub/Sub processing with {max_processing_time}s time limit max messages: {max_messages}")
        
        # Process Pub/Sub messages
        pubsub_stats = process_pubsub_messages(gcp_credentials, context, max_processing_time, max_messages)
        
        # Merge stats into result
        result.update({
            'messages_received': pubsub_stats.get('messages_received', 0),
            'events_processed': pubsub_stats.get('events_processed', 0),
            'events_sent_to_sqs': pubsub_stats.get('events_sent_to_sqs', 0),
            'messages_acknowledged': pubsub_stats.get('messages_acknowledged', 0),
            'errors': pubsub_stats.get('errors', 0),
            'processing_method': 'pubsub_native_tracking'
        })
        
        # Calculate processing duration
        end_time = datetime.now(timezone.utc)
        result['processing_duration_ms'] = int((end_time - start_time).total_seconds() * 1000)
        result['end_time'] = end_time.isoformat()
        result['status'] = 'completed_successfully'
        
        logger.info("Pub/Sub processing completed successfully", extra={
            'stats': result,
            'request_id': context.aws_request_id
        })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'GCP Security Command Center Pub/Sub processing completed successfully',
                'stats': result,
                'timestamp': end_time.isoformat(),
                'request_id': context.aws_request_id
            })
        }
        
    except Exception as e:
        # Calculate processing duration even on error
        end_time = datetime.now(timezone.utc)
        result['processing_duration_ms'] = int((end_time - start_time).total_seconds() * 1000)
        result['end_time'] = end_time.isoformat()
        result['status'] = 'failed'
        result['errors'] += 1
        
        error_msg = f"Lambda execution failed: {str(e)}"
        logger.error(error_msg, extra={
            'request_id': context.aws_request_id,
            'error_type': type(e).__name__,
            'stats': result
        })
        
        # For scheduled events, return success to prevent them from going to DLQ
        # Scheduled triggers should never retry - they're just periodic polling triggers
        if is_scheduled_event:
            logger.warning(
                "Scheduled event encountered error but returning success to prevent DLQ - "
                "error will be logged but event will not retry",
                extra={'error': error_msg, 'request_id': context.aws_request_id}
            )
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Scheduled event processed (with errors logged)',
                    'note': 'Errors are logged but scheduled events always return success to prevent DLQ accumulation',
                    'error_encountered': error_msg,
                    'stats': result,
                    'request_id': context.aws_request_id,
                    'timestamp': end_time.isoformat()
                })
            }
        
        # For non-scheduled events, return failure for proper error handling
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'stats': result,
                'request_id': context.aws_request_id,
                'timestamp': end_time.isoformat()
            })
        }


def validate_environment() -> bool:
    """
    Validate required environment variables
    
    Returns:
        True if all required variables are present
    """
    required_vars = [
        'AWS_REGION',
        'SQS_QUEUE_URL',
        'GCP_CREDENTIALS_SECRET_NAME',
        'GCP_PROJECT_ID',
        'GCP_SUBSCRIPTION_ID'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    return True


# For local testing
if __name__ == "__main__":
    # Mock context for local testing
    class MockContext:
        aws_request_id = "local-test-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        function_name = "pubsub-poller-local"
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"
        
        def get_remaining_time_in_millis(self):
            return 300000  # 5 minutes
    
    # Set environment variables for local testing
    os.environ.setdefault('AWS_REGION', 'us-east-1')
    os.environ.setdefault('SQS_QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/test-queue')
    os.environ.setdefault('GCP_CREDENTIALS_SECRET_NAME', 'test-gcp-credentials')
    os.environ.setdefault('GCP_PROJECT_ID', 'test-project')
    os.environ.setdefault('GCP_SUBSCRIPTION_ID', 'test-subscription')
    os.environ.setdefault('LOGGING_LEVEL', 'DEBUG')
    
    # Validate environment before running
    if validate_environment():
        # Run local test
        result = lambda_handler({}, MockContext())
        print(json.dumps(result, indent=2))
    else:
        print("Environment validation failed - check required variables")