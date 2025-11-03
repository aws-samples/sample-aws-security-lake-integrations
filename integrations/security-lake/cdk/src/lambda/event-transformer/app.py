# © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
Event Transformer Lambda - Convert cloud security events to CloudTrail Lake integration format

This Lambda function:
1. Receives cloud security events from SQS queue (standard trigger)
2. OR processes messages from a specific SQS queue (custom event with queue_url)
3. Transforms them to CloudTrail Lake integration format
4. Sends them to CloudTrail Event Data Store for unified security monitoring

Author: SecureSight Team
Version: 3.1.2 (Enhanced with Custom Queue Processing)
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError
from helpers.event_transformer import CloudTrailTransformer
from helpers.security_lake_client import SecurityLakeClient
from helpers.json_fixer import fix_json

# Environment Variables - Loaded once at module level for better readability and performance
LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'INFO')
EVENT_DATA_STORE_ARN = os.getenv('EVENT_DATA_STORE_ARN','')
CLOUDTRAIL_CHANNEL_ARN = os.getenv('CLOUDTRAIL_CHANNEL_ARN')
CLOUDTRAIL_ENABLED = os.getenv('CLOUDTRAIL_ENABLED', 'true').lower() == 'true'
SECURITY_LAKE_ENABLED = os.getenv('SECURITY_LAKE_ENABLED', 'false').lower() == 'true'
SECURITY_LAKE_S3_BUCKET = os.getenv('SECURITY_LAKE_S3_BUCKET','')
SECURITY_LAKE_SOURCES = os.getenv('SECURITY_LAKE_SOURCES','')
SECURITY_LAKE_PATH = os.getenv('SECURITY_LAKE_PATH', '')
ASFF_ENABLED = os.getenv('ASFF_ENABLED', 'false').lower() == 'true'
ASFF_SQS_QUEUE = os.getenv('ASFF_SQS_QUEUE', '')  # SQS Queue URL for ASFF findings
FLOW_LOG_SQS_QUEUE = os.getenv('FLOW_LOG_SQS_QUEUE', '')  # SQS Queue URL for Flow Log events
EVENT_DLQ = os.getenv('EVENT_DLQ', '')  # Dead Letter Queue URL for failed transformations
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_LAMBDA_FUNCTION_NAME = os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'unknown')
AWS_LAMBDA_FUNCTION_VERSION = os.getenv('AWS_LAMBDA_FUNCTION_VERSION', 'unknown')
AWS_EXECUTION_ENV = os.getenv('AWS_EXECUTION_ENV', 'unknown')
AWS_LAMBDA_FUNCTION_MEMORY_SIZE = os.getenv('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', 'unknown')
AWS_LAMBDA_LOG_GROUP_NAME = os.getenv('AWS_LAMBDA_LOG_GROUP_NAME', 'unknown')
AWS_LAMBDA_LOG_STREAM_NAME = os.getenv('AWS_LAMBDA_LOG_STREAM_NAME', 'unknown')

try:
    logging.basicConfig(
        level=LOGGING_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
        force=True  # Override any existing configuration
    )
    logger = logging.getLogger(__name__)
    
    # Test logging immediately
    logger.info("LOGGER TEST: Logger configured successfully")
    
    # Suppress noisy third-party library debug logs
    noisy_loggers = [
        'pyarrow', 'pyarrow.compute', 'pyarrow.memory', 'pyarrow.lib',
        'pyarrow.parquet', 'pyarrow.io', 'pyarrow.dataset',
        'botocore', 'boto3', 'urllib3', 's3transfer'
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
        logging.getLogger(logger_name).propagate = False  # Prevent propagation to root logger
    
except Exception as e:
    # Fallback logger setup
    import sys
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    logger = logging.getLogger(__name__)

# Global variables for connection reuse and performance optimization
transformer: Optional[CloudTrailTransformer] = None
sqs_client: Optional[boto3.client] = None
security_lake_client: Optional[SecurityLakeClient] = None


def get_transformer() -> CloudTrailTransformer:
    """
    Get or create CloudTrail transformer instance with connection reuse
    
    Returns:
        CloudTrailTransformer: Configured transformer instance
        
    Raises:
        ValueError: If required environment variables are missing
        Exception: If transformer initialization fails
    """
    global transformer
    
    if transformer is None:
        if not EVENT_DATA_STORE_ARN:
            raise ValueError("EVENT_DATA_STORE_ARN environment variable is required")
        
        try:
            transformer = CloudTrailTransformer(
                event_data_store_arn=EVENT_DATA_STORE_ARN,
                channel_arn=CLOUDTRAIL_CHANNEL_ARN,
                logger=logger
            )
            
            # Validate configuration on first initialization
            if not transformer.validate_configuration():
                raise Exception("Transformer configuration validation failed")
                
            logger.info("CloudTrail transformer initialized and validated successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CloudTrail transformer: {str(e)}")
            raise
    
    return transformer


def get_sqs_client() -> boto3.client:
    """
    Get or create SQS client instance with connection reuse
    
    Returns:
        boto3.client: Configured SQS client instance
    """
    global sqs_client
    
    if sqs_client is None:
        try:
            sqs_client = boto3.client('sqs')
            logger.info("SQS client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SQS client: {str(e)}")
            raise
    
    return sqs_client


def get_security_lake_client() -> Optional[SecurityLakeClient]:
    """
    Get or create Security Lake client instance with connection reuse
    
    Returns:
        SecurityLakeClient instance if enabled, None otherwise
    """
    global security_lake_client
    
    # Check if Security Lake is enabled
    if not SECURITY_LAKE_ENABLED:
        return None
    
    if security_lake_client is None:
        if not SECURITY_LAKE_S3_BUCKET or not SECURITY_LAKE_SOURCES:
            logger.warning("Security Lake enabled but missing required environment variables (SECURITY_LAKE_S3_BUCKET or SECURITY_LAKE_SOURCES)")
            return None
        
        try:
            # Parse source configurations
            source_configurations = json.loads(SECURITY_LAKE_SOURCES)
            
            security_lake_client = SecurityLakeClient(
                s3_bucket=SECURITY_LAKE_S3_BUCKET,
                source_configurations=source_configurations,
                s3_path=SECURITY_LAKE_PATH
            )
            
            # Validate configuration
            if not security_lake_client.validate_configuration():
                logger.error("Security Lake client configuration validation failed")
                security_lake_client = None
                return None
                
            logger.info("Security Lake client initialized and validated successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in SECURITY_LAKE_SOURCES environment variable: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Security Lake client: {str(e)}")
            return None
    
    return security_lake_client


def fetch_messages_from_queue(queue_url: str, max_messages: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch messages from a specified SQS queue using batched polling for high throughput
    
    Args:
        queue_url: URL of the SQS queue to poll
        max_messages: Maximum number of messages to retrieve (1-10000)
                     Note: SQS allows max 10 per API call, so we'll poll in batches
        
    Returns:
        List of SQS message records in the same format as SQS trigger events
        
    Raises:
        ClientError: If SQS operations fail
        ValueError: If queue_url is invalid
    """
    if not queue_url:
        raise ValueError("queue_url cannot be empty")
        
    if not (1 <= max_messages <= 10000):
        raise ValueError("max_messages must be between 1 and 10,000")
    
    try:
        sqs = get_sqs_client()
        
        logger.info(f"Polling messages from queue: {queue_url} (max: {max_messages})")
        
        all_records = []
        messages_fetched = 0
        batch_count = 0
        consecutive_empty_polls = 0
        
        while messages_fetched < max_messages:
            batch_count += 1
            # Calculate how many messages to request in this batch (max 10 per SQS API call)
            messages_to_request = min(10, max_messages - messages_fetched)
            
            logger.debug(f"Batch {batch_count}: Requesting {messages_to_request} messages (fetched so far: {messages_fetched}/{max_messages})")
            
            # Receive messages from the queue
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=messages_to_request,
                WaitTimeSeconds=0,  # No wait time - return immediately if no messages
                MessageAttributeNames=['All'],
                AttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            
            if not messages:
                logger.info(f"Queue empty after fetching {messages_fetched} messages (requested {max_messages})")
                break  # Exit immediately when queue is empty
            
            logger.debug(f"Batch {batch_count}: Retrieved {len(messages)} messages")
            
            # Convert SQS messages to the same format as SQS trigger event records
            for message in messages:
                record = {
                    'messageId': message['MessageId'],
                    'receiptHandle': message['ReceiptHandle'],
                    'body': message['Body'],
                    'attributes': message.get('Attributes', {}),
                    'messageAttributes': message.get('MessageAttributes', {}),
                    'md5OfBody': message.get('MD5OfBody', ''),
                    'eventSource': 'aws:sqs',
                    'eventSourceARN': f"arn:aws:sqs:{boto3.Session().region_name}:*:queue-name",
                    'awsRegion': boto3.Session().region_name or AWS_REGION
                }
                all_records.append(record)
                messages_fetched += 1
                
                # Stop if we've reached the max
                if messages_fetched >= max_messages:
                    break
        
        logger.info(f"Completed polling: Retrieved {len(all_records)} messages from queue in {batch_count} batches")
        return all_records
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"Failed to fetch messages from queue {queue_url}: {error_code} - {error_message}")
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error fetching messages from queue {queue_url}: {str(e)}")
        raise


def send_failed_event_to_dlq(original_message: Dict[str, Any], failure_reason: str, error_details: Optional[str] = None,
                            source_queue_url: Optional[str] = None) -> bool:
    """
    Send a failed transformation event to the Dead Letter Queue exactly as received
    
    Args:
        original_message: The original SQS message that failed to transform
        failure_reason: Reason for the transformation failure (logged only)
        error_details: Additional error details (logged only)
        source_queue_url: URL of the queue being processed (to prevent cycles)
        
    Returns:
        True if successfully sent to DLQ, False otherwise
    """
    if not EVENT_DLQ:
        logger.warning("EVENT_DLQ not configured, cannot send failed event to DLQ")
        return False
    
    # Prevent DLQ cycling: Don't send messages back to the same queue they came from
    if source_queue_url and source_queue_url == EVENT_DLQ:
        logger.warning(f"DLQ CYCLE PREVENTION: Not sending message back to same DLQ it came from. Original failure: {failure_reason}")
        return False
    
    try:
        sqs = get_sqs_client()
        
        # Send the original message body exactly as it was received
        # Extract the original body from the SQS record
        original_body = original_message.get('body', '')
        message_id = original_message.get('messageId', 'unknown')
        
        # Send to DLQ with the exact original message body
        response = sqs.send_message(
            QueueUrl=EVENT_DLQ,
            MessageBody=original_body,
            MessageAttributes=original_message.get('messageAttributes', {})
        )
        
        # Log at WARN level as requested
        logger.warning(f"Message {message_id} sent to DLQ: NewMessageId={response.get('MessageId')}, Reason={failure_reason}")
        if error_details:
            logger.debug(f"DLQ failure details for {message_id}: {error_details}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send message to DLQ: {str(e)}")
        return False


def delete_processed_messages(queue_url: str, receipt_handles: List[str]) -> Dict[str, Any]:
    """
    Delete successfully processed messages from the SQS queue using efficient batching
    
    Args:
        queue_url: URL of the SQS queue
        receipt_handles: List of receipt handles for messages to delete
        
    Returns:
        Dictionary with deletion results
    """
    if not receipt_handles:
        logger.info("No messages to delete")
        return {'successful_deletions': 0, 'failed_deletions': 0}
    
    try:
        sqs = get_sqs_client()
        
        logger.info(f"Deleting {len(receipt_handles)} processed messages from queue")
        
        successful_deletions = 0
        failed_deletions = 0
        batch_count = 0
        
        # Delete messages in batches (SQS allows up to 10 per batch)
        for i in range(0, len(receipt_handles), 10):
            batch_count += 1
            batch_handles = receipt_handles[i:i+10]
            
            # Prepare batch delete entries
            delete_entries = []
            for j, receipt_handle in enumerate(batch_handles):
                delete_entries.append({
                    'Id': str(j),
                    'ReceiptHandle': receipt_handle
                })
            
            try:
                logger.debug(f"Deleting batch {batch_count} with {len(delete_entries)} messages")
                
                response = sqs.delete_message_batch(
                    QueueUrl=queue_url,
                    Entries=delete_entries
                )
                
                batch_successful = len(response.get('Successful', []))
                batch_failed = len(response.get('Failed', []))
                
                successful_deletions += batch_successful
                failed_deletions += batch_failed
                
                logger.debug(f"Batch {batch_count}: {batch_successful} successful, {batch_failed} failed")
                
                # Log successful deletions at INFO level per message
                for success in response.get('Successful', []):
                    logger.info(f"Successfully deleted message from queue (batch {batch_count}, id: {success.get('Id', 'unknown')})")
                
                # Log any failures with details
                for failed in response.get('Failed', []):
                    logger.warning(f"Failed to delete message in batch {batch_count}: {failed}")
                    
            except ClientError as e:
                logger.error(f"Failed to delete batch {batch_count}: {str(e)}")
                failed_deletions += len(batch_handles)
            except Exception as e:
                logger.error(f"Unexpected error deleting batch {batch_count}: {str(e)}")
                failed_deletions += len(batch_handles)
        
        logger.info(f"Message deletion completed: {successful_deletions} successful, {failed_deletions} failed across {batch_count} batches")
        
        return {
            'successful_deletions': successful_deletions,
            'failed_deletions': failed_deletions,
            'total_batches': batch_count
        }
        
    except Exception as e:
        logger.error(f"Critical error deleting messages from queue {queue_url}: {str(e)}")
        return {
            'successful_deletions': 0,
            'failed_deletions': len(receipt_handles),
            'error': str(e)
        }


def is_sqs_trigger_event(event: Dict[str, Any]) -> bool:
    """
    Determine if the event is an SQS trigger event or a custom event
    
    Args:
        event: Lambda event data
        
    Returns:
        True if this is an SQS trigger event, False if it's a custom event
    """
    return 'Records' in event and isinstance(event.get('Records'), list)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing SQS messages containing cloud security events
    
    Supports two event types:
    1. SQS trigger events (standard Lambda SQS integration)
    2. Custom events with queue_url parameter for processing specific queues (e.g., DLQ)
    
    Args:
        event: Either SQS trigger event or custom event with queue_url parameter
        context: Lambda context object
        
    Returns:
        Response with processing results including batch item failures for retry
    """
    logger.info(f"LAMBDA START: Handler invoked for request {context.aws_request_id}")
    logger.info(f"Event: {json.dumps(event, indent=4, default=str)}")
    # Determine event type and get SQS records
    if is_sqs_trigger_event(event):
        logger.info(f"Processing SQS trigger event with {len(event.get('Records', []))} messages")
        records = event.get('Records', [])
        event_type = 'sqs_trigger'
        queue_url = None
    else:
        # Custom event with queue_url parameter
        queue_url = event.get('queue_url')
        if not queue_url:
            return {
                'statusCode': 400,
                'error': 'queue_url parameter is required for custom events',
                'event_type': 'custom_queue_processing'
            }
        
        max_messages = event.get('max_messages', 100)
        logger.info(f"Processing custom event for queue: {queue_url} (max messages: {max_messages})")
        
        try:
            records = fetch_messages_from_queue(queue_url, max_messages)
            event_type = 'custom_queue_processing'
            logger.info(f"Fetched {len(records)} messages from queue {queue_url}")
        except Exception as e:
            logger.error(f"Failed to fetch messages from queue {queue_url}: {str(e)}")
            return {
                'statusCode': 500,
                'error': f'Failed to fetch messages from queue: {str(e)}',
                'event_type': 'custom_queue_processing'
            }
    
    try:
        # Initialize Security Lake client (if enabled)
        security_lake_client = get_security_lake_client() if SECURITY_LAKE_ENABLED else None
        
        # Get AWS account ID from Lambda context
        aws_account_id = context.invoked_function_arn.split(':')[4]
        
        # Initialize processing statistics
        processing_stats = {
            'event_type': event_type,
            'queue_url': queue_url,
            'total_messages': len(records),
            'processed_messages': 0,
            'failed_messages': 0,
            'total_cloud_events': 0,
            'successful_transformations': 0,
            'failed_transformations': 0,
            'events_sent_to_datastore': 0,
            'datastore_send_failures': 0,
            'security_lake_enabled': SECURITY_LAKE_ENABLED,
            'cloudtrail_enabled': CLOUDTRAIL_ENABLED,
            'asff_enabled': ASFF_ENABLED,
            'ocsf_events_sent': 0,
            'security_lake_send_failures': 0,
            'asff_findings_sent': 0,
            'asff_send_failures': 0,
            'flow_log_events_routed': 0,
            'flow_log_routing_failures': 0
        }
        
        # Track batch item failures for SQS retry mechanism
        batch_item_failures = []
        # Track successful message receipt handles for deletion (custom queue processing only)
        successful_receipt_handles = []
        
        # Process each SQS record
        for record in records:
            message_id = record['messageId']
            
            # Initialize failure tracking for this message
            message_has_failures = False
            
            # Add message lifecycle logging
            logger.debug(f"Starting processing for message {message_id} from {event_type}")
            logger.info(f"record: {record}")
            try:
                # Check for empty message body first
                message_body_str = record.get('body', '').strip()
                if not message_body_str or message_body_str == '{}':
                    logger.info(f"Empty message body for message {message_id}, marking as successful")
                    processing_stats['processed_messages'] += 1
                    # For custom queue processing, delete empty message immediately
                    if event_type == 'custom_queue_processing' and 'receiptHandle' in record and queue_url:
                        try:
                            sqs = get_sqs_client()
                            sqs.delete_message(
                                QueueUrl=queue_url,
                                ReceiptHandle=record['receiptHandle']
                            )
                            logger.info(f"Successfully deleted empty message {message_id} from queue")
                            processing_stats.setdefault('messages_deleted_immediately', 0)
                            processing_stats['messages_deleted_immediately'] += 1
                        except Exception as delete_error:
                            logger.warning(f"Failed to delete empty message {message_id}: {str(delete_error)}")
                    continue
                
               
                message_body, parse_error = fix_json(message_body_str, logger=logger)
                
                if message_body is None:
                    # JSON parsing failed even after fixes
                    raise parse_error
                
                logger.debug(f"Processing SQS message {message_id}")
                
                # Check if this is a Flow Log blob creation event that should be routed
                if is_flow_log_event(message_body):
                    logger.info(f"Detected Flow Log blob creation event in message {message_id}, routing to flow log queue")
                    
                    if FLOW_LOG_SQS_QUEUE:
                        try:
                            sqs = get_sqs_client()
                            # Forward the entire message to flow log queue for processing
                            response = sqs.send_message(
                                QueueUrl=FLOW_LOG_SQS_QUEUE,
                                MessageBody=message_body_str
                            )
                            processing_stats['flow_log_events_routed'] += 1
                            processing_stats['processed_messages'] += 1
                            logger.info(f"Successfully routed Flow Log event {message_id} to flow log queue: {response.get('MessageId')}")
                            
                            # For custom queue processing, delete message immediately after successful routing
                            if event_type == 'custom_queue_processing' and 'receiptHandle' in record and queue_url:
                                try:
                                    sqs.delete_message(
                                        QueueUrl=queue_url,
                                        ReceiptHandle=record['receiptHandle']
                                    )
                                    logger.info(f"Successfully deleted routed Flow Log message {message_id} from source queue")
                                except Exception as delete_error:
                                    logger.warning(f"Failed to delete routed message {message_id}: {str(delete_error)}")
                            
                            continue  # Skip normal processing for this message
                            
                        except Exception as e:
                            logger.error(f"Failed to route Flow Log event to queue: {str(e)}")
                            processing_stats['flow_log_routing_failures'] += 1
                            batch_item_failures.append({'itemIdentifier': message_id})
                            processing_stats['failed_messages'] += 1
                            continue
                    else:
                        logger.warning(f"Flow Log event detected but FLOW_LOG_SQS_QUEUE not configured")
                
                # Extract cloud events from message body (Azure, GCP, etc.)
                cloud_events = extract_cloud_events_from_message(message_body)
                processing_stats['total_cloud_events'] += len(cloud_events)
                
                if not cloud_events:
                    logger.warning(f"No cloud events found in SQS message: {message_id}")
                    processing_stats['failed_messages'] += 1
                    batch_item_failures.append({'itemIdentifier': message_id})
                    continue
                
                # Initialize processing results for this message
                cloudtrail_result = {'Successful': 0, 'Failed': 0}
                security_lake_result = {'Successful': 0, 'Failed': 0}
                
                # Transform events to CloudTrail format using template system (if enabled)
                cloudtrail_events = []
                cloudtrail_transformation_failures = 0
                if CLOUDTRAIL_ENABLED:
                    from core.event_mapper import CloudEventMapper
                    event_mapper = CloudEventMapper(logger=logger, use_templates=True)
                    
                    for cloud_event in cloud_events:
                        try:
                            # Determine event type for proper template selection
                            event_type = event_mapper._determine_event_type(cloud_event)
                            
                            # Check if CloudTrail template exists for this event type
                            event_type_mapping = event_mapper.template_transformer.event_type_mappings.get(event_type, {})
                            cloudtrail_template_name = event_type_mapping.get('cloudtrail_template')
                            
                            # Skip if CloudTrail template is null (expected for event types like VPC Flow Logs)
                            if cloudtrail_template_name is None:
                                logger.debug(f"CloudTrail template not available for event type {event_type}, skipping CloudTrail transformation (expected)")
                                continue
                            
                            # Generate CloudTrail event using template system
                            if hasattr(event_mapper, 'template_transformer') and event_mapper.template_transformer:
                                cloudtrail_event = event_mapper.template_transformer.transform_event(
                                    azure_event=cloud_event,
                                    aws_account_id=aws_account_id,
                                    event_type=event_type,
                                    output_format='cloudtrail'
                                )
                                if cloudtrail_event:
                                    cloudtrail_events.append(cloudtrail_event)
                                else:
                                    cloudtrail_transformation_failures += 1
                                    logger.error(f"CloudTrail transformation returned None for event type: {event_type}")
                            else:
                                cloudtrail_transformation_failures += 1
                                logger.error(f"Template transformer not available for CloudTrail transformation")
                        except Exception as e:
                            cloudtrail_transformation_failures += 1
                            logger.error(f"CloudTrail transformation failed: {str(e)}")
                    
                    processing_stats['successful_transformations'] += len(cloudtrail_events)
                    processing_stats['failed_transformations'] += cloudtrail_transformation_failures
                    
                    logger.debug(f"Transformed {len(cloudtrail_events)} cloud events to CloudTrail format using templates")
                    
                    # Log transformation failures for debugging and send to DLQ if enabled
                    if cloudtrail_transformation_failures > 0:
                        logger.warning(f"Failed CloudTrail transformations from message {message_id}: {cloudtrail_transformation_failures}")
                        # Send failed events to DLQ for investigation
                        send_failed_event_to_dlq(
                            original_message=record,
                            failure_reason="CloudTrail transformation failed",
                            error_details=f"Failed to transform {cloudtrail_transformation_failures} out of {len(cloud_events)} cloud events to CloudTrail format",
                            source_queue_url=queue_url
                        )
                
                # Transform events to OCSF format for Security Lake using templates (if enabled)
                ocsf_events = []
                asff_findings = []
                transformation_failures = 0
                asff_transformation_failures = 0
                
                if SECURITY_LAKE_ENABLED and security_lake_client:
                    # Use template system instead of hardcoded transformation
                    from core.event_mapper import CloudEventMapper
                    event_mapper = CloudEventMapper(logger=logger, use_templates=True)
                    
                    for cloud_event in cloud_events:
                        try:
                            # Determine event type for proper template selection
                            event_type = event_mapper._determine_event_type(cloud_event)
                            
                            # Generate OCSF event using template system only
                            if hasattr(event_mapper, 'template_transformer') and event_mapper.template_transformer:
                                ocsf_event = event_mapper.template_transformer.transform_event(
                                    azure_event=cloud_event,
                                    aws_account_id=aws_account_id,
                                    event_type=event_type,
                                    output_format='ocsf'
                                )
                                if ocsf_event:
                                    ocsf_events.append(ocsf_event)
                                else:
                                    transformation_failures += 1
                                    logger.error(f"Template transformation returned None for event type: {event_type}")
                            else:
                                transformation_failures += 1
                                logger.error(f"Template transformer not available for event")
                        except Exception as e:
                            transformation_failures += 1
                            logger.error(f"Template transformation failed: {str(e)}")
                    
                    logger.debug(f"Transformed {len(ocsf_events)} events to OCSF format using templates for Security Lake")
                    
                    # Mark message as failed if any transformations failed and send to DLQ
                    if transformation_failures > 0:
                        logger.error(f"OCSF transformation failures for message {message_id}: {transformation_failures} out of {len(cloud_events)} events failed")
                        # Send failed events to DLQ for investigation
                        send_failed_event_to_dlq(
                            original_message=record,
                            failure_reason="OCSF transformation failed",
                            error_details=f"Failed to transform {transformation_failures} out of {len(cloud_events)} cloud events to OCSF format for Security Lake",
                            source_queue_url=queue_url
                        )
                        message_has_failures = True
                
                # Transform events to ASFF format (if enabled)
                if ASFF_ENABLED and ASFF_SQS_QUEUE:
                    from core.event_mapper import CloudEventMapper
                    event_mapper = CloudEventMapper(logger=logger, use_templates=True)
                    
                    for cloud_event in cloud_events:
                        try:
                            # Determine event type for proper template selection
                            event_type = event_mapper._determine_event_type(cloud_event)
                            
                            # Check if ASFF template exists for this event type
                            event_type_mapping = event_mapper.template_transformer.event_type_mappings.get(event_type, {})
                            asff_template_name = event_type_mapping.get('asff_template')
                            
                            # Skip if ASFF template is null or not defined (expected for event types like VPC Flow Logs)
                            if asff_template_name is None:
                                logger.debug(f"ASFF template not available for event type {event_type}, skipping ASFF transformation (expected)")
                                continue
                            
                            # Generate ASFF finding using template system
                            if hasattr(event_mapper, 'template_transformer') and event_mapper.template_transformer:
                                asff_finding = event_mapper.template_transformer.transform_event(
                                    azure_event=cloud_event,
                                    aws_account_id=aws_account_id,
                                    event_type=event_type,
                                    output_format='asff'
                                )
                                if asff_finding:
                                    asff_findings.append(asff_finding)
                                else:
                                    asff_transformation_failures += 1
                                    logger.error(f"ASFF transformation returned None for event type: {event_type}")
                            else:
                                asff_transformation_failures += 1
                                logger.error(f"Template transformer not available for ASFF transformation")
                        except Exception as e:
                            asff_transformation_failures += 1
                            logger.error(f"ASFF transformation failed: {str(e)}")
                    
                    logger.debug(f"Transformed {len(asff_findings)} cloud events to ASFF format")
                    
                    # Mark message as failed if any ASFF transformations failed
                    if asff_transformation_failures > 0:
                        logger.error(f"ASFF transformation failures for message {message_id}: {asff_transformation_failures} out of {len(cloud_events)} events failed")
                        send_failed_event_to_dlq(
                            original_message=record,
                            failure_reason="ASFF transformation failed",
                            error_details=f"Failed to transform {asff_transformation_failures} out of {len(cloud_events)} cloud events to ASFF format",
                            source_queue_url=queue_url
                        )
                        message_has_failures = True
                
                # Send events to destinations
                # Note: Don't reset message_has_failures here - preserve transformation failure state
                
                # Send to CloudTrail (if enabled and events available)
                if CLOUDTRAIL_ENABLED and cloudtrail_events:
                    # Use legacy transformer for sending (only for the send operation, not transformation)
                    event_transformer = get_transformer()
                    cloudtrail_result = event_transformer.send_events_to_datastore(cloudtrail_events)
                    processing_stats['events_sent_to_datastore'] += cloudtrail_result.get('Successful', 0)
                    processing_stats['datastore_send_failures'] += cloudtrail_result.get('Failed', 0)
                    
                    if cloudtrail_result.get('Failed', 0) > 0:
                        logger.warning(f"CloudTrail failures for message {message_id}: {cloudtrail_result.get('Failed', 0)}")
                        message_has_failures = True
                
                # Send to Security Lake (if enabled and events available)
                if SECURITY_LAKE_ENABLED and ocsf_events and security_lake_client:
                    security_lake_result = security_lake_client.send_events_to_security_lake(ocsf_events)
                    processing_stats['ocsf_events_sent'] += security_lake_result.get('Successful', 0)
                    processing_stats['security_lake_send_failures'] += security_lake_result.get('Failed', 0)
                    
                    if security_lake_result.get('Failed', 0) > 0:
                        logger.warning(f"Security Lake failures for message {message_id}: {security_lake_result.get('Failed', 0)}")
                
                # Send ASFF findings to SQS queue (if enabled and findings available)
                if ASFF_ENABLED and asff_findings and ASFF_SQS_QUEUE:
                    try:
                        sqs = get_sqs_client()
                        asff_sent = 0
                        asff_failed = 0
                        
                        # Send findings in batches (10 per SQS batch)
                        for i in range(0, len(asff_findings), 10):
                            batch = asff_findings[i:i+10]
                            entries = []
                            
                            for idx, finding in enumerate(batch):
                                entries.append({
                                    'Id': f"asff_{i+idx}",
                                    'MessageBody': json.dumps(finding)
                                })
                            
                            try:
                                response = sqs.send_message_batch(
                                    QueueUrl=ASFF_SQS_QUEUE,
                                    Entries=entries
                                )
                                asff_sent += len(response.get('Successful', []))
                                asff_failed += len(response.get('Failed', []))
                                
                                # Log any batch failures
                                for failed in response.get('Failed', []):
                                    logger.warning(f"Failed to send ASFF finding to queue: {failed}")
                                    
                            except Exception as batch_error:
                                logger.error(f"Failed to send ASFF batch to queue: {str(batch_error)}")
                                asff_failed += len(batch)
                        
                        processing_stats['asff_findings_sent'] += asff_sent
                        processing_stats['asff_send_failures'] += asff_failed
                        
                        logger.info(f"Sent {asff_sent} ASFF findings to SQS queue, {asff_failed} failed")
                        
                        if asff_failed > 0:
                            logger.warning(f"ASFF send failures for message {message_id}: {asff_failed}")
                            message_has_failures = True
                            
                    except Exception as e:
                        logger.error(f"Failed to send ASFF findings to queue: {str(e)}")
                        processing_stats['asff_send_failures'] += len(asff_findings)
                        message_has_failures = True
                        message_has_failures = True
                
                # Log detailed processing results
                logger.info(
                    f"Processed SQS message {message_id}",
                    extra={
                        'message_id': message_id,
                        'cloud_events_count': len(cloud_events),
                        'cloudtrail_events_count': len(cloudtrail_events),
                        'ocsf_events_count': len(ocsf_events),
                        'cloudtrail_successful': cloudtrail_result.get('Successful', 0),
                        'cloudtrail_failed': cloudtrail_result.get('Failed', 0),
                        'security_lake_successful': security_lake_result.get('Successful', 0),
                        'security_lake_failed': security_lake_result.get('Failed', 0)
                    }
                )
                
                # Check for failures and handle accordingly
                if message_has_failures:
                    logger.warning(f"Partial failures processing message {message_id}")
                    batch_item_failures.append({'itemIdentifier': message_id})
                    processing_stats['failed_messages'] += 1
                elif len(cloud_events) > 0:
                    processing_stats['processed_messages'] += 1
                    
                    # DEBUG: Log why deletion might not be happening
                    logger.info(f"Message {message_id} processed successfully - checking deletion conditions:")
                    logger.info(f"  event_type: {event_type}")
                    logger.info(f"  receiptHandle present: {'receiptHandle' in record}")
                    logger.info(f"  queue_url: {queue_url}")
                    
                    # For custom queue processing, delete message immediately after successful processing
                    if event_type == 'custom_queue_processing' and 'receiptHandle' in record and queue_url:
                        try:
                            sqs = get_sqs_client()
                            sqs.delete_message(
                                QueueUrl=queue_url,
                                ReceiptHandle=record['receiptHandle']
                            )
                            logger.info(f"Successfully deleted processed message {message_id} from queue (processed {len(cloud_events)} events)")
                            processing_stats.setdefault('messages_deleted_immediately', 0)
                            processing_stats['messages_deleted_immediately'] += 1
                        except Exception as delete_error:
                            logger.warning(f"Failed to delete processed message {message_id}: {str(delete_error)}")
                            # Still track for batch deletion as fallback
                            successful_receipt_handles.append(record['receiptHandle'])
                    elif event_type == 'custom_queue_processing':
                        # Only log warning for custom_queue_processing where we expected to delete but couldn't
                        logger.warning(f"Message {message_id} not deleted - conditions not met (receiptHandle: {'receiptHandle' in record}, queue_url: {bool(queue_url)})")
                    # For SQS trigger events, AWS Lambda handles deletion automatically if not in batchItemFailures
                else:
                    # No events to process
                    logger.warning(f"No cloud events found in message {message_id}")
                    batch_item_failures.append({'itemIdentifier': message_id})
                    processing_stats['failed_messages'] += 1
                
            except json.JSONDecodeError as e:
                logger.error(
                    f"Invalid JSON in SQS message {message_id}",
                    extra={'error': str(e)}
                )
                # Send JSON parsing failure to DLQ
                send_failed_event_to_dlq(
                    original_message=record,
                    failure_reason="JSON parsing error",
                    error_details=f"Failed to parse SQS message body as JSON: {str(e)}",
                    source_queue_url=queue_url
                )
                batch_item_failures.append({'itemIdentifier': message_id})
                processing_stats['failed_messages'] += 1
                
            except Exception as e:
                import traceback
                logger.error(
                    f"DETAILED ERROR processing SQS message {message_id}: {type(e).__name__}: {str(e)}",
                    extra={
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'message_id': message_id
                    }
                )
                # Log full traceback for debugging
                logger.error(f"Full traceback for message {message_id}:\n{traceback.format_exc()}")
                
                # Send general processing failure to DLQ
                send_failed_event_to_dlq(
                    original_message=record,
                    failure_reason=f"General processing error: {type(e).__name__}",
                    error_details=f"{str(e)}\n\nFull traceback:\n{traceback.format_exc()}",
                    source_queue_url=queue_url
                )
                
                batch_item_failures.append({'itemIdentifier': message_id})
                processing_stats['failed_messages'] += 1
        
        # For custom queue processing, handle any remaining messages that failed immediate deletion
        immediate_deletions = processing_stats.get('messages_deleted_immediately', 0)
        if event_type == 'custom_queue_processing':
            if successful_receipt_handles and queue_url:
                # Process any fallback messages that couldn't be deleted immediately
                logger.info(f"Processing {len(successful_receipt_handles)} fallback messages for batch deletion")
                try:
                    deletion_result = delete_processed_messages(queue_url, successful_receipt_handles)
                    batch_deleted = deletion_result.get('successful_deletions', 0)
                    batch_failed = deletion_result.get('failed_deletions', 0)
                    
                    processing_stats.update({
                        'messages_deleted_batch': batch_deleted,
                        'messages_deleted_total': immediate_deletions + batch_deleted,
                        'deletion_failures': batch_failed
                    })
                    
                    if batch_deleted > 0:
                        logger.info(f"Batch deleted {batch_deleted} fallback messages from queue {queue_url}")
                    if batch_failed > 0:
                        logger.warning(f"Failed to batch delete {batch_failed} messages from queue {queue_url}")
                        
                except Exception as e:
                    logger.error(f"Failed batch deletion for queue {queue_url}: {str(e)}")
                    processing_stats.update({
                        'messages_deleted_batch': 0,
                        'messages_deleted_total': immediate_deletions,
                        'deletion_failures': len(successful_receipt_handles),
                        'deletion_error': str(e)
                    })
            else:
                processing_stats.update({
                    'messages_deleted_total': immediate_deletions,
                    'messages_deleted_batch': 0,
                    'deletion_failures': 0
                })
                if immediate_deletions > 0:
                    logger.info(f"Total messages deleted immediately: {immediate_deletions}")
        
        # Prepare final response
        response = {
            'statusCode': 200,
            **processing_stats
        }
        
        # Include batch item failures for SQS partial batch failure handling
        if batch_item_failures:
            response['batchItemFailures'] = batch_item_failures
            logger.warning(f"Returning {len(batch_item_failures)} messages for retry")
        
        # Log final processing summary
        logger.info(
            f"Lambda execution completed",
            extra=processing_stats
        )
        
        return response
        
    except Exception as e:
        import traceback
        logger.error(
            f"CRITICAL ERROR in Lambda handler: {type(e).__name__}: {str(e)}",
            extra={
                'error': str(e),
                'error_type': type(e).__name__,
                'event_data_store_arn': EVENT_DATA_STORE_ARN,
                'total_messages': len(records) if 'records' in locals() else 0
            }
        )
        # Always log full traceback for critical errors
        logger.error(f"CRITICAL ERROR Full traceback:\n{traceback.format_exc()}")
        
        # Return all messages as failed for retry on critical errors
        # Handle both SQS trigger events and custom queue events
        if is_sqs_trigger_event(event):
            batch_item_failures = [
                {'itemIdentifier': record['messageId']}
                for record in event.get('Records', [])
            ]
        else:
            # For custom queue processing, we can't retry automatically
            batch_item_failures = []
        
        return {
            'statusCode': 500,
            'error': str(e),
            'event_type': 'sqs_trigger' if is_sqs_trigger_event(event) else 'custom_queue_processing',
            'queue_url': event.get('queue_url') if not is_sqs_trigger_event(event) else None,
            'batchItemFailures': batch_item_failures,
            'critical_failure': True
        }


def is_flow_log_event(message_body: Dict[str, Any]) -> bool:
    """
    Check if message contains a Flow Log blob creation event
    
    Args:
        message_body: Parsed SQS message body
        
    Returns:
        True if this is a Flow Log blob creation event, False otherwise
    """
    try:
        # Check if message has event_data array
        if isinstance(message_body, dict) and 'event_data' in message_body:
            event_data = message_body['event_data']
            
            # Check if event_data is a list
            if isinstance(event_data, list) and len(event_data) > 0:
                # Check first event for BlobCreated type
                first_event = event_data[0]
                if isinstance(first_event, dict):
                    event_type = first_event.get('type', '')
                    
                    # Check for Microsoft.Storage.BlobCreated type
                    if event_type == 'Microsoft.Storage.BlobCreated':
                        # Additional validation: check subject contains flow log path
                        subject = first_event.get('subject', '')
                        if 'flowlog' in subject.lower() or 'insights-logs-flowlogflowevent' in subject:
                            logger.debug(f"Detected Flow Log blob creation event with subject: {subject}")
                            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking for Flow Log event: {str(e)}")
        return False


def extract_cloud_events_from_message(message_body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract cloud security events from SQS message body with flexible parsing
    
    Args:
        message_body: Parsed SQS message body
        
    Returns:
        List of cloud events ready for transformation
    """
    cloud_events = []
    
    try:
        # Handle different message body structures
        if isinstance(message_body, list):
            # Direct array of events
            cloud_events = message_body
        elif isinstance(message_body, dict):
            # Check for events array in wrapper
            if 'events' in message_body:
                cloud_events = message_body['events']
            elif 'event_data' in message_body:
                event_data = message_body['event_data']
                
                # Check if event_data contains a records array (Microsoft Graph Activity pattern)
                if isinstance(event_data, dict) and 'records' in event_data:
                    records = event_data['records']
                    if isinstance(records, list) and len(records) > 0:
                        # Each record becomes its own event with event_data at root
                        cloud_events = [{'event_data': record} for record in records]
                        logger.info(f"Unwrapped {len(records)} records from event_data.records array")
                    else:
                        # Single event
                        cloud_events = [message_body]
                else:
                    # Single event with event_data structure (most common)
                    cloud_events = [message_body]
            else:
                # Treat entire message as single event
                cloud_events = [message_body]
        
        logger.debug(f"Extracted {len(cloud_events)} cloud events from message")
        return cloud_events
        
    except Exception as e:
        logger.error(f"Error extracting cloud events from message: {str(e)}")
        return []


def get_lambda_info() -> Dict[str, Any]:
    """
    Get Lambda function information for debugging and monitoring
    
    Returns:
        Dictionary with Lambda function details
    """
    return {
        'function_name': AWS_LAMBDA_FUNCTION_NAME,
        'function_version': AWS_LAMBDA_FUNCTION_VERSION,
        'runtime': AWS_EXECUTION_ENV,
        'memory_size': AWS_LAMBDA_FUNCTION_MEMORY_SIZE,
        'log_group': AWS_LAMBDA_LOG_GROUP_NAME,
        'log_stream': AWS_LAMBDA_LOG_STREAM_NAME,
        'transformer_version': '3.1.0',
        'target_format': 'CloudTrail Lake Integration',
        'enhanced_features': ['custom_queue_processing', 'dlq_support']
    }


# Log initialization information with both print and logger for debugging
lambda_info = get_lambda_info()

try:
    logger.info(f"Enhanced Event Transformer Lambda initialized successfully", extra=lambda_info)
except Exception as e:
    logger.error(f"MODULE INIT ERROR: Logger failed during initialization: {str(e)}")

# Test basic imports
try:
    from helpers.event_transformer import CloudTrailTransformer
    from helpers.security_lake_client import SecurityLakeClient
    from core.event_mapper import CloudEventMapper
except ImportError as e:
    print(f"MODULE INIT ERROR: Import failure: {str(e)}")
except Exception as e:
    print(f"MODULE INIT ERROR: Unexpected import error: {str(e)}")