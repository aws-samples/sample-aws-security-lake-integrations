# OpenSearch Serverless Security Analytics - Quickstart Guide

This guide provides step-by-step instructions for deploying the OpenSearch Serverless security analytics stack with default values.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Step-by-Step Deployment](#step-by-step-deployment)
- [Post-Deployment: CloudWatch Logs Subscription](#post-deployment-cloudwatch-logs-subscription)
- [Verification](#verification)
- [Configuration Reference](#configuration-reference)
- [Next Steps](#next-steps)

## Prerequisites

### Required Software

| Component | Minimum Version | Installation |
|-----------|-----------------|--------------|
| Node.js | 18.0.0 or higher | [Download from nodejs.org](https://nodejs.org/) |
| npm | 9.0.0 or higher | Included with Node.js |
| AWS CDK CLI | 2.0.0 or higher | `npm install -g aws-cdk` |
| AWS CLI | 2.0.0 or higher | [AWS CLI Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| Docker | Latest | Required for Lambda bundling |

### AWS Account Configuration

1. **Configure AWS credentials** with appropriate permissions:
   ```bash
   aws configure
   ```
   
2. **Verify your credentials**:
   ```bash
   aws sts get-caller-identity
   ```

3. **Required IAM permissions** for the deploying user/role:
   - CloudFormation: `cloudformation:*`
   - OpenSearch Serverless: `aoss:*`
   - Lambda: `lambda:*`
   - IAM: `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PassRole`
   - S3: `s3:*`
   - KMS: `kms:CreateKey`, `kms:CreateAlias` (if using customer-managed encryption)
   - Kinesis: `kinesis:*`
   - OSIS: `osis:*`

### Bootstrap CDK (First-Time Only)

If this is your first CDK deployment in the target AWS account/region, bootstrap CDK:

```bash
cdk bootstrap aws://<ACCOUNT_ID>/<REGION>
```

## Step-by-Step Deployment

### Step 1: Navigate to the Project Directory

```bash
cd integrations/aws/opensearch-serverless
```

### Step 2: Install Dependencies

```bash
npm install
```

Expected output:
```
added 345 packages, and audited 346 packages in 12s
```

### Step 3: Create Configuration File

Copy the example configuration template:

```bash
cp config.yaml.example config.yaml
```

### Step 4: Configure Required Settings

Edit [`config.yaml`](config.yaml) with your values. Minimum required configuration:

```yaml
# Project identification
projectName: opensearch-quickstart
environment: dev
awsRegion: us-east-1

# Resource tags
tagSource: aws-delivery-kits
tagProduct: security-lake-integrations
tagKitVersion: 1.0.0

# Collection settings
collection:
  name: security-data
  type: TIMESERIES
  description: Security event data collection
  standbyReplicas: ENABLED

# OpenSearch Application (UI)
application:
  enabled: true
  name: "security-app"
  iamIdentityCenter:
    enabled: false
  admins:
    iamPrincipals:
      - "*"  # All users for initial deployment - restrict after testing
  dataSource:
    autoAddCollection: true
    description: "Security Lake data"

# Workspace for organizing dashboards
workspaces:
  enabled: true
  workspaces:
    - name: "security-operations"
      description: "SOC workspace"
      color: "#E74C3C"
      feature: "use-case-observability"

# Encryption (shared KMS key)
encryption:
  enabled: true
  useSharedKey: true

# Network access
network:
  accessType: Public
  allowFromPublic: true

# Data access - IMPORTANT: Add your IAM principals
dataAccess:
  principals:
    - arn:aws:sts::<YOUR_ACCOUNT_ID>:assumed-role/<YOUR_ROLE>/*
  permissions:
    - aoss:*

# Security Lake pipeline (if using Security Lake)
# securityLakePipeline:
#   queueUrl: "https://sqs.<region>.amazonaws.com/<account>/AmazonSecurityLake-xxx-Main-Queue"

# CloudWatch Logs pipeline
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

# Pre-built dashboards and index patterns
savedObjects:
  enabled: true
  imports:
    - name: "indexpatterns"
      file: "index-patterns.ndjson"
      overwrite: true
    - name: "logProcessing"
      file: "log-processing.ndjson"
      overwrite: true
    - name: "cloudApiAudit"
      file: "cloud-api-audit.ndjson"
      overwrite: true
    - name: "flowlogs"
      file: "flowlogs.ndjson"
      overwrite: true
    - name: "detectionsAlerts"
      file: "detections-alerts.ndjson"
      overwrite: true
```

**Important**: Replace `<YOUR_ACCOUNT_ID>` and `<YOUR_ROLE>` with actual values.

### Step 5: Build the Project

**Critical**: Always run build before any CDK command to compile TypeScript to JavaScript.

```bash
npm run build
```

### Step 6: Preview the Deployment (Optional)

Generate and review the CloudFormation template:

```bash
cdk synth -c configFile=config.yaml
```

Compare changes with any existing deployment:

```bash
cdk diff -c configFile=config.yaml
```

### Step 7: Deploy the Stack

```bash
cdk deploy -c configFile=config.yaml
```

When prompted to approve IAM changes, review and type `y` to confirm.

**Expected deployment time**: 10-15 minutes

### Step 8: Note the Outputs

After successful deployment, the stack outputs will display:

```
Outputs:
opensearch-quickstart.CollectionId = abc123xyz
opensearch-quickstart.CollectionArn = arn:aws:aoss:us-east-1:123456789012:collection/abc123xyz
opensearch-quickstart.CollectionEndpoint = abc123xyz.us-east-1.aoss.amazonaws.com
opensearch-quickstart.DashboardEndpoint = https://abc123xyz.us-east-1.aoss.amazonaws.com/_dashboards
opensearch-quickstart.ApplicationId = app-123456
opensearch-quickstart.ApplicationEndpoint = https://application-security-app-app123.us-east-1.opensearch.amazonaws.com
opensearch-quickstart.KinesisStreamArn = arn:aws:kinesis:us-east-1:123456789012:stream/cloudwatch-logs-stream
opensearch-quickstart.CloudWatchLogsRoleArn = arn:aws:iam::123456789012:role/opensearch-quickstart-CloudWatchLogsKinesisRole
opensearch-quickstart.PipelineName = cloudwatch-logs-pipeline
```

Save these values for the next step.

## Post-Deployment: CloudWatch Logs Subscription

The stack creates a Kinesis Data Stream and IAM role for CloudWatch Logs, but you must manually create subscription filters to stream logs.

### Get Required ARNs

```bash
# Get Kinesis stream ARN
KINESIS_ARN=$(aws cloudformation describe-stacks \
  --stack-name opensearch-quickstart \
  --query 'Stacks[0].Outputs[?OutputKey==`KinesisStreamArn`].OutputValue' \
  --output text)

# Get CloudWatch Logs role ARN
ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name opensearch-quickstart \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudWatchLogsRoleArn`].OutputValue' \
  --output text)

echo "Kinesis ARN: $KINESIS_ARN"
echo "Role ARN: $ROLE_ARN"
```

### Create Subscription Filters

Create a subscription filter for each log group you want to ingest:

```bash
# Example: Lambda function logs
aws logs put-subscription-filter \
  --log-group-name /aws/lambda/my-function \
  --filter-name opensearch-subscription \
  --filter-pattern "" \
  --destination-arn $KINESIS_ARN \
  --role-arn $ROLE_ARN

# Example: ECS container logs
aws logs put-subscription-filter \
  --log-group-name /ecs/my-service \
  --filter-name opensearch-subscription \
  --filter-pattern "" \
  --destination-arn $KINESIS_ARN \
  --role-arn $ROLE_ARN

# Example: API Gateway logs (errors only)
aws logs put-subscription-filter \
  --log-group-name /aws/apigateway/my-api \
  --filter-name opensearch-errors \
  --filter-pattern "ERROR" \
  --destination-arn $KINESIS_ARN \
  --role-arn $ROLE_ARN
```

### Batch Subscription Script

For multiple log groups, create a script:

```bash
#!/bin/bash
# subscribe-logs.sh

KINESIS_ARN="<your-kinesis-arn>"
ROLE_ARN="<your-role-arn>"

LOG_GROUPS=(
  "/aws/lambda/function-1"
  "/aws/lambda/function-2"
  "/ecs/service-1"
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

## Verification

### Verify Collection Status

```bash
aws opensearchserverless batch-get-collection \
  --ids <COLLECTION_ID> \
  --query 'collectionDetails[0].status'
```

Expected output: `"ACTIVE"`

### Verify Pipeline Status

```bash
aws osis get-pipeline --pipeline-name cloudwatch-logs-pipeline \
  --query 'Pipeline.Status'
```

Expected output: `"ACTIVE"`

### Access OpenSearch Dashboards

1. Get the Application endpoint:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name opensearch-quickstart \
     --query 'Stacks[0].Outputs[?OutputKey==`ApplicationEndpoint`].OutputValue' \
     --output text
   ```

2. Open the URL in your browser
3. Sign in with your AWS credentials
4. Navigate to your workspace to view pre-built dashboards

### Verify Data Ingestion

After creating subscription filters and generating some log events:

1. Open OpenSearch Dashboards
2. Go to **Discover**
3. Select an index pattern (e.g., `*-log_data-*`)
4. Verify log events are appearing

## Configuration Reference

### Understanding dataAccess Principals

The `dataAccess.principals` configuration defines which IAM principals can access the collection.

**How to Find Your Principal ARN:**

```bash
# Current caller identity
aws sts get-caller-identity --query 'Arn' --output text

# IAM role ARN
aws iam get-role --role-name <ROLE_NAME> --query 'Role.Arn' --output text

# IAM user ARN
aws iam get-user --user-name <USER_NAME> --query 'User.Arn' --output text
```

**Example formats:**

```yaml
dataAccess:
  principals:
    # IAM Role
    - "arn:aws:iam::123456789012:role/MyRole"
    
    # Assumed Role (any session)
    - "arn:aws:sts::123456789012:assumed-role/AdminRole/*"
    
    # IAM User
    - "arn:aws:iam::123456789012:user/analyst"
```

### Understanding securityLakePipeline Configuration

If using AWS Security Lake, add the pipeline configuration:

```yaml
securityLakePipeline:
  queueUrl: "https://sqs.us-east-1.amazonaws.com/123456789012/AmazonSecurityLake-xxx-Main-Queue"
```

**Finding the Queue URL:**

1. Open AWS Security Lake Console
2. Navigate to **Subscribers**
3. Find or create a subscriber for OpenSearch
4. Copy the **SQS Queue URL**

Or via CLI:
```bash
aws sqs list-queues --queue-name-prefix "AmazonSecurityLake" --output table
```

### Filter Pattern Syntax

CloudWatch Logs subscription filters support pattern matching:

| Pattern | Description |
|---------|-------------|
| `""` | All log events |
| `ERROR` | Events containing "ERROR" |
| `{ $.level = "ERROR" }` | JSON field matching |
| `{ $.statusCode >= 400 }` | Numeric comparison |

See [CloudWatch Logs Filter Pattern Syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html).

## Next Steps

After successful deployment:

1. **Create subscription filters** for your CloudWatch Log groups using the commands above
2. **Restrict access** - Update `dataAccess.principals` from `"*"` to specific IAM roles/users
3. **Configure Security Lake** (optional) - Add `securityLakePipeline.queueUrl` for OCSF data ingestion
4. **Customize dashboards** - Modify the pre-built dashboards in OpenSearch for your use case
5. **Set up alerts** - Configure OpenSearch alerting for security events

For comprehensive documentation, see [`README.md`](README.md).
