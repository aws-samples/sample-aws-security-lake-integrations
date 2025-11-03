"""
AWS Secrets Manager Client for Azure Event Hub Credentials

This module handles retrieving Azure Event Hub connection details
from AWS Secrets Manager for secure credential storage.

Author: SecureSight Team
Version: 1.0.0
"""

import json
import logging
from typing import Dict, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

class SecretsManagerClient:
    """AWS Secrets Manager client for Azure Event Hub credentials"""
    
    def __init__(self, region: str):
        """
        Initialize Secrets Manager client
        
        Args:
            region: AWS region for Secrets Manager
        """
        self.region = region
        self.client = boto3.client('secretsmanager', region_name=region)
        logger.info(f"SecretsManagerClient initialized for region: {region}")
    
    def get_azure_credentials(self, secret_name: str) -> Optional[Dict[str, str]]:
        """
        Retrieve Azure Event Hub credentials from Secrets Manager
        
        Args:
            secret_name: Name of the secret containing Azure credentials
            
        Returns:
            Dictionary containing Azure Event Hub connection details:
            - connectionString: Azure Event Hub connection string
            - eventHubNamespace: Event Hub namespace name
            - eventHubName: Event Hub name
            - consumerGroup: Consumer group (defaults to $Default)
            
        Returns None if retrieval fails.
        """
        try:
            logger.info(f"Retrieving Azure credentials from secret: {secret_name}")
            
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_string = response['SecretString']
            
            # Parse the JSON secret
            credentials = json.loads(secret_string)
            
            # Validate required fields
            required_fields = ['connectionString', 'eventHubNamespace', 'eventHubName']
            missing_fields = [field for field in required_fields if field not in credentials]
            
            if missing_fields:
                logger.error(f"Missing required fields in secret: {missing_fields}")
                return None
            
            # Set default consumer group if not provided
            if 'consumerGroup' not in credentials:
                credentials['consumerGroup'] = '$Default'
            
            logger.info("Azure credentials retrieved successfully", extra={
                'secret_name': secret_name,
                'eventhub_namespace': credentials['eventHubNamespace'],
                'eventhub_name': credentials['eventHubName'],
                'consumer_group': credentials['consumerGroup']
            })
            
            return credentials
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"AWS Secrets Manager error: {error_code} - {error_message}", extra={
                'secret_name': secret_name,
                'error_code': error_code
            })
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing secret JSON: {str(e)}", extra={
                'secret_name': secret_name
            })
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error retrieving Azure credentials: {str(e)}", extra={
                'secret_name': secret_name,
                'error_type': type(e).__name__
            })
            return None
    
    def update_azure_credentials(self, secret_name: str, credentials: Dict[str, str]) -> bool:
        """
        Update Azure Event Hub credentials in Secrets Manager
        
        Args:
            secret_name: Name of the secret to update
            credentials: Dictionary containing Azure Event Hub connection details
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            logger.info(f"Updating Azure credentials in secret: {secret_name}")
            
            # Validate required fields
            required_fields = ['connectionString', 'eventHubNamespace', 'eventHubName']
            missing_fields = [field for field in required_fields if field not in credentials]
            
            if missing_fields:
                logger.error(f"Missing required fields for update: {missing_fields}")
                return False
            
            # Convert to JSON string
            secret_string = json.dumps(credentials)
            
            # Update the secret
            self.client.update_secret(
                SecretId=secret_name,
                SecretString=secret_string
            )
            
            logger.info("Azure credentials updated successfully", extra={
                'secret_name': secret_name,
                'eventhub_namespace': credentials['eventHubNamespace'],
                'eventhub_name': credentials['eventHubName']
            })
            
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"AWS Secrets Manager update error: {error_code} - {error_message}", extra={
                'secret_name': secret_name,
                'error_code': error_code
            })
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error updating Azure credentials: {str(e)}", extra={
                'secret_name': secret_name,
                'error_type': type(e).__name__
            })
            return False