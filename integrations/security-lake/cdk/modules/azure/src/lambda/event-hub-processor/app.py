"""
Microsoft Defender for Cloud - AWS Lambda Event Hub Processor

This Lambda function connects to Azure Event Hub to consume Microsoft Defender
events and forwards them to AWS SQS for CloudTrail transformation processing.

Author: SecureSight Team
Version: 4.0.0 (CheckpointStore Integration)
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Import helper classes for Azure Event Hub and AWS services
from helpers.secrets_manager_client import SecretsManagerClient
from helpers.eventhub_client import EventHubClient
from helpers.dynamodb_cursor_client import DynamoDBCursorClient
from helpers.dynamodb_checkpoint_store import DynamoDBCheckpointStore
from helpers.sqs_client import SQSClient

# Configure logging
logging.basicConfig(
    level=os.getenv('LOGGING_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()
logger.setLevel(os.getenv('LOGGING_LEVEL', 'INFO'))

# Suppress verbose Azure SDK logging
logging.getLogger('azure.eventhub').setLevel(logging.WARNING)
logging.getLogger('azure.eventhub._pyamqp').setLevel(logging.WARNING)
logging.getLogger('azure.eventhub._eventprocessor').setLevel(logging.WARNING)

# Global clients for connection reuse
cursor_client: Optional[DynamoDBCursorClient] = None
checkpoint_store_client: Optional[DynamoDBCheckpointStore] = None
sqs_client: Optional[SQSClient] = None


def get_cursor_client() -> DynamoDBCursorClient:
    """Get or create DynamoDB cursor client with connection reuse"""
    global cursor_client
    
    if cursor_client is None:
        table_name = os.getenv('DYNAMODB_TABLE_NAME')
        if not table_name:
            raise ValueError("DYNAMODB_TABLE_NAME environment variable is required")
        
        cursor_client = DynamoDBCursorClient(
            table_name=table_name,
            region_name=os.getenv('AWS_REGION', 'ca-central-1'),
            logger=logger
        )
    
    return cursor_client


def get_checkpoint_store() -> DynamoDBCheckpointStore:
    """Get or create DynamoDB checkpoint store with connection reuse"""
    global checkpoint_store_client
    
    if checkpoint_store_client is None:
        table_name = os.getenv('DYNAMODB_TABLE_NAME')
        if not table_name:
            raise ValueError("DYNAMODB_TABLE_NAME environment variable is required")
        
        checkpoint_store_client = DynamoDBCheckpointStore(
            table_name=table_name,
            region_name=os.getenv('AWS_REGION', 'ca-central-1'),
            logger=logger
        )
    
    return checkpoint_store_client


def get_sqs_client() -> SQSClient:
    """Get or create SQS client with connection reuse"""
    global sqs_client
    
    if sqs_client is None:
        sqs_client = SQSClient(
            region_name=os.getenv('AWS_REGION', 'ca-central-1'),
            logger=logger
        )
    
    return sqs_client


def create_event_processor_context(azure_credentials: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
    """Create event processing context with consistent namespace parsing"""
    connection_string = azure_credentials.get('connectionString', '')
    namespace = None
    
    try:
        parts = dict(part.split('=', 1) for part in connection_string.split(';') if '=' in part)
        endpoint = parts.get('Endpoint', '').replace('sb://', '').replace('/', '')
        if endpoint:
            namespace = endpoint
    except Exception as e:
        logger.warning(f"Namespace parse failed: {e}")
    
    if not namespace:
        namespace = azure_credentials.get('eventHubNamespace', '')
        if namespace and not namespace.endswith('.servicebus.windows.net'):
            namespace = f"{namespace}.servicebus.windows.net"
    
    if not namespace:
        namespace = f"{azure_credentials['eventHubName']}.servicebus.windows.net"
    
    return {
        'fully_qualified_namespace': namespace,
        'eventhub_name': azure_credentials['eventHubName'],
        'consumer_group': azure_credentials.get('consumerGroup', '$Default'),
        'owner_id': str(uuid.uuid4()),
        'stats': stats
    }


def on_event_received(context: Dict[str, Any], event_data: Dict[str, Any], sqs_client: SQSClient, sqs_queue_url: str, checkpoint_store: DynamoDBCheckpointStore):
    """Send event to SQS (checkpoints updated in eventhub_client.py)"""
    try:
        partition_id = event_data.get('event_metadata', {}).get('partition_id', '0')
        
        # Create SQS batch entry
        sqs_entries = sqs_client.create_batch_entries([event_data], f"azure_partition_{partition_id}")
        
        # Send to SQS
        sqs_response = sqs_client.send_message_batch(sqs_queue_url, sqs_entries)
        
        if sqs_response.get('Successful'):
            context['stats']['events_sent_to_sqs'] += 1
            context['stats']['events_processed'] += 1
        else:
            context['stats']['errors'] += 1
            logger.warning(f"Failed to send event to SQS from partition {partition_id}: {sqs_response.get('Failed', [])}")
            
    except Exception as e:
        context['stats']['errors'] += 1
        logger.error(f"Error processing event from partition {partition_id}: {str(e)}")


def process_with_checkpoint_store(azure_credentials: Dict[str, Any], context_lambda, max_processing_time: int) -> Dict[str, Any]:
    """Process Event Hub events with checkpoint store"""
    stats = {
        'events_received': 0,
        'events_processed': 0,
        'events_sent_to_sqs': 0,
        'checkpoints_updated': 0,
        'partitions_processed': set(),
        'errors': 0,
        'processing_method': 'checkpoint_store'
    }
    
    # Initialize processing context
    processing_context = create_event_processor_context(azure_credentials, stats)
    
    # Get clients
    checkpoint_store = get_checkpoint_store()
    sqs = get_sqs_client()
    sqs_queue_url = os.environ.get('SQS_QUEUE_URL', '')
    
    # Initialize Event Hub client
    eventhub_client = None
    try:
        eventhub_client = EventHubClient(
            connection_string=azure_credentials['connectionString'],
            eventhub_name=azure_credentials['eventHubName'],
            consumer_group=azure_credentials.get('consumerGroup', '$Default'),
            checkpoint_store=checkpoint_store
        )
        
        # Receive events from Event Hub
        events_result = eventhub_client.receive_events(
            max_events=100,
            max_wait_time=min(max_processing_time, 30),
            starting_sequence_number=None
        )
        
        events = events_result.get("events", [])
        stats['events_received'] = len(events)
        
        logger.info(f"Received {len(events)} events from Event Hub")
        
        # Send events to SQS
        for event in events:
            try:
                partition_id = event.get('event_metadata', {}).get('partition_id', '0')
                stats['partitions_processed'].add(partition_id)
                
                # Process event with checkpoint store
                on_event_received(processing_context, event, sqs, sqs_queue_url, checkpoint_store)
                
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error processing individual event: {str(e)}")
        
        # Convert partitions_processed set to count for serialization
        stats['partitions_processed'] = len(stats['partitions_processed'])
        
        logger.info(f"Checkpoint store processing completed: {stats['events_processed']} events processed from {stats['partitions_processed']} partitions")
        
        return stats
        
    except Exception as e:
        stats['errors'] += 1
        logger.error(f"Error in checkpoint store processing: {str(e)}")
        return stats
        
    finally:
        if eventhub_client:
            try:
                eventhub_client.close()
            except Exception as e:
                logger.warning(f"Error closing Event Hub client: {str(e)}")


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    AWS Lambda entry point for Microsoft Defender Event Hub processing
    
    Args:
        event: CloudWatch Events rule trigger (scheduled execution)
        context: Lambda context object
        
    Returns:
        Dictionary containing processing statistics and results
    """
    start_time = datetime.now(timezone.utc)
    processing_start_ms = int(time.time() * 1000)
    
    logger.info("Microsoft Defender Event Hub Processor Lambda started", extra={
        'request_id': context.aws_request_id,
        'function_name': context.function_name,
        'remaining_time_ms': context.get_remaining_time_in_millis(),
        'start_time': start_time.isoformat()
    })
    
    # Initialize result statistics
    result = {
        'events_received': 0,
        'events_processed': 0,
        'events_sent_to_sqs': 0,
        'cursor_updated': False,
        'checkpoints_updated': 0,
        'errors': 0,
        'start_time': start_time.isoformat(),
        'processing_duration_ms': 0,
        'status': 'started',
        'processing_method': 'hybrid'  # Can use both cursor and checkpoint approaches
    }
    
    try:
        # Get environment variables
        region = os.environ.get('AWS_REGION', 'ca-central-1')
        sqs_queue_url = os.environ.get('SQS_QUEUE_URL')
        secrets_name = os.environ.get('AZURE_CREDENTIALS_SECRET_NAME')
        dynamodb_table = os.environ.get('DYNAMODB_TABLE_NAME')
        use_checkpoint_store = os.environ.get('USE_CHECKPOINT_STORE', 'true').lower() == 'true'
        
        # Validate required environment variables
        if not all([region, sqs_queue_url, secrets_name, dynamodb_table]):
            raise ValueError(f"Missing required environment variables: region={region}, sqs_queue={sqs_queue_url}, secrets={secrets_name}, dynamodb={dynamodb_table}")
        
        logger.info("Environment configuration validated", extra={
            'region': region,
            'sqs_queue_url': sqs_queue_url,
            'secrets_name': secrets_name,
            'dynamodb_table': dynamodb_table,
            'use_checkpoint_store': use_checkpoint_store
        })
        
        # Initialize AWS clients
        secrets_client = SecretsManagerClient(region)
        
        # Retrieve Azure credentials from Secrets Manager
        logger.info("Retrieving Azure Event Hub credentials from Secrets Manager")
        azure_credentials = secrets_client.get_azure_credentials(secrets_name)
        
        if not azure_credentials:
            raise ValueError("Failed to retrieve Azure Event Hub credentials from Secrets Manager")
        
        # Validate credentials
        if azure_credentials.get('connectionString', '').startswith('PLACEHOLDER'):
            raise ValueError("Azure credentials contain PLACEHOLDER values - run configure-secrets-manager.sh")
        
        # Calculate available processing time (reserve 30 seconds for cleanup)
        remaining_time_ms = context.get_remaining_time_in_millis()
        max_processing_time = max(10, (remaining_time_ms - 30000) // 1000)  # Convert to seconds
        
        logger.info(f"Starting Event Hub processing with {max_processing_time}s time limit")
        
        # Choose processing method based on configuration
        if use_checkpoint_store:
            logger.info("Using checkpoint store processing method")
            checkpoint_stats = process_with_checkpoint_store(azure_credentials, context, max_processing_time)
            
            # Merge checkpoint stats into result
            result.update({
                'events_received': checkpoint_stats.get('events_received', 0),
                'events_processed': checkpoint_stats.get('events_processed', 0),
                'events_sent_to_sqs': checkpoint_stats.get('events_sent_to_sqs', 0),
                'checkpoints_updated': checkpoint_stats.get('checkpoints_updated', 0),
                'partitions_processed': checkpoint_stats.get('partitions_processed', 0),
                'errors': checkpoint_stats.get('errors', 0),
                'processing_method': 'checkpoint_store'
            })
        else:
            logger.info("Using legacy cursor processing method")
            # Fall back to original cursor-based processing
            result.update(process_with_cursor_fallback(azure_credentials, context, max_processing_time))
        
        # Calculate processing duration
        end_time = datetime.now(timezone.utc)
        result['processing_duration_ms'] = int((end_time - start_time).total_seconds() * 1000)
        result['end_time'] = end_time.isoformat()
        result['status'] = 'completed_successfully'
        
        logger.info("Event Hub processing completed successfully", extra={
            'stats': result,
            'request_id': context.aws_request_id,
            'processing_method': result.get('processing_method')
        })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Microsoft Defender Event Hub processing completed successfully',
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
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'stats': result,
                'request_id': context.aws_request_id,
                'timestamp': end_time.isoformat()
            })
        }


def process_with_cursor_fallback(azure_credentials: Dict[str, Any], context_lambda, max_processing_time: int) -> Dict[str, Any]:
    """
    Fallback to original cursor-based processing method for backward compatibility
    
    Args:
        azure_credentials: Azure Event Hub credentials
        context_lambda: Lambda context
        max_processing_time: Maximum processing time in seconds
        
    Returns:
        Processing results
    """
    stats = {
        'events_received': 0,
        'events_processed': 0,
        'events_sent_to_sqs': 0,
        'cursor_updated': False,
        'errors': 0,
        'processing_method': 'cursor_fallback'
    }
    
    eventhub_client = None
    
    try:
        # Get clients
        cursor_db = get_cursor_client()
        sqs = get_sqs_client()
        sqs_queue_url = os.environ.get('SQS_QUEUE_URL', '')
        
        # Create base cursor ID for this Event Hub
        base_cursor_id = f"eventhub:{azure_credentials['eventHubName']}:{azure_credentials.get('consumerGroup', '$Default')}"
        
        # Get partition cursors from DynamoDB
        partition_cursors = {}
        for partition_id in range(4):  # Check partitions 0-3
            partition_cursor_id = f"{base_cursor_id}:partition:{partition_id}"
            partition_cursor = cursor_db.get_cursor_value(partition_cursor_id)
            if partition_cursor:
                partition_cursors[str(partition_id)] = partition_cursor
                
        logger.info(f"Found cursors for {len(partition_cursors)} partitions")
        
        # Initialize Azure Event Hub client for cursor mode
        eventhub_client = EventHubClient(
            connection_string=azure_credentials['connectionString'],
            eventhub_name=azure_credentials['eventHubName'],
            consumer_group=azure_credentials.get('consumerGroup', '$Default'),
            checkpoint_store=None
        )
        
        # Process events from primary partition
        primary_cursor = partition_cursors.get("0")
        events_result = eventhub_client.receive_events(
            max_events=100,
            max_wait_time=min(max_processing_time, 60),
            starting_sequence_number=primary_cursor
        )
        
        events = events_result.get("events", [])
        stats['events_received'] = len(events)
        
        if events:
            # Process events in batches
            batch_size = 10
            events_sent = 0
            
            for i in range(0, len(events), batch_size):
                batch = events[i:i + batch_size]
                sqs_entries = sqs.create_batch_entries(batch, f"azure_batch_{i}")
                sqs_response = sqs.send_message_batch(sqs_queue_url, sqs_entries)
                events_sent += len(sqs_response.get('Successful', []))
                
                if sqs_response.get('Failed'):
                    stats['errors'] += len(sqs_response['Failed'])
            
            stats['events_sent_to_sqs'] = events_sent
            stats['events_processed'] = len(events)
            
            # Update cursors if events were processed successfully
            if events_sent > 0:
                processing_end_ms = int(time.time() * 1000)
                processing_time_ms = processing_end_ms - int(time.time() * 1000)
                
                # Find max sequence number
                max_seq_num = None
                for event in events:
                    seq_num = event.get('event_metadata', {}).get('sequence_number')
                    if seq_num is not None:
                        max_seq_num = max(max_seq_num or 0, int(seq_num))
                
                if max_seq_num is not None:
                    partition_cursor_id = f"{base_cursor_id}:partition:0"
                    cursor_db.save_cursor(
                        cursor_id=partition_cursor_id,
                        cursor_value=str(max_seq_num),
                        messages_processed_batch=len(events),
                        last_batch_size=len(events),
                        processing_time_ms=processing_time_ms
                    )
                    stats['cursor_updated'] = True
        
        return stats
        
    except Exception as e:
        stats['errors'] += 1
        logger.error(f"Error in cursor fallback processing: {str(e)}")
        return stats
        
    finally:
        if eventhub_client:
            try:
                eventhub_client.close()
            except Exception as e:
                logger.warning(f"Error closing Event Hub client: {str(e)}")


def validate_environment() -> bool:
    """
    Validate required environment variables
    
    Returns:
        True if all required variables are present
    """
    required_vars = [
        'AWS_REGION',
        'SQS_QUEUE_URL',
        'AZURE_CREDENTIALS_SECRET_NAME',
        'DYNAMODB_TABLE_NAME'
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
        function_name = "event-hub-processor-local"
        invoked_function_arn = "arn:aws:lambda:ca-central-1:123456789012:function:test"
        
        def get_remaining_time_in_millis(self):
            return 300000  # 5 minutes
    
    # Set environment variables for local testing
    os.environ.setdefault('AWS_REGION', 'ca-central-1')
    os.environ.setdefault('SQS_QUEUE_URL', 'https://sqs.ca-central-1.amazonaws.com/123456789012/test-queue')
    os.environ.setdefault('AZURE_CREDENTIALS_SECRET_NAME', 'test-azure-credentials')
    os.environ.setdefault('DYNAMODB_TABLE_NAME', 'test-cursor-table')
    os.environ.setdefault('USE_CHECKPOINT_STORE', 'true')
    os.environ.setdefault('LOGGING_LEVEL', 'DEBUG')
    
    # Validate environment before running
    if validate_environment():
        # Run local test
        result = lambda_handler({}, MockContext())
        print(json.dumps(result, indent=2))
    else:
        print("Environment validation failed - check required variables")