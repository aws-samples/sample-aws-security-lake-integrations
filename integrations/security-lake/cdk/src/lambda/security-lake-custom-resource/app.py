#!/usr/bin/env python3
"""
Security Lake Custom Resource Lambda Handler

This Lambda function manages Security Lake custom log sources via CloudFormation custom resources.
It handles CREATE, UPDATE, and DELETE operations for Security Lake integrations.

Author: SecureSight Team
Version: 1.0.0
"""

import json
import logging
import os
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
security_lake_client = boto3.client('securitylake')
iam_client = boto3.client('iam')
s3_client = boto3.client('s3')
sts_client = boto3.client('sts')
lakeformation_client = boto3.client('lakeformation')

# Constants
TIMEOUT_SECONDS = 60
SUCCESS = "SUCCESS"
FAILED = "FAILED"


class SecurityLakeCustomResourceError(Exception):
    """Custom exception for Security Lake custom resource operations"""
    pass


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for Security Lake custom resource operations.
    
    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context
        
    Returns:
        CloudFormation custom resource response
    """
    start_time = time.time()
    
    logger.info(f"Security Lake custom resource event received")
    logger.info(f"Request Type: {event.get('RequestType')}")
    logger.info(f"Resource Properties: {json.dumps(event, default=str, indent=2)}")
    
    # Extract event details
    request_type = event.get('RequestType')
    resource_properties = event.get('ResourceProperties', {})
    physical_resource_id = event.get('PhysicalResourceId', 'security-lake-custom-sources')
    
    response_data = {}
    status = SUCCESS
    reason = "Operation completed successfully"
    
    try:
        # Validate timeout
        remaining_time = context.get_remaining_time_in_millis() / 1000
        if remaining_time < 10:
            raise SecurityLakeCustomResourceError("Insufficient time remaining for operation")
        
        # Route to appropriate handler
        if request_type == 'Create':
            response_data = handle_create(resource_properties)
            physical_resource_id = response_data.get('PhysicalResourceId', physical_resource_id)
        elif request_type == 'Update':
            response_data = handle_update(resource_properties, physical_resource_id)
        elif request_type == 'Delete':
            response_data = handle_delete(resource_properties, physical_resource_id)
        else:
            raise SecurityLakeCustomResourceError(f"Unknown request type: {request_type}")
            
        logger.info(f"Security Lake {request_type} operation completed successfully")
        
    except Exception as error:
        logger.error(f"Security Lake {request_type} operation failed: {str(error)}", exc_info=True)
        status = FAILED
        reason = str(error)
        # Always include ProviderLocation attribute even on failure to prevent CDK errors
        response_data = {
            'ProviderLocation': '',  # Empty string on failure
            'Error': str(error),
            'FailedAt': datetime.utcnow().isoformat()
        }
    
    # Check timeout
    elapsed_time = time.time() - start_time
    if elapsed_time > TIMEOUT_SECONDS - 5:  # Leave 5 seconds buffer
        logger.warning(f"Operation approaching timeout: {elapsed_time}s elapsed")
    
    # Build response
    response = {
        'Status': status,
        'Reason': reason,
        'PhysicalResourceId': physical_resource_id,
        'StackId': event.get('StackId'),
        'RequestId': event.get('RequestId'),
        'LogicalResourceId': event.get('LogicalResourceId'),
        'Data': response_data
    }
    
    logger.info(f"Security Lake custom resource response: {json.dumps(response, default=str)}")
    return response


def check_custom_log_source_status(account_id: str, region: str, source_name: str) -> Dict[str, Any]:
    """
    Check the status of a custom log source in Security Lake.

    Args:
        account_id: AWS account ID
        region: AWS region
        source_name: Name of the custom log source

    Returns:
        Dict 
            exists: True if the custom log source is ready, False otherwise
            location: location of datasource
    """
    logger.info(f"Checking custom log source status for {source_name} in account {account_id} in region {region}")
    paginator = security_lake_client.get_paginator('list_log_sources')
    for page in paginator.paginate():
        for source in page.get('sources', []):
            for item in source.get('sources', []):
                if 'customLogSource' in item:
                    if item.get('customLogSource',{}).get('sourceName') == source_name:
                        logger.info(f"Found custom log source: {source}")
                        return { 'exists': True, 'location': item.get('customLogSource', {}).get('provider', {}).get('location','') }
    return { 'exists': False, 'location': ''}

def handle_create(resource_properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle CREATE operation for Security Lake custom log sources.
    
    Args:
        resource_properties: CloudFormation resource properties
        
    Returns:
        Response data with created resource details
    """
    logger.info("Starting Security Lake custom log source creation")
    
    # Extract configuration
    s3_bucket = resource_properties.get('S3Bucket')
    external_id = resource_properties.get('ExternalId')
    service_role_name = resource_properties.get('ServiceRole')  # Expect role name from config
    ocsf_configurations = resource_properties.get('OCSFEventClass', [])
    
    # Initialize variables that may be used in response
    physical_resource_id = 'security-lake-custom-sources'
    provider_location = ''
    
    # Validate required parameters with detailed logging
    missing_params = []
    if not s3_bucket:
        missing_params.append("S3Bucket")
    if not external_id:
        missing_params.append("ExternalId") 
    if not service_role_name:
        missing_params.append("ServiceRole")
    if not ocsf_configurations:
        missing_params.append("OCSFEventClass")
    
    if missing_params:
        error_msg = f"Missing required parameters: {', '.join(missing_params)}"
        logger.error(error_msg)
        raise SecurityLakeCustomResourceError(error_msg)
    
    # Get current AWS account and region
    account_info = sts_client.get_caller_identity()
    account_id = account_info['Account']
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Construct service role ARN from the provided role name
    service_role_arn = f"arn:aws:iam::{account_id}:role/{service_role_name}"
    
    logger.info(f"Creating Security Lake sources for account {account_id} in region {region}")
    logger.info(f"S3 Bucket: {s3_bucket}")
    logger.info(f"Service Role Name: {service_role_name}")
    logger.info(f"Service Role ARN: {service_role_arn}")
    logger.info(f"External ID: {external_id}")
    logger.info(f"OCSF Configurations: {len(ocsf_configurations)} source(s)")
    
    # Grant Lake Formation database permissions via API call
    database_name = f"amazon_security_lake_glue_db_{region.replace('-', '_')}"
    try:
        current_role_info = sts_client.get_caller_identity()
        assumed_role_arn = current_role_info.get('Arn', '')
        
        # Convert assumed role ARN to base role ARN for Lake Formation
        # Format: arn:aws:sts::account:assumed-role/role-name/session-name → arn:aws:iam::account:role/role-name
        if 'assumed-role' in assumed_role_arn:
            arn_parts = assumed_role_arn.split(':')
            if len(arn_parts) >= 6:
                account_id_from_arn = arn_parts[4]
                resource_part = arn_parts[5]  # assumed-role/role-name/session-name
                role_name = resource_part.split('/')[1]  # Extract role-name
                current_role_arn = f"arn:aws:iam::{account_id_from_arn}:role/{role_name}"
            else:
                current_role_arn = assumed_role_arn  # Fallback to original
        else:
            current_role_arn = assumed_role_arn
        
        logger.info(f"Assumed role ARN: {assumed_role_arn}")
        logger.info(f"Base role ARN for Lake Formation: {current_role_arn}")
        logger.info(f"Target Security Lake database: {database_name}")
        
        lakeformation_client.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': current_role_arn},
            Resource={'Database': {'CatalogId': account_id, 'Name': database_name}},
            Permissions=['CREATE_TABLE', 'ALTER', 'DROP', 'DESCRIBE']
        )
        
        logger.info("Successfully granted Lake Formation table creation permissions")
        
    except Exception as lf_error:
        logger.warning(f"Failed to grant Lake Formation permissions (will continue): {str(lf_error)}")
        # Don't fail the entire operation - Security Lake might work without explicit Lake Formation grants
      
    logger.info(f"Service role exists: {service_role_arn}")
    
    # Create custom log sources for each OCSF configuration
    created_sources = []
    last_provider_location = ''  # Track the last provider location for response
    for config in ocsf_configurations:
        # Security Lake source name must be exactly 20 characters and include 'securitylake'
        # Format: 'securitylake' (12 chars) + 8-char hash = 20 chars total
        original_source_name = config.get('sourceName', 'default')
        source_hash = hashlib.md5(original_source_name.encode()).hexdigest()[:8]
        source_name = f"securitylake{source_hash}"
        source_version = config.get('sourceVersion', '1.0')
        event_classes = config.get('eventClasses', [])
        
        logger.info(f"Generated Security Lake source name: {source_name} (from: {original_source_name})")
        
        if not source_name or not event_classes:
            logger.warning(f"Skipping invalid OCSF configuration: {config}")
            continue
        
        try:
            logger.info(f"Creating custom log source: {source_name} with event classes: {event_classes}")
            configuration = {
                    'crawlerConfiguration': {
                        'roleArn': service_role_arn
                    },
                    'providerIdentity': {
                        'externalId': external_id,
                        'principal': account_id
                    }
                }
            # Create custom log source
            logger.info(f"configuration: {json.dumps(configuration)} ")
            logger.info(f"eventClasses: {event_classes} ")
            logger.info(f"sourceName: {source_name} ")
            logger.info(f"sourceVersion: {source_version} ")
            check_status = check_custom_log_source_status(account_id=account_id, region=region, source_name=source_name)
            if check_status.get('exists', False):
                logger.info(f"Custom log source {source_name} already exists, in {check_status.get('location','')} skipping creation")
                provider_location_full = check_status.get('location', '')
            else:
                response = security_lake_client.create_custom_log_source(
                    configuration=configuration,
                    eventClasses=event_classes,
                    sourceName=source_name,
                    sourceVersion=source_version
                )
                # Extract source details
                source_info = response.get('source', {})
                provider_info = source_info.get('provider', {})
                provider_location_full = provider_info.get('location', '')
                
            # Extract just the S3 path without bucket (e.g., s3://bucket/path → path)
            current_provider_location = ""
            if provider_location_full.startswith('s3://'):
                # Parse S3 URI to extract path portion only
                # Format: s3://bucket-name/path → path
                s3_parts = provider_location_full.replace('s3://', '').split('/', 1)
                if len(s3_parts) > 1:
                    current_provider_location = s3_parts[1]  # Path portion only
                    logger.info(f"Extracted S3 path from {provider_location_full} → {current_provider_location}")
                else:
                    logger.warning(f"Could not extract path from provider location: {provider_location_full}")
            else:
                current_provider_location = provider_location_full
                logger.info(f"Using provider location as-is: {current_provider_location}")
            
            # Update the last provider location for the response
            last_provider_location = current_provider_location
            
            created_sources.append({
                'sourceName': source_name,
                'sourceVersion': source_version,
                'eventClasses': event_classes,
                'sourceArn': f"arn:aws:securitylake:{region}:{account_id}:data/lake/custom/{source_name}",
                'providerLocation': current_provider_location
            })
            
            physical_resource_id = f"security-lake-sources-{'-'.join(source_name)}"
            
            logger.info(f"Final provider location for {source_name}: {current_provider_location}")
            
            logger.info(f"Successfully created custom log source: {source_name}")
            
        except ClientError as error:
            error_code = error.response.get('Error', {}).get('Code', 'Unknown')
            error_message = error.response.get('Error', {}).get('Message', 'Unknown error')
            
            # Log the full error details first
            logger.error(f"SecurityLake API Error for source {source_name}: Code={error_code}, Message={error_message}")
            logger.error(f"Full error response: {json.dumps(error.response, default=str)}")
            
            # Handle different Security Lake API error types appropriately
            if error_code == 'ConflictException':
                logger.info(f"Custom log source {source_name} (ConflictException), attempting to retrieve details")
                logger.error(f"ConflictException: {error_message}")
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied creating source {source_name}: {error_message}")
                logger.error("Check IAM permissions for securitylake:CreateCustomLogSource and iam:PassRole")
                raise SecurityLakeCustomResourceError(f"Access denied creating {source_name}: {error_message}")
            elif error_code == 'BadRequestException':
                logger.error(f"Bad request creating source {source_name}: {error_message}")
                logger.error(f"Verify configuration parameters: sourceName={source_name}, eventClasses={event_classes}")
                raise SecurityLakeCustomResourceError(f"Bad request creating {source_name}: {error_message}")
            elif error_code == 'ThrottlingException':
                retry_after = error.response.get('Error', {}).get('retryAfterSeconds', 5)
                logger.warning(f"Throttling when creating {source_name}, should retry after {retry_after} seconds")
                logger.warning(f"Quota code: {error.response.get('Error', {}).get('quotaCode', 'Unknown')}")
                raise SecurityLakeCustomResourceError(f"Throttling creating {source_name}: retry after {retry_after}s")
            elif error_code == 'InternalServerException':
                logger.error(f"Internal server error creating source {source_name}: {error_message}")
                logger.error("This may be a transient issue, recommend retry")
                raise SecurityLakeCustomResourceError(f"Internal server error creating {source_name}: {error_message}")
            else:
                # Unknown or other error type
                logger.error(f"Unknown error creating custom log source {source_name}: ErrorCode={error_code}, ErrorMessage={error_message}")
                logger.error(f"Full error response: {json.dumps(error.response, default=str)}")
                raise SecurityLakeCustomResourceError(f"Failed to create custom log source {source_name}: {error_code} - {error_message}")
    
    # Always return success with ProviderLocation attribute (even if empty) to avoid CDK attribute errors
    response_data = {
        'PhysicalResourceId': physical_resource_id,
        'ServiceRoleArn': service_role_arn,
        'CustomLogSources': created_sources,
        'S3Bucket': s3_bucket,
        'Region': region,
        'AccountId': account_id,
        'ProviderLocation': last_provider_location or '',  # Always provide ProviderLocation attribute for CDK
        'CreatedAt': datetime.utcnow().isoformat()
    }
    
    logger.info(f"Returning custom resource response with ProviderLocation: '{last_provider_location}'")
    return response_data


def handle_update(resource_properties: Dict[str, Any], physical_resource_id: str) -> Dict[str, Any]:
    """
    Handle UPDATE operation for Security Lake custom log sources.
    
    Args:
        resource_properties: CloudFormation resource properties
        physical_resource_id: Physical resource identifier
        
    Returns:
        Response data with updated resource details
    """
    logger.info(f"Starting Security Lake custom log source update for {physical_resource_id}")
    
    logger.info("Performing update by recreating resources")
    
    return handle_create(resource_properties)


def handle_delete(resource_properties: Dict[str, Any], physical_resource_id: str) -> Dict[str, Any]:
    """
    Handle DELETE operation for Security Lake custom log sources.
    
    Args:
        resource_properties: CloudFormation resource properties
        physical_resource_id: Physical resource identifier
        
    Returns:
        Response data confirming deletion
    """
    logger.info(f"Starting Security Lake custom log source deletion for {physical_resource_id}")
    
    ocsf_configurations = resource_properties.get('OCSFEventClass', [])
    deleted_sources = []
    
    for config in ocsf_configurations:
        original_source_name = config.get('sourceName')
        
        if not original_source_name:
            continue
        
        # Generate the same Security Lake source name used during creation
        source_hash = hashlib.md5(original_source_name.encode()).hexdigest()[:8]
        source_name = f"securitylake{source_hash}"
        
        try:
            logger.info(f"Deleting custom log source: {source_name}")
            
            # Delete custom log source
            security_lake_client.delete_custom_log_source(
                sourceName=source_name,
                sourceVersion=config.get('sourceVersion', '1.0')
            )
            
            deleted_sources.append(source_name)
            logger.info(f"Successfully deleted custom log source: {source_name}")
            
        except ClientError as error:
            error_code = error.response.get('Error', {}).get('Code', 'Unknown')
            error_message = error.response.get('Error', {}).get('Message', 'Unknown error')
            
            # Log full error details
            logger.error(f"SecurityLake Delete API Error for source {source_name}: Code={error_code}, Message={error_message}")
            
            if error_code == 'ResourceNotFoundException':
                logger.info(f"Custom log source {source_name} not found (ResourceNotFoundException), considering as successfully deleted")
                deleted_sources.append(source_name)
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied when trying to delete {source_name}: {error_message}")
                # Continue with other sources rather than failing completely
            elif error_code == 'ThrottlingException':
                retry_after = error.response.get('Error', {}).get('retryAfterSeconds', 5)
                logger.warning(f"Throttling when deleting {source_name}, should retry after {retry_after} seconds")
                # Continue with other sources rather than failing completely
            else:
                logger.error(f"Failed to delete custom log source {source_name}: {error_code} - {error_message}")
                # Continue with other sources rather than failing completely
    
    logger.info(f"Successfully processed deletion of {len(deleted_sources)} Security Lake custom log sources")
    
    return {
        'DeletedSources': deleted_sources,
        'DeletedAt': datetime.utcnow().isoformat()
    }
