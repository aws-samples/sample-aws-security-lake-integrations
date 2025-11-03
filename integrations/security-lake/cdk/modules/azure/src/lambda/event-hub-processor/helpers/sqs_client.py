"""
SQS Client for handling SQS message operations in Event Hub Processor
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
            self.logger.info("SQS client initialized successfully")
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
            events: List of event dictionaries
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
        
        return entries