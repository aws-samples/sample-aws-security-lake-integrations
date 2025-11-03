© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Integration Module Development Guide

## Version 1.0.0

## Overview

This guide provides step-by-step instructions for developing new Security Lake integration modules. Following this guide ensures your module integrates seamlessly with the framework and follows AWS best practices.

## Prerequisites

- Familiarity with AWS CDK and TypeScript
- Understanding of Python Lambda development
- Knowledge of the data source you're integrating
- Review of [`MODULE_INTERFACE_SPEC.md`](./MODULE_INTERFACE_SPEC.md)

## Development Process

### Step 1: Plan Your Integration

**Define Requirements:**
- What security data source are you integrating?
- What event types will you collect?
- How will you authenticate and connect to the source?
- What AWS resources will you need (Lambda, SQS, DynamoDB, Secrets)?
- What IAM permissions are required?

**Design Considerations:**
- Event polling frequency
- Data transformation requirements
- Error handling and retry logic
- Monitoring and alerting needs

### Step 2: Create Module Directory Structure

```bash
cd integrations/security-lake/cdk/modules
mkdir -p my-integration/src/lambda/event-processor/{helpers,tests}
```

**Required Structure:**
```
modules/my-integration/
├── index.ts                          # Module exports
├── my-integration-module.ts          # Module implementation
├── README.md                         # Module documentation
├── src/
│   └── lambda/
│       └── event-processor/
│           ├── app.py                # Lambda handler
│           ├── local_test.py         # Local testing
│           ├── test_lambda.py        # Unit tests
│           ├── requirements.txt      # Python dependencies
│           └── helpers/              # Helper classes
│               ├── __init__.py
│               └── client.py
└── config.schema.json                # JSON schema for module config
```

### Step 3: Implement Module Interface

**Create Module Class:**

```typescript
/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * My Integration Module
 */

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Construct } from 'constructs';
import { 
  BaseIntegrationModule, 
  ValidationResult, 
  CoreResources 
} from '../core/integration-module-interface';

export class MyIntegrationModule extends BaseIntegrationModule {
  // Required properties
  readonly moduleId = 'my-integration';
  readonly moduleName = 'My Integration';
  readonly moduleVersion = '1.0.0';
  readonly moduleDescription = 'Integrates My Service security events with AWS Security Lake';

  // Module resources (stored for reference)
  private processorFunction?: lambda.Function;

  /**
   * Validate module configuration
   */
  validateConfig(config: any): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Check required fields
    if (!config.eventProcessor) {
      errors.push('eventProcessor configuration is required');
    }

    if (config.eventProcessor?.enabled) {
      // Validate processor config
      if (!config.credentialsSecretName) {
        errors.push('credentialsSecretName is required when eventProcessor is enabled');
      }

      if (!config.eventProcessor.schedule) {
        errors.push('eventProcessor.schedule is required');
      } else {
        // Validate schedule format
        const schedulePattern = /^(rate\(.+\)|cron\(.+\))$/;
        if (!schedulePattern.test(config.eventProcessor.schedule)) {
          errors.push('eventProcessor.schedule must be valid EventBridge expression');
        }
      }
    }

    // Check for deprecated fields
    if (config.oldField) {
      warnings.push('oldField is deprecated, use newField instead');
    }

    return {
      valid: errors.length === 0,
      errors: errors.length > 0 ? errors : undefined,
      warnings: warnings.length > 0 ? warnings : undefined
    };
  }

  /**
   * Create module resources
   */
  createResources(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): void {
    // Create module-specific resources
    this.processorFunction = this.createEventProcessor(scope, coreResources, config);

    // Set up scheduled polling if configured
    if (config.eventProcessor.schedule) {
      this.createPollingSchedule(scope, this.processorFunction, config);
    }
  }

  /**
   * Get required IAM permissions
   */
  getRequiredPermissions(): iam.PolicyStatement[] {
    return [
      new iam.PolicyStatement({
        sid: `${this.moduleId}SecretsAccess`,
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret'
        ],
        resources: [
          `arn:aws:secretsmanager:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:secret:${this.moduleId}-*`
        ]
      })
    ];
  }

  /**
   * Create event processor Lambda
   */
  private createEventProcessor(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): lambda.Function {
    const processorConfig = config.eventProcessor;

    // Create IAM role
    const role = new iam.Role(scope, this.createResourceId(scope, 'ProcessorRole'), {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ]
    });

    // Grant module permissions
    this.getRequiredPermissions().forEach(statement => {
      role.addToPolicy(statement);
    });

    // Grant access to core resources
    coreResources.eventTransformerQueue.grantSendMessages(role);
    if (coreResources.sharedKmsKey) {
      coreResources.sharedKmsKey.grantEncryptDecrypt(role);
    }

    // Create Lambda function
    const fn = new lambda.Function(scope, this.createResourceId(scope, 'Processor'), {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'app.lambda_handler',
      architecture: lambda.Architecture.ARM_64,
      code: lambda.Code.fromAsset(`modules/${this.moduleId}/src/lambda/event-processor`, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            'bash', '-c', [
              'pip install -r requirements.txt -t /asset-output',
              'cp -au . /asset-output',
              'find /asset-output -name "*.pyc" -delete',
              'find /asset-output -type d -name "__pycache__" | xargs rm -rf',
            ].join(' && ')
          ],
          user: 'root',
        }
      }),
      role: role,
      timeout: cdk.Duration.seconds(processorConfig.timeout || 300),
      memorySize: processorConfig.memorySize || 512,
      reservedConcurrentExecutions: processorConfig.reservedConcurrentExecutions,
      environment: {
        MODULE_ID: this.moduleId,
        SQS_QUEUE_URL: coreResources.eventTransformerQueue.queueUrl,
        CREDENTIALS_SECRET_NAME: config.credentialsSecretName,
        LOGGING_LEVEL: processorConfig.environment?.LOGGING_LEVEL || 'INFO',
        ...processorConfig.environment
      },
      deadLetterQueueEnabled: true,
      retryAttempts: 2
    });

    return fn;
  }

  /**
   * Create polling schedule
   */
  private createPollingSchedule(
    scope: Construct,
    fn: lambda.Function,
    config: any
  ): void {
    const schedule = new events.Rule(scope, this.createResourceId(scope, 'PollSchedule'), {
      schedule: events.Schedule.expression(config.eventProcessor.schedule),
      enabled: true,
      description: `Polling schedule for ${this.moduleName}`
    });
    
    schedule.addTarget(new targets.LambdaFunction(fn));
  }
}
```

### Step 4: Register Module

**Create Module Index:**

```typescript
// modules/my-integration/index.ts
import { registerModule } from '../core/module-registry';
import { MyIntegrationModule } from './my-integration-module';

// Register module on import
registerModule('my-integration', MyIntegrationModule);

// Export module for direct use if needed
export { MyIntegrationModule };
```

**Import in Main App:**

```typescript
// bin/security-lake-integration.ts
import '../modules/my-integration';  // Auto-registers module
```

### Step 5: Implement Lambda Function

**Lambda Handler (`app.py`):**

```python
"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.

My Integration Event Processor Lambda
"""

import json
import logging
import os
from typing import Dict, Any, List
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from helpers.client import MyServiceClient
from helpers.sqs_client import SQSClient

# Initialize Powertools
logger = Logger(service="my-integration-processor")
tracer = Tracer(service="my-integration-processor")

# Global clients for reuse (prevents cold starts)
my_service_client = None
sqs_client = None

def get_my_service_client() -> MyServiceClient:
    """Get or create My Service client"""
    global my_service_client
    if my_service_client is None:
        credentials_secret = os.environ['CREDENTIALS_SECRET_NAME']
        my_service_client = MyServiceClient(credentials_secret)
    return my_service_client

def get_sqs_client() -> SQSClient:
    """Get or create SQS client"""
    global sqs_client
    if sqs_client is None:
        queue_url = os.environ['SQS_QUEUE_URL']
        sqs_client = SQSClient(queue_url)
    return sqs_client

@tracer.capture_lambda_handler
@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler for My Service event processing
    
    Args:
        event: Lambda event (scheduled or direct invocation)
        context: Lambda context
        
    Returns:
        Response dictionary with processing results
    """
    try:
        logger.info("Processing My Service events", extra={
            "module_id": os.environ.get('MODULE_ID'),
            "event_type": event.get('detail-type', 'scheduled')
        })
        
        # Get clients
        service_client = get_my_service_client()
        sqs = get_sqs_client()
        
        # Fetch events from My Service
        events = service_client.fetch_events()
        logger.info(f"Fetched {len(events)} events from My Service")
        
        # Send to SQS for transformation
        if events:
            sqs.send_batch(events)
            logger.info(f"Sent {len(events)} events to transformer queue")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'events_processed': len(events),
                'status': 'success'
            })
        }
        
    except Exception as e:
        logger.exception("Error processing My Service events")
        raise
```

**Helper Client (`helpers/client.py`):**

```python
"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.

My Service Client Helper
"""

import json
import boto3
from typing import Dict, Any, List
from aws_lambda_powertools import Logger

logger = Logger(child=True)

class MyServiceClient:
    """Client for interacting with My Service API"""
    
    def __init__(self, credentials_secret_name: str):
        """
        Initialize client
        
        Args:
            credentials_secret_name: Name of AWS Secrets Manager secret
        """
        self.credentials = self._load_credentials(credentials_secret_name)
        # Initialize your service client here
        
    def _load_credentials(self, secret_name: str) -> Dict[str, Any]:
        """Load credentials from Secrets Manager"""
        secrets_client = boto3.client('secretsmanager')
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    
    def fetch_events(self) -> List[Dict[str, Any]]:
        """
        Fetch events from My Service
        
        Returns:
            List of event dictionaries
        """
        logger.info("Fetching events from My Service")
        # Implement your event fetching logic here
        return []
```

**Requirements (`requirements.txt`):**

```
boto3>=1.28.0
aws-lambda-powertools>=2.20.0
requests>=2.31.0
# Add your service-specific dependencies
```

**Unit Tests (`test_lambda.py`):**

```python
"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.

Unit tests for My Integration Lambda
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from app import lambda_handler

@pytest.fixture
def lambda_context():
    """Mock Lambda context"""
    context = Mock()
    context.function_name = 'test-function'
    context.memory_limit_in_mb = 512
    context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789:function:test'
    context.aws_request_id = 'test-request-id'
    return context

@pytest.fixture
def scheduled_event():
    """Mock scheduled event"""
    return {
        'version': '0',
        'id': 'test-id',
        'detail-type': 'Scheduled Event',
        'source': 'aws.events',
        'time': '2025-01-22T12:00:00Z'
    }

@patch('app.get_my_service_client')
@patch('app.get_sqs_client')
def test_lambda_handler_success(mock_sqs, mock_service, scheduled_event, lambda_context):
    """Test successful event processing"""
    # Setup mocks
    mock_service_instance = Mock()
    mock_service_instance.fetch_events.return_value = [{'test': 'event'}]
    mock_service.return_value = mock_service_instance
    
    mock_sqs_instance = Mock()
    mock_sqs.return_value = mock_sqs_instance
    
    # Execute
    response = lambda_handler(scheduled_event, lambda_context)
    
    # Verify
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['events_processed'] == 1
    assert body['status'] == 'success'
    
    mock_service_instance.fetch_events.assert_called_once()
    mock_sqs_instance.send_batch.assert_called_once()
```

### Step 4: Configure Module

**Create Config Schema (`config.schema.json`):**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MyIntegration Module Configuration",
  "type": "object",
  "required": ["eventProcessor", "credentialsSecretName"],
  "properties": {
    "eventProcessor": {
      "type": "object",
      "required": ["enabled", "schedule"],
      "properties": {
        "enabled": {
          "type": "boolean",
          "description": "Enable/disable event processor"
        },
        "schedule": {
          "type": "string",
          "pattern": "^(rate\\(.+\\)|cron\\(.+\\))$",
          "description": "EventBridge schedule expression"
        },
        "memorySize": {
          "type": "number",
          "minimum": 128,
          "maximum": 10240,
          "description": "Lambda memory in MB"
        },
        "timeout": {
          "type": "number",
          "minimum": 1,
          "maximum": 900,
          "description": "Lambda timeout in seconds"
        }
      }
    },
    "credentialsSecretName": {
      "type": "string",
      "description": "AWS Secrets Manager secret name for My Service credentials"
    }
  }
}
```

**Document Configuration in README:**

```markdown
# My Integration Module

## Configuration

```yaml
integrations:
  my-integration:
    enabled: true
    config:
      eventProcessor:
        enabled: true
        schedule: rate(5 minutes)
        memorySize: 512
        timeout: 300
      credentialsSecretName: my-service-credentials
```

## Setup

1. Create secret in AWS Secrets Manager:
```bash
aws secretsmanager create-secret \
  --name my-service-credentials \
  --secret-string '{"apiKey":"your-key","endpoint":"https://api.example.com"}'
```
```

### Step 5: Testing

**Local Testing (`local_test.py`):**

```python
"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.

Local testing script for My Integration Lambda
"""

import json
from app import lambda_handler

def test_local():
    """Run Lambda locally with mock event"""
    event = {
        'version': '0',
        'id': 'test-local',
        'detail-type': 'Scheduled Event',
        'source': 'aws.events',
        'time': '2025-01-22T12:00:00Z'
    }
    
    class Context:
        function_name = 'test-local'
        memory_limit_in_mb = 512
        invoked_function_arn = 'arn:aws:lambda:test'
        aws_request_id = 'test-request'
    
    result = lambda_handler(event, Context())
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    test_local()
```

**Run Tests:**

```bash
# Unit tests with pytest
cd modules/my-integration/src/lambda/event-processor
pytest test_lambda.py -v

# Local execution
python local_test.py

# Integration tests (requires AWS credentials)
pytest integration_test.py -v
```

### Step 6: Documentation

**Create Module README:**

Must include:
- Module overview and purpose
- Data source description
- Configuration parameters
- Setup instructions
- IAM permissions required
- Troubleshooting guide
- Monitoring recommendations

**Example:**

```markdown
# My Integration Module

## Overview
Integrates My Service security events into AWS Security Lake.

## Prerequisites
- My Service API access
- AWS Secrets Manager configured
- Security Lake enabled

## Architecture
- Event Processor Lambda: Polls My Service API every 5 minutes
- Sends events to core transformer queue
- Checkpoint tracking in DynamoDB (if needed)

## Configuration
See config.schema.json for complete schema.

## IAM Permissions
- secretsmanager:GetSecretValue (My Service credentials)
- sqs:SendMessage (to transformer queue)

## Monitoring
- CloudWatch Logs: /aws/lambda/my-integration-processor
- Metrics: EventsProcessed, APIErrors, TransformationSuccess

## Troubleshooting
### Common Issues
...
```

### Step 7: Security Review

**Checklist:**
- [ ] Credentials stored in Secrets Manager (not hardcoded)
- [ ] Least privilege IAM permissions (no wildcards unless required)
- [ ] Data encrypted at rest (KMS)
- [ ] Data encrypted in transit (TLS 1.2+)
- [ ] Input validation on all external data
- [ ] Error handling doesn't leak sensitive data
- [ ] Logging doesn't include secrets
- [ ] AWS Powertools used for tracing
- [ ] pytest tests with >80% coverage
- [ ] No emotes in code or documentation

### Step 8: Module Registration

**Update Module Registry:**

```typescript
// lib/core/module-registry.ts (add to imports)
import '../modules/my-integration';
```

**Verify Registration:**

```bash
cd integrations/security-lake/cdk
npm run build
npm run synth -- -c configFile=config.test.yaml
```

## Best Practices

### Lambda Development
1. Use global client instances (prevents cold starts)
2. Implement exponential backoff for retries
3. Use batch processing for high volume
4. Set appropriate timeouts and memory
5. Include structured logging with context

### Error Handling
1. Catch specific exceptions
2. Log errors with full context
3. Use DLQ for permanently failed events
4. Don't retry non-retriable errors
5. Return proper status codes

### Performance
1. Minimize Lambda cold starts
2. Use connection pooling
3. Batch API calls when possible
4. Set appropriate concurrent executions
5. Monitor and optimize based on metrics

### Security
1. Never log credentials
2. Validate all inputs
3. Use IAM roles, not access keys
4. Encrypt sensitive data
5. Follow least privilege principle

## Testing Strategy

### Unit Tests (pytest)
- Mock all AWS services
- Test happy path and error cases
- Test configuration validation
- Coverage target: >80%

### Integration Tests
- Use LocalStack or AWS test account
- Test end-to-end flow
- Verify IAM permissions
- Test with real AWS services

### Security Tests
- Scan for hardcoded secrets
- Verify encryption configuration
- Check IAM policy least privilege
- Test error handling doesn't leak data

## Common Pitfalls

### 1. Forgetting to Register Module
**Symptom**: Module not found error during synthesis
**Solution**: Import module in bin/security-lake-integration.ts

### 2. Invalid Configuration
**Symptom**: Validation errors during deployment
**Solution**: Test config with JSON schema validator

### 3. Missing IAM Permissions
**Symptom**: Lambda execution errors
**Solution**: Review getRequiredPermissions() method

### 4. Cold Start Performance
**Symptom**: First invocation timeouts
**Solution**: Use global client instances

### 5. Lambda Package Size
**Symptom**: Deployment fails due to size
**Solution**: Minimize dependencies, use Lambda layers

## Module Lifecycle Hooks

```
1. Configuration Phase
   └── validateConfig() called
   
2. Synthesis Phase
   ├── createResources() called
   ├── getRequiredPermissions() called
   └── getModuleOutputs() called (optional)
   
3. Deployment Phase
   └── CloudFormation creates resources
   
4. Runtime Phase
   └── Lambda functions execute
   
5. Deactivation Phase (when disabled)
   └── cleanup() called (optional)
```

## Examples

See [`modules/azure/`](../cdk/modules/azure/) for production example implementing:
- Multiple Lambda functions
- DynamoDB checkpoint store
- Secrets Manager integration
- Scheduled polling
- Error handling

## Resources

- [Module Interface Specification](./MODULE_INTERFACE_SPEC.md)
- [Configuration Schema](./CONFIG_SCHEMA.md)
- [AWS CDK Python Lambda](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_lambda-readme.html)
- [AWS Lambda Powertools Python](https://awslabs.github.io/aws-lambda-powertools-python/)
- [Security Lake OCSF](https://docs.aws.amazon.com/security-lake/latest/userguide/open-cybersecurity-schema-framework.html)

## Support

For questions or issues:
1. Review this guide and MODULE_INTERFACE_SPEC.md
2. Check existing module implementations
3. Review CDK synthesis errors

## Version History

### Version 1.0.0 (2025-01-22)
- Initial module development guide
- Complete examples for all steps
- Security and testing best practices