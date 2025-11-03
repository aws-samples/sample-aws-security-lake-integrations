/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Google Security Command Center Integration Module
 * 
 * Integrates Google Cloud Security Command Center findings with AWS Security Lake
 * via Pub/Sub polling and event transformation.
 */

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Construct } from 'constructs';
import {
  BaseIntegrationModule,
  ValidationResult,
  CoreResources
} from '../../lib/core/integration-module-interface';

export class GoogleSccIntegrationModule extends BaseIntegrationModule {
  readonly moduleId = 'google-scc';
  readonly moduleName = 'Google Security Command Center Integration';
  readonly moduleVersion = '1.0.0';
  readonly moduleDescription = 'Integrates Google Cloud Security Command Center findings with AWS Security Lake via Pub/Sub polling';

  private pubsubPollerFunctions: Map<string, lambda.Function> = new Map();
  private gcpCredentialsSecrets: Map<string, secretsmanager.ISecret> = new Map();

  /**
   * Validate module configuration
   */
  validateConfig(config: any): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Check required top-level fields
    if (!config.pubsubPollers) {
      errors.push('pubsubPollers configuration is required (should be an array)');
      return { valid: false, errors };
    }

    // Ensure pubsubPollers is an array
    if (!Array.isArray(config.pubsubPollers)) {
      errors.push('pubsubPollers must be an array of poller configurations');
      return { valid: false, errors };
    }

    // Validate each poller configuration
    config.pubsubPollers.forEach((pollerConfig: any, index: number) => {
      const pollerPrefix = `pubsubPollers[${index}]`;

      // Validate Pub/Sub Poller configuration
      if (pollerConfig.enabled) {
        if (!pollerConfig.moduleId) {
          errors.push(`${pollerPrefix}.moduleId is required`);
        }

        if (!pollerConfig.gcpCredentialsSecretName) {
          errors.push(`${pollerPrefix}.gcpCredentialsSecretName is required when poller is enabled`);
        }

        if (!pollerConfig.schedule) {
          errors.push(`${pollerPrefix}.schedule is required`);
        } else {
          const schedulePattern = /^(rate\(.+\)|cron\(.+\))$/;
          if (!schedulePattern.test(pollerConfig.schedule)) {
            errors.push(`${pollerPrefix}.schedule must be valid EventBridge expression (e.g., "rate(5 minutes)" or "cron(0 */5 * * ? *)")`);
          }
        }

        // Validate memory size
        if (pollerConfig.memorySize && (pollerConfig.memorySize < 128 || pollerConfig.memorySize > 10240)) {
          errors.push(`${pollerPrefix}.memorySize must be between 128 and 10240 MB`);
        }

        // Validate timeout
        if (pollerConfig.timeout && (pollerConfig.timeout < 1 || pollerConfig.timeout > 900)) {
          errors.push(`${pollerPrefix}.timeout must be between 1 and 900 seconds`);
        }

        // Validate reserved concurrent executions
        if (pollerConfig.reservedConcurrentExecutions !== undefined) {
          if (pollerConfig.reservedConcurrentExecutions < 0) {
            errors.push(`${pollerPrefix}.reservedConcurrentExecutions must be non-negative`);
          }
          if (pollerConfig.reservedConcurrentExecutions > 1) {
            warnings.push(`${pollerPrefix}.reservedConcurrentExecutions > 1 may cause duplicate processing; recommend value of 1`);
          }
        }
      }
    });

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
    // First, create all secrets defined in secretsManager section
    const createdSecrets = new Map<string, secretsmanager.ISecret>();
    if (config.secretsManager?.gcpCredentialsSecrets) {
      config.secretsManager.gcpCredentialsSecrets.forEach((secretConfig: any) => {
        if (secretConfig.create === true && secretConfig.secretName) {
          const secret = this.createSecret(scope, secretConfig);
          createdSecrets.set(secretConfig.secretName, secret);
        }
      });
    }

    // Then create pollers, referencing secrets by name
    if (config.pubsubPollers && Array.isArray(config.pubsubPollers)) {
      config.pubsubPollers.forEach((pollerConfig: any) => {
        if (pollerConfig.enabled) {
          const secretName = pollerConfig.gcpCredentialsSecretName;
          
          // Use created secret if available, otherwise reference existing
          let secret: secretsmanager.ISecret;
          if (createdSecrets.has(secretName)) {
            secret = createdSecrets.get(secretName)!;
          } else {
            secret = this.referenceSecret(scope, pollerConfig.moduleId, secretName);
          }
          
          this.gcpCredentialsSecrets.set(pollerConfig.moduleId, secret);

          // Create Pub/Sub poller Lambda (pass secret for IAM grants)
          const pollerFunction = this.createPubsubPoller(
            scope,
            coreResources,
            pollerConfig,
            secret
          );
          this.pubsubPollerFunctions.set(pollerConfig.moduleId, pollerFunction);

          // Set up scheduled polling
          if (pollerConfig.schedule) {
            this.createPollingSchedule(scope, pollerFunction, pollerConfig);
          }
        }
      });
    }
  }

  /**
   * Get required IAM permissions
   */
  getRequiredPermissions(): iam.PolicyStatement[] {
    return [
      new iam.PolicyStatement({
        sid: 'GoogleSccSecretsAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue',
          'secretsmanager:DescribeSecret'
        ],
        resources: [
          `arn:aws:secretsmanager:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:secret:${this.moduleId}-*`,
          `arn:aws:secretsmanager:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:secret:gcp-*`
        ]
      })
    ];
  }

  /**
   * Get module-specific CloudFormation outputs
   */
  getModuleOutputs(): Record<string, any> {
    const outputs: Record<string, any> = {};

    // Output information for each poller
    this.pubsubPollerFunctions.forEach((fn, moduleId) => {
      const sanitizedModuleId = moduleId.replace(/-/g, '');
      outputs[`PubsubPoller${sanitizedModuleId}FunctionArn`] = fn.functionArn;
      outputs[`PubsubPoller${sanitizedModuleId}FunctionName`] = fn.functionName;
    });

    this.gcpCredentialsSecrets.forEach((secret, moduleId) => {
      const sanitizedModuleId = moduleId.replace(/-/g, '');
      outputs[`GcpCredentials${sanitizedModuleId}SecretArn`] = secret.secretArn;
    });

    return outputs;
  }

  /**
   * Create a new GCP credentials secret
   */
  private createSecret(
    scope: Construct,
    secretConfig: any
  ): secretsmanager.ISecret {
    const secretName = secretConfig.secretName;

    if (!secretConfig.secretTemplate) {
      throw new Error(`secretTemplate is required for secret ${secretName}`);
    }

    // Create secret with explicit name
    const secret = new secretsmanager.Secret(scope, this.createResourceId(scope, `GcpSecret-${secretName}`), {
      secretName: secretName,  // Physical secret name - CDK uses this exact name
      description: secretConfig.description || `GCP Pub/Sub credentials`,
      secretStringValue: cdk.SecretValue.unsafePlainText(JSON.stringify(secretConfig.secretTemplate, null, 2))
    });

    cdk.Tags.of(secret).add('Module', this.moduleId);

    // Add CFN output
    new cdk.CfnOutput(scope, `GcpSecretCreated-${secretName}`, {
      value: secretName,
      description: `Created GCP secret: ${secretName}`
    });

    return secret;
  }

  /**
   * Reference an existing GCP credentials secret
   */
  private referenceSecret(
    scope: Construct,
    moduleId: string,
    secretName: string
  ): secretsmanager.ISecret {
    return secretsmanager.Secret.fromSecretNameV2(
      scope,
      this.createResourceId(scope, `RefGcpSecret-${moduleId}`),
      secretName
    );
  }

  /**
   * Create Pub/Sub poller Lambda function
   */
  private createPubsubPoller(
    scope: Construct,
    coreResources: CoreResources,
    pollerConfig: any,
    gcpSecret: secretsmanager.ISecret
  ): lambda.Function {
    const moduleId = pollerConfig.moduleId;

    // Get queue configuration for DLQ settings
    const queueConfig = coreResources.projectConfig.sqsQueue || {
      encryption: { useSharedKey: true },
      deadLetterQueue: {
        messageRetentionPeriod: 1209600
      }
    };

    // Create dedicated DLQ for this Pub/Sub Poller Lambda with CMK encryption
    const pubsubPollerDLQ = new sqs.Queue(
      scope,
      this.createResourceId(scope, `PubsubPollerDeadLetterQueue-${moduleId}`),
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
    const role = new iam.Role(scope, this.createResourceId(scope, `PubsubPollerRole-${moduleId}`), {
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
        resources: [pubsubPollerDLQ.queueArn]
      })
    );

    // Grant access to specific GCP credentials secret for this poller
    gcpSecret.grantRead(role);

    // Grant access to core resources
    coreResources.eventTransformerQueue.grantSendMessages(role);
    
    if (coreResources.sharedKmsKey) {
      coreResources.sharedKmsKey.grantEncryptDecrypt(role);
    }

    // Build environment variables
    const environment: { [key: string]: string } = {
      MODULE_ID: moduleId,
      SQS_QUEUE_URL: coreResources.eventTransformerQueue.queueUrl,
      GCP_CREDENTIALS_SECRET_NAME: pollerConfig.gcpCredentialsSecretName,
      LOGGING_LEVEL: pollerConfig.environment?.LOGGING_LEVEL || 'INFO',
      ...pollerConfig.environment
    };

    // Create Lambda function with Docker bundling
    const fn = new lambda.Function(scope, this.createResourceId(scope, `PubsubPoller-${moduleId}`), {
      description: `Polls GCP Pub/Sub subscription for ${moduleId} and forwards events to core transformer queue`,
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'app.lambda_handler',
      architecture: lambda.Architecture.ARM_64,
      code: lambda.Code.fromAsset(`modules/${this.moduleId}/src/lambda/pubsub-poller`, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            'bash', '-c', [
              'pip install -r requirements.txt -t /asset-output --platform manylinux2014_aarch64 --only-binary=:all:',
              'cp -au . /asset-output',
              'find /asset-output -name "*.pyc" -delete',
              'find /asset-output -type d -name "__pycache__" | xargs rm -rf'
            ].join(' && ')
          ],
          user: 'root',
        }
      }),
      role: role,
      timeout: cdk.Duration.seconds(pollerConfig.timeout || 300),
      memorySize: pollerConfig.memorySize || 512,
      reservedConcurrentExecutions: pollerConfig.reservedConcurrentExecutions !== undefined
        ? pollerConfig.reservedConcurrentExecutions
        : 1,
      environment: environment,
      deadLetterQueue: pubsubPollerDLQ,
      retryAttempts: 2
    });

    cdk.Tags.of(fn).add('Module', this.moduleId);
    cdk.Tags.of(fn).add('PollerId', moduleId);
    cdk.Tags.of(fn).add('Purpose', 'PubSubPoller');

    return fn;
  }

  /**
   * Create polling schedule for Pub/Sub poller
   */
  private createPollingSchedule(
    scope: Construct,
    fn: lambda.Function,
    pollerConfig: any
  ): void {
    const moduleId = pollerConfig.moduleId;
    const schedule = new events.Rule(scope, this.createResourceId(scope, `PollSchedule-${moduleId}`), {
      schedule: events.Schedule.expression(pollerConfig.schedule),
      enabled: true,
      description: `Polling schedule for ${moduleId}`
    });
    
    schedule.addTarget(new targets.LambdaFunction(fn, {
      retryAttempts: 2
    }));

    cdk.Tags.of(schedule).add('Module', this.moduleId);
    cdk.Tags.of(schedule).add('PollerId', moduleId);
  }
}