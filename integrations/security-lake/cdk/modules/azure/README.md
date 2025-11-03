© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Azure Integration Module

## Version 1.0.0

## Overview

The Azure integration module provides production-ready integration of Microsoft Defender for Cloud security events with AWS Security Lake. This module implements the Security Lake Integration Framework's [`IIntegrationModule`](../../docs/MODULE_INTERFACE_SPEC.md) interface, providing a pluggable, maintainable solution for cross-cloud security monitoring.

**Note**: Azure VNet Flow Logs are processed by the core Flow Log Processor Lambda (part of the base framework), which supports multiple cloud providers. This module focuses specifically on Microsoft Defender for Cloud event integration.

## Features

- **Microsoft Defender Event Hub Integration**: Scheduled polling of Azure Event Hub for security alerts, recommendations, and compliance findings
- **DynamoDB Checkpoint Store**: Reliable event position tracking with automatic resumption after failures
- **AWS Secrets Manager Integration**: Secure storage of Azure Event Hub credentials
- **Automatic Event Transformation**: Conversion to OCSF, CloudTrail, and ASFF formats
- **Comprehensive Monitoring**: CloudWatch metrics, alarms, and structured logging

## Architecture

### Components

```
Azure Event Hub → [Event Hub Processor] → DynamoDB Checkpoint → SQS Queue → Event Transformer → Security Lake
                                                                                             → CloudTrail
                                                                                             → Security Hub
```

**Note**: For Azure VNet Flow Log processing, refer to the core Flow Log Processor Lambda documentation in the main framework README.

### Key Resources

1. **Event Hub Processor Lambda** (Azure Module)
   - Scheduled execution (default: every 5 minutes)
   - Polls Azure Event Hub using AMQP protocol
   - Maintains checkpoints in DynamoDB
   - Single concurrent execution prevents duplicate processing

2. **DynamoDB Checkpoint Store** (Azure Module)
   - Composite primary key: `pk` (partition key) and `sk` (sort key)
   - Checkpoint format: `{namespace}#{eventhub}#{consumergroup}#{partition}`
   - TTL-enabled for automatic cleanup
   - PAY_PER_REQUEST billing mode

3. **AWS Secrets Manager Secret** (Azure Module)
   - Event Hub credentials: Connection string and namespace details

## Prerequisites

### Azure Requirements

1. **Azure Subscription** with active Microsoft Defender for Cloud
2. **Event Hub Namespace** and Event Hub configured
3. **Storage Account** for VNet Flow Logs (if enabled)
4. **Azure AD App Registration** with appropriate permissions:
   - Storage Blob Data Reader role (for flow logs)
   - Event Hub Data Receiver role (for Event Hub)

### AWS Requirements

1. **Security Lake enabled** in target AWS account/region
2. **Pre-existing Security Lake S3 bucket**
3. **Lake Formation** admin role configured
4. **IAM permissions** to deploy CDK stacks

## Configuration

### Module Configuration Structure

```yaml
integrations:
  azure:
    enabled: true
    modulePath: modules/azure  # Optional, defaults to modules/azure
    config:
      # Event Hub Processor Configuration
      eventHubProcessor:
        enabled: true
        functionName: azure-eventhub-processor
        memorySize: 512
        timeout: 300
        reservedConcurrentExecutions: 1
        schedule: rate(5 minutes)
        azureCredentialsSecretName: azure-eventhub-credentials
        environment:
          LOGGING_LEVEL: INFO
      
      # Secrets Manager Configuration
      secretsManager:
        eventHubSecret:
          secretName: azure-eventhub-credentials
          description: Azure Event Hub connection credentials
          secretTemplate:
            eventHubNamespace: PLACEHOLDER
            eventHubName: PLACEHOLDER
            consumerGroup: $Default
            connectionString: PLACEHOLDER
      
      # DynamoDB Checkpoint Store Configuration
      checkpointStore:
        enabled: true
        tableName: azure-eventhub-checkpoint-store
        billingMode: PAY_PER_REQUEST
        encryption:
          useSharedKey: true
        ttl:
          enabled: true
          attributeName: ttl
          defaultTtlHours: 168  # 7 days
```

### Configuration Parameters

#### Event Hub Processor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable Event Hub processor |
| `functionName` | string | azure-eventhub-processor | Lambda function name |
| `memorySize` | number | 512 | Lambda memory in MB (128-10240) |
| `timeout` | number | 300 | Lambda timeout in seconds (1-900) |
| `reservedConcurrentExecutions` | number | 1 | Reserved concurrent executions (prevents duplicates) |
| `schedule` | string | rate(5 minutes) | EventBridge schedule expression |
| `azureCredentialsSecretName` | string | Required | Secrets Manager secret name |
| `environment` | object | {} | Additional environment variables |

#### Flow Log Processor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | boolean | false | Enable/disable flow log processor |
| `functionName` | string | azure-flowlog-processor | Lambda function name |
| `memorySize` | number | 1024 | Lambda memory in MB |
| `timeout` | number | 600 | Lambda timeout in seconds |
| `reservedConcurrentExecutions` | number | 5 | Reserved concurrent executions |
| `batchSize` | number | 10 | SQS batch size |
| `maximumBatchingWindowInSeconds` | number | 5 | SQS batching window |
| `azureFlowLogsSecretName` | string | Required | Secrets Manager secret name |
| `environment` | object | {} | Additional environment variables |

## Installation

### Step 1: Deploy Azure Infrastructure

Deploy Event Hub and optionally VNet Flow Logs infrastructure using Terraform:

```bash
cd integrations/azure/microsoft_defender_cloud/terraform

# Copy and configure terraform.tfvars
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your Azure subscription details

# Initialize and deploy
terraform init
terraform plan
terraform apply

# Note the outputs for AWS configuration
terraform output
```

### Step 2: Configure AWS CDK

Create or update `config.yaml`:

```bash
cd integrations/security-lake/cdk

# Copy example configuration
cp config.example.yaml config.yaml

# Edit config.yaml and configure the Azure module
# Set integrations.azure.enabled: true
# Configure event processor and flow log processor settings
```

### Step 3: Deploy AWS Infrastructure

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Synthesize CloudFormation template
cdk synth -c configFile=config.yaml

# Deploy to AWS
cdk deploy -c configFile=config.yaml
```

### Step 4: Configure Azure Credentials

After deployment, configure the Azure credentials in AWS Secrets Manager:

```bash
cd integrations/azure/microsoft_defender_cloud/scripts

# Run automated configuration script
./configure-secrets-manager.sh

# Or manually update secrets
aws secretsmanager update-secret \
  --secret-id azure-eventhub-credentials \
  --secret-string '{
    "eventHubNamespace": "your-namespace.servicebus.windows.net",
    "eventHubName": "your-eventhub",
    "consumerGroup": "$Default",
    "connectionString": "Endpoint=sb://your-namespace.servicebus.windows.net/;..."
  }'
```

### Step 5: Verify Microsoft Defender Configuration

Terraform automatically configured Microsoft Defender continuous export during deployment. Verify the configuration:

```bash
# Check Terraform output for continuous export ID
cd ../terraform
terraform output continuous_export_id

# Verify in Azure Portal (optional):
# 1. Navigate to Microsoft Defender for Cloud
# 2. Go to Environment Settings → Continuous Export
# 3. Confirm export to Event Hub is active
```

**Automatic Configuration**: Terraform created the continuous export configuration with all required settings (Security alerts, Recommendations, Secure score).

### Step 6: Verify Integration

Monitor Lambda execution and event flow:

```bash
# Check Event Hub Processor logs
aws logs tail /aws/lambda/azure-eventhub-processor-{env} --follow

# Check transformer queue depth
aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name event-queue-{env} --query QueueUrl --output text) \
  --attribute-names ApproximateNumberOfMessages

# Query Security Lake for Azure events
aws s3 ls s3://aws-security-data-lake-{region}-{hash}/ext/
```

## Lambda Functions

### Event Hub Processor

**Purpose**: Polls Azure Event Hub on a schedule and forwards events to transformer queue.

**Key Features**:
- AMQP protocol for reliable Event Hub consumption
- DynamoDB checkpoint management
- Automatic connection reuse (prevents cold starts)
- Single concurrent execution
- Exponential backoff for transient failures

**Environment Variables**:
- `MODULE_ID`: azure
- `SQS_QUEUE_URL`: Event transformer queue URL
- `AZURE_CREDENTIALS_SECRET_NAME`: Secrets Manager secret name
- `CHECKPOINT_TABLE_NAME`: DynamoDB table name
- `LOGGING_LEVEL`: INFO (default) or DEBUG

**Local Testing**:
```bash
cd modules/azure/src/lambda/event-hub-processor
python local_test.py
pytest test_lambda.py -v
```

### Flow Log Processor

**Purpose**: Processes Azure VNet Flow Logs triggered by Event Grid blob creation events.

**Key Features**:
- Azure AD authentication to Storage Account
- Event Grid Cloud Events v1.0 schema support
- Batch processing of flow log entries
- Parallel processing with multiple concurrent executions
- OCSF transformation for network events

**Environment Variables**:
- `MODULE_ID`: azure
- `SQS_QUEUE_URL`: Event transformer queue URL
- `AZURE_FLOWLOGS_SECRET_NAME`: Secrets Manager secret name
- `LOGGING_LEVEL`: INFO (default) or DEBUG

**Local Testing**:
```bash
cd modules/azure/src/lambda/flow-log-processor
python local_test.py
pytest test_lambda.py -v
```

## IAM Permissions

The module requires the following IAM permissions:

```typescript
// Event Hub Processor Permissions
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue",
    "secretsmanager:DescribeSecret"
  ],
  "Resource": "arn:aws:secretsmanager:{region}:{account}:secret:azure-eventhub-*"
}
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:Query"
  ],
  "Resource": "arn:aws:dynamodb:{region}:{account}:table/azure-eventhub-checkpoint-store"
}
{
  "Effect": "Allow",
  "Action": "sqs:SendMessage",
  "Resource": "arn:aws:sqs:{region}:{account}:event-queue-*"
}

// Flow Log Processor Permissions (if enabled)
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue",
    "secretsmanager:DescribeSecret"
  ],
  "Resource": "arn:aws:secretsmanager:{region}:{account}:secret:azure-flowlogs-*"
}
```

## Monitoring and Troubleshooting

### CloudWatch Metrics

Key metrics to monitor:

- `Invocations`: Lambda function invocations
- `Duration`: Lambda execution time
- `Errors`: Lambda execution errors
- `Throttles`: Lambda throttling events
- `ConcurrentExecutions`: Active Lambda executions

### CloudWatch Logs

Log groups:
- `/aws/lambda/azure-eventhub-processor-{env}`
- `/aws/lambda/azure-flowlog-processor-{env}`

### Common Issues

#### Issue: No events received from Event Hub

**Symptoms**: Event Hub Processor runs successfully but processes zero events

**Solutions**:
1. Verify Event Hub has data: Check Azure Portal metrics
2. Verify connection string: Test in Azure Portal Event Hub explorer
3. Check consumer group: Ensure `$Default` group exists
4. Review checkpoints: Query DynamoDB table for stuck checkpoints

#### Issue: Flow logs not processing

**Symptoms**: Event Grid events trigger Lambda but processing fails

**Solutions**:
1. Verify Azure AD credentials: Test client secret hasn't expired
2. Check Storage Account permissions: Verify service principal has Storage Blob Data Reader role
3. Review Event Grid subscription: Ensure Cloud Event Schema v1.0 is configured
4. Check Lambda logs: Review detailed error messages

#### Issue: DynamoDB throttling

**Symptoms**: `ProvisionedThroughputExceededException` errors

**Solutions**:
1. Review billing mode: Change to PAY_PER_REQUEST if provisioned
2. Increase partition throughput: If using provisioned mode
3. Review checkpoint frequency: Consider reducing polling frequency

#### Issue: Secrets Manager access denied

**Symptoms**: `AccessDeniedException` when accessing secrets

**Solutions**:
1. Verify IAM role permissions: Check Lambda execution role
2. Verify secret ARN: Ensure exact match in policy
3. Check KMS key permissions: If using customer-managed CMK

### Debug Mode

Enable detailed logging:

```yaml
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

## Performance Tuning

### Event Hub Processor

**High Volume Environments** (>1000 events/minute):
```yaml
eventHubProcessor:
  memorySize: 1024
  timeout: 600
  schedule: rate(1 minute)
```

**Low Volume Environments** (<100 events/minute):
```yaml
eventHubProcessor:
  memorySize: 256
  timeout: 120
  schedule: rate(15 minutes)
```

### Flow Log Processor

**High Throughput**:
```yaml
flowLogProcessor:
  memorySize: 2048
  timeout: 900
  reservedConcurrentExecutions: 10
  batchSize: 5
```

**Cost-Optimized**:
```yaml
flowLogProcessor:
  memorySize: 512
  timeout: 300
  reservedConcurrentExecutions: 2
  batchSize: 10
```

## Security Best Practices

1. **Rotate Azure credentials regularly**: Update Secrets Manager every 90 days
2. **Use least privilege IAM roles**: Only grant required permissions
3. **Enable encryption at rest**: Use customer-managed KMS keys in production
4. **Monitor failed authentication**: Set CloudWatch alarms for access denied errors
5. **Implement network isolation**: Use VPC endpoints for AWS service access
6. **Review checkpoint data**: Periodically audit DynamoDB for anomalies
7. **Enable CloudTrail logging**: Audit all Secrets Manager and DynamoDB access

## Cost Optimization

### Development Environment
- Use AWS_OWNED_CMK encryption
- Disable CloudWatch alarms
- Reduce polling frequency
- Lower Lambda memory allocation

### Production Environment
- Enable auto-scaling for DynamoDB (if needed)
- Use reserved concurrency carefully
- Monitor and optimize Lambda execution time
- Implement TTL for DynamoDB checkpoints

**Estimated Monthly Costs** (1000 events/hour):
- Lambda executions: $15-30
- DynamoDB: $5-15
- Secrets Manager: $0.80
- CloudWatch Logs: $5-10
- Total: Approximately $30-60/month

## Version History

### Version 1.0.0 (2025-01-22)
- Initial modular Azure integration
- Event Hub processor with checkpoint store
- Flow Log processor with Event Grid integration
- Full OCSF transformation support
- Comprehensive monitoring and alerting

## References

**Framework Documentation:**
- [Security Lake Integration Framework](../../README.md) - Core framework overview
- [Module Interface Specification](../../docs/MODULE_INTERFACE_SPEC.md) - Module development standards
- [Module Development Guide](../../docs/MODULE_DEVELOPMENT_GUIDE.md) - Creating new modules
- [Configuration Schema](../../docs/CONFIG_SCHEMA.md) - Complete configuration reference
- [Installation Guide](../../../INSTALLATION_GUIDE.md) - Framework installation walkthrough
- [Threat Model](../../docs/THREAT_MODEL.md) - Security analysis and controls

**Related Integrations:**
- [Azure Defender Main README](../../../../azure/microsoft_defender_cloud/README.md) - Legacy standalone integration
- [Google SCC Module](../google-scc/README.md) - GCP Security Command Center integration
- [GCP VPC Flow Logs](../../../../../gcp-vpc-flow-logs/README.md) - GCP network visibility

**Lambda Function Documentation:**
- [Event Hub Processor README](src/lambda/event-hub-processor/README.md) - Detailed processor documentation
- [Event Hub Processor Local Testing](src/lambda/event-hub-processor/LOCAL_TESTING.md) - Local development
- [Event Transformer](../../src/lambda/event-transformer/README.md) - Transformation pipeline
- [Flow Log Processor](../../src/lambda/flow-log-processor/README.md) - Network flow processing

**Azure Resources:**
- [Microsoft Defender Blog Post](../../../../../BLOG_POST.md) - Real-world implementation
- [Azure Terraform Modules](../../../../azure/microsoft_defender_cloud/terraform/README.md) - Infrastructure deployment
- [Azure Configuration Scripts](../../../../azure/microsoft_defender_cloud/scripts/README.md) - Automation tools

**External Resources:**
- [Azure Event Hubs Documentation](https://docs.microsoft.com/en-us/azure/event-hubs/)
- [AWS Security Lake Documentation](https://docs.aws.amazon.com/security-lake/)
- [OCSF Schema](https://schema.ocsf.io/)

## Support

For questions or issues with this module:
1. Review this documentation and troubleshooting section
2. Check CloudWatch Logs for detailed error messages
3. Consult the Module Development Guide
4. Contact your AWS Professional Services team