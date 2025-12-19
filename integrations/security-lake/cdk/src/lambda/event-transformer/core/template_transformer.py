"""
Template-driven JSON transformation engine using JSONPath + Jinja2
Replaces hardcoded CloudTrailEventBuilder methods with flexible templates
"""

import json
import logging
import os
import re
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from functools import lru_cache

try:
    from jsonpath_ng import parse as jsonpath_parse
    from jsonpath_ng.exceptions import JSONPathError
except ImportError:
    # Fallback for local development
    jsonpath_parse = None
    class JSONPathError(Exception):
        pass

try:
    from jinja2 import Environment, Template, BaseLoader, TemplateError
    from jinja2.sandbox import SandboxedEnvironment
except ImportError:
    # Fallback for local development
    Environment = None
    Template = None
    BaseLoader = None
    TemplateError = Exception
    SandboxedEnvironment = None

import yaml
from core.cloudtrail_types import CloudTrailAuditEvent

# Environment Variables
VALIDATE_OCSF = os.getenv('VALIDATE_OCSF', 'false').lower() == 'true'

# Try to import jsonschema for OCSF validation
try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    jsonschema = None
    JSONSCHEMA_AVAILABLE = False


# OCSF Class Dictionary for validation (from Amazon Security Lake validator)
OCSF_CLASS_DICTIONARY = {
    "1.7.0": {
        "2001": {"url": "security_finding", "class_name": "Security Finding", "category_name": "Findings", "category_uid": 2},
        "2002": {"url": "vulnerability_finding", "class_name": "Vulnerability Finding", "category_name": "Findings", "category_uid": 2},
        "2003": {"url": "compliance_finding", "class_name": "Compliance Finding", "category_name": "Findings", "category_uid": 2},
        "2004": {"url": "detection_finding", "class_name": "Detection Finding", "category_name": "Findings", "category_uid": 2},
        "2005": {"url": "incident_finding", "class_name": "Incident Finding", "category_name": "Findings", "category_uid": 2}
    },
    "1.1.0": {
        "2001": {"url": "security_finding", "class_name": "Security Finding", "category_name": "Findings", "category_uid": 2},
        "2002": {"url": "vulnerability_finding", "class_name": "Vulnerability Finding", "category_name": "Findings", "category_uid": 2},
        "2003": {"url": "compliance_finding", "class_name": "Compliance Finding", "category_name": "Findings", "category_uid": 2},
        "2004": {"url": "detection_finding", "class_name": "Detection Finding", "category_name": "Findings", "category_uid": 2},
        "2005": {"url": "incident_finding", "class_name": "Incident Finding", "category_name": "Findings", "category_uid": 2}
    },
    "1.0.0-rc.2": {
        "2001": {"url": "security_finding", "class_name": "Security Finding", "category_name": "Findings", "category_uid": 2}
    }
}


@dataclass
class TransformationTemplate:
    """Definition of a transformation template"""
    name: str
    input_schema: str
    output_schema: str
    extractors: Dict[str, str]  # JSONPath expressions
    template: str  # Jinja2 template
    filters: Optional[Dict[str, Any]] = None  # Custom Jinja2 filters
    conditionals: Optional[Dict[str, Any]] = None  # Conditional logic


class JSONPathExtractor:
    """High-performance JSONPath expression evaluator with caching"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._compiled_expressions = {}
        
    @lru_cache(maxsize=128)
    def _compile_expression(self, jsonpath_expr: str):
        """Compile and cache JSONPath expressions for performance"""
        try:
            if jsonpath_parse is None:
                raise ImportError("jsonpath-ng not available")
            return jsonpath_parse(jsonpath_expr)
        except (JSONPathError, Exception) as e:
            self.logger.error(f"Failed to compile JSONPath expression '{jsonpath_expr}': {str(e)}")
            return None
    
    def extract(self, data: Dict[str, Any], jsonpath_expr: str) -> Union[Any, List[Any], None]:
        """Extract data using JSONPath expression"""
        compiled_expr = self._compile_expression(jsonpath_expr)
        if compiled_expr is None:
            return None
            
        try:
            matches = compiled_expr.find(data)
            if not matches:
                return None
            
            # Return single value if only one match, otherwise list
            values = [match.value for match in matches]
            return values[0] if len(values) == 1 else values
            
        except Exception as e:
            self.logger.warning(f"JSONPath extraction failed for '{jsonpath_expr}': {str(e)}")
            return None


class TemplateEngine:
    """Jinja2 template engine with custom filters for event transformation"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        # Use sandboxed environment for security
        if SandboxedEnvironment:
            self.env = SandboxedEnvironment()
        else:
            self.env = None
            
        # Register custom filters
        if self.env:
            self.env.filters.update(self._get_custom_filters())
    
    def _get_custom_filters(self) -> Dict[str, callable]:
        """Custom Jinja2 filters for event transformation"""
        return {
            # CloudTrail filters
            'normalize_timestamp': self._normalize_timestamp,
            'format_severity': self._format_severity,
            'generate_uuid': lambda: str(uuid.uuid4()),
            'to_json': lambda obj: json.dumps(obj) if obj else '{}',
            'safe_get': lambda obj, key, default=None: obj.get(key, default) if isinstance(obj, dict) else default,
            
            # JSON string escaping (critical for descriptions with newlines)
            'json_escape': self._json_escape_string,
            
            # OCSF-specific filters
            'to_unix_timestamp': self._to_unix_timestamp,
            'map_azure_severity_to_ocsf': self._map_azure_severity_to_ocsf,
            'map_alert_status': self._map_alert_status,
            'map_confidence_level': self._map_confidence_level,
            'extract_subscription_id': self._extract_subscription_id,
            'extract_azure_region': self._extract_azure_region,
            'extract_resource_name': self._extract_resource_name,
            'extract_azure_resource_type': self._extract_azure_resource_type,
            'map_mitre_tactic': self._map_mitre_tactic,
            'truncate': lambda s, length=500: s[:length] + '...' if isinstance(s, str) and len(s) > length else s,
            'extract_azure_subscription': self._extract_azure_subscription_from_resources,
            'extract_source_ip': self._extract_source_ip,
            
            # OCSF v1.7.0-dev compliant filters
            'to_unix_timestamp_ms': self._to_unix_timestamp,
            'extract_azure_tenant': self._extract_azure_tenant_from_resources,
            'calculate_compliance_severity': self._calculate_compliance_severity,
            'calculate_compliance_severity_name': self._calculate_compliance_severity_name,
            
            # Additional secure_score template filters
            'safe_string': lambda s: str(s) if s is not None else 'Unknown',
            
            # ASFF-specific filters
            'asff_severity_label': self._asff_severity_label,
            'asff_severity_normalized': self._asff_severity_normalized,
            'to_asff_types': self._to_asff_types,
            'compliance_status': self._compliance_status,
            'asff_record_state': self._asff_record_state,
            'score_to_severity': self._score_to_severity,
            'score_to_severity_normalized': self._score_to_severity_normalized,
            'score_to_compliance_status': self._score_to_compliance_status,
            'score_to_reason_code': self._score_to_reason_code,
            'compliance_reason_code': self._compliance_reason_code,
            
            # Utility filters for handling "None" strings and invalid values
            'is_valid': self._is_valid_value,
            'default_if_invalid': self._default_if_invalid,
            'omit_if_invalid': self._omit_if_invalid,
            
            # Timestamp manipulation
            'add_one_second': self._add_one_second,
            
            # IP address filtering (strip port numbers)
            'extract_ip': self._extract_ip_from_address,
            'extract_port': self._extract_port_from_address,
            
            # OCSF Compliance status mapping filters
            'map_compliance_status': self._map_compliance_status,
            'map_compliance_status_id': self._map_compliance_status_id,
            
            # Text transformation filters
            'slugify': self._slugify
        }
    def _add_one_second(self, timestamp_str: str) -> str:
        """Add 1 second to an ISO8601 timestamp string"""
        if not timestamp_str:
            return timestamp_str
        try:
            from datetime import datetime, timedelta
            # Parse ISO timestamp
            if timestamp_str.endswith('Z'):
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            elif '+' in timestamp_str or timestamp_str.count('-') > 2:
                dt = datetime.fromisoformat(timestamp_str)
            else:
                dt = datetime.fromisoformat(timestamp_str + '+00:00')
            # Add 1 second
            dt_plus_one = dt + timedelta(seconds=1)
            # Return in ISO format with Z
            return dt_plus_one.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        except Exception as e:
            # logger may not be imported in this context, use print as fallback
            print(f"Failed to add 1 second to timestamp {timestamp_str}: {e}")
            return timestamp_str
    
    def _normalize_timestamp(self, timestamp: str) -> str:
        """Normalize timestamp to CloudTrail format (YYYY-MM-DDTHH:MM:SSZ)"""
        try:
            if not timestamp:
                return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                
            # Handle various timestamp formats
            dt = None
            
            # Try parsing ISO format with timezone
            if timestamp.endswith('Z'):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif '+' in timestamp or timestamp.endswith('+00:00'):
                dt = datetime.fromisoformat(timestamp)
            else:
                # Assume UTC if no timezone info
                dt = datetime.fromisoformat(timestamp + '+00:00' if 'T' in timestamp else timestamp)
            
            # Convert to UTC naive datetime and format for CloudTrail
            if dt.tzinfo is not None:
                dt = dt.utctimetuple()
                dt = datetime(*dt[:6])  # Remove microseconds and timezone info
            
            # Return in strict CloudTrail format: YYYY-MM-DDTHH:MM:SSZ
            return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            
        except Exception as e:
            self.logger.warning(f"Could not normalize timestamp '{timestamp}': {e}")
            return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    def _extract_source_ip(self, entities: List[Dict[str, Any]]) -> Optional[str]:
        """Extract source IP from Azure alert entities"""
        if not isinstance(entities, list):
            return None
            
        for entity in entities:
            if isinstance(entity, dict):
                if entity.get('Type') == 'ip' or 'ip' in entity.get('Type', '').lower():
                    for ip_field in ['Address', 'SourceAddress', 'address']:
                        if ip_field in entity:
                            if isinstance(entity[ip_field], dict):
                                return entity[ip_field].get('Address')
                            else:
                                return entity[ip_field]
        return None
    
    def _format_severity(self, severity: str) -> str:
        """Standardize severity values"""
        severity_map = {
            'informational': 'Low',
            'low': 'Low',
            'medium': 'Medium',
            'high': 'High',
            'critical': 'Critical'
        }
        return severity_map.get(severity.lower() if severity else '', severity or 'Unknown')
    
    # OCSF-specific filter methods
    def _to_unix_timestamp(self, timestamp_str: str) -> int:
        """Convert timestamp to Unix epoch (milliseconds) for OCSF"""
        if not timestamp_str:
            return int(datetime.utcnow().timestamp() * 1000)
        try:
            if timestamp_str.endswith('Z'):
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(timestamp_str)
            return int(dt.timestamp() * 1000)
        except Exception as e:
            self.logger.warning(f"Could not parse timestamp '{timestamp_str}': {e}")
            return int(datetime.utcnow().timestamp() * 1000)
    
    def _map_azure_severity_to_ocsf(self, severity: str) -> int:
        """Map Azure severity to OCSF severity ID"""
        mapping = {
            'Informational': 1,
            'Low': 2, 
            'Medium': 3,
            'High': 4,
            'Critical': 5
        }
        return mapping.get(severity, 99)  # 99 = Other/Unknown
    
    def _map_alert_status(self, status: str) -> int:
        """Map Azure alert status to OCSF status ID"""
        mapping = {
            'New': 1,
            'Active': 1,
            'InProgress': 2,
            'Dismissed': 3,
            'Resolved': 4,
            'Closed': 4
        }
        return mapping.get(status, 99)  # 99 = Other/Unknown
    
    def _map_confidence_level(self, level: str) -> int:
        """Map confidence level to OCSF confidence ID"""
        mapping = {
            'High': 3,
            'Medium': 2,
            'Low': 1,
            'Unknown': 0
        }
        return mapping.get(level, 99)
    
    def _extract_subscription_id(self, resource_id: Union[str, List[str]]) -> str:
        """Extract subscription ID from Azure resource ID"""
        if isinstance(resource_id, list) and len(resource_id) > 0:
            resource_id = resource_id[0]
        if isinstance(resource_id, str) and '/subscriptions/' in resource_id:
            return resource_id.split('/subscriptions/')[1].split('/')[0]
        return 'unknown'
    
    def _extract_azure_region(self, resource_id: str) -> str:
        """Extract region from Azure resource ID"""
        # For now, return unknown - would need more sophisticated Azure resource parsing
        return 'unknown'
    
    def _extract_resource_name(self, resource_path: str) -> str:
        """Extract resource name from resource path"""
        if not resource_path:
            return 'unknown'
        if '/' in resource_path:
            return resource_path.split('/')[-1]
        return resource_path
    
    def _extract_azure_resource_type(self, resource_id: str) -> str:
        """Extract Azure resource type from resource ID"""
        if isinstance(resource_id, str) and '/providers/' in resource_id:
            parts = resource_id.split('/providers/')
            if len(parts) > 1:
                return parts[1].split('/')[0]
        return 'Subscription'
    
    def _extract_azure_subscription_from_resources(self, resource_identifiers: List[Dict[str, Any]]) -> str:
        """Extract Azure subscription ID from ResourceIdentifiers list"""
        if not isinstance(resource_identifiers, list):
            return 'unknown'
        
        for resource in resource_identifiers:
            if isinstance(resource, dict) and resource.get('Type') == 'AzureResource':
                azure_resource_id = resource.get('AzureResourceId', '')
                if '/subscriptions/' in azure_resource_id:
                    return azure_resource_id.split('/subscriptions/')[1].split('/')[0]
        return 'unknown'
    
    def _map_mitre_tactic(self, tactic_name: str) -> str:
        """Map Azure intent to MITRE tactic ID"""
        mapping = {
            'DefenseEvasion': 'TA0005',
            'LateralMovement': 'TA0008',
            'PrivilegeEscalation': 'TA0004',
            'Persistence': 'TA0003',
            'InitialAccess': 'TA0001',
            'Execution': 'TA0002',
            'Discovery': 'TA0007',
            'Collection': 'TA0009',
            'Exfiltration': 'TA0010',
            'Impact': 'TA0040'
        }
        return mapping.get(tactic_name, 'TA0000')
    
    def _extract_azure_tenant_from_resources(self, resource_identifiers: List[Dict[str, Any]]) -> str:
        """Extract Azure tenant ID from ResourceIdentifiers list"""
        if not isinstance(resource_identifiers, list):
            return ''
        
        for resource in resource_identifiers:
            if isinstance(resource, dict) and resource.get('Type') == 'AAD':
                return resource.get('AadTenantId', '')
        return ''
    
    def _calculate_compliance_severity(self, current_score: Union[int, float], max_score: Union[int, float]) -> int:
        """Calculate OCSF severity_id from Azure compliance score"""
        try:
            if not current_score or not max_score or max_score == 0:
                return 3  # Medium (Unknown score)
            
            percentage = float(current_score) / float(max_score)
            if percentage >= 0.9:
                return 1  # Informational (Good compliance)
            elif percentage >= 0.7:
                return 2  # Low (Minor issues)
            elif percentage >= 0.5:
                return 3  # Medium (Moderate issues)
            elif percentage >= 0.3:
                return 4  # High (Significant issues)
            else:
                return 5  # Critical (Poor compliance)
        except (ValueError, TypeError):
            return 3  # Medium (Default)
    
    def _calculate_compliance_severity_name(self, current_score: Union[int, float], max_score: Union[int, float]) -> str:
        """Calculate OCSF severity name from Azure compliance score"""
        severity_id = self._calculate_compliance_severity(current_score, max_score)
        mapping = {
            1: "Informational",
            2: "Low",
            3: "Medium",
            4: "High",
            5: "Critical"
        }
        return mapping.get(severity_id, "Medium")
    
    # ASFF-specific filter methods
    def _asff_severity_label(self, severity: str) -> str:
        """Convert Azure severity to ASFF severity label"""
        severity_map = {
            'informational': 'INFORMATIONAL',
            'low': 'LOW',
            'medium': 'MEDIUM',
            'high': 'HIGH',
            'critical': 'CRITICAL'
        }
        if not severity or not isinstance(severity, str):
            return 'INFORMATIONAL'
        return severity_map.get(severity.lower(), 'INFORMATIONAL')
    
    def _asff_severity_normalized(self, severity: str) -> int:
        """Convert Azure severity to ASFF normalized score (0-100)"""
        severity_map = {
            'informational': 0,
            'low': 30,
            'medium': 60,
            'high': 80,
            'critical': 100
        }
        if not severity or not isinstance(severity, str):
            return 0
        return severity_map.get(severity.lower(), 0)
    
    def _to_asff_types(self, alert_type: str) -> str:
        """Convert Azure alert type to ASFF Types array (returns JSON string)"""
        if not alert_type or not isinstance(alert_type, str):
            return json.dumps(['Security Monitoring/Threat Detection'])
        
        # Map to MITRE ATT&CK-based types when possible
        type_mapping = {
            'Backdoor': 'TTPs/Defense Evasion',
            'Malware': 'Effects/Data Exfiltration',
            'Crypto': 'Effects/Resource Consumption',
            'SQLInjection': 'TTPs/Initial Access',
            'Phishing': 'TTPs/Initial Access',
            'Brute': 'TTPs/Credential Access',
            'Exploit': 'TTPs/Execution',
            'Vulnerability': 'Software and Configuration Checks/Vulnerabilities'
        }
        
        # Check if any key is in the alert type
        for key, value in type_mapping.items():
            if key.lower() in alert_type.lower():
                return json.dumps([value])
        
        # Default to Security Monitoring category
        return json.dumps(['Security Monitoring/Threat Detection'])
    
    def _compliance_status(self, state: str) -> str:
        """Convert Azure compliance state to ASFF compliance status"""
        if not state or not isinstance(state, str):
            return 'FAILED'
        
        status_map = {
            'passed': 'PASSED',
            'pass': 'PASSED',
            'failed': 'FAILED',
            'fail': 'FAILED',
            'not_applicable': 'NOT_APPLICABLE',
            'notapplicable': 'NOT_APPLICABLE',
            'unknown': 'UNKNOWN'
        }
        return status_map.get(state.lower(), 'FAILED')
    
    def _asff_record_state(self, state: str) -> str:
        """Convert compliance/assessment state to ASFF RecordState"""
        if not state or not isinstance(state, str):
            return 'ACTIVE'
        
        state_upper = state.upper()
        # ARCHIVED for passed/healthy states, ACTIVE for everything else
        if state_upper in ['PASSED', 'PASS', 'HEALTHY']:
            return 'ARCHIVED'
        return 'ACTIVE'
    
    def _score_to_severity(self, current_score: Union[int, float, str], max_score: Union[int, float, str] = None) -> str:
        """Convert score to ASFF severity label"""
        try:
            if max_score is None:
                # If only one argument, treat as percentage
                percentage = float(current_score)
            else:
                # Calculate percentage from score/max_score
                score = float(current_score)
                max_val = float(max_score)
                if max_val == 0:
                    return 'MEDIUM'
                percentage = (score / max_val) * 100
            
            # Determine severity based on percentage
            if percentage >= 90:
                return 'INFORMATIONAL'
            elif percentage >= 70:
                return 'LOW'
            elif percentage >= 50:
                return 'MEDIUM'
            else:
                return 'HIGH'
        except (ValueError, TypeError, ZeroDivisionError):
            return 'MEDIUM'
    
    def _score_to_severity_normalized(self, current_score: Union[int, float, str], max_score: Union[int, float, str] = None) -> int:
        """Convert score to ASFF normalized severity (0-100)"""
        try:
            if max_score is None:
                # If only one argument, treat as percentage
                percentage = float(current_score)
            else:
                # Calculate percentage from score/max_score
                score = float(current_score)
                max_val = float(max_score)
                if max_val == 0:
                    return 50
                percentage = (score / max_val) * 100
            
            # Invert: lower score = higher severity
            normalized = int(100 - percentage)
            # Ensure it's in valid range
            return max(0, min(100, normalized))
        except (ValueError, TypeError, ZeroDivisionError):
            return 50
    
    def _score_to_compliance_status(self, current_score: Union[int, float, str], max_score: Union[int, float, str] = None) -> str:
        """Convert score to ASFF compliance status"""
        try:
            if max_score is None:
                # If only one argument, treat as percentage
                percentage = float(current_score)
            else:
                # Calculate percentage from score/max_score
                score = float(current_score)
                max_val = float(max_score)
                if max_val == 0:
                    return 'NOT_AVAILABLE'
                percentage = (score / max_val) * 100
            
            # Determine compliance status based on percentage
            if percentage >= 90:
                return 'PASSED'
            elif percentage >= 70:
                return 'WARNING'
            else:
                return 'FAILED'
        except (ValueError, TypeError, ZeroDivisionError):
            return 'NOT_AVAILABLE'
    
    def _score_to_reason_code(self, current_score: Union[int, float, str], max_score: Union[int, float, str] = None) -> str:
        """
        Convert score to Security Hub allowed ReasonCode enum value.
        Maps to one of: PASSED, FAILED, WARNING, NOT_AVAILABLE, NO_DATA_AVAILABLE
        """
        try:
            if max_score is None:
                # If only one argument, treat as percentage
                percentage = float(current_score)
            else:
                # Calculate percentage from score/max_score
                score = float(current_score)
                max_val = float(max_score)
                if max_val == 0:
                    return 'NOT_AVAILABLE'
                percentage = (score / max_val) * 100
            
            # Map percentage to Security Hub ReasonCode
            if percentage >= 90:
                return 'PASSED'
            elif percentage >= 70:
                return 'WARNING'
            else:
                return 'FAILED'
        except (ValueError, TypeError, ZeroDivisionError):
            return 'NOT_AVAILABLE'
    
    def _compliance_reason_code(self, state: str) -> str:
        """
        Convert Azure compliance state to Security Hub allowed ReasonCode enum value.
        Maps to one of: PASSED, FAILED, WARNING, NOT_AVAILABLE, NO_DATA_AVAILABLE
        """
        if not state or not isinstance(state, str):
            return 'NOT_AVAILABLE'
        
        state_lower = state.lower()
        
        # Map Azure compliance states to Security Hub ReasonCode
        reason_code_map = {
            # Pass states
            'passed': 'PASSED',
            'pass': 'PASSED',
            'healthy': 'PASSED',
            'compliant': 'PASSED',
            
            # Fail states
            'failed': 'FAILED',
            'fail': 'FAILED',
            'unhealthy': 'FAILED',
            'non-compliant': 'FAILED',
            'noncompliant': 'FAILED',
            
            # Warning states
            'warning': 'WARNING',
            'degraded': 'WARNING',
            
            # Not available states
            'not_applicable': 'NOT_AVAILABLE',
            'notapplicable': 'NOT_AVAILABLE',
            'unknown': 'NOT_AVAILABLE',
            'pending': 'NOT_AVAILABLE',
            
            # No data states
            'nodata': 'NO_DATA_AVAILABLE',
            'no_data': 'NO_DATA_AVAILABLE'
        }
        
        return reason_code_map.get(state_lower, 'NOT_AVAILABLE')
    
    def _is_valid_value(self, value: Any) -> bool:
        """Check if a value is valid (not None, empty, or the string 'None')"""
        if value is None:
            return False
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == '' or stripped.lower() in ('none', 'unknown', 'n/a'):
                return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
        return True
    
    def _default_if_invalid(self, value: Any, default: Any = None) -> Any:
        """Return default if value is invalid, otherwise return value"""
        if not self._is_valid_value(value):
            return default
        return value
    
    def _omit_if_invalid(self, value: Any) -> Any:
        """Return None if value is invalid (for conditional field rendering)"""
        if not self._is_valid_value(value):
            return None
        return value
    
    def _extract_ip_from_address(self, address: str) -> str:
        """
        Extract IP address from address:port format.
        Handles both IPv4 and IPv6 with ports.
        
        Args:
            address: IP address potentially with port (e.g., '10.0.74.237:34171')
            
        Returns:
            Just the IP address without port
        """
        if not address or not isinstance(address, str):
            return ''
        
        # Check if port is present (contains colon)
        if ':' not in address:
            return address
        
        # Handle IPv6 (contains multiple colons)
        # IPv6 with port looks like: [2001:db8::1]:8080
        if address.startswith('['):
            # Extract IPv6 from brackets
            end_bracket = address.find(']')
            if end_bracket > 0:
                return address[1:end_bracket]
            return address
        
        # Handle IPv4 with port (single colon)
        # Count colons - if only one, it's IPv4:port
        if address.count(':') == 1:
            return address.split(':')[0]
        
        # Multiple colons without brackets = pure IPv6 without port
        return address
    
    def _extract_port_from_address(self, address: str) -> Optional[int]:
        """
        Extract port number from address:port format.
        
        Args:
            address: IP address potentially with port (e.g., '10.0.74.237:34171')
            
        Returns:
            Port number as integer, or None if no port present
        """
        if not address or not isinstance(address, str):
            return None
        
        # Check if port is present
        if ':' not in address:
            return None
        
        # Handle IPv6 with port: [2001:db8::1]:8080
        if address.startswith('['):
            bracket_end = address.find(']')
            if bracket_end > 0 and bracket_end < len(address) - 1:
                port_part = address[bracket_end+2:]  # Skip ']:'
                try:
                    return int(port_part)
                except (ValueError, IndexError):
                    return None
            return None
        
        # Handle IPv4 with port (single colon)
        if address.count(':') == 1:
            try:
                return int(address.split(':')[1])
            except (ValueError, IndexError):
                return None
        
        # Multiple colons without brackets = pure IPv6, no port
        return None
    
    def _map_compliance_status(self, status_code: str) -> str:
        """
        Map Azure assessment status codes to OCSF compliance status strings.
        
        Args:
            status_code: Azure status code (e.g., 'Healthy', 'Unhealthy', 'NotApplicable')
            
        Returns:
            OCSF compliance status string ('Pass', 'Fail', 'Skip', 'Unknown')
        """
        if not status_code or not isinstance(status_code, str):
            return 'Unknown'
        
        status_mapping = {
            'healthy': 'Pass',
            'unhealthy': 'Fail',
            'notapplicable': 'Skip',
            'not_applicable': 'Skip',
            'unknown': 'Unknown',
            # Additional status codes that might appear
            'low': 'Pass',
            'medium': 'Fail',
            'high': 'Fail',
            'critical': 'Fail',
        }
        return status_mapping.get(status_code.lower(), 'Unknown')
    
    def _map_compliance_status_id(self, status_code: str) -> int:
        """
        Map Azure assessment status codes to OCSF status_id integers.
        
        OCSF Compliance Finding status_id values:
            1 = Pass
            2 = Fail
            3 = Skip/NotApplicable
            99 = Unknown/Other
        
        Args:
            status_code: Azure status code (e.g., 'Healthy', 'Unhealthy', 'NotApplicable')
            
        Returns:
            OCSF status_id integer (1=Pass, 2=Fail, 3=Skip, 99=Unknown)
        """
        if not status_code or not isinstance(status_code, str):
            return 99  # Unknown
        
        status_id_mapping = {
            'healthy': 1,       # Pass
            'unhealthy': 2,     # Fail
            'notapplicable': 3, # Skip
            'not_applicable': 3, # Skip
            'unknown': 99,      # Unknown
            # Additional status codes that might appear
            'low': 1,           # Pass (low severity = acceptable)
            'medium': 2,        # Fail
            'high': 2,          # Fail
            'critical': 2,      # Fail
        }
        return status_id_mapping.get(status_code.lower(), 99)
    
    def _slugify(self, text: Any) -> str:
        """
        Convert text to URL-safe slug format for UIDs.
        
        Args:
            text: Input text to convert (e.g., "Defense Evasion")
            
        Returns:
            URL-safe slug (e.g., "defense-evasion")
        """
        if text is None:
            return ''
        
        # Convert to string if not already
        if not isinstance(text, str):
            text = str(text)
        
        # Handle empty string
        if not text.strip():
            return ''
        
        # Convert to lowercase
        slug = text.lower()
        
        # Replace spaces and special characters with hyphens
        # Keep only alphanumeric characters and hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        # Remove consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        return slug
    
    def _json_escape_string(self, text: str) -> str:
        """
        Properly escape a string for JSON by handling all control characters
        This is critical for descriptions that contain newlines, tabs, etc.
        
        Args:
            text: String to escape
            
        Returns:
            Properly escaped string safe for JSON
        """
        if not text or not isinstance(text, str):
            return ''
        
        # Use json.dumps to properly escape, then remove the surrounding quotes
        # This handles all control characters: \n, \r, \t, etc.
        escaped = json.dumps(text)[1:-1]  # Remove leading and trailing quotes
        return escaped
    
    def render_template(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render Jinja2 template with given context"""
        try:
            if self.env is None:
                raise ImportError("Jinja2 not available")
            
            # DEBUG: Log template rendering start
            self.logger.debug(f"JINJA2 DEBUG - Starting template render with {len(context)} context keys")
            
            template = self.env.from_string(template_str)
            
            # DEBUG: Log specific extractors that are commonly problematic
            extractors = context.get('extractors', {})
            problematic_fields = ['time_generated', 'start_time_utc', 'end_time_utc', 'intent', 'entities', 'resource_identifiers']
            for field in problematic_fields:
                value = extractors.get(field)
                self.logger.debug(f"JINJA2 DEBUG - {field}: {repr(value)} (type: {type(value).__name__})")
            
            rendered = template.render(**context)
            
            # DEBUG: Log rendered template summary (single-line for CloudWatch compatibility)
            self.logger.debug(f"JINJA2 DEBUG - Rendered template: {len(rendered)} chars")
            
            return rendered
            
        except Exception as e:
            self.logger.error(f"Template rendering failed: {str(e)}")
            raise TemplateError(f"Template rendering failed: {str(e)}")


class TemplateTransformer:
    """
    Main template-driven transformation engine
    Replaces hardcoded CloudTrailEventBuilder methods
    """
    
    def __init__(self, event_type_mappings: Dict[str, Dict[str, Any]], 
                 logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.event_type_mappings = event_type_mappings
        
        # Initialize components
        self.jsonpath_extractor = JSONPathExtractor(logger=self.logger)
        self.template_engine = TemplateEngine(logger=self.logger)
        
        # Template cache for Lambda performance
        self._template_cache = {}
        self._loaded_templates = {}
    
    def transform_event(self, azure_event: Dict[str, Any], aws_account_id: str,
                       event_type: str, output_format: str = 'cloudtrail') -> Optional[Union[CloudTrailAuditEvent, Dict[str, Any]]]:
        """
        Transform a single Azure event using templates
        
        Args:
            azure_event: Raw Azure event data
            aws_account_id: AWS account ID for the recipient
            event_type: Type of event (security_alert, secure_score, etc.)
            output_format: Output format ('cloudtrail' or 'ocsf')
            
        Returns:
            CloudTrailAuditEvent for CloudTrail format, Dict for OCSF format, or None if transformation fails
        """
        try:
            # Load transformation template for event type and format
            template = self._load_template(event_type, output_format)
            if not template:
                self.logger.warning(f"No {output_format} template found for event type: {event_type}")
                return None
            
            # Extract data using JSONPath expressions
            extracted_data = self._extract_template_data(azure_event, template)
            
            # Get event type configuration
            event_config = self.event_type_mappings.get(event_type, {})
            
            # Build template context
            # Get AWS region from environment or default
            aws_region = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
            
            context = {
                'extractors': extracted_data,
                'config': event_config,
                'aws_account_id': aws_account_id,
                'aws_region': aws_region,
                'event_type': event_type,
                'timestamp': datetime.utcnow().isoformat(),
                'azure_event': azure_event,  # For Azure template compatibility
                'gcp_event': azure_event,  # For GCP template compatibility (same event, different name)
                'generate_uuid': lambda: str(uuid.uuid4())  # Add as function, not filter
            }
            
            # Register template-specific filters if defined
            if template.filters:
                self._register_template_filters(template.filters)
            
            # Render template
            rendered_json = self.template_engine.render_template(template.template, context)
            
            # DEBUG: Log extracted data summary (single-line, no indent for CloudWatch compatibility)
            self.logger.debug(f"TEMPLATE DEBUG - Extracted data for {event_type}: {json.dumps(extracted_data, default=str)}")
            
            # DEBUG: Log template rendering context (single-line, no indent)
            context_debug = {k: v for k, v in context.items() if k != 'azure_event'}  # Exclude raw event for brevity
            self.logger.debug(f"TEMPLATE DEBUG - Template context: {json.dumps(context_debug, default=str)}")
            
            # Parse rendered JSON
            try:
                result_data = json.loads(rendered_json)
                self.logger.debug(f"Successfully parsed JSON with {len(result_data)} top-level fields")
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse rendered template JSON: {str(e)}")
                
                # Enhanced debugging for JSON parsing failures
                lines = rendered_json.split('\n')
                error_line_num = getattr(e, 'lineno', 1) - 1
                error_col = getattr(e, 'colno', 1) - 1
                
                self.logger.error(f"JSON ERROR at line {error_line_num + 1}, column {error_col + 1}")
                
                # Show context around error line
                start_line = max(0, error_line_num - 3)
                end_line = min(len(lines), error_line_num + 4)
                
                self.logger.error("JSON CONTEXT AROUND ERROR:")
                for i in range(start_line, end_line):
                    marker = " >>> " if i == error_line_num else "     "
                    line_content = lines[i] if i < len(lines) else ''
                    self.logger.error(f"{marker}Line {i+1:3}: {line_content}")
                    
                    # Show character position for error line
                    if i == error_line_num:
                        pointer = ' ' * (error_col + 10) + '^'  # 10 chars for line number prefix
                        self.logger.error(f"     Col {error_col+1:3}: {pointer}")
                
                # Also log full template for complete debugging (truncated for CloudWatch compatibility)
                self.logger.debug(f"FULL RENDERED TEMPLATE (first 1000 chars): {rendered_json[:1000]}...")
                
                # Show specific character around error position
                char_start = max(0, 5394 - 100)
                char_end = min(len(rendered_json), 5394 + 100)
                error_context = rendered_json[char_start:char_end]
                error_pos = 5394 - char_start
                self.logger.debug(f"CHARACTER CONTEXT (±100 chars around error pos {5394}):")
                self.logger.debug(f"'{error_context[:error_pos]}' >>> ERROR HERE >>> '{error_context[error_pos:]}'")
                raise
            
            # Log basic success without detailed template output
            if output_format in ['ocsf', 'ocsf_compliant']:
                self.logger.debug(f"OCSF event successfully generated with {len(result_data)} fields")
            elif output_format == 'asff':
                self.logger.debug(f"ASFF finding successfully generated with {len(result_data)} fields")
            
            # Return appropriate format
            if output_format == 'asff':
                # Return ASFF format as dictionary for Security Hub ingestion
                return result_data
            elif output_format in ['ocsf', 'ocsf_compliant']:
                # Optional OCSF validation (only if VALIDATE_OCSF environment variable is true)
                if VALIDATE_OCSF:
                    validation_result = self.validate_ocsf_event(result_data)
                    
                    if validation_result['valid']:
                        self.logger.info("=== OCSF VALIDATION: PASSED ===")
                        self.logger.info(f"Valid OCSF {validation_result['version']} event (class_uid: {validation_result['class_uid']})")
                        if validation_result['warnings']:
                            for warning in validation_result['warnings']:
                                self.logger.warning(f"OCSF Warning: {warning}")
                    else:
                        self.logger.error("=== OCSF VALIDATION: FAILED ===")
                        self.logger.error(f"Invalid OCSF event (class_uid: {validation_result.get('class_uid', 'unknown')})")
                        for error in validation_result['errors']:
                            self.logger.error(f"OCSF Error: {error}")
                        for warning in validation_result['warnings']:
                            self.logger.warning(f"OCSF Warning: {warning}")
                else:
                    self.logger.debug("OCSF validation skipped (VALIDATE_OCSF not enabled)")
                
                return result_data
            else:
                # Create CloudTrailAuditEvent for cloudtrail format
                # Always use UUID for CloudTrail compliance (Azure IDs too long/invalid chars)
                # Azure resource ID is preserved in the eventData/additionalEventData section
                cloudtrail_event_id = str(uuid.uuid4())
                return CloudTrailAuditEvent(
                    eventData=json.dumps(result_data.get('eventData', result_data)),
                    id=cloudtrail_event_id
                )
            
        except Exception as e:
            self.logger.error(
                f"Template transformation failed for event type {event_type} ({output_format}): {str(e)}",
                extra={'azure_event_keys': list(azure_event.keys()) if azure_event else []}
            )
            return None
    
    def _register_template_filters(self, filters_dict: Dict[str, str]) -> None:
        """
        Dynamically register template-specific filters with Jinja2 environment
        Supports filter inter-dependencies by executing all filters in shared namespace
        
        Args:
            filters_dict: Dictionary of filter_name -> filter_code from template
        """
        if not filters_dict or not self.template_engine.env:
            return
        
        try:
            # Create shared execution namespace for all filters
            exec_globals = {
                'datetime': datetime,
                'json': json,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'len': len,
                'dict': dict,
                'list': list,
            }
            exec_locals = {}
            
            # Execute all filter code in shared namespace to support inter-dependencies
            for filter_name, filter_code in filters_dict.items():
                try:
                    exec(filter_code, exec_globals, exec_locals)
                    
                    # Verify function was defined
                    if filter_name in exec_locals:
                        self.logger.debug(f"Executed filter code for: {filter_name}")
                    else:
                        self.logger.warning(f"Filter function {filter_name} not found after execution")
                except Exception as e:
                    self.logger.error(f"Failed to execute filter code for {filter_name}: {str(e)}")
            
            # CRITICAL: Make all loaded filters available to each other by updating exec_globals
            # This allows filter functions to call other filter functions (interdependencies)
            exec_globals.update(exec_locals)
            
            # Now register all successfully executed filters with Jinja2
            for filter_name in filters_dict.keys():
                if filter_name in exec_locals:
                    filter_func = exec_locals[filter_name]
                    self.template_engine.env.filters[filter_name] = filter_func
                    self.logger.debug(f"Registered template filter: {filter_name}")
                    
        except Exception as e:
            self.logger.error(f"Failed to register template filters: {str(e)}")
    
    def _extract_template_data(self, azure_event: Dict[str, Any], 
                              template: TransformationTemplate) -> Dict[str, Any]:
        """Extract data from Azure event using template's JSONPath expressions"""
        extracted = {}
        
        for field_name, jsonpath_expr in template.extractors.items():
            try:
                value = self.jsonpath_extractor.extract(azure_event, jsonpath_expr)
                extracted[field_name] = value
                
                self.logger.debug(f"Extracted {field_name}: {value}")
                
            except Exception as e:
                self.logger.warning(f"Failed to extract {field_name} using '{jsonpath_expr}': {str(e)}")
                extracted[field_name] = None
        
        return extracted
    
    def _load_template(self, event_type: str, output_format: str = 'cloudtrail') -> Optional[TransformationTemplate]:
        """Load transformation template for event type and format (with caching)"""
        cache_key = f"{event_type}_{output_format}"
        
        if cache_key in self._loaded_templates:
            return self._loaded_templates[cache_key]
        
        # Try to load template file
        template_path = self._get_template_path(event_type, output_format)
        
        # Return None if template is explicitly null in mapping
        if template_path is None:
            self.logger.debug(f"Template explicitly disabled (null) for {event_type} ({output_format})")
            return None
        
        if not os.path.exists(template_path):
            self.logger.warning(f"Template file not found: {template_path}")
            return None
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)
            
            template = TransformationTemplate(
                name=template_data['name'],
                input_schema=template_data['input_schema'],
                output_schema=template_data['output_schema'],
                extractors=template_data['extractors'],
                template=template_data['template'],
                filters=template_data.get('filters'),
                conditionals=template_data.get('conditionals')
            )
            
            # Cache the loaded template
            self._loaded_templates[cache_key] = template
            
            self.logger.info(f"Loaded transformation template: {template.name} ({output_format})")
            return template
            
        except Exception as e:
            self.logger.error(f"Failed to load template for {event_type} ({output_format}): {str(e)}")
            return None
    
    def _get_template_path(self, event_type: str, output_format: str = 'cloudtrail') -> Optional[str]:
        """Get file path for transformation template using mapping configuration"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(current_dir, '..', 'templates')
        
        # Get template filename from mapping configuration
        event_config = self.event_type_mappings.get(event_type, {})
        template_key = f'{output_format}_template'
        
        if template_key in event_config:
            template_filename = event_config[template_key]
            # Return None if template is explicitly set to null in mapping
            if template_filename is None:
                self.logger.debug(f"Template explicitly set to null for {event_type} ({output_format})")
                return None
            # Additional defensive check to prevent os.path.join with None
            if not isinstance(template_filename, str) or not template_filename:
                self.logger.warning(f"Invalid template filename for {event_type} ({output_format}): {template_filename}")
                return None
            return os.path.join(templates_dir, template_filename)
        
        # Fallback to constructed filename if not in mapping
        return os.path.join(templates_dir, f'{event_type}_{output_format}.yaml')
    
    def get_supported_templates(self, output_format: str = 'cloudtrail') -> List[str]:
        """Get list of available transformation templates for given format"""
        templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
        if not os.path.exists(templates_dir):
            return []
        
        templates = []
        suffix = f'_{output_format}.yaml'
        
        for filename in os.listdir(templates_dir):
            if filename.endswith(suffix):
                event_type = filename.replace(suffix, '')
                templates.append(event_type)
        
        return templates
    
    def get_all_supported_templates(self) -> Dict[str, List[str]]:
        """Get all available templates grouped by output format"""
        return {
            'cloudtrail': self.get_supported_templates('cloudtrail'),
            'ocsf': self.get_supported_templates('ocsf'),
            'asff': self.get_supported_templates('asff')
        }
    
    def validate_template(self, template: TransformationTemplate) -> bool:
        """Validate transformation template structure and syntax"""
        try:
            # Validate required fields
            required_fields = ['name', 'input_schema', 'output_schema', 'extractors', 'template']
            for field in required_fields:
                if not hasattr(template, field) or getattr(template, field) is None:
                    self.logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate extractors structure
            if not isinstance(template.extractors, dict):
                self.logger.error("Extractors must be a dictionary")
                return False
            
            if len(template.extractors) == 0:
                self.logger.error("Template must have at least one extractor")
                return False
            
            # Validate JSONPath expressions
            for field_name, jsonpath_expr in template.extractors.items():
                if not isinstance(jsonpath_expr, str) or not jsonpath_expr.strip():
                    self.logger.error(f"Invalid JSONPath expression for {field_name}: must be non-empty string")
                    return False
                    
                compiled = self.jsonpath_extractor._compile_expression(jsonpath_expr)
                if compiled is None:
                    self.logger.error(f"Invalid JSONPath expression for {field_name}: {jsonpath_expr}")
                    return False
            
            # Validate template string
            if not isinstance(template.template, str) or not template.template.strip():
                self.logger.error("Template must be a non-empty string")
                return False
            
            # Validate Jinja2 template syntax
            if self.template_engine.env:
                try:
                    compiled_template = self.template_engine.env.from_string(template.template)
                    
                    # Test template with mock data to catch runtime errors
                    mock_context = {
                        'extractors': {name: f'mock_value_{i}' for i, name in enumerate(template.extractors.keys())},
                        'config': {'event_source': 'test', 'user_agent': 'test', 'ocsf_class': 'test'},
                        'aws_account_id': '123456789012',
                        'event_type': 'test',
                        'timestamp': '2025-01-01T00:00:00Z'
                    }
                    
                    rendered = compiled_template.render(**mock_context)
                    
                    # Validate that rendered output is valid JSON
                    json.loads(rendered)
                    
                except TemplateError as e:
                    self.logger.error(f"Invalid Jinja2 template: {str(e)}")
                    return False
                except json.JSONDecodeError as e:
                    self.logger.error(f"Template does not produce valid JSON: {str(e)}")
                    return False
            
            # Validate schema names
            valid_input_schemas = ['azure_security_alert', 'azure_secure_score', 'azure_generic_event']
            valid_output_schemas = ['cloudtrail_audit_event', 'ocsf_event']
            
            if template.input_schema not in valid_input_schemas:
                self.logger.warning(f"Unknown input schema: {template.input_schema}")
            
            if template.output_schema not in valid_output_schemas:
                self.logger.warning(f"Unknown output schema: {template.output_schema}")
            
            self.logger.info(f"Template validation passed for: {template.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Template validation failed: {str(e)}")
            return False
    
    def validate_all_templates(self) -> Dict[str, bool]:
        """Validate all available templates and return results"""
        validation_results = {}
        
        available_templates = self.get_supported_templates()
        
        for event_type in available_templates:
            try:
                template = self._load_template(event_type)
                if template:
                    validation_results[event_type] = self.validate_template(template)
                else:
                    validation_results[event_type] = False
                    self.logger.error(f"Failed to load template for {event_type}")
            except Exception as e:
                validation_results[event_type] = False
                self.logger.error(f"Exception validating template {event_type}: {str(e)}")
        
        # Log summary
        passed = sum(1 for result in validation_results.values() if result)
        total = len(validation_results)
        
        self.logger.info(f"Template validation summary: {passed}/{total} templates passed")
        
        return validation_results
    
    def validate_ocsf_event(self, ocsf_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate OCSF event using Amazon Security Lake validation approach
        
        Args:
            ocsf_event: OCSF-formatted event to validate
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'class_uid': None,
            'version': None,
            'profiles': []
        }
        
        try:
            # Step 1: Check required fields (from validate.py lines 517-526)
            if 'class_uid' not in ocsf_event:
                validation_result['errors'].append("The class_uid field has not been defined")
                return validation_result
            
            if 'metadata' not in ocsf_event or 'version' not in ocsf_event['metadata']:
                validation_result['errors'].append("The version field has not been defined within metadata")
                return validation_result
            
            class_uid = str(ocsf_event['class_uid'])
            version = ocsf_event['metadata']['version']
            profiles = ocsf_event['metadata'].get('profiles', [])
            
            validation_result['class_uid'] = class_uid
            validation_result['version'] = version
            validation_result['profiles'] = profiles
            
            # Step 2: Validate version support (from validate.py lines 538-540)
            if version not in ["1.7.0", "1.1.0", "1.0.0-rc.2"]:
                validation_result['errors'].append(f"{version} is not a supported OCSF schema version. Please ensure the schema version is one of the following: 1.7.0, 1.1.0, 1.0.0-rc.2")
                return validation_result
            
            # Step 3: Validate class_uid exists (from validate.py lines 541-545)
            if version not in OCSF_CLASS_DICTIONARY or class_uid not in OCSF_CLASS_DICTIONARY[version]:
                validation_result['errors'].append(f"The class_uid: {class_uid} is not defined within OCSF {version}")
                return validation_result
            
            expected_class_info = OCSF_CLASS_DICTIONARY[version][class_uid]
            
            # Step 4: Validate class consistency (from validate.py lines 565-576)
            if 'class_name' in ocsf_event:
                if ocsf_event['class_name'] != expected_class_info['class_name']:
                    validation_result['errors'].append(
                        f"The input contains the 'class name' value: {ocsf_event['class_name']}. "
                        f"Using OCSF class uid {class_uid} requires the 'class name' value: {expected_class_info['class_name']}"
                    )
            
            if 'category_name' in ocsf_event:
                if ocsf_event['category_name'] != expected_class_info['category_name']:
                    validation_result['errors'].append(
                        f"The input contains the 'category name' value: {ocsf_event['category_name']}. "
                        f"Using OCSF class uid {class_uid} requires the 'category name' value: {expected_class_info['category_name']}"
                    )
            
            if 'category_uid' in ocsf_event:
                if ocsf_event['category_uid'] != expected_class_info['category_uid']:
                    validation_result['errors'].append(
                        f"The input contains the 'category uid' value: {ocsf_event['category_uid']}. "
                        f"Using OCSF class uid {class_uid} requires the 'category uid' value: {expected_class_info['category_uid']}"
                    )
            
            # Step 5: Add deprecation warnings
            if class_uid == '2001':
                validation_result['warnings'].append("OCSF event class: Security Findings (2001) is deprecated!")
            
            # Step 6: Validate against official OCSF schema (if jsonschema available)
            if JSONSCHEMA_AVAILABLE and jsonschema:
                schema_validation = self._validate_against_ocsf_schema(ocsf_event, expected_class_info, version, profiles)
                validation_result['errors'].extend(schema_validation.get('errors', []))
                validation_result['warnings'].extend(schema_validation.get('warnings', []))
            else:
                validation_result['warnings'].append("jsonschema not available - skipping official OCSF schema validation")
            
            # If no errors, mark as valid
            validation_result['valid'] = len(validation_result['errors']) == 0
            
            return validation_result
            
        except Exception as e:
            validation_result['errors'].append(f"Exception during OCSF validation: {str(e)}")
            return validation_result
    
    def _validate_against_ocsf_schema(self, ocsf_event: Dict[str, Any],
                                     expected_class_info: Dict[str, Any],
                                     version: str, profiles: List[str]) -> Dict[str, Any]:
        """
        Basic OCSF event validation without downloading external schemas
        
        Args:
            ocsf_event: OCSF event to validate
            expected_class_info: Expected class information from OCSF_CLASS_DICTIONARY
            version: OCSF version
            profiles: OCSF profiles
            
        Returns:
            Dictionary with basic validation results
        """
        schema_validation = {'errors': [], 'warnings': []}
        
        try:
            # Clean event data (remove None values)
            cleaned_event = self._recursive_filter(ocsf_event, None, 'None')
            
            # Basic structural checks without downloading schemas
            
            # Check for basic required OCSF fields
            required_fields = ['version', 'class_uid', 'category_uid', 'activity_id', 'time']
            for field in required_fields:
                if field not in cleaned_event:
                    schema_validation['errors'].append(f"Missing required OCSF field: {field}")
            
            self.logger.debug("OCSF event passed basic structural validation (no external schema download)")
            
            return schema_validation
            
        except Exception as e:
            schema_validation['errors'].append(f"Exception during basic schema validation: {str(e)}")
            return schema_validation
    
    def _recursive_filter(self, item, *forbidden):
        """
        Recursively remove forbidden values from JSON object
        (From Amazon Security Lake validator lines 483-501)
        """
        if isinstance(item, list):
            return [self._recursive_filter(entry, *forbidden) for entry in item if entry not in forbidden]
        if isinstance(item, dict):
            result = {}
            for (key, value) in item.items():
                value = self._recursive_filter(value, *forbidden)
                if key not in forbidden and value not in forbidden:
                    result[key] = value
            return result
        return item