"""
DynamoDB Cursor Client for managing Pub/Sub processing position
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError


class DynamoDBCursorClient:
    """
    DynamoDB client for managing Pub/Sub cursor operations
    """
    
    def __init__(self, table_name: str, region_name: str = None, logger: logging.Logger = None):
        """
        Initialize DynamoDB cursor client
        
        Args:
            table_name: DynamoDB table name
            region_name: AWS region name
            logger: Logger instance
        """
        self.table_name = table_name
        self.logger = logger or logging.getLogger(__name__)
        
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
            self.table = self.dynamodb.Table(table_name)
            self.logger.info(f"DynamoDB cursor client initialized for table: {table_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize DynamoDB cursor client: {str(e)}")
            raise
    
    def get_cursor(self, cursor_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cursor data from DynamoDB
        
        Args:
            cursor_id: Unique identifier for the cursor
            
        Returns:
            Cursor data dictionary or None if not found
        """
        try:
            response = self.table.get_item(
                Key={'id': cursor_id}
            )
            
            cursor_data = response.get('Item')
            
            if cursor_data:
                self.logger.info(
                    f"Retrieved cursor data",
                    extra={
                        'cursor_id': cursor_id,
                        'last_updated': cursor_data.get('last_updated'),
                        'messages_processed_total': cursor_data.get('messages_processed_total', 0)
                    }
                )
            else:
                self.logger.info(f"No cursor data found for ID: {cursor_id}")
            
            return cursor_data
            
        except ClientError as e:
            self.logger.error(
                f"Failed to get cursor from DynamoDB",
                extra={
                    'cursor_id': cursor_id,
                    'table_name': self.table_name,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error getting cursor: {str(e)}")
            raise
    
    def save_cursor(
        self,
        cursor_id: str,
        cursor_value: str,
        messages_processed_batch: int = 0,
        last_batch_size: int = 0,
        processing_time_ms: int = 0
    ) -> Dict[str, Any]:
        """
        Save or update cursor data in DynamoDB
        
        Args:
            cursor_id: Unique identifier for the cursor
            cursor_value: Current cursor position/offset (e.g., publish timestamp)
            messages_processed_batch: Number of messages processed in this batch
            last_batch_size: Size of the last batch processed
            processing_time_ms: Time taken to process the batch in milliseconds
            
        Returns:
            Response from DynamoDB put_item
        """
        try:
            current_timestamp = datetime.now(timezone.utc).isoformat()
            ttl_timestamp = int(time.time()) + (7 * 24 * 60 * 60)  # 7 days from now
            
            # Get existing data to update totals
            existing_cursor = self.get_cursor(cursor_id)
            existing_total = existing_cursor.get('messages_processed_total', 0) if existing_cursor else 0
            
            cursor_data = {
                'id': cursor_id,
                'cursor_value': cursor_value,
                'last_updated': current_timestamp,
                'messages_processed_total': existing_total + messages_processed_batch,
                'messages_processed_batch': messages_processed_batch,
                'last_batch_size': last_batch_size,
                'processing_time_ms': processing_time_ms,
                'expiry': ttl_timestamp  # TTL attribute
            }
            
            response = self.table.put_item(Item=cursor_data)
            
            self.logger.info(
                f"Cursor data saved successfully",
                extra={
                    'cursor_id': cursor_id,
                    'cursor_value': cursor_value,
                    'messages_processed_batch': messages_processed_batch,
                    'messages_processed_total': cursor_data['messages_processed_total'],
                    'processing_time_ms': processing_time_ms
                }
            )
            
            return response
            
        except ClientError as e:
            self.logger.error(
                f"Failed to save cursor to DynamoDB",
                extra={
                    'cursor_id': cursor_id,
                    'table_name': self.table_name,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error saving cursor: {str(e)}")
            raise
    
    def delete_cursor(self, cursor_id: str) -> Dict[str, Any]:
        """
        Delete cursor data from DynamoDB
        
        Args:
            cursor_id: Unique identifier for the cursor
            
        Returns:
            Response from DynamoDB delete_item
        """
        try:
            response = self.table.delete_item(
                Key={'id': cursor_id}
            )
            
            self.logger.info(f"Cursor deleted successfully: {cursor_id}")
            
            return response
            
        except ClientError as e:
            self.logger.error(
                f"Failed to delete cursor from DynamoDB",
                extra={
                    'cursor_id': cursor_id,
                    'table_name': self.table_name,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error deleting cursor: {str(e)}")
            raise
    
    def get_cursor_value(self, cursor_id: str) -> Optional[str]:
        """
        Get just the cursor value (convenience method)
        
        Args:
            cursor_id: Unique identifier for the cursor
            
        Returns:
            Cursor value string or None if not found
        """
        cursor_data = self.get_cursor(cursor_id)
        return cursor_data.get('cursor_value') if cursor_data else None
    
    def update_processing_stats(
        self,
        cursor_id: str,
        processing_time_ms: int,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update processing statistics without changing cursor position
        
        Args:
            cursor_id: Unique identifier for the cursor
            processing_time_ms: Time taken to process
            success: Whether processing was successful
            error_message: Error message if processing failed
        """
        try:
            current_timestamp = datetime.now(timezone.utc).isoformat()
            
            update_expression = "SET last_updated = :timestamp, processing_time_ms = :time"
            expression_values = {
                ':timestamp': current_timestamp,
                ':time': processing_time_ms
            }
            
            if not success and error_message:
                update_expression += ", last_error = :error"
                expression_values[':error'] = error_message
            
            self.table.update_item(
                Key={'id': cursor_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            self.logger.info(
                f"Processing stats updated",
                extra={
                    'cursor_id': cursor_id,
                    'processing_time_ms': processing_time_ms,
                    'success': success
                }
            )
            
        except ClientError as e:
            self.logger.warning(
                f"Failed to update processing stats",
                extra={
                    'cursor_id': cursor_id,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            # Don't re-raise, as this is a non-critical operation
        except Exception as e:
            self.logger.warning(f"Unexpected error updating processing stats: {str(e)}")
            # Don't re-raise, as this is a non-critical operation
    
    def list_all_cursors(self) -> List[Dict[str, Any]]:
        """
        List all cursors in the table (for debugging/monitoring)
        
        Returns:
            List of all cursor records
        """
        try:
            response = self.table.scan()
            cursors = response.get('Items', [])
            
            self.logger.info(f"Retrieved {len(cursors)} cursor records from table")
            
            return cursors
            
        except ClientError as e:
            self.logger.error(
                f"Failed to list cursors from DynamoDB",
                extra={
                    'table_name': self.table_name,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error listing cursors: {str(e)}")
            raise