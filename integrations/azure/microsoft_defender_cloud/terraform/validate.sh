#!/bin/bash
# Microsoft Defender for Cloud - Event Hub Integration Validation Script
# 
# This script validates the Terraform configuration and Azure connectivity
# before deployment.
# 
# Author: SecureSight Team
# Version: 1.0.0

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "Microsoft Defender for Cloud - Event Hub Integration Validator"
echo "============================================================="
echo

# Check Terraform installation
print_status "Checking Terraform installation..."
if command -v terraform &> /dev/null; then
    TERRAFORM_VERSION=$(terraform version -json | jq -r '.terraform_version')
    print_success "Terraform $TERRAFORM_VERSION found"
else
    print_error "Terraform not found. Please install Terraform >= 1.0"
    exit 1
fi

# Check Azure CLI installation
print_status "Checking Azure CLI installation..."
if command -v az &> /dev/null; then
    AZ_VERSION=$(az version --query '"azure-cli"' -o tsv)
    print_success "Azure CLI $AZ_VERSION found"
else
    print_error "Azure CLI not found. Please install Azure CLI >= 2.30"
    exit 1
fi

# Check Azure authentication
print_status "Checking Azure authentication..."
if az account show &> /dev/null; then
    SUBSCRIPTION=$(az account show --query 'name' -o tsv)
    ACCOUNT_ID=$(az account show --query 'id' -o tsv)
    TENANT_ID=$(az account show --query 'tenantId' -o tsv)
    print_success "Authenticated to subscription: $SUBSCRIPTION"
    print_status "Account ID: $ACCOUNT_ID"
    print_status "Tenant ID: $TENANT_ID"
else
    print_error "Not authenticated with Azure. Please run 'az login'"
    exit 1
fi

# Check permissions
print_status "Checking Azure permissions..."
ROLE_ASSIGNMENTS=$(az role assignment list --assignee "$(az account show --query 'user.name' -o tsv)" --query '[].roleDefinitionName' -o tsv)
if echo "$ROLE_ASSIGNMENTS" | grep -q -E "(Owner|Contributor)"; then
    print_success "Required permissions found"
else
    print_warning "Could not verify Contributor/Owner permissions"
    print_status "Please ensure you have Contributor or Owner role on the target subscription/resource group"
fi

# Validate Terraform configuration
print_status "Validating Terraform configuration..."
if terraform validate; then
    print_success "Terraform configuration is valid"
else
    print_error "Terraform configuration validation failed"
    exit 1
fi

# Check for required files
print_status "Checking required files..."
REQUIRED_FILES=(
    "main.tf"
    "variables.tf"
    "outputs.tf"
    "terraform.tfvars.example"
    "modules/eventhub-namespace/main.tf"
    "modules/eventhub/main.tf"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_success "✓ $file"
    else
        print_error "✗ $file (missing)"
        exit 1
    fi
done

# Check for configuration file
if [ -f "terraform.tfvars" ]; then
    print_success "Configuration file found: terraform.tfvars"
else
    print_warning "No terraform.tfvars found"
    print_status "You can copy terraform.tfvars.example to terraform.tfvars and customize it"
fi

# Test Azure resource provider registration
print_status "Checking Azure resource provider registrations..."
REQUIRED_PROVIDERS=(
    "Microsoft.EventHub"
    "Microsoft.OperationalInsights"
    "Microsoft.Insights"
)

for provider in "${REQUIRED_PROVIDERS[@]}"; do
    STATUS=$(az provider show --namespace "$provider" --query 'registrationState' -o tsv 2>/dev/null || echo "NotFound")
    if [ "$STATUS" = "Registered" ]; then
        print_success "✓ $provider: Registered"
    else
        print_warning "✗ $provider: $STATUS"
        print_status "Registering provider: $provider"
        az provider register --namespace "$provider" --wait
    fi
done

# Summary
echo
print_success "Validation completed successfully!"
echo
print_status "Ready for deployment. Run one of the following:"
echo "  ./deploy.sh           # Full deployment"
echo "  ./deploy.sh --plan    # Create execution plan only"
echo "  terraform init && terraform plan  # Manual deployment"
echo