© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Example Skeleton Integration Module

## Purpose

This is a template module that demonstrates how to create new Security Lake integration modules. Use this as a starting point for your own integrations.

## How to Use This Template

### 1. Copy the Module

```bash
cd integrations/security-lake/cdk/modules
cp -r example-skeleton your-integration-name
cd your-integration-name
```

### 2. Update Module Metadata

Edit `example-integration-module.ts`:
- Rename class to `YourIntegrationModule`
- Update `moduleId` to `'your-integration-name'`
- Update `moduleName` to `'Your Integration Name'`
- Update `moduleDescription` with your integration purpose

### 3. Implement Required Methods

**validateConfig():**
- Add your configuration field validations
- Check required fields exist
- Validate field formats and ranges
- Provide clear error messages

**createResources():**
- Create Lambda functions for your integration
- Create any needed DynamoDB tables, SQS queues, etc.
- Set up EventBridge schedules if needed
- Configure CloudWatch log groups

**getRequiredPermissions():**
- Define IAM permissions your module needs
- Use specific resource ARNs when possible
- Follow least privilege principle

### 4. Implement Lambda Code

Edit `src/lambda/event-processor/app.py`:
- Implement service client for your data source
- Add event fetching logic
- Transform events to standard format
- Send to core transformer queue

### 5. Add Dependencies

Edit `src/lambda/event-processor/requirements.txt`:
- Add Python packages for your data source API
- Include any transformation libraries
- Keep minimal to reduce package size

### 6. Create Tests

Add `src/lambda/event-processor/test_lambda.py`:
- Unit tests with mocked AWS services
- Test configuration validation
- Test event processing logic
- Aim for >80% code coverage

### 7. Register Module

```typescript
// In lib/core/module-registry.ts, add import:
import '../modules/your-integration-name';
```

### 8. Configure

Add to `config.yaml`:
```yaml
integrations:
  your-integration-name:
    enabled: true
    config:
      eventProcessor:
        enabled: true
        schedule: rate(5 minutes)
        memorySize: 512
        timeout: 300
      credentialsSecretName: your-service-credentials
```

### 9. Test

```bash
cd integrations/security-lake/cdk
npm run build
npm run synth -- -c configFile=config.yaml
```

### 10. Deploy

```bash
npm run deploy -- -c configFile=config.yaml
```

## Module Structure

```
your-integration-name/
├── example-integration-module.ts    # Rename and customize
├── index.ts                         # Module exports (create this)
├── README.md                        # Update with your integration details
├── config.schema.json               # JSON schema for your config (create this)
└── src/
    └── lambda/
        └── event-processor/
            ├── app.py              # Main Lambda handler
            ├── local_test.py       # Local testing script (create this)
            ├── test_lambda.py      # Unit tests (create this)
            ├── requirements.txt    # Python dependencies
            └── helpers/            # Helper classes (create as needed)
                ├── __init__.py
                └── client.py
```

## Configuration Example

```yaml
integrations:
  your-integration-name:
    enabled: true
    modulePath: modules/your-integration-name  # Optional, auto-detected
    config:
      eventProcessor:
        enabled: true
        schedule: rate(5 minutes)
        memorySize: 512
        timeout: 300
        reservedConcurrentExecutions: 1
        environment:
          LOGGING_LEVEL: INFO
          CUSTOM_SETTING: value
      credentialsSecretName: your-service-credentials
      additionalSettings:
        # Add your module-specific settings
```

## Required IAM Permissions Template

```typescript
getRequiredPermissions(): iam.PolicyStatement[] {
  return [
    // Secrets Manager access
    new iam.PolicyStatement({
      sid: 'ModuleSecretsAccess',
      actions: ['secretsmanager:GetSecretValue'],
      resources: [`arn:aws:secretsmanager:*:*:secret:${this.moduleId}-*`]
    }),
    
    // Add your service-specific permissions
    new iam.PolicyStatement({
      sid: 'ModuleServiceAccess',
      actions: ['service:Action'],
      resources: ['arn:aws:service:*:*:resource/*']
    })
  ];
}
```

## Checklist

Before submitting your module:

- [ ] Module class implements all IIntegrationModule methods
- [ ] Configuration validation covers all required fields
- [ ] IAM permissions follow least privilege
- [ ] Lambda code includes error handling
- [ ] AWS Powertools used for logging and tracing
- [ ] Unit tests with >80% coverage
- [ ] Local testing script provided
- [ ] README documents configuration and setup
- [ ] NO emotes in code or documentation
- [ ] Copyright header in all files
- [ ] Module registered in module-registry.ts
- [ ] Successfully synthesizes with CDK

## Common Patterns

### Polling Pattern
Use for APIs that require periodic polling:
- EventBridge scheduled rule triggers Lambda
- Lambda fetches events since last checkpoint
- Stores checkpoint for next invocation
- Sends events to transformer queue

### Event-Driven Pattern
Use for push-based integrations:
- EventBridge rule or SNS topic triggers Lambda
- Lambda receives events directly
- Validates and forwards to transformer queue

### Batch Processing Pattern
Use for high-volume sources:
- SQS queue receives events
- Lambda processes batches
- Supports partial batch failures
- DLQ for permanently failed events

## Support

See:
- [`../../docs/MODULE_DEVELOPMENT_GUIDE.md`](../../docs/MODULE_DEVELOPMENT_GUIDE.md) for detailed guide
- [`../../docs/MODULE_INTERFACE_SPEC.md`](../../docs/MODULE_INTERFACE_SPEC.md) for interface specification
- [`../azure/`](../azure/) for production example