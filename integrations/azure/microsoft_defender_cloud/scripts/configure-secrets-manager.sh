#!/bin/bash

# Microsoft Defender for Cloud - Secrets Manager Configuration Script
# 
# This script automatically configures AWS Secrets Manager with Azure Event Hub
# credentials extracted from Terraform outputs, eliminating manual configuration.
#
# Author: SecureSight Team
# Version: 1.0.0

set -e  # Exit on any error

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TERRAFORM_DIR="../terraform"
CDK_DIR="../cdk"
AWS_REGION="ca-central-1"

echo -e "${BLUE}Microsoft Defender - Secrets Manager Configuration${NC}"
echo "=================================================================="

# Function to check if command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: $1 is not installed or not in PATH${NC}"
        exit 1
    fi
}

# Check required tools
echo -e "${BLUE}Checking required tools...${NC}"
check_command "terraform"
check_command "aws"
check_command "jq"

# Navigate to terraform directory
cd "$TERRAFORM_DIR"
echo -e "${BLUE}Changed to Terraform directory: $(pwd)${NC}"

# Get Terraform outputs
echo -e "${BLUE}Extracting Azure Event Hub configuration from Terraform...${NC}"

# Check if terraform state exists
if [ ! -f "terraform.tfstate" ]; then
    echo -e "${RED}Error: terraform.tfstate not found. Run 'terraform apply' first.${NC}"
    exit 1
fi

# Extract AWS Lambda configuration from Terraform output
AWS_LAMBDA_CONFIG=$(terraform output -json aws_lambda_configuration 2>/dev/null)

if [ -z "$AWS_LAMBDA_CONFIG" ] || [ "$AWS_LAMBDA_CONFIG" = "null" ]; then
    echo -e "${RED}Error: aws_lambda_configuration output not found in Terraform state${NC}"
    echo -e "${YELLOW}Tip: Make sure Terraform has been applied with the latest configuration${NC}"
    exit 1
fi

# Get the first (and likely only) region from the aws_lambda_configuration output
REGION=$(echo "$AWS_LAMBDA_CONFIG" | jq -r 'keys[0]')

if [ -z "$REGION" ] || [ "$REGION" = "null" ]; then
    echo -e "${RED}Error: No regions found in aws_lambda_configuration output${NC}"
    exit 1
fi

echo -e "${GREEN}Found AWS Lambda configuration for region: $REGION${NC}"

# Extract configuration for the detected region
LAMBDA_CONFIG=$(echo "$AWS_LAMBDA_CONFIG" | jq -r --arg region "$REGION" '.[$region]')

if [ -z "$LAMBDA_CONFIG" ] || [ "$LAMBDA_CONFIG" = "null" ]; then
    echo -e "${RED}Error: Configuration not found for region $REGION${NC}"
    exit 1
fi

# Extract individual values from aws_lambda_configuration output
EVENT_HUB_NAMESPACE=$(echo "$LAMBDA_CONFIG" | jq -r '.event_hub_namespace_name')
EVENT_HUB_NAME=$(echo "$LAMBDA_CONFIG" | jq -r '.event_hub_name')
CONNECTION_STRING=$(echo "$LAMBDA_CONFIG" | jq -r '.event_hub_connection_string')
CONSUMER_GROUP=$(echo "$LAMBDA_CONFIG" | jq -r '.consumer_group')

echo -e "${GREEN}Azure Event Hub configuration extracted:${NC}"
echo "   • Region: $REGION"
echo "   • Namespace: $EVENT_HUB_NAMESPACE"
echo "   • Event Hub: $EVENT_HUB_NAME" 
echo "   • Consumer Group: $CONSUMER_GROUP"
if [ ! -z "$CONNECTION_STRING" ] && [ "$CONNECTION_STRING" != "null" ]; then
    echo "   • Connection String: [REDACTED for security]"
else
    echo "   • Connection String: [NOT AVAILABLE - may need to be retrieved separately]"
fi

# Navigate to CDK directory to get AWS outputs
cd "../cdk"
echo -e "${BLUE}Changed to CDK directory: $(pwd)${NC}"

# Get CDK outputs for Secrets Manager secret name
echo -e "${BLUE}Extracting AWS Secrets Manager configuration from CDK...${NC}"

# Try to get the stack name dynamically first
echo -e "${BLUE}Looking for CDK stack...${NC}"
STACK_NAME=$(aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
    --region "$AWS_REGION" \
    --query 'StackSummaries[?contains(StackName, `mdc-cloudtrail-integration`)].StackName' \
    --output text 2>/dev/null)

if [ -z "$STACK_NAME" ] || [ "$STACK_NAME" = "None" ]; then
    echo -e "${YELLOW}CDK stack not found, using direct secret name approach${NC}"
    # Use the secret name directly from config.yaml
    SECRET_NAME="mdc-azure-eventhub-credentials"
else
    echo -e "${GREEN}Found CDK stack: $STACK_NAME${NC}"
    
    # Get CDK outputs for additional validation
    CDK_OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" \
        --query 'Stacks[0].Outputs' \
        --output json 2>/dev/null)

    if [ ! -z "$CDK_OUTPUTS" ]; then
        # Try to extract secret name from outputs
        EXTRACTED_SECRET_NAME=$(echo "$CDK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="AzureCredentialsSecretName") | .OutputValue' 2>/dev/null)
        if [ ! -z "$EXTRACTED_SECRET_NAME" ] && [ "$EXTRACTED_SECRET_NAME" != "null" ]; then
            SECRET_NAME="$EXTRACTED_SECRET_NAME"
        else
            # If no output exists, try to find the secret by looking for secrets matching the config pattern
            echo -e "${YELLOW}No AzureCredentialsSecretName output found, searching for existing secret...${NC}"
            FOUND_SECRET=$(aws secretsmanager list-secrets \
                --region "$AWS_REGION" \
                --query 'SecretList[?contains(Name, `azure-eventhub-credentials`)].Name' \
                --output text 2>/dev/null | head -1)
            
            if [ ! -z "$FOUND_SECRET" ] && [ "$FOUND_SECRET" != "None" ]; then
                SECRET_NAME="$FOUND_SECRET"
                echo -e "${GREEN}Found existing secret: $SECRET_NAME${NC}"
            else
                # Fallback to config.yaml value
                SECRET_NAME="mdc-azure-eventhub-credentials"
            fi
        fi
    else
        # If no CDK outputs, try to find the secret by searching
        echo -e "${YELLOW}No CDK outputs available, searching for existing secret...${NC}"
        FOUND_SECRET=$(aws secretsmanager list-secrets \
            --region "$AWS_REGION" \
            --query 'SecretList[?contains(Name, `azure-eventhub-credentials`)].Name' \
            --output text 2>/dev/null | head -1)
        
        if [ ! -z "$FOUND_SECRET" ] && [ "$FOUND_SECRET" != "None" ]; then
            SECRET_NAME="$FOUND_SECRET"
            echo -e "${GREEN}Found existing secret: $SECRET_NAME${NC}"
        else
            # Fallback to config.yaml value
            SECRET_NAME="mdc-azure-eventhub-credentials"
        fi
    fi
fi

echo -e "${GREEN}AWS Secrets Manager configuration found:${NC}"
echo "   • Secret Name: $SECRET_NAME"
echo "   • AWS Region: $AWS_REGION"

# Create the secret JSON
SECRET_JSON=$(jq -n \
    --arg conn "$CONNECTION_STRING" \
    --arg namespace "$EVENT_HUB_NAMESPACE" \
    --arg name "$EVENT_HUB_NAME" \
    --arg group "$CONSUMER_GROUP" \
    '{
        "connectionString": $conn,
        "eventHubNamespace": $namespace,
        "eventHubName": $name,
        "consumerGroup": $group
    }')

echo -e "${BLUE}Updating AWS Secrets Manager with Azure Event Hub credentials...${NC}"
echo -e "${BLUE}Secret Details:${NC}"
echo "   • Secret Name: $SECRET_NAME"
echo "   • AWS Region: $AWS_REGION"
echo "   • JSON Payload:"
echo "$SECRET_JSON" | jq '.'

echo -e "${BLUE}Executing AWS Secrets Manager operation...${NC}"

# Try to update the secret first, if it fails, create it
aws secretsmanager update-secret \
    --secret-id "$SECRET_NAME" \
    --secret-string "$SECRET_JSON" \
    --region "$AWS_REGION" 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}AWS Secrets Manager secret updated successfully!${NC}"
    SECRET_OPERATION="updated"
else
    echo -e "${YELLOW}Secret not found, creating new secret...${NC}"
    
    # Create the secret
    aws secretsmanager create-secret \
        --name "$SECRET_NAME" \
        --description "Azure Event Hub credentials for Microsoft Defender integration" \
        --secret-string "$SECRET_JSON" \
        --region "$AWS_REGION"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}AWS Secrets Manager secret created successfully!${NC}"
        SECRET_OPERATION="created"
    else
        echo -e "${RED}Error: Failed to create AWS Secrets Manager secret${NC}"
        echo -e "${YELLOW}Tip: Check AWS CLI credentials and permissions${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}Configuration Summary (Event Hub):${NC}"
echo "   • Secret Name: $SECRET_NAME (${SECRET_OPERATION})"
echo "   • Azure Region: $REGION"
echo "   • Event Hub: $EVENT_HUB_NAMESPACE/$EVENT_HUB_NAME"
echo "   • Consumer Group: $CONSUMER_GROUP"
echo "   • AWS Region: $AWS_REGION"

# ============================================================================
# AZURE FLOW LOGS CREDENTIALS CONFIGURATION
# ============================================================================

echo ""
echo -e "${BLUE}=================================================================${NC}"
echo -e "${BLUE}Configuring Azure Flow Logs Credentials${NC}"
echo -e "${BLUE}=================================================================${NC}"

# Navigate back to terraform directory
cd "$TERRAFORM_DIR"

# Extract Flow Logs App Registration credentials from Terraform output
echo -e "${BLUE}Extracting Azure Flow Logs App Registration credentials...${NC}"

FLOWLOG_CREDS=$(terraform output -json flowlog_ingestion_app_registration 2>/dev/null)

if [ -z "$FLOWLOG_CREDS" ] || [ "$FLOWLOG_CREDS" = "null" ]; then
    echo -e "${YELLOW}Warning: flowlog_ingestion_app_registration output not found${NC}"
    echo -e "${YELLOW}Flow logs may not be configured or vnet_ids may be empty${NC}"
    echo -e "${YELLOW}Skipping Flow Logs secret configuration${NC}"
else
    echo -e "${GREEN}Flow Logs App Registration credentials found${NC}"
    
    # Extract credentials
    FLOW_TENANT_ID=$(echo "$FLOWLOG_CREDS" | jq -r '.authentication.tenant_id')
    FLOW_CLIENT_ID=$(echo "$FLOWLOG_CREDS" | jq -r '.authentication.client_id')
    FLOW_CLIENT_SECRET=$(echo "$FLOWLOG_CREDS" | jq -r '.authentication.client_secret')
    FLOW_SUBSCRIPTION_ID=$(echo "$FLOWLOG_CREDS" | jq -r '.authentication.subscription_id')
    
    # Get first storage account details (assuming primary region)
    FLOW_STORAGE_ACCOUNT_NAME=$(echo "$FLOWLOG_CREDS" | jq -r '.storage_accounts | to_entries[0].value.name')
    FLOW_STORAGE_ACCOUNT_ID=$(echo "$FLOWLOG_CREDS" | jq -r '.storage_accounts | to_entries[0].value.id')
    
    echo -e "${GREEN}Flow Logs credentials extracted:${NC}"
    echo "   • Tenant ID: [REDACTED]"
    echo "   • Client ID: $FLOW_CLIENT_ID"
    echo "   • Client Secret: [REDACTED]"
    echo "   • Subscription ID: $FLOW_SUBSCRIPTION_ID"
    echo "   • Storage Account: $FLOW_STORAGE_ACCOUNT_NAME"
    
    # Navigate to CDK directory to get Flow Logs secret name
    cd "../cdk"
    
    # Find Flow Logs secret name from CDK outputs
    echo -e "${BLUE}Finding Azure Flow Logs secret name from CDK outputs...${NC}"
    
    if [ ! -z "$STACK_NAME" ] && [ "$STACK_NAME" != "None" ]; then
        FLOW_SECRET_NAME=$(echo "$CDK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="AzureFlowLogsSecretName") | .OutputValue' 2>/dev/null)
        
        if [ -z "$FLOW_SECRET_NAME" ] || [ "$FLOW_SECRET_NAME" = "null" ]; then
            # Search for existing secret
            echo -e "${YELLOW}No AzureFlowLogsSecretName output found, searching for existing secret...${NC}"
            FOUND_FLOW_SECRET=$(aws secretsmanager list-secrets \
                --region "$AWS_REGION" \
                --query 'SecretList[?contains(Name, `azure-flowlog-credentials`)].Name' \
                --output text 2>/dev/null | head -1)
            
            if [ ! -z "$FOUND_FLOW_SECRET" ] && [ "$FOUND_FLOW_SECRET" != "None" ]; then
                FLOW_SECRET_NAME="$FOUND_FLOW_SECRET"
                echo -e "${GREEN}Found existing Flow Logs secret: $FLOW_SECRET_NAME${NC}"
            else
                echo -e "${YELLOW}Flow Logs secret not found - may need to deploy CDK stack first${NC}"
                FLOW_SECRET_NAME=""
            fi
        fi
    else
        # Search for existing secret without stack name
        FOUND_FLOW_SECRET=$(aws secretsmanager list-secrets \
            --region "$AWS_REGION" \
            --query 'SecretList[?contains(Name, `azure-flowlog-credentials`)].Name' \
            --output text 2>/dev/null | head -1)
        
        if [ ! -z "$FOUND_FLOW_SECRET" ] && [ "$FOUND_FLOW_SECRET" != "None" ]; then
            FLOW_SECRET_NAME="$FOUND_FLOW_SECRET"
            echo -e "${GREEN}Found existing Flow Logs secret: $FLOW_SECRET_NAME${NC}"
        else
            echo -e "${YELLOW}Flow Logs secret not found${NC}"
            FLOW_SECRET_NAME=""
        fi
    fi
    
    if [ ! -z "$FLOW_SECRET_NAME" ]; then
        # Create the Flow Logs secret JSON
        FLOW_SECRET_JSON=$(jq -n \
            --arg tenant "$FLOW_TENANT_ID" \
            --arg client "$FLOW_CLIENT_ID" \
            --arg secret "$FLOW_CLIENT_SECRET" \
            --arg sub "$FLOW_SUBSCRIPTION_ID" \
            --arg storage_name "$FLOW_STORAGE_ACCOUNT_NAME" \
            --arg storage_id "$FLOW_STORAGE_ACCOUNT_ID" \
            '{
                "tenantId": $tenant,
                "clientId": $client,
                "clientSecret": $secret,
                "subscriptionId": $sub,
                "storageAccountName": $storage_name,
                "storageAccountResourceId": $storage_id
            }')
        
        echo -e "${BLUE}Updating Flow Logs secret: $FLOW_SECRET_NAME${NC}"
        
        # Update the Flow Logs secret
        aws secretsmanager update-secret \
            --secret-id "$FLOW_SECRET_NAME" \
            --secret-string "$FLOW_SECRET_JSON" \
            --region "$AWS_REGION" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Flow Logs secret updated successfully!${NC}"
            FLOW_SECRET_OPERATION="updated"
        else
            echo -e "${YELLOW}Secret not found, creating new Flow Logs secret...${NC}"
            
            aws secretsmanager create-secret \
                --name "$FLOW_SECRET_NAME" \
                --description "Azure Storage Account credentials for Flow Logs access" \
                --secret-string "$FLOW_SECRET_JSON" \
                --region "$AWS_REGION"
            
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}Flow Logs secret created successfully!${NC}"
                FLOW_SECRET_OPERATION="created"
            else
                echo -e "${RED}Error: Failed to create Flow Logs secret${NC}"
                FLOW_SECRET_OPERATION="failed"
            fi
        fi
        
        echo ""
        echo -e "${BLUE}Flow Logs Configuration Summary:${NC}"
        echo "   • Secret Name: $FLOW_SECRET_NAME (${FLOW_SECRET_OPERATION})"
        echo "   • Storage Account: $FLOW_STORAGE_ACCOUNT_NAME"
        echo "   • Client ID: $FLOW_CLIENT_ID"
        echo "   • AWS Region: $AWS_REGION"
    fi
fi

echo ""
echo -e "${GREEN}=================================================================${NC}"
echo -e "${GREEN}Configuration Complete!${NC}"
echo -e "${GREEN}=================================================================${NC}"
echo -e "${GREEN}Ready for Lambda function deployment and testing!${NC}"
