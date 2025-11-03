"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Azure NSG Flow Log to OCSF 1.0.0 Converter

This script converts Azure NSG Flow Log records to OCSF Network Activity (Class 4001) format.
Each flow tuple becomes an individual OCSF record.

Author: Jeremy Tirrell
Version: 1.0.0

Usage:
    python convert_to_ocsf.py
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List
import uuid


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


def parse_flow_tuple(tuple_str: str) -> Dict[str, Any]:
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
            "version": "1.0.0",
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
        "type_uid": 400100 + activity['id'],  # 400105, 400103, 400106, 400101
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


def extract_subscription_id(flow_log_resource_id: str) -> str:
    """Extract Azure subscription ID from flowLogResourceID"""
    try:
        parts = flow_log_resource_id.split('/')
        if 'SUBSCRIPTIONS' in parts:
            sub_idx = parts.index('SUBSCRIPTIONS') + 1
            if sub_idx < len(parts):
                return parts[sub_idx].lower()  # Convert to lowercase
        return 'unknown'
    except Exception:
        return 'unknown'


def convert_azure_flowlog_to_ocsf(azure_records: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert Azure NSG Flow Log records to OCSF format
    
    Args:
        azure_records: Azure flow log data with 'records' array
        
    Returns:
        List of OCSF Network Activity events
    """
    ocsf_events = []
    
    # Extract subscription ID from first record
    subscription_id = 'unknown'
    if azure_records.get('records'):
        first_record = azure_records['records'][0]
        flow_log_resource_id = first_record.get('flowLogResourceID', '')
        subscription_id = extract_subscription_id(flow_log_resource_id)
        print(f"Extracted subscription ID: {subscription_id}")
    
    for record in azure_records.get('records', []):
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
                    # Parse tuple
                    tuple_data = parse_flow_tuple(tuple_str)
                    
                    # Convert to OCSF
                    ocsf_event = convert_tuple_to_ocsf(
                        tuple_data=tuple_data,
                        record_metadata=record_metadata,
                        acl_id=acl_id,
                        rule_name=rule_name,
                        subscription_id=subscription_id
                    )
                    
                    ocsf_events.append(ocsf_event)
    
    return ocsf_events


def main():
    """Main conversion function"""
    print("=" * 80)
    print("Azure NSG Flow Log to OCSF 1.0.0 Converter")
    print("=" * 80)
    print()
    
    # Load example record
    print("Loading example_record.json...")
    with open('example_record.json', 'r', encoding='utf-8') as f:
        azure_data = json.load(f)
    
    print(f"Loaded {len(azure_data.get('records', []))} Azure flow log records")
    
    # Count total tuples
    total_tuples = 0
    for record in azure_data.get('records', []):
        for flow in record.get('flowRecords', {}).get('flows', []):
            for flow_group in flow.get('flowGroups', []):
                total_tuples += len(flow_group.get('flowTuples', []))
    
    print(f"Total flow tuples to convert: {total_tuples}")
    print()
    print("-" * 80)
    
    # Convert to OCSF
    print("Converting to OCSF format...")
    ocsf_events = convert_azure_flowlog_to_ocsf(azure_data)
    
    print(f"Generated {len(ocsf_events)} OCSF events")
    print()
    
    # Save output
    output_file = 'converted_ocsf_output.json'
    print(f"Saving to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ocsf_events, f, indent=2)
    
    print(f"Successfully saved {len(ocsf_events)} events")
    print()
    print("-" * 80)
    
    # Show first event as sample
    if ocsf_events:
        print("Sample OCSF Event (first record):")
        print(json.dumps(ocsf_events[0], indent=2))
        print()
        print("-" * 80)
    
    # Show statistics
    print("Conversion Statistics:")
    print(f"  Input Records: {len(azure_data.get('records', []))}")
    print(f"  Output OCSF Events: {len(ocsf_events)}")
    print(f"  Conversion Ratio: {total_tuples} tuples -> {len(ocsf_events)} events")
    
    # Count by activity type
    activity_counts = {}
    for event in ocsf_events:
        activity_name = event.get('activity_name', 'Unknown')
        activity_counts[activity_name] = activity_counts.get(activity_name, 0) + 1
    
    print()
    print("Events by Activity Type:")
    for activity, count in sorted(activity_counts.items()):
        print(f"  {activity}: {count}")
    
    print()
    print("=" * 80)
    print(f"Conversion complete! Output saved to {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()