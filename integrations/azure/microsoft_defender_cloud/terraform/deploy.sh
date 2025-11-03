#!/bin/bash
# Microsoft Defender for Cloud - Event Hub Integration Deployment Script
# 
# This script automates the deployment process with proper error handling
# and validation steps.
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

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if Terraform is installed
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed. Please install Terraform >= 1.0"
        exit 1
    fi
    
    # Check Terraform version
    TERRAFORM_VERSION=$(terraform version -json | jq -r '.terraform_version')
    print_status "Found Terraform version: $TERRAFORM_VERSION"
    
    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed. Please install Azure CLI >= 2.30"
        exit 1
    fi
    
    # Check Azure CLI authentication
    if ! az account show &> /dev/null; then
        print_error "Not authenticated with Azure. Please run 'az login'"
        exit 1
    fi
    
    # Display current Azure context
    SUBSCRIPTION=$(az account show --query 'name' -o tsv)
    ACCOUNT_ID=$(az account show --query 'id' -o tsv)
    print_status "Using Azure subscription: $SUBSCRIPTION ($ACCOUNT_ID)"
    
    print_success "All prerequisites met!"
}

# Function to validate configuration
validate_config() {
    print_status "Validating Terraform configuration..."
    
    # Check if tfvars file exists
    if [ ! -f "terraform.tfvars" ]; then
        print_warning "terraform.tfvars file not found!"
        if [ -f "terraform.tfvars.example" ]; then
            print_status "Copying terraform.tfvars.example to terraform.tfvars..."
            cp terraform.tfvars.example terraform.tfvars
            print_warning "Please edit terraform.tfvars with your specific configuration before proceeding!"
            read -p "Press Enter to continue once you've configured terraform.tfvars..."
        else
            print_error "No configuration file found. Please create terraform.tfvars"
            exit 1
        fi
    fi
    
    # Validate Terraform configuration
    if terraform validate; then
        print_success "Terraform configuration is valid!"
    else
        print_error "Terraform configuration validation failed!"
        exit 1
    fi
}

# Function to initialize Terraform
init_terraform() {
    print_status "Initializing Terraform..."
    
    if terraform init; then
        print_success "Terraform initialized successfully!"
    else
        print_error "Terraform initialization failed!"
        exit 1
    fi
}

# Function to plan deployment
plan_deployment() {
    print_status "Creating Terraform execution plan..."
    
    if terraform plan -out=tfplan; then
        print_success "Terraform plan created successfully!"
        print_status "Review the plan above before proceeding with deployment."
        read -p "Do you want to proceed with the deployment? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Deployment cancelled by user."
            exit 0
        fi
    else
        print_error "Terraform plan failed!"
        exit 1
    fi
}

# Function to apply deployment
apply_deployment() {
    print_status "Applying Terraform configuration..."
    
    if terraform apply tfplan; then
        print_success "Deployment completed successfully!"
        
        # Clean up plan file
        rm -f tfplan
        
        # Show important outputs
        print_status "Retrieving deployment outputs..."
        echo
        echo "=== DEPLOYMENT SUMMARY ==="
        terraform output deployment_summary
        echo
        echo "=== NEXT STEPS ==="
        terraform output next_steps
        
    else
        print_error "Terraform apply failed!"
        exit 1
    fi
}

# Function to show help
show_help() {
    echo "Microsoft Defender for Cloud - Event Hub Integration Deployment Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -p, --plan     Only create execution plan (don't apply)"
    echo "  -v, --validate Only validate configuration"
    echo "  -d, --destroy  Destroy the infrastructure"
    echo "  -o, --output   Show deployment outputs"
    echo ""
    echo "Examples:"
    echo "  $0                 # Full deployment (validate, init, plan, apply)"
    echo "  $0 --plan          # Only create execution plan"
    echo "  $0 --validate      # Only validate configuration"
    echo "  $0 --destroy       # Destroy infrastructure"
    echo "  $0 --output        # Show deployment outputs"
    echo ""
}

# Function to destroy infrastructure
destroy_infrastructure() {
    print_warning "This will DESTROY all infrastructure created by this Terraform configuration!"
    print_warning "This action cannot be undone!"
    echo
    read -p "Are you absolutely sure you want to destroy the infrastructure? (type 'yes'): " -r
    if [[ $REPLY != "yes" ]]; then
        print_status "Destroy cancelled by user."
        exit 0
    fi
    
    print_status "Destroying infrastructure..."
    if terraform destroy -auto-approve; then
        print_success "Infrastructure destroyed successfully!"
    else
        print_error "Terraform destroy failed!"
        exit 1
    fi
}

# Function to show outputs
show_outputs() {
    print_status "Showing deployment outputs..."
    echo
    echo "=== DEPLOYMENT SUMMARY ==="
    terraform output deployment_summary
    echo
    echo "=== MICROSOFT DEFENDER CONFIGURATION ==="
    terraform output microsoft_defender_configuration
    echo
    echo "=== EVENT HUB CONNECTION STRINGS (SENSITIVE) ==="
    terraform output eventhub_connection_strings
}

# Main execution logic
main() {
    echo "Microsoft Defender for Cloud - Event Hub Integration"
    echo "===================================================="
    echo
    
    # Parse command line arguments
    case "${1:-}" in
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--plan)
            check_prerequisites
            validate_config
            init_terraform
            plan_deployment
            exit 0
            ;;
        -v|--validate)
            validate_config
            exit 0
            ;;
        -d|--destroy)
            check_prerequisites
            init_terraform
            destroy_infrastructure
            exit 0
            ;;
        -o|--output)
            show_outputs
            exit 0
            ;;
        "")
            # Full deployment
            check_prerequisites
            validate_config
            init_terraform
            plan_deployment
            apply_deployment
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"