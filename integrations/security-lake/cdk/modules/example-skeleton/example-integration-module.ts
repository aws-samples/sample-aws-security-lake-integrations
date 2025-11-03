/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Example Skeleton Integration Module
 * 
 * This is a template for creating new Security Lake integration modules.
 * Copy this directory and modify for your specific integration.
 * 
 * INSTRUCTIONS:
 * 1. Copy this entire directory to modules/your-integration/
 * 2. Rename class ExampleIntegrationModule to YourIntegrationModule
 * 3. Update moduleId, moduleName, moduleVersion, moduleDescription
 * 4. Implement validateConfig() with your config requirements
 * 5. Implement createResources() with your AWS resources
 * 6. Implement getRequiredPermissions() with your IAM needs
 * 7. Update Lambda code in src/lambda/event-processor/
 * 8. Test locally and with integration tests
 * 9. Register module in lib/core/module-registry.ts
 * 10. Document in README.md
 */

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { 
  BaseIntegrationModule, 
  ValidationResult, 
  CoreResources,
  HealthCheckConfig
} from '../../lib/core/integration-module-interface';

/**
 * Example Integration Module
 * 
 * Template for creating new Security Lake integrations.
 * Demonstrates all required and optional interface methods.
 */
export class ExampleIntegrationModule extends BaseIntegrationModule {
  // ==========================================================================
  // REQUIRED PROPERTIES - Update these for your integration
  // ==========================================================================
  
  /** Unique module identifier (lowercase, alphanumeric, hyphens only) */
  readonly moduleId = 'example-skeleton';
  
  /** Human-readable module name */
  readonly moduleName = 'Example Skeleton Integration';
  
  /** Semantic version (MAJOR.MINOR.PATCH) */
  readonly moduleVersion = '1.0.0';
  
  /** Brief description of module functionality */
  readonly moduleDescription = 'Template module demonstrating integration pattern';

  // ==========================================================================
  // PRIVATE MODULE RESOURCES - Store created resources for reference
  // ==========================================================================
  
  private processorFunction?: lambda.Function;
  private credentialsSecret?: secretsmanager.ISecret;

  // ==========================================================================
  // REQUIRED METHOD: Configuration Validation
  // ==========================================================================
  
  /**
   * Validate module-specific configuration
   * 
   * Check all required fields, validate formats, provide helpful error messages.
   * This is called before createResources() during stack synthesis.
   * 
   * @param config - Module-specific configuration object
   * @returns ValidationResult with errors/warnings
   */
  validateConfig(config: any): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    // TODO: Add your configuration validation logic here

    // Example: Check required fields
    if (!config.eventProcessor) {
      errors.push('eventProcessor configuration is required');
    }

    if (config.eventProcessor?.enabled) {
      // Validate enabled processor configuration
      if (!config.eventProcessor.schedule) {
        errors.push('eventProcessor.schedule is required when processor is enabled');
      } else {
        // Validate schedule format
        const schedulePattern = /^(rate\(.+\)|cron\(.+\))$/;
        if (!schedulePattern.test(config.eventProcessor.schedule)) {
          errors.push('eventProcessor.schedule must be valid EventBridge rate or cron expression');
        }
      }

      // Validate memory size
      if (config.eventProcessor.memorySize) {
        if (config.eventProcessor.memorySize < 128 || config.eventProcessor.memorySize > 10240) {
          errors.push('eventProcessor.memorySize must be between 128 and 10240 MB');
        }
      }

      // Validate timeout
      if (config.eventProcessor.timeout) {
        if (config.eventProcessor.timeout < 1 || config.eventProcessor.timeout > 900) {
          errors.push('eventProcessor.timeout must be between 1 and 900 seconds');
        }
      }
    }

    // Example: Check for credentials secret name
    if (!config.credentialsSecretName) {
      errors.push('credentialsSecretName is required for authentication');
    }

    // Example: Check for deprecated fields
    if (config.deprecatedField) {
      warnings.push('deprecatedField is deprecated and will be removed in v2.0.0. Use newField instead');
    }

    return {
      valid: errors.length === 0,
      errors: errors.length > 0 ? errors : undefined,
      warnings: warnings.length > 0 ? warnings : undefined
    };
  }

  // ==========================================================================
  // REQUIRED METHOD: Resource Creation
  // ==========================================================================
  
  /**
   * Create module-specific AWS resources
   * 
   * This is where you create your Lambda functions, SQS queues, DynamoDB tables,
   * Secrets Manager secrets, and any other AWS resources your module needs.
   * 
   * @param scope - CDK construct scope (the SecurityLakeStack)
   * @param coreResources - Shared resources from core stack
   * @param config - Module-specific configuration
   */
  createResources(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): void {
    // TODO: Implement your resource creation logic

    // Example: Create credentials secret
    this.credentialsSecret = this.createCredentialsSecret(scope, config);

    // Example: Create event processor Lambda
    if (config.eventProcessor?.enabled) {
      this.processorFunction = this.createEventProcessor(scope, coreResources, config);
      
      // Example: Set up scheduled polling
      if (config.eventProcessor.schedule) {
        this.createPollingSchedule(scope, this.processorFunction, config);
      }
    }

    // TODO: Create additional resources as needed:
    // - SQS queues
    // - DynamoDB tables
    // - EventBridge rules
    // - CloudWatch alarms
    // - etc.
  }

  // ==========================================================================
  // REQUIRED METHOD: IAM Permissions
  // ==========================================================================
  
  /**
   * Get IAM policy statements required by this module
   * 
   * Return all IAM permissions your module needs.
   * Follow least privilege - be as specific as possible with resources.
   * 
   * @returns Array of IAM PolicyStatement objects
   */
  getRequiredPermissions(): iam.PolicyStatement[] {
    // TODO: Define your module's IAM permissions

    const permissions: iam.PolicyStatement[] = [];

    // Example: Secrets Manager access
    permissions.push(
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
    );

    // TODO: Add additional permissions as needed:
    // - DynamoDB access
    // - S3 access
    // - CloudWatch Logs
    // - etc.

    return permissions;
  }

  // ==========================================================================
  // OPTIONAL METHOD: Health Checks
  // ==========================================================================
  
  /**
   * Get health check configuration
   * 
   * Optional method to define health monitoring for your module components.
   * 
   * @returns HealthCheckConfig or undefined
   */
  getHealthCheckConfig(): HealthCheckConfig {
    // TODO: Configure health checks for your module

    return {
      enabled: true,
      checkInterval: cdk.Duration.minutes(5),
      failureThreshold: 3,
      alarmActions: [] // Add SNS topic ARNs for notifications
    };
  }

  // ==========================================================================
  // OPTIONAL METHOD: Module Outputs
  // ==========================================================================
  
  /**
   * Get module-specific CloudFormation outputs
   * 
   * Optional method to export useful values for operators.
   * 
   * @returns Record of output names to values
   */
  getModuleOutputs(): Record<string, any> {
    // TODO: Export useful information about your deployed module

    const outputs: Record<string, any> = {};

    if (this.processorFunction) {
      outputs[`${this.moduleId}ProcessorArn`] = this.processorFunction.functionArn;
      outputs[`${this.moduleId}ProcessorName`] = this.processorFunction.functionName;
    }

    if (this.credentialsSecret) {
      outputs[`${this.moduleId}SecretArn`] = this.credentialsSecret.secretArn;
    }

    return outputs;
  }

  // ==========================================================================
  // PRIVATE HELPER METHODS
  // ==========================================================================
  
  /**
   * Create credentials secret
   */
  private createCredentialsSecret(scope: Construct, config: any): secretsmanager.ISecret {
    // TODO: Implement credentials secret creation

    const secret = new secretsmanager.Secret(
      scope, 
      this.createResourceId(scope, 'Credentials'),
      {
        description: `Credentials for ${this.moduleName}`,
        secretName: config.credentialsSecretName,
        generateSecretString: {
          secretStringTemplate: JSON.stringify({
            apiKey: 'PLACEHOLDER',
            endpoint: 'PLACEHOLDER'
          }),
          generateStringKey: 'placeholder',
          excludeCharacters: '"\\'
        }
      }
    );

    return secret;
  }

  /**
   * Create event processor Lambda function
   */
  private createEventProcessor(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): lambda.Function {
    // TODO: Customize Lambda creation for your integration

    const processorConfig = config.eventProcessor;

    // Create IAM role
    const role = new iam.Role(scope, this.createResourceId(scope, 'ProcessorRole'), {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ]
    });

    // Apply module permissions
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
        MODULE_VERSION: this.moduleVersion,
        SQS_QUEUE_URL: coreResources.eventTransformerQueue.queueUrl,
        CREDENTIALS_SECRET_NAME: config.credentialsSecretName,
        LOGGING_LEVEL: processorConfig.environment?.LOGGING_LEVEL || 'INFO',
        ...processorConfig.environment
      },
      deadLetterQueueEnabled: true,
      retryAttempts: 2
    });

    // Create log group with retention
    new logs.LogGroup(scope, this.createResourceId(scope, 'ProcessorLogGroup'), {
      logGroupName: `/aws/lambda/${fn.functionName}`,
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    return fn;
  }

  /**
   * Create polling schedule for processor
   */
  private createPollingSchedule(
    scope: Construct,
    fn: lambda.Function,
    config: any
  ): void {
    // TODO: Customize polling schedule

    const schedule = new events.Rule(scope, this.createResourceId(scope, 'PollSchedule'), {
      schedule: events.Schedule.expression(config.eventProcessor.schedule),
      enabled: true,
      description: `Polling schedule for ${this.moduleName}`
    });
    
    schedule.addTarget(new targets.LambdaFunction(fn));
  }
}