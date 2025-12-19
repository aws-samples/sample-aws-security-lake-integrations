# Security Lake Integration Configuration Schema

This document provides comprehensive documentation for all configuration parameters used in the Security Lake CDK integration stack. The configuration file controls infrastructure deployment, processing behavior, encryption settings, and integration module activation.

## Table of Contents

- [Overview](#overview)
- [Configuration File Location](#configuration-file-location)
- [Core Configuration Sections](#core-configuration-sections)
  - [Project Configuration](#project-configuration)
  - [Resource Tagging](#resource-tagging)
  - [Encryption Configuration](#encryption-configuration)
  - [Security Lake Configuration](#security-lake-configuration)
  - [Core Processing Configuration](#core-processing-configuration)
  - [SQS Queue Configuration](#sqs-queue-configuration)
  - [CloudTrail Configuration](#cloudtrail-configuration)
  - [Security Hub Configuration](#security-hub-configuration)
  - [Monitoring Configuration](#monitoring-configuration)
  - [Integration Modules Configuration](#integration-modules-configuration)
- [Lambda Layer Configuration](#lambda-layer-configuration)
- [Configuration Examples](#configuration-examples)
- [Validation Rules](#validation-rules)

## Overview

The configuration file (`config.yaml`) is a YAML-formatted file that defines all aspects of the Security Lake integration deployment. It uses a hierarchical structure to organize settings for core infrastructure, processing components, and integration modules.

**Reference Example**: See [`config.example.yaml`](../config.example.yaml) for a complete example configuration with all available parameters.

## Configuration File Location

The configuration file must be located at:
```
integrations/security-lake/cdk/config.yaml
```

When deploying the CDK stack, reference the configuration file using:
```bash
cdk deploy -c configFile=config.yaml
```

## Core Configuration Sections

### Project Configuration

Defines basic project identification and AWS environment settings.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `projectName` | string | Yes | - | Name of the project, used in resource naming |
| `environment` | string | Yes | - | Deployment environment: `dev`, `staging`, or `prod` |
| `awsRegion` | string | Yes | - | AWS region for deployment (e.g., `us-east-1`, `ca-central-1`) |
| `accountId` | string | No | Auto-detected | AWS account ID. Leave empty for auto-detection |

**Example:**
```yaml
projectName: security-lake-integration
environment: dev
awsRegion: ca-central-1
accountId: ''  # Auto-detected if empty
```

### Resource Tagging

Defines tags applied to all resources for organization and cost tracking.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tagSource` | string | No | - | Source identifier tag |
| `tagProduct` | string | No | - | Product identifier tag |
| `tagKitVersion` | string | No | - | Version tag for the delivery kit |
| `tags` | array | No | [] | Custom tags as key-value pairs |
| `tags[].key` | string | Yes | - | Tag key |
| `tags[].value` | string | Yes | - | Tag value |

**Example:**
```yaml
tagSource: ProServe Delivery Kit
tagProduct: Security-Lake-Integration-Framework
tagKitVersion: 2.0.0

tags:
  - key: Project
    value: Security-Lake-Integration
  - key: Environment
    value: dev
  - key: Owner
    value: Security-Team
```

### Encryption Configuration

Controls KMS encryption settings for all resources in the stack.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `encryption.enabled` | boolean | No | true | Enable/disable encryption |
| `encryption.keyType` | string | No | CUSTOMER_MANAGED_CMK | Key type: `AWS_OWNED_CMK` or `CUSTOMER_MANAGED_CMK` |
| `encryption.keyAlias` | string | No | - | Alias for the KMS key |
| `encryption.keyDescription` | string | No | - | Description of the KMS key |
| `encryption.keyRotationEnabled` | boolean | No | true | Enable automatic key rotation |
| `encryption.keyPendingWindowInDays` | number | No | 30 | Days before key deletion (7-30) |

**Key Types:**
- `AWS_OWNED_CMK`: AWS-managed keys (no additional cost)
- `CUSTOMER_MANAGED_CMK`: Customer-managed keys (supports rotation, audit logging)

**Example:**
```yaml
encryption:
  enabled: true
  keyType: CUSTOMER_MANAGED_CMK
  keyAlias: security-lake-integration
  keyDescription: Shared KMS key for Security Lake integration framework
  keyRotationEnabled: true
  keyPendingWindowInDays: 30
```

### Security Lake Configuration

Configures AWS Security Lake integration and custom log source creation.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `securityLake.enabled` | boolean | Yes | - | Enable Security Lake integration |
| `securityLake.s3Bucket` | string | Yes | - | Pre-existing Security Lake S3 bucket name |
| `securityLake.externalId` | string | Yes | - | External ID for Security Lake IAM role trust policy |
| `securityLake.serviceRole` | string | Yes | - | IAM role name for Glue crawler (typically `SecurityLakeGlueCrawler`) |
| `securityLake.OCSFEventClass` | array | Yes | - | OCSF event class definitions |
| `securityLake.OCSFEventClass[].sourceName` | string | Yes | - | Name of the custom log source |
| `securityLake.OCSFEventClass[].sourceVersion` | string | Yes | - | Version of the custom log source |
| `securityLake.OCSFEventClass[].eventClasses` | array | Yes | - | OCSF event classes (e.g., `SECURITY_FINDING`, `COMPLIANCE_FINDING`) |

**IMPORTANT**: The Security Lake S3 bucket MUST exist before deployment. The stack does not create this bucket.

**Example:**
```yaml
securityLake:
  enabled: true
  s3Bucket: aws-security-data-lake-ca-central-1-abcd1234
  externalId: YOUR-SECURE-RANDOM-STRING-HERE
  serviceRole: SecurityLakeGlueCrawler
  OCSFEventClass:
    - sourceName: unifiedSecurityEvents
      sourceVersion: '1.0'
      eventClasses:
        - SECURITY_FINDING
        - VULNERABILITY_FINDING
        - COMPLIANCE_FINDING
```

### Core Processing Configuration

Defines Lambda functions for core event processing.

#### Event Transformer

Transforms security events from SQS into OCSF format and routes to Security Lake.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `coreProcessing.eventTransformer.enabled` | boolean | Yes | - | Enable event transformer Lambda |
| `coreProcessing.eventTransformer.functionName` | string | No | event-transformer | Lambda function name |
| `coreProcessing.eventTransformer.runtime` | string | No | python3.13 | Lambda runtime |
| `coreProcessing.eventTransformer.memorySize` | number | No | 512 | Memory allocation in MB (128-10240) |
| `coreProcessing.eventTransformer.timeout` | number | No | 60 | Timeout in seconds (1-900) |
| `coreProcessing.eventTransformer.reservedConcurrentExecutions` | number | No | 10 | Reserved concurrent executions (0-1000) |
| `coreProcessing.eventTransformer.batchSize` | number | No | 10 | SQS batch size (1-10000) |
| `coreProcessing.eventTransformer.maximumBatchingWindowInSeconds` | number | No | 5 | Maximum batching window (0-300) |
| `coreProcessing.eventTransformer.lambdaLayerArn` | string | No | '' | AWS SDK for pandas layer ARN (see [Lambda Layer Configuration](#lambda-layer-configuration)) |
| `coreProcessing.eventTransformer.eventDataStoreEnabled` | boolean | No | false | Enable CloudTrail Event Data Store integration |
| `coreProcessing.eventTransformer.environment` | object | No | {} | Environment variables |
| `coreProcessing.eventTransformer.environment.LOGGING_LEVEL` | string | No | INFO | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `coreProcessing.eventTransformer.environment.CLOUDTRAIL_CHANNEL_ARN` | string | Conditional | - | CloudTrail channel ARN (required if `eventDataStoreEnabled` is true) |

**Example:**
```yaml
coreProcessing:
  eventTransformer:
    enabled: true
    functionName: event-transformer
    runtime: python3.13
    memorySize: 512
    timeout: 60
    reservedConcurrentExecutions: 10
    batchSize: 10
    maximumBatchingWindowInSeconds: 5
    lambdaLayerArn: 'arn:aws:lambda:ca-central-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15'
    eventDataStoreEnabled: false
    environment:
      LOGGING_LEVEL: INFO
```

#### Security Hub Processor

Imports ASFF-formatted findings into AWS Security Hub.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `coreProcessing.securityHubProcessor.enabled` | boolean | Yes | - | Enable Security Hub processor Lambda |
| `coreProcessing.securityHubProcessor.functionName` | string | No | securityhub-processor | Lambda function name |
| `coreProcessing.securityHubProcessor.runtime` | string | No | python3.13 | Lambda runtime |
| `coreProcessing.securityHubProcessor.memorySize` | number | No | 256 | Memory allocation in MB |
| `coreProcessing.securityHubProcessor.timeout` | number | No | 60 | Timeout in seconds |
| `coreProcessing.securityHubProcessor.reservedConcurrentExecutions` | number | No | 5 | Reserved concurrent executions |
| `coreProcessing.securityHubProcessor.batchSize` | number | No | 10 | SQS batch size |
| `coreProcessing.securityHubProcessor.maximumBatchingWindowInSeconds` | number | No | 5 | Maximum batching window |
| `coreProcessing.securityHubProcessor.environment` | object | No | {} | Environment variables |

**Example:**
```yaml
coreProcessing:
  securityHubProcessor:
    enabled: true
    functionName: securityhub-processor
    runtime: python3.13
    memorySize: 256
    timeout: 60
    reservedConcurrentExecutions: 5
    batchSize: 10
    maximumBatchingWindowInSeconds: 5
    environment:
      LOGGING_LEVEL: INFO
```

#### Flow Log Processor

Processes network flow logs and transforms them to OCSF network activity format.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `coreProcessing.flowLogProcessor.enabled` | boolean | No | false | Enable flow log processor Lambda |
| `coreProcessing.flowLogProcessor.functionName` | string | No | flowlog-processor | Lambda function name |
| `coreProcessing.flowLogProcessor.runtime` | string | No | python3.13 | Lambda runtime |
| `coreProcessing.flowLogProcessor.memorySize` | number | No | 1024 | Memory allocation in MB |
| `coreProcessing.flowLogProcessor.timeout` | number | No | 600 | Timeout in seconds |
| `coreProcessing.flowLogProcessor.reservedConcurrentExecutions` | number | No | 5 | Reserved concurrent executions |
| `coreProcessing.flowLogProcessor.batchSize` | number | No | 10 | SQS batch size |
| `coreProcessing.flowLogProcessor.maximumBatchingWindowInSeconds` | number | No | 5 | Maximum batching window |
| `coreProcessing.flowLogProcessor.environment` | object | No | {} | Environment variables |

### SQS Queue Configuration

Configures SQS queues for event processing.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `sqsQueue.enabled` | boolean | Yes | - | Enable SQS queue creation |
| `sqsQueue.queueName` | string | No | event-queue | Main queue name |
| `sqsQueue.visibilityTimeout` | number | No | 300 | Visibility timeout in seconds (0-43200) |
| `sqsQueue.messageRetentionPeriod` | number | No | 345600 | Message retention in seconds (60-1209600) |
| `sqsQueue.maxMessageSize` | number | No | 262144 | Maximum message size in bytes (1024-262144) |
| `sqsQueue.receiveMessageWaitTime` | number | No | 20 | Long polling wait time in seconds (0-20) |
| `sqsQueue.encryption.useSharedKey` | boolean | No | true | Use shared KMS key for encryption |
| `sqsQueue.deadLetterQueue.enabled` | boolean | No | true | Enable dead letter queue |
| `sqsQueue.deadLetterQueue.queueName` | string | No | event-dlq | DLQ name |
| `sqsQueue.deadLetterQueue.maxReceiveCount` | number | No | 3 | Max receive count before moving to DLQ |
| `sqsQueue.deadLetterQueue.messageRetentionPeriod` | number | No | 1209600 | DLQ message retention in seconds |

**Example:**
```yaml
sqsQueue:
  enabled: true
  queueName: event-queue
  visibilityTimeout: 300
  messageRetentionPeriod: 345600  # 4 days
  maxMessageSize: 262144  # 256 KB
  receiveMessageWaitTime: 20
  encryption:
    useSharedKey: true
  deadLetterQueue:
    enabled: true
    queueName: event-dlq
    maxReceiveCount: 3
    messageRetentionPeriod: 1209600  # 14 days
```

### CloudTrail Configuration

Configures optional CloudTrail Event Data Store integration.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `cloudTrailEventDataStore.enabled` | boolean | No | false | Enable CloudTrail Event Data Store |
| `cloudTrailEventDataStore.name` | string | No | - | Event data store name |
| `cloudTrailEventDataStore.retentionPeriod` | number | No | 90 | Retention period in days (7-2557) |
| `cloudTrailEventDataStore.eventCategories` | array | No | - | Event categories: `Data`, `Management` |
| `cloudTrailEventDataStore.terminationProtectionEnabled` | boolean | No | false | Enable termination protection |
| `cloudTrailEventDataStore.encryption.useSharedKey` | boolean | No | true | Use shared KMS key |

**Example:**
```yaml
cloudTrailEventDataStore:
  enabled: false
  name: unified-security-events
  retentionPeriod: 90
  eventCategories:
    - Data
    - Management
  terminationProtectionEnabled: false
  encryption:
    useSharedKey: true
```

### Security Hub Configuration

Configures AWS Security Hub integration.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `securityHub.enabled` | boolean | No | true | Enable Security Hub integration |
| `securityHub.encryption.useSharedKey` | boolean | No | true | Use shared KMS key for encryption |

**Example:**
```yaml
securityHub:
  enabled: true
  encryption:
    useSharedKey: true
```

### Monitoring Configuration

Configures CloudWatch monitoring and alarms.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `monitoring.enabled` | boolean | No | true | Enable monitoring |
| `monitoring.cloudWatchLogs.enabled` | boolean | No | true | Enable CloudWatch Logs |
| `monitoring.cloudWatchLogs.retentionDays` | number | No | 90 | Log retention in days |
| `monitoring.alarms.enabled` | boolean | No | true | Enable CloudWatch alarms |
| `monitoring.alarms.snsTopicName` | string | No | - | SNS topic name for alarm notifications |
| `monitoring.alarms.emailEndpoints` | array | No | [] | Email addresses for alarm notifications |
| `monitoring.alarms.dlqAlarm.enabled` | boolean | No | true | Enable DLQ alarm |
| `monitoring.alarms.dlqAlarm.threshold` | number | No | 1 | Alarm threshold |
| `monitoring.alarms.dlqAlarm.evaluationPeriods` | number | No | 1 | Evaluation periods |
| `monitoring.alarms.dlqAlarm.datapointsToAlarm` | number | No | 1 | Datapoints to alarm |
| `monitoring.alarms.dlqAlarm.period` | number | No | 300 | Period in seconds |
| `monitoring.alarms.lambdaErrorAlarm` | object | No | - | Lambda error alarm configuration |
| `monitoring.alarms.sqsAgeAlarm` | object | No | - | SQS message age alarm configuration |

**Example:**
```yaml
monitoring:
  enabled: true
  cloudWatchLogs:
    enabled: true
    retentionDays: 90
  alarms:
    enabled: true
    snsTopicName: security-lake-alerts
    emailEndpoints:
      - security-team@example.com
    dlqAlarm:
      enabled: true
      threshold: 1
      evaluationPeriods: 1
      datapointsToAlarm: 1
      period: 300
```

### Integration Modules Configuration

Configures integration modules for external security platforms.

#### Azure Integration Module

Integrates with Microsoft Defender for Cloud via Azure Event Hub.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `integrations.azure.enabled` | boolean | Yes | - | Enable Azure integration module |
| `integrations.azure.modulePath` | string | No | modules/azure | Path to module directory |
| `integrations.azure.config` | object | Yes | - | Module-specific configuration |

**Azure Module Configuration:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `config.eventHubProcessor.enabled` | boolean | Yes | - | Enable Event Hub processor |
| `config.eventHubProcessor.functionName` | string | No | azure-eventhub-processor | Lambda function name |
| `config.eventHubProcessor.memorySize` | number | No | 512 | Memory in MB |
| `config.eventHubProcessor.timeout` | number | No | 300 | Timeout in seconds |
| `config.eventHubProcessor.schedule` | string | No | rate(5 minutes) | EventBridge schedule expression |
| `config.eventHubProcessor.azureCredentialsSecretName` | string | Yes | - | Secrets Manager secret name |
| `config.checkpointStore.enabled` | boolean | No | true | Enable DynamoDB checkpoint store |
| `config.checkpointStore.tableName` | string | No | - | DynamoDB table name |
| `config.checkpointStore.billingMode` | string | No | PAY_PER_REQUEST | Billing mode |
| `config.checkpointStore.encryption.useSharedKey` | boolean | No | true | Use shared KMS key |

**Example:**
```yaml
integrations:
  azure:
    enabled: true
    modulePath: modules/azure
    config:
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
      
      flowLogProcessor:
        enabled: true
        functionName: azure-flowlog-processor
        memorySize: 1024
        timeout: 600
        reservedConcurrentExecutions: 5
        batchSize: 10
        maximumBatchingWindowInSeconds: 5
        azureFlowLogsSecretName: azure-flowlogs-credentials
        environment:
          LOGGING_LEVEL: INFO
      
      checkpointStore:
        enabled: true
        tableName: azure-eventhub-checkpoint-store
        billingMode: PAY_PER_REQUEST
        encryption:
          useSharedKey: true
```

#### Google SCC Integration Module

Integrates with Google Security Command Center via Pub/Sub.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `integrations.google-scc.enabled` | boolean | Yes | - | Enable Google SCC integration module |
| `integrations.google-scc.modulePath` | string | No | modules/google-scc | Path to module directory |
| `integrations.google-scc.config` | object | Yes | - | Module-specific configuration |

**Google SCC Module Configuration:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `config.pubsubPoller.enabled` | boolean | Yes | - | Enable Pub/Sub poller |
| `config.pubsubPoller.memorySize` | number | No | 512 | Memory in MB |
| `config.pubsubPoller.timeout` | number | No | 300 | Timeout in seconds |
| `config.pubsubPoller.schedule` | string | No | rate(5 minutes) | EventBridge schedule expression |
| `config.gcpCredentialsSecretName` | string | Yes | - | Secrets Manager secret name for GCP credentials |

**Example:**
```yaml
integrations:
  google-scc:
    enabled: false
    modulePath: modules/google-scc
    config:
      pubsubPoller:
        enabled: true
        memorySize: 512
        timeout: 300
        reservedConcurrentExecutions: 1
        schedule: rate(5 minutes)
        environment:
          LOGGING_LEVEL: INFO
      
      gcpCredentialsSecretName: gcp-pubsub-credentials
```

## Lambda Layer Configuration

### AWS SDK for Pandas (awswrangler) Layer

The Event Transformer Lambda requires the AWS SDK for pandas (awswrangler) layer to handle Parquet file generation for Security Lake/OCSF format. This layer provides the awswrangler library along with its dependencies (pandas and PyArrow) which are essential for converting events to Parquet format.

#### Why This Layer is Required

1. **Parquet File Generation**: Security Lake requires events in OCSF format stored as Parquet files. The awswrangler library provides efficient Parquet serialization.

2. **Package Size Limits**: The awswrangler library and its dependencies (pandas, PyArrow) are too large to bundle directly in the Lambda deployment package. Using a Lambda Layer solves this issue.

3. **ARM64 Architecture**: The Lambda uses ARM64 architecture (Graviton2) for cost efficiency. The layer must match this architecture.

4. **Python 3.13 Compatibility**: The layer must be compatible with Python 3.13 runtime.

#### Parameter Details

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lambdaLayerArn` | string | No | '' (empty) | ARN of the AWS SDK for pandas Lambda Layer |

**Format:**
```
arn:aws:lambda:REGION:336392948345:layer:AWSSDKPandas-Python313-Arm64:VERSION
```

**Components:**
- `REGION`: Your AWS region (e.g., `us-east-1`, `ca-central-1`)
- `336392948345`: AWS-managed account ID for public layers
- `AWSSDKPandas-Python313-Arm64`: Layer name for Python 3.13 ARM64
- `VERSION`: Layer version number (latest version recommended)

#### Finding the Correct Layer ARN

1. **Official Documentation**: Visit [AWS SDK for pandas Lambda Layers](https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html)

2. **Search by Region**: Find your AWS region in the list

3. **Select ARM64 Architecture**: Choose the `AWSSDKPandas-Python313-Arm64` layer

4. **Copy Latest Version**: Use the latest version number for your region

#### Examples by Region

| Region | Example ARN |
|--------|-------------|
| us-east-1 | `arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15` |
| us-west-2 | `arn:aws:lambda:us-west-2:336392948345:layer:AWSSDKPandas-Python313-Arm64:15` |
| ca-central-1 | `arn:aws:lambda:ca-central-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15` |
| eu-west-1 | `arn:aws:lambda:eu-west-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15` |
| ap-southeast-1 | `arn:aws:lambda:ap-southeast-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15` |

**Note**: Version numbers (`:15` in examples) may change. Always check the official documentation for the latest version in your region.

#### Impact of Not Configuring the Layer

If `lambdaLayerArn` is left empty or not configured:

1. **Lambda Deployment Failure**: The Lambda may exceed the 250 MB deployment package size limit
2. **Runtime Errors**: The Lambda will fail with `ModuleNotFoundError: No module named 'awswrangler'`
3. **Event Processing Failure**: Events cannot be converted to Parquet format and will not reach Security Lake
4. **DLQ Accumulation**: Failed events will accumulate in the dead letter queue

#### Configuration Example

**Minimal Configuration:**
```yaml
coreProcessing:
  eventTransformer:
    enabled: true
    lambdaLayerArn: 'arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15'
```

**Complete Configuration:**
```yaml
coreProcessing:
  eventTransformer:
    enabled: true
    functionName: event-transformer
    runtime: python3.13
    memorySize: 512
    timeout: 60
    reservedConcurrentExecutions: 10
    batchSize: 10
    maximumBatchingWindowInSeconds: 5
    # CRITICAL: Configure this layer for Parquet file generation
    lambdaLayerArn: 'arn:aws:lambda:ca-central-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15'
    eventDataStoreEnabled: false
    environment:
      LOGGING_LEVEL: INFO
```

## Configuration Examples

### Minimal Required Configuration

Minimum configuration for Security Lake integration without optional features:

```yaml
projectName: security-lake-integration
environment: dev
awsRegion: us-east-1

encryption:
  enabled: true
  keyType: CUSTOMER_MANAGED_CMK

securityLake:
  enabled: true
  s3Bucket: aws-security-data-lake-us-east-1-abcd1234
  externalId: YOUR-SECURE-RANDOM-STRING
  serviceRole: SecurityLakeGlueCrawler
  OCSFEventClass:
    - sourceName: unifiedSecurityEvents
      sourceVersion: '1.0'
      eventClasses:
        - SECURITY_FINDING

coreProcessing:
  eventTransformer:
    enabled: true
    lambdaLayerArn: 'arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15'

sqsQueue:
  enabled: true
```

### Full Configuration with All Features

Complete configuration including monitoring, Security Hub, and CloudTrail:

```yaml
projectName: security-lake-integration
environment: prod
awsRegion: us-east-1
accountId: ''

tagSource: ProServe Delivery Kit
tagProduct: Security-Lake-Integration-Framework
tagKitVersion: 2.0.0

tags:
  - key: Project
    value: Security-Lake-Integration
  - key: Environment
    value: prod
  - key: CostCenter
    value: Security

encryption:
  enabled: true
  keyType: CUSTOMER_MANAGED_CMK
  keyAlias: security-lake-integration
  keyDescription: Shared KMS key for Security Lake integration
  keyRotationEnabled: true
  keyPendingWindowInDays: 30

securityLake:
  enabled: true
  s3Bucket: aws-security-data-lake-us-east-1-abcd1234
  externalId: YOUR-SECURE-RANDOM-STRING
  serviceRole: SecurityLakeGlueCrawler
  OCSFEventClass:
    - sourceName: unifiedSecurityEvents
      sourceVersion: '1.0'
      eventClasses:
        - SECURITY_FINDING
        - VULNERABILITY_FINDING
        - COMPLIANCE_FINDING

coreProcessing:
  eventTransformer:
    enabled: true
    functionName: event-transformer
    runtime: python3.13
    memorySize: 512
    timeout: 60
    reservedConcurrentExecutions: 10
    batchSize: 10
    maximumBatchingWindowInSeconds: 5
    lambdaLayerArn: 'arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15'
    eventDataStoreEnabled: false
    environment:
      LOGGING_LEVEL: INFO
  
  securityHubProcessor:
    enabled: true
    functionName: securityhub-processor
    runtime: python3.13
    memorySize: 256
    timeout: 60
    reservedConcurrentExecutions: 5
    batchSize: 10
    maximumBatchingWindowInSeconds: 5
    environment:
      LOGGING_LEVEL: INFO

sqsQueue:
  enabled: true
  queueName: event-queue
  visibilityTimeout: 300
  messageRetentionPeriod: 345600
  maxMessageSize: 262144
  receiveMessageWaitTime: 20
  encryption:
    useSharedKey: true
  deadLetterQueue:
    enabled: true
    queueName: event-dlq
    maxReceiveCount: 3
    messageRetentionPeriod: 1209600

cloudTrailEventDataStore:
  enabled: false
  name: unified-security-events
  retentionPeriod: 90
  eventCategories:
    - Data
    - Management
  terminationProtectionEnabled: true
  encryption:
    useSharedKey: true

securityHub:
  enabled: true
  encryption:
    useSharedKey: true

monitoring:
  enabled: true
  cloudWatchLogs:
    enabled: true
    retentionDays: 90
  alarms:
    enabled: true
    snsTopicName: security-lake-alerts
    emailEndpoints:
      - security-team@example.com
    dlqAlarm:
      enabled: true
      threshold: 1
      evaluationPeriods: 1
      datapointsToAlarm: 1
      period: 300
    lambdaErrorAlarm:
      enabled: true
      errorRateThreshold: 0.05
      evaluationPeriods: 2
      datapointsToAlarm: 2
      period: 300
    sqsAgeAlarm:
      enabled: true
      ageThreshold: 600
      evaluationPeriods: 2
      datapointsToAlarm: 2
      period: 300
```

### Multi-Cloud Integration Example

Configuration with Azure and Google SCC integrations:

```yaml
projectName: multi-cloud-security-lake
environment: prod
awsRegion: us-east-1

encryption:
  enabled: true
  keyType: CUSTOMER_MANAGED_CMK

securityLake:
  enabled: true
  s3Bucket: aws-security-data-lake-us-east-1-abcd1234
  externalId: YOUR-SECURE-RANDOM-STRING
  serviceRole: SecurityLakeGlueCrawler
  OCSFEventClass:
    - sourceName: multiCloudSecurityEvents
      sourceVersion: '1.0'
      eventClasses:
        - SECURITY_FINDING
        - COMPLIANCE_FINDING
        - NETWORK_ACTIVITY

coreProcessing:
  eventTransformer:
    enabled: true
    lambdaLayerArn: 'arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python313-Arm64:15'
  
  securityHubProcessor:
    enabled: true
  
  flowLogProcessor:
    enabled: true
    memorySize: 1024
    timeout: 600

sqsQueue:
  enabled: true

integrations:
  azure:
    enabled: true
    config:
      eventHubProcessor:
        enabled: true
        functionName: azure-eventhub-processor
        schedule: rate(5 minutes)
        azureCredentialsSecretName: azure-eventhub-credentials
      
      flowLogProcessor:
        enabled: true
        azureFlowLogsSecretName: azure-flowlogs-credentials
      
      checkpointStore:
        enabled: true
        tableName: azure-eventhub-checkpoint-store
  
  google-scc:
    enabled: true
    config:
      pubsubPoller:
        enabled: true
        schedule: rate(5 minutes)
      
      gcpCredentialsSecretName: gcp-pubsub-credentials

monitoring:
  enabled: true
  alarms:
    enabled: true
    snsTopicName: multi-cloud-security-alerts
    emailEndpoints:
      - cloud-security-team@example.com
```

## Validation Rules

### Required Parameters

The following parameters are required for successful deployment:

1. **Project Configuration:**
   - `projectName`
   - `environment`
   - `awsRegion`

2. **Security Lake (if enabled):**
   - `securityLake.s3Bucket` (must be pre-existing)
   - `securityLake.externalId`
   - `securityLake.serviceRole`
   - `securityLake.OCSFEventClass`

3. **Core Processing:**
   - At least one processor must be enabled (`eventTransformer`, `securityHubProcessor`, or `flowLogProcessor`)
   - `lambdaLayerArn` is strongly recommended for `eventTransformer`

4. **Integration Modules:**
   - Module-specific required parameters (see module documentation)

### Parameter Format Requirements

1. **ARN Format:**
   - Lambda Layer ARNs must follow pattern: `arn:aws:lambda:REGION:ACCOUNT:layer:NAME:VERSION`

2. **Region Format:**
   - Must be valid AWS region (e.g., `us-east-1`, `ca-central-1`)

3. **Environment:**
   - Must be one of: `dev`, `staging`, `prod`

4. **Memory Size:**
   - Must be between 128 and 10240 MB
   - Must be a multiple of 64

5. **Timeout:**
   - Must be between 1 and 900 seconds

6. **Batch Size:**
   - SQS batch size must be between 1 and 10000

7. **Retention Periods:**
   - SQS message retention: 60 to 1209600 seconds (1 minute to 14 days)
   - CloudWatch logs retention: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 2192, 2557, 2922, 3288, or 3653 days

### Cross-Parameter Dependencies

1. **Security Hub Integration:**
   - If `securityHub.enabled` is `true`, then `coreProcessing.securityHubProcessor.enabled` should also be `true`

2. **CloudTrail Integration:**
   - If `coreProcessing.eventTransformer.eventDataStoreEnabled` is `true`, then:
     - `cloudTrailEventDataStore.enabled` must be `true`
     - `coreProcessing.eventTransformer.environment.CLOUDTRAIL_CHANNEL_ARN` must be set

3. **Flow Log Processing:**
   - If `coreProcessing.flowLogProcessor.enabled` is `true`, at least one integration module with flow log support must be enabled

4. **Encryption:**
   - If `encryption.keyType` is `CUSTOMER_MANAGED_CMK`, then:
     - `encryption.keyAlias` is required
     - `encryption.keyDescription` is recommended

5. **Queue Visibility:**
   - `sqsQueue.visibilityTimeout` should be at least 6 times the Lambda `timeout` value

### Common Validation Errors

1. **Missing Lambda Layer ARN:**
   ```
   ERROR: Event transformer will fail without lambdaLayerArn configured
   ```
   **Solution**: Add the appropriate AWS SDK for pandas layer ARN for your region

2. **Invalid S3 Bucket:**
   ```
   ERROR: Security Lake S3 bucket does not exist
   ```
   **Solution**: Ensure the S3 bucket exists before deployment

3. **Invalid Region:**
   ```
   ERROR: AWS region 'invalid-region' is not valid
   ```
   **Solution**: Use a valid AWS region code

4. **Memory Size Not Multiple of 64:**
   ```
   ERROR: Memory size must be a multiple of 64
   ```
   **Solution**: Adjust memory size to nearest multiple of 64 (e.g., 512, 1024, 1536)

5. **Missing Required Integration Parameters:**
   ```
   ERROR: Azure integration enabled but azureCredentialsSecretName not specified
   ```
   **Solution**: Provide all required parameters for enabled integration modules

### Validation Checklist

Before deployment, verify:

- [ ] All required parameters are provided
- [ ] AWS region is valid and Lambda layer ARN matches region
- [ ] Security Lake S3 bucket exists
- [ ] Lambda memory sizes are multiples of 64
- [ ] Timeout values are appropriate for workload
- [ ] Queue visibility timeout is sufficient for Lambda execution
- [ ] External IDs are secure random strings (not default values)
- [ ] Email addresses for alarms are valid
- [ ] Integration module credentials secrets will be created/configured post-deployment
- [ ] Environment-specific overrides are applied correctly

### Testing Configuration

After creating your configuration file, validate it before deployment:

```bash
# Syntax check (YAML validation)
yamllint config.yaml

# Dry run (CDK synth without deployment)
cd integrations/security-lake/cdk
npm run build
cdk synth -c configFile=config.yaml

# Review generated CloudFormation template
cdk synth -c configFile=config.yaml > template.yaml
```

## Additional Resources

- [Security Lake Integration Installation Guide](../../INSTALLATION_GUIDE.md)
- [Module Development Guide](MODULE_DEVELOPMENT_GUIDE.md)
- [Key Rotation Guide](KEY_ROTATION_GUIDE.md)
- [AWS SDK for pandas Lambda Layers Documentation](https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html)
- [OCSF Schema Documentation](https://schema.ocsf.io/)
- [AWS Security Lake Documentation](https://docs.aws.amazon.com/security-lake/)