# © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
Template driven Event Mapper for transforming cloud security events to other formats

"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from core.cloudtrail_types import CloudTrailAuditEvent

# Try to import template transformer - gracefully handle if not available
try:
    from core.template_transformer import TemplateTransformer
    TEMPLATE_TRANSFORMER_AVAILABLE = True
except ImportError:
    TEMPLATE_TRANSFORMER_AVAILABLE = False
    TemplateTransformer = None


class CloudEventMapper:
    """
    Template driven Event Mapper for transforming cloud security events to other formats
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None, use_templates: bool = True):
        """
        Initialize the event mapper
        
        Args:
            logger: Logger instance for debugging and monitoring
            use_templates: Whether to use template-driven transformation (default: True)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.event_type_mappings = self._load_event_type_mappings()
        self.use_templates = use_templates and TEMPLATE_TRANSFORMER_AVAILABLE
        
        # Initialize template transformer if available and requested
        if self.use_templates:
            try:
                self.template_transformer = TemplateTransformer(
                    event_type_mappings=self.event_type_mappings,
                    logger=self.logger
                )
                self.logger.info("Template-driven transformation enabled")
            except Exception as e:
                self.logger.warning(f"Failed to initialize template transformer: {str(e)}, falling back to legacy methods")
                self.use_templates = False
                self.template_transformer = None
        else:
            self.template_transformer = None
            if not TEMPLATE_TRANSFORMER_AVAILABLE:
                self.logger.info("Template transformer not available, using legacy transformation methods")
            else:
                self.logger.info("Template transformation disabled, using legacy transformation methods")
    
    def map_cloud_event_to_cloudtrail(self, cloud_event: Dict[str, Any], aws_account_id: str,
                                      output_format: str = 'cloudtrail') -> Optional[Union[CloudTrailAuditEvent, Dict[str, Any]]]:
        """
        Map a single cloud event to specified output format (CloudTrail, OCSF, or ASFF)
        Uses template-driven transformation when available, falls back to legacy methods
        
        Args:
            cloud_event: Raw cloud event data from SQS
            aws_account_id: AWS account ID for the recipient
            output_format: Output format - 'cloudtrail', 'ocsf', or 'asff' (default: 'cloudtrail')
            
        Returns:
            CloudTrailAuditEvent for CloudTrail format, Dict for OCSF/ASFF formats, or None if mapping fails
        """
        try:
            event_type = self._determine_event_type(cloud_event)
            self.logger.debug(f"Determined event type: {event_type}")
            
            # Try template-driven transformation first
            if self.use_templates and self.template_transformer:
                try:
                    result = self.template_transformer.transform_event(
                        cloud_event, aws_account_id, event_type, output_format=output_format
                    )
                    if result:
                        self.logger.debug(f"Successfully transformed using template for {event_type} ({output_format})")
                        return result
                    else:
                        self.logger.warning(f"Template transformation returned None for {event_type} ({output_format}), falling back to legacy")
                except Exception as template_error:
                    self.logger.warning(
                        f"Template transformation failed for {event_type} ({output_format}): {str(template_error)}, falling back to legacy methods"
                    )
            
            # Fallback to legacy hardcoded transformation methods (only for cloudtrail format)
            if output_format != 'cloudtrail':
                self.logger.error(f"No template available for {event_type} with {output_format} format, and no legacy fallback exists")
                return None
            
            self.logger.debug(f"Using legacy transformation for {event_type}")
            
            if event_type == 'azure_security_alert':
                return CloudTrailEventBuilder.build_from_azure_security_alert(
                    cloud_event, aws_account_id
                )
            elif event_type == 'azure_secure_score':
                return CloudTrailEventBuilder.build_from_azure_secure_score(
                    cloud_event, aws_account_id
                )
            else:
                # Use generic builder for all other types
                return CloudTrailEventBuilder.build_generic_event(
                    cloud_event, aws_account_id
                )
                
        except Exception as e:
            # Safe extraction for error logging
            event_data = cloud_event.get('event_data', {})
            event_type = 'unknown'
            event_id = 'unknown'
            
            if isinstance(event_data, dict):
                event_type = event_data.get('type', 'unknown')
                event_id = event_data.get('id', 'unknown')
            
            # Log failed event as INFO for visibility
            self.logger.info(f"Failed to map cloud event: {json.dumps(cloud_event, default=str)}")
            
            self.logger.error(
                f"Failed to map cloud event to CloudTrail format",
                extra={
                    'error': str(e),
                    'event_type': event_type,
                    'event_id': event_id,
                    'transformation_method': 'template' if self.use_templates else 'legacy'
                }
            )
            return None
    
    def map_cloud_events_batch(self, cloud_events: List[Dict[str, Any]],
                              aws_account_id: str) -> List[CloudTrailAuditEvent]:
        """
        Map multiple cloud events to CloudTrail format
        
        Args:
            cloud_events: List of cloud events
            aws_account_id: AWS account ID
            
        Returns:
            List of successfully mapped CloudTrail events
        """
        cloudtrail_events = []
        successful_mappings = 0
        failed_mappings = 0
        
        for i, cloud_event in enumerate(cloud_events):
            try:
                cloudtrail_event = self.map_cloud_event_to_cloudtrail(cloud_event, aws_account_id)
                if cloudtrail_event:
                    cloudtrail_events.append(cloudtrail_event)
                    successful_mappings += 1
                else:
                    failed_mappings += 1
                    self.logger.warning(f"Failed to map cloud event {i}")
                    
            except Exception as e:
                failed_mappings += 1
                self.logger.error(
                    f"Error mapping cloud event {i}",
                    extra={'error': str(e)}
                )
        
        self.logger.info(
            f"Event mapping completed",
            extra={
                'total_events': len(cloud_events),
                'successful_mappings': successful_mappings,
                'failed_mappings': failed_mappings
            }
        )
        
        return cloudtrail_events
    
    def _determine_event_type(self, cloud_event: Dict[str, Any]) -> str:
        """
        Determine the type of cloud event for proper mapping using the event type mappings configuration
        
        Args:
            cloud_event: Cloud event data (Azure, GCP, etc.)
            
        Returns:
            Event type string
        """
        # Try event_data first (common format)
        event_data = cloud_event.get('event_data', {})
        
        # If no event_data, try data directly (alternative format from pub/sub poller)
        if not event_data:
            data = cloud_event.get('data', {})
            # For GCP VPC Flow Logs: data contains event_data wrapper
            if isinstance(data, dict) and 'event_data' in data:
                event_data = data['event_data']
                self.logger.debug(f"DIAGNOSTIC: Using data.event_data for GCP VPC Flow Logs")
            else:
                event_data = data
        
        # Ensure event_data is a dictionary
        if not isinstance(event_data, dict):
            self.logger.warning(f"event_data is not a dictionary: {type(event_data)}")
            return 'generic'
        
        self.logger.debug(f"DIAGNOSTIC: Event data keys: {list(event_data.keys())}")
        
        # Sort mappings by specificity (check detection_keys first, then by event_type_value length)
        sorted_mappings = sorted(
            [(k, v) for k, v in self.event_type_mappings.items() if k != 'generic'],
            key=lambda x: (
                len(x[1].get('detection_keys', [])) > 0,  # Prioritize detection_keys
                len(x[1].get('event_type_value', '')) if x[1].get('event_type_value') else 0
            ),
            reverse=True
        )
        
        # Iterate through sorted mappings to find a match
        for mapping_name, mapping_config in sorted_mappings:
            # Check if this mapping has detection_keys
            has_detection_keys = 'detection_keys' in mapping_config and mapping_config['detection_keys']
            all_keys_present = False
            
            if has_detection_keys:
                detection_keys = mapping_config['detection_keys']
                # Check if ALL detection keys are present (supports nested paths with dots)
                all_keys_present = True
                for key in detection_keys:
                    if '.' in key:
                        # Nested key - use _get_nested_value
                        value = self._get_nested_value(event_data, key)
                        if value is None or value == '':
                            all_keys_present = False
                            break
                    else:
                        # Simple key - direct check
                        if key not in event_data:
                            all_keys_present = False
                            break
            
            # Check event type matching
            event_type_key = mapping_config.get('event_type_key')
            expected_value = mapping_config.get('event_type_value')
            match_mode = mapping_config.get('event_type_match_mode', 'contains')
            
            # Get the actual value from event_data (support nested fields with dot notation)
            actual_value = self._get_nested_value(event_data, event_type_key) if event_type_key else ''
            
            # Check if event_type_value matches
            event_type_matches = False
            if event_type_key and expected_value:
                self.logger.debug(f"DIAGNOSTIC: Checking {mapping_name}: key={event_type_key}, expected={expected_value}, actual={actual_value}, mode={match_mode}")
                
                # Apply match mode (use case-insensitive matching for contains/startswith since Azure resourceIds are uppercase)
                if match_mode == 'contains':
                    event_type_matches = expected_value.lower() in str(actual_value).lower()
                elif match_mode == 'exact' or match_mode == 'nested_exact':
                    event_type_matches = expected_value == str(actual_value)
                elif match_mode == 'startswith':
                    event_type_matches = str(actual_value).lower().startswith(expected_value.lower())
            
            # Determine if this mapping matches based on what criteria are configured
            # Case 1: Both detection_keys AND event_type matching configured - require BOTH to match
            if has_detection_keys and event_type_key and expected_value:
                if all_keys_present and event_type_matches:
                    self.logger.debug(f"DIAGNOSTIC: Classified as {mapping_name} (detection keys + event_type match)")
                    return mapping_name
            # Case 2: Only detection_keys configured (no event_type matching) - require detection_keys to match
            elif has_detection_keys and (not event_type_key or not expected_value):
                if all_keys_present:
                    self.logger.debug(f"DIAGNOSTIC: Classified as {mapping_name} (detection keys only match: {mapping_config['detection_keys']})")
                    return mapping_name
            # Case 3: Only event_type matching configured (no detection_keys) - require event_type to match
            elif not has_detection_keys and event_type_key and expected_value:
                if event_type_matches:
                    self.logger.debug(f"DIAGNOSTIC: Classified as {mapping_name} (event_type only match)")
                    return mapping_name
        
        # Default to generic mapping
        self.logger.debug(f"DIAGNOSTIC: Classified as generic (no specific match found)")
        return 'generic'
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """
        Get a value from nested dictionary using dot notation with array index support
        
        Args:
            data: Dictionary to extract value from
            key_path: Dot-separated path with optional array indices (e.g., 'finding.findingClass' or 'records[0].Type')
            
        Returns:
            The value at the path, or empty string if not found
        """
        if not key_path:
            return ''
        
        # Parse the key path to handle array indices
        import re
        
        # Split by dots but preserve array indices
        # e.g., "records[0].Type" -> ["records[0]", "Type"]
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            # Check if this key has an array index (e.g., "records[0]")
            array_match = re.match(r'^(.+)\[(\d+)\]$', key)
            
            if array_match:
                # Extract the base key and index
                base_key = array_match.group(1)
                index = int(array_match.group(2))
                
                # Navigate to the array
                if isinstance(current, dict):
                    current = current.get(base_key)
                    if current is None:
                        return ''
                else:
                    return ''
                
                # Access the array element
                if isinstance(current, list):
                    if index < len(current):
                        current = current[index]
                    else:
                        return ''
                else:
                    return ''
            else:
                # Simple key access
                if isinstance(current, dict):
                    current = current.get(key)
                    if current is None:
                        return ''
                else:
                    return ''
        
        return current
    
    def _load_event_type_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Load event type mappings configuration from JSON file
        Falls back to hardcoded configuration if file loading fails
        
        Returns:
            Event type mappings dictionary
        """
        # No default fallback mappings - require JSON configuration file
        default_mappings = {}
        
        try:
            # Get the Lambda function root directory (go up from core/ to function root)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            function_root = os.path.dirname(current_dir)  # Go up one level from core/
            config_file_path = os.path.join(function_root, 'mapping', 'event_type_mappings.json')
            
            # Check if the config file exists
            if os.path.exists(config_file_path):
                with open(config_file_path, 'r', encoding='utf-8') as f:
                    loaded_mappings = json.load(f)
                
                # Validate that loaded mappings have required fields
                if self._validate_mappings(loaded_mappings):
                    self.logger.info(f"Successfully loaded event type mappings from {config_file_path}")
                    return loaded_mappings
                else:
                    self.logger.warning("Loaded mappings failed validation, using default mappings")
                    return default_mappings
            else:
                self.logger.info(f"Configuration file not found at {config_file_path}, using default mappings")
                return default_mappings
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON configuration file: {str(e)}, using default mappings")
            return default_mappings
        except Exception as e:
            self.logger.error(f"Error loading event type mappings: {str(e)}, using default mappings")
            return default_mappings
    
    def _validate_mappings(self, mappings: Dict[str, Dict[str, Any]]) -> bool:
        """
        Validate that event type mappings have required fields
        
        Args:
            mappings: Event type mappings to validate
            
        Returns:
            True if mappings are valid, False otherwise
        """
        required_fields = ['event_source', 'event_name_prefix', 'user_agent', 'ocsf_class']
        optional_fields = ['event_type_key', 'event_type_value', 'event_type_match_mode', 'detection_keys',
                          'ocsf_template', 'asff_template', 'cloudtrail_template',
                          'asff_product_name', 'asff_product_id']
        
        try:
            if not isinstance(mappings, dict):
                self.logger.warning("Mappings is not a dictionary")
                return False
            
            for event_type, mapping in mappings.items():
                if not isinstance(mapping, dict):
                    self.logger.warning(f"Mapping for {event_type} is not a dictionary")
                    return False
                
                # Check required fields
                for field in required_fields:
                    if field not in mapping:
                        self.logger.warning(f"Missing required field '{field}' in mapping for {event_type}")
                        return False
                    
                    if not isinstance(mapping[field], str) or not mapping[field].strip():
                        self.logger.warning(f"Field '{field}' in mapping for {event_type} is empty or not a string")
                        return False
                
                # Validate event type matching configuration (if present)
                if 'event_type_key' in mapping or 'event_type_value' in mapping:
                    event_type_key = mapping.get('event_type_key')
                    event_type_value = mapping.get('event_type_value')
                    
                    # Allow null values for generic fallback type
                    if event_type != 'generic':
                        if not event_type_key or not event_type_value:
                            self.logger.warning(f"event_type_key and event_type_value must both be set for {event_type}")
                            return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating mappings: {str(e)}")
            return False
    
    def get_supported_event_types(self) -> List[str]:
        """
        Get list of supported cloud event types
        
        Returns:
            List of supported event type strings
        """
        return list(self.event_type_mappings.keys())
    
    def validate_cloud_event(self, cloud_event: Dict[str, Any]) -> bool:
        """
        Validate if a cloud event has the minimum required fields for mapping
        
        Args:
            cloud_event: Cloud event to validate
            
        Returns:
            True if event can be mapped, False otherwise
        """
        try:
            # Check for required top-level fields
            if 'event_data' not in cloud_event:
                self.logger.warning("Cloud event missing 'event_data' field")
                return False
            
            event_data = cloud_event['event_data']
            
            # Check for basic identifiers
            if not any(key in event_data for key in ['id', 'SystemAlertId', 'name']):
                self.logger.warning("Cloud event missing basic identifier fields")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating cloud event: {str(e)}")
            return False