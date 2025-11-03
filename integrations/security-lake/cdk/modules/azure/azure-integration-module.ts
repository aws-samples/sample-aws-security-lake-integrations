/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Azure Defender Integration Module
 * 
 * Integrates Microsoft Defender for Cloud and Azure VNet Flow Logs with AWS Security Lake.
 * Implements the IIntegrationModule interface for the Security Lake framework.
 */

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import { Construct } from 'constructs';
import { 
  BaseIntegrationModule, 
  ValidationResult, 
  CoreResources,
  HealthCheckConfig
} from '../../lib/core/integration-module-interface';

/**
 * Azure Defender Integration Module
 * 
 * Provides integration with:
 * - Microsoft Defender for Cloud (via Event Hub)
 * - Azure VNet Flow Logs (via Blob Storage)
 */
export class AzureIntegrationModule extends BaseIntegrationModule {
  // Module metadata
  readonly moduleId = 'azure';
  readonly moduleName = 'Azure Defender Integration';
  readonly moduleVersion = '2.0.0';
  readonly moduleDescription = 'Integrates Microsoft Defender for Cloud and Azure Flow Logs with AWS Security Lake';

  // Module resources
  private eventHubProcessor?: lambda.Function;
  private checkpointTable?: dynamodb.Table;
  private eventHubSecret?: secretsmanager.Secret;
  private flowLogSecret?: secretsmanager.Secret;

  /**
   * Validate Azure module configuration
   */
  validateConfig(config: any): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Validate Event Hub Processor config
    if (config.eventHubProcessor) {
      if (config.eventHubProcessor.enabled) {
        if (!config.eventHubProcessor.schedule) {
          errors.push('eventHubProcessor.schedule is required when enabled');
        } else {
          const schedulePattern = /^(rate\(.+\)|cron\(.+\))$/;
          if (!schedulePattern.test(config.eventHubProcessor.schedule)) {
            errors.push('eventHubProcessor.schedule must be valid EventBridge rate or cron expression');
          }
        }

        if (!config.eventHubProcessor.azureCredentialsSecretName) {
          errors.push('eventHubProcessor.azureCredentialsSecretName is required');
        }

        // Validate memory size
        if (config.eventHubProcessor.memorySize) {
          if (config.eventHubProcessor.memorySize < 128 || config.eventHubProcessor.memorySize > 10240) {
            errors.push('eventHubProcessor.memorySize must be between 128 and 10240 MB');
          }
        }

        // Validate timeout
        if (config.eventHubProcessor.timeout) {
          if (config.eventHubProcessor.timeout < 1 || config.eventHubProcessor.timeout > 900) {
            errors.push('eventHubProcessor.timeout must be between 1 and 900 seconds');
          }
        }
      }
    }

    // Validate Flow Log Secret config
    if (config.flowLogSecret) {
      if (!config.flowLogSecret.secretName) {
        warnings.push('flowLogSecret.secretName not specified, using default');
      }
    }

    // Validate checkpoint store config
    if (config.checkpointStore) {
      if (config.checkpointStore.enabled && !config.checkpointStore.tableName) {
        errors.push('checkpointStore.tableName is required when enabled');
      }
    }

    return {
      valid: errors.length === 0,
      errors: errors.length > 0 ? errors : undefined,
      warnings: warnings.length > 0 ? warnings : undefined
    };
  }

  /**
   * Create Azure module resources
   */
  createResources(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): void {
    // Create checkpoint store if needed
    if (config.checkpointStore?.enabled) {
      this.checkpointTable = this.createCheckpointStore(scope, coreResources, config);
    }

    // Create secrets
    this.eventHubSecret = this.createEventHubSecret(scope, config);
    this.flowLogSecret = this.createFlowLogSecret(scope, config);

    // Create Event Hub Processor Lambda
    if (config.eventHubProcessor?.enabled) {
      this.eventHubProcessor = this.createEventHubProcessor(scope, coreResources, config);
    }
  }

  /**
   * Get required IAM permissions for Azure module
   */
  getRequiredPermissions(): iam.PolicyStatement[] {
    const permissions: iam.PolicyStatement[] = [];

    // Secrets Manager permissions
    permissions.push(
      new iam.PolicyStatement({
        sid: 'AzureSecretsAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret'
        ],
        resources: [
          `arn:aws:secretsmanager:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:secret:azure-*`
        ]
      })
    );

    // DynamoDB checkpoint store permissions
    if (this.checkpointTable) {
      permissions.push(
        new iam.PolicyStatement({
          sid: 'AzureCheckpointStoreAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            'dynamodb:GetItem',
            'dynamodb:PutItem',
            'dynamodb:UpdateItem',
            'dynamodb:DeleteItem',
            'dynamodb:Query',
            'dynamodb:Scan'
          ],
          resources: [
            this.checkpointTable.tableArn,
            `${this.checkpointTable.tableArn}/index/*`
          ]
        })
      );
    }

    return permissions;
  }

  /**
   * Get health check configuration
   */
  getHealthCheckConfig(): HealthCheckConfig {
    return {
      enabled: true,
      checkInterval: cdk.Duration.minutes(5),
      failureThreshold: 3,
      alarmActions: []
    };
  }

  /**
   * Get module outputs
   */
  getModuleOutputs(): Record<string, any> {
    const outputs: Record<string, any> = {};

    if (this.eventHubProcessor) {
      outputs.AzureEventHubProcessorArn = this.eventHubProcessor.functionArn;
      outputs.AzureEventHubProcessorName = this.eventHubProcessor.functionName;
    }

    if (this.checkpointTable) {
      outputs.AzureCheckpointTableName = this.checkpointTable.tableName;
      outputs.AzureCheckpointTableArn = this.checkpointTable.tableArn;
    }

    if (this.eventHubSecret) {
      outputs.AzureEventHubSecretArn = this.eventHubSecret.secretArn;
    }

    if (this.flowLogSecret) {
      outputs.AzureFlowLogSecretArn = this.flowLogSecret.secretArn;
    }

    return outputs;
  }

  /**
   * Create DynamoDB checkpoint store for Event Hub
   */
  private createCheckpointStore(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): dynamodb.Table {
    const tableConfig = config.checkpointStore;

    const table = new dynamodb.Table(scope, this.createResourceId(scope, 'CheckpointStore'), {
      partitionKey: {
        name: 'pk',
        type: dynamodb.AttributeType.STRING
      },
      sortKey: {
        name: 'sk',
        type: dynamodb.AttributeType.STRING
      },
      billingMode: tableConfig.billingMode === 'PROVISIONED' 
        ? dynamodb.BillingMode.PROVISIONED 
        : dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: tableConfig.encryption?.useSharedKey && coreResources.sharedKmsKey
        ? dynamodb.TableEncryption.CUSTOMER_MANAGED
        : dynamodb.TableEncryption.AWS_MANAGED,
      encryptionKey: tableConfig.encryption?.useSharedKey ? coreResources.sharedKmsKey : undefined,
      timeToLiveAttribute: tableConfig.ttl?.attributeName || 'ttl',
      removalPolicy: coreResources.projectConfig.environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      pointInTimeRecovery: coreResources.projectConfig.environment === 'prod'
    });

    // Add GSI for type-based queries
    table.addGlobalSecondaryIndex({
      indexName: 'TypeIndex',
      partitionKey: {
        name: 'type',
        type: dynamodb.AttributeType.STRING
      },
      sortKey: {
        name: 'last_modified_time',
        type: dynamodb.AttributeType.STRING
      },
      projectionType: dynamodb.ProjectionType.ALL
    });

    return table;
  }

  /**
   * Create Event Hub credentials secret
   */
  private createEventHubSecret(scope: Construct, config: any): secretsmanager.Secret {
    const secretConfig = config.secretsManager?.eventHubSecret || {};

    return new secretsmanager.Secret(scope, this.createResourceId(scope, 'EventHubCredentials'), {
      description: secretConfig.description || 'Azure Event Hub connection credentials',
      secretName: config.eventHubProcessor?.azureCredentialsSecretName || 'azure-eventhub-credentials',
      generateSecretString: {
        secretStringTemplate: JSON.stringify(secretConfig.secretTemplate || {
          eventHubNamespace: 'PLACEHOLDER',
          eventHubName: 'PLACEHOLDER',
          consumerGroup: '$Default',
          connectionString: 'PLACEHOLDER'
        }),
        generateStringKey: 'connectionString',
        excludeCharacters: '"\\'
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });
  }

  /**
   * Create Flow Log credentials secret
   */
  private createFlowLogSecret(scope: Construct, config: any): secretsmanager.Secret {
    const secretConfig = config.secretsManager?.flowLogsSecret || config.flowLogSecret || {};

    return new secretsmanager.Secret(scope, this.createResourceId(scope, 'FlowLogCredentials'), {
      description: secretConfig.description || 'Azure Storage Account credentials for Flow Logs',
      secretName: secretConfig.secretName || 'azure-flowlogs-credentials',
      generateSecretString: {
        secretStringTemplate: JSON.stringify(secretConfig.secretTemplate || {
          tenantId: 'PLACEHOLDER',
          clientId: 'PLACEHOLDER',
          clientSecret: 'PLACEHOLDER',
          subscriptionId: 'PLACEHOLDER',
          storageAccountName: 'PLACEHOLDER'
        }),
        generateStringKey: 'placeholder',
        excludeCharacters: '"\\'
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });
  }

  /**
   * Create Event Hub Processor Lambda
   */
  private createEventHubProcessor(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): lambda.Function {
    const processorConfig = config.eventHubProcessor;

    // Get queue configuration for DLQ settings
    const queueConfig = config.checkpointStore?.encryption || coreResources.projectConfig.sqsQueue || {
      encryption: { useSharedKey: true },
      deadLetterQueue: {
        messageRetentionPeriod: 1209600
      }
    };

    // Create dedicated DLQ for Event Hub Processor Lambda with CMK encryption
    const eventHubProcessorDLQ = new sqs.Queue(
      scope,
      this.createResourceId(scope, 'EventHubProcessorDeadLetterQueue'),
      {
        retentionPeriod: cdk.Duration.seconds(
          queueConfig.deadLetterQueue?.messageRetentionPeriod || 1209600
        ),
        encryption: queueConfig.encryption?.useSharedKey && coreResources.sharedKmsKey
          ? sqs.QueueEncryption.KMS
          : sqs.QueueEncryption.KMS_MANAGED,
        encryptionMasterKey: queueConfig.encryption?.useSharedKey ? coreResources.sharedKmsKey : undefined
      }
    );

    // Create IAM role
    const role = new iam.Role(scope, this.createResourceId(scope, 'EventHubProcessorRole'), {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ]
    });

    // Grant module permissions
    this.getRequiredPermissions().forEach(statement => {
      role.addToPolicy(statement);
    });

    // Grant DLQ access
    role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'SQSDLQAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'sqs:SendMessage',
          'sqs:GetQueueAttributes'
        ],
        resources: [eventHubProcessorDLQ.queueArn]
      })
    );

    // Grant core resource access
    coreResources.eventTransformerQueue.grantSendMessages(role);
    if (coreResources.sharedKmsKey) {
      coreResources.sharedKmsKey.grantEncryptDecrypt(role);
    }

    // Grant access to EventHub credentials secret
    if (this.eventHubSecret) {
      this.eventHubSecret.grantRead(role);
    }

    // Create Lambda function
    const fn = new lambda.Function(
      scope,
      this.createResourceId(scope, "EventHubProcessor"),
      {
        description: 'Polls Azure Event Hub for Microsoft Defender events on schedule, manages DynamoDB checkpoints, and forwards events to core transformer queue',
        runtime: lambda.Runtime.PYTHON_3_13,
        handler: "app.lambda_handler",
        architecture: lambda.Architecture.ARM_64,
        code: lambda.Code.fromAsset(
          `modules/${this.moduleId}/src/lambda/event-hub-processor`,
          {
            bundling: {
              image: lambda.Runtime.PYTHON_3_13.bundlingImage,
              command: [
                "bash",
                "-c",
                [
                  // Install packages normally - Docker environment is already x86_64
                  "pip install -r requirements.txt -t /asset-output",
                  "cp -r . /asset-output",
                  // Add diagnostic information for pyarrow installation
                  'echo "=== PYARROW DIAGNOSTIC INFO ==="',
                  'find /asset-output -name "*pyarrow*" -type d | head -10',
                  'find /asset-output -name "*.so" -path "*pyarrow*" | head -10',
                  'ls -la /asset-output/pyarrow/ || echo "pyarrow directory not found"',
                  'file /asset-output/pyarrow/*.so 2>/dev/null | head -5 || echo "No .so files found in pyarrow"',
                  'echo "Lambda architecture: x86_64, Docker environment should match"',
                  // Minimal cleanup - only remove clearly unnecessary files
                  'find /asset-output -name "*.pyc" -delete',
                  'find /asset-output -type d -name "__pycache__" -exec rm -rf {} + || true',
                  // Only remove documentation from non-critical packages
                  'find /asset-output -name "README*" -path "*/site-packages/jinja2*" -delete || true',
                  'find /asset-output -name "README*" -path "*/site-packages/yaml*" -delete || true',
                  'find /asset-output -name "*.md" -path "*/site-packages/jinja2*" -delete || true',
                  // Set proper permissions on shared libraries
                  'find /asset-output -name "*.so" -exec chmod 755 {} \\;',
                  'echo "=== END DIAGNOSTIC INFO ==="',
                ].join(" && "),
              ],
              user: "root",
            },
          }
        ),
        role: role,
        timeout: cdk.Duration.seconds(processorConfig.timeout || 300),
        memorySize: processorConfig.memorySize || 512,
        reservedConcurrentExecutions:
          processorConfig.reservedConcurrentExecutions || 1,
        environment: {
          MODULE_ID: this.moduleId,
          MODULE_VERSION: this.moduleVersion,
          DYNAMODB_TABLE_NAME: this.checkpointTable?.tableName || "",
          SQS_QUEUE_URL: coreResources.eventTransformerQueue.queueUrl,
          AZURE_CREDENTIALS_SECRET_NAME:
            processorConfig.azureCredentialsSecretName,
          USE_CHECKPOINT_STORE: this.checkpointTable ? "true" : "false",
          LOGGING_LEVEL: processorConfig.environment?.LOGGING_LEVEL || "INFO",
          ...processorConfig.environment,
        },
        deadLetterQueue: eventHubProcessorDLQ,
        retryAttempts: 2,
      }
    );

    // Create log group
    new logs.LogGroup(scope, this.createResourceId(scope, 'EventHubProcessorLogGroup'), {
      logGroupName: `/aws/lambda/${fn.functionName}`,
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    // Create polling schedule
    const schedule = new events.Rule(scope, this.createResourceId(scope, 'EventHubPollSchedule'), {
      schedule: events.Schedule.expression(processorConfig.schedule),
      enabled: true,
      description: `Polling schedule for ${this.moduleName} Event Hub`
    });
    
    schedule.addTarget(new targets.LambdaFunction(fn));

    return fn;
  }
}