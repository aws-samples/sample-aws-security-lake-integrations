"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Flow Log Transformer

This module transforms Azure NSG Flow Logs to OCSF Network Activity (Class 4001) format.

Author: Jeremy Tirrell
Version: 1.0.0
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
import uuid

logger = logging.getLogger(__name__)


# Flow state to OCSF activity mapping
FLOW_STATE_TO_ACTIVITY = {
    'D': {'id': 5, 'name': 'Refuse'},     # Deny
    'E': {'id': 3, 'name': 'Reset'},      # End
    'C': {'id': 6, 'name': 'Traffic'},    # Continue
    'B': {'id': 1, 'name': 'Open'},       # Begin
}

# Protocol number mapping
PROTOCOL_MAP = {
    '6': {'num': 6, 'name': 'TCP'},
    '17': {'num': 17, 'name': 'UDP'},
}

# Direction mapping
DIRECTION_MAP = {
    'I': {'id': 1, 'name': 'Inbound'},
    'O': {'id': 2, 'name': 'Outbound'},
}


class FlowLogTransformer:
    """Transforms Azure NSG Flow Logs to OCSF format"""
    
    def __init__(self):
        """Initialize Flow Log Transformer"""
        self.ocsf_version = "1.0.0"
        logger.info("Initialized Flow Log Transformer")
    
    def parse_flow_tuple(self, tuple_str: str) -> Dict[str, Any]:
        """
        Parse Azure NSG flow tuple string
        
        Format: timestamp,src_ip,dest_ip,src_port,dest_port,protocol,direction,flow_state,encryption,packets_out,bytes_out,packets_in,bytes_in
        
        Args:
            tuple_str: Comma-separated flow tuple string
            
        Returns:
            Parsed tuple dictionary
        """
        parts = tuple_str.split(',')
        
        return {
            'timestamp': int(parts[0]) if len(parts) > 0 else 0,
            'src_ip': parts[1] if len(parts) > 1 else '',
            'dest_ip': parts[2] if len(parts) > 2 else '',
            'src_port': int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0,
            'dest_port': int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0,
            'protocol': parts[5] if len(parts) > 5 else '',
            'direction': parts[6] if len(parts) > 6 else '',
            'flow_state': parts[7] if len(parts) > 7 else '',
            'encryption': parts[8] if len(parts) > 8 else '',
            'packets_out': int(parts[9]) if len(parts) > 9 and parts[9].isdigit() else 0,
            'bytes_out': int(parts[10]) if len(parts) > 10 and parts[10].isdigit() else 0,
            'packets_in': int(parts[11]) if len(parts) > 11 and parts[11].isdigit() else 0,
            'bytes_in': int(parts[12]) if len(parts) > 12 and parts[12].isdigit() else 0,
            'raw': tuple_str
        }
    
    def convert_tuple_to_ocsf(
        self,
        tuple_data: Dict[str, Any],
        record_metadata: Dict[str, Any],
        acl_id: str,
        rule_name: str,
        subscription_id: str = 'unknown'
    ) -> Dict[str, Any]:
        """
        Convert a single flow tuple to OCSF Network Activity format
        
        Args:
            tuple_data: Parsed flow tuple data
            record_metadata: Metadata from the parent record
            acl_id: ACL/NSG ID
            rule_name: NSG rule name
            subscription_id: Azure subscription ID
            
        Returns:
            OCSF Network Activity event (class_uid: 4001)
        """
        # Get activity info from flow state
        activity = FLOW_STATE_TO_ACTIVITY.get(tuple_data['flow_state'], {'id': 99, 'name': 'Other'})
        
        # Get protocol info
        protocol = PROTOCOL_MAP.get(tuple_data['protocol'], {'num': 0, 'name': 'Unknown'})
        
        # Get direction info
        direction = DIRECTION_MAP.get(tuple_data['direction'], {'id': 0, 'name': 'Unknown'})
        
        # Determine MAC address placement based on direction
        dst_mac = record_metadata['macAddress'] if tuple_data['direction'] == 'I' else ''
        src_mac = record_metadata['macAddress'] if tuple_data['direction'] == 'O' else ''
        
        # Convert timestamp (Azure uses milliseconds since epoch)
        timestamp_ms = tuple_data['timestamp']
        
        # Parse original time and convert to milliseconds timestamp
        try:
            original_time_dt = datetime.fromisoformat(record_metadata['time'].replace('Z', '+00:00'))
            original_time_ms = int(original_time_dt.timestamp() * 1000)
        except Exception:
            original_time_ms = timestamp_ms
        
        modified_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        
        # Build OCSF event
        ocsf_event = {
            "time": timestamp_ms,
            "end_time": timestamp_ms,
            "metadata": {
                "version": self.ocsf_version,
                "product": {
                    "name": "Microsoft Azure Network Watcher",
                    "version": str(record_metadata.get('flowLogVersion', 4)),
                    "uid": record_metadata['flowLogResourceID'],
                    "feature": {
                        "name": record_metadata['category'],
                        "version": "1.0.0"
                    },
                    "lang": "en",
                    "vendor_name": "Microsoft Azure"
                },
                "profiles": ["cloud"],
                "event_code": record_metadata['operationName'],
                "log_name": record_metadata['flowLogResourceID'],
                "log_provider": "Microsoft Azure",
                "log_version": str(record_metadata.get('flowLogVersion', 4)),
                "modified_time": modified_time_ms,
                "original_time": original_time_ms
            },
            "connection_info": {
                "uid": str(uuid.uuid4()),
                "boundary": "Unknown",
                "boundary_id": 0,
                "direction": direction['name'],
                "direction_id": direction['id'],
                "protocol_num": protocol['num'],
                "protocol_name": protocol['name']
            },
            "severity": "Informational",
            "severity_id": 1,
            "category_uid": 4,
            "category_name": "Network Activity",
            "class_uid": 4001,
            "class_name": "Network Activity",
            "activity_id": activity['id'],
            "activity_name": activity['name'],
            "type_uid": 400100 + activity['id'],
            "type_name": f"Network Activity: {activity['name']}",
            "timezone_offset": 0,
            "status": "Unknown",
            "status_id": 0,
            "cloud": {
                "provider": "Azure",
                "region": "unknown",
                "zone": "unknown",
                "account": {
                    "uid": subscription_id
                }
            },
            "src_endpoint": {
                "name": "Source_IP",
                "port": tuple_data['src_port'],
                "ip": tuple_data['src_ip'],
                "mac": src_mac
            },
            "dst_endpoint": {
                "name": "Destination_IP",
                "port": tuple_data['dest_port'],
                "ip": tuple_data['dest_ip'],
                "mac": dst_mac
            },
            "traffic": {
                "packets_in": tuple_data['packets_in'],
                "packets_out": tuple_data['packets_out'],
                "packets": tuple_data['packets_in'] + tuple_data['packets_out'],
                "bytes_in": tuple_data['bytes_in'],
                "bytes_out": tuple_data['bytes_out'],
                "bytes": tuple_data['bytes_in'] + tuple_data['bytes_out']
            },
            "enrichment": {
                "value": "flowData",
                "data": {
                    "aclId": acl_id,
                    "rule": rule_name,
                    "targetResourceID": record_metadata.get('targetResourceID', '')
                }
            }
        }
        
        return ocsf_event
    
    def transform_to_ocsf(self, flow_log_data: Dict[str, Any], subscription_id: str = 'unknown') -> List[Dict[str, Any]]:
        """
        Transform Azure Flow Log to OCSF Network Activity events
        
        Args:
            flow_log_data: Azure Flow Log JSON data with 'records' array
            subscription_id: Azure subscription ID for cloud.account.uid
            
        Returns:
            List of OCSF Network Activity events (one per flow tuple)
        """
        ocsf_records = []
        
        try:
            for record in flow_log_data.get('records', []):
                # Extract metadata from record
                record_metadata = {
                    'time': record['time'],
                    'flowLogGUID': record['flowLogGUID'],
                    'macAddress': record['macAddress'],
                    'category': record['category'],
                    'flowLogResourceID': record['flowLogResourceID'],
                    'targetResourceID': record['targetResourceID'],
                    'flowLogVersion': record['flowLogVersion'],
                    'operationName': record['operationName']
                }
                
                # Process all flows in the record
                for flow in record.get('flowRecords', {}).get('flows', []):
                    acl_id = flow.get('aclID', '')
                    
                    # Process all flow groups
                    for flow_group in flow.get('flowGroups', []):
                        rule_name = flow_group.get('rule', '')
                        
                        # Process all tuples in the group
                        for tuple_str in flow_group.get('flowTuples', []):
                            try:
                                # Parse tuple
                                tuple_data = self.parse_flow_tuple(tuple_str)
                                
                                # Convert to OCSF
                                ocsf_event = self.convert_tuple_to_ocsf(
                                    tuple_data=tuple_data,
                                    record_metadata=record_metadata,
                                    acl_id=acl_id,
                                    rule_name=rule_name,
                                    subscription_id=subscription_id
                                )
                                
                                ocsf_records.append(ocsf_event)
                                
                            except Exception as e:
                                logger.error(f"Error converting tuple to OCSF: {str(e)}")
                                continue
            
            logger.info(f"Transformed {len(ocsf_records)} flow tuples to OCSF format")
            
        except Exception as e:
            logger.error(f"Error transforming flow log data: {str(e)}")
        
        return ocsf_records