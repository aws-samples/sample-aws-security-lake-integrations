"""
Azure Event Hub Client for AWS Lambda
Receives events using receive_batch with checkpoint management for Lambda compatibility.
"""

import json
import logging
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from helpers.dynamodb_checkpoint_store import DynamoDBCheckpointStore
from azure.eventhub import EventHubConsumerClient, EventData

logger = logging.getLogger(__name__)

# Suppress verbose Azure SDK logging
logging.getLogger('azure.eventhub').setLevel(logging.WARNING)
logging.getLogger('azure.eventhub._pyamqp').setLevel(logging.WARNING)
logging.getLogger('azure.eventhub._eventprocessor').setLevel(logging.WARNING)

class EventHubClient:
    """Azure Event Hub client for consuming Microsoft Defender events in AWS Lambda."""
    
    def __init__(self, connection_string: str, eventhub_name: str, consumer_group: str = '$Default', checkpoint_store: Optional[DynamoDBCheckpointStore] = None):
        """
        Initialize Event Hub consumer client
        
        Args:
            connection_string: Azure Event Hub connection string
            eventhub_name: Name of the Event Hub
            consumer_group: Consumer group name (defaults to $Default)
            checkpoint_store: Optional checkpoint store for position management
        """
        self.connection_string = connection_string
        self.eventhub_name = eventhub_name
        self.consumer_group = consumer_group
        self.checkpoint_store = checkpoint_store
        
        # Parse namespace from connection string
        self.namespace = self._parse_namespace_from_connection_string(connection_string)
        
        # Event collection
        self.events = []
        self.last_sequence_number = None
        self.events_lock = threading.Lock()
        
        logger.info(f"EventHub client initialized: {eventhub_name} on {self.namespace}")
    
    def _parse_namespace_from_connection_string(self, connection_string: str) -> str:
        """Parse the Event Hub namespace from connection string"""
        try:
            parts = dict(part.split('=', 1) for part in connection_string.split(';') if '=' in part)
            endpoint = parts.get('Endpoint', '').replace('sb://', '').replace('/', '')
            if endpoint:
                return endpoint
        except Exception as e:
            logger.warning(f"Failed to parse namespace: {e}")
        
        return f"{self.eventhub_name}.servicebus.windows.net"
    
    def receive_events(self, max_events: int = 100, max_wait_time: int = 30, starting_sequence_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Receive events from Event Hub
        
        Args:
            max_events: Maximum number of events to receive in one batch
            max_wait_time: Maximum time to wait for events (seconds)
            starting_sequence_number: Sequence number to start from (for cursor management)
            
        Returns:
            Dictionary with 'events' and 'last_sequence_number' for cursor management
        """
        # Reset state
        self.events = []
        self.last_sequence_number = starting_sequence_number
        
        # Determine if we should use checkpoint store or explicit starting position
        use_checkpoint_store = self.checkpoint_store is not None and starting_sequence_number is None
        
        logger.info(f"Receiving from {self.eventhub_name} (mode: {'checkpoint' if use_checkpoint_store else 'cursor'})")
        
        try:
            # Always use manual checkpoint management (don't pass checkpoint_store to Azure SDK)
            # This avoids EventProcessor lifecycle conflicts in Lambda
            return self._receive_with_manual_checkpoints(max_events, max_wait_time, starting_sequence_number)
                
        except Exception as e:
            logger.error(f"Error receiving events from Event Hub: {str(e)}")
            return {
                "events": [],
                "last_sequence_number": self.last_sequence_number,
                "events_count": 0
            }
    
    def _receive_with_manual_checkpoints(self, max_events: int, max_wait_time: int, starting_sequence_number: Optional[str]) -> Dict[str, Any]:
        """Receive events with checkpoint management"""
        namespace = self.namespace
        starting_position = "-1"
        
        if self.checkpoint_store and starting_sequence_number is None:
            checkpoints = list(self.checkpoint_store.list_checkpoints(
                namespace,
                self.eventhub_name,
                self.consumer_group
            ))
            
            if checkpoints:
                for checkpoint in checkpoints:
                    if checkpoint['partition_id'] == '0':
                        seq_num = checkpoint.get('sequence_number')
                        if seq_num is not None and seq_num > 100:
                            starting_position = f"@{int(seq_num)}"
                            logger.info(f"Resuming from checkpoint seq={seq_num}")
                        elif seq_num is not None:
                            logger.warning(f"Stale checkpoint seq={seq_num}, starting from earliest")
                        break
            else:
                logger.info("No checkpoints found, starting from earliest")
        elif starting_sequence_number:
            starting_position = f"@{starting_sequence_number}"
        
        consumer = EventHubConsumerClient.from_connection_string(
            conn_str=self.connection_string,
            consumer_group=self.consumer_group,
            eventhub_name=self.eventhub_name,
            checkpoint_store=self.checkpoint_store
        )
        
        batch_received = [False]
        
        def on_event_batch(partition_context, event_batch):
            """Process batch and update checkpoint"""
            try:
                batch_size = len(event_batch)
                partition_id = partition_context.partition_id if hasattr(partition_context, 'partition_id') else '0'
                
                if batch_size > 0:
                    logger.info(f"Received {batch_size} events from partition {partition_id}")
                
                for event in event_batch:
                    if event is None:
                        continue
                    
                    event_dict = self._process_event_data(event)
                    if event_dict:
                        with self.events_lock:
                            self.events.append(event_dict)
                            if hasattr(event, 'sequence_number'):
                                self.last_sequence_number = str(event.sequence_number)
                
                if batch_size > 0:
                    partition_context.update_checkpoint(event_batch[-1])
                
                batch_received[0] = True
                
            except Exception as e:
                logger.error(f"Batch processing error: {str(e)}")
                batch_received[0] = True
        
        try:
            # Get partition information
            props = consumer.get_eventhub_properties()
            partition_ids = props['partition_ids']
            logger.info(f"Found {len(partition_ids)} partitions: {partition_ids}")
            
            # receive_batch blocks forever - must run in thread and forcibly close after first batch
            logger.info(f"Starting receive_batch in thread for ALL partitions")
            
            import threading
            
            def receive_wrapper():
                try:
                    logger.info("THREAD: Starting receive_batch")
                    consumer.receive_batch(
                        on_event_batch=on_event_batch,
                        # NO partition_id - SDK handles all partitions
                        starting_position=starting_position,
                        max_batch_size=100,
                        max_wait_time=max_wait_time
                    )
                    logger.info("THREAD: receive_batch returned (unexpected)")
                except Exception as e:
                    logger.error(f"THREAD ERROR: {e}")
            
            worker = threading.Thread(target=receive_wrapper)
            worker.daemon = True
            worker.start()
            
            # Wait for first batch, then close consumer to force exit
            check_interval = 0.5
            max_iterations = int(max_wait_time / check_interval) + 10
            
            for i in range(max_iterations):
                if batch_received[0]:
                    logger.info(f"Batch received, closing consumer to stop receive_batch")
                    consumer.close()
                    worker.join(timeout=3.0)
                    break
                time.sleep(check_interval)
            else:
                # Timeout reached without batch
                logger.warning(f"No batch received after {max_wait_time}s, closing consumer")
                consumer.close()
                worker.join(timeout=3.0)
            
            logger.info(f"Exited receive_batch, collected {len(self.events)} events")
            
            with self.events_lock:
                final_count = len(self.events)
            
            logger.info(f"Successfully received {final_count} events from Event Hub across all partitions")
            
        except Exception as e:
            logger.error(f"Error in manual checkpoint receive: {str(e)}")
            try:
                consumer.close()
            except:
                pass
        
        return {
            "events": self.events.copy(),
            "last_sequence_number": self.last_sequence_number,
            "events_count": len(self.events)
        }
    
    def _process_event_data(self, event_data: EventData) -> Optional[Dict[str, Any]]:
        """
        Process individual Event Hub event data
        
        Args:
            event_data: Azure EventData object (can be None)
            
        Returns:
            Processed event dictionary or None if processing fails
        """
        try:
            # Check for None event_data
            if event_data is None:
                logger.warning("Received None event_data for processing")
                return None
            
            # Get the event body
            try:
                if hasattr(event_data, 'body_as_str'):
                    body_str = event_data.body_as_str()
                else:
                    body_str = str(event_data.body) if event_data.body is not None else ""
            except Exception as body_error:
                logger.warning(f"Error reading event body: {str(body_error)}")
                body_str = ""
            
            # Parse JSON if possible
            try:
                if body_str.strip() and body_str.strip()[0] in '{[':
                    event_json = json.loads(body_str)
                else:
                    event_json = {'raw_data': body_str}
            except (json.JSONDecodeError, IndexError):
                event_json = {'raw_data': body_str}
            
            # Add Event Hub metadata
            processed_event = {
                'event_data': event_json,
                'event_metadata': {
                    'sequence_number': int(event_data.sequence_number) if hasattr(event_data, 'sequence_number') and event_data.sequence_number is not None else None,
                    'offset': str(event_data.offset) if hasattr(event_data, 'offset') and event_data.offset is not None else None,
                    'enqueued_time': event_data.enqueued_time.isoformat() if hasattr(event_data, 'enqueued_time') and event_data.enqueued_time else None,
                    'partition_id': str(getattr(event_data, 'partition_id', None)) if getattr(event_data, 'partition_id', None) is not None else None,
                    'partition_key': str(event_data.partition_key) if hasattr(event_data, 'partition_key') and event_data.partition_key is not None else None,
                    'properties': self._convert_to_serializable(dict(event_data.properties)) if hasattr(event_data, 'properties') and event_data.properties else {},
                    'system_properties': self._convert_to_serializable(dict(event_data.system_properties)) if hasattr(event_data, 'system_properties') and event_data.system_properties else {}
                },
                'processing_metadata': {
                    'processed_timestamp': datetime.now(timezone.utc).isoformat(),
                    'processor_version': '5.0.0',
                    'source': 'azure-eventhub',
                    'eventhub_name': self.eventhub_name,
                    'consumer_group': self.consumer_group
                }
            }
            
            return processed_event
            
        except Exception as e:
            logger.error(f"Error processing event data: {str(e)}")
            return None
    
    def _convert_to_serializable(self, obj):
        """Convert objects with bytes values to JSON-serializable format"""
        if isinstance(obj, dict):
            return {str(k): self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except UnicodeDecodeError:
                import base64
                return base64.b64encode(obj).decode('utf-8')
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            return str(obj)

    def close(self):
        """Close the Event Hub client connection"""
        logger.info("Event Hub client connection closed")