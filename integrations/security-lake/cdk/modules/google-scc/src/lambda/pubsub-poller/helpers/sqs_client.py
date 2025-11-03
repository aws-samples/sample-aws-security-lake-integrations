"""
SQS Client for handling SQS message operations in Pub/Sub Poller

This module provides SQS operations for sending GCP Security Command Center
findings from Pub/Sub to SQS for further processing.

Author: SecureSight Team
Version: 1.0.0
"""

import json
import logging
import boto3
from typing import Dict, List, Any, Optional, Union
from botocore.exceptions import ClientError

class SQSClient:
    """
    AWS SQS client for handling queue operations
    """
    
    def __init__(self, region_name: str = None, logger: logging.Logger = None):
        """
        Initialize SQS client
        
        Args:
            region_name: AWS region name
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        
        try:
            self.sqs = boto3.client('sqs', region_name=region_name)
            self.logger.info("SQS client initialized successfully", extra={
                'region': region_name
            })
        except Exception as e:
            self.logger.error(f"Failed to initialize SQS client: {str(e)}")
            raise
    
    def send_message_batch(
        self, 
        queue_url: str, 
        messages: List[Dict]
    ) -> Dict[str, Any]:
        """
        Send multiple messages to SQS queue in batch (up to 10 messages)
        
        Args:
            queue_url: SQS queue URL
            messages: List of message dicts, each containing:
                - Id: Unique ID for the message
                - MessageBody: Message content
                - DelaySeconds: (optional) Delay before availability
                - MessageAttributes: (optional) Message attributes
                
        Returns:
            Response from SQS send_message_batch
        """
        try:
            if len(messages) > 10:
                raise ValueError("Cannot send more than 10 messages in a single batch")
            
            if not messages:
                self.logger.warning("No messages to send to SQS")
                return {'Successful': [], 'Failed': []}
            
            # Ensure message bodies are strings
            for message in messages:
                if isinstance(message.get('MessageBody'), dict):
                    message['MessageBody'] = json.dumps(message['MessageBody'])
            
            response = self.sqs.send_message_batch(
                QueueUrl=queue_url,
                Entries=messages
            )
            
            successful_count = len(response.get('Successful', []))
            failed_count = len(response.get('Failed', []))
            
            self.logger.info(
                f"Batch message send completed",
                extra={
                    'queue_url': queue_url,
                    'successful_messages': successful_count,
                    'failed_messages': failed_count,
                    'total_messages': len(messages)
                }
            )
            
            # Log any failures
            if response.get('Failed'):
                for failed_msg in response['Failed']:
                    self.logger.warning(
                        f"Failed to send message in batch",
                        extra={
                            'message_id': failed_msg.get('Id'),
                            'error_code': failed_msg.get('Code'),
                            'error_message': failed_msg.get('Message'),
                            'sender_fault': failed_msg.get('SenderFault')
                        }
                    )
            
            return response
            
        except ClientError as e:
            self.logger.error(
                f"Failed to send message batch to SQS",
                extra={
                    'queue_url': queue_url,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending SQS batch: {str(e)}")
            raise
    
    def create_batch_entries(
        self, 
        events: List[Dict], 
        id_prefix: str = "msg"
    ) -> List[Dict]:
        """
        Create SQS batch entries from a list of events
        
        Args:
            events: List of event dictionaries (GCP findings)
            id_prefix: Prefix for message IDs
            
        Returns:
            List of SQS batch entries
        """
        entries = []
        
        for idx, event in enumerate(events):
            entry = {
                'Id': f"{id_prefix}_{idx}",
                'MessageBody': json.dumps(event) if isinstance(event, dict) else str(event)
            }
            entries.append(entry)
        
        self.logger.debug(f"Created {len(entries)} batch entries with prefix '{id_prefix}'")
        
        return entries
    
    def send_findings_batch(
        self,
        queue_url: str,
        findings: List[Dict],
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """
        Send GCP findings to SQS in batches
        
        Args:
            queue_url: SQS queue URL
            findings: List of GCP finding dictionaries
            batch_size: Number of messages per batch (max 10)
            
        Returns:
            Dictionary with summary:
            - total_findings: Total number of findings
            - successful: Number of successfully sent findings
            - failed: Number of failed findings
            - batches_sent: Number of batches processed
        """
        if batch_size > 10:
            raise ValueError("Batch size cannot exceed 10 messages")
        
        total_findings = len(findings)
        successful = 0
        failed = 0
        batches_sent = 0
        
        try:
            # Process findings in batches
            for i in range(0, total_findings, batch_size):
                batch = findings[i:i + batch_size]
                batch_entries = self.create_batch_entries(
                    batch,
                    id_prefix=f"finding_batch{batches_sent}"
                )
                
                response = self.send_message_batch(queue_url, batch_entries)
                
                successful += len(response.get('Successful', []))
                failed += len(response.get('Failed', []))
                batches_sent += 1
            
            self.logger.info(
                "Findings batch send completed",
                extra={
                    'total_findings': total_findings,
                    'successful': successful,
                    'failed': failed,
                    'batches_sent': batches_sent
                }
            )
            
            return {
                'total_findings': total_findings,
                'successful': successful,
                'failed': failed,
                'batches_sent': batches_sent
            }
            
        except Exception as e:
            self.logger.error(
                f"Error sending findings batch: {str(e)}",
                extra={
                    'total_findings': total_findings,
                    'processed': successful + failed,
                    'successful': successful,
                    'failed': failed
                }
            )
            raise
    
    def send_single_message(
        self,
        queue_url: str,
        message_body: Union[Dict, str],
        delay_seconds: int = 0,
        message_attributes: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Send a single message to SQS queue
        
        Args:
            queue_url: SQS queue URL
            message_body: Message content (dict or string)
            delay_seconds: Delay before message is available
            message_attributes: Optional message attributes
            
        Returns:
            Response from SQS send_message
        """
        try:
            # Convert dict to JSON string
            if isinstance(message_body, dict):
                message_body = json.dumps(message_body)
            
            params = {
                'QueueUrl': queue_url,
                'MessageBody': message_body,
                'DelaySeconds': delay_seconds
            }
            
            if message_attributes:
                params['MessageAttributes'] = message_attributes
            
            response = self.sqs.send_message(**params)
            
            self.logger.info(
                "Single message sent successfully",
                extra={
                    'queue_url': queue_url,
                    'message_id': response.get('MessageId'),
                    'delay_seconds': delay_seconds
                }
            )
            
            return response
            
        except ClientError as e:
            self.logger.error(
                f"Failed to send single message to SQS",
                extra={
                    'queue_url': queue_url,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending single message: {str(e)}")
            raise