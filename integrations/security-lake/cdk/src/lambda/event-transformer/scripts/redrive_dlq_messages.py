#!/usr/bin/env python3
"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

DLQ Message Redrive Script

This script redrives (reprocesses) messages from a Dead Letter Queue (DLQ) back to the
source queue for reprocessing. It's designed to safely handle failed messages after fixes
have been deployed.

Usage Examples:
    # Dry run to preview what would happen
    python redrive_dlq_messages.py \\
        --dlq-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-dlq \\
        --source-queue-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-queue \\
        --dry-run

    # Actually redrive messages with confirmation
    python redrive_dlq_messages.py \\
        --dlq-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-dlq \\
        --source-queue-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-queue

    # Redrive messages without confirmation prompt
    python redrive_dlq_messages.py \\
        --dlq-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-dlq \\
        --source-queue-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-queue \\
        --yes

    # Redrive with custom batch size and max messages
    python redrive_dlq_messages.py \\
        --dlq-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-dlq \\
        --source-queue-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-queue \\
        --batch-size 5 \\
        --max-messages 50 \\
        --yes
"""

import argparse
import logging
import sys
import time
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class DLQRedriveStats:
    """Track statistics for DLQ redrive operation."""
    
    def __init__(self):
        self.total_received = 0
        self.total_sent = 0
        self.total_deleted = 0
        self.total_failed = 0
        self.failed_message_ids: List[str] = []
        self.failed_errors: List[str] = []
    
    def add_received(self, count: int = 1):
        """Increment received message count."""
        self.total_received += count
    
    def add_sent(self, count: int = 1):
        """Increment sent message count."""
        self.total_sent += count
    
    def add_deleted(self, count: int = 1):
        """Increment deleted message count."""
        self.total_deleted += count
    
    def add_failed(self, message_id: str, error: str):
        """Record a failed message."""
        self.total_failed += 1
        self.failed_message_ids.append(message_id)
        self.failed_errors.append(error)
    
    def print_summary(self):
        """Print summary statistics."""
        logger.info("=" * 80)
        logger.info("REDRIVE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Messages received from DLQ: {self.total_received}")
        logger.info(f"Messages sent to source queue: {self.total_sent}")
        logger.info(f"Messages deleted from DLQ: {self.total_deleted}")
        logger.info(f"Messages failed: {self.total_failed}")
        
        if self.total_failed > 0:
            logger.warning("=" * 80)
            logger.warning("FAILED MESSAGES")
            logger.warning("=" * 80)
            for msg_id, error in zip(self.failed_message_ids, self.failed_errors):
                logger.warning(f"Message ID: {msg_id}")
                logger.warning(f"Error: {error}")
                logger.warning("-" * 80)


class DLQRedriver:
    """Handle redrive operations for DLQ messages."""
    
    def __init__(
        self,
        dlq_url: str,
        source_queue_url: str,
        batch_size: int = 10,
        visibility_timeout: int = 30
    ):
        """
        Initialize DLQ redriver.
        
        Args:
            dlq_url: URL of the Dead Letter Queue
            source_queue_url: URL of the source queue to redrive messages to
            batch_size: Number of messages to receive in each batch (max 10)
            visibility_timeout: Visibility timeout for received messages in seconds
        """
        self.dlq_url = dlq_url
        self.source_queue_url = source_queue_url
        self.batch_size = min(batch_size, 10)  # AWS max is 10
        self.visibility_timeout = visibility_timeout
        self.sqs_client = boto3.client('sqs')
        self.stats = DLQRedriveStats()
    
    def receive_messages(self) -> List[Dict]:
        """
        Receive messages from DLQ.
        
        Returns:
            List of message dictionaries
        """
        try:
            response = self.sqs_client.receive_message(
                QueueUrl=self.dlq_url,
                MaxNumberOfMessages=self.batch_size,
                VisibilityTimeout=self.visibility_timeout,
                WaitTimeSeconds=0,  # Short polling for faster results
                AttributeNames=['All'],
                MessageAttributeNames=['All']
            )
            messages = response.get('Messages', [])
            self.stats.add_received(len(messages))
            return messages
        except ClientError as e:
            logger.error(f"Error receiving messages from DLQ: {e}")
            raise
    
    def send_message(self, message: Dict) -> bool:
        """
        Send a message to the source queue.
        
        Args:
            message: Message dictionary from DLQ
            
        Returns:
            True if send succeeded, False otherwise
        """
        try:
            # Prepare message attributes
            message_attributes = message.get('MessageAttributes', {})
            
            # Send message to source queue
            self.sqs_client.send_message(
                QueueUrl=self.source_queue_url,
                MessageBody=message['Body'],
                MessageAttributes=message_attributes
            )
            self.stats.add_sent()
            return True
        except ClientError as e:
            error_msg = f"Error sending message: {e}"
            logger.error(error_msg)
            self.stats.add_failed(message.get('MessageId', 'unknown'), error_msg)
            return False
    
    def delete_message(self, receipt_handle: str, message_id: str) -> bool:
        """
        Delete a message from the DLQ.
        
        Args:
            receipt_handle: Receipt handle of the message
            message_id: Message ID for logging
            
        Returns:
            True if delete succeeded, False otherwise
        """
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.dlq_url,
                ReceiptHandle=receipt_handle
            )
            self.stats.add_deleted()
            return True
        except ClientError as e:
            error_msg = f"Error deleting message: {e}"
            logger.error(error_msg)
            self.stats.add_failed(message_id, error_msg)
            return False
    
    def process_message(self, message: Dict) -> bool:
        """
        Process a single message: send to source queue and delete from DLQ.
        
        Args:
            message: Message dictionary from DLQ
            
        Returns:
            True if processing succeeded, False otherwise
        """
        message_id = message.get('MessageId', 'unknown')
        receipt_handle = message.get('ReceiptHandle')
        
        logger.info(f"Processing message {message_id}")
        
        # Send to source queue
        if not self.send_message(message):
            logger.error(f"Failed to send message {message_id} to source queue")
            return False
        
        # Delete from DLQ only if send succeeded
        if not self.delete_message(receipt_handle, message_id):
            logger.error(f"Failed to delete message {message_id} from DLQ")
            return False
        
        logger.info(f"Successfully redrove message {message_id}")
        return True
    
    def get_queue_attributes(self, queue_url: str) -> Dict:
        """
        Get queue attributes to check message count.
        
        Args:
            queue_url: URL of the queue
            
        Returns:
            Dictionary of queue attributes
        """
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            return response.get('Attributes', {})
        except ClientError as e:
            logger.error(f"Error getting queue attributes: {e}")
            return {}
    
    def run(self, max_messages: Optional[int] = None, dry_run: bool = False) -> int:
        """
        Run the redrive operation.
        
        Args:
            max_messages: Maximum number of messages to process (None for all)
            dry_run: If True, only show what would happen without making changes
            
        Returns:
            Exit code (0 for success, 1 for failure)
        """
        logger.info("Starting DLQ redrive operation")
        logger.info(f"DLQ URL: {self.dlq_url}")
        logger.info(f"Source Queue URL: {self.source_queue_url}")
        logger.info(f"Batch Size: {self.batch_size}")
        logger.info(f"Max Messages: {max_messages if max_messages else 'All'}")
        logger.info(f"Dry Run: {dry_run}")
        
        # Check DLQ message count
        dlq_attrs = self.get_queue_attributes(self.dlq_url)
        approx_messages = int(dlq_attrs.get('ApproximateNumberOfMessages', 0))
        logger.info(f"Approximate messages in DLQ: {approx_messages}")
        
        if approx_messages == 0:
            logger.info("DLQ is empty. Nothing to redrive.")
            return 0
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        messages_processed = 0
        
        try:
            while True:
                # Check if we've hit max_messages limit
                if max_messages and messages_processed >= max_messages:
                    logger.info(f"Reached max_messages limit of {max_messages}")
                    break
                
                # Receive batch of messages
                messages = self.receive_messages()
                
                if not messages:
                    logger.info("No more messages in DLQ")
                    break
                
                logger.info(f"Received batch of {len(messages)} messages")
                
                # Process each message
                for message in messages:
                    message_id = message.get('MessageId', 'unknown')
                    
                    if dry_run:
                        logger.info(f"[DRY RUN] Would redrive message {message_id}")
                        self.stats.add_sent()
                        self.stats.add_deleted()
                    else:
                        self.process_message(message)
                    
                    messages_processed += 1
                    
                    # Check if we've hit max_messages limit
                    if max_messages and messages_processed >= max_messages:
                        logger.info(f"Reached max_messages limit of {max_messages}")
                        break
                
                # Brief pause between batches to avoid throttling
                if not dry_run:
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            logger.warning("Operation interrupted by user")
            self.stats.print_summary()
            return 1
        except Exception as e:
            logger.error(f"Unexpected error during redrive operation: {e}")
            self.stats.print_summary()
            return 1
        
        # Print final statistics
        self.stats.print_summary()
        
        if self.stats.total_failed > 0:
            logger.error("Some messages failed to redrive")
            return 1
        
        logger.info("Redrive operation completed successfully")
        return 0


def confirm_operation(dlq_url: str, source_queue_url: str) -> bool:
    """
    Prompt user to confirm the redrive operation.
    
    Args:
        dlq_url: URL of the Dead Letter Queue
        source_queue_url: URL of the source queue
        
    Returns:
        True if user confirms, False otherwise
    """
    print("\n" + "=" * 80)
    print("CONFIRMATION REQUIRED")
    print("=" * 80)
    print(f"DLQ URL: {dlq_url}")
    print(f"Source Queue URL: {source_queue_url}")
    print("\nThis operation will:")
    print("1. Receive messages from the DLQ")
    print("2. Send them to the source queue")
    print("3. Delete them from the DLQ")
    print("\nAre you sure you want to proceed?")
    print("=" * 80)
    
    response = input("Type 'yes' to continue: ").strip().lower()
    return response == 'yes'


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Redrive messages from DLQ to source queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--dlq-url',
        required=True,
        help='URL of the Dead Letter Queue'
    )
    
    parser.add_argument(
        '--source-queue-url',
        required=True,
        help='URL of the source queue to redrive messages to'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of messages to receive in each batch (default: 10, max: 10)'
    )
    
    parser.add_argument(
        '--max-messages',
        type=int,
        default=None,
        help='Maximum number of messages to process (default: all)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would happen without making changes'
    )
    
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    parser.add_argument(
        '--visibility-timeout',
        type=int,
        default=30,
        help='Visibility timeout for received messages in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Set log level
    logger.setLevel(getattr(logging, args.log_level))
    
    # Validate batch size
    if args.batch_size < 1 or args.batch_size > 10:
        logger.error("batch-size must be between 1 and 10")
        return 1
    
    # Validate max_messages
    if args.max_messages is not None and args.max_messages < 1:
        logger.error("max-messages must be greater than 0")
        return 1
    
    # Confirm operation unless --yes or --dry-run
    if not args.dry_run and not args.yes:
        if not confirm_operation(args.dlq_url, args.source_queue_url):
            logger.info("Operation cancelled by user")
            return 0
    
    # Create redriver and execute
    try:
        redriver = DLQRedriver(
            dlq_url=args.dlq_url,
            source_queue_url=args.source_queue_url,
            batch_size=args.batch_size,
            visibility_timeout=args.visibility_timeout
        )
        
        return redriver.run(
            max_messages=args.max_messages,
            dry_run=args.dry_run
        )
    
    except BotoCoreError as e:
        logger.error(f"AWS SDK error: {e}")
        return 1
    except ClientError as e:
        logger.error(f"AWS API error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())