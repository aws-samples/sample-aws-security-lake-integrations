© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Integration Module Interface Specification

## Version 1.0.0

## Overview

This document defines the formal interface contract that all Security Lake integration modules MUST implement. The interface ensures consistency, maintainability, and security across all integration modules while enabling rapid development of new integrations.

## Core Interface Definition

### TypeScript Interface

```typescript
import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/**
 * Validation result returned by module config validation
 */
export interface ValidationResult {
  valid: boolean;
  errors?: string[];
  warnings?: string[];
}

/**
 * Health check configuration for module monitoring
 */
export interface HealthCheckConfig {
  enabled: boolean;
  checkInterval: cdk.Duration;
  failureThreshold: number;
  alarmActions?: string[];
}

/**
 * Core resources provided by SecurityLakeStack to modules
 */
export interface CoreResources {
  readonly eventTransformerQueue: sqs.IQueue;
  readonly eventTransformerDeadLetterQueue: sqs.IQueue;
  readonly sharedKmsKey?: kms.IKey;
  readonly securityLakeBucket: string;
  readonly securityLakeCustomResource?: cdk.CustomResource;
}

/**
 * Base interface that all integration modules MUST implement
 */
export interface IIntegrationModule {
  /**
   * Unique identifier for this module
   * Must be lowercase alphanumeric with hyphens only
   * Example: "azure-defender", "future-integration", "gcp-scc"
   */
  readonly moduleId: string;

  /**
   * Human-readable name for this module
   * Example: "Azure Defender Integration"
   */
  readonly moduleName: string;

  /**
   * Semantic version of this module
   * Must follow semver: MAJOR.MINOR.PATCH
   * Example: "1.0.0"
   */
  readonly moduleVersion: string;

  /**
   * Brief description of module functionality
   * Example: "Integrates Azure Defender for Cloud security events with AWS Security Lake"
   */
  readonly moduleDescription: string;

  /**
   * Validate module-specific configuration
   * Called during stack synthesis before resource creation
   * 
   * @param config - Module-specific configuration object
   * @returns ValidationResult with any errors or warnings
   */
  validateConfig(config: any): ValidationResult;

  /**
   * Create module-specific AWS resources
   * Called during stack synthesis after config validation
   * 
   * @param scope - CDK construct scope (typically the SecurityLakeStack)
   * @param coreResources - Shared resources from core stack
   * @param config - Module-specific configuration object
   */
  createResources(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): void;

  /**
   * Get IAM policy statements required by this module
   * Called during role creation to grant least-privilege permissions
   * 
   * @returns Array of IAM PolicyStatement objects
   */
  getRequiredPermissions(): iam.PolicyStatement[];

  /**
   * Get health check configuration for module monitoring
   * Optional: Modules can implement health checks for their components
   * 
   * @returns HealthCheckConfig or undefined if not implemented
   */
  getHealthCheckConfig?(): HealthCheckConfig;

  /**
   * Get module-specific CloudFormation outputs
   * Optional: Modules can export useful values for operators
   * 
   * @returns Record of output names to values
   */
  getModuleOutputs?(): Record<string, any>;

  /**
   * Cleanup resources during module deactivation
   * Optional: Called when module is disabled in config
   * 
   * @param scope - CDK construct scope
   */
  cleanup?(scope: Construct): void;
}
```

## Implementation Requirements

### Required Methods

#### 1. validateConfig()

**Purpose**: Validate module-specific configuration before resource creation

**Requirements**:
- MUST check all required configuration fields are present
- MUST validate field types and formats
- MUST return meaningful error messages
- SHOULD provide warnings for deprecated configurations
- MUST NOT make AWS API calls
- MUST complete in < 1 second

**Example Implementation**:
```typescript
validateConfig(config: any): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Check required fields
  if (!config.eventHubNamespace) {
    errors.push('eventHubNamespace is required');
  }

  // Validate formats
  if (config.schedule && !config.schedule.match(/^rate\(\d+ (minute|minutes|hour|hours)\)$/)) {
    errors.push('schedule must be in format: rate(X minutes)');
  }

  // Check deprecated fields
  if (config.oldParameter) {
    warnings.push('oldParameter is deprecated, use newParameter instead');
  }

  return {
    valid: errors.length === 0,
    errors: errors.length > 0 ? errors : undefined,
    warnings: warnings.length > 0 ? warnings : undefined
  };
}
```

#### 2. createResources()

**Purpose**: Create all module-specific AWS resources

**Requirements**:
- MUST create all Lambda functions, SQS queues, DynamoDB tables, etc.
- MUST use constructs pattern for reusable components
- MUST follow CDK best practices for resource naming
- MUST implement proper error handling
- MUST NOT create resources if config validation failed
- MUST respect environment-specific settings (dev/prod)
- SHOULD use core resources when available (shared KMS key, etc.)

**Example Implementation**:
```typescript
createResources(
  scope: Construct,
  coreResources: CoreResources,
  config: any
): void {
  // Create module-specific Lambda function
  const processor = new lambda.Function(scope, `${this.moduleId}-processor`, {
    runtime: lambda.Runtime.PYTHON_3_13,
    handler: 'app.lambda_handler',
    code: lambda.Code.fromAsset(`modules/${this.moduleId}/src/lambda/processor`),
    environment: {
      SQS_QUEUE_URL: coreResources.eventTransformerQueue.queueUrl,
      MODULE_ID: this.moduleId
    }
  });

  // Grant permissions to write to core queue
  coreResources.eventTransformerQueue.grantSendMessages(processor);
}
```

#### 3. getRequiredPermissions()

**Purpose**: Define least-privilege IAM permissions for module

**Requirements**:
- MUST return array of IAM PolicyStatement objects
- MUST use least-privilege principle
- MUST include specific resource ARNs when possible
- MUST include descriptive Sid for each statement
- SHOULD group related permissions logically
- MUST NOT use wildcards unless absolutely necessary

**Example Implementation**:
```typescript
getRequiredPermissions(): iam.PolicyStatement[] {
  return [
    new iam.PolicyStatement({
      sid: 'AzureEventHubProcessorSecrets',
      effect: iam.Effect.ALLOW,
      actions: [
        'secretsmanager:GetSecretValue',
        'secretsmanager:DescribeSecret'
      ],
      resources: [
        `arn:aws:secretsmanager:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:secret:azure-eventhub-*`
      ]
    }),
    new iam.PolicyStatement({
      sid: 'AzureCheckpointStore',
      effect: iam.Effect.ALLOW,
      actions: [
        'dynamodb:GetItem',
        'dynamodb:PutItem',
        'dynamodb:UpdateItem',
        'dynamodb:Query'
      ],
      resources: [
        `arn:aws:dynamodb:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:table/azure-checkpoint-store`
      ]
    })
  ];
}
```

### Optional Methods

#### 4. getHealthCheckConfig()

**Purpose**: Define health monitoring for module components

**Requirements**:
- SHOULD implement if module has long-running components
- MUST return HealthCheckConfig with alarm settings
- SHOULD use CloudWatch metrics and alarms

**Example Implementation**:
```typescript
getHealthCheckConfig(): HealthCheckConfig {
  return {
    enabled: true,
    checkInterval: cdk.Duration.minutes(5),
    failureThreshold: 3,
    alarmActions: ['arn:aws:sns:us-east-1:123456789:ops-team']
  };
}
```

#### 5. getModuleOutputs()

**Purpose**: Export useful values from module deployment

**Requirements**:
- SHOULD include ARNs, URLs, names of key resources
- MUST use descriptive output names
- SHOULD include configuration values for operators

**Example Implementation**:
```typescript
getModuleOutputs(): Record<string, any> {
  return {
    ProcessorFunctionArn: this.processorFunction.functionArn,
    CheckpointTableName: this.checkpointTable.tableName,
    EventHubNamespace: this.config.eventHubNamespace
  };
}
```

## Module Lifecycle

### 1. Initialization Phase
```
ConfigLoad -> ModuleValidation -> ResourceCreation -> PermissionGrant
```

### 2. Runtime Phase
```
EventIngestion -> Processing -> Transformation -> SecurityLakeDelivery
```

### 3. Deactivation Phase
```
ConfigDisable -> GracefulShutdown -> ResourceCleanup (optional)
```

## Configuration Schema

### Module Configuration Structure

```yaml
integrations:
  <module-id>:
    enabled: boolean          # Required: Enable/disable module
    modulePath: string        # Required: Path to module code
    config:                   # Required: Module-specific config
      # Module-specific parameters here
```

### Example: Azure Module Configuration

```yaml
integrations:
  azure:
    enabled: true
    modulePath: modules/azure
    config:
      eventHubProcessor:
        enabled: true
        schedule: rate(5 minutes)
        memorySize: 512
        timeout: 300
        azureCredentialsSecretName: azure-eventhub-creds
      flowLogProcessor:
        enabled: true
        memorySize: 1024
        timeout: 600
        azureFlowLogsSecretName: azure-flowlogs-creds
```

## Security Requirements

### 1. Least Privilege Access
- Each module gets ONLY the permissions it requires
- No cross-module resource access without explicit grants
- Separate IAM roles per module component

### 2. Data Encryption
- All data at rest MUST be encrypted with KMS
- All data in transit MUST use TLS 1.2+
- Module can use shared KMS key or request dedicated key

### 3. Secret Management
- Credentials MUST be stored in AWS Secrets Manager
- Never hardcode secrets in code or config
- Use IAM roles for AWS service authentication

### 4. Audit Logging
- All module actions MUST be logged to CloudWatch
- Include module ID in all log entries
- Enable CloudTrail for all API calls

## Testing Requirements

### 1. Unit Tests
- MUST test config validation with valid/invalid inputs
- MUST test permission generation
- MUST mock all AWS service calls

### 2. Integration Tests
- SHOULD test resource creation in isolated stack
- SHOULD verify IAM permissions are sufficient
- SHOULD test health checks if implemented

### 3. Security Tests
- MUST verify least-privilege permissions
- MUST check for exposed secrets
- MUST validate encryption configuration

## Module Development Checklist

Before submitting a new integration module:

- [ ] Implements IIntegrationModule interface completely
- [ ] Includes comprehensive config validation
- [ ] Uses least-privilege IAM permissions
- [ ] Includes unit tests with >80% coverage
- [ ] Includes integration tests
- [ ] Includes README with setup instructions
- [ ] Follows project code style (NO EMOTES)
- [ ] Includes copyright header in all files
- [ ] Documents all configuration parameters
- [ ] Provides example configuration
- [ ] Implements health checks (optional but recommended)
- [ ] Includes CloudWatch dashboards (optional)
- [ ] Updates module registry documentation

## Module Registry

All approved modules must be registered in `lib/core/module-registry.ts`:

```typescript
export const REGISTERED_MODULES: Record<string, () => IIntegrationModule> = {
  'azure': () => new AzureIntegrationModule(),
  'future-integration': () => new FutureIntegrationModule()
};
```

## Versioning

Modules follow semantic versioning:
- **MAJOR**: Breaking changes to interface or config schema
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, no interface changes

## Support and Maintenance

### Module Ownership
- Each module has designated owner/team
- Owner responsible for updates and bug fixes
- Owner maintains module documentation

### Deprecation Policy
- Modules may be deprecated with 6-month notice
- Deprecated modules remain functional during notice period
- Users notified via CloudWatch Events and documentation

## References

- [AWS CDK Best Practices](https://docs.aws.amazon.com/cdk/latest/guide/best-practices.html)
- [AWS Security Best Practices](https://docs.aws.amazon.com/security/latest/userguide/security-best-practices.html)
- [Security Lake Documentation](https://docs.aws.amazon.com/security-lake/latest/userguide/)
- [Module Development Guide](./MODULE_DEVELOPMENT_GUIDE.md)

## Changelog

### Version 1.0.0 (2025-01-22)
- Initial interface specification
- Core methods defined
- Security requirements established