"""
OCSF Schema Validation Utility
Validates OCSF events against schema definitions using metaschema rules
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

# Data type validation patterns from OCSF schema
OCSF_DATA_TYPE_PATTERNS = {
    'email_t': r'^[a-zA-Z0-9!#$%&\'*+-/=?^_`{|}~.]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',
    'file_hash_t': r'^[a-fA-F0-9]+$',
    'hostname_t': r'^[a-zA-Z0-9.-]+$',
    'ip_t': r'((^\s*((([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]).){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]))\s*$)|(^\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*$))',
    'mac_t': r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$',
    'url_t': r'^https?://.*',
    'uuid_t': r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',
    'datetime_t': r'^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?([Zz]|[\+-]\d{2}:\d{2})?$'
}

# OCSF enumeration values
OCSF_ENUMS = {
    'severity_id': {0: 'Unknown', 1: 'Informational', 2: 'Low', 3: 'Medium', 4: 'High', 5: 'Critical', 6: 'Fatal', 99: 'Other'},
    'confidence_id': {0: 'Unknown', 1: 'Low', 2: 'Medium', 3: 'High', 99: 'Other'},
    'activity_id': {0: 'Unknown', 1: 'Create', 2: 'Update', 3: 'Close', 99: 'Other'},
    'status_id': {0: 'Unknown', 1: 'New', 2: 'In Progress', 3: 'Suppressed', 4: 'Resolved', 5: 'Archived', 6: 'Deleted', 99: 'Other'},
    'category_uid': {1: 'System Activity', 2: 'Findings', 3: 'Identity & Access Management', 4: 'Network Activity', 5: 'Discovery', 6: 'Application Activity', 7: 'Remediation', 8: 'Unmanned Systems'},
    'impact_id': {0: 'Unknown', 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical', 99: 'Other'},
    'risk_level_id': {0: 'Info', 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical', 99: 'Other'}
}

# OCSF Class UIDs
OCSF_CLASS_UIDS = {
    'detection_finding': 2004,
    'compliance_finding': 2003,
    'security_finding': 2001,
    'vulnerability_finding': 2002,
    'data_security_finding': 2005
}


class OCSFValidator:
    """
    OCSF Schema Validator for ensuring events comply with OCSF v1.7.0-dev standards
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
    
    def validate_ocsf_event(self, event: Dict[str, Any], event_class: str = 'detection_finding') -> Dict[str, Any]:
        """
        Validate an OCSF event against schema requirements
        
        Args:
            event: OCSF event dictionary
            event_class: OCSF event class name
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'event_class': event_class,
            'schema_version': '1.7.0'
        }
        
        try:
            # Validate required base fields
            self._validate_base_fields(event, validation_result)
            
            # Validate class-specific requirements
            if event_class == 'detection_finding':
                self._validate_detection_finding(event, validation_result)
            elif event_class == 'compliance_finding':
                self._validate_compliance_finding(event, validation_result)
            
            # Validate data types
            self._validate_data_types(event, validation_result)
            
            # Validate enumerations
            self._validate_enumerations(event, validation_result)
            
            # Validate object structures
            self._validate_object_structures(event, validation_result)
            
        except Exception as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"Validation exception: {str(e)}")
            self.logger.error(f"OCSF validation failed: {str(e)}")
        
        # Log results
        if validation_result['is_valid']:
            self.logger.info(f"OCSF event validation passed for {event_class}")
        else:
            self.logger.warning(f"OCSF event validation failed for {event_class}: {len(validation_result['errors'])} errors")
        
        return validation_result
    
    def _validate_base_fields(self, event: Dict[str, Any], result: Dict[str, Any]):
        """Validate required base fields for all OCSF events"""
        required_fields = [
            'activity_id', 'category_uid', 'class_uid', 'finding_info', 
            'metadata', 'severity_id', 'time', 'type_uid'
        ]
        
        for field in required_fields:
            if field not in event:
                result['errors'].append(f"Missing required field: {field}")
                result['is_valid'] = False
        
        # Validate category_uid is 2 (Findings)
        if event.get('category_uid') != 2:
            result['errors'].append(f"Invalid category_uid: expected 2 (Findings), got {event.get('category_uid')}")
            result['is_valid'] = False
        
        # Validate type_uid calculation
        expected_type_uid = event.get('class_uid', 0) * 100 + event.get('activity_id', 0)
        if event.get('type_uid') != expected_type_uid:
            result['warnings'].append(f"type_uid should be {expected_type_uid} (class_uid * 100 + activity_id)")
    
    def _validate_detection_finding(self, event: Dict[str, Any], result: Dict[str, Any]):
        """Validate Detection Finding specific requirements"""
        if event.get('class_uid') != 2004:
            result['errors'].append(f"Invalid class_uid for detection_finding: expected 2004, got {event.get('class_uid')}")
            result['is_valid'] = False
        
        # Validate recommended fields
        recommended_fields = ['confidence_id', 'evidences', 'resources', 'is_alert']
        for field in recommended_fields:
            if field not in event:
                result['warnings'].append(f"Recommended field missing: {field}")
    
    def _validate_compliance_finding(self, event: Dict[str, Any], result: Dict[str, Any]):
        """Validate Compliance Finding specific requirements"""
        if event.get('class_uid') != 2003:
            result['errors'].append(f"Invalid class_uid for compliance_finding: expected 2003, got {event.get('class_uid')}")
            result['is_valid'] = False
        
        # Validate required compliance field
        if 'compliance' not in event:
            result['errors'].append("Missing required field for compliance_finding: compliance")
            result['is_valid'] = False
    
    def _validate_data_types(self, event: Dict[str, Any], result: Dict[str, Any]):
        """Validate OCSF data types"""
        
        # Validate timestamp_t fields (should be integers representing milliseconds)
        timestamp_fields = ['time', 'start_time', 'end_time']
        for field in timestamp_fields:
            if field in event:
                value = event[field]
                if not isinstance(value, int):
                    result['errors'].append(f"{field} should be timestamp_t (integer milliseconds), got {type(value).__name__}")
                    result['is_valid'] = False
                elif value < 0 or value > 9999999999999:  # Reasonable timestamp range
                    result['warnings'].append(f"{field} timestamp seems out of reasonable range: {value}")
        
        # Validate string fields
        string_fields = ['activity_name', 'category_name', 'class_name', 'type_name', 'severity', 'status']
        for field in string_fields:
            if field in event and not isinstance(event[field], str):
                result['warnings'].append(f"{field} should be string_t, got {type(event[field]).__name__}")
    
    def _validate_enumerations(self, event: Dict[str, Any], result: Dict[str, Any]):
        """Validate OCSF enumeration values"""
        for field, valid_values in OCSF_ENUMS.items():
            if field in event:
                value = event[field]
                if value not in valid_values:
                    result['errors'].append(f"Invalid {field} value: {value}. Valid values: {list(valid_values.keys())}")
                    result['is_valid'] = False
    
    def _validate_object_structures(self, event: Dict[str, Any], result: Dict[str, Any]):
        """Validate OCSF object structures"""
        
        # Validate finding_info object
        if 'finding_info' in event:
            finding_info = event['finding_info']
            if not isinstance(finding_info, dict):
                result['errors'].append("finding_info should be an object")
                result['is_valid'] = False
            else:
                if 'uid' not in finding_info:
                    result['errors'].append("finding_info.uid is required")
                    result['is_valid'] = False
                if 'title' not in finding_info:
                    result['warnings'].append("finding_info.title is recommended")
        
        # Validate metadata object
        if 'metadata' in event:
            metadata = event['metadata']
            if not isinstance(metadata, dict):
                result['errors'].append("metadata should be an object")
                result['is_valid'] = False
            else:
                required_metadata = ['version', 'product']
                for field in required_metadata:
                    if field not in metadata:
                        result['errors'].append(f"metadata.{field} is required")
                        result['is_valid'] = False
                
                # Validate product object
                if 'product' in metadata and isinstance(metadata['product'], dict):
                    product = metadata['product']
                    required_product_fields = ['name', 'vendor_name']
                    for field in required_product_fields:
                        if field not in product:
                            result['warnings'].append(f"metadata.product.{field} is recommended")
        
        # Validate cloud object
        if 'cloud' in event:
            cloud = event['cloud']
            if not isinstance(cloud, dict):
                result['errors'].append("cloud should be an object")
                result['is_valid'] = False
            else:
                if 'provider' not in cloud:
                    result['errors'].append("cloud.provider is required")
                    result['is_valid'] = False
                if 'account' not in cloud:
                    result['warnings'].append("cloud.account is recommended")
        
        # Validate observables array
        if 'observables' in event:
            observables = event['observables']
            if not isinstance(observables, list):
                result['errors'].append("observables should be an array")
                result['is_valid'] = False
            else:
                for i, observable in enumerate(observables):
                    if not isinstance(observable, dict):
                        result['errors'].append(f"observables[{i}] should be an object")
                        result['is_valid'] = False
                    elif 'type_id' not in observable:
                        result['errors'].append(f"observables[{i}].type_id is required")
                        result['is_valid'] = False
    
    def validate_data_type_pattern(self, value: str, data_type: str) -> bool:
        """
        Validate a value against OCSF data type pattern
        
        Args:
            value: Value to validate
            data_type: OCSF data type (e.g., 'email_t', 'ip_t')
            
        Returns:
            True if value matches pattern, False otherwise
        """
        if data_type not in OCSF_DATA_TYPE_PATTERNS:
            return True  # No pattern to validate against
        
        pattern = OCSF_DATA_TYPE_PATTERNS[data_type]
        try:
            return re.match(pattern, value) is not None
        except Exception as e:
            self.logger.warning(f"Error validating {data_type} pattern: {str(e)}")
            return False
    
    def validate_timestamp_range(self, timestamp: int) -> bool:
        """
        Validate timestamp is within reasonable range for OCSF timestamp_t
        
        Args:
            timestamp: Timestamp in milliseconds since epoch
            
        Returns:
            True if timestamp is reasonable, False otherwise
        """
        # Reasonable range: 2000-01-01 to 2100-01-01
        min_timestamp = 946684800000  # 2000-01-01
        max_timestamp = 4102444800000  # 2100-01-01
        
        return min_timestamp <= timestamp <= max_timestamp
    
    def get_enum_description(self, field: str, value: int) -> Optional[str]:
        """
        Get OCSF enumeration description for a field and value
        
        Args:
            field: OCSF field name
            value: Enumeration value
            
        Returns:
            Description string or None if not found
        """
        return OCSF_ENUMS.get(field, {}).get(value)
    
    def validate_required_objects(self, event: Dict[str, Any], event_class: str) -> List[str]:
        """
        Validate required objects are present for event class
        
        Args:
            event: OCSF event dictionary
            event_class: OCSF event class name
            
        Returns:
            List of missing required objects
        """
        missing = []
        
        # Base requirements for all findings
        base_required = ['finding_info', 'metadata']
        for obj in base_required:
            if obj not in event or not isinstance(event[obj], dict):
                missing.append(obj)
        
        # Class-specific requirements
        if event_class == 'compliance_finding':
            if 'compliance' not in event or not isinstance(event['compliance'], dict):
                missing.append('compliance')
        
        return missing
    
    def create_validation_report(self, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a comprehensive validation report from multiple event validations
        
        Args:
            validation_results: List of validation result dictionaries
            
        Returns:
            Summary validation report
        """
        total_events = len(validation_results)
        valid_events = sum(1 for result in validation_results if result['is_valid'])
        
        all_errors = []
        all_warnings = []
        
        for result in validation_results:
            all_errors.extend(result.get('errors', []))
            all_warnings.extend(result.get('warnings', []))
        
        # Count unique error/warning types
        unique_errors = list(set(all_errors))
        unique_warnings = list(set(all_warnings))
        
        return {
            'total_events': total_events,
            'valid_events': valid_events,
            'invalid_events': total_events - valid_events,
            'validation_rate': (valid_events / total_events * 100) if total_events > 0 else 0,
            'total_errors': len(all_errors),
            'unique_errors': len(unique_errors),
            'total_warnings': len(all_warnings),
            'unique_warnings': len(unique_warnings),
            'error_types': unique_errors[:10],  # Top 10 error types
            'warning_types': unique_warnings[:10],  # Top 10 warning types
            'schema_version': '1.7.0',
            'validation_timestamp': int(datetime.utcnow().timestamp() * 1000)
        }


class OCSFDataTypeConverter:
    """
    Utility for converting Azure data to OCSF-compliant data types
    """
    
    @staticmethod
    def to_timestamp_t(iso_timestamp: str) -> int:
        """Convert ISO timestamp to OCSF timestamp_t (milliseconds since epoch)"""
        try:
            if not iso_timestamp:
                return int(datetime.utcnow().timestamp() * 1000)
            
            if iso_timestamp.endswith('Z'):
                dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
            elif '+' in iso_timestamp:
                dt = datetime.fromisoformat(iso_timestamp)
            else:
                dt = datetime.fromisoformat(iso_timestamp + '+00:00' if 'T' in iso_timestamp else iso_timestamp)
            
            return int(dt.timestamp() * 1000)
        except Exception:
            return int(datetime.utcnow().timestamp() * 1000)
    
    @staticmethod
    def map_severity_to_ocsf(azure_severity: str) -> int:
        """Map Azure severity to OCSF severity_id"""
        mapping = {
            'Informational': 1,
            'Low': 2,
            'Medium': 3, 
            'High': 4,
            'Critical': 5
        }
        return mapping.get(azure_severity, 99)  # 99 = Other
    
    @staticmethod
    def map_confidence_to_ocsf(azure_confidence: str) -> int:
        """Map Azure confidence to OCSF confidence_id"""
        mapping = {
            'Unknown': 0,
            'Low': 1,
            'Medium': 2,
            'High': 3
        }
        return mapping.get(azure_confidence, 99)  # 99 = Other
    
    @staticmethod
    def map_status_to_ocsf(azure_status: str) -> int:
        """Map Azure status to OCSF status_id"""
        mapping = {
            'New': 1,
            'Active': 1,
            'InProgress': 2,
            'Dismissed': 3,
            'Resolved': 4,
            'Closed': 4
        }
        return mapping.get(azure_status, 99)  # 99 = Other
    
    @staticmethod
    def create_ocsf_cloud_object(subscription_id: str, tenant_id: str = '', region: str = '') -> Dict[str, Any]:
        """Create OCSF-compliant cloud object for Azure"""
        cloud_obj = {
            'provider': 'Azure',
            'account': {
                'uid': subscription_id,
                'type': 'Azure Subscription',
                'type_id': 10
            }
        }
        
        if tenant_id:
            cloud_obj['org'] = {'uid': tenant_id}
        
        if region:
            cloud_obj['region'] = region
            
        return cloud_obj
    
    @staticmethod
    def create_ocsf_metadata_object(product_name: str = 'Microsoft Defender for Cloud',
                                   vendor_name: str = 'Microsoft',
                                   event_code: str = '',
                                   logged_time: Optional[int] = None,
                                   original_time: str = '') -> Dict[str, Any]:
        """Create OCSF-compliant metadata object"""
        metadata_obj = {
            'version': '1.7.0',
            'product': {
                'name': product_name,
                'vendor_name': vendor_name,
                'version': '1.0'
            },
            'profiles': ['security_control']
        }
        
        if event_code:
            metadata_obj['event_code'] = event_code
        
        if logged_time:
            metadata_obj['logged_time'] = logged_time
            
        if original_time:
            metadata_obj['original_time'] = original_time
            
        return metadata_obj