#!/bin/bash

################################################################################
# GCP Security Command Center - AWS Secrets Manager Configuration Script
#
# This script automates the configuration of AWS Secrets Manager with GCP
# service account credentials required for the Pub/Sub integration.
#
# Author: SecureSight Team
# Version: 1.0.0
################################################################################

set -e  # Exit on any error

# Color output for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
AWS_REGION=""
SECRET_NAME=""
GCP_PROJECT_ID=""
GCP_SUBSCRIPTION_ID=""
GCP_TOPIC_ID=""
SERVICE_ACCOUNT_KEY_PATH=""
DRY_RUN=false
VERBOSE=false

################################################################################
# Helper Functions
################################################################################

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Configure AWS Secrets Manager with GCP service account credentials for
Security Command Center integration.

Required Options:
    --secret-name NAME              AWS Secrets Manager secret name
    --gcp-project-id ID             GCP project ID
    --gcp-subscription-id ID        GCP Pub/Sub subscription ID
    --gcp-topic-id ID               GCP Pub/Sub topic ID
    --service-account-key PATH      Path to GCP service account JSON key file
    --region REGION                 AWS region

Optional Flags:
    --dry-run                       Validate inputs without making changes
    --verbose                       Enable verbose output
    -h, --help                      Display this help message

Examples:
    # Basic usage
    $0 \\
        --secret-name "gcp-scc-pubsub-credentials-dev" \\
        --gcp-project-id "my-gcp-project" \\
        --gcp-subscription-id "scc-findings-sub" \\
        --gcp-topic-id "scc-findings-topic" \\
        --service-account-key "./gcp-sa-key.json" \\
        --region "us-east-1"

    # Dry run to validate configuration
    $0 --dry-run \\
        --secret-name "gcp-scc-pubsub-credentials-dev" \\
        --gcp-project-id "my-gcp-project" \\
        --gcp-subscription-id "scc-findings-sub" \\
        --gcp-topic-id "scc-findings-topic" \\
        --service-account-key "./gcp-sa-key.json" \\
        --region "us-east-1"

EOF
}

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

################################################################################
# Validation Functions
################################################################################

check_dependencies() {
    log "Checking dependencies..."
    
    local missing_deps=()
    
    # Check for AWS CLI
    if ! command -v aws &> /dev/null; then
        missing_deps+=("aws-cli")
    fi
    
    # Check for jq
    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_error "Install missing dependencies and try again."
        exit 1
    fi
    
    log_verbose "All dependencies found"
}

validate_inputs() {
    log "Validating inputs..."
    
    local errors=()
    
    # Check required parameters
    if [ -z "$SECRET_NAME" ]; then
        errors+=("--secret-name is required")
    fi
    
    if [ -z "$GCP_PROJECT_ID" ]; then
        errors+=("--gcp-project-id is required")
    fi
    
    if [ -z "$GCP_SUBSCRIPTION_ID" ]; then
        errors+=("--gcp-subscription-id is required")
    fi
    
    if [ -z "$GCP_TOPIC_ID" ]; then
        errors+=("--gcp-topic-id is required")
    fi
    
    if [ -z "$SERVICE_ACCOUNT_KEY_PATH" ]; then
        errors+=("--service-account-key is required")
    fi
    
    if [ -z "$AWS_REGION" ]; then
        errors+=("--region is required")
    fi
    
    # Check if service account key file exists
    if [ -n "$SERVICE_ACCOUNT_KEY_PATH" ] && [ ! -f "$SERVICE_ACCOUNT_KEY_PATH" ]; then
        errors+=("Service account key file not found: $SERVICE_ACCOUNT_KEY_PATH")
    fi
    
    # Validate service account key JSON format
    if [ -n "$SERVICE_ACCOUNT_KEY_PATH" ] && [ -f "$SERVICE_ACCOUNT_KEY_PATH" ]; then
        if ! jq empty "$SERVICE_ACCOUNT_KEY_PATH" 2>/dev/null; then
            errors+=("Service account key file is not valid JSON: $SERVICE_ACCOUNT_KEY_PATH")
        fi
    fi
    
    # Report errors
    if [ ${#errors[@]} -ne 0 ]; then
        log_error "Validation failed:"
        for error in "${errors[@]}"; do
            log_error "  - $error"
        done
        exit 1
    fi
    
    log_verbose "Input validation passed"
}

check_aws_credentials() {
    log "Checking AWS credentials..."
    
    if ! aws sts get-caller-identity --region "$AWS_REGION" &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        log_error "Configure AWS CLI with: aws configure"
        exit 1
    fi
    
    local caller_identity
    caller_identity=$(aws sts get-caller-identity --region "$AWS_REGION" --output json)
    local account_id
    account_id=$(echo "$caller_identity" | jq -r '.Account')
    local user_arn
    user_arn=$(echo "$caller_identity" | jq -r '.Arn')
    
    log_verbose "AWS Account ID: $account_id"
    log_verbose "AWS Identity: $user_arn"
}

################################################################################
# Secret Management Functions
################################################################################

check_secret_exists() {
    log "Checking if secret exists..."
    
    if aws secretsmanager describe-secret \
        --secret-id "$SECRET_NAME" \
        --region "$AWS_REGION" &> /dev/null; then
        log_verbose "Secret '$SECRET_NAME' exists"
        return 0
    else
        log_verbose "Secret '$SECRET_NAME' does not exist"
        return 1
    fi
}

create_secret_value() {
    log "Creating secret value JSON..."
    
    # Read the service account key
    local sa_key
    sa_key=$(cat "$SERVICE_ACCOUNT_KEY_PATH")
    
    # Validate it's valid JSON
    if ! echo "$sa_key" | jq empty 2>/dev/null; then
        log_error "Invalid JSON in service account key file"
        exit 1
    fi
    
    # Create the secret value structure
    local secret_value
    secret_value=$(jq -n \
        --arg projectId "$GCP_PROJECT_ID" \
        --arg subscriptionId "$GCP_SUBSCRIPTION_ID" \
        --arg topicId "$GCP_TOPIC_ID" \
        --argjson serviceAccountKey "$sa_key" \
        '{
            projectId: $projectId,
            subscriptionId: $subscriptionId,
            topicId: $topicId,
            serviceAccountKey: $serviceAccountKey
        }')
    
    # Validate the final structure
    if ! echo "$secret_value" | jq empty 2>/dev/null; then
        log_error "Failed to create valid secret value JSON"
        exit 1
    fi
    
    log_verbose "Secret value JSON created successfully"
    
    echo "$secret_value"
}

update_secret() {
    local secret_value="$1"
    
    log "Updating secret in AWS Secrets Manager..."
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Would update secret '$SECRET_NAME' in region '$AWS_REGION'"
        log_verbose "Secret value (first 100 chars): ${secret_value:0:100}..."
        return 0
    fi
    
    # Update the secret
    if aws secretsmanager update-secret \
        --secret-id "$SECRET_NAME" \
        --secret-string "$secret_value" \
        --region "$AWS_REGION" > /dev/null 2>&1; then
        log_success "Secret '$SECRET_NAME' updated successfully"
        return 0
    else
        log_error "Failed to update secret '$SECRET_NAME'"
        return 1
    fi
}

create_secret() {
    local secret_value="$1"
    
    log "Creating new secret in AWS Secrets Manager..."
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Would create secret '$SECRET_NAME' in region '$AWS_REGION'"
        log_verbose "Secret value (first 100 chars): ${secret_value:0:100}..."
        return 0
    fi
    
    # Create the secret with tags
    if aws secretsmanager create-secret \
        --name "$SECRET_NAME" \
        --description "GCP Pub/Sub service account credentials for Security Command Center integration" \
        --secret-string "$secret_value" \
        --region "$AWS_REGION" \
        --tags Key=Integration,Value=GCP-SCC Key=ManagedBy,Value=configure-script > /dev/null 2>&1; then
        log_success "Secret '$SECRET_NAME' created successfully"
        return 0
    else
        log_error "Failed to create secret '$SECRET_NAME'"
        return 1
    fi
}

verify_secret() {
    log "Verifying secret configuration..."
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Skipping secret verification"
        return 0
    fi
    
    # Retrieve and validate the secret
    local retrieved_secret
    retrieved_secret=$(aws secretsmanager get-secret-value \
        --secret-id "$SECRET_NAME" \
        --region "$AWS_REGION" \
        --query 'SecretString' \
        --output text 2>/dev/null)
    
    if [ -z "$retrieved_secret" ]; then
        log_error "Failed to retrieve secret for verification"
        return 1
    fi
    
    # Validate JSON structure
    if ! echo "$retrieved_secret" | jq empty 2>/dev/null; then
        log_error "Retrieved secret is not valid JSON"
        return 1
    fi
    
    # Validate required fields
    local required_fields=("projectId" "subscriptionId" "topicId" "serviceAccountKey")
    for field in "${required_fields[@]}"; do
        if ! echo "$retrieved_secret" | jq -e ".$field" > /dev/null 2>&1; then
            log_error "Secret is missing required field: $field"
            return 1
        fi
    done
    
    log_verbose "Secret structure validated successfully"
    log_success "Secret verification passed"
    return 0
}

################################################################################
# Main Execution
################################################################################

main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  GCP Security Command Center - AWS Secrets Manager Setup      ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Check dependencies
    check_dependencies
    
    # Validate inputs
    validate_inputs
    
    # Check AWS credentials
    check_aws_credentials
    
    # Display configuration summary
    echo ""
    log "Configuration Summary:"
    echo "  Secret Name:        $SECRET_NAME"
    echo "  AWS Region:         $AWS_REGION"
    echo "  GCP Project ID:     $GCP_PROJECT_ID"
    echo "  GCP Subscription:   $GCP_SUBSCRIPTION_ID"
    echo "  GCP Topic:          $GCP_TOPIC_ID"
    echo "  SA Key File:        $SERVICE_ACCOUNT_KEY_PATH"
    echo "  Dry Run:            $DRY_RUN"
    echo ""
    
    # Create secret value
    local secret_value
    secret_value=$(create_secret_value)
    
    # Check if secret exists and update or create accordingly
    if check_secret_exists; then
        update_secret "$secret_value"
    else
        create_secret "$secret_value"
    fi
    
    # Verify the secret
    verify_secret
    
    echo ""
    log_success "Configuration complete!"
    echo ""
    
    if [ "$DRY_RUN" = false ]; then
        echo "Next steps:"
        echo "  1. Deploy the AWS CDK stack if not already deployed"
        echo "  2. Verify Lambda functions can access the secret"
        echo "  3. Test the Pub/Sub poller Lambda function"
        echo ""
        echo "Useful commands:"
        echo "  # View secret"
        echo "  aws secretsmanager get-secret-value --secret-id $SECRET_NAME --region $AWS_REGION"
        echo ""
        echo "  # Test Lambda"
        echo "  aws lambda invoke --function-name <poller-function-name> response.json"
        echo ""
    fi
}

################################################################################
# Parse Command Line Arguments
################################################################################

while [[ $# -gt 0 ]]; do
    case $1 in
        --secret-name)
            SECRET_NAME="$2"
            shift 2
            ;;
        --gcp-project-id)
            GCP_PROJECT_ID="$2"
            shift 2
            ;;
        --gcp-subscription-id)
            GCP_SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        --gcp-topic-id)
            GCP_TOPIC_ID="$2"
            shift 2
            ;;
        --service-account-key)
            SERVICE_ACCOUNT_KEY_PATH="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Run main function
main