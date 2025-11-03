© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Security Lake Integration Framework - Complete Installation Guide

## Version 2.0.0

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation Paths](#installation-paths)
- [Complete Installation Procedure](#complete-installation-procedure)
- [Azure Integration Setup](#azure-integration-setup)
- [Post-Installation Verification](#post-installation-verification)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

## Overview

This guide provides comprehensive step-by-step instructions for installing and configuring the Security Lake Integration Framework. The framework supports modular deployment, allowing you to install only the components you need.

**Estimated Installation Time**: 1-2 hours (depending on integration modules)

**Skill Level Required**: Intermediate to Advanced AWS and Cloud Infrastructure

## Prerequisites

### Required Tools and Access

#### AWS Prerequisites

| Requirement | Version | Purpose | Installation |
|-------------|---------|---------|--------------|
| Node.js | >= 18.0.0 | CDK runtime and package management | [nodejs.org](https://nodejs.org/) |
| Python | >= 3.9 | Lambda development and testing | [python.org](https://www.python.org/) |
| AWS CLI | >= 2.0 | AWS resource management | [AWS CLI Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| AWS CDK CLI | >= 2.0 | Infrastructure deployment | `npm install -g aws-cdk` |
| Git | Latest | Source code management | [git-scm.com](https://git-scm.com/) |

#### Azure Prerequisites (If Using Azure Module)

| Requirement | Version | Purpose | Installation |
|-------------|---------|---------|--------------|
| Azure CLI | >= 2.0 | Azure resource management | [Azure CLI Install Guide](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) |
| Terraform | >= 1.0 | Azure infrastructure deployment | [terraform.io](https://www.terraform.io/downloads) |

### AWS Account Requirements

**Required AWS Services:**
- AWS Security Lake (enabled in target region)
- AWS IAM (with administrative access)
- AWS CloudFormation
- AWS Lambda
- AWS SQS
- AWS DynamoDB (if using checkpoint stores)
- AWS Secrets Manager
- AWS CloudWatch
- AWS KMS (for encryption)

**IAM Permissions Required:**
The deployment user/role needs permissions to:
- Create and manage CloudFormation stacks
- Create and manage Lambda functions
- Create and manage IAM roles and policies
- Create and manage KMS keys
- Create and manage SQS queues
- Create and manage DynamoDB tables
- Create and manage Secrets Manager secrets
- Create and manage CloudWatch log groups and alarms
- Create and manage Security Lake resources

**Pre-existing Resources:**
- Security Lake S3 bucket (CRITICAL: Must exist before deployment)
- Lake Formation admin role configured

### Azure Account Requirements (If Using Azure Integration)

- Active Azure subscription
- Microsoft Defender for Cloud enabled
- Permissions to create:
  - Resource Groups
  - Event Hub Namespaces
  - Event Hubs
  - Storage Accounts (for Flow Logs)
  - App Registrations
  - Role Assignments

## Installation Paths

Choose the installation path that matches your use case:

### Path 1: Core Framework Only

Install the core Security Lake integration framework without any specific integrations. Useful for:
- Testing the framework
- Developing custom modules
- Minimal deployment for future expansion

**Components Installed:**
- Event Transformer Lambda
- Security Hub Processor Lambda
- Security Lake Custom Resource
- SQS Queues
- Optional: Shared KMS Key

### Path 2: Azure Defender Integration

Install with Microsoft Defender for Cloud integration. Recommended for:
- Cross-cloud security monitoring
- Azure security event collection
- Unified security operations

**Components Installed:**
- All Core Framework components
- Azure Event Hub Processor Lambda
- DynamoDB Checkpoint Store
- Azure Event Hub credentials in Secrets Manager

### Path 3: Core Framework with Flow Logs

Install core framework with Flow Log processing enabled. Recommended for:
- Multi-cloud network visibility
- Network traffic analysis from various sources
- Advanced threat detection

**Components Installed:**
- All Core Framework components
- Flow Log Processor Lambda (enabled)
- Cloud-specific credentials in Secrets Manager (as needed)

**Note**: Flow Log Processor is part of the core framework and supports multiple cloud providers, not just Azure.

### Path 4: CloudTrail Event Data Store Integration

Install with CloudTrail Event Data Store support. Recommended for:
- Legacy CloudTrail integration
- Dual Security Lake and CloudTrail storage
- Compliance requirements for CloudTrail retention

**Components Installed:**
- All Core Framework components
- CloudTrail Event Data Store
- CloudTrail Channel

## Complete Installation Procedure

### Phase 1: Environment Preparation

#### Step 1.1: Verify AWS Account Setup

```bash
# Verify AWS CLI is configured
aws sts get-caller-identity

# Expected output: Your AWS account ID and user/role information
```

#### Step 1.2: Verify Security Lake Prerequisites

```bash
# Check if Security Lake is enabled
aws securitylake get-data-lake-sources --region ca-central-1

# List Security Lake S3 buckets
aws s3 ls | grep security-data-lake

# CRITICAL: Note your Security Lake bucket name - you'll need it for configuration
# Format: aws-security-data-lake-{region}-{unique-hash}
```

#### Step 1.3: Bootstrap CDK (First Time Only)

```bash
# Bootstrap CDK in your target account and region
cdk bootstrap aws://ACCOUNT-NUMBER/REGION

# Example:
cdk bootstrap aws://123456789012/ca-central-1
```

### Phase 2: Source Code Setup

#### Step 2.1: Clone Repository

```bash
# Clone the repository
git clone <repository-url>
cd security-lake-integrations

# Verify structure
ls -la
```

#### Step 2.2: Install Pre-commit Hooks (Recommended)

```bash
# Install pre-commit tool
pip install pre-commit

# Install git hooks
pre-commit install

# Test hooks (optional)
pre-commit run --all-files
```

### Phase 3: Core Framework Installation

#### Step 3.1: Navigate to CDK Directory

```bash
cd integrations/security-lake/cdk
```

#### Step 3.2: Install Node.js Dependencies

```bash
# Install all npm packages
npm install

# Verify installation
npm list --depth=0
```

#### Step 3.3: Create Configuration File

```bash
# Copy example configuration
cp config.example.yaml config.yaml
```

#### Step 3.4: Edit Configuration File

Open `config.yaml` in your preferred editor and configure:

**Minimum Required Configuration:**

```yaml
# Project identification
projectName: my-security-lake  # Lowercase, hyphens only
environment: dev  # dev, staging, or prod
awsRegion: ca-central-1  # Your target region

# Security Lake configuration
securityLake:
  enabled: true
  s3Bucket: aws-security-data-lake-ca-central-1-YOUR-HASH  # REPLACE with actual bucket
  externalId: GENERATE-SECURE-RANDOM-STRING-HERE  # See below for generation
  
# Core processing
coreProcessing:
  eventTransformer:
    enabled: true
  securityHubProcessor:
    enabled: true  # Set to false if not using Security Hub

# Encryption (recommended for production)
encryption:
  enabled: true
  keyType: CUSTOMER_MANAGED_CMK  # Use AWS_OWNED_CMK for dev/test
```

**Generate Secure External ID:**

```bash
# Generate a secure random string for externalId
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Copy the output and use it as your externalId
```

#### Step 3.5: Validate Configuration

```bash
# Build TypeScript
npm run build

# Validate configuration
npm run validate-config -- --config config.yaml

# Expected output: "Configuration is valid"
```

#### Step 3.6: Synthesize CloudFormation Template

```bash
# Generate CloudFormation template
npm run synth

# Review the synthesized template
ls -la cdk.out/
```

#### Step 3.7: Deploy Core Framework

```bash
# Deploy to AWS
npm run deploy

# Or deploy with approval prompts
cdk deploy

# Expected: CloudFormation stack creation progress
# Duration: 5-10 minutes
```

#### Step 3.8: Verify Core Deployment

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name my-security-lake-dev \
  --query 'Stacks[0].StackStatus' \
  --output text

# Expected output: CREATE_COMPLETE

# List created Lambda functions
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `my-security-lake`)].FunctionName' \
  --output table
```

### Phase 4: Azure Integration Setup (Optional)

#### Step 4.1: Deploy Azure Infrastructure

```bash
# Navigate to Terraform directory
cd ../../../azure/microsoft_defender_cloud/terraform

# Create terraform.tfvars from example
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
# Required variables
azure_subscription_id = "your-subscription-id"
azure_tenant_id       = "your-tenant-id"
location              = "canadacentral"

# Event Hub configuration
eventhub_namespace_name = "defender-events-prod"
eventhub_name          = "security-events"
eventhub_partition_count = 4

# Optional: VNet Flow Logs
enable_vnet_flowlogs = true
vnet_ids = [
  "/subscriptions/YOUR-SUB/resourceGroups/YOUR-RG/providers/Microsoft.Network/virtualNetworks/YOUR-VNET"
]
```

Deploy Azure resources:

```bash
# Initialize Terraform
terraform init

# Review plan
terraform plan

# Apply configuration
terraform apply

# Note the outputs - you'll need them
terraform output
```

#### Step 4.2: Update AWS Configuration for Azure Module

```bash
# Return to CDK directory
cd ../../../security-lake/cdk
```

Edit `config.yaml` to enable Azure module:

```yaml
integrations:
  azure:
    enabled: true
    config:
      eventHubProcessor:
        enabled: true
        schedule: rate(5 minutes)
        memorySize: 512
        timeout: 300
        azureCredentialsSecretName: azure-eventhub-credentials
      
      checkpointStore:
        enabled: true

# Note: Flow Log Processor is configured in coreProcessing section
coreProcessing:
  flowLogProcessor:
    enabled: true  # Set to true if processing flow logs from any cloud provider
    memorySize: 1024
    timeout: 600
```

#### Step 4.3: Deploy Updated Stack

```bash
# Rebuild and deploy
npm run build
npm run deploy
```

#### Step 4.4: Verify Azure Deployment

```bash
# Terraform automatically configures everything needed for the integration
# No manual configuration required

# Verify deployment with Terraform outputs
cd ../../../azure/microsoft_defender_cloud/terraform
terraform output

# Key outputs confirm successful configuration:
# - event_hub_namespace_name: Azure Event Hub created
# - event_hub_name: Event Hub for Defender events
# - continuous_export_id: Microsoft Defender export configured
# - secrets_manager_arn: AWS Secrets Manager updated with credentials
```

**What Terraform Automated:**
- Created Azure Event Hub Namespace and Event Hub
- Configured Microsoft Defender for Cloud continuous export to Event Hub
- Updated AWS Secrets Manager with Event Hub connection credentials
- Set up all required Azure AD permissions and role assignments
- Configured optional VNet Flow Logs infrastructure (if enabled in terraform.tfvars)

**Result**: The integration is fully operational immediately after `terraform apply` completes successfully. Microsoft Defender events will automatically flow to AWS Security Lake through the deployed infrastructure.

### Phase 5: Post-Installation Configuration

#### Step 5.1: Configure Monitoring and Alerts

Edit `config.yaml` monitoring section:

```yaml
monitoring:
  enabled: true
  alarms:
    enabled: true
    snsTopicName: security-lake-alerts
    emailEndpoints:
      - security-team@yourcompany.com
      - ops-team@yourcompany.com
```

Redeploy to apply monitoring changes:

```bash
npm run deploy
```

#### Step 5.2: Subscribe to SNS Notifications

```bash
# Get SNS topic ARN
SNS_TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name my-security-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`AlarmTopicArn`].OutputValue' \
  --output text)

# Verify email subscriptions were created
aws sns list-subscriptions-by-topic --topic-arn $SNS_TOPIC_ARN

# Check your email and confirm subscriptions
```

## Post-Installation Verification

### Verification Checklist

```bash
# 1. Verify Lambda Functions
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName, `my-security-lake`)].{Name:FunctionName,Status:State}' \
  --output table

# 2. Verify SQS Queues
aws sqs list-queues --queue-name-prefix my-security-lake

# 3. Verify DynamoDB Tables (if using Azure module)
aws dynamodb list-tables --query 'TableNames[?contains(@, `checkpoint`)]'

# 4. Verify Secrets Manager Secrets (if using Azure module)
aws secretsmanager list-secrets \
  --query 'SecretList[?contains(Name, `azure`)].Name'

# 5. Test Event Hub Processor (if using Azure module)
aws lambda invoke \
  --function-name azure-eventhub-processor-dev \
  --payload '{}' \
  response.json && cat response.json

# 6. Check CloudWatch Logs
aws logs tail /aws/lambda/event-transformer-dev --follow
```

### Expected Results

**Successful Installation Indicators:**
- All Lambda functions in `Active` state
- SQS queues created and accessible
- Secrets Manager secrets created (for Azure integration)
- No errors in CloudWatch Logs during test invocations
- CloudFormation stack in `CREATE_COMPLETE` or `UPDATE_COMPLETE` status

## Troubleshooting

### Common Installation Issues

#### Issue 1: CDK Bootstrap Failed

**Error Message:**
```
ERROR: current credentials could not be used to assume
```

**Solution:**
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Ensure you have AdministratorAccess or equivalent
# Re-run bootstrap with explicit credentials
AWS_PROFILE=your-profile cdk bootstrap
```

#### Issue 2: Security Lake Bucket Not Found

**Error Message:**
```
Security Lake S3 bucket does not exist
```

**Solution:**
1. Verify Security Lake is enabled in your account/region
2. Check bucket name in AWS Console: Security Lake → Settings
3. Update `config.yaml` with correct bucket name
4. Ensure bucket is in the same region as deployment

#### Issue 3: Terraform Apply Failed (Azure)

**Error Message:**
```
Error creating Event Hub Namespace: authorization failed
```

**Solution:**
```bash
# Verify Azure CLI login
az account show

# Login if needed
az login

# Set correct subscription
az account set --subscription YOUR-SUBSCRIPTION-ID

# Verify permissions
az role assignment list --assignee YOUR-USER-ID
```

#### Issue 4: Lambda Deployment Package Too Large

**Error Message:**
```
Unzipped size must be smaller than 262144000 bytes
```

**Solution:**
- This is handled automatically by CDK Docker bundling
- Ensure Docker is running
- If issue persists, check `requirements.txt` for unnecessary dependencies

#### Issue 5: Secrets Manager Access Denied

**Error Message:**
```
User is not authorized to perform: secretsmanager:GetSecretValue
```

**Solution:**
```bash
# Verify Lambda execution role has correct permissions
aws iam get-role-policy \
  --role-name EventHubProcessorRole-dev \
  --policy-name SecretsAccess

# If missing, redeploy stack (permissions should be auto-created)
npm run deploy
```

### Debug Mode

Enable detailed logging for troubleshooting:

```yaml
# In config.yaml
integrations:
  azure:
    config:
      eventHubProcessor:
        environment:
          LOGGING_LEVEL: DEBUG
      flowLogProcessor:
        environment:
          LOGGING_LEVEL: DEBUG
```

Redeploy and check logs:

```bash
npm run deploy

# Monitor logs in real-time
aws logs tail /aws/lambda/azure-eventhub-processor-dev --follow
```

## Next Steps

After successful installation:

### 1. Monitor Event Flow

```bash
# Watch for events being processed
aws logs tail /aws/lambda/event-transformer-dev --follow

# Check SQS queue metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name NumberOfMessagesSent \
  --dimensions Name=QueueName,Value=event-queue-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### 2. Query Security Lake Data

```bash
# List partitions in Security Lake
aws s3 ls s3://aws-security-data-lake-region-hash/ext/ --recursive

# Query data using Athena
aws athena start-query-execution \
  --query-string "SELECT * FROM amazon_security_lake_glue_db_region.amazon_security_lake_table_region_ext_unifiedSecurityEvents LIMIT 10" \
  --result-configuration OutputLocation=s3://your-athena-results-bucket/
```

### 3. Configure Additional Integrations

See:
- [Module Development Guide](cdk/docs/MODULE_DEVELOPMENT_GUIDE.md)
- [Module Interface Specification](cdk/docs/MODULE_INTERFACE_SPEC.md)

### 4. Review Security Best Practices

- Enable KMS encryption in production
- Rotate Azure credentials regularly
- Configure CloudWatch alarms
- Review IAM permissions
- Enable AWS CloudTrail logging

### 5. Performance Optimization

See module-specific documentation for tuning:
- [Azure Module README](cdk/modules/azure/README.md)
- [Configuration Schema](cdk/docs/CONFIG_SCHEMA.md)

## Additional Resources

### Framework Documentation

- [Framework README](cdk/README.md) - Core framework overview and quick start
- [Configuration Schema](cdk/docs/CONFIG_SCHEMA.md) - Complete configuration reference
- [Module Interface Specification](cdk/docs/MODULE_INTERFACE_SPEC.md) - Module development standards
- [Module Development Guide](cdk/docs/MODULE_DEVELOPMENT_GUIDE.md) - Creating custom integrations
- [Threat Model](cdk/docs/THREAT_MODEL.md) - Security analysis and controls
- [Code Formatting Standard](../../DOCUMENTATION_CODE_FORMATTING_STANDARD.md) - Documentation style guide

### Integration Guides

- [Azure Defender Integration](../azure/microsoft_defender_cloud/README.md) - Microsoft Defender for Cloud
  - [Azure Module](cdk/modules/azure/README.md) - Modular Azure integration
  - [Azure Terraform](../azure/microsoft_defender_cloud/terraform/README.md) - Azure infrastructure
  - [Azure Scripts](../azure/microsoft_defender_cloud/scripts/README.md) - Configuration automation
- [Google SCC Integration](../google_security_command_center/README.md) - Google Security Command Center
  - [Google SCC Module](cdk/modules/google-scc/README.md) - Modular GCP integration
  - [Google SCC Terraform](../google_security_command_center/terraform/README.md) - GCP infrastructure
- [GCP VPC Flow Logs](../../gcp-vpc-flow-logs/README.md) - GCP network visibility

### Lambda Function Documentation

- [Event Transformer](cdk/src/lambda/event-transformer/README.md) - Multi-format transformation pipeline
- [Flow Log Processor](cdk/src/lambda/flow-log-processor/README.md) - Network flow log processing
- [Security Hub Processor](cdk/src/lambda/securityhub-processor/app.py) - ASFF finding import

### Technical Deep Dives

- [Technical Blog Post](../../BLOG_POST.md) - Real-world implementation walkthrough

### External Resources

- [AWS Security Lake Documentation](https://docs.aws.amazon.com/security-lake/) - Security Lake and OCSF
- [OCSF Schema Documentation](https://schema.ocsf.io/) - Open Cybersecurity Schema Framework
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/) - Infrastructure as code
- [CloudTrail Lake Documentation](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake.html) - Event Data Store
- [Microsoft Defender for Cloud Documentation](https://docs.microsoft.com/en-us/azure/defender-for-cloud/)
- [Google Security Command Center Documentation](https://cloud.google.com/security-command-center/docs)

### Support

For questions or issues:
1. Review this installation guide
2. Check troubleshooting section
3. Review CloudWatch Logs for detailed errors
4. Consult module-specific documentation
5. Contact your AWS Professional Services team

## Version History

### Version 2.0.0 (2025-01-22)
- Initial comprehensive installation guide
- Support for modular architecture
- Azure integration procedures
- Complete troubleshooting section

---

**Installation Complete!** Your Security Lake Integration Framework is now ready for use.