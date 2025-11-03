# GCP Security Command Center - Terraform Deployment

This Terraform configuration deploys the Google Cloud Platform (GCP) infrastructure required for the Security Command Center integration with AWS Security Lake.

## Overview

This Terraform module creates:
- **Pub/Sub Topic** - Receives Security Command Center notifications
- **Pub/Sub Subscription** - AWS Lambda polls from this subscription
- **Service Account** - Provides AWS Lambda with GCP API access
- **IAM Permissions** - Grants necessary permissions to the service account
- **SCC Notification Config** - Configures Security Command Center to publish findings

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    GCP Environment (Terraform)                │
│                                                               │
│  ┌────────────────────┐                                      │
│  │  Security Command  │                                      │
│  │     Center (SCC)   │                                      │
│  └────────┬───────────┘                                      │
│           │                                                   │
│           │ Notification Config                              │
│           │                                                   │
│           ▼                                                   │
│  ┌────────────────────┐                                      │
│  │   Pub/Sub Topic    │                                      │
│  │  scc-findings-topic│                                      │
│  └────────┬───────────┘                                      │
│           │                                                   │
│           │ Subscription                                     │
│           │                                                   │
│           ▼                                                   │
│  ┌────────────────────┐                                      │
│  │  Pub/Sub Sub       │◀────────────────────────────┐       │
│  │  scc-findings-sub  │                             │       │
│  └────────────────────┘                             │       │
│           ▲                                          │       │
│           │                                          │       │
│           │ IAM Binding                              │       │
│           │                                          │       │
│  ┌────────┴───────────┐                             │       │
│  │  Service Account   │                             │       │
│  │  (aws-integration) │                             │       │
│  └────────┬───────────┘                             │       │
│           │                                          │       │
│           │ Key Export                               │       │
│           ▼                                          │       │
│  ┌────────────────────┐                             │       │
│  │  Service Account   │──────────────────────┐      │       │
│  │    JSON Key        │                      │      │       │
│  └────────────────────┘                      │      │       │
│                                               │      │       │
└───────────────────────────────────────────────┼──────┼───────┘
                                                │      │
                                                │      │
                                       Store in │      │ Poll
                                       Secrets  │      │
                                       Manager  │      │
                                                │      │
┌───────────────────────────────────────────────┼──────┼───────┐
│              AWS Environment (CDK)            │      │       │
│                                               ▼      │       │
│  ┌────────────────────────────────────────────────┐ │       │
│  │         AWS Secrets Manager                    │ │       │
│  │     (GCP Service Account Key)                  │ │       │
│  └────────────────┬───────────────────────────────┘ │       │
│                   │                                  │       │
│                   ▼                                  │       │
│  ┌────────────────────────────────────────────────┐ │       │
│  │        Pub/Sub Poller Lambda                   │─┘       │
│  │  (Authenticates with GCP using SA key)         │         │
│  └────────────────────────────────────────────────┘         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Required Tools

1. **Terraform** (v1.0 or later)
   ```bash
   terraform --version
   ```

2. **Google Cloud SDK**
   ```bash
   gcloud --version
   ```

### GCP Requirements

1. **GCP Project**
   - Active GCP project
   - Billing enabled
   - Security Command Center API enabled
   - Pub/Sub API enabled

2. **GCP Permissions**
   - `roles/pubsub.admin` - Create topics and subscriptions
   - `roles/iam.serviceAccountAdmin` - Create service accounts
   - `roles/iam.serviceAccountKeyAdmin` - Create service account keys
   - `roles/securitycenter.notificationConfigEditor` - Create SCC notifications

### Authentication

Configure GCP authentication:

```bash
# Authenticate with your user account
gcloud auth login

# Or use a service account
gcloud auth activate-service-account --key-file=/path/to/key.json

# Set the project
gcloud config set project YOUR_PROJECT_ID
```

## Quick Start

### 1. Configure Variables

```bash
# Copy example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

**Minimum Required Variables:**
```hcl
gcp_project_id      = "your-gcp-project-id"
gcp_organization_id = "123456789012"
```

### 2. Initialize Terraform

```bash
# Initialize Terraform (downloads providers)
terraform init
```

### 3. Plan Deployment

```bash
# Review planned changes
terraform plan
```

### 4. Apply Configuration

```bash
# Deploy infrastructure
terraform apply

# Or skip confirmation prompt
terraform apply -auto-approve
```

### 5. Save Service Account Key

After deployment, the service account key is output. Save it securely:

```bash
# Extract key to file
terraform output -raw service_account_key > gcp-sa-key.json

# Set restrictive permissions
chmod 600 gcp-sa-key.json

# Use this key in AWS Secrets Manager configuration
```

## Configuration

### Required Variables

```hcl
variable "gcp_project_id" {
  description = "GCP Project ID where resources will be created"
  type        = string
}

variable "gcp_organization_id" {
  description = "GCP Organization ID for Security Command Center"
  type        = string
}
```

### Optional Variables

#### Pub/Sub Configuration

```hcl
variable "pubsub_topic_name" {
  description = "Name of the Pub/Sub topic"
  type        = string
  default     = "scc-findings-topic"
}

variable "pubsub_subscription_name" {
  description = "Name of the Pub/Sub subscription"
  type        = string
  default     = "scc-findings-aws-subscription"
}

variable "message_retention_duration" {
  description = "Message retention (e.g., '604800s' for 7 days)"
  type        = string
  default     = "604800s"
}

variable "ack_deadline_seconds" {
  description = "Acknowledgment deadline in seconds"
  type        = number
  default     = 600
}
```

#### Service Account Configuration

```hcl
variable "service_account_name" {
  description = "Service account name for AWS integration"
  type        = string
  default     = "aws-security-lake-integration"
}

variable "service_account_display_name" {
  description = "Service account display name"
  type        = string
  default     = "AWS Security Lake Integration Service Account"
}
```

#### Security Command Center Configuration

```hcl
variable "create_scc_notification" {
  description = "Whether to create SCC notification config"
  type        = bool
  default     = true
}

variable "scc_notification_config_id" {
  description = "SCC notification config identifier"
  type        = string
  default     = "scc-findings-to-aws-security-lake"
}

variable "scc_findings_filter" {
  description = "Filter for SCC findings (empty = all)"
  type        = string
  default     = ""
}
```

### Example terraform.tfvars

```hcl
# Basic Configuration
gcp_project_id      = "my-gcp-project"
gcp_organization_id = "123456789012"
gcp_region          = "us-central1"
environment         = "prod"

# Pub/Sub Configuration
pubsub_topic_name              = "scc-findings-topic"
pubsub_subscription_name       = "scc-findings-aws-subscription"
message_retention_duration     = "604800s"  # 7 days
ack_deadline_seconds          = 600

# Service Account
service_account_name          = "aws-security-lake-integration"
service_account_display_name  = "AWS Security Lake Integration"

# Security Command Center
create_scc_notification      = true
scc_notification_config_id   = "scc-to-aws-security-lake"
scc_findings_filter          = "state=\"ACTIVE\""

# Labels
labels = {
  environment = "production"
  managed_by  = "terraform"
  integration = "aws-security-lake"
  team        = "security-ops"
}
```

## Outputs

After successful deployment, Terraform provides these outputs:

```hcl
# Pub/Sub Resources
output "pubsub_topic_id"
output "pubsub_topic_name"
output "pubsub_subscription_id"
output "pubsub_subscription_name"

# Service Account
output "service_account_email"
output "service_account_id"
output "service_account_key"  # Sensitive - handle carefully

# Security Command Center
output "scc_notification_config_name"

# Project Information
output "project_id"
output "project_number"
```

### Accessing Outputs

```bash
# View all outputs
terraform output

# Get specific output
terraform output pubsub_subscription_id

# Get sensitive output (service account key)
terraform output -raw service_account_key

# Export to environment variable
export GCP_SA_KEY=$(terraform output -raw service_account_key)
```

## Common Use Cases

### Filter SCC Findings

Only send specific findings to AWS:

```hcl
# In terraform.tfvars
scc_findings_filter = "state=\"ACTIVE\" AND severity=\"HIGH\""
```

**Common Filters:**
- By state: `state="ACTIVE"`
- By severity: `severity="CRITICAL"` or `severity="HIGH"`
- By category: `category="OPEN_FIREWALL"`
- Combined: `state="ACTIVE" AND severity in ("HIGH", "CRITICAL")`

See [SCC Filter Documentation](https://cloud.google.com/security-command-center/docs/how-to-api-filter-findings) for more options.

### Enable Dead Letter Queue

```hcl
# In terraform.tfvars
enable_dead_letter_queue = true
max_delivery_attempts    = 5
```

### Configure Message Retention

```hcl
# In terraform.tfvars
message_retention_duration             = "604800s"   # 7 days
subscription_message_retention_duration = "604800s"   # 7 days
```

### Regional Deployment

```hcl
# In terraform.tfvars
gcp_region = "us-central1"

# For regional message storage
allowed_persistence_regions = ["us-central1", "us-east1"]
```

## Terraform Commands

```bash
# Initialize and update providers
terraform init -upgrade

# Validate configuration
terraform validate

# Format configuration files
terraform fmt -recursive

# Plan with variable file
terraform plan -var-file=terraform.tfvars

# Apply with variable file
terraform apply -var-file=terraform.tfvars

# Show current state
terraform show

# List resources
terraform state list

# Inspect specific resource
terraform state show google_pubsub_topic.scc_findings

# Destroy all resources
terraform destroy

# Target specific resource
terraform apply -target=google_pubsub_topic.scc_findings
```

## Post-Deployment Steps

### 1. Save Service Account Key

```bash
# Extract key to secure location
terraform output -raw service_account_key > gcp-sa-key.json
chmod 600 gcp-sa-key.json

# Verify key format
cat gcp-sa-key.json | jq .
```

### 2. Configure AWS Secrets Manager

Use the extracted key with the AWS CDK deployment:

```bash
# Navigate to scripts directory
cd ../cdk/scripts

# Run configuration script
./configure-secrets-manager.sh \
  --secret-name "gcp-scc-pubsub-credentials-prod" \
  --gcp-project-id "$(terraform output -raw project_id)" \
  --gcp-subscription-id "$(terraform output -raw pubsub_subscription_id)" \
  --gcp-topic-id "$(terraform output -raw pubsub_topic_id)" \
  --service-account-key "../terraform/gcp-sa-key.json" \
  --region "us-east-1"
```

### 3. Verify SCC Notifications

```bash
# List SCC notification configs
gcloud scc notifications list --organization=$(terraform output -raw organization_id)

# Describe specific notification
gcloud scc notifications describe $(terraform output -raw scc_notification_config_id) \
  --organization=$(terraform output -raw organization_id)
```

### 4. Test Pub/Sub

```bash
# Publish test message
gcloud pubsub topics publish $(terraform output -raw pubsub_topic_id) \
  --message='{"test": "message"}'

# Pull from subscription
gcloud pubsub subscriptions pull $(terraform output -raw pubsub_subscription_id) \
  --auto-ack \
  --limit=10
```

## Monitoring

### Check Pub/Sub Metrics

```bash
# Get subscription details
gcloud pubsub subscriptions describe $(terraform output -raw pubsub_subscription_id)

# Monitor message backlog
gcloud pubsub subscriptions describe $(terraform output -raw pubsub_subscription_id) \
  --format="value(pushConfig.pushEndpoint)"
```

### View SCC Findings

```bash
# List recent findings
gcloud scc findings list \
  --organization=$(terraform output -raw organization_id) \
  --filter="state=\"ACTIVE\"" \
  --page-size=10
```

## Troubleshooting

### Common Issues

#### 1. API Not Enabled

**Error:**
```
Error: Error creating Topic: googleapi: Error 403: 
Pub/Sub API has not been used in project...
```

**Solution:**
```bash
# Enable required APIs
gcloud services enable pubsub.googleapis.com
gcloud services enable securitycenter.googleapis.com
```

#### 2. Insufficient Permissions

**Error:**
```
Error: Error creating ServiceAccount: googleapi: Error 403:
Permission iam.serviceAccounts.create is required...
```

**Solution:**
```bash
# Grant necessary roles to your user account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="user:your-email@example.com" \
  --role="roles/editor"
```

#### 3. Organization Not Found

**Error:**
```
Error: Error creating NotificationConfig: 
Organization not found or permission denied
```

**Solution:**
```bash
# Verify organization ID
gcloud organizations list

# Ensure you have securitycenter.notificationConfigEditor role
```

#### 4. Subscription Already Exists

**Error:**
```
Error: Error creating Subscription: 
googleapi: Error 409: Resource already exists
```

**Solution:**
```bash
# Import existing subscription
terraform import google_pubsub_subscription.scc_findings \
  projects/YOUR_PROJECT/subscriptions/SUBSCRIPTION_NAME

# Or delete and recreate
gcloud pubsub subscriptions delete SUBSCRIPTION_NAME
terraform apply
```

## State Management

### Remote State (Recommended for Teams)

Configure GCS backend:

```hcl
# backend.tf
terraform {
  backend "gcs" {
    bucket = "your-terraform-state-bucket"
    prefix = "gcp-scc-integration"
  }
}
```

Initialize with backend:
```bash
terraform init -backend-config="bucket=your-terraform-state-bucket"
```

### State Commands

```bash
# Pull remote state
terraform state pull > terraform.tfstate.backup

# Push local state to remote
terraform state push terraform.tfstate

# Remove resource from state (without destroying)
terraform state rm google_pubsub_topic.scc_findings

# Move resource in state
terraform state mv google_pubsub_topic.old google_pubsub_topic.new
```

## Updates and Maintenance

### Updating Configuration

```bash
# Modify terraform.tfvars or *.tf files
nano terraform.tfvars

# Preview changes
terraform plan

# Apply updates
terraform apply
```

### Updating Providers

```bash
# Update provider versions
terraform init -upgrade

# Verify new versions
terraform version
```

### Rotating Service Account Keys

```bash
# Create new key
terraform apply -replace=google_service_account_key.aws_integration

# Extract new key
terraform output -raw service_account_key > gcp-sa-key-new.json

# Update AWS Secrets Manager
# (Use configure-secrets-manager.sh script)

# Test new key works

# Delete old key manually in GCP Console if needed
```

## Security Best Practices

1. **Secure State Files**
   - Use remote state with encryption
   - Never commit state files to version control
   - Restrict access to state storage

2. **Service Account Keys**
   - Store keys in AWS Secrets Manager immediately
   - Delete local copies after upload
   - Rotate keys regularly (annually recommended)
   - Use `chmod 600` for any local key files

3. **IAM Permissions**
   - Grant least privilege to service accounts
   - Use predefined roles when possible
   - Regularly audit permissions

4. **Monitoring**
   - Enable audit logging
   - Monitor Pub/Sub usage
   - Set up alerts for unusual activity

## Cleanup

To remove all created resources:

```bash
# Preview what will be destroyed
terraform plan -destroy

# Destroy all resources
terraform destroy

# Confirm when prompted
```

**Note:** This will delete:
- Pub/Sub topic and subscription
- Service account and keys
- SCC notification configuration

**Data Retention:** Messages in Pub/Sub will be deleted. Ensure all messages are processed before destroying.

## Integration with AWS CDK

After deploying GCP infrastructure with Terraform:

1. **Save outputs** for CDK configuration
2. **Extract service account key** and store in AWS Secrets Manager
3. **Deploy AWS infrastructure** using CDK
4. **Configure AWS Lambda** to poll from the Pub/Sub subscription

See [CDK README](../cdk/README.md) for AWS deployment instructions.

## Additional Resources

- [Terraform GCP Provider Documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [GCP Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)
- [GCP Security Command Center](https://cloud.google.com/security-command-center/docs)
- [Terraform Best Practices](https://www.terraform.io/docs/cloud/guides/recommended-practices/index.html)

## Support

For issues or questions:
- Check [main README](../README.md) for architecture overview
- Review [CDK documentation](../cdk/README.md) for AWS integration
- Open an issue in the project repository