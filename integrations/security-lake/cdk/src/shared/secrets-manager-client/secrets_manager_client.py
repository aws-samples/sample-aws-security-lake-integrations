"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Secrets Manager Client for Security Lake Integration Framework

Shared Secrets Manager client for retrieving credentials across all integration modules.
Handles credential retrieval, validation, and caching.
"""

import json
import logging
from typing import Dict, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

class SecretsManagerClient:
    """
    AWS Secrets Manager client for retrieving integration credentials
    
    Provides methods for retrieving and validating secrets from Secrets Manager.
    Designed for reuse across all integration modules.
    """
    
    def __init__(self, region: str, logger: logging.Logger = None):
        """
        Initialize Secrets Manager client
        
        Args:
            region: AWS region for Secrets Manager
            logger: Logger instance (None for default logger)
        """
        self.region = region
        self.logger = logger or logging.getLogger(__name__)
        self.client = boto3.client('secretsmanager', region_name=region)
        
        self.logger.info(f"SecretsManagerClient initialized for region: {region}")
    
    def get_secret(self, secret_name: str, required_fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve secret from Secrets Manager with optional field validation
        
        Args:
            secret_name: Name of the secret to retrieve
            required_fields: Optional list of required fields in the secret
            
        Returns:
            Dictionary containing secret data, or None if retrieval fails
        """
        try:
            self.logger.info(f"Retrieving secret: {secret_name}")
            
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_string = response['SecretString']
            
            # Parse the JSON secret
            secret_data = json.loads(secret_string)
            
            # Validate required fields if specified
            if required_fields:
                missing_fields = [field for field in required_fields if field not in secret_data]
                
                if missing_fields:
                    self.logger.error(f"Missing required fields in secret: {missing_fields}")
                    return None
            
            self.logger.info("Secret retrieved successfully", extra={
                'secret_name': secret_name,
                'has_required_fields': required_fields is None or len(required_fields) == 0 or not missing_fields
            })
            
            return secret_data
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            self.logger.error(f"AWS Secrets Manager error: {error_code} - {error_message}", extra={
                'secret_name': secret_name,
                'error_code': error_code
            })
            return None
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing secret JSON: {str(e)}", extra={
                'secret_name': secret_name
            })
            return None
            
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving secret: {str(e)}", extra={
                'secret_name': secret_name,
                'error_type': type(e).__name__
            })
            return None
    
    def update_secret(self, secret_name: str, secret_data: Dict[str, Any]) -> bool:
        """
        Update secret in Secrets Manager
        
        Args:
            secret_name: Name of the secret to update
            secret_data: Dictionary containing secret data
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            self.logger.info(f"Updating secret: {secret_name}")
            
            # Convert to JSON string
            secret_string = json.dumps(secret_data)
            
            # Update the secret
            self.client.update_secret(
                SecretId=secret_name,
                SecretString=secret_string
            )
            
            self.logger.info("Secret updated successfully", extra={
                'secret_name': secret_name
            })
            
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            self.logger.error(f"AWS Secrets Manager update error: {error_code} - {error_message}", extra={
                'secret_name': secret_name,
                'error_code': error_code
            })
            return False
            
        except Exception as e:
            self.logger.error(f"Unexpected error updating secret: {str(e)}", extra={
                'secret_name': secret_name,
                'error_type': type(e).__name__
            })
            return False