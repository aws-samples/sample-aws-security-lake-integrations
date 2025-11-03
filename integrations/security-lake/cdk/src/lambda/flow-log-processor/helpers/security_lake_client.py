"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Security Lake Client

This module handles writing OCSF records to AWS Security Lake as Parquet files.

Author: Jeremy Tirrell
Version: 1.0.0
"""

import json
import logging
import os
import io
from datetime import datetime, timezone
from typing import List, Dict, Any
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

# Import PyArrow for Parquet support
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info(f"PyArrow version {pa.__version__} loaded successfully")
except ImportError as e:
    PARQUET_AVAILABLE = False
    pa = None
    pq = None
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import PyArrow: {str(e)}")


class SecurityLakeClient:
    """AWS Security Lake client for writing OCSF records as Parquet files"""
    
    def __init__(self, s3_bucket: str, s3_path: str = '', region_name: str = 'us-east-1'):
        """
        Initialize Security Lake client
        
        Args:
            s3_bucket: Security Lake S3 bucket name
            s3_path: Optional S3 path prefix
            region_name: AWS region name
        """
        self.s3_bucket = s3_bucket
        self.s3_path = s3_path.strip('/') if s3_path else ''
        self.region_name = region_name
        self.s3_client = boto3.client('s3', region_name=region_name)
        logger.info(f"Initialized Security Lake client for bucket: {s3_bucket}")
    
    def write_ocsf_records(self, records: List[Dict[str, Any]], source_name: str = 'azure-flowlogs', account_id: str = 'unknown') -> bool:
        """
        Write OCSF records to Security Lake S3 bucket as Parquet
        
        Args:
            records: List of OCSF records
            source_name: Source name for the records
            account_id: Azure subscription ID for accountId partition
            
        Returns:
            True if successful, False otherwise
        """
        if not records:
            logger.warning("No records to write")
            return True
        
        if not PARQUET_AVAILABLE:
            logger.error("PyArrow not available - cannot write Parquet")
            return False
        
        try:
            # Create S3 key path
            timestamp = datetime.now(timezone.utc)
            s3_key = self._generate_s3_key(source_name, timestamp, account_id)
            
            # Create Parquet buffer
            parquet_buffer = self._create_parquet_buffer(records)
            
            logger.info(f"Writing {len(records)} OCSF records to S3: {s3_key}")
            
            # Write to S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=parquet_buffer,
                ContentType='application/octet-stream',
                Metadata={
                    'record_count': str(len(records)),
                    'source_name': source_name,
                    'event_class': 'Network Activity',
                    'ocsf_version': '1.0.0',
                    'format': 'parquet',
                    'compression': 'gzip'
                }
            )
            
            logger.info(f"Successfully wrote {len(records)} records to Security Lake")
            return True
            
        except ClientError as e:
            logger.error(f"S3 error writing to Security Lake: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error writing to Security Lake: {str(e)}")
            return False
    
    def _create_parquet_buffer(self, records: List[Dict[str, Any]]) -> bytes:
        """
        Create Apache Parquet buffer using PyArrow
        
        Args:
            records: List of OCSF records
            
        Returns:
            Parquet file as bytes
        """
        try:
            # Clean records for PyArrow
            cleaned_records = [self._clean_event_for_pyarrow(record) for record in records]
            
            # Create PyArrow table from records
            table = pa.Table.from_pylist(cleaned_records)
            
            logger.debug(f"Created PyArrow table with {table.num_rows} rows and {table.num_columns} columns")
            
            # Create in-memory buffer
            buffer = io.BytesIO()
            
            # Write to Parquet with GZIP compression
            pq.write_table(
                table,
                buffer,
                compression='gzip',
                use_dictionary=True,
                write_statistics=True
            )
            
            # Get buffer contents
            parquet_data = buffer.getvalue()
            buffer.close()
            
            parquet_size_mb = len(parquet_data) / (1024 * 1024)
            logger.debug(f"Created Parquet file: {len(records)} events, {parquet_size_mb:.2f}MB")
            
            return parquet_data
            
        except Exception as e:
            logger.error(f"Failed to create Parquet buffer: {str(e)}")
            raise
    
    def _clean_event_for_pyarrow(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean OCSF event for PyArrow compatibility
        
        Args:
            event: OCSF event dictionary
            
        Returns:
            Cleaned event
        """
        if isinstance(event, dict):
            cleaned = {}
            for key, value in event.items():
                # Sanitize keys
                clean_key = key.replace('$', '').replace('@', '').replace(' ', '_').replace('-', '_')
                
                if isinstance(value, dict):
                    cleaned_value = self._clean_event_for_pyarrow(value)
                    if cleaned_value:
                        cleaned[clean_key] = cleaned_value
                elif isinstance(value, list):
                    if value:
                        # Flatten string lists to avoid nesting issues
                        if all(isinstance(item, str) for item in value):
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
    
    def _generate_s3_key(self, source_name: str, timestamp: datetime, account_id: str = 'unknown') -> str:
        """
        Generate S3 key with Security Lake partitioning for flow logs
        
        Format: {s3_path}/region=unknown/accountid={subscriptionId}/eventday=YYYYMMDD/{uuid}.parquet
        
        Args:
            source_name: Source name (not used in path for flow logs)
            timestamp: Timestamp for partitioning
            account_id: Azure subscription ID extracted from flowLogResourceID
            
        Returns:
            S3 key path
        """
        event_day = timestamp.strftime('%Y%m%d')
        filename = f"{uuid4()}.parquet"
        
        # Build S3 key with azureFlowLog/flows subdirectory
        parts = [
            self.s3_path,
            f"region=Azure",
            f"accountid={account_id}",
            f"eventday={event_day}",
            filename
        ]
        
        s3_key = '/'.join([p for p in parts if p])
        logger.debug(f"Generated S3 key with account_id={account_id}: {s3_key}")
        return s3_key