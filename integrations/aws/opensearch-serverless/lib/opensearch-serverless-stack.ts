/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 *
 * OpenSearch Serverless Stack
 *
 * This stack deploys an OpenSearch Serverless collection for Security Lake data visualization.
 */

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { CfnCollection, CfnSecurityPolicy, CfnAccessPolicy } from 'aws-cdk-lib/aws-opensearchserverless';
import { CfnApplication } from 'aws-cdk-lib/aws-opensearchservice';
import { CfnPipeline } from 'aws-cdk-lib/aws-osis';
import { Key, IKey } from 'aws-cdk-lib/aws-kms';
import { Stream, StreamMode, StreamEncryption } from 'aws-cdk-lib/aws-kinesis';
import { Bucket, BucketEncryption, BlockPublicAccess } from 'aws-cdk-lib/aws-s3';
import { Duration, CfnOutput, Stack, RemovalPolicy } from 'aws-cdk-lib';
import { Role, ServicePrincipal, PolicyStatement, Effect, CfnRole } from 'aws-cdk-lib/aws-iam';
import { LogGroup, RetentionDays } from 'aws-cdk-lib/aws-logs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { ProjectConfig } from './core/config-loader';
import { SavedObjectsImporter } from './constructs/saved-objects-importer';
import { WorkspaceCreator } from './constructs/workspace-creator';
import * as yaml from 'yaml';

export class OpenSearchServerlessStack extends cdk.Stack {
  /**
   * The SavedObjectsImporter construct (if savedObjects is configured).
   * Used to import dashboards, visualizations, and index patterns to OpenSearch.
   */
  public readonly savedObjectsImporter?: SavedObjectsImporter;

  /**
   * The WorkspaceCreator construct (if workspaces is configured).
   * Used to create OpenSearch Dashboards workspaces via the Workspace API.
   */
  public readonly workspaceCreator?: WorkspaceCreator;

  /**
   * Generate OpenSearch Ingestion pipeline configuration
   * Processes CloudWatch Logs from Kinesis and writes to OpenSearch Serverless
   *
   * Pipeline Structure:
   * - Source: Kinesis Data Stream with polling consumer strategy
   *   - Codec handles gzip decompression automatically
   *   - Extracts logEvents array and includes owner, logGroup, logStream fields
   * - Processor: 11-step transformation chain for CloudWatch Logs:
   *   1. Parse logEvents JSON array
   *   2. Rename logGroup to log_group
   *   3. Replace '/' with '-' in log_group (sanitize for index names)
   *   4. Remove leading '-' from log_group (ensure valid index names)
   *   5. Convert log_group to lowercase
   *   6. Rename logStream to log_stream
   *   7. Format timestamp to ISO 8601
   *   8. Extract log_group_type via grok pattern (optional)
   *   9. Extract metrics from message via grok patterns (optional)
   *   10. Normalize event_type to lowercase
   *   11. Replace spaces with underscores in event_type
   * - Sinks:
   *   1. OpenSearch Serverless (primary) with dynamic index naming
   *   2. S3 DLQ for OpenSearch failures
   *   3. S3 backup for all records
   *
   * Dynamic Index Naming Pattern: ${log_group}-log_data-%{yyyy.MM.dd}
   * log_group is sanitized to ensure valid index names (no leading special chars)
   * This creates daily indices per log group for efficient querying and lifecycle management
   */
  private generatePipelineConfig(
    kinesisStreamArn: string,
    collectionEndpoint: string,
    collectionName: string,
    s3BucketName: string,
    pipelineRoleArn: string,
    logGroupPattern: string = '.*'
  ): string {
    const config = {
      version: '2',
      'log-pipeline': {
        source: {
          kinesis_data_streams: {
            streams: [
              {
                stream_arn: kinesisStreamArn,
                initial_position: 'LATEST',
                compression: 'gzip',
              },
            ],
            consumer_strategy: 'polling',
            polling: {
              max_polling_records: 1000,
              idle_time_between_reads: '1s',
            },
            codec: {
              json: {
                key_name: 'logEvents',
                include_keys: ['owner', 'logGroup', 'logStream'],
              },
            },
            aws: {
              sts_role_arn: pipelineRoleArn,
              region: Stack.of(this).region,
            },
          },
        },
        processor: [
          // Step 1: Parse logEvents JSON array
          {
            parse_json: {
              source: 'logEvents',
            },
          },
          // Step 2: Rename logGroup to log_group
          {
            rename_keys: {
              entries: [
                {
                  from_key: 'logGroup',
                  to_key: 'log_group',
                },
              ],
            },
          },
          // Step 3: Replace '/' with '-' in log_group
          {
            substitute_string: {
              entries: [
                {
                  source: 'log_group',
                  from: '/',
                  to: '-',
                },
              ],
            },
          },
          // Step 4: Remove leading '-' from log_group
          {
            substitute_string: {
              entries: [
                {
                  source: 'log_group',
                  from: '^-',
                  to: '',
                },
              ],
            },
          },
          // Step 5: Convert log_group to lowercase
          {
            lowercase_string: {
              with_keys: ['log_group'],
            },
          },
          // Step 6: Rename logStream to log_stream
          {
            rename_keys: {
              entries: [
                {
                  from_key: 'logStream',
                  to_key: 'log_stream',
                },
              ],
            },
          },
          // Step 7: Format timestamp
          {
            date: {
              match: [
                {
                  key: '/timestamp',
                  patterns: ['epoch_milli'],
                },
              ],
              destination: '/timestamp',
              output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
            },
          },
          // Step 8: Extract log_group_type (optional pattern matching)
          {
            grok: {
              match: {
                log_group: ['%{GREEDYDATA}-%{DATA:log_group_type}-%{WORD}$'],
              },
            },
          },
          // Step 9: Extract metrics from message (optional)
          {
            grok: {
              match: {
                message: [
                  'Received %{NUMBER:events_received:int} events from Event Hub',
                  'Pub/Sub processing completed: %{NUMBER:events_received:int} events processed',
                  'Successfully sent %{NUMBER:events_sent:int} %{DATA:event_type} events to Security Lake as Parquet',
                  'Batch processing complete: %{NUMBER:security_hub_success:int} success, %{NUMBER:security_hub_failed:int} failed',
                  'Successfully wrote %{NUMBER:flow_log_events:int} records to Security Lake',
                ],
              },
            },
          },
          // Step 10: Normalize event_type field
          {
            lowercase_string: {
              with_keys: ['event_type'],
            },
          },
          // Step 11: Replace spaces with underscores in event_type
          {
            substitute_string: {
              entries: [
                {
                  source: 'event_type',
                  from: ' ',
                  to: '_',
                },
              ],
            },
          },
        ],
        sink: [
          // Primary sink: OpenSearch Serverless
          // Dynamic index naming creates daily indices per log group
          // Format: ${log_group}-log_data-YYYY.MM.DD
          {
            opensearch: {
              hosts: [collectionEndpoint],
              index: '${log_group}-log_data-%{yyyy.MM.dd}',
              aws: {
                sts_role_arn: pipelineRoleArn,
                region: Stack.of(this).region,
                serverless: true,
                serverless_options: {
                  network_policy_name: `network-${collectionName}`,
                },
              },
              dlq: {
                s3: {
                  bucket: s3BucketName,
                  key_path_prefix: 'dlq/opensearch-failures/',
                  region: Stack.of(this).region,
                  sts_role_arn: pipelineRoleArn,
                },
              },
            },
          },
          // Backup sink: S3 for all records
          // Partitioned by date for efficient querying and lifecycle management
          // Records buffered with configurable thresholds before writing
          {
            s3: {
              bucket: s3BucketName,
              object_key: {
                path_prefix: 'backup/logs/%{yyyy}/%{MM}/%{dd}/',
              },
              threshold: {
                event_count: 1000,
                maximum_size: '50mb',
                event_collect_timeout: '60s',
              },
              codec: {
                ndjson: {},
              },
              aws: {
                sts_role_arn: pipelineRoleArn,
                region: Stack.of(this).region,
              },
            },
          },
        ],
      },
    };
    
    return yaml.stringify(config);
  }

  /**
   * Generate Security Lake OpenSearch Ingestion pipeline configuration
   * Processes OCSF Parquet data from Security Lake S3 buckets via SQS notifications
   */
  private generateSecurityLakePipelineConfig(
    queueUrl: string,
    collectionEndpoint: string,
    s3BucketName: string,
    pipelineRoleArn: string,
    networkPolicyName: string
  ): string {
    const config = {
      version: '2',
      'collection-pipeline': {
        source: {
          s3: {
            acknowledgments: true,
            sqs: {
              queue_url: queueUrl,
              visibility_timeout: '60s',
              visibility_duplication_protection: true,
            },
            aws: {
              region: Stack.of(this).region,
              sts_role_arn: pipelineRoleArn,
            },
            notification_type: 'sqs',
            notification_source: 'eventbridge',
            codec: {
              parquet: {},
            },
            compression: 'none',
            workers: '1',
          },
        },
        processor: [
          // USE USER-PROVIDED PROCESSOR CHAIN EXACTLY
          { lowercase_string: { with_keys: ['/metadata/product/name', '/class_name'] } },
          { add_entries: { entries: [{ key: '/index_name', value_expression: '/metadata/product/name' }] } },
          { substitute_string: { entries: [{ source: '/index_name', from: '[\\[\\]\\"*\\\\<|,>/?\\s]', to: '_' }] } },
          { trim_string: { with_keys: ['/cloud/provider'] } },
          {
            grok: {
              grok_when: '/class_uid == 4002 and /metadata/product/name == "AWS WAF"',
              match: {
                '/metadata/product/feature/uid': [
                  '%{DATA}:%{DATA}:%{DATA}:%{DATA:/cloud/region}:%{DATA:/cloud/account/uid}:%{GREEDYDATA}',
                ],
              },
            },
          },
          { delete_entries: { with_keys: ['/cloud/account'], delete_when: '/metadata/product/name == "Amazon EKS"' } },
          {
            grok: {
              grok_when: '/class_uid == 6003 and /metadata/product/name == "Amazon EKS"',
              match: {
                '/s3/key': [
                  '%{DATA}/%{DATA}/%{DATA}/%{DATA}=%{DATA:/cloud/region}/%{DATA}=%{DATA:/cloud/account/uid}/%{DATA}/%{GREEDYDATA}',
                ],
              },
            },
          },
          { delete_entries: { with_keys: ['uid', 's3'] } },
          // Date conversions for OCSF timestamps
          { date: { match: [{ key: '/time', patterns: ['epoch_milli'] }], destination: '/time', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/metadata/logged_time', patterns: ['epoch_milli'] }], destination: '/metadata/logged_time', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/metadata/modified_time', patterns: ['epoch_milli'] }], destination: '/metadata/modified_time', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/start_time', patterns: ['epoch_milli'] }], destination: '/start_time', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/time_dt', patterns: ['epoch_milli'] }], destination: '/time_dt', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/end_time_dt', patterns: ['epoch_milli'] }], destination: '/end_time_dt', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/start_time_dt', patterns: ['epoch_milli'] }], destination: '/start_time_dt', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/end_time', patterns: ['epoch_milli'] }], destination: '/end_time', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/finding_info/created_time_dt', patterns: ['epoch_milli'] }], destination: '/finding_info/created_time_dt', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/finding_info/first_seen_time_dt', patterns: ['epoch_milli'] }], destination: '/finding_info/first_seen_time_dt', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/finding_info/modified_time_dt', patterns: ['epoch_milli'] }], destination: '/finding_info/modified_time_dt', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/finding_info/last_seen_time_dt', patterns: ['epoch_milli'] }], destination: '/finding_info/last_seen_time_dt', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { date: { match: [{ key: '/metadata/processed_time_dt', patterns: ['epoch_milli'] }], destination: '/metadata/processed_time_dt', output_format: "yyyy-MM-dd'T'HH:mm:ss.SSSXXX" } },
          { lowercase_string: { with_keys: ['/class_name'] } },
          {
            substitute_string: {
              entries: [
                { source: '/class_name', from: '\\s', to: '_' },
                { source: '/src_endpoint/ip', from: '-', to: '0.0.0.0' },
                { source: '/dst_endpoint/ip', from: '-', to: '0.0.0.0' },
              ],
            },
          },
        ],
        sink: [
          // Primary sink: OpenSearch Serverless
          {
            opensearch: {
              hosts: [collectionEndpoint],
              aws: {
                serverless: true,
                region: Stack.of(this).region,
                sts_role_arn: pipelineRoleArn,
                serverless_options: {
                  network_policy_name: networkPolicyName,
                },
              },
              index_type: 'custom',
              index: '${/index_name}-${/class_name}-ocsf-cuid-${/class_uid}-%{yyyy.MM.dd}',
              dlq: {
                s3: {
                  bucket: s3BucketName,
                  key_path_prefix: 'dlq/security-lake-failures/',
                  region: Stack.of(this).region,
                  sts_role_arn: pipelineRoleArn,
                },
              },
            },
          },
          // Backup sink: S3
          {
            s3: {
              bucket: s3BucketName,
              object_key: {
                path_prefix: 'backup/security-lake/%{yyyy}/%{MM}/%{dd}/',
              },
              threshold: {
                event_count: 1000,
                maximum_size: '50mb',
                event_collect_timeout: '60s',
              },
              codec: {
                ndjson: {},
              },
              aws: {
                sts_role_arn: pipelineRoleArn,
                region: Stack.of(this).region,
              },
            },
          },
        ],
      },
    };

    return yaml.stringify(config);
  }

  constructor(scope: Construct, id: string, props: cdk.StackProps, config: ProjectConfig) {
    super(scope, id, props);

    // Validate required configuration
    if (!config.collection?.name) {
      throw new Error('Collection name is required in configuration');
    }
    if (!config.dataAccess?.principals || config.dataAccess.principals.length === 0) {
      throw new Error('At least one IAM principal is required in dataAccess.principals');
    }

    const collectionName = config.collection.name;

    // Declare variables at wider scope for use across multiple sections
    // These are needed by the data access policy and pipeline role
    let kinesisStream: Stream | undefined;
    let kinesisEncryptionKey: IKey | undefined;
    let dlqBucket: Bucket | undefined;
    let pipelineRole: Role | undefined;

    // ========================================
    // 1. KMS Key (Optional)
    // ========================================
    // Create KMS key if useSharedKey is true and no existing key ARN provided
    // This follows the three encryption modes pattern:
    // - Mode 1: useSharedKey: true → create new shared KMS key
    // - Mode 2: existingKeyArn provided → use existing CMK
    // - Mode 3: Neither → use AWS-owned key (default)
    let kmsKeyArn: string | undefined;
    let kmsKey: Key | undefined;

    if (config.encryption?.useSharedKey && !config.encryption?.existingKeyArn) {
      kmsKey = new Key(this, 'SharedKmsKey', {
        enableKeyRotation: true,
        description: `Shared KMS key for OpenSearch Serverless collection ${collectionName}`,
        alias: `opensearch-serverless/${collectionName}`,
      });
      kmsKeyArn = kmsKey.keyArn;
    } else if (config.encryption?.existingKeyArn) {
      kmsKeyArn = config.encryption.existingKeyArn;
    }

    // ========================================
    // 2. Encryption Policy
    // ========================================
    // Defines encryption settings for the collection
    // Uses AWS-owned key by default, or custom KMS key if provided
    const encryptionPolicyDocument: any = {
      Rules: [
        {
          Resource: [`collection/${collectionName}`],
          ResourceType: 'collection',
        },
      ],
    };

    // Add encryption configuration based on KMS key availability
    if (kmsKeyArn) {
      encryptionPolicyDocument.AWSOwnedKey = false;
      encryptionPolicyDocument.KmsARN = kmsKeyArn;
    } else {
      encryptionPolicyDocument.AWSOwnedKey = true;
    }

    const encryptionPolicy = new CfnSecurityPolicy(this, 'EncryptionPolicy', {
      name: `encryption-${collectionName}`,
      type: 'encryption',
      policy: JSON.stringify(encryptionPolicyDocument),
      description: `Encryption policy for ${collectionName} collection`,
    });

    // ========================================
    // 3. Network Policy
    // ========================================
    // Defines network access settings for the collection
    // Configured for public access with AllowFromPublic: true
    // Note: Network policy requires array format
    const networkPolicyDocument = [
      {
        Rules: [
          {
            Resource: [`collection/${collectionName}`],
            ResourceType: 'collection',
          },
        ],
        AllowFromPublic: true,
      },
    ];

    const networkPolicy = new CfnSecurityPolicy(this, 'NetworkPolicy', {
      name: `network-${collectionName}`,
      type: 'network',
      policy: JSON.stringify(networkPolicyDocument),
      description: `Network policy for ${collectionName} collection`,
    });

    // ========================================
    // 4. OpenSearch Serverless Collection
    // ========================================
    // Creates the TIMESERIES collection with standby replicas enabled
    // Collection depends on encryption and network policies being created first
    const collection = new CfnCollection(this, 'Collection', {
      name: collectionName,
      type: config.collection.type || 'TIMESERIES',
      description: config.collection.description || `OpenSearch Serverless collection for ${config.projectName}`,
      standbyReplicas: config.collection.standbyReplicas || 'ENABLED',
      tags: [
        {
          key: 'Source',
          value: config.tagSource,
        },
        {
          key: 'Product',
          value: config.tagProduct,
        },
        {
          key: 'KitVersion',
          value: config.tagKitVersion,
        },
        {
          key: 'Environment',
          value: config.environment,
        },
        {
          key: 'Project',
          value: config.projectName,
        },
        // Add custom tags if provided
        ...(config.tags || []).map((tag) => ({
          key: tag.key,
          value: tag.value,
        })),
      ],
    });

    // Ensure policies are created before the collection
    collection.addDependency(encryptionPolicy);
    collection.addDependency(networkPolicy);

    // ========================================
    // 4a. Saved Objects Importer (Optional) - Deferred to Section 10b
    // ========================================
    // SavedObjectsImporter creation is deferred to Section 10b (after WorkspaceCreator)
    // because it needs the workspace ID to construct the workspace-specific URL.
    // If workspaces are configured, saved objects will be imported to the workspace.
    // If no workspaces are configured, saved objects are imported to the global context.
    //
    // The Lambda function's role will be added to the data access policy below,
    // so we pre-create a placeholder reference that gets set later.
    // See Section 10b for SavedObjectsImporter instantiation.

    // ========================================
    // 5. Kinesis Data Stream (Optional)
    // ========================================
    // Create Kinesis Data Stream if configured
    // This stream receives data from CloudWatch Logs subscriptions
    // and forwards it to OpenSearch Serverless for visualization
    if (config.kinesis) {
      // Determine encryption key for Kinesis stream
      // Encryption priority order:
      // 1. Kinesis-specific existingKeyArn (highest priority)
      // 2. Kinesis-specific useSharedKey (use shared KMS key created above)
      // 3. Global existingKeyArn from encryption config
      // 4. Global useSharedKey from encryption config
      // 5. No encryption (if enabled: false or no config)

      if (config.kinesis.encryption?.enabled !== false) {
        if (config.kinesis.encryption?.existingKeyArn) {
          // Priority 1: Use Kinesis-specific existing key
          kinesisEncryptionKey = Key.fromKeyArn(
            this,
            'KinesisExistingKey',
            config.kinesis.encryption.existingKeyArn
          );
        } else if (config.kinesis.encryption?.useSharedKey && kmsKey) {
          // Priority 2: Share the key created for OpenSearch
          kinesisEncryptionKey = kmsKey;
        } else if (config.encryption?.existingKeyArn && !config.kinesis.encryption) {
          // Priority 3: Inherit global encryption key
          kinesisEncryptionKey = Key.fromKeyArn(
            this,
            'KinesisSharedKey',
            config.encryption.existingKeyArn
          );
        } else if (config.encryption?.useSharedKey && kmsKey) {
          // Priority 4: Use the shared KMS key created for OpenSearch
          kinesisEncryptionKey = kmsKey;
        }
        // If none of the above, kinesisEncryptionKey remains undefined (no encryption)
      }

      // Create Kinesis Data Stream
      // Stream mode: ON_DEMAND for auto-scaling (recommended) or PROVISIONED for fixed capacity
      // Retention: Default 24 hours, configurable up to 8760 hours (365 days)
      // Encryption: Uses KMS key determined above, or unencrypted if no key specified
      kinesisStream = new Stream(this, 'KinesisStream', {
        streamName: config.kinesis.streamName,
        streamMode: config.kinesis.streamMode === 'PROVISIONED' 
          ? StreamMode.PROVISIONED 
          : StreamMode.ON_DEMAND,
        shardCount: config.kinesis.streamMode === 'PROVISIONED' ? config.kinesis.shardCount : undefined,
        retentionPeriod: Duration.hours(config.kinesis.retentionPeriodHours || 24),
        encryption: kinesisEncryptionKey 
          ? StreamEncryption.KMS 
          : StreamEncryption.UNENCRYPTED,
        encryptionKey: kinesisEncryptionKey,
      });

      // Add stack outputs for Kinesis Data Stream
      new CfnOutput(this, 'KinesisStreamName', {
        value: kinesisStream.streamName,
        description: 'Kinesis Data Stream name',
        exportName: `${this.stackName}-KinesisStreamName`,
      });

      new CfnOutput(this, 'KinesisStreamArn', {
        value: kinesisStream.streamArn,
        description: 'Kinesis Data Stream ARN',
        exportName: `${this.stackName}-KinesisStreamArn`,
      });

      // ========================================
      // Create IAM Role for CloudWatch Logs Subscription Filter
      // ========================================
      // This role allows CloudWatch Logs service to write log data to the Kinesis Data Stream.
      // The role is required when creating CloudWatch Logs subscription filters that forward
      // logs to Kinesis.
      //
      // Trust Policy:
      // - Principal: logs.<region>.amazonaws.com service
      // - Conditions: Restricted to source account and region-specific log ARNs
      //
      // Permissions:
      // - kinesis:PutRecord: Write individual records to stream
      // - kinesis:PutRecords: Write multiple records in batch (more efficient)
      //
      // Usage Example:
      // aws logs put-subscription-filter \
      //   --log-group-name /aws/lambda/my-function \
      //   --filter-name kinesis-subscription \
      //   --filter-pattern "" \
      //   --destination-arn <kinesis-stream-arn> \
      //   --role-arn <cloudwatch-logs-role-arn>
      const cloudWatchLogsRole = new Role(this, 'CloudWatchLogsKinesisRole', {
        assumedBy: new ServicePrincipal(`logs.${Stack.of(this).region}.amazonaws.com`),
        description: 'Role for CloudWatch Logs to write to Kinesis Data Stream',
        roleName: `${config.projectName}-CloudWatchLogsKinesisRole`,
      });

      // Grant write permissions to the Kinesis stream
      // This automatically adds kinesis:PutRecord and kinesis:PutRecords permissions
      kinesisStream.grantWrite(cloudWatchLogsRole);

      // Export the role ARN for use when creating subscription filters
      new CfnOutput(this, 'CloudWatchLogsRoleArn', {
        value: cloudWatchLogsRole.roleArn,
        description: 'IAM role ARN for CloudWatch Logs subscription filters',
        exportName: `${this.stackName}-CloudWatchLogsRoleArn`,
      });
    }

    // ========================================
    // 6. S3 DLQ Bucket for OpenSearch Ingestion Pipeline (Optional)
    // ========================================
    // Create S3 bucket for Dead Letter Queue (DLQ) if pipeline is configured
    // This bucket stores failed records from the OpenSearch Ingestion pipeline
    // Only created when pipeline.enabled is true and dlqBucket.enabled is not explicitly false
    if (config.pipeline?.enabled && config.pipeline?.dlqBucket?.enabled !== false) {
      // Determine encryption key for S3 bucket
      // Encryption priority order (same as Kinesis):
      // 1. Bucket-specific existingKeyArn (highest priority)
      // 2. Bucket-specific useSharedKey (use shared KMS key created above)
      // 3. Global existingKeyArn from encryption config
      // 4. Global useSharedKey from encryption config
      // 5. S3-managed encryption (default if no KMS specified)
      let s3EncryptionKey: IKey | undefined;
      
      if (config.pipeline.dlqBucket?.encryption?.existingKeyArn) {
        // Priority 1: Use bucket-specific existing key
        s3EncryptionKey = Key.fromKeyArn(
          this,
          'S3DlqExistingKey',
          config.pipeline.dlqBucket.encryption.existingKeyArn
        );
      } else if (config.pipeline.dlqBucket?.encryption?.useSharedKey && kmsKey) {
        // Priority 2: Share the key created for OpenSearch/Kinesis
        s3EncryptionKey = kmsKey;
      } else if (config.encryption?.existingKeyArn && !config.pipeline.dlqBucket?.encryption) {
        // Priority 3: Inherit global encryption key
        s3EncryptionKey = Key.fromKeyArn(
          this,
          'S3DlqSharedKey',
          config.encryption.existingKeyArn
        );
      } else if (config.encryption?.useSharedKey && kmsKey) {
        // Priority 4: Use the shared KMS key created for OpenSearch
        s3EncryptionKey = kmsKey;
      }
      // If none of the above, s3EncryptionKey remains undefined (S3-managed encryption)

      // Create S3 bucket for DLQ
      // Security best practices applied:
      // - BlockPublicAccess.BLOCK_ALL: Prevent any public access to bucket contents
      // - enforceSSL: Require HTTPS for all S3 operations
      // - RemovalPolicy.RETAIN: Prevent accidental deletion of DLQ data during stack deletion
      // - versioned: false: No need for versioning on DLQ records
      // Lifecycle policy automatically deletes objects after retention period (default: 2 days)
      dlqBucket = new Bucket(this, 'DlqBucket', {
        bucketName: config.pipeline.dlqBucket?.bucketName,  // Optional, auto-generated if not provided
        encryption: s3EncryptionKey
          ? BucketEncryption.KMS
          : BucketEncryption.S3_MANAGED,
        encryptionKey: s3EncryptionKey,
        blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
        versioned: false,
        lifecycleRules: [
          {
            id: 'DeleteOldDlqRecords',
            enabled: true,
            expiration: Duration.days(config.pipeline.dlqBucket?.lifecycleRetentionDays || 2),
          },
        ],
        removalPolicy: RemovalPolicy.RETAIN,  // Prevent accidental deletion
        enforceSSL: true,  // Require SSL for all S3 operations
      });

      // Add stack outputs for S3 DLQ bucket
      // These outputs allow the OpenSearch Ingestion pipeline role to reference the bucket
      // Note: OSI pipeline role will need PutObject permission on this bucket
      new CfnOutput(this, 'DlqBucketName', {
        value: dlqBucket.bucketName,
        description: 'S3 bucket name for OpenSearch Ingestion DLQ',
        exportName: `${this.stackName}-DlqBucketName`,
      });

      new CfnOutput(this, 'DlqBucketArn', {
        value: dlqBucket.bucketArn,
        description: 'S3 bucket ARN for OpenSearch Ingestion DLQ',
        exportName: `${this.stackName}-DlqBucketArn`,
      });
    }

    // ========================================
    // 7. IAM Role for OpenSearch Ingestion Pipeline (Optional)
    // ========================================
    // Create IAM role for OpenSearch Ingestion (OSI) pipeline if configured
    // This role enables the pipeline to:
    // - Read from Kinesis Data Stream (enhanced fan-out consumer)
    // - Write to OpenSearch Serverless collection
    // - Write failed records to S3 DLQ bucket
    // Only created when pipeline.enabled is true
    if (config.pipeline?.enabled) {
      // Create IAM role with trust policy for OSI service
      // Trust policy conditions restrict the role to:
      // - The current AWS account (prevents cross-account assumption)
      // - Pipeline resources in the current region (ARN pattern matching)
      pipelineRole = new Role(this, 'PipelineRole', {
        assumedBy: new ServicePrincipal('osis-pipelines.amazonaws.com', {
          conditions: {
            StringEquals: {
              'aws:SourceAccount': Stack.of(this).account,
            },
            ArnLike: {
              'aws:SourceArn': `arn:aws:osis:${Stack.of(this).region}:${Stack.of(this).account}:pipeline/*`,
            },
          },
        }),
        description: 'IAM role for OpenSearch Ingestion pipeline to access Kinesis, OpenSearch, and S3',
        roleName: `${config.projectName}-OSIPipelineRole`,
      });

      // Grant Kinesis read permissions for polling consumer
      // Polling strategy uses GetRecords API and does not require consumer registration
      // Requires 10 specific actions for full Kinesis access (permissions retained for compatibility):
      // - Stream operations: DescribeStream, GetRecords, GetShardIterator, ListShards
      // - Enhanced fan-out: SubscribeToShard (push model for streaming)
      // - Consumer management: Register/Deregister/Describe/List stream consumers
      if (kinesisStream) {
        pipelineRole.addToPolicy(
          new PolicyStatement({
            effect: Effect.ALLOW,
            actions: [
              'kinesis:DescribeStream',
              'kinesis:GetRecords',
              'kinesis:GetShardIterator',
              'kinesis:ListShards',
              'kinesis:SubscribeToShard',
              'kinesis:DescribeStreamSummary',
              'kinesis:RegisterStreamConsumer',
              'kinesis:DeregisterStreamConsumer',
              'kinesis:DescribeStreamConsumer',
              'kinesis:ListStreamConsumers',
            ],
            resources: [
              kinesisStream.streamArn,
              `${kinesisStream.streamArn}/*`,  // Covers stream consumers
            ],
          })
        );

        // Grant KMS decrypt permission if Kinesis stream is encrypted
        // Required to read encrypted records from the stream
        if (kinesisEncryptionKey) {
          kinesisEncryptionKey.grantDecrypt(pipelineRole);
        }
      }

      // Grant OpenSearch Serverless collection access (IAM-level permissions)
      // These permissions allow the pipeline to read collection metadata and access the API
      // The data access policy (added below) grants index-level permissions separately
      pipelineRole.addToPolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'aoss:BatchGetCollection',
            'aoss:APIAccessAll',
          ],
          resources: [collection.attrArn],
        })
      );

      // Grant OpenSearch Serverless security policy permissions
      // Security policies are account-level resources requiring wildcard access
      pipelineRole.addToPolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'aoss:GetSecurityPolicy',
            'aoss:ListSecurityPolicies',
            'aoss:UpdateSecurityPolicy',
          ],
          resources: ['*'],  // Security policies require wildcard resource
        })
      );

      // Grant OpenSearch Serverless collection access
      // The pipeline role ARN will be added to the data access policy below
      // This dependency ensures the role exists before the collection is fully configured
      collection.addDependency(pipelineRole.node.defaultChild as CfnRole);

      // Grant S3 DLQ write permissions
      // grantWrite() includes both PutObject and PutObjectAcl permissions
      // This allows the pipeline to write failed records to the DLQ bucket
      if (dlqBucket) {
        dlqBucket.grantWrite(pipelineRole);
      }

      // Export pipeline role ARN for use when creating the OSI pipeline
      // This ARN is required in the pipeline configuration
      new CfnOutput(this, 'PipelineRoleArn', {
        value: pipelineRole.roleArn,
        description: 'IAM role ARN for OpenSearch Ingestion pipeline',
        exportName: `${this.stackName}-PipelineRoleArn`,
      });
    }

    // Security Lake Pipeline IAM Role (if configured)
    let securityLakePipelineRole: Role | undefined;
    if (config.securityLakePipeline?.queueUrl) {
      securityLakePipelineRole = new Role(this, 'SecurityLakePipelineRole', {
        assumedBy: new ServicePrincipal('osis-pipelines.amazonaws.com', {
          conditions: {
            StringEquals: {
              'aws:SourceAccount': Stack.of(this).account,
            },
            ArnLike: {
              'aws:SourceArn': `arn:aws:osis:${Stack.of(this).region}:${Stack.of(this).account}:pipeline/*`,
            },
          },
        }),
        description: 'IAM role for Security Lake OpenSearch Ingestion pipeline',
        roleName: `${config.projectName}-SecurityLakePipelineRole`,
      });

      // Grant SQS permissions to read from Security Lake queue
      // Parse queue URL to extract queue name for proper ARN construction
      const queueUrlParts = config.securityLakePipeline.queueUrl.split('/');
      const queueName = queueUrlParts[queueUrlParts.length - 1];
      const queueArn = `arn:aws:sqs:${Stack.of(this).region}:${Stack.of(this).account}:${queueName}`;
      
      securityLakePipelineRole.addToPolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'sqs:ReceiveMessage',
            'sqs:DeleteMessage',
            'sqs:GetQueueAttributes',
            'sqs:ChangeMessageVisibility',
          ],
          resources: [queueArn],
        })
      );

      // Grant S3 permissions to read Security Lake data
      // Use wildcard for resources to avoid IAM legacy parser issues with bucket name wildcards
      securityLakePipelineRole.addToPolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            's3:GetObject',
            's3:ListBucket',
          ],
          resources: ['*'],
        })
      );

      // Grant OpenSearch Serverless collection access
      securityLakePipelineRole.addToPolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'aoss:BatchGetCollection',
            'aoss:APIAccessAll',
          ],
          resources: [collection.attrArn],
        })
      );

      securityLakePipelineRole.addToPolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'aoss:GetSecurityPolicy',
            'aoss:ListSecurityPolicies',
            'aoss:UpdateSecurityPolicy',
          ],
          resources: ['*'],
        })
      );

      // Grant S3 DLQ write permissions (reuse existing bucket)
      if (dlqBucket) {
        dlqBucket.grantWrite(securityLakePipelineRole);
      }

      // Add to data access policy principals
      collection.addDependency(securityLakePipelineRole.node.defaultChild as CfnRole);

      // Add stack output
      new CfnOutput(this, 'SecurityLakePipelineRoleArn', {
        value: securityLakePipelineRole.roleArn,
        description: 'IAM role ARN for Security Lake OSI pipeline',
        exportName: `${this.stackName}-SecurityLakePipelineRoleArn`,
      });
    }

    // ========================================
    // 8. Data Access Policy
    // ========================================
    // Defines IAM principals and their permissions for collection and index operations
    // Must be created AFTER the collection exists AND after the pipeline role (if configured)
    // Permissions include both collection-level and index-level operations
    // The pipeline role (if configured) is automatically added to the principals list
    const dataAccessPrincipals = [...config.dataAccess.principals];

    // Add pipeline role to data access if configured
    // This grants the OSI pipeline full access to the OpenSearch Serverless collection
    // including the ability to create indices and write documents
    if (config.pipeline?.enabled && pipelineRole) {
      dataAccessPrincipals.push(pipelineRole.roleArn);
    }

    // Add Security Lake pipeline role if configured
    if (config.securityLakePipeline?.queueUrl && securityLakePipelineRole) {
      dataAccessPrincipals.push(securityLakePipelineRole.roleArn);
    }

    // Add SavedObjectsImporter Lambda role if configured
    // This grants the importer Lambda access to the OpenSearch Dashboards API
    // for importing saved objects (dashboards, visualizations, index patterns)
    if (this.savedObjectsImporter?.lambdaFunction.role) {
      dataAccessPrincipals.push(this.savedObjectsImporter.lambdaFunction.role.roleArn);
    }

    // ========================================
    // 4b. Workspace Creator (Optional) - Deferred to Section 10
    // ========================================
    // WorkspaceCreator instantiation is moved to after the Application is created
    // (Section 10) because it needs the application endpoint URL which is derived
    // from the CfnApplication.attrId. If no application is configured, it falls
    // back to using the collection dashboard endpoint.
    // See Section 10 for WorkspaceCreator instantiation.

    // Add WorkspaceCreator Lambda role if configured
    // This grants the workspace creator Lambda access to the OpenSearch Dashboards API
    // for creating and managing workspaces
    if (this.workspaceCreator?.lambdaFunction.role) {
      dataAccessPrincipals.push(this.workspaceCreator.lambdaFunction.role.roleArn);
    }

    const dataAccessPolicyDocument = [
      {
        Rules: [
          // Collection-level permissions
          {
            Resource: [`collection/${collectionName}`],
            Permission: [
              'aoss:CreateCollectionItems',
              'aoss:DeleteCollectionItems',
              'aoss:UpdateCollectionItems',
              'aoss:DescribeCollectionItems',
            ],
            ResourceType: 'collection',
          },
          // Index-level permissions for all indices in the collection
          {
            Resource: [`index/${collectionName}/*`],
            Permission: [
              'aoss:CreateIndex',
              'aoss:DeleteIndex',
              'aoss:UpdateIndex',
              'aoss:DescribeIndex',
              'aoss:ReadDocument',
              'aoss:WriteDocument',
            ],
            ResourceType: 'index',
          },
        ],
        Principal: dataAccessPrincipals,
      },
    ];

    const dataAccessPolicy = new CfnAccessPolicy(this, 'DataAccessPolicy', {
      name: `data-${collectionName}`,
      type: 'data',
      policy: JSON.stringify(dataAccessPolicyDocument),
      description: `Data access policy for ${collectionName} collection`,
    });

    // Ensure data access policy is created after the collection
    dataAccessPolicy.addDependency(collection);
    
    // Ensure data access policy is created after pipeline role (if configured)
    // This is critical because the policy references the pipeline role ARN
    if (config.pipeline?.enabled && pipelineRole) {
      dataAccessPolicy.node.addDependency(pipelineRole.node.defaultChild as CfnRole);
    }

    // Ensure data access policy is created after Security Lake pipeline role (if configured)
    if (config.securityLakePipeline?.queueUrl && securityLakePipelineRole) {
      dataAccessPolicy.node.addDependency(securityLakePipelineRole.node.defaultChild as CfnRole);
    }

    // Ensure data access policy is created after SavedObjectsImporter Lambda role (if configured)
    // This is critical because the policy references the Lambda role ARN
    if (this.savedObjectsImporter?.lambdaFunction.role) {
      dataAccessPolicy.node.addDependency(this.savedObjectsImporter.lambdaFunction);
    }

    // Ensure data access policy is created after WorkspaceCreator Lambda role (if configured)
    // This is critical because the policy references the Lambda role ARN
    if (this.workspaceCreator?.lambdaFunction.role) {
      dataAccessPolicy.node.addDependency(this.workspaceCreator.lambdaFunction);
    }

    // Ensure SavedObjectsImporter import custom resources wait for data access policy
    // This is critical because the Lambda needs data access permissions before it can
    // import saved objects to OpenSearch Serverless. Without this dependency, the custom
    // resource may execute before the data access policy grants the Lambda role permissions.
    //
    // IMPORTANT: We add dependency only on the import custom resources, NOT the entire
    // SavedObjectsImporter construct. Adding dependency on the whole construct would create
    // a circular dependency because:
    // - DataAccessPolicy references the Lambda role (line 989)
    // - DataAccessPolicy depends on the Lambda function (line 1048)
    // - If SavedObjectsImporter depends on DataAccessPolicy, and Lambda is inside
    //   SavedObjectsImporter, we get: DataAccessPolicy -> Lambda -> SavedObjectsImporter -> DataAccessPolicy
    //
    // By targeting only the import custom resources (which are separate from the Lambda),
    // we break this cycle while ensuring imports execute after the policy is deployed.
    if (this.savedObjectsImporter) {
      for (const importResource of this.savedObjectsImporter.importCustomResources) {
        importResource.node.addDependency(dataAccessPolicy);
      }
    }

    // Ensure WorkspaceCreator custom resources wait for data access policy
    // This is critical because the Lambda needs data access permissions before it can
    // create workspaces via the OpenSearch Serverless API. Without this dependency, the
    // custom resource may execute before the data access policy grants the Lambda role permissions.
    if (this.workspaceCreator) {
      for (const workspaceResource of this.workspaceCreator.workspaceCustomResources) {
        workspaceResource.node.addDependency(dataAccessPolicy);
      }
    }

    // ========================================
    // 9. OpenSearch Ingestion Pipeline (Optional - continued from section 7)
    // ========================================
    if (config.pipeline?.enabled) {
      // ========================================
      // Create CloudWatch Logs log group for pipeline monitoring
      // ========================================
      // The OSI pipeline publishes operational logs to this log group
      // This must be created before the pipeline to avoid deployment failures
      const pipelineLogGroup = new LogGroup(this, 'PipelineLogGroup', {
        logGroupName: `/aws/vendedlogs/OpenSearchIngestion/${config.pipeline.pipelineName || `${config.projectName}-pipeline`}`,
        retention: RetentionDays.ONE_WEEK,
        removalPolicy: RemovalPolicy.DESTROY,
      });

      // ========================================
      // Create OpenSearch Ingestion Pipeline
      // ========================================
      // OpenSearch Ingestion (OSI) pipeline that:
      // 1. Reads CloudWatch Logs data from Kinesis Data Stream
      // 2. Processes logs through a 10-step transformation chain
      // 3. Writes to OpenSearch Serverless collection (primary sink)
      // 4. Writes failed records to S3 DLQ bucket
      // 5. Backs up all records to S3 (backup sink)
      //
      // Capacity Units (OCUs):
      // - Each OCU provides 6GB memory and 2 vCPUs
      // - Min/Max settings enable auto-scaling based on throughput
      // - Typical range: 2-4 OCUs for most workloads
      // - Maximum: 96 OCUs per pipeline
      //
      // CloudWatch Logs Publishing:
      // - Automatically creates log group for pipeline logs
      // - Tracks ingestion metrics, errors, and performance
      // - Essential for monitoring and troubleshooting
      const pipeline = new CfnPipeline(this, 'IngestionPipeline', {
        pipelineName: config.pipeline.pipelineName || `${config.projectName}-pipeline`,
        minUnits: config.pipeline.minCapacity || 2,
        maxUnits: config.pipeline.maxCapacity || 4,
        pipelineConfigurationBody: this.generatePipelineConfig(
          kinesisStream!.streamArn,
          collection.attrCollectionEndpoint,
          collectionName,
          dlqBucket!.bucketName,
          pipelineRole!.roleArn,
          config.pipeline.logGroupPattern
        ),
        logPublishingOptions: {
          isLoggingEnabled: true,
          cloudWatchLogDestination: {
            logGroup: pipelineLogGroup.logGroupName,
          },
        },
        tags: [
          {
            key: 'Project',
            value: config.projectName,
          },
          {
            key: 'Environment',
            value: config.environment,
          },
        ],
      });

      // Ensure pipeline is created after all dependencies
      // This is critical for successful pipeline initialization
      pipeline.node.addDependency(collection);
      pipeline.node.addDependency(kinesisStream!);
      pipeline.node.addDependency(dlqBucket!);
      pipeline.node.addDependency(pipelineRole!);
      pipeline.node.addDependency(pipelineLogGroup);
      pipeline.node.addDependency(dataAccessPolicy);

      // Export pipeline information for monitoring and management
      new CfnOutput(this, 'PipelineName', {
        value: pipeline.pipelineName || '',
        description: 'OpenSearch Ingestion pipeline name',
        exportName: `${this.stackName}-PipelineName`,
      });

      new CfnOutput(this, 'PipelineArn', {
        value: pipeline.attrPipelineArn,
        description: 'OpenSearch Ingestion pipeline ARN',
        exportName: `${this.stackName}-PipelineArn`,
      });
    }

    // Security Lake Pipeline (if configured)
    if (config.securityLakePipeline?.queueUrl && securityLakePipelineRole) {
      // Generate Security Lake pipeline name with 28-character limit enforcement
      // Default pattern truncates project name to 19 chars and adds '-sl-pipe' suffix (8 chars) = 27 total
      const securityLakePipelineName = config.securityLakePipeline.pipelineName ||
        `${config.projectName.substring(0, 19)}-sl-pipe`;
      
      // Create CloudWatch Logs log group for Security Lake pipeline monitoring
      const securityLakePipelineLogGroup = new LogGroup(this, 'SecurityLakePipelineLogGroup', {
        logGroupName: `/aws/vendedlogs/OpenSearchIngestion/${securityLakePipelineName}`,
        retention: RetentionDays.ONE_WEEK,
        removalPolicy: RemovalPolicy.DESTROY,
      });

      const securityLakePipeline = new CfnPipeline(this, 'SecurityLakeIngestionPipeline', {
        pipelineName: securityLakePipelineName,
        minUnits: config.securityLakePipeline.minCapacity || 2,
        maxUnits: config.securityLakePipeline.maxCapacity || 4,
        pipelineConfigurationBody: this.generateSecurityLakePipelineConfig(
          config.securityLakePipeline.queueUrl,
          collection.attrCollectionEndpoint,
          dlqBucket!.bucketName,
          securityLakePipelineRole.roleArn,
          `network-${collectionName}`
        ),
        logPublishingOptions: {
          isLoggingEnabled: true,
          cloudWatchLogDestination: {
            logGroup: securityLakePipelineLogGroup.logGroupName,
          },
        },
      });

      // Add dependencies
      securityLakePipeline.node.addDependency(collection);
      securityLakePipeline.node.addDependency(dlqBucket!);
      securityLakePipeline.node.addDependency(securityLakePipelineRole);
      securityLakePipeline.node.addDependency(securityLakePipelineLogGroup);
      securityLakePipeline.node.addDependency(dataAccessPolicy);

      // Add stack outputs
      new CfnOutput(this, 'SecurityLakePipelineName', {
        value: securityLakePipeline.pipelineName || '',
        description: 'Security Lake OSI pipeline name',
        exportName: `${this.stackName}-SecurityLakePipelineName`,
      });

      new CfnOutput(this, 'SecurityLakePipelineArn', {
        value: securityLakePipeline.attrPipelineArn,
        description: 'Security Lake OSI pipeline ARN',
        exportName: `${this.stackName}-SecurityLakePipelineArn`,
      });
    }

    // ========================================
    // 10. OpenSearch Application (UI) - Optional
    // ========================================
    // Create OpenSearch Application if configured and enabled
    // The application provides a unified UI for interacting with the collection
    //
    // IMPORTANT: Resource creation order for WorkspaceCreator + Application:
    // 1. Create WorkspaceCreator Lambda function FIRST (if workspaces configured)
    // 2. Add Lambda execution role to CfnApplication admin principals
    // 3. Create CfnApplication with Lambda role as admin
    // 4. Create WorkspaceCreator custom resources (depend on Application)
    //
    // This order is critical because the Lambda needs dashboard admin access
    // to call the workspace API, but the custom resources need the application
    // endpoint URL which is only available after CfnApplication is created.
    let applicationEndpointUrl: string | undefined;
    
    // Pre-create workspace Lambda function if both application and workspaces are configured
    // This allows us to add the Lambda's execution role to the application admins
    let workspaceLambdaRoleArn: string | undefined;
    
    if (config.application?.enabled && config.workspaces && config.workspaces.enabled !== false) {
      // Pre-create the workspace Lambda function to get its execution role ARN
      // This Lambda will be reused by WorkspaceCreator later
      const workspaceLambdaPath = require('path').join(__dirname, '../src/lambda/workspace-creator');
      
      const workspaceLambdaFunction = new lambda.Function(this, 'WorkspaceCreatorFunction', {
        runtime: lambda.Runtime.PYTHON_3_13,
        architecture: lambda.Architecture.ARM_64,
        handler: 'app.handler',
        code: lambda.Code.fromAsset(workspaceLambdaPath, {
          bundling: {
            image: lambda.Runtime.PYTHON_3_13.bundlingImage,
            platform: 'linux/arm64',
            command: [
              'bash', '-c',
              'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
            ],
          },
        }),
        timeout: Duration.minutes(5),
        memorySize: 512,
        environment: {
          // Placeholder endpoint - will be updated by custom resource properties
          OPENSEARCH_ENDPOINT: 'https://placeholder.opensearch.amazonaws.com',
          COLLECTION_ARN: collection.attrArn,
          COLLECTION_ENDPOINT: collection.attrCollectionEndpoint,
          LOG_LEVEL: 'INFO',
        },
        description: `Manage OpenSearch Dashboards workspaces for ${config.projectName}`,
      });
      
      // Grant permissions to Lambda
      workspaceLambdaFunction.addToRolePolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: ['aoss:APIAccessAll'],
          resources: [collection.attrArn],
        })
      );
      
      workspaceLambdaFunction.addToRolePolicy(
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: ['aoss:DashboardsAccessAll'],
          resources: ['*'],
        })
      );
      
      // Store the Lambda role ARN for adding to application admins
      workspaceLambdaRoleArn = workspaceLambdaFunction.role?.roleArn;
      
      // Store the Lambda function for later use by WorkspaceCreator
      // We'll pass it via a different mechanism - by storing on 'this'
      (this as any)._workspaceLambdaFunction = workspaceLambdaFunction;
    }
    
    if (config.application?.enabled) {
      // Build the appConfigs array for dashboard admin configuration
      // IMPORTANT: appConfigs only supports these keys:
      // - opensearchDashboards.dashboardAdmin.users (for IAM user/role principals)
      // - opensearchDashboards.dashboardAdmin.groups (for IAM Identity Center groups)
      // Data sources must be configured via the separate dataSources property
      const appConfigs: CfnApplication.AppConfigProperty[] = [];
      
      // Build data sources array for OpenSearch collections
      // This is separate from appConfigs and uses the dataSources property
      const dataSources: CfnApplication.DataSourceProperty[] = [];
      
      // Add data source configuration if autoAddCollection is enabled (default: true)
      const autoAddCollection = config.application.dataSource?.autoAddCollection !== false;
      if (autoAddCollection) {
        const dataSourceDescription = config.application.dataSource?.description ||
          `Security Lake data collection for ${config.projectName}`;
        dataSources.push({
          dataSourceArn: collection.attrArn,
          dataSourceDescription: dataSourceDescription,
        });
      }
      
      // Determine identity type based on IAM Identity Center configuration
      const useIamIdentityCenter = config.application.iamIdentityCenter?.enabled === true;
      
      // Build admin configuration with IAM principals
      // Use the correct key: opensearchDashboards.dashboardAdmin.users
      // The value must be a JSON array of IAM principal ARNs
      // Include both config-defined admins AND the workspace Lambda role (if configured)
      const adminPrincipals: string[] = [];
      
      // Add user-defined admin principals from config
      if (config.application.admins?.iamPrincipals && config.application.admins.iamPrincipals.length > 0) {
        adminPrincipals.push(...config.application.admins.iamPrincipals);
      }
      
      // Add workspace Lambda execution role to admins (if workspaces are configured)
      // This is CRITICAL: the Lambda needs dashboard admin access to call the workspace API
      if (workspaceLambdaRoleArn) {
        adminPrincipals.push(workspaceLambdaRoleArn);
      }
      
      // Only add appConfigs if there are admin principals
      if (adminPrincipals.length > 0) {
        appConfigs.push({
          key: 'opensearchDashboards.dashboardAdmin.users',
          value: JSON.stringify(adminPrincipals),
        });
      }
      
      // Add IAM Identity Center groups configuration if enabled
      // Use the correct key: opensearchDashboards.dashboardAdmin.groups
      // The value must be a JSON array of IAM Identity Center group IDs
      if (useIamIdentityCenter && config.application.iamIdentityCenter?.adminGroups &&
          config.application.iamIdentityCenter.adminGroups.length > 0) {
        appConfigs.push({
          key: 'opensearchDashboards.dashboardAdmin.groups',
          value: JSON.stringify(config.application.iamIdentityCenter.adminGroups),
        });
      }
      
      // Create the OpenSearch Application
      // - dataSources: OpenSearch Serverless collections to connect
      // - appConfigs: Dashboard admin users/groups configuration
      // - iamIdentityCenterOptions: Enable IAM Identity Center SSO if configured
      const application = new CfnApplication(this, 'OpenSearchApplication', {
        name: config.application.name,
        dataSources: dataSources.length > 0 ? dataSources : undefined,
        appConfigs: appConfigs.length > 0 ? appConfigs : undefined,
        iamIdentityCenterOptions: useIamIdentityCenter ? {
          enabled: true,
          iamIdentityCenterInstanceArn: config.application.iamIdentityCenter!.instanceArn,
          ...(config.application.iamIdentityCenter!.roleArn && {
            iamRoleForIdentityCenterApplicationArn: config.application.iamIdentityCenter!.roleArn,
          }),
        } : undefined,
      });
      
      // Ensure application is created after the collection
      application.addDependency(collection);
      
      // Construct the application endpoint URL from the application ID
      // Format: https://application-{application-name}-{application-id}.{region}.opensearch.amazonaws.com/
      // Example: https://application-security-lake-app-gfw68hz673cbsd9qlnnf.ca-central-1.opensearch.amazonaws.com
      applicationEndpointUrl = `https://application-${config.application.name}-${application.attrId}.${Stack.of(this).region}.opensearch.amazonaws.com`;
      
      // Export application information
      new CfnOutput(this, 'ApplicationId', {
        value: application.attrId,
        description: 'OpenSearch Application ID',
        exportName: `${config.projectName}-${config.environment}-application-id`,
      });
      
      new CfnOutput(this, 'ApplicationArn', {
        value: application.attrArn,
        description: 'OpenSearch Application ARN',
        exportName: `${config.projectName}-${config.environment}-application-arn`,
      });
      
      new CfnOutput(this, 'ApplicationEndpoint', {
        value: applicationEndpointUrl,
        description: 'OpenSearch Application Endpoint URL for API access',
        exportName: `${config.projectName}-${config.environment}-application-endpoint`,
      });
      
      // ========================================
      // 10a. Workspace Creator (Optional)
      // ========================================
      // Create WorkspaceCreator if workspaces are configured and enabled.
      // Uses the application endpoint URL for workspace API access.
      // The Lambda function was pre-created above to add its role to application admins.
      if (config.workspaces && config.workspaces.enabled !== false) {
        // Get the pre-created Lambda function
        const workspaceLambda = (this as any)._workspaceLambdaFunction as lambda.Function;
        
        this.workspaceCreator = new WorkspaceCreator(this, 'WorkspaceCreator', {
          // Use the Application endpoint URL for workspace API access
          applicationEndpoint: applicationEndpointUrl,
          collectionArn: collection.attrArn,
          collectionEndpoint: collection.attrCollectionEndpoint,
          config: config.workspaces,
          projectName: config.projectName,
          environment: config.environment,
          // Pass the pre-created Lambda function
          existingLambdaFunction: workspaceLambda,
        });

        // Add dependency on application to ensure it exists before creating workspaces
        this.workspaceCreator.node.addDependency(application);
        this.workspaceCreator.node.addDependency(collection);
      }
    } else if (config.workspaces && config.workspaces.enabled !== false) {
      // If no application is configured but workspaces are, use the collection dashboard endpoint
      // This is the fallback behavior for backwards compatibility
      this.workspaceCreator = new WorkspaceCreator(this, 'WorkspaceCreator', {
        // Use the Collection Dashboard endpoint for workspace API access (fallback)
        applicationEndpoint: collection.attrDashboardEndpoint,
        collectionArn: collection.attrArn,
        collectionEndpoint: collection.attrCollectionEndpoint,
        config: config.workspaces,
        projectName: config.projectName,
        environment: config.environment,
      });

      // Add dependency on collection to ensure it exists before creating workspaces
      this.workspaceCreator.node.addDependency(collection);
    }

    // ========================================
    // 10b. Saved Objects Importer (Optional) - After WorkspaceCreator
    // ========================================
    // Create SavedObjectsImporter if configured and enabled.
    // This construct deploys dashboards, visualizations, and index patterns
    // from NDJSON files to OpenSearch Serverless via a Lambda-backed custom resource.
    //
    // IMPORTANT: This is created AFTER WorkspaceCreator because:
    // 1. If workspaces are configured, we need the workspace ID to construct the URL
    // 2. Saved objects should be imported to the workspace context, not global
    // 3. The workspace URL format is: {applicationEndpoint}/w/{workspaceId}/
    //
    // Mutable reference to track the SavedObjectsImporter for data access policy
    let savedObjectsImporterInstance: SavedObjectsImporter | undefined;
    
    if (config.savedObjects && config.savedObjects.enabled !== false) {
      // Determine the endpoint to use for saved objects import
      let savedObjectsEndpoint: string;
      
      // Data source ID for workspace-scoped saved objects imports
      // This is resolved by the workspace-creator Lambda via API lookup
      let savedObjectsDataSourceId: string | undefined;
      
      // If workspaces are configured and we have a WorkspaceCreator, get the workspace ID
      // and construct the workspace-specific URL
      if (this.workspaceCreator && config.workspaces?.workspaces && config.workspaces.workspaces.length > 0) {
        // Use the first workspace's ID to construct the URL
        // The workspace ID is returned from the custom resource via getAtt
        const firstWorkspaceConfig = config.workspaces.workspaces[0];
        const workspaceCustomResource = this.workspaceCreator.workspaceCustomResources[0];
        
        // Construct workspace URL: {applicationEndpoint}/w/{workspaceId}/
        // We use the application endpoint URL if an application was created,
        // otherwise fall back to the collection dashboard endpoint
        const baseEndpoint = applicationEndpointUrl || collection.attrDashboardEndpoint;
        
        // The workspace ID is retrieved from the custom resource output
        // We need to use cdk.Fn.join to construct the URL since workspace ID is a token
        savedObjectsEndpoint = cdk.Fn.join('', [
          baseEndpoint,
          '/w/',
          workspaceCustomResource.getAttString('WorkspaceId'),
          '/'
        ]);
        
        // Get the data source ID from the workspace custom resource
        // The workspace-creator Lambda resolves this by looking up the collection
        // in the OpenSearch data sources API and returns the UUID
        // DataSourceIds is returned as a list; use Fn.select to get the first element
        const dataSourceIdsList = workspaceCustomResource.getAtt('DataSourceIds');
        savedObjectsDataSourceId = cdk.Fn.select(0, dataSourceIdsList as unknown as string[]);
        
        // Note: Saved objects will be imported to workspace: ${firstWorkspaceConfig.name}
      } else if (applicationEndpointUrl) {
        // Application is configured but no workspaces - use application endpoint
        savedObjectsEndpoint = applicationEndpointUrl;
      } else {
        // No application or workspaces - use collection endpoint
        savedObjectsEndpoint = collection.attrCollectionEndpoint;
      }
      
      savedObjectsImporterInstance = new SavedObjectsImporter(this, 'SavedObjectsImporter', {
        collectionEndpoint: collection.attrCollectionEndpoint,
        collectionArn: collection.attrArn,
        workspaceEndpoint: savedObjectsEndpoint,
        config: config.savedObjects,
        projectName: config.projectName,
        environment: config.environment,
        encryptionKey: kmsKey,
        // Pass the data source ID for workspace-scoped imports
        // This allows saved objects to reference the correct data source
        dataSourceId: savedObjectsDataSourceId,
      });

      // Add dependency on collection to ensure it exists before importing
      savedObjectsImporterInstance.node.addDependency(collection);
      
      // If workspaces are configured, add dependency on workspace custom resources
      // to ensure workspaces exist before importing saved objects
      if (this.workspaceCreator) {
        for (const workspaceResource of this.workspaceCreator.workspaceCustomResources) {
          savedObjectsImporterInstance.node.addDependency(workspaceResource);
        }
      }
      
      // Store the reference for use in data access policy updates
      // Note: We use Object.assign to set this.savedObjectsImporter since it's readonly
      (this as any).savedObjectsImporter = savedObjectsImporterInstance;
    }

    // ========================================
    // 11. Stack Outputs
    // ========================================
    // Export key resource identifiers for use by other stacks or external systems
    new CfnOutput(this, 'CollectionId', {
      value: collection.attrId,
      description: 'OpenSearch Serverless Collection ID',
      exportName: `${config.projectName}-${config.environment}-collection-id`,
    });

    new CfnOutput(this, 'CollectionArn', {
      value: collection.attrArn,
      description: 'OpenSearch Serverless Collection ARN',
      exportName: `${config.projectName}-${config.environment}-collection-arn`,
    });

    new CfnOutput(this, 'CollectionEndpoint', {
      value: collection.attrCollectionEndpoint,
      description: 'OpenSearch Serverless Collection Endpoint',
      exportName: `${config.projectName}-${config.environment}-collection-endpoint`,
    });

    new CfnOutput(this, 'DashboardEndpoint', {
      value: collection.attrDashboardEndpoint,
      description: 'OpenSearch Dashboards Endpoint',
      exportName: `${config.projectName}-${config.environment}-dashboard-endpoint`,
    });

    // Only output KMS key ARN if a key was created
    if (kmsKey) {
      new CfnOutput(this, 'KmsKeyArn', {
        value: kmsKey.keyArn,
        description: 'KMS Key ARN used for collection encryption',
        exportName: `${config.projectName}-${config.environment}-kms-key-arn`,
      });
    }
  }
}