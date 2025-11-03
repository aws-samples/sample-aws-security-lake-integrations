"""
SQS Client for handling SQS message operations
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
    
    def send_message(
        self, 
        queue_url: str, 
        message_body: Union[str, Dict], 
        message_attributes: Optional[Dict] = None,
        delay_seconds: int = 0
    ) -> Dict[str, Any]:
        """
        Send a single message to SQS queue
        
        Args:
            queue_url: SQS queue URL
            message_body: Message body (string or dict - will be JSON serialized if dict)
            message_attributes: Optional message attributes
            delay_seconds: Delay in seconds before message becomes available
            
        Returns:
            Response from SQS send_message
        """
        try:
            # Convert dict to JSON string if needed
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
                f"Message sent to SQS queue",
                extra={
                    'queue_url': queue_url,
                    'message_id': response.get('MessageId'),
                    'md5_of_body': response.get('MD5OfBody')
                }
            )
            
            return response
            
        except ClientError as e:
            self.logger.error(
                f"Failed to send message to SQS",
                extra={
                    'queue_url': queue_url,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending SQS message: {str(e)}")
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
    
    def get_queue_attributes(self, queue_url: str) -> Dict[str, Any]:
        """
        Get queue attributes
        
        Args:
            queue_url: SQS queue URL
            
        Returns:
            Dictionary of queue attributes
        """
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['All']
            )
            
            return response.get('Attributes', {})
            
        except ClientError as e:
            self.logger.error(
                f"Failed to get queue attributes",
                extra={
                    'queue_url': queue_url,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            raise