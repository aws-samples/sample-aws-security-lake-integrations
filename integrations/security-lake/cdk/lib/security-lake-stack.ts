/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Security Lake Integration Stack
 * 
 * Modular CDK stack that deploys core Security Lake processing infrastructure
 * and dynamically loads integration modules based on configuration.
 * 
 * Architecture:
 * - Core: Event transformer, Security Hub processor, Security Lake custom resource
 * - Modules: Dynamically loaded integration modules (Azure, GuardDuty, etc.)
 * - Shared: KMS encryption, SQS queues, monitoring
 */

import * as cdk from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as lakeformation from 'aws-cdk-lib/aws-lakeformation';
import { Construct } from 'constructs';
import { Logger } from './core/logger';
import { ProjectConfig } from './core/config-loader';
import { ModuleLoader } from './core/module-loader';
import { ModuleRegistry } from './core/module-registry';
import { CoreResources } from './core/integration-module-interface';

export interface SecurityLakeStackProps extends cdk.StackProps {
  config: ProjectConfig;
}

/**
 * Main Security Lake Integration Stack
 * 
 * This stack creates the core infrastructure for Security Lake integration
 * and dynamically loads integration modules based on configuration.
 */
export class SecurityLakeStack extends cdk.Stack {
  private readonly logger: Logger;
  private readonly config: ProjectConfig;
  private readonly moduleLoader: ModuleLoader;
  private sharedKmsKey: kms.Key | undefined;
  private eventTransformerQueue: sqs.Queue;
  private eventTransformerDeadLetterQueue: sqs.Queue;
  private eventTransformerLambda: lambda.Function | undefined;
  private securityHubProcessorLambda: lambda.Function | undefined;
  private flowLogProcessorLambda: lambda.Function | undefined;
  private asffQueue: sqs.Queue | undefined;
  private flowLogQueue: sqs.Queue | undefined;
  private securityLakeCustomResource: cdk.CustomResource | undefined;

  constructor(scope: Construct, id: string, props: SecurityLakeStackProps) {
    super(scope, id, props);

    this.config = props.config;
    this.logger = new Logger('SecurityLakeStack');
    this.moduleLoader = new ModuleLoader({ strictMode: true });

    this.logger.info('Initializing Security Lake Integration Stack', {
      projectName: this.config.projectName,
      environment: this.config.environment,
      region: this.config.awsRegion,
      securityLakeEnabled: this.config.securityLake?.enabled
    });

    // Apply resource tags
    this.applyResourceTags();

    // Create shared infrastructure
    this.sharedKmsKey = this.createSharedKmsKey();
    const queueResources = this.createCoreQueues();
    this.eventTransformerQueue = queueResources.queue;
    this.eventTransformerDeadLetterQueue = queueResources.deadLetterQueue;

    // Create ASFF queue if Security Hub is enabled
    if (this.config.securityHub?.enabled || this.config.coreProcessing?.securityHubProcessor?.enabled) {
      this.asffQueue = this.createAsffQueue();
    }

    // Create Flow Log queue if flow log processor is enabled
    if (this.config.coreProcessing?.flowLogProcessor?.enabled) {
      this.flowLogQueue = this.createFlowLogQueue();
    }

    // Create Security Lake integration (if enabled)
    this.createSecurityLakeIntegration();

    // Create core processing Lambdas
    this.createCoreProcessingLambdas(queueResources);

    // Load and initialize integration modules
    this.loadIntegrationModules();

    // Create monitoring and alarms
    this.createMonitoring();

    // Create stack outputs
    this.createStackOutputs();
  }

  /**
   * Apply resource tags
   */
  private applyResourceTags(): void {
    if (this.config.tags) {
      this.config.tags.forEach((tag: any) => {
        cdk.Tags.of(this).add(tag.key, tag.value);
      });
    }
  }

  /**
   * Create shared KMS key for all encrypted resources
   */
  private createSharedKmsKey(): kms.Key | undefined {
    if (!this.config.encryption?.enabled) {
      this.logger.info('Encryption disabled, skipping KMS key creation');
      return undefined;
    }

    const keyType = this.config.environment === 'prod' 
      ? this.config.production?.encryptionKeyType || this.config.encryption.keyType
      : this.config.development?.encryptionKeyType || this.config.encryption.keyType;

    if (keyType === 'AWS_OWNED_CMK') {
      this.logger.info('Using AWS owned CMK, no custom key needed');
      return undefined;
    }

    this.logger.info('Creating shared KMS key for all resources');

    const key = new kms.Key(this, 'SharedKmsKey', {
      alias: this.config.encryption.keyAlias,
      description: this.config.encryption.keyDescription || 'Shared KMS key for Security Lake integration',
      enableKeyRotation: this.config.encryption.keyRotationEnabled !== false,
      pendingWindow: cdk.Duration.days(this.config.encryption.keyPendingWindowInDays || 30),
      removalPolicy: this.config.environment === 'prod' 
        ? cdk.RemovalPolicy.RETAIN 
        : cdk.RemovalPolicy.DESTROY
    });

    // Grant permissions to AWS services
    key.grantEncryptDecrypt(new iam.ServicePrincipal('sqs.amazonaws.com'));
    key.grantEncryptDecrypt(new iam.ServicePrincipal('lambda.amazonaws.com'));
    key.grantEncryptDecrypt(new iam.ServicePrincipal('s3.amazonaws.com'));

    return key;
  }

  /**
   * Create core SQS queues
   */
  private createCoreQueues(): { queue: sqs.Queue; deadLetterQueue: sqs.Queue } {
    this.logger.info('Creating core SQS queues');

    const queueConfig = this.config.sqsQueue || {
      visibilityTimeout: 300,
      messageRetentionPeriod: 345600,
      maxMessageSize: 262144,
      receiveMessageWaitTime: 20,
      encryption: { useSharedKey: true },
      deadLetterQueue: {
        maxReceiveCount: 3,
        messageRetentionPeriod: 1209600
      }
    };

    const deadLetterQueue = new sqs.Queue(this, 'EventTransformerDLQ', {
      retentionPeriod: cdk.Duration.seconds(queueConfig.deadLetterQueue.messageRetentionPeriod),
      encryption: queueConfig.encryption.useSharedKey && this.sharedKmsKey
        ? sqs.QueueEncryption.KMS
        : sqs.QueueEncryption.KMS_MANAGED,
      encryptionMasterKey: queueConfig.encryption.useSharedKey ? this.sharedKmsKey : undefined
    });

    const queue = new sqs.Queue(this, 'EventTransformerQueue', {
      visibilityTimeout: cdk.Duration.seconds(queueConfig.visibilityTimeout),
      retentionPeriod: cdk.Duration.seconds(queueConfig.messageRetentionPeriod),
      maxMessageSizeBytes: queueConfig.maxMessageSize,
      receiveMessageWaitTime: cdk.Duration.seconds(queueConfig.receiveMessageWaitTime),
      encryption: queueConfig.encryption.useSharedKey && this.sharedKmsKey
        ? sqs.QueueEncryption.KMS
        : sqs.QueueEncryption.KMS_MANAGED,
      encryptionMasterKey: queueConfig.encryption.useSharedKey ? this.sharedKmsKey : undefined,
      deadLetterQueue: {
        queue: deadLetterQueue,
        maxReceiveCount: queueConfig.deadLetterQueue.maxReceiveCount
      }
    });

    return { queue, deadLetterQueue };
  }

  /**
   * Create ASFF SQS queue for Security Hub integration
   */
  private createAsffQueue(): sqs.Queue {
    this.logger.info('Creating ASFF SQS queue for Security Hub integration');

    const queueConfig = this.config.sqsQueue || {
      visibilityTimeout: 300,
      messageRetentionPeriod: 345600,
      encryption: { useSharedKey: true },
      deadLetterQueue: {
        maxReceiveCount: 3,
        messageRetentionPeriod: 1209600
      }
    };

    const asffDeadLetterQueue = new sqs.Queue(this, 'AsffDLQ', {
      retentionPeriod: cdk.Duration.seconds(queueConfig.deadLetterQueue.messageRetentionPeriod),
      encryption: queueConfig.encryption.useSharedKey && this.sharedKmsKey
        ? sqs.QueueEncryption.KMS
        : sqs.QueueEncryption.KMS_MANAGED,
      encryptionMasterKey: queueConfig.encryption.useSharedKey ? this.sharedKmsKey : undefined
    });

    const asffQueue = new sqs.Queue(this, 'AsffQueue', {
      visibilityTimeout: cdk.Duration.seconds(queueConfig.visibilityTimeout),
      retentionPeriod: cdk.Duration.seconds(queueConfig.messageRetentionPeriod),
      encryption: queueConfig.encryption.useSharedKey && this.sharedKmsKey
        ? sqs.QueueEncryption.KMS
        : sqs.QueueEncryption.KMS_MANAGED,
      encryptionMasterKey: queueConfig.encryption.useSharedKey ? this.sharedKmsKey : undefined,
      deadLetterQueue: {
        queue: asffDeadLetterQueue,
        maxReceiveCount: queueConfig.deadLetterQueue.maxReceiveCount
      }
    });

    return asffQueue;
  }

  /**
   * Create Flow Log SQS queue for flow log processing
   */
  private createFlowLogQueue(): sqs.Queue {
    this.logger.info('Creating Flow Log SQS queue');

    const queueConfig = this.config.sqsQueue || {
      visibilityTimeout: 300,
      messageRetentionPeriod: 345600,
      encryption: { useSharedKey: true },
      deadLetterQueue: {
        maxReceiveCount: 3,
        messageRetentionPeriod: 1209600
      }
    };

    // Ensure queue visibility timeout is at least as long as the flow log processor timeout plus buffer
    const flowLogProcessorTimeout = this.config.coreProcessing?.flowLogProcessor?.timeout || 600;
    const queueVisibilityTimeout = Math.max(queueConfig.visibilityTimeout, flowLogProcessorTimeout + 10);

    const flowLogDeadLetterQueue = new sqs.Queue(this, 'FlowLogDLQ', {
      retentionPeriod: cdk.Duration.seconds(queueConfig.deadLetterQueue.messageRetentionPeriod),
      encryption: queueConfig.encryption.useSharedKey && this.sharedKmsKey
        ? sqs.QueueEncryption.KMS
        : sqs.QueueEncryption.KMS_MANAGED,
      encryptionMasterKey: queueConfig.encryption.useSharedKey ? this.sharedKmsKey : undefined
    });

    const flowLogQueue = new sqs.Queue(this, 'FlowLogQueue', {
      visibilityTimeout: cdk.Duration.seconds(queueVisibilityTimeout),
      retentionPeriod: cdk.Duration.seconds(queueConfig.messageRetentionPeriod),
      encryption: queueConfig.encryption.useSharedKey && this.sharedKmsKey
        ? sqs.QueueEncryption.KMS
        : sqs.QueueEncryption.KMS_MANAGED,
      encryptionMasterKey: queueConfig.encryption.useSharedKey ? this.sharedKmsKey : undefined,
      deadLetterQueue: {
        queue: flowLogDeadLetterQueue,
        maxReceiveCount: queueConfig.deadLetterQueue.maxReceiveCount
      }
    });

    return flowLogQueue;
  }

  /**
   * Create Security Lake integration resources
   */
  private createSecurityLakeIntegration(): void {
    if (!this.config.securityLake?.enabled) {
      this.logger.info('Security Lake integration disabled, skipping');
      return;
    }

    this.logger.info('Creating Security Lake integration custom resource');

    // Create IAM role for custom resource Lambda
    const customResourceRole = new iam.Role(this, 'SecurityLakeCustomResourceRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
        managedPolicies: [
          iam.ManagedPolicy.fromAwsManagedPolicyName(
            "service-role/AWSLambdaBasicExecutionRole",
          ),
          iam.ManagedPolicy.fromAwsManagedPolicyName(
            "service-role/AWSGlueServiceRole",
          ),
        ],
        inlinePolicies: {
          SecurityLakePolicy: new iam.PolicyDocument({
            statements: [
              new iam.PolicyStatement({
                sid: "SecurityLakeAccess",
                effect: iam.Effect.ALLOW,
                actions: [
                  "securitylake:CreateCustomLogSource",
                  "securitylake:DeleteCustomLogSource",
                  "securitylake:UpdateCustomLogSource",
                  "securitylake:ListLogSources",
                  "securitylake:GetCustomLogSource",
                  "lakeformation:RegisterResource",
                  "lakeformation:GrantPermissions",
                  "lakeformation:CreateTable",
                  "lakeformation:UpdateTable",
                  "lakeformation:DeleteTable",
                  "lakeformation:GetTable",
                  "lakeformation:GetTableObjects",
                  "glue:CreateCrawler",
                  "glue:CreateDatabase",
                  "glue:CreateTable",
                  "glue:UpdateTable",
                  "glue:DeleteTable",
                  "glue:GetTable",
                  "glue:GetTables",
                  "glue:StopCrawlerSchedule",
                ],
                resources: ["*"],
              }),
              new iam.PolicyStatement({
                sid: "SecurityLakeS3Access",
                effect: iam.Effect.ALLOW,
                actions: ["s3:PutObject", "s3:ListBucket"],
                resources: [
                  `arn:aws:s3:::${this.config.securityLake.s3Bucket}`,
                  `arn:aws:s3:::${this.config.securityLake.s3Bucket}/*`,
                ],
              }),
              new iam.PolicyStatement({
                sid: "IAMPassRoleOnly",
                effect: iam.Effect.ALLOW,
                actions: ["iam:PassRole"],
                resources: [
                  `arn:aws:iam::${this.account}:role/${this.config.securityLake.serviceRole}`,
                  `arn:aws:iam::${this.account}:role/AmazonSecurityLake-Provider-*`,
                ],
              }),
              new iam.PolicyStatement({
                sid: "IAMRolesOnly",
                effect: iam.Effect.ALLOW,
                actions: [
                  "iam:CreateRole",
                  "iam:GetRole",
                  "iam:DeleteRole",
                  "iam:PutRolePolicy",
                  "iam:DeleteRolePolicy",
                  "iam:ListRolePolicies",
                ],
                resources: [`*`],
              }),
              new iam.PolicyStatement({
                sid: "STSGetCallerIdentity",
                effect: iam.Effect.ALLOW,
                actions: ["sts:GetCallerIdentity"],
                resources: ["*"],
              }),
            ],
          }),
        },
      }
    );

    // Grant KMS permissions if using shared key
    if (this.sharedKmsKey) {
      this.sharedKmsKey.grantEncryptDecrypt(customResourceRole);
    }

    // Configure Lake Formation administrator
    const dataLakeSettings = new lakeformation.CfnDataLakeSettings(
      this,
      'SecurityLakeDataLakeSettings',
      {
        admins: [
          {
            dataLakePrincipalIdentifier: customResourceRole.roleArn
          }
        ]
      }
    );

    this.logger.info(
      'Configured custom resource role as Lake Formation administrator'
    );

    // Create custom resource Lambda
    const customResourceLambda = new lambda.Function(
      this,
      'SecurityLakeCustomResourceLambda',
      {
        description: 'CloudFormation custom resource handler that creates Security Lake custom log sources and configures Lake Formation permissions',
        runtime: lambda.Runtime.PYTHON_3_13,
        handler: 'app.lambda_handler',
        code: lambda.Code.fromAsset('src/lambda/security-lake-custom-resource', {
          bundling: {
            image: lambda.Runtime.PYTHON_3_13.bundlingImage,
            command: [
              'bash',
              '-c',
              [
                'pip install -r requirements.txt -t /asset-output',
                'cp -au . /asset-output',
                'find /asset-output -name "*.pyc" -delete',
                'find /asset-output -type d -name "__pycache__" | xargs rm -rf'
              ].join(' && ')
            ],
            user: 'root'
          }
        }),
        role: customResourceRole,
        timeout: cdk.Duration.seconds(60),
        memorySize: 256,
        environment: {
          LOGGING_LEVEL: 'INFO'
        }
      }
    );

    // Create custom resource provider
    const provider = new cr.Provider(this, 'SecurityLakeCustomResourceProvider', {
      onEventHandler: customResourceLambda,
      logRetention: logs.RetentionDays.ONE_WEEK
    });

    // Create custom resource
    this.securityLakeCustomResource = new cdk.CustomResource(
      this,
      'SecurityLakeCustomResource',
      {
        serviceToken: provider.serviceToken,
        properties: {
          S3Bucket: this.config.securityLake.s3Bucket,
          ExternalId: this.config.securityLake.externalId,
          ServiceRole: this.config.securityLake.serviceRole,
          OCSFEventClass: this.config.securityLake.OCSFEventClass,
          ConfigHash: cdk.Fn.base64(JSON.stringify(this.config.securityLake)),
          DeploymentVersion: (this.config as any).deploymentVersion || '2.0.0'
        }
      }
    );

    // Ensure Lake Formation settings are applied before custom resource runs
    this.securityLakeCustomResource.node.addDependency(dataLakeSettings);

    this.logger.info('Security Lake integration created successfully');
  }

  /**
   * Create core processing Lambda functions
   */
  private createCoreProcessingLambdas(queueResources: { queue: sqs.Queue; deadLetterQueue: sqs.Queue }): void {
    // Create Event Transformer Lambda
    if (this.config.coreProcessing?.eventTransformer?.enabled) {
      this.eventTransformerLambda = this.createEventTransformerLambda(
        queueResources.queue,
        queueResources.deadLetterQueue
      );
    }

    // Create Security Hub Processor Lambda
    if (this.config.coreProcessing?.securityHubProcessor?.enabled && this.config.securityHub?.enabled && this.asffQueue) {
      this.securityHubProcessorLambda = this.createSecurityHubProcessorLambda(this.asffQueue);
    }

    // Create Flow Log Processor Lambda
    if (this.config.coreProcessing?.flowLogProcessor?.enabled && this.flowLogQueue) {
      this.flowLogProcessorLambda = this.createFlowLogProcessorLambda(this.flowLogQueue);
    }
  }

  /**
   * Create Event Transformer Lambda
   */
  private createEventTransformerLambda(
    queue: sqs.Queue,
    deadLetterQueue: sqs.Queue
  ): lambda.Function {
    this.logger.info('Creating Event Transformer Lambda');

    const lambdaConfig = this.config.coreProcessing?.eventTransformer || {
      memorySize: 512,
      timeout: 300,
      reservedConcurrentExecutions: 10,
      batchSize: 10,
      maximumBatchingWindowInSeconds: 5,
      environment: {}
    };

    // Create IAM role for Lambda
    const lambdaRole = new iam.Role(this, 'EventTransformerLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        SQSAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'SQSQueueAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'sqs:ReceiveMessage',
                'sqs:DeleteMessage',
                'sqs:GetQueueAttributes',
                'sqs:SendMessage'
              ],
              resources: [
                queue.queueArn,
                deadLetterQueue.queueArn,
                ...(this.asffQueue ? [this.asffQueue.queueArn] : []),
                ...(this.flowLogQueue ? [this.flowLogQueue.queueArn] : [])
              ]
            })
          ]
        }),
        S3Access: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'SecurityLakeS3Access',
              effect: iam.Effect.ALLOW,
              actions: [
                's3:PutObject',
                's3:PutObjectAcl',
                's3:GetBucketLocation',
                's3:ListBucket'
              ],
              resources: this.config.securityLake?.enabled
                ? [
                    `arn:aws:s3:::${this.config.securityLake.s3Bucket}`,
                    `arn:aws:s3:::${this.config.securityLake.s3Bucket}/*`
                  ]
                : ['*']
            })
          ]
        })
      }
    });

    // Grant KMS permissions if using shared key
    if (this.sharedKmsKey) {
      this.sharedKmsKey.grantEncryptDecrypt(lambdaRole);
    }

    const lambdaFunction = new lambda.Function(this, 'EventTransformerLambda', {
      description: 'Transforms security events from SQS into OCSF format, routes to Security Lake S3, ASFF queue for Security Hub, and flow log queue for network events',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'app.lambda_handler',
      architecture: lambda.Architecture.ARM_64,
      code: lambda.Code.fromAsset('src/lambda/event-transformer', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              'pip install -r requirements.txt -t /asset-output',
              'cp -r . /asset-output',
              'find /asset-output -name "*.pyc" -delete',
              'find /asset-output -type d -name "__pycache__" -exec rm -rf {} + || true',
              'find /asset-output -name "README*" -path "*/site-packages/jinja2*" -delete || true',
              'find /asset-output -name "README*" -path "*/site-packages/yaml*" -delete || true',
              'find /asset-output -name "*.md" -path "*/site-packages/jinja2*" -delete || true',
              'find /asset-output -name "*.so" -exec chmod 755 {} \\;'
            ].join(' && ')
          ],
          user: 'root'
        }
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(lambdaConfig.timeout),
      memorySize: lambdaConfig.memorySize,
      reservedConcurrentExecutions: lambdaConfig.reservedConcurrentExecutions,
      environment: {
        // Logging configuration
        LOGGING_LEVEL: lambdaConfig.environment?.LOGGING_LEVEL || 'INFO',
        
        // Spread any additional config environment variables
        ...lambdaConfig.environment,
        
        // Feature flags
        CLOUDTRAIL_ENABLED: lambdaConfig.eventDataStoreEnabled ? 'true' : 'false',
        SECURITY_LAKE_ENABLED: this.config.securityLake?.enabled ? 'true' : 'false',
        ASFF_ENABLED: this.config.securityHub?.enabled ? 'true' : 'false',
        
        // Queue URLs
        EVENT_DLQ: deadLetterQueue.queueUrl,
        ASFF_SQS_QUEUE: this.asffQueue?.queueUrl || '',
        FLOW_LOG_SQS_QUEUE: this.flowLogQueue?.queueUrl || '',
        
        // Security Lake configuration (conditionally set when enabled)
        ...(this.config.securityLake?.enabled
          ? {
              SECURITY_LAKE_S3_BUCKET: this.config.securityLake.s3Bucket,
              SECURITY_LAKE_SOURCES: JSON.stringify(
                this.config.securityLake.OCSFEventClass
              ),
              SECURITY_LAKE_PATH:
                this.securityLakeCustomResource
                  ?.getAtt('ProviderLocation')
                  .toString() || '',
            }
          : {})
      }
    });

    // Connect Lambda to SQS queue as event source
    lambdaFunction.addEventSource(
      new lambdaEventSources.SqsEventSource(queue, {
        batchSize: lambdaConfig.batchSize,
        maxBatchingWindow: cdk.Duration.seconds(lambdaConfig.maximumBatchingWindowInSeconds),
        reportBatchItemFailures: true
      })
    );

    // Create CloudWatch log group
    new logs.LogGroup(this, 'EventTransformerLogGroup', {
      logGroupName: `/aws/lambda/${lambdaFunction.functionName}`,
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    this.logger.info('Event Transformer Lambda created successfully');
    return lambdaFunction;
  }

  /**
   * Create Security Hub Processor Lambda
   */
  private createSecurityHubProcessorLambda(asffQueue: sqs.Queue): lambda.Function {
    this.logger.info('Creating Security Hub Processor Lambda');

    const lambdaConfig = this.config.coreProcessing?.securityHubProcessor || {
      memorySize: 256,
      timeout: 60,
      reservedConcurrentExecutions: 5,
      batchSize: 10,
      maximumBatchingWindowInSeconds: 5,
      environment: {}
    };

    const queueConfig = this.config.sqsQueue || {
      encryption: { useSharedKey: true },
      deadLetterQueue: {
        messageRetentionPeriod: 1209600
      }
    };

    // Create dedicated DLQ for Security Hub Processor Lambda with CMK encryption
    const securityHubProcessorDLQ = new sqs.Queue(this, 'SecurityHubProcessorLambdaDeadLetterQueue', {
      retentionPeriod: cdk.Duration.seconds(queueConfig.deadLetterQueue.messageRetentionPeriod),
      encryption: queueConfig.encryption.useSharedKey && this.sharedKmsKey
        ? sqs.QueueEncryption.KMS
        : sqs.QueueEncryption.KMS_MANAGED,
      encryptionMasterKey: queueConfig.encryption.useSharedKey ? this.sharedKmsKey : undefined
    });

    // Create IAM role for Lambda
    const lambdaRole = new iam.Role(this, 'SecurityHubProcessorLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        SecurityHubAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'SQSAsffQueueAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'sqs:ReceiveMessage',
                'sqs:DeleteMessage',
                'sqs:DeleteMessageBatch',
                'sqs:GetQueueAttributes',
                'sqs:ChangeMessageVisibility',
                'sqs:ChangeMessageVisibilityBatch'
              ],
              resources: [asffQueue.queueArn]
            }),
            new iam.PolicyStatement({
              sid: 'SQSDLQAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'sqs:SendMessage',
                'sqs:GetQueueAttributes'
              ],
              resources: [securityHubProcessorDLQ.queueArn]
            }),
            new iam.PolicyStatement({
              sid: 'SecurityHubFindingsImport',
              effect: iam.Effect.ALLOW,
              actions: ['securityhub:BatchImportFindings'],
              resources: ['*'] // SecurityHub findings import requires wildcard
            })
          ]
        })
      }
    });

    // Grant KMS permissions if using shared key
    if (this.sharedKmsKey) {
      this.sharedKmsKey.grantEncryptDecrypt(lambdaRole);
    }

    const lambdaFunction = new lambda.Function(this, 'SecurityHubProcessorLambda', {
      description: 'Imports ASFF-formatted security findings from SQS into AWS Security Hub using BatchImportFindings API',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'app.lambda_handler',
      code: lambda.Code.fromAsset('src/lambda/securityhub-processor', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              'pip install -r requirements.txt -t /asset-output',
              'cp -au . /asset-output',
              'find /asset-output -name "*.pyc" -delete',
              'find /asset-output -type d -name "__pycache__" | xargs rm -rf'
            ].join(' && ')
          ],
          user: 'root'
        }
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(lambdaConfig.timeout),
      memorySize: lambdaConfig.memorySize,
      reservedConcurrentExecutions: lambdaConfig.reservedConcurrentExecutions,
      environment: {
        ...lambdaConfig.environment,
        DEPLOYMENT_VERSION: (this.config as any).deploymentVersion || '2.0.0'
      },
      deadLetterQueue: securityHubProcessorDLQ,
      retryAttempts: 2
    });

    // Connect Lambda to ASFF SQS queue as event source
    lambdaFunction.addEventSource(
      new lambdaEventSources.SqsEventSource(asffQueue, {
        batchSize: lambdaConfig.batchSize,
        maxBatchingWindow: cdk.Duration.seconds(lambdaConfig.maximumBatchingWindowInSeconds),
        reportBatchItemFailures: true
      })
    );

    // Create CloudWatch log group
    new logs.LogGroup(this, 'SecurityHubProcessorLogGroup', {
      logGroupName: `/aws/lambda/${lambdaFunction.functionName}`,
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    this.logger.info('Security Hub Processor Lambda created successfully');
    return lambdaFunction;
  }

  /**
   * Create Flow Log Processor Lambda
   */
  private createFlowLogProcessorLambda(flowLogQueue: sqs.Queue): lambda.Function {
    this.logger.info('Creating Flow Log Processor Lambda');

    const lambdaConfig = this.config.coreProcessing?.flowLogProcessor || {
      memorySize: 1024,
      timeout: 600,
      reservedConcurrentExecutions: 5,
      batchSize: 10,
      maximumBatchingWindowInSeconds: 5,
      environment: {}
    };

    const queueConfig = this.config.sqsQueue || {
      encryption: { useSharedKey: true },
      deadLetterQueue: {
        messageRetentionPeriod: 1209600
      }
    };

    // Create dedicated DLQ for Flow Log Processor Lambda with CMK encryption
    const flowLogProcessorDLQ = new sqs.Queue(this, 'FlowLogProcessorLambdaDeadLetterQueue', {
      retentionPeriod: cdk.Duration.seconds(queueConfig.deadLetterQueue.messageRetentionPeriod),
      encryption: queueConfig.encryption.useSharedKey && this.sharedKmsKey
        ? sqs.QueueEncryption.KMS
        : sqs.QueueEncryption.KMS_MANAGED,
      encryptionMasterKey: queueConfig.encryption.useSharedKey ? this.sharedKmsKey : undefined
    });

    // Create IAM role for Lambda
    const lambdaRole = new iam.Role(this, 'FlowLogProcessorLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        SQSAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'FlowLogSQSQueueAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'sqs:ReceiveMessage',
                'sqs:DeleteMessage',
                'sqs:DeleteMessageBatch',
                'sqs:GetQueueAttributes',
                'sqs:ChangeMessageVisibility',
                'sqs:ChangeMessageVisibilityBatch'
              ],
              resources: [flowLogQueue.queueArn]
            }),
            new iam.PolicyStatement({
              sid: 'SQSDLQAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'sqs:SendMessage',
                'sqs:GetQueueAttributes'
              ],
              resources: [flowLogProcessorDLQ.queueArn]
            })
          ]
        }),
        S3Access: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'SecurityLakeS3FlowLogAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                's3:PutObject',
                's3:PutObjectAcl',
                's3:GetBucketLocation',
                's3:ListBucket'
              ],
              resources: this.config.securityLake?.enabled
                ? [
                    `arn:aws:s3:::${this.config.securityLake.s3Bucket}`,
                    `arn:aws:s3:::${this.config.securityLake.s3Bucket}/*`
                  ]
                : ['*']
            })
          ]
        }),
        SecretsManagerAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'FlowLogSecretsAccess',
              effect: iam.Effect.ALLOW,
              actions: [
                'secretsmanager:GetSecretValue',
                'secretsmanager:DescribeSecret'
              ],
              resources: [
                `arn:aws:secretsmanager:${this.region}:${this.account}:secret:*flowlog*`,
                `arn:aws:secretsmanager:${this.region}:${this.account}:secret:*flow-log*`
              ]
            })
          ]
        })
      }
    });

    // Grant KMS permissions if using shared key
    if (this.sharedKmsKey) {
      this.sharedKmsKey.grantEncryptDecrypt(lambdaRole);
    }

    const lambdaFunction = new lambda.Function(this, 'FlowLogProcessorLambda', {
      description: 'Processes network flow logs from SQS, retrieves data from cloud storage, transforms to OCSF network activity format, and writes to Security Lake S3',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'app.lambda_handler',
      architecture: lambda.Architecture.ARM_64,
      code: lambda.Code.fromAsset('src/lambda/flow-log-processor', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              'pip install -r requirements.txt -t /asset-output',
              'cp -r . /asset-output',
              'find /asset-output -name "*.pyc" -delete',
              'find /asset-output -type d -name "__pycache__" -exec rm -rf {} + || true',
              'find /asset-output -name "README*" -path "*/site-packages/jinja2*" -delete || true',
              'find /asset-output -name "README*" -path "*/site-packages/yaml*" -delete || true',
              'find /asset-output -name "*.md" -path "*/site-packages/jinja2*" -delete || true',
              'find /asset-output -name "*.so" -exec chmod 755 {} \\;'
            ].join(' && ')
          ],
          user: 'root'
        }
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(lambdaConfig.timeout),
      memorySize: lambdaConfig.memorySize,
      reservedConcurrentExecutions: lambdaConfig.reservedConcurrentExecutions,
      environment: {
        // Logging configuration
        LOGGING_LEVEL: lambdaConfig.environment?.LOGGING_LEVEL || 'INFO',
        
        // Spread any additional config environment variables
        ...lambdaConfig.environment,
        
        // Azure credentials secret name (for flow log processor to access Azure blob storage)
        AZURE_FLOWLOG_CREDENTIALS_SECRET_NAME:
          ((this.config.integrations?.azure as any)?.config?.flowLogProcessor?.azureFlowLogsSecretName ||
          (this.config.integrations?.azure as any)?.config?.secretsManager?.flowLogsSecret?.secretName ||
          'mdc-azure-flowlog-credentials'),
        
        // Security Lake configuration (conditionally set when enabled)
        ...(this.config.securityLake?.enabled
          ? {
              SECURITY_LAKE_ENABLED: 'true',
              SECURITY_LAKE_S3_BUCKET: this.config.securityLake.s3Bucket,
              SECURITY_LAKE_PATH:
                this.securityLakeCustomResource
                  ?.getAtt('ProviderLocation')
                  .toString() || '',
            }
          : { SECURITY_LAKE_ENABLED: 'false' })
      },
      deadLetterQueue: flowLogProcessorDLQ,
      retryAttempts: 2
    });

    // Connect Lambda to SQS queue as event source
    lambdaFunction.addEventSource(
      new lambdaEventSources.SqsEventSource(flowLogQueue, {
        batchSize: lambdaConfig.batchSize,
        maxBatchingWindow: cdk.Duration.seconds(lambdaConfig.maximumBatchingWindowInSeconds),
        reportBatchItemFailures: true
      })
    );

    // Create CloudWatch log group
    new logs.LogGroup(this, 'FlowLogProcessorLogGroup', {
      logGroupName: `/aws/lambda/${lambdaFunction.functionName}`,
      retention: logs.RetentionDays.THREE_MONTHS,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    this.logger.info('Flow Log Processor Lambda created successfully');
    return lambdaFunction;
  }

  /**
   * Load and initialize integration modules
   */
  private async loadIntegrationModules(): Promise<void> {
    if (!this.config.integrations) {
      this.logger.info('No integration modules configured');
      return;
    }

    this.logger.info('Loading integration modules', {
      configuredModules: Object.keys(this.config.integrations)
    });

    // Load modules from configuration
    try {
      const modules = await this.moduleLoader.loadModules(this.config.integrations);
      
      // Build core resources object to pass to modules
      const coreResources: CoreResources = {
        eventTransformerQueue: this.eventTransformerQueue,
        eventTransformerDeadLetterQueue: this.eventTransformerDeadLetterQueue,
        asffQueue: this.asffQueue,
        flowLogQueue: this.flowLogQueue,
        sharedKmsKey: this.sharedKmsKey,
        securityLakeBucket: this.config.securityLake?.s3Bucket || '',
        securityLakeCustomResource: this.securityLakeCustomResource,
        projectConfig: this.config
      };

      // Initialize modules
      this.moduleLoader.initializeModules(this, coreResources);

      this.logger.info('Integration modules loaded and initialized successfully', {
        totalModules: modules.length,
        enabledModules: modules.filter(m => m.enabled).length
      });
    } catch (error) {
      this.logger.error('Failed to load integration modules', error);
      throw error;
    }
  }

  /**
   * Create monitoring and alarms
   */
  private createMonitoring(): void {
    if (!this.config.monitoring?.enabled) {
      this.logger.info('Monitoring disabled, skipping alarms');
      return;
    }

    this.logger.info('Monitoring will be configured for core components and modules');
    // Implementation will include CloudWatch alarms for:
    // - DLQ message counts
    // - Lambda errors
    // - SQS message age
    // - Module-specific health checks
  }

  /**
   * Create stack outputs
   */
  private createStackOutputs(): void {
    new cdk.CfnOutput(this, 'StackVersion', {
      value: '2.0.0',
      description: 'Security Lake Integration Stack version'
    });

    new cdk.CfnOutput(this, 'Framework', {
      value: 'Modular',
      description: 'Stack architecture type'
    });

    new cdk.CfnOutput(this, 'EventTransformerQueueUrl', {
      value: this.eventTransformerQueue.queueUrl,
      description: 'Core event transformer queue URL'
    });

    if (this.sharedKmsKey) {
      new cdk.CfnOutput(this, 'SharedKmsKeyArn', {
        value: this.sharedKmsKey.keyArn,
        description: 'Shared KMS key ARN'
      });
    }

    // Module-specific outputs will be added dynamically by modules
    const enabledModules = this.moduleLoader.getEnabledModules();
    new cdk.CfnOutput(this, 'EnabledModules', {
      value: enabledModules.map(m => m.module.moduleId).join(', ') || 'none',
      description: 'Enabled integration modules'
    });
  }
}