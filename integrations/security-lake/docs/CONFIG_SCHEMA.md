© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Security Lake Integration Configuration Schema

## Version 2.0.0

## Overview

This document defines the configuration schema for the modular Security Lake integration framework. The schema supports both new modular configurations and backward compatibility with the legacy schema.

## New Configuration Structure

### Complete Example

```yaml
# ============================================================================
# PROJECT CONFIGURATION
# ============================================================================

projectName: security-lake-integration
environment: dev  # dev, staging, prod
awsRegion: ca-central-1
accountId: ''  # Optional, auto-detected if empty

# ============================================================================
# RESOURCE TAGGING
# ============================================================================

tagSource: ProServe Delivery Kit
tagProduct: Security-Lake-Integration
tagKitVersion: 2.0.0

tags:
  - key: Project
    value: Security-Lake-Integration
  - key: Environment
    value: dev
  - key: Owner
    value: Security-Team
  - key: ManagedBy
    value: CDK

# ============================================================================
# ENCRYPTION CONFIGURATION
# ============================================================================

encryption:
  enabled: true
  keyType: CUSTOMER_MANAGED_CMK  # AWS_OWNED_CMK, CUSTOMER_MANAGED_CMK
  keyAlias: security-lake-integration
  keyDescription: Master KMS key for Security Lake integration
  keyRotationEnabled: true
  keyPendingWindowInDays: 30

# ============================================================================
# SECURITY LAKE CONFIGURATION
# ============================================================================

securityLake:
  enabled: true
  s3Bucket: aws-security-data-lake-ca-central-1-uniqueid
  externalId: SecureRandomString
  serviceRole: SecurityLakeGlueCrawler
  OCSFEventClass:
    - sourceName: unifiedSecurityEvents
      sourceVersion: '1.0'
      eventClasses:
        - SECURITY_FINDING
        - VULNERABILITY_FINDING
        - COMPLIANCE_FINDING

# ============================================================================
# CORE PROCESSING CONFIGURATION
# ============================================================================

coreProcessing:
  # Event Transformer Lambda - always deployed
  eventTransformer:
    enabled: true
    functionName: event-transformer
    runtime: python3.13
    memorySize: 512
    timeout: 60
    reservedConcurrentExecutions: 10
    batchSize: 10
    maximumBatchingWindowInSeconds: 5
    environment:
      LOGGING_LEVEL: INFO
  
  # Security Hub Processor Lambda - optional
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
  
  # Security Lake Custom Resource - required if securityLake.enabled
  securityLakeCustomResource:
    enabled: true  # Auto-set based on securityLake.enabled
    timeout: 60
    memorySize: 256

# ============================================================================
# SQS QUEUE CONFIGURATION
# ============================================================================

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

# ============================================================================
# CLOUDTRAIL CONFIGURATION (Optional)
# ============================================================================

cloudTrailEventDataStore:
  enabled: true
  name: unified-security-events
  retentionPeriod: 90
  eventCategories:
    - Data
    - Management
  terminationProtectionEnabled: false
  encryption:
    useSharedKey: true

# ============================================================================
# SECURITY HUB INTEGRATION (Optional)
# ============================================================================

securityHub:
  enabled: true
  encryption:
    useSharedKey: true

# ============================================================================
# MONITORING CONFIGURATION
# ============================================================================

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

# ============================================================================
# INTEGRATION MODULES CONFIGURATION (NEW)
# ============================================================================

integrations:
  # Azure Defender Integration Module
  azure:
    enabled: true
    modulePath: modules/azure  # Relative to cdk root
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
      
      # Azure-specific secrets configuration
      secretsManager:
        eventHubSecret:
          secretName: azure-eventhub-credentials
          description: Azure Event Hub connection credentials
          secretTemplate:
            eventHubNamespace: PLACEHOLDER
            eventHubName: PLACEHOLDER
            consumerGroup: $Default
            connectionString: PLACEHOLDER
        
        flowLogsSecret:
          secretName: azure-flowlogs-credentials
          description: Azure Storage Account credentials for Flow Logs
          secretTemplate:
            tenantId: PLACEHOLDER_TENANT_ID
            clientId: PLACEHOLDER_CLIENT_ID
            clientSecret: PLACEHOLDER_CLIENT_SECRET
            subscriptionId: PLACEHOLDER_SUBSCRIPTION_ID
            storageAccountName: PLACEHOLDER_STORAGE_ACCOUNT_NAME
            storageAccountResourceId: PLACEHOLDER_STORAGE_ACCOUNT_RESOURCE_ID
      
      # Azure-specific resources
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
  
  # Future: GCP Security Command Center Integration (Example)
  gcp-scc:
    enabled: false
    modulePath: modules/gcp-scc
    config:
      findingsProcessor:
        enabled: true
        memorySize: 512
        timeout: 120
      
      organizations:
        - organizations/123456789

# ============================================================================
# ENVIRONMENT-SPECIFIC OVERRIDES
# ============================================================================

development:
  encryptionKeyType: AWS_OWNED_CMK

production:
  encryptionKeyType: CUSTOMER_MANAGED_CMK
  reservedConcurrentExecutions:
    transformationLambda: 100
```

## Backward Compatibility Mapping

The framework automatically maps legacy configuration to the new schema:

### Legacy Config Format
```yaml
# OLD FORMAT (Deprecated but supported)
azureIntegration:
  enabled: true
  azureTenantId: tenant-id
  secretsManager:
    secretName: azure-eventhub-credentials
    # ...

lambdaFunctions:
  eventHubProcessor:
    enabled: true
    # ...
  flowLogProcessor:
    enabled: true
    # ...
```

### Automatic Mapping to New Format
```yaml
# NEW FORMAT (Automatically converted)
integrations:
  azure:
    enabled: true  # from azureIntegration.enabled
    config:
      eventHubProcessor:
        enabled: true  # from lambdaFunctions.eventHubProcessor.enabled
        # ... other settings from lambdaFunctions.eventHubProcessor
      flowLogProcessor:
        enabled: true  # from lambdaFunctions.flowLogProcessor.enabled
        # ... other settings from lambdaFunctions.flowLogProcessor
      secretsManager:
        # ... from azureIntegration.secretsManager
```

## Configuration Schema Validation

### Required Fields
- `projectName`: String, lowercase with hyphens
- `environment`: Enum [dev, staging, prod]
- `awsRegion`: Valid AWS region identifier
- `securityLake.enabled`: Boolean
- `securityLake.s3Bucket`: String (if securityLake.enabled)
- `integrations`: Object (can be empty)

### Optional Fields
- `accountId`: AWS account ID (auto-detected if not provided)
- `encryption`: Encryption configuration (defaults applied)
- `monitoring`: Monitoring configuration (defaults applied)
- `cloudTrailEventDataStore`: CloudTrail configuration
- `securityHub`: Security Hub integration configuration

### Field Validation Rules

#### projectName
- Pattern: `^[a-z][a-z0-9-]*$`
- Max length: 64 characters
- No uppercase or special characters except hyphens

#### environment
- Valid values: `dev`, `staging`, `prod`
- Case-sensitive

#### awsRegion
- Must be valid AWS region
- Examples: `us-east-1`, `ca-central-1`, `eu-west-1`

#### encryption.keyType
- Valid values: `AWS_OWNED_CMK`, `CUSTOMER_MANAGED_CMK`
- Default: `CUSTOMER_MANAGED_CMK` for prod, `AWS_OWNED_CMK` for dev

#### integrations
- Each key must match pattern: `^[a-z][a-z0-9-]*$`
- Each integration must have: `enabled` (boolean), `config` (object)
- Optional: `modulePath` (string, defaults to `modules/{key}`)

## Module-Specific Configuration

### Azure Module Configuration Schema

```yaml
integrations:
  azure:
    enabled: boolean
    modulePath: string  # Default: modules/azure
    config:
      eventHubProcessor:
        enabled: boolean
        functionName: string
        memorySize: number  # 128-10240 MB
        timeout: number  # 1-900 seconds
        reservedConcurrentExecutions: number
        schedule: string  # EventBridge rate/cron expression
        azureCredentialsSecretName: string
        environment: {}
      
      flowLogProcessor:
        enabled: boolean
        functionName: string
        memorySize: number
        timeout: number
        reservedConcurrentExecutions: number
        batchSize: number  # 1-10
        maximumBatchingWindowInSeconds: number
        azureFlowLogsSecretName: string
        environment: {}
      
      secretsManager:
        eventHubSecret: {}
        flowLogsSecret: {}
      
      checkpointStore:
        enabled: boolean
        tableName: string
        billingMode: string  # PAY_PER_REQUEST, PROVISIONED
        encryption: {}
        ttl: {}
```

## Migration Guide

### Step 1: Identify Current Config Format

Check if your `config.yaml` has:
- `azureIntegration` section → Legacy format
- `integrations` section → New format

### Step 2: Convert to New Format

If using legacy format, run migration tool:
```bash
cd integrations/security-lake/cdk
npm run migrate-config -- --input config.yaml --output config-v2.yaml
```

Or manually convert using mapping rules above.

### Step 3: Validate New Config

```bash
cd integrations/security-lake/cdk
npm run build
npm run validate-config -- --config config-v2.yaml
```

### Step 4: Test Deployment

```bash
cdk synth -c configFile=config-v2.yaml
# Review synthesized template
cdk deploy -c configFile=config-v2.yaml
```

## Configuration Best Practices

### Security
1. Always enable encryption in production
2. Use CUSTOMER_MANAGED_CMK for production environments
3. Rotate KMS keys regularly
4. Never commit secrets to version control
5. Use strong, unique externalId for Security Lake

### Performance
1. Adjust Lambda memory based on workload
2. Set appropriate timeout values (function runtime + buffer)
3. Configure reserved concurrency to prevent throttling
4. Use batch processing for high-volume integrations

### Cost Optimization
1. Use AWS_OWNED_CMK for development
2. Set appropriate log retention periods
3. Disable unused integration modules
4. Use PAY_PER_REQUEST billing for variable workloads

### Monitoring
1. Always enable CloudWatch alarms in production
2. Configure SNS notifications for operations team
3. Set appropriate alarm thresholds
4. Monitor DLQ for failed events

## Configuration Validation

The config loader validates:
1. Schema structure and required fields
2. Data types and formats
3. Cross-field dependencies
4. Module-specific configuration
5. Security best practices compliance

Validation errors will prevent stack synthesis.

## Environment-Specific Configurations

### Development
```yaml
environment: dev
encryption:
  keyType: AWS_OWNED_CMK
monitoring:
  alarms:
    enabled: false
```

### Production
```yaml
environment: prod
encryption:
  keyType: CUSTOMER_MANAGED_CMK
  keyRotationEnabled: true
cloudTrailEventDataStore:
  retentionPeriod: 2555  # 7 years
  terminationProtectionEnabled: true
monitoring:
  alarms:
    enabled: true
```

## Troubleshooting

### Common Configuration Errors

**Error**: "Required configuration field missing: projectName"
- **Solution**: Add projectName field at root level

**Error**: "Security Lake s3Bucket is required when enabled"
- **Solution**: Provide pre-existing Security Lake S3 bucket name

**Error**: "Module azure configuration validation failed"
- **Solution**: Check module-specific config requirements in module documentation

**Error**: "Invalid module ID format"
- **Solution**: Module IDs must be lowercase alphanumeric with hyphens only

## References

- [Module Interface Specification](./MODULE_INTERFACE_SPEC.md)
- [Module Development Guide](./MODULE_DEVELOPMENT_GUIDE.md)
- [AWS Security Lake Documentation](https://docs.aws.amazon.com/security-lake/)
- [CDK Best Practices](https://docs.aws.amazon.com/cdk/latest/guide/best-practices.html)