"""
Security Hub Processor Lambda
Processes ASFF messages from SQS and sends them to AWS Security Hub
"""

import json
import logging
import os
from typing import Dict, Any, List
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

# Configure logging for AWS Lambda
# Lambda pre-configures root logger, so we just set the level
logger = logging.getLogger()
if logger.handlers:
    for handler in logger.handlers:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s'
        ))
logger.setLevel(os.getenv('LOGGING_LEVEL', 'INFO'))

# AWS clients
securityhub_client = boto3.client('securityhub')

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process ASFF messages from SQS and import to Security Hub
    
    Args:
        event: SQS trigger event with ASFF findings
        context: Lambda context
        
    Returns:
        Response with batch item failures for retry/DLQ routing
        
    IMPORTANT: Always returns success (200) to prevent entire batch retry.
    Failed messages are reported via batchItemFailures for SQS to route to DLQ.
    """
    logger.info(f"Security Hub Processor started with {len(event.get('Records', []))} messages")
    
    stats = {
        'total_messages': len(event.get('Records', [])),
        'processed_findings': 0,
        'failed_findings': 0,
        'batch_item_failures': []
    }
    
    # Process each message individually
    for record in event.get('Records', []):
        message_id = record.get('messageId', 'unknown')
        
        try:
            # Parse ASFF finding from message body
            message_body = json.loads(record['body'])
            finding = json.loads(message_body) if isinstance(message_body, str) else message_body
            
            logger.info(f"Processing finding: {finding.get('Id', 'unknown')} (message: {message_id})")
            
            # Validate finding has required ASFF fields
            if not finding.get('Id') or not finding.get('AwsAccountId'):
                logger.error(f"Invalid ASFF finding structure - missing required fields (message: {message_id})")
                logger.info(f"Failed event content (message: {message_id}): {json.dumps(finding, indent=2, default=str)}")
                stats['failed_findings'] += 1
                stats['batch_item_failures'].append({'itemIdentifier': message_id})
                continue
            
            # Enforce field length limits for Security Hub
            if 'Remediation' in finding and 'Recommendation' in finding['Remediation']:
                recommendation_text = finding['Remediation']['Recommendation'].get('Text', '')
                if len(recommendation_text) > 512:
                    logger.warning(f"Truncating Remediation.Recommendation.Text from {len(recommendation_text)} to 512 chars")
                    finding['Remediation']['Recommendation']['Text'] = recommendation_text[:512]
            
            if 'Description' in finding and len(finding['Description']) > 1024:
                logger.warning(f"Truncating Description from {len(finding['Description'])} to 1024 chars")
                finding['Description'] = finding['Description'][:1024]
            
            if 'Title' in finding and len(finding['Title']) > 256:
                logger.warning(f"Truncating Title from {len(finding['Title'])} to 256 chars")
                finding['Title'] = finding['Title'][:256]
            
            # Batch import findings to Security Hub
            response = securityhub_client.batch_import_findings(
                Findings=[finding]
            )
            
            if response.get('FailedCount', 0) > 0:
                failed_findings = response.get('FailedFindings', [])
                logger.error(f"SecurityHub rejected finding {message_id}: {failed_findings}")
                logger.info(f"Failed event content (message: {message_id}): {json.dumps(finding, indent=2, default=str)}")
                stats['failed_findings'] += 1
                stats['batch_item_failures'].append({'itemIdentifier': message_id})
            else:
                logger.info(f"Successfully imported finding to SecurityHub (message: {message_id})")
                stats['processed_findings'] += 1
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message {message_id}: {str(e)}")
            logger.info(f"Failed event content (message: {message_id}): {record.get('body', 'N/A')}")
            stats['failed_findings'] += 1
            stats['batch_item_failures'].append({'itemIdentifier': message_id})
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"SecurityHub API error for message {message_id}: {error_code} - {error_message}")
            logger.info(f"Failed event content (message: {message_id}): {json.dumps(finding, indent=2, default=str)}")
            stats['failed_findings'] += 1
            stats['batch_item_failures'].append({'itemIdentifier': message_id})
        except KeyError as e:
            logger.error(f"Missing required field in message {message_id}: {str(e)}")
            logger.info(f"Failed event content (message: {message_id}): {record.get('body', 'N/A')}")
            stats['failed_findings'] += 1
            stats['batch_item_failures'].append({'itemIdentifier': message_id})
        except Exception as e:
            logger.error(f"Unexpected error processing message {message_id}: {str(e)}", exc_info=True)
            try:
                # Try to log the finding if it was parsed
                logger.info(f"Failed event content (message: {message_id}): {json.dumps(finding, indent=2, default=str)}")
            except:
                # Fall back to raw body if finding wasn't parsed
                logger.info(f"Failed event content (message: {message_id}): {record.get('body', 'N/A')}")
            stats['failed_findings'] += 1
            stats['batch_item_failures'].append({'itemIdentifier': message_id})
    
    logger.info(f"Batch processing complete: {stats['processed_findings']} success, {stats['failed_findings']} failed")
    
    # CRITICAL: Always return 200 to prevent Lambda from retrying entire batch
    # Failed messages are returned in batchItemFailures for SQS to route to DLQ after max retries
    return {
        'batchItemFailures': stats['batch_item_failures']
    }