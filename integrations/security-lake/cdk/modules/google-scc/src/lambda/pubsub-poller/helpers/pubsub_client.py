"""
GCP Pub/Sub Client for AWS Lambda
Provides simplified interface for pulling messages from GCP Pub/Sub subscriptions.
"""

import json
import logging
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from google.cloud import pubsub_v1
from google.oauth2 import service_account
from google.api_core import exceptions as gcp_exceptions

logger = logging.getLogger(__name__)


class PubSubClient:
    """GCP Pub/Sub client for consuming Security Command Center events."""
    
    def __init__(self, project_id: str, subscription_id: str, 
                 credentials_json: Optional[Dict[str, Any]] = None,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize Pub/Sub subscriber client
        
        Args:
            project_id: GCP project ID
            subscription_id: Pub/Sub subscription ID
            credentials_json: Service account credentials as JSON dict
            logger: Logger instance
        """
        self.project_id = project_id
        self.subscription_id = subscription_id
        self.logger = logger or logging.getLogger(__name__)
        
        # Build full subscription path
        self.subscription_path = f"projects/{project_id}/subscriptions/{subscription_id}"
        
        # Initialize credentials and subscriber client
        try:
            if credentials_json:
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_json
                )
                self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
            else:
                # Use application default credentials
                self.subscriber = pubsub_v1.SubscriberClient()
            
            self.logger.info("PubSubClient initialized", extra={
                'project_id': project_id,
                'subscription_id': subscription_id,
                'subscription_path': self.subscription_path
            })
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Pub/Sub client: {str(e)}")
            raise
    
    def pull_messages(self, max_messages: int = 100, 
                     return_immediately: bool = False,
                     timeout: int = 30) -> Dict[str, Any]:
        """
        Pull messages from Pub/Sub subscription
        
        Args:
            max_messages: Maximum number of messages to pull
            return_immediately: Whether to return immediately if no messages
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary with 'messages' list and metadata
        """
        try:
            self.logger.info(f"Pulling messages from subscription: {self.subscription_path}")
            self.logger.debug(f"Parameters: max_messages={max_messages}, timeout={timeout}s")
            
            # Create pull request
            request = {
                "subscription": self.subscription_path,
                "max_messages": max_messages,
                "return_immediately": return_immediately
            }
            
            # Pull messages synchronously
            response = self.subscriber.pull(
                request=request,
                timeout=timeout
            )
            
            # Process received messages
            messages = []
            for received_message in response.received_messages:
                processed_message = self._process_pubsub_message(received_message)
                if processed_message:
                    messages.append(processed_message)
            
            self.logger.info(f"Successfully pulled {len(messages)} messages from Pub/Sub")
            
            return {
                "messages": messages,
                "message_count": len(messages)
            }
            
        except gcp_exceptions.DeadlineExceeded:
            self.logger.info("Pull request timed out - no messages available")
            return {
                "messages": [],
                "message_count": 0
            }
        except gcp_exceptions.GoogleAPICallError as e:
            self.logger.error(f"GCP API error pulling messages: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error pulling messages from Pub/Sub: {str(e)}")
            raise
    
    def _process_pubsub_message(self, received_message) -> Optional[Dict[str, Any]]:
        """
        Process individual Pub/Sub message
        
        Args:
            received_message: GCP ReceivedMessage object
            
        Returns:
            Processed message dictionary or None if processing fails
        """
        try:
            message = received_message.message
            
            # Decode message data
            try:
                message_data_bytes = message.data
                message_data_str = message_data_bytes.decode('utf-8')
                
                # Try to parse as JSON
                try:
                    event_data = json.loads(message_data_str)
                except json.JSONDecodeError:
                    # If not JSON, store as raw string
                    event_data = {'raw_data': message_data_str}
            except Exception as decode_error:
                self.logger.warning(f"Error decoding message data: {str(decode_error)}")
                event_data = {'raw_data': base64.b64encode(message.data).decode('utf-8')}
            
            # Extract message attributes
            attributes = dict(message.attributes) if message.attributes else {}
            
            # Build processed message structure
            processed_message = {
                'event_data': event_data,
                'message_metadata': {
                    'message_id': message.message_id,
                    'publish_time': message.publish_time.isoformat() if message.publish_time else None,
                    'ack_id': received_message.ack_id,
                    'delivery_attempt': received_message.delivery_attempt if hasattr(received_message, 'delivery_attempt') else None,
                    'attributes': attributes,
                    'ordering_key': message.ordering_key if message.ordering_key else None
                },
                'processing_metadata': {
                    'processed_timestamp': datetime.now(timezone.utc).isoformat(),
                    'processor_version': '1.0.0',
                    'source': 'gcp-pubsub',
                    'project_id': self.project_id,
                    'subscription_id': self.subscription_id
                }
            }
            
            return processed_message
            
        except Exception as e:
            self.logger.error(f"Error processing Pub/Sub message: {str(e)}")
            return None
    
    def acknowledge_messages(self, ack_ids: List[str]) -> bool:
        """
        Acknowledge messages to remove them from subscription
        
        Args:
            ack_ids: List of acknowledgment IDs to acknowledge
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not ack_ids:
                self.logger.warning("No ack_ids provided for acknowledgment")
                return True
            
            request = {
                "subscription": self.subscription_path,
                "ack_ids": ack_ids
            }
            
            self.subscriber.acknowledge(request=request)
            
            self.logger.debug(f"Successfully acknowledged {len(ack_ids)} messages")
            return True
            
        except gcp_exceptions.GoogleAPICallError as e:
            self.logger.error(f"GCP API error acknowledging messages: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error acknowledging messages: {str(e)}")
            return False
    
    def modify_ack_deadline(self, ack_ids: List[str], ack_deadline_seconds: int) -> bool:
        """
        Modify acknowledgment deadline for messages
        
        Args:
            ack_ids: List of acknowledgment IDs
            ack_deadline_seconds: New deadline in seconds (0-600)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not ack_ids:
                self.logger.warning("No ack_ids provided for deadline modification")
                return True
            
            request = {
                "subscription": self.subscription_path,
                "ack_ids": ack_ids,
                "ack_deadline_seconds": ack_deadline_seconds
            }
            
            self.subscriber.modify_ack_deadline(request=request)
            
            self.logger.debug(f"Modified ack deadline for {len(ack_ids)} messages to {ack_deadline_seconds}s")
            return True
            
        except gcp_exceptions.GoogleAPICallError as e:
            self.logger.error(f"GCP API error modifying ack deadline: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error modifying ack deadline: {str(e)}")
            return False
    
    def get_subscription_info(self) -> Optional[Dict[str, Any]]:
        """
        Get subscription configuration and status
        
        Returns:
            Subscription info dictionary or None if error
        """
        try:
            subscription = self.subscriber.get_subscription(
                request={"subscription": self.subscription_path}
            )
            
            info = {
                'name': subscription.name,
                'topic': subscription.topic,
                'ack_deadline_seconds': subscription.ack_deadline_seconds,
                'retain_acked_messages': subscription.retain_acked_messages,
                'message_retention_duration': subscription.message_retention_duration.seconds if subscription.message_retention_duration else None,
                'labels': dict(subscription.labels) if subscription.labels else {},
                'enable_message_ordering': subscription.enable_message_ordering,
                'expiration_policy': str(subscription.expiration_policy) if subscription.expiration_policy else None,
                'filter': subscription.filter if subscription.filter else None
            }
            
            self.logger.info(f"Retrieved subscription info: {subscription.name}")
            return info
            
        except gcp_exceptions.GoogleAPICallError as e:
            self.logger.error(f"GCP API error getting subscription info: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting subscription info: {str(e)}")
            return None
    
    def seek_to_timestamp(self, timestamp: datetime) -> bool:
        """
        Seek subscription to specific timestamp
        
        Args:
            timestamp: Timestamp to seek to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            request = {
                "subscription": self.subscription_path,
                "time": timestamp
            }
            
            self.subscriber.seek(request=request)
            
            self.logger.info(f"Seeked subscription to timestamp: {timestamp.isoformat()}")
            return True
            
        except gcp_exceptions.GoogleAPICallError as e:
            self.logger.error(f"GCP API error seeking subscription: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error seeking subscription: {str(e)}")
            return False
    
    def close(self):
        """Close the Pub/Sub client connection"""
        try:
            if self.subscriber:
                # Close the subscriber client
                self.subscriber.close()
                self.logger.info("Pub/Sub client connection closed")
        except Exception as e:
            self.logger.warning(f"Error closing Pub/Sub client: {str(e)}")


class PubSubClientError(Exception):
    """Custom exception for Pub/Sub client errors"""
    pass