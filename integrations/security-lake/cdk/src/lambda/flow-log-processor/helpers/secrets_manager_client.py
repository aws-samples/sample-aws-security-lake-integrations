"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

AWS Secrets Manager Client

This module handles retrieving secrets from AWS Secrets Manager.

Author: Jeremy Tirrell
Version: 1.0.0
"""

import json
import logging
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SecretsManagerClient:
    """AWS Secrets Manager client for retrieving credentials"""
    
    def __init__(self, region_name: str):
        """
        Initialize Secrets Manager client
        
        Args:
            region_name: AWS region name
        """
        self.region_name = region_name
        self.client = boto3.client('secretsmanager', region_name=region_name)
        logger.info(f"Initialized Secrets Manager client for region: {region_name}")
    
    def get_secret(self, secret_name: str) -> Optional[Dict]:
        """
        Retrieve secret value from Secrets Manager
        
        Args:
            secret_name: Name of the secret to retrieve
            
        Returns:
            Dictionary containing secret data, or None if retrieval fails
        """
        try:
            logger.info(f"Retrieving secret: {secret_name}")
            
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_string = response['SecretString']
            
            # Parse JSON secret
            secret_data = json.loads(secret_string)
            
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret_data
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"AWS Secrets Manager error: {error_code} - {error_message}")
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing secret JSON: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret: {str(e)}")
            return None