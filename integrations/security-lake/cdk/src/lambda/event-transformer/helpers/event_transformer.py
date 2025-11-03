# © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
Event Transformer for converting cloud security events
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError
from core.event_mapper import CloudEventMapper
from core.cloudtrail_types import CloudTrailAuditEvent


class CloudTrailTransformer:
    """
    Transform cloud security events into CloudTrail Lake integration format
    for unified cross-cloud security monitoring
    """
    
    def __init__(self, event_data_store_arn: str, region_name: str = None, logger: logging.Logger = None,
                 channel_arn: str = None):
        """
        Initialize the CloudTrail transformer
        
        Args:
            event_data_store_arn: ARN of the CloudTrail Event Data Store (for reference)
            region_name: AWS region name
            logger: Logger instance
            channel_arn: ARN of the CloudTrail Channel (required for put_audit_events)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.event_data_store_arn = event_data_store_arn
        self.channel_arn = channel_arn
        self.event_mapper = CloudEventMapper(logger=self.logger)
        
        try:
            self.cloudtrail_data = boto3.client('cloudtrail-data', region_name=region_name)
            self.cloudtrail = boto3.client('cloudtrail', region_name=region_name)
            self.logger.info("CloudTrail clients initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize CloudTrail clients: {str(e)}")
            raise
            
        # If no channel ARN provided, we'll need to find or create one
        if not self.channel_arn:
            self.logger.warning("No Channel ARN provided. Will attempt to find existing channel for Event Data Store.")
    
    def transform_cloud_event(self, cloud_event: Dict[str, Any], aws_account_id: str) -> Optional[Dict[str, Any]]:
        """
        Transform a single cloud security event into CloudTrail format
        
        Args:
            cloud_event: Cloud security event data
            aws_account_id: AWS Account ID for the event
            
        Returns:
            CloudTrail formatted event as dict or None if transformation fails
        """
        try:
            # Validate the cloud event first
            if not self.event_mapper.validate_cloud_event(cloud_event):
                self.logger.warning("Cloud event failed validation, skipping transformation")
                return None
            
            # Map cloud event to CloudTrail format
            cloudtrail_event = self.event_mapper.map_cloud_event_to_cloudtrail(cloud_event, aws_account_id)
            
            if cloudtrail_event:
                # Convert to dict for CloudTrail API
                cloudtrail_dict = cloudtrail_event.to_dict()
                
                self.logger.debug(
                    f"Successfully transformed cloud event",
                    extra={
                        'cloud_event_type': self.event_mapper._determine_event_type(cloud_event),
                        'cloudtrail_event_id': cloudtrail_dict.get('id'),
                        'event_data_preview': str(cloudtrail_dict.get('eventData', ''))[:100] + '...'
                    }
                )
                
                return cloudtrail_dict
            else:
                self.logger.warning("Event mapper returned None for cloud event")
                return None
                
        except Exception as e:
            self.logger.error(
                f"Failed to transform cloud event to CloudTrail format",
                extra={
                    'cloud_event_id': cloud_event.get('event_data', {}).get('id', 'unknown'),
                    'error': str(e)
                }
            )
            return None
    
    def transform_events_batch(self, cloud_events: List[Dict[str, Any]], aws_account_id: str) -> List[Dict[str, Any]]:
        """
        Transform multiple cloud security events into CloudTrail format
        
        Args:
            cloud_events: List of cloud security events
            aws_account_id: AWS Account ID
            
        Returns:
            List of CloudTrail formatted events
        """
        self.logger.info(f"Starting batch transformation of {len(cloud_events)} cloud events")
        
        transformed_events = []
        transformation_stats = {
            'total_events': len(cloud_events),
            'successful_transformations': 0,
            'failed_transformations': 0,
            'skipped_events': 0,
            'event_types': {}
        }
        
        for i, cloud_event in enumerate(cloud_events):
            try:
                # Determine event type for statistics
                event_type = self.event_mapper._determine_event_type(cloud_event)
                transformation_stats['event_types'][event_type] = transformation_stats['event_types'].get(event_type, 0) + 1
                
                # Transform the event
                transformed_event = self.transform_cloud_event(cloud_event, aws_account_id)
                
                if transformed_event:
                    transformed_events.append(transformed_event)
                    transformation_stats['successful_transformations'] += 1
                else:
                    transformation_stats['skipped_events'] += 1
                    self.logger.warning(
                        f"Skipped cloud event {i} during transformation",
                        extra={'event_type': event_type}
                    )
                    
            except Exception as e:
                transformation_stats['failed_transformations'] += 1
                self.logger.error(
                    f"Error transforming cloud event {i}",
                    extra={
                        'error': str(e),
                        'event_data': cloud_event.get('event_data', {}).get('id', 'unknown')
                    }
                )
                # Continue processing other events
                continue
        
        self.logger.info(
            f"Batch transformation completed",
            extra=transformation_stats
        )
        
        return transformed_events
    
    def send_events_to_datastore(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Send CloudTrail transformed events to CloudTrail Event Data Store
        
        Args:
            events: List of CloudTrail formatted events
            
        Returns:
            Response from CloudTrail PutAuditEvents with statistics
        """
        try:
            if not events:
                self.logger.info("No events to send to Event Data Store")
                return {'Successful': 0, 'Failed': 0, 'Total': 0}
            
            self.logger.info(f"Sending {len(events)} CloudTrail events to CloudTrail Event Data Store")
            
            # CloudTrail PutAuditEvents accepts up to 100 events per call
            batch_size = 100
            total_successful = 0
            total_failed = 0
            total_batches = (len(events) + batch_size - 1) // batch_size
            
            for batch_num in range(0, len(events), batch_size):
                batch = events[batch_num:batch_num + batch_size]
                current_batch_number = (batch_num // batch_size) + 1
                
                try:
                    # Prepare audit events for CloudTrail with detailed logging
                    audit_events = []
                    for i, event in enumerate(batch):
                        try:
                            # Events should already be in the correct format from CloudTrailAuditEvent.to_dict()
                            audit_event = {
                                'eventData': event.get('eventData'),
                                'id': event.get('id', str(uuid.uuid4()))
                            }
                            
                            # Add eventDataChecksum if present
                            if event.get('eventDataChecksum'):
                                audit_event['eventDataChecksum'] = event['eventDataChecksum']
                            
                            audit_events.append(audit_event)
                            self.logger.debug(f"Prepared audit event {i+1}/{len(batch)} for CloudTrail")
                            
                        except Exception as prep_error:
                            self.logger.error(
                                f"Failed to prepare audit event {i+1} in batch {current_batch_number}: {str(prep_error)}",
                                extra={
                                    'prep_error': str(prep_error),
                                    'event_id': event.get('id', 'unknown'),
                                    'event_keys': list(event.keys()) if isinstance(event, dict) else 'not_dict'
                                }
                            )
                            raise  # Re-raise to fail the batch
                    
                    self.logger.debug(f"Sending batch {current_batch_number} with {len(audit_events)} events to CloudTrail")
                    
                    # Log event details for debugging
                    self.logger.info(f"Batch {current_batch_number} event details:")
                    for i, audit_event in enumerate(audit_events):
                        self.logger.info(f"  Event {i+1} - id: {audit_event.get('id', 'MISSING')}")
                        
                        # Parse and log key eventData fields
                        if audit_event.get('eventData'):
                            try:
                                event_data_obj = json.loads(audit_event['eventData'])
                                self.logger.info(f"    eventTime: '{event_data_obj.get('eventTime', 'MISSING')}'")
                                self.logger.info(f"    eventSource: '{event_data_obj.get('eventSource', 'MISSING')}'")
                                self.logger.info(f"    eventName: '{event_data_obj.get('eventName', 'MISSING')}'")
                                
                            except Exception as parse_error:
                                self.logger.error(f"    ERROR parsing eventData: {parse_error}")
                    
                    # Get the channel ARN for sending events
                    channel_arn = self._get_channel_arn()
                    if not channel_arn:
                        raise Exception("No valid Channel ARN available for sending events to Event Data Store")
                    
                    # Send batch to CloudTrail Channel (which forwards to Event Data Store)
                    self.logger.debug(f"Sending batch to Channel ARN: {channel_arn}")
                    response = self.cloudtrail_data.put_audit_events(
                        auditEvents=audit_events,
                        channelArn=channel_arn
                    )
                    
                    self.logger.debug(f"CloudTrail put_audit_events response: {response}")
                    
                    # Process response
                    successful = len(response.get('successful', []))
                    failed = len(response.get('failed', []))
                    
                    total_successful += successful
                    total_failed += failed
                    
                    self.logger.info(
                        f"Batch {current_batch_number}/{total_batches}: {successful} successful, {failed} failed"
                    )
                    
                    # Log any failures with details
                    if response.get('failed'):
                        for failed_event in response['failed']:
                            # Find the original event data for the failed event
                            failed_id = failed_event.get('id')
                            original_event = None
                            for original in audit_events:
                                if original.get('id') == failed_id:
                                    original_event = original
                                    break
                            
                            if original_event:
                                self.logger.info(f"Failed event: {original_event.get('eventData', 'N/A')}")
                            
                            self.logger.warning(
                                f"Failed to send event to Event Data Store",
                                extra={
                                    'event_id': failed_id,
                                    'error_code': failed_event.get('errorCode'),
                                    'error_message': failed_event.get('errorMessage'),
                                    'batch_number': current_batch_number
                                }
                            )
                
                except ClientError as e:
                    total_failed += len(batch)
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    self.logger.error(
                        f"Failed to send batch {current_batch_number} to Event Data Store - {error_code}: {error_message}",
                        extra={
                            'batch_size': len(batch),
                            'error_code': error_code,
                            'error_message': error_message,
                            'batch_number': current_batch_number,
                            'datastore_arn': self.event_data_store_arn
                        }
                    )
                
                except Exception as e:
                    total_failed += len(batch)
                    import traceback
                    
                    # Log detailed error information
                    self.logger.error(
                        f"DETAILED ERROR - Batch {current_batch_number} failed: {type(e).__name__}: {str(e)}",
                        extra={
                            'batch_size': len(batch),
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'batch_number': current_batch_number,
                            'datastore_arn': self.event_data_store_arn,
                            'first_event_id': batch[0].get('id', 'unknown') if batch else 'no_events'
                        }
                    )
                    
                    # Always log the full traceback for debugging
                    self.logger.error(f"FULL EXCEPTION TRACEBACK:\n{traceback.format_exc()}")
            
            # Final summary
            result = {
                'Total': len(events),
                'Successful': total_successful,
                'Failed': total_failed,
                'Batches': total_batches
            }
            
            self.logger.info(
                f"Event Data Store send operation completed",
                extra={
                    **result,
                    'datastore_arn': self.event_data_store_arn,
                    'success_rate': (total_successful / len(events)) * 100 if events else 0
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Critical error in send_events_to_datastore",
                extra={
                    'error': str(e),
                    'event_count': len(events),
                    'datastore_arn': self.event_data_store_arn
                }
            )
            raise
    
    def _get_channel_arn(self) -> Optional[str]:
        """
        Get CloudTrail Channel ARN from instance variable or environment variables.
        Does not create channels - only retrieves existing channel configuration.
        
        Returns:
            Channel ARN string if configured, None otherwise
        """
        import os
        
        try:
            # If channel ARN is already provided, use it
            if self.channel_arn:
                self.logger.debug(f"Using provided Channel ARN: {self.channel_arn}")
                return self.channel_arn
            
            # Check environment variable for Channel ARN
            channel_arn_env = os.getenv('CLOUDTRAIL_CHANNEL_ARN')
            if channel_arn_env:
                self.logger.info(f"Using Channel ARN from environment: {channel_arn_env}")
                self.channel_arn = channel_arn_env
                return channel_arn_env
            
            # No channel ARN configured
            self.logger.error("CLOUDTRAIL_CHANNEL_ARN environment variable is required but not set")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting channel ARN: {str(e)}")
            return None
    
    def get_transformation_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about supported event types and transformations
        
        Returns:
            Dictionary with transformation statistics
        """
        return {
            'supported_event_types': self.event_mapper.get_supported_event_types(),
            'event_type_mappings': self.event_mapper.event_type_mappings,
            'transformer_version': '3.0.0',
            'target_format': 'CloudTrail Lake Integration'
        }
    
    def validate_configuration(self) -> bool:
        """
        Validate transformer configuration and connectivity
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check CloudTrail client
            if not self.cloudtrail:
                self.logger.error("CloudTrail client not initialized")
                return False
            
            # Check Event Data Store ARN
            if not self.event_data_store_arn:
                self.logger.error("Event Data Store ARN not configured")
                return False
            
            # Validate event mapper
            if not self.event_mapper:
                self.logger.error("Event mapper not initialized")
                return False
            
            self.logger.info("Transformer configuration validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {str(e)}")
            return False


# Backward compatibility aliases
AzureToCloudTrailTransformer = CloudTrailTransformer
AzureToOCSFTransformer = CloudTrailTransformer