"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Azure Blob Storage Client

This module handles authentication and download operations
from Azure Blob Storage using Service Principal credentials.

Author: Jeremy Tirrell
Version: 1.0.0
"""

import logging
from typing import Optional

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, BlobClient

logger = logging.getLogger(__name__)


class AzureBlobClient:
    """Azure Blob Storage client for downloading flow logs"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, storage_account_name: str):
        """
        Initialize Azure Blob Storage client
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Service principal client ID
            client_secret: Service principal client secret
            storage_account_name: Azure Storage account name
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.storage_account_name = storage_account_name
        
        # Create credential
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Create blob service client
        account_url = f"https://{storage_account_name}.blob.core.windows.net"
        self.blob_service_client = BlobServiceClient(
            account_url=account_url,
            credential=self.credential
        )
        
        logger.info(f"Initialized Azure Blob client for storage account: {storage_account_name}")
    
    def download_blob(self, container_name: str, blob_name: str) -> Optional[bytes]:
        """
        Download blob content from Azure Storage
        
        Args:
            container_name: Name of the blob container
            blob_name: Name of the blob to download
            
        Returns:
            Blob content as bytes, or None if download fails
        """
        try:
            logger.info(f"Downloading blob: {blob_name} from container: {container_name}")
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            # Download blob
            download_stream = blob_client.download_blob()
            blob_data = download_stream.readall()
            
            logger.info(f"Successfully downloaded blob: {blob_name} ({len(blob_data)} bytes)")
            return blob_data
            
        except Exception as e:
            logger.error(f"Failed to download blob {blob_name}: {str(e)}")
            return None
    
    def list_blobs(self, container_name: str, prefix: Optional[str] = None) -> list:
        """
        List blobs in a container
        
        Args:
            container_name: Name of the blob container
            prefix: Optional prefix to filter blobs
            
        Returns:
            List of blob names
        """
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            
            blob_list = []
            for blob in container_client.list_blobs(name_starts_with=prefix):
                blob_list.append(blob.name)
            
            logger.info(f"Found {len(blob_list)} blobs in container {container_name}")
            return blob_list
            
        except Exception as e:
            logger.error(f"Failed to list blobs in container {container_name}: {str(e)}")
            return []