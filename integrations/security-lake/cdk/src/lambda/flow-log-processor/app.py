"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Microsoft Defender for Cloud - AWS Lambda Flow Log Processor

This Lambda function processes Azure Event Grid events for flow log blob creation.
Downloads blobs from Azure Storage, converts to OCSF format, and writes to Security Lake as Parquet.

Author: Jeremy Tirrell
Version: 2.0.1 (Full OCSF Conversion and Parquet Output)
Build: 20251020-2051
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

# Import helper classes
from helpers.azure_blob_client import AzureBlobClient
from helpers.secrets_manager_client import SecretsManagerClient
from helpers.flow_log_transformer import FlowLogTransformer
from helpers.security_lake_client import SecurityLakeClient

# Configure logging
logging.basicConfig(
    level=os.getenv('LOGGING_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s'
)
logger = logging.getLogger()
logger.setLevel(os.getenv('LOGGING_LEVEL', 'INFO'))

# Global clients for connection reuse
secrets_client: Optional[SecretsManagerClient] = None
azure_blob_client: Optional[AzureBlobClient] = None
security_lake_client: Optional[SecurityLakeClient] = None
flow_log_transformer: Optional[FlowLogTransformer] = None


def get_secrets_client() -> SecretsManagerClient:
    """Get or create Secrets Manager client with connection reuse"""
    global secrets_client
    
    if secrets_client is None:
        secrets_client = SecretsManagerClient(
            region_name=os.getenv('AWS_REGION', 'ca-central-1')
        )
    
    return secrets_client


def get_azure_blob_client(credentials: Dict[str, Any]) -> AzureBlobClient:
    """Get or create Azure Blob client with connection reuse"""
    global azure_blob_client
    
    if azure_blob_client is None:
        azure_blob_client = AzureBlobClient(
            tenant_id=credentials['tenantId'],
            client_id=credentials['clientId'],
            client_secret=credentials['clientSecret'],
            storage_account_name=credentials['storageAccountName']
        )
    
    return azure_blob_client


def get_security_lake_client() -> Optional[SecurityLakeClient]:
    """Get or create Security Lake client with connection reuse"""
    global security_lake_client
    
    if security_lake_client is None:
        s3_bucket = os.getenv('SECURITY_LAKE_S3_BUCKET')
        s3_path = os.getenv('SECURITY_LAKE_PATH', '')
        
        if not s3_bucket:
            logger.warning("SECURITY_LAKE_S3_BUCKET not configured")
            return None
        
        security_lake_client = SecurityLakeClient(
            s3_bucket=s3_bucket,
            s3_path=s3_path,
            region_name=os.getenv('AWS_REGION', 'ca-central-1')
        )
    
    return security_lake_client


def get_flow_log_transformer() -> FlowLogTransformer:
    """Get or create Flow Log Transformer with connection reuse"""
    global flow_log_transformer
    
    if flow_log_transformer is None:
        flow_log_transformer = FlowLogTransformer()
    
    return flow_log_transformer


def parse_event_grid_event(message_body: str) -> Optional[Dict[str, Any]]:
    """
    Parse Azure Event Grid BlobCreated event
    
    Args:
        message_body: SQS message body containing Event Grid event
        
    Returns:
        Parsed event or None if parsing fails
    """
    try:
        message = json.loads(message_body)
        
        # Extract event_data array
        event_data = message.get('event_data', [])
        if not event_data or not isinstance(event_data, list):
            logger.warning("No event_data array found in message")
            return None
        
        # Get first event
        event = event_data[0]
        
        # Validate required fields
        if event.get('type') != 'Microsoft.Storage.BlobCreated':
            logger.warning(f"Unsupported event type: {event.get('type')}")
            return None
        
        return event
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Event Grid event: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing event: {str(e)}")
        return None


def extract_blob_info(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Extract blob storage information from Event Grid event
    
    Args:
        event: Parsed Event Grid event
        
    Returns:
        Dictionary with container and blob names, or None if extraction fails
    """
    try:
        # Extract from subject: /blobServices/default/containers/{container}/blobs/{blob}
        subject = event.get('subject', '')
        parts = subject.split('/')
        
        if 'containers' not in parts or 'blobs' not in parts:
            logger.error(f"Invalid subject format: {subject}")
            return None
        
        container_idx = parts.index('containers') + 1
        blobs_idx = parts.index('blobs') + 1
        
        container_name = parts[container_idx] if container_idx < len(parts) else None
        blob_name = '/'.join(parts[blobs_idx:]) if blobs_idx < len(parts) else None
        
        if not container_name or not blob_name:
            logger.error(f"Failed to extract container/blob from subject: {subject}")
            return None
        
        # Extract URL from event data
        blob_url = event.get('data', {}).get('url', '')
        content_length = event.get('data', {}).get('contentLength', 0)
        
        return {
            'container_name': container_name,
            'blob_name': blob_name,
            'url': blob_url,
            'content_length': content_length
        }
        
    except Exception as e:
        logger.error(f"Error extracting blob info: {str(e)}")
        return None


def extract_subscription_id(flow_log_resource_id: str) -> str:
    """
    Extract Azure subscription ID from flowLogResourceID
    
    Args:
        flow_log_resource_id: Flow log resource ID (e.g., /SUBSCRIPTIONS/39B6331A-.../...)
        
    Returns:
        Subscription ID (lowercase) or 'unknown' if extraction fails
    """
    try:
        parts = flow_log_resource_id.split('/')
        if 'SUBSCRIPTIONS' in parts:
            sub_idx = parts.index('SUBSCRIPTIONS') + 1
            if sub_idx < len(parts):
                return parts[sub_idx].lower()  # Convert to lowercase
        return 'unknown'
    except Exception as e:
        logger.warning(f"Failed to extract subscription ID: {str(e)}")
        return 'unknown'


def process_flow_log_blob(
    blob_client: AzureBlobClient,
    blob_info: Dict[str, str],
    transformer: FlowLogTransformer,
    lake_client: Optional[SecurityLakeClient]
) -> Dict[str, Any]:
    """
    Download blob, convert to OCSF, and write to Security Lake
    
    Args:
        blob_client: Azure Blob Storage client
        blob_info: Blob information dictionary
        transformer: Flow log transformer
        lake_client: Security Lake client
        
    Returns:
        Processing results dictionary
    """
    result = {
        'blob_downloaded': False,
        'ocsf_records_created': 0,
        'records_written_to_lake': 0,
        'error': None
    }
    
    try:
        logger.debug(f"Downloading blob: {blob_info['blob_name']} ({blob_info['content_length']} bytes)")
        
        # Download blob content
        blob_data = blob_client.download_blob(
            container_name=blob_info['container_name'],
            blob_name=blob_info['blob_name']
        )
        
        if not blob_data:
            result['error'] = "Failed to download blob data"
            return result
        
        result['blob_downloaded'] = True
        logger.debug(f"Downloaded {len(blob_data)} bytes")
        
        # Parse flow log JSON
        try:
            flow_log_data = json.loads(blob_data.decode('utf-8'))
            logger.debug(f"Parsed flow log with {len(flow_log_data.get('records', []))} records")
        except json.JSONDecodeError as e:
            result['error'] = f"Failed to parse flow log JSON: {str(e)}"
            return result
        
        # Extract subscription ID from first record for partitioning
        subscription_id = 'unknown'
        if flow_log_data.get('records'):
            first_record = flow_log_data['records'][0]
            flow_log_resource_id = first_record.get('flowLogResourceID', '')
            subscription_id = extract_subscription_id(flow_log_resource_id)
            logger.debug(f"Extracted Azure subscription ID: {subscription_id}")
        
        # Transform to OCSF format (pass subscription_id for cloud.account.uid)
        ocsf_records = transformer.transform_to_ocsf(flow_log_data, subscription_id)
        result['ocsf_records_created'] = len(ocsf_records)
        
        logger.debug(f"Transformed {len(ocsf_records)} flow tuples to OCSF format")
        
        # Write to Security Lake if enabled
        if lake_client and ocsf_records:
            security_lake_enabled = os.getenv('SECURITY_LAKE_ENABLED', 'false').lower() == 'true'
            
            if security_lake_enabled:
                success = lake_client.write_ocsf_records(
                    records=ocsf_records,
                    source_name='azure-flowlogs',
                    account_id=subscription_id
                )
                
                if success:
                    result['records_written_to_lake'] = len(ocsf_records)
                    logger.info(f"Successfully wrote {len(ocsf_records)} records to Security Lake")
                else:
                    result['error'] = "Failed to write to Security Lake"
            else:
                logger.warning("Security Lake disabled, skipping write")
        
        return result
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error processing flow log blob: {str(e)}")
        return result


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    AWS Lambda entry point for Flow Log processing
    
    Args:
        event: SQS event containing Azure Event Grid messages
        context: Lambda context object
        
    Returns:
        Dictionary containing processing results with batch item failures
    """
    logger.info(f"Flow Log Processor started - Processing {len(event.get('Records', []))} messages")
    logger.debug(f"Request ID: {context.aws_request_id}")
    logger.debug(f"Remaining Time: {context.get_remaining_time_in_millis()}ms")
    
    stats = {
        'messages_received': len(event.get('Records', [])),
        'messages_processed': 0,
        'blobs_downloaded': 0,
        'ocsf_records_created': 0,
        'records_written_to_lake': 0,
        'errors': 0
    }
    
    batch_item_failures = []
    
    try:
        # Get Azure credentials
        secrets_name = os.getenv('AZURE_FLOWLOG_CREDENTIALS_SECRET_NAME')
        if not secrets_name:
            raise ValueError("AZURE_FLOWLOG_CREDENTIALS_SECRET_NAME not configured")
        
        logger.debug(f"Retrieving Azure credentials from secret: {secrets_name}")
        secrets = get_secrets_client()
        azure_credentials = secrets.get_secret(secrets_name)
        
        if not azure_credentials:
            raise ValueError("Failed to retrieve Azure credentials")
        
        logger.debug("Azure credentials retrieved successfully")
        
        # Initialize clients
        blob_client = get_azure_blob_client(azure_credentials)
        transformer = get_flow_log_transformer()
        lake_client = get_security_lake_client()
        
        # Process each SQS message
        for idx, record in enumerate(event.get('Records', [])):
            message_id = record['messageId']
            
            logger.debug(f"Processing message {idx + 1}/{len(event.get('Records', []))}: {message_id}")
            
            try:
                # Parse Event Grid event
                event_grid_event = parse_event_grid_event(record['body'])
                if not event_grid_event:
                    logger.error("Failed to parse Event Grid event")
                    batch_item_failures.append({'itemIdentifier': message_id})
                    stats['errors'] += 1
                    continue
                
                # Extract blob information
                blob_info = extract_blob_info(event_grid_event)
                if not blob_info:
                    logger.error("Failed to extract blob information")
                    batch_item_failures.append({'itemIdentifier': message_id})
                    stats['errors'] += 1
                    continue
                
                # Process blob: download, convert, write
                process_result = process_flow_log_blob(
                    blob_client=blob_client,
                    blob_info=blob_info,
                    transformer=transformer,
                    lake_client=lake_client
                )
                
                if process_result.get('error'):
                    logger.error(f"Failed to process blob: {process_result['error']}")
                    batch_item_failures.append({'itemIdentifier': message_id})
                    stats['errors'] += 1
                else:
                    stats['blobs_downloaded'] += 1 if process_result['blob_downloaded'] else 0
                    stats['ocsf_records_created'] += process_result['ocsf_records_created']
                    stats['records_written_to_lake'] += process_result['records_written_to_lake']
                    stats['messages_processed'] += 1
                    logger.debug(f"Successfully processed message {message_id}")
                
            except Exception as e:
                logger.error(f"Error processing message {message_id}: {str(e)}")
                batch_item_failures.append({'itemIdentifier': message_id})
                stats['errors'] += 1
        
        logger.info(f"Flow Log Processor complete - Processed: {stats['messages_processed']}/{stats['messages_received']}, OCSF events: {stats['ocsf_records_created']}, Written to Lake: {stats['records_written_to_lake']}, Errors: {stats['errors']}")
        
        # Return ONLY batchItemFailures for SQS batch processing
        # Do not include statusCode or body as they interfere with SQS failure handling
        return {
            'batchItemFailures': batch_item_failures
        }
        
    except Exception as e:
        logger.error(f"Fatal error in Lambda handler: {str(e)}")
        stats['errors'] += 1
        
        # Return all messages as failures on fatal error
        batch_item_failures = [
            {'itemIdentifier': record['messageId']}
            for record in event.get('Records', [])
        ]
        
        # Return ONLY batchItemFailures for SQS batch processing
        return {
            'batchItemFailures': batch_item_failures
        }