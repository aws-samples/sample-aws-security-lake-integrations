# OpenSearch Serverless Security Analytics Stack

AWS CDK project for deploying a comprehensive OpenSearch Serverless solution optimized for security data visualization and analysis. This stack provides a complete data pipeline from AWS Security Lake and CloudWatch Logs into OpenSearch for centralized security analytics.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Post-Deployment: CloudWatch Logs Subscription](#post-deployment-cloudwatch-logs-subscription)
- [Accessing the Dashboards](#accessing-the-dashboards)
- [Stack Outputs](#stack-outputs)
- [Troubleshooting](#troubleshooting)
- [Cost Considerations](#cost-considerations)
- [Cleanup](#cleanup)

## Overview

This CDK stack deploys a fully integrated security analytics solution consisting of:

| Component | Description |
|-----------|-------------|
| **OpenSearch Serverless Collection** | TIMESERIES collection optimized for log and security event data |
| **OpenSearch Application** | Unified UI for data exploration with IAM/IAM Identity Center authentication |
| **OpenSearch Workspaces** | Organized containers for team-specific dashboards and visualizations |
| **Saved Objects Importer** | Automated deployment of pre-built dashboards and index patterns |
| **Security Lake Pipeline** | Ingests OCSF Parquet data from AWS Security Lake via SQS |
| **CloudWatch Logs Pipeline** | Ingests CloudWatch Logs via Kinesis Data Streams |

## Architecture

```
                                    +---------------------------+
                                    |   OpenSearch Application  |
                                    |         (UI)              |
                                    +-------------+-------------+
                                                  |
                                    +-------------v-------------+
                                    | OpenSearch Serverless     |
                                    | Collection (TIMESERIES)   |
                                    +--^-------------------^----+
                                       |                   |
              +------------------------+                   +------------------------+
              |                                                                     |
+-------------+-------------+                                       +---------------+-----------+
|  CloudWatch Logs Pipeline |                                       | Security Lake Pipeline    |
|  (OpenSearch Ingestion)   |                                       | (OpenSearch Ingestion)    |
+-------------^-------------+                                       +---------------^-----------+
              |                                                                     |
+-------------+-------------+                                       +---------------+-----------+
|  Kinesis Data Stream      |                                       |  SQS Queue                |
|  (CloudWatch Logs dest.)  |                                       |  (EventBridge Events)     |
+-------------^-------------+                                       +---------------^-----------+
              |                                                                     |
+-------------+-------------+                                       +---------------+-----------+
| CloudWatch Logs           |                                       | AWS Security Lake         |
| (Subscription Filters)    |                                       | (OCSF Parquet in S3)      |
+---------------------------+                                       +---------------------------+
```

## Features

### OpenSearch Serverless Collection

- **TIMESERIES** type optimized for sequential time-stamped data
- High availability with standby replicas (configurable)
- Automatic scaling based on data volume
- Public network access with IAM authentication (no VPC required)
- Three encryption modes: AWS-owned key, existing CMK, or CDK-managed shared key

### OpenSearch Application (UI)

- Unified search interface for security data exploration
- IAM authentication (default) or IAM Identity Center (SSO) integration
- Automatic data source connection to the serverless collection
- Configurable administrator principals

### OpenSearch Workspaces

- Logical containers for organizing dashboards by team or use case
- Color-coded workspaces for visual organization
- Feature-based configuration (observability, search, security analytics)
- Automatic data source association

### Saved Objects Importer

Pre-built dashboards and index patterns are automatically deployed:

| Asset | Description |
|-------|-------------|
| [`index-patterns.ndjson`](assets/index-patterns.ndjson) | OCSF index patterns for Security Lake data |
| [`log-processing.ndjson`](assets/log-processing.ndjson) | Log processing and ingestion monitoring |
| [`cloud-api-audit.ndjson`](assets/cloud-api-audit.ndjson) | CloudTrail and API audit visualizations |
| [`external-workload-logs.ndjson`](assets/external-workload-logs.ndjson) | External workload log analytics |
| [`aws-workload-logs.ndjson`](assets/aws-workload-logs.ndjson) | AWS workload monitoring dashboards |
| [`flowlogs.ndjson`](assets/flowlogs.ndjson) | VPC Flow Logs analysis dashboards |
| [`detections-alerts.ndjson`](assets/detections-alerts.ndjson) | Security detections and alerts |

### Security Lake Pipeline

- Reads OCSF Parquet files from Security Lake S3 buckets
- Processes S3 event notifications via SQS queue
- Comprehensive OCSF data transformation (timestamp conversion, field normalization)
- Dynamic index naming: `{product}-{class}-ocsf-cuid-{class_uid}-%{yyyy.MM.dd}`
- S3 DLQ for failed records and backup for all records

### CloudWatch Logs Pipeline

- Reads from Kinesis Data Stream (subscription filter destination)
- Gzip decompression and JSON parsing
- Log group-based dynamic indexing: `${log_group}-log_data-%{yyyy.MM.dd}`
- Metrics extraction via grok patterns
- S3 DLQ and backup sinks

## Prerequisites

### Required Software

| Component | Version | Installation |
|-----------|---------|--------------|
| Node.js | >= 18.0.0 | [Download](https://nodejs.org/) |
| npm | >= 9.0.0 | Included with Node.js |
| AWS CDK CLI | >= 2.0.0 | `npm install -g aws-cdk` |
| AWS CLI | >= 2.0.0 | [Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| Docker | Latest | Required for Lambda bundling |

### AWS Account Requirements

- IAM permissions for CloudFormation, OpenSearch Serverless, Lambda, S3, KMS, IAM, Kinesis
- Service quotas for OpenSearch Serverless collections (default: 5 per account)
- For Security Lake pipeline: AWS Security Lake must be configured and producing data
- For Security Lake pipeline: Security Lake SQS subscriber queue URL

## Installation

```bash
# Navigate to project directory
cd integrations/aws/opensearch-serverless

# Install dependencies
npm install

# Verify installation
npm run build
```

## Configuration

### Step 1: Copy Configuration Template

```bash
cp config.yaml.example config.yaml
```

### Step 2: Edit Configuration

Edit [`config.yaml`](config.yaml) with your specific values. Key sections:

#### Project Settings

```yaml
projectName: my-security-analytics
environment: dev
awsRegion: us-east-1

tagSource: aws-delivery-kits
tagProduct: security-lake-integrations
tagKitVersion: 1.0.0
```

#### Collection Configuration

```yaml
collection:
  name: security-data-collection
  type: TIMESERIES
  description: Security event data collection
  standbyReplicas: ENABLED
```

#### OpenSearch Application (UI)

```yaml
application:
  enabled: true
  name: "security-lake-app"
  iamIdentityCenter:
    enabled: false
  admins:
    iamPrincipals:
      - "*"  # All users for initial deployment
  dataSource:
    autoAddCollection: true
    description: "Security Lake data collection"
```

#### Workspaces

```yaml
workspaces:
  enabled: true
  workspaces:
    - name: "security-operations"
      description: "SOC workspace for threat detection"
      color: "#E74C3C"
      feature: "use-case-observability"
```

#### Encryption

```yaml
encryption:
  enabled: true
  useSharedKey: true  # Creates CDK-managed KMS key
```

#### Data Access

```yaml
dataAccess:
  principals:
    - arn:aws:sts::123456789012:assumed-role/Admin/*
  permissions:
    - aoss:*
```

#### Security Lake Pipeline

```yaml
securityLakePipeline:
  queueUrl: "https://sqs.us-east-1.amazonaws.com/123456789012/AmazonSecurityLake-xxx-Main-Queue"
```

#### Kinesis and CloudWatch Logs Pipeline

```yaml
kinesis:
  streamName: cloudwatch-logs-stream
  streamMode: ON_DEMAND
  retentionPeriodHours: 24
  encryption:
    enabled: true
    useSharedKey: true

pipeline:
  enabled: true
  pipelineName: cloudwatch-logs-pipeline
  minCapacity: 2
  maxCapacity: 4
  logGroupPattern: '.*'
  dlqBucket:
    enabled: true
    lifecycleRetentionDays: 2
    encryption:
      useSharedKey: true
```

#### Saved Objects

```yaml
savedObjects:
  enabled: true
  imports:
    - name: "indexpatterns"
      file: "index-patterns.ndjson"
      overwrite: true
    - name: "logProcessing"
      file: "log-processing.ndjson"
      overwrite: true
    # Add additional imports as needed
```

See [`config.yaml.example`](config.yaml.example) for complete configuration options and documentation.

## Deployment

### Build and Synthesize

```bash
# Build TypeScript
npm run build

# Synthesize CloudFormation template (validation)
cdk synth -c configFile=config.yaml
```

### Review Changes

```bash
cdk diff -c configFile=config.yaml
```

### Deploy

```bash
cdk deploy -c configFile=config.yaml
```

Deployment creates resources in the following order:

1. KMS Key (if `useSharedKey: true`)
2. Encryption and Network Security Policies
3. OpenSearch Serverless Collection
4. IAM Roles (Pipeline, CloudWatch Logs)
5. Kinesis Data Stream
6. S3 DLQ Bucket
7. OpenSearch Application
8. OpenSearch Workspaces
9. Saved Objects Import
10. OpenSearch Ingestion Pipelines

**Expected deployment time**: 10-15 minutes

## Post-Deployment: CloudWatch Logs Subscription

After deployment, you must manually create CloudWatch Logs subscription filters to stream logs to the Kinesis Data Stream. The stack creates the necessary IAM role for CloudWatch Logs but does not create subscription filters automatically.

### Getting Required ARNs

Retrieve the Kinesis stream ARN and CloudWatch Logs role ARN from stack outputs:

```bash
# Get all stack outputs
aws cloudformation describe-stacks \
  --stack-name <your-stack-name> \
  --query 'Stacks[0].Outputs' \
  --output table

# Or get specific values
KINESIS_ARN=$(aws cloudformation describe-stacks \
  --stack-name <your-stack-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`KinesisStreamArn`].OutputValue' \
  --output text)

ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name <your-stack-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchLogsRoleArn`].OutputValue' \
  --output text)

echo "Kinesis ARN: $KINESIS_ARN"
echo "Role ARN: $ROLE_ARN"
```

### Creating Subscription Filters

Create subscription filters for each log group you want to stream to OpenSearch:

```bash
# Example: Subscribe Lambda function logs
aws logs put-subscription-filter \
  --log-group-name /aws/lambda/my-function \
  --filter-name opensearch-subscription \
  --filter-pattern "" \
  --destination-arn $KINESIS_ARN \
  --role-arn $ROLE_ARN

# Example: Subscribe with filter pattern (only ERROR logs)
aws logs put-subscription-filter \
  --log-group-name /aws/lambda/my-function \
  --filter-name opensearch-errors-only \
  --filter-pattern "ERROR" \
  --destination-arn $KINESIS_ARN \
  --role-arn $ROLE_ARN

# Example: Subscribe ECS container logs
aws logs put-subscription-filter \
  --log-group-name /ecs/my-service \
  --filter-name opensearch-subscription \
  --filter-pattern "" \
  --destination-arn $KINESIS_ARN \
  --role-arn $ROLE_ARN
```

### Filter Pattern Syntax

CloudWatch Logs subscription filters support pattern matching:

| Pattern | Description |
|---------|-------------|
| `""` | All log events (no filtering) |
| `ERROR` | Events containing "ERROR" |
| `[timestamp, requestId, level=ERROR]` | Space-delimited with field matching |
| `{ $.level = "ERROR" }` | JSON field matching |
| `{ $.level = "ERROR" \|\| $.level = "WARN" }` | Multiple conditions |

See [CloudWatch Logs Filter Pattern Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html) for complete documentation.

### Automating Subscription Filter Creation

For multiple log groups, create a script:

```bash
#!/bin/bash
# subscribe-logs.sh

KINESIS_ARN="<your-kinesis-arn>"
ROLE_ARN="<your-cloudwatch-role-arn>"

# List of log groups to subscribe
LOG_GROUPS=(
  "/aws/lambda/function-1"
  "/aws/lambda/function-2"
  "/ecs/service-1"
  "/aws/apigateway/my-api"
)

for LOG_GROUP in "${LOG_GROUPS[@]}"; do
  echo "Creating subscription for $LOG_GROUP..."
  aws logs put-subscription-filter \
    --log-group-name "$LOG_GROUP" \
    --filter-name "opensearch-subscription" \
    --filter-pattern "" \
    --destination-arn "$KINESIS_ARN" \
    --role-arn "$ROLE_ARN"
done
```

### Verifying Subscription Filters

```bash
# List subscription filters for a log group
aws logs describe-subscription-filters \
  --log-group-name /aws/lambda/my-function

# Verify Kinesis stream is receiving data
aws kinesis describe-stream-summary \
  --stream-name <your-stream-name>
```

## Accessing the Dashboards

### OpenSearch Application URL

The OpenSearch Application endpoint is provided in the stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name <your-stack-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`ApplicationEndpoint`].OutputValue' \
  --output text
```

URL format: `https://application-{app-name}-{app-id}.{region}.opensearch.amazonaws.com`

### Authentication

1. Navigate to the Application URL in your browser
2. Sign in with AWS IAM credentials (or IAM Identity Center if configured)
3. Select your workspace to view dashboards

### Collection Dashboard URL

The direct collection dashboard endpoint is also available:

```bash
aws cloudformation describe-stacks \
  --stack-name <your-stack-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`DashboardEndpoint`].OutputValue' \
  --output text
```

## Stack Outputs

| Output | Description |
|--------|-------------|
| `CollectionId` | OpenSearch Serverless collection ID |
| `CollectionArn` | Collection Amazon Resource Name |
| `CollectionEndpoint` | Collection API endpoint |
| `DashboardEndpoint` | OpenSearch Dashboards URL |
| `ApplicationId` | OpenSearch Application ID |
| `ApplicationArn` | Application Amazon Resource Name |
| `ApplicationEndpoint` | Application UI endpoint URL |
| `KinesisStreamName` | Kinesis Data Stream name |
| `KinesisStreamArn` | Kinesis stream ARN for subscription filters |
| `CloudWatchLogsRoleArn` | IAM role ARN for CloudWatch Logs subscriptions |
| `DlqBucketName` | S3 bucket for failed records |
| `PipelineName` | CloudWatch Logs OSI pipeline name |
| `SecurityLakePipelineName` | Security Lake OSI pipeline name |
| `KmsKeyArn` | KMS key ARN (if using shared key) |

## Troubleshooting

### Pipeline Not Ingesting Data

1. **Check pipeline status**:
   ```bash
   aws osis get-pipeline --pipeline-name <pipeline-name>
   ```

2. **View pipeline logs**:
   ```bash
   aws logs tail /aws/vendedlogs/OpenSearchIngestion/<pipeline-name> --follow
   ```

3. **Verify Kinesis stream has data**:
   ```bash
   aws kinesis describe-stream-summary --stream-name <stream-name>
   ```

4. **Check subscription filter status**:
   ```bash
   aws logs describe-subscription-filters --log-group-name <log-group>
   ```

### Access Denied Errors

1. **Verify IAM principal is in data access policy**:
   - Check [`config.yaml`](config.yaml) `dataAccess.principals` includes your IAM role/user ARN
   - Redeploy stack after updating configuration

2. **Add IAM permissions**:
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "aoss:APIAccessAll",
       "aoss:DashboardsAccessAll"
     ],
     "Resource": "arn:aws:aoss:*:*:collection/*"
   }
   ```

### Saved Objects Not Appearing

1. **Check Lambda logs**:
   ```bash
   aws logs tail /aws/lambda/<importer-function-name> --follow
   ```

2. **Verify NDJSON files in S3**:
   ```bash
   aws s3 ls s3://<assets-bucket-name>/
   ```

3. **Re-import by updating stack**:
   ```bash
   cdk deploy -c configFile=config.yaml
   ```

### Security Lake Pipeline Issues

1. **Verify SQS queue URL** is correct in configuration
2. **Check Security Lake subscriber** is configured with correct SQS destination
3. **Verify IAM permissions** for reading Security Lake S3 buckets
4. **Check DLQ bucket** for failed records:
   ```bash
   aws s3 ls s3://<dlq-bucket>/dlq/security-lake-failures/ --recursive
   ```

## Cost Considerations

### OpenSearch Serverless

- **Indexing OCUs**: Minimum 2 OCUs when active (~$350/month)
- **Search OCUs**: Minimum 2 OCUs when active (~$350/month)
- **Storage**: $0.024/GB-month

### OpenSearch Ingestion Pipelines

- **OCU pricing**: ~$0.24/OCU-hour
- **Minimum**: 2 OCUs per pipeline (~$350/month each)
- Two pipelines (CloudWatch + Security Lake) = ~$700/month

### Kinesis Data Streams

- **ON_DEMAND**: Pay per GB ingested/retrieved
- **PROVISIONED**: $0.015/shard-hour + data transfer

### S3 Storage

- **DLQ bucket**: $0.023/GB-month (auto-deleted after retention period)

### KMS

- **Customer-managed key**: $1/month + $0.03/10,000 requests

**Estimated minimum cost**: ~$1,400-1,800/month (varies by region and usage)

## Cleanup

### Destroy Stack

```bash
cdk destroy -c configFile=config.yaml
```

### Manual Cleanup (if stack deletion fails)

1. **Delete subscription filters first**:
   ```bash
   aws logs delete-subscription-filter \
     --log-group-name <log-group> \
     --filter-name opensearch-subscription
   ```

2. **Empty and delete S3 buckets** (if retention policy prevents deletion)

3. **Delete collection manually**:
   ```bash
   aws opensearchserverless delete-collection --id <collection-id>
   ```

4. **Retry stack deletion**:
   ```bash
   aws cloudformation delete-stack --stack-name <stack-name>
   ```

**Warning**: Destroying the stack permanently deletes all indexed data in the collection.

## Related Documentation

- [AWS OpenSearch Serverless Documentation](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html)
- [OpenSearch Ingestion Documentation](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ingestion.html)
- [AWS Security Lake Documentation](https://docs.aws.amazon.com/security-lake/)
- [OCSF Schema](https://schema.ocsf.io/)
- [CloudWatch Logs Subscription Filters](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/SubscriptionFilters.html)

## License

Copyright 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.

This AWS Content is provided subject to the terms of the AWS Customer Agreement available at http://aws.amazon.com/agreement or other written agreement between Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
