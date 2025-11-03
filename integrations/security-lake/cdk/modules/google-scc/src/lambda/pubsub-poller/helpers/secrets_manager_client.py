"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Secrets Manager Client for retrieving GCP credentials
"""

import json
import logging
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError


class SecretsManagerClient:
    """
    AWS Secrets Manager client for retrieving GCP Pub/Sub credentials
    """
    
    def __init__(self, region_name: str = None, logger: logging.Logger = None):
        """
        Initialize Secrets Manager client
        
        Args:
            region_name: AWS region name
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        
        try:
            self.client = boto3.client('secretsmanager', region_name=region_name)
            self.logger.info("Secrets Manager client initialized successfully", extra={
                'region': region_name
            })
        except Exception as e:
            self.logger.error(f"Failed to initialize Secrets Manager client: {str(e)}")
            raise
    
    def get_secret(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve secret value from AWS Secrets Manager
        
        Args:
            secret_name: Name or ARN of the secret
            
        Returns:
            Secret value as dictionary, or None if error
        """
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            
            # Parse secret string as JSON
            secret_string = response.get('SecretString')
            if secret_string:
                secret_data = json.loads(secret_string)
                self.logger.info(f"Retrieved secret successfully: {secret_name}")
                return secret_data
            else:
                self.logger.error(f"Secret has no SecretString: {secret_name}")
                return None
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            self.logger.error(
                f"Failed to retrieve secret from Secrets Manager",
                extra={
                    'secret_name': secret_name,
                    'error_code': error_code,
                    'error_message': e.response['Error']['Message']
                }
            )
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse secret as JSON: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving secret: {str(e)}")
            raise
    
    def get_gcp_credentials(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve GCP Pub/Sub credentials from Secrets Manager
        
        Expected secret format:
        {
          "projectId": "gcp-project-id",
          "subscriptionId": "subscription-id",
          "credentials": {
            "type": "service_account",
            "project_id": "gcp-project-id",
            "private_key_id": "...",
            "private_key": "...",
            "client_email": "...",
            "client_id": "...",
            "auth_uri": "...",
            "token_uri": "...",
            "auth_provider_x509_cert_url": "...",
            "client_x509_cert_url": "..."
          }
        }
        
        Args:
            secret_name: Name of the secret containing GCP credentials
            
        Returns:
            GCP credentials dictionary
        """
        secret_data = self.get_secret(secret_name)
        
        if not secret_data:
            return None
        
        # Validate required fields
        if 'credentials' in secret_data:
            credentials = secret_data['credentials']
            if isinstance(credentials, str):
                try:
                    credentials = json.loads(credentials)
                    secret_data['credentials'] = credentials
                except json.JSONDecodeError:
                    self.logger.error("Failed to parse credentials JSON string")
                    return None
        
        return secret_data
    
    def update_secret(self, secret_name: str, secret_value: Dict[str, Any]) -> bool:
        """
        Update secret value in Secrets Manager
        
        Args:
            secret_name: Name of the secret
            secret_value: New secret value as dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps(secret_value)
            )
            
            self.logger.info(f"Updated secret successfully: {secret_name}")
            return True
            
        except ClientError as e:
            self.logger.error(
                f"Failed to update secret",
                extra={
                    'secret_name': secret_name,
                    'error_code': e.response['Error']['Code'],
                    'error_message': e.response['Error']['Message']
                }
            )
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating secret: {str(e)}")
            return False