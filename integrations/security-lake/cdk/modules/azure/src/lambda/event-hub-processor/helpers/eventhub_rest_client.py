"""
Azure Event Hub REST API Client for AWS Lambda
Uses direct HTTP calls to Azure Event Hubs REST API for Lambda-compatible operation.
"""

import json
import logging
import hmac
import hashlib
import base64
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

class EventHubRestClient:
    """Azure Event Hub client using REST API for Lambda compatibility."""
    
    def __init__(self, connection_string: str, eventhub_name: str, consumer_group: str = '$Default'):
        """
        Initialize Event Hub REST client
        
        Args:
            connection_string: Azure Event Hub connection string
            eventhub_name: Name of the Event Hub
            consumer_group: Consumer group name (defaults to $Default)
        """
        self.eventhub_name = eventhub_name
        self.consumer_group = consumer_group
        
        # Parse connection string
        self._parse_connection_string(connection_string)
        
        logger.info("EventHubRestClient initialized", extra={
            'eventhub_name': eventhub_name,
            'consumer_group': consumer_group,
            'namespace': self.namespace
        })
    
    def _parse_connection_string(self, connection_string: str):
        """Parse Azure Event Hub connection string"""
        parts = dict(part.split('=', 1) for part in connection_string.split(';') if '=' in part)
        
        endpoint = parts.get('Endpoint', '').replace('sb://', '').replace('/', '')
        self.namespace = endpoint
        self.shared_access_key_name = parts.get('SharedAccessKeyName', '')
        self.shared_access_key = parts.get('SharedAccessKey', '')
        
        # Get entity path if present in connection string
        entity_path = parts.get('EntityPath')
        if entity_path and not self.eventhub_name:
            self.eventhub_name = entity_path
        
        logger.debug(f"Parsed connection string: namespace={self.namespace}")
    
    def _generate_sas_token(self, uri: str, ttl: int = 3600) -> str:
        """Generate SAS token for authorization"""
        expiry = int(time.time() + ttl)
        string_to_sign = f"{quote(uri, safe='')}\n{expiry}"
        
        signed_hmac_sha256 = hmac.new(
            self.shared_access_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        )
        signature = quote(base64.b64encode(signed_hmac_sha256.digest()))
        
        return f"SharedAccessSignature sr={quote(uri, safe='')}&sig={signature}&se={expiry}&skn={self.shared_access_key_name}"
    
    def receive_events(self, max_events: int = 100, max_wait_time: int = 30, starting_sequence_number: Optional[str] = None, partition_id: str = '0') -> Dict[str, Any]:
        """
        Receive events from Event Hub using REST API
        
        Args:
            max_events: Maximum number of events to receive
            max_wait_time: Maximum time to wait (not used in REST API, included for compatibility)
            starting_sequence_number: Sequence number to start from
            partition_id: Partition to read from
            
        Returns:
            Dictionary with 'events' and metadata
        """
        events = []
        
        try:
            # Build REST API URL
            # GET https://{namespace}/{ eventhub}/consumergroups/{consumer-group}/partitions/{partition-id}/messages/head?timeout={seconds}
            base_url = f"https://{self.namespace}/{self.eventhub_name}/consumergroups/{self.consumer_group}/partitions/{partition_id}/messages/head"
            
            # Add query parameters
            params = []
            params.append(f"timeout={min(max_wait_time, 60)}")  # Max 60s for REST API
            
            if starting_sequence_number:
                # Use sequence number filter if provided
                params.append(f"$filter=SequenceNumber gt {starting_sequence_number}")
            
            url = f"{base_url}?{'&'.join(params)}"
            
            # Generate SAS token
            resource_uri = f"https://{self.namespace}/{self.eventhub_name}"
            sas_token = self._generate_sas_token(resource_uri)
            
            logger.info(f"Making REST API call to partition {partition_id}", extra={
                'partition_id': partition_id,
                'starting_sequence': starting_sequence_number,
                'max_events': max_events
            })
            
            # Make HTTP request
            request = urllib.request.Request(url)
            request.add_header('Authorization', sas_token)
            request.add_header('Content-Type', 'application/atom+xml;type=entry;charset=utf-8')
            
            try:
                with urllib.request.urlopen(request, timeout=max_wait_time) as response:
                    # Read response
                    response_data = response.read().decode('utf-8')
                    
                    # Parse response (Event Hubs returns JSON array of events)
                    if response_data:
                        event_list = json.loads(response_data) if response_data.strip() else []
                        
                        for event_data in event_list[:max_events]:
                            processed_event = self._process_event_data(event_data)
                            if processed_event:
                                events.append(processed_event)
                        
                        logger.info(f"Received {len(events)} events from REST API")
                    else:
                        logger.info("No events available in partition")
                        
            except urllib.error.HTTPError as e:
                if e.code == 204:  # No Content - no messages available
                    logger.info(f"Partition {partition_id}: No messages available (HTTP 204)")
                else:
                    logger.error(f"HTTP error receiving events: {e.code} - {e.reason}")
                    
        except Exception as e:
            logger.error(f"Error in REST API receive: {str(e)}")
        
        return {
            "events": events,
            "last_sequence_number": events[-1].get('event_metadata', {}).get('sequence_number') if events else None,
            "events_count": len(events)
        }
    
    def _process_event_data(self, event_data: Any) -> Optional[Dict[str, Any]]:
        """Process event data from REST API response"""
        try:
            # REST API returns events in different format than SDK
            # Extract body and metadata
            body = event_data.get('Body') or event_data.get('body', '')
            
            # Parse JSON body if possible
            try:
                if isinstance(body, str) and body.strip() and body.strip()[0] in '{[':
                    event_json = json.loads(body)
                else:
                    event_json = {'raw_data': body}
            except (json.JSONDecodeError, IndexError):
                event_json = {'raw_data': body}
            
            # Extract metadata
            processed_event = {
                'event_data': event_json,
                'event_metadata': {
                    'sequence_number': event_data.get('SequenceNumber') or event_data.get('sequenceNumber'),
                    'offset': str(event_data.get('Offset') or event_data.get('offset', '')),
                    'enqueued_time': event_data.get('EnqueuedTimeUtc') or event_data.get('enqueuedTimeUtc'),
                    'partition_id': event_data.get('PartitionId') or event_data.get('partitionId'),
                    'partition_key': event_data.get('PartitionKey') or event_data.get('partitionKey'),
                    'properties': event_data.get('Properties') or event_data.get('properties', {}),
                    'system_properties': event_data.get('SystemProperties') or event_data.get('systemProperties', {})
                },
                'processing_metadata': {
                    'processed_timestamp': datetime.now(timezone.utc).isoformat(),
                    'processor_version': '6.0.0-rest',
                    'source': 'azure-eventhub-rest',
                    'eventhub_name': self.eventhub_name,
                    'consumer_group': self.consumer_group
                }
            }
            
            return processed_event
            
        except Exception as e:
            logger.error(f"Error processing REST event data: {str(e)}")
            return None
    
    def close(self):
        """Close the client (no-op for REST API)"""
        logger.debug("EventHubRestClient closed")