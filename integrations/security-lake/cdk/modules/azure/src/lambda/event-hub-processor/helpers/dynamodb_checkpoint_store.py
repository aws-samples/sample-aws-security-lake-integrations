"""
DynamoDB Checkpoint Store for Azure Event Hub
Implementation of Azure CheckpointStore interface using DynamoDB as backend storage.

Optimized for efficient Query operations with proper DynamoDB design patterns.
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Iterable, Union
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError


class DynamoDBCheckpointStore:
    """
    DynamoDB-backed implementation of Azure EventHub CheckpointStore interface.
    
    This class provides persistent storage for partition ownership and checkpoint data
    using DynamoDB as the backend, enabling Event Hub processing to resume from the
    last processed position across Lambda function invocations.
    
    Table Design:
    - Primary Key: pk (Partition Key) + sk (Sort Key)
    - pk format: "eventhub#{namespace}#{eventhub_name}#{consumer_group}"
    - sk format: "ownership#{partition_id}" or "checkpoint#{partition_id}"
    - GSI1: type (ownership/checkpoint) for global queries
    """
    
    def __init__(self, table_name: str, region_name: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize DynamoDB checkpoint store
        
        Args:
            table_name: DynamoDB table name for storing checkpoint and ownership data
            region_name: AWS region name (uses default if not provided)
            logger: Logger instance for debug/info logging
        """
        self.table_name = table_name
        self.logger = logger or logging.getLogger(__name__)
        
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
            self.table = self.dynamodb.Table(table_name)
            self.logger.info(f"DynamoDB checkpoint store initialized for table: {table_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize DynamoDB checkpoint store: {str(e)}")
            raise

    def _create_partition_key(self, fully_qualified_namespace: str, eventhub_name: str, consumer_group: str) -> str:
        """Create primary partition key for eventhub context"""
        return f"eventhub#{fully_qualified_namespace}#{eventhub_name}#{consumer_group}"

    def _create_ownership_sort_key(self, partition_id: str) -> str:
        """Create sort key for ownership records"""
        return f"ownership#{partition_id}"
    
    def _create_checkpoint_sort_key(self, partition_id: str) -> str:
        """Create sort key for checkpoint records"""
        return f"checkpoint#{partition_id}"

    def list_ownership(
        self, 
        fully_qualified_namespace: str, 
        eventhub_name: str, 
        consumer_group: str, 
        **kwargs: Any
    ) -> Iterable[Dict[str, Any]]:
        """
        Retrieves a complete ownership list from DynamoDB storage.

        Args:
            fully_qualified_namespace: Event Hub namespace (e.g., "namespace.servicebus.windows.net")
            eventhub_name: Name of the Event Hub
            consumer_group: Consumer group name
            **kwargs: Additional arguments (ignored for DynamoDB implementation)

        Returns:
            Iterable of dictionaries containing partition ownership information
        """
        try:
            pk = self._create_partition_key(fully_qualified_namespace, eventhub_name, consumer_group)
            
            # Query for all ownership records for this EventHub
            response = self.table.query(
                KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('ownership#')
            )
            
            ownerships = []
            for item in response.get('Items', []):
                # Extract partition_id from sort key
                partition_id = item['sk'].replace('ownership#', '')
                
                # Convert ISO timestamp back to Unix timestamp for Azure SDK compatibility
                iso_time = item.get('last_modified_time', datetime.now(timezone.utc).isoformat())
                if isinstance(iso_time, str):
                    dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
                    timestamp = dt.timestamp()
                else:
                    timestamp = datetime.now(timezone.utc).timestamp()
                
                ownership = {
                    'fully_qualified_namespace': fully_qualified_namespace,
                    'eventhub_name': eventhub_name,
                    'consumer_group': consumer_group,
                    'partition_id': partition_id,
                    'owner_id': item.get('owner_id', ''),
                    'last_modified_time': timestamp,  # Unix timestamp for Azure SDK compatibility
                    'etag': item.get('etag', '')
                }
                ownerships.append(ownership)
            
            self.logger.info(f"Retrieved {len(ownerships)} ownership records for {eventhub_name}")
            return ownerships
            
        except ClientError as e:
            self.logger.error(f"Failed to list ownership from DynamoDB: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error listing ownership: {str(e)}")
            return []

    def claim_ownership(
        self, 
        ownership_list: Iterable[Dict[str, Any]], 
        **kwargs: Any
    ) -> Iterable[Dict[str, Any]]:
        """
        Tries to claim ownership for a list of specified partitions.

        Args:
            ownership_list: List of ownership dictionaries to claim
            **kwargs: Additional arguments (ignored for DynamoDB implementation)

        Returns:
            List of successfully claimed ownership dictionaries
        """
        claimed_ownerships = []
        
        for ownership in ownership_list:
            try:
                fully_qualified_namespace = ownership['fully_qualified_namespace']
                eventhub_name = ownership['eventhub_name']
                consumer_group = ownership['consumer_group']
                partition_id = ownership['partition_id']
                owner_id = ownership['owner_id']
                
                # Create keys
                pk = self._create_partition_key(fully_qualified_namespace, eventhub_name, consumer_group)
                sk = self._create_ownership_sort_key(partition_id)
                
                # Generate new etag and timestamp
                current_time = datetime.now(timezone.utc)
                new_etag = str(uuid.uuid4())
                ttl_timestamp = int(time.time()) + (7 * 24 * 60 * 60)  # 7 days TTL
                
                ownership_data = {
                    'pk': pk,
                    'sk': sk,
                    'type': 'ownership',
                    'owner_id': owner_id,
                    'last_modified_time': current_time.isoformat(),
                    'etag': new_etag,
                    'fully_qualified_namespace': fully_qualified_namespace,
                    'eventhub_name': eventhub_name,
                    'consumer_group': consumer_group,
                    'partition_id': partition_id,
                    'ttl': ttl_timestamp
                }
                
                # Use conditional write to ensure atomic ownership claims
                condition_expression = None
                if 'etag' in ownership and ownership['etag']:
                    # Ownership transfer - must match existing etag
                    condition_expression = Attr('etag').eq(ownership['etag'])
                else:
                    # New ownership claim - record must not exist
                    condition_expression = Attr('pk').not_exists()
                
                self.table.put_item(
                    Item=ownership_data,
                    ConditionExpression=condition_expression
                )
                
                # Return claimed ownership with updated values (Unix timestamp for Azure SDK)
                claimed_ownership = {
                    'fully_qualified_namespace': fully_qualified_namespace,
                    'eventhub_name': eventhub_name,
                    'consumer_group': consumer_group,
                    'partition_id': partition_id,
                    'owner_id': owner_id,
                    'last_modified_time': current_time.timestamp(),  # Unix timestamp for Azure SDK compatibility
                    'etag': new_etag
                }
                
                claimed_ownerships.append(claimed_ownership)
                
                self.logger.info(f"Successfully claimed ownership for partition {partition_id} by owner {owner_id}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    self.logger.warning(f"Failed to claim ownership for partition {partition_id} - already owned or etag mismatch")
                else:
                    self.logger.error(f"Failed to claim ownership for partition {partition_id}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error claiming ownership for partition {partition_id}: {str(e)}")
        
        return claimed_ownerships

    def update_checkpoint(
        self, 
        checkpoint: Dict[str, Optional[Union[str, int]]], 
        **kwargs: Any
    ) -> None:
        """
        Updates the checkpoint using the given information for the offset, associated partition 
        and consumer group in DynamoDB storage.

        Args:
            checkpoint: Dictionary containing checkpoint information:
                - fully_qualified_namespace (str): Event Hub namespace
                - eventhub_name (str): Event Hub name  
                - consumer_group (str): Consumer group name
                - partition_id (str): Partition ID
                - sequence_number (int): Sequence number of the EventData
                - offset (str): Offset of the EventData
            **kwargs: Additional arguments (ignored for DynamoDB implementation)
        """
        try:
            fully_qualified_namespace = str(checkpoint['fully_qualified_namespace'])
            eventhub_name = str(checkpoint['eventhub_name'])
            consumer_group = str(checkpoint['consumer_group'])
            partition_id = str(checkpoint['partition_id'])
            sequence_number = checkpoint.get('sequence_number')
            offset = checkpoint.get('offset')
            
            # Create keys
            pk = self._create_partition_key(fully_qualified_namespace, eventhub_name, consumer_group)
            sk = self._create_checkpoint_sort_key(partition_id)
            
            current_time = datetime.now(timezone.utc)
            ttl_timestamp = int(time.time()) + (7 * 24 * 60 * 60)  # 7 days TTL
            
            checkpoint_data = {
                'pk': pk,
                'sk': sk,
                'type': 'checkpoint',
                'fully_qualified_namespace': fully_qualified_namespace,
                'eventhub_name': eventhub_name,
                'consumer_group': consumer_group,
                'partition_id': partition_id,
                'sequence_number': int(sequence_number) if sequence_number is not None else None,
                'offset': str(offset) if offset is not None else None,
                'last_updated': current_time.isoformat(),
                'ttl': ttl_timestamp
            }
            
            # Remove None values to avoid DynamoDB errors
            checkpoint_data = {k: v for k, v in checkpoint_data.items() if v is not None}
            
            self.table.put_item(Item=checkpoint_data)
            
            self.logger.info(
                f"Updated checkpoint for partition {partition_id}: sequence={sequence_number}, offset={offset}"
            )
            
        except ClientError as e:
            self.logger.error(f"Failed to update checkpoint in DynamoDB: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error updating checkpoint: {str(e)}")
            raise

    def list_checkpoints(
        self, 
        fully_qualified_namespace: str, 
        eventhub_name: str, 
        consumer_group: str, 
        **kwargs: Any
    ) -> Iterable[Dict[str, Any]]:
        """
        List the updated checkpoints from DynamoDB storage.

        Args:
            fully_qualified_namespace: Event Hub namespace
            eventhub_name: Event Hub name
            consumer_group: Consumer group name
            **kwargs: Additional arguments (ignored for DynamoDB implementation)

        Returns:
            Iterable of dictionaries containing partition checkpoint information
        """
        try:
            pk = self._create_partition_key(fully_qualified_namespace, eventhub_name, consumer_group)
            
            # Query for all checkpoint records for this EventHub
            response = self.table.query(
                KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('checkpoint#')
            )
            
            checkpoints = []
            for item in response.get('Items', []):
                # Extract partition_id from sort key
                partition_id = item['sk'].replace('checkpoint#', '')
                
                checkpoint = {
                    'fully_qualified_namespace': fully_qualified_namespace,
                    'eventhub_name': eventhub_name,
                    'consumer_group': consumer_group,
                    'partition_id': partition_id,
                    'sequence_number': item.get('sequence_number'),
                    'offset': item.get('offset')
                }
                
                # Only include checkpoint if it has valid data
                if checkpoint['sequence_number'] is not None or checkpoint['offset'] is not None:
                    checkpoints.append(checkpoint)
            
            self.logger.info(f"Retrieved {len(checkpoints)} checkpoint records for {eventhub_name}")
            return checkpoints
            
        except ClientError as e:
            self.logger.error(f"Failed to list checkpoints from DynamoDB: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error listing checkpoints: {str(e)}")
            return []

    def get_checkpoint_for_partition(
        self, 
        fully_qualified_namespace: str, 
        eventhub_name: str, 
        consumer_group: str, 
        partition_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Convenience method to get checkpoint for a specific partition.
        
        Args:
            fully_qualified_namespace: Event Hub namespace
            eventhub_name: Event Hub name
            consumer_group: Consumer group name
            partition_id: Partition ID
            
        Returns:
            Checkpoint dictionary or None if not found
        """
        try:
            pk = self._create_partition_key(fully_qualified_namespace, eventhub_name, consumer_group)
            sk = self._create_checkpoint_sort_key(partition_id)
            
            response = self.table.get_item(Key={'pk': pk, 'sk': sk})
            item = response.get('Item')
            
            if item and item.get('type') == 'checkpoint':
                return {
                    'fully_qualified_namespace': fully_qualified_namespace,
                    'eventhub_name': eventhub_name,
                    'consumer_group': consumer_group,
                    'partition_id': partition_id,
                    'sequence_number': item.get('sequence_number'),
                    'offset': item.get('offset')
                }
            
            return None
            
        except ClientError as e:
            self.logger.error(f"Failed to get checkpoint for partition {partition_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting checkpoint for partition {partition_id}: {str(e)}")
            return None

    def cleanup_expired_records(self, days_old: int = 7) -> int:
        """
        Cleanup utility to remove old ownership and checkpoint records.
        Note: DynamoDB TTL should handle most cleanup automatically.
        
        Args:
            days_old: Remove records older than this many days
            
        Returns:
            Number of records deleted
        """
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - (days_old * 24 * 60 * 60)
            
            # Scan for old records (use sparingly due to cost)
            response = self.table.scan(
                FilterExpression=Attr('ttl').lt(int(cutoff_time))
            )
            
            deleted_count = 0
            for item in response.get('Items', []):
                try:
                    self.table.delete_item(Key={'pk': item['pk'], 'sk': item['sk']})
                    deleted_count += 1
                except ClientError as e:
                    self.logger.warning(f"Failed to delete expired record {item['pk']}#{item['sk']}: {e}")
            
            self.logger.info(f"Cleaned up {deleted_count} expired records")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            return 0

    def get_table_info(self) -> Dict[str, Any]:
        """
        Get information about the required DynamoDB table structure
        
        Returns:
            Dictionary with table schema information
        """
        return {
            'table_name': self.table_name,
            'primary_key': {
                'partition_key': {
                    'name': 'pk',
                    'type': 'S'  # String
                },
                'sort_key': {
                    'name': 'sk', 
                    'type': 'S'  # String
                }
            },
            'global_secondary_indexes': [
                {
                    'name': 'TypeIndex',
                    'partition_key': {
                        'name': 'type',
                        'type': 'S'
                    },
                    'sort_key': {
                        'name': 'last_modified_time',
                        'type': 'S'
                    }
                }
            ],
            'ttl_attribute': 'ttl',
            'sample_records': {
                'ownership': {
                    'pk': 'eventhub#namespace.servicebus.windows.net#my-eventhub#$Default',
                    'sk': 'ownership#0',
                    'type': 'ownership',
                    'owner_id': 'uuid-processor-id',
                    'etag': 'uuid-etag',
                    'last_modified_time': '2023-12-01T10:00:00Z',
                    'ttl': 1234567890
                },
                'checkpoint': {
                    'pk': 'eventhub#namespace.servicebus.windows.net#my-eventhub#$Default',
                    'sk': 'checkpoint#0',
                    'type': 'checkpoint',
                    'sequence_number': 12345,
                    'offset': '67890',
                    'last_updated': '2023-12-01T10:00:00Z',
                    'ttl': 1234567890
                }
            }
        }