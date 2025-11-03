"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Security Lake Client for Security Lake Integration Framework

Shared Security Lake client for sending OCSF events to AWS Security Lake.
Handles Parquet file generation, S3 upload, and partitioning.
"""

import json
import logging
import os
import io
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

# Import numpy for array handling
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

# Parquet support using PyArrow
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
    logging.info(f"PyArrow version {pa.__version__} loaded successfully")
except ImportError as e:
    PARQUET_AVAILABLE = False
    pa = None
    pq = None
    logging.error(f"PyArrow import failed: {str(e)}")

class SecurityLakeClient:
    """
    Security Lake client for sending OCSF events as Parquet files
    
    Handles OCSF event submission to AWS Security Lake with:
    - PyArrow-based Parquet file generation
    - Proper S3 partitioning (region/accountid/eventday)
    - GZIP compression
    - Event validation and cleaning
    """
    
    def __init__(self, s3_bucket: str, source_configurations: List[Dict[str, Any]], 
                 s3_path: str = '', logger: logging.Logger = None):
        """
        Initialize Security Lake client
        
        Args:
            s3_bucket: Security Lake S3 bucket name
            source_configurations: List of OCSF event class configurations
            s3_path: Optional S3 path prefix (e.g., 'ext/sourcename/1.0/')
            logger: Logger instance (None for default logger)
        """
        self.s3_bucket = s3_bucket
        self.source_configurations = source_configurations
        self.s3_path = s3_path.strip('/') if s3_path else ''
        self.logger = logger or logging.getLogger(__name__)
        self.s3_client = boto3.client('s3', config=boto3.session.Config(signature_version='s3v4'))
        
        self.logger.info(f"Initialized Security Lake client", extra={
            'bucket': s3_bucket,
            's3_path': self.s3_path or '(root)',
            'source_count': len(source_configurations)
        })
        
    def validate_configuration(self) -> bool:
        """
        Validate Security Lake client configuration
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Validate bucket exists and is accessible
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            
            # Validate source configurations
            if not self.source_configurations:
                self.logger.error("No source configurations provided")
                return False
            
            # Validate each source has required fields
            for config in self.source_configurations:
                if 'sourceName' not in config:
                    self.logger.error(f"Invalid source configuration (missing sourceName): {config}")
                    return False
            
            self.logger.info("Security Lake client configuration is valid")
            return True
            
        except ClientError as e:
            self.logger.error(f"Failed to validate Security Lake configuration: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error validating configuration: {str(e)}")
            return False
    
    def send_events_to_security_lake(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Send OCSF events to Security Lake, grouped by event class
        
        Args:
            events: List of OCSF events (can be mixed event classes)
            
        Returns:
            Dictionary with success/failure counts
        """
        if not events:
            self.logger.warning("No events provided to send to Security Lake")
            return {'successful': 0, 'failed': 0}
        
        # Group events by class_name
        events_by_class = {}
        for event in events:
            class_name = event.get('class_name', 'Unknown')
            if class_name not in events_by_class:
                events_by_class[class_name] = []
            events_by_class[class_name].append(event)
        
        # Send each group
        total_successful = 0
        total_failed = 0
        
        for event_class, class_events in events_by_class.items():
            result = self.send_ocsf_events(class_events, event_class)
            total_successful += result['successful']
            total_failed += result['failed']
        
        return {'successful': total_successful, 'failed': total_failed}
    
    def send_ocsf_events(self, events: List[Dict[str, Any]], event_class: str) -> Dict[str, int]:
        """
        Send OCSF events to Security Lake as Parquet using PyArrow
        
        Args:
            events: List of OCSF events (all same event class)
            event_class: OCSF event class name (e.g., 'Compliance Finding')
            
        Returns:
            Dictionary with success/failure counts
        """
        if not events:
            self.logger.warning("No events provided")
            return {'successful': 0, 'failed': 0}
            
        if not PARQUET_AVAILABLE:
            self.logger.error("Parquet format not available - cannot send events to Security Lake")
            return {'successful': 0, 'failed': len(events)}
        
        try:
            # Use first configuration as default source name
            if not self.source_configurations:
                self.logger.error(f"No source configurations available for event class: {event_class}")
                return {'successful': 0, 'failed': len(events)}
            
            source_name = self.source_configurations[0].get('sourceName', 'defaultSource')
            
            # Get region and account ID for partitioning
            region = os.environ.get('AWS_REGION', 'us-east-1')
            first_event = events[0] if events else {}
            account_id = first_event.get('cloud', {}).get('account', {}).get('uid', 'unknown')
            
            # Generate S3 key with partitioning
            timestamp = datetime.now(timezone.utc)
            s3_key = self._generate_s3_key(source_name, event_class, timestamp, region, account_id)
            
            # Create Parquet buffer
            parquet_buffer = self._create_parquet_buffer(events, event_class)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=parquet_buffer,
                ContentType='application/octet-stream',
                Metadata={
                    'source': source_name,
                    'event_class': event_class,
                    'event_count': str(len(events)),
                    'ocsf_version': '1.1.0',
                    'format': 'parquet',
                    'compression': 'gzip'
                }
            )
            
            self.logger.info(f"Successfully sent {len(events)} {event_class} events to Security Lake at {s3_key}")
            
            return {'successful': len(events), 'failed': 0}
            
        except Exception as e:
            self.logger.error(f"Failed to send events to Security Lake: {str(e)}")
            return {'successful': 0, 'failed': len(events)}
    
    def _create_parquet_buffer(self, events: List[Dict[str, Any]], event_class: str) -> bytes:
        """
        Create Parquet buffer using PyArrow
        
        Args:
            events: List of OCSF events (same event class)
            event_class: OCSF event class name
            
        Returns:
            Parquet file as bytes buffer
        """
        try:
            # Clean events
            cleaned_events = [self._clean_event_for_pyarrow(event) for event in events]
            
            if pa is None or pq is None:
                raise Exception("PyArrow modules not available")
            
            # Convert numpy arrays to Python lists if needed
            if NUMPY_AVAILABLE and np is not None:
                cleaned_events = [self._denumpyify(event) for event in cleaned_events]
            
            # Create PyArrow table
            table = pa.Table.from_pylist(cleaned_events)
            
            # Create buffer
            buffer = io.BytesIO()
            
            # Write Parquet with GZIP compression
            pq.write_table(
                table,
                buffer,
                compression='gzip',
                use_dictionary=True,
                write_statistics=True
            )
            
            parquet_data = buffer.getvalue()
            buffer.close()
            
            parquet_size_mb = len(parquet_data) / (1024 * 1024)
            self.logger.debug(f"Created Parquet file: {len(events)} events, {parquet_size_mb:.2f}MB")
            
            return parquet_data
            
        except Exception as e:
            self.logger.error(f"Failed to create Parquet buffer: {str(e)}")
            raise
    
    def _clean_event_for_pyarrow(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean OCSF event for PyArrow compatibility
        
        Removes empty dicts/lists, sanitizes field names, drops metadata.
        
        Args:
            event: OCSF event dictionary
            
        Returns:
            Cleaned event
        """
        if isinstance(event, dict):
            cleaned = {}
            for key, value in event.items():
                # Drop event_metadata field
                if key == 'event_metadata':
                    continue
                
                # Sanitize key names
                clean_key = self._sanitize_field_name(key)
                
                if isinstance(value, dict):
                    cleaned_value = self._clean_event_for_pyarrow(value)
                    if cleaned_value:
                        cleaned[clean_key] = cleaned_value
                elif isinstance(value, list):
                    if value:
                        if all(isinstance(item, str) for item in value):
                            # Flatten string lists to comma-separated
                            cleaned[clean_key] = ','.join(value)
                        else:
                            cleaned_list = [self._clean_event_for_pyarrow(item) for item in value]
                            cleaned_list = [item for item in cleaned_list if item not in (None, {}, [])]
                            if cleaned_list:
                                cleaned[clean_key] = cleaned_list
                elif value is not None:
                    cleaned[clean_key] = value
            return cleaned
        elif isinstance(event, list):
            cleaned_list = [self._clean_event_for_pyarrow(item) for item in event]
            return [item for item in cleaned_list if item not in (None, {}, [])]
        else:
            return event
    
    def _sanitize_field_name(self, field_name: str) -> str:
        """
        Sanitize field name for Parquet compatibility
        
        Args:
            field_name: Original field name
            
        Returns:
            Sanitized field name
        """
        if not isinstance(field_name, str):
            return str(field_name)
        
        # Remove byte string prefix if present
        if field_name.startswith("b'") and field_name.endswith("'"):
            field_name = field_name[2:-1]
        elif field_name.startswith('b"') and field_name.endswith('"'):
            field_name = field_name[2:-1]
        
        # Remove invalid characters
        sanitized = (field_name.replace('$', '')
                                .replace('@', '')
                                .replace('(', '')
                                .replace(')', '')
                                .replace(' ', '_')
                                .replace('-', '_'))
        
        return sanitized
    
    def _denumpyify(self, obj):
        """
        Recursively convert numpy arrays to Python lists
        
        Args:
            obj: Object to convert
            
        Returns:
            Object with numpy arrays converted to lists
        """
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self._denumpyify(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._denumpyify(item) for item in obj]
        else:
            return obj
    
    def _generate_s3_key(self, source_name: str, event_class: str, timestamp: datetime,
                         region: str = 'unknown', account_id: str = 'unknown') -> str:
        """
        Generate S3 key with Security Lake partitioning
        
        Format: {s3_path}/region={region}/accountid={accountid}/eventday=YYYYMMDD/{sourceName}{uuid}.parquet
        
        Args:
            source_name: Source name from configuration
            event_class: OCSF event class name
            timestamp: Event timestamp for partitioning
            region: AWS region
            account_id: Account ID
            
        Returns:
            Complete S3 key path
        """
        event_day = timestamp.strftime('%Y%m%d')
        filename = f"{source_name}{uuid4()}.parquet"
        
        # Build S3 key with Security Lake partitioning
        parts = [
            self.s3_path,
            f"region={region}",
            f"accountid={account_id}",
            f"eventday={event_day}",
            filename
        ]
        
        # Filter out empty parts and join
        s3_key = '/'.join([p for p in parts if p])
        
        return s3_key