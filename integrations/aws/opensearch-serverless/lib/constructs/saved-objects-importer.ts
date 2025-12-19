/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 *
 * Saved Objects Importer Construct
 *
 * This construct deploys saved objects (dashboards, visualizations, index patterns)
 * from NDJSON files to OpenSearch Serverless via a Lambda-backed custom resource.
 */

import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';
import { SavedObjectsConfig } from '../core/config-loader';

/**
 * Properties for the SavedObjectsImporter construct.
 */
export interface SavedObjectsImporterProps {
  /**
   * OpenSearch Serverless collection endpoint URL.
   * Format: https://{collection-id}.{region}.aoss.amazonaws.com
   *
   * Note: If workspaceEndpoint is provided, this is still used for permissions
   * but the Lambda will use workspaceEndpoint for API calls.
   */
  readonly collectionEndpoint: string;

  /**
   * OpenSearch Serverless collection ARN.
   * Used for granting IAM permissions to the Lambda function.
   */
  readonly collectionArn: string;

  /**
   * Optional workspace-specific endpoint URL.
   * Format: https://application-{app-name}-{app-id}.{region}.opensearch.amazonaws.com/w/{workspace-id}
   *
   * If provided, the Lambda will import saved objects to this specific workspace
   * instead of the default global context. This is required when using
   * OpenSearch Applications with workspaces.
   */
  readonly workspaceEndpoint?: string;

  /**
   * Optional data source ID for workspace imports.
   * When importing to a workspace, this specifies which data source the
   * saved objects should be associated with. This is the ID of the
   * OpenSearch Serverless collection as registered in the workspace.
   *
   * The data source ID is obtained from the workspace-creator Lambda
   * which looks it up via the OpenSearch data sources API.
   */
  readonly dataSourceId?: string;

  /**
   * Saved objects configuration from config.yaml.
   * Contains the list of imports to process.
   */
  readonly config: SavedObjectsConfig;

  /**
   * Optional KMS key for S3 bucket encryption.
   * If not provided, S3-managed encryption (SSE-S3) will be used.
   */
  readonly encryptionKey?: kms.IKey;

  /**
   * Project name for resource naming.
   */
  readonly projectName: string;

  /**
   * Environment name for resource naming (e.g., dev, staging, prod).
   */
  readonly environment: string;

  /**
   * Optional pre-created Lambda function.
   * If provided, this Lambda will be used instead of creating a new one.
   * This is useful when the Lambda needs to be created earlier in the stack
   * to add its execution role to other resources (e.g., data access policy).
   */
  readonly existingLambdaFunction?: lambda.Function;
}

/**
 * SavedObjectsImporter construct deploys saved objects to OpenSearch Serverless.
 *
 * This construct:
 * 1. Creates an S3 bucket to store NDJSON asset files
 * 2. Deploys NDJSON files from the local assets/ directory to S3
 * 3. Creates a Lambda function to import saved objects via the OpenSearch API
 * 4. Creates custom resources for each import with sequential dependencies
 *
 * The imports are processed in the order specified in the config to ensure
 * dependencies are resolved (e.g., index patterns before dashboards).
 *
 * @example
 * ```typescript
 * const importer = new SavedObjectsImporter(this, 'SavedObjects', {
 *   collectionEndpoint: collection.attrCollectionEndpoint,
 *   collectionArn: collection.attrArn,
 *   config: config.savedObjects!,
 *   encryptionKey: kmsKey,
 *   projectName: config.projectName,
 *   environment: config.environment,
 * });
 * ```
 */
export class SavedObjectsImporter extends Construct {
  /**
   * The S3 bucket containing the NDJSON asset files.
   * Can be used to grant additional permissions or add lifecycle rules.
   */
  public readonly assetsBucket: s3.Bucket;

  /**
   * The Lambda function that imports saved objects.
   * Can be used to add additional permissions or environment variables.
   */
  public readonly lambdaFunction: lambda.Function;

  /**
   * The custom resource provider used for all imports.
   */
  public readonly provider: cr.Provider;

  /**
   * The custom resources for each import operation.
   * Exposed to allow external code to add dependencies on specific imports
   * without creating circular dependencies with the entire construct.
   */
  public readonly importCustomResources: cdk.CustomResource[];

  constructor(scope: Construct, id: string, props: SavedObjectsImporterProps) {
    super(scope, id);

    // Validate configuration
    if (!props.config.imports || props.config.imports.length === 0) {
      throw new Error('SavedObjectsImporter requires at least one import in config.imports');
    }

    // ========================================
    // 1. Create S3 Assets Bucket
    // ========================================
    // This bucket stores the NDJSON files during deployment.
    // Features:
    // - KMS encryption if key provided, otherwise S3-managed
    // - Auto-delete objects on stack deletion (ephemeral deployment artifacts)
    // - 1-day lifecycle rule for cleanup (files only needed during deployment)
    // - Block all public access for security
    this.assetsBucket = new s3.Bucket(this, 'AssetsBucket', {
      encryption: props.encryptionKey
        ? s3.BucketEncryption.KMS
        : s3.BucketEncryption.S3_MANAGED,
      encryptionKey: props.encryptionKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: false,
      lifecycleRules: [
        {
          id: 'DeleteAssetsAfter1Day',
          enabled: true,
          expiration: cdk.Duration.days(1),
        },
      ],
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
    });

    // ========================================
    // 2. Deploy Assets from Local Directory
    // ========================================
    // Upload all NDJSON files from the assets/ directory to S3.
    // The path is relative to the construct file location in lib/constructs/.
    // Files are uploaded to the root of the bucket.
    // IMPORTANT: Store reference for dependency management with import custom resources.
    const assetsPath = path.join(__dirname, '../../assets');

    const assetsDeployment = new s3deploy.BucketDeployment(this, 'DeployAssets', {
      sources: [s3deploy.Source.asset(assetsPath)],
      destinationBucket: this.assetsBucket,
      // Do not set destinationKeyPrefix to keep files at root
      exclude: ['README.md', '*.txt', '.gitkeep'],
      prune: false, // Keep previous versions for rollback capability
      retainOnDelete: false,
    });

    // ========================================
    // 3. Create or Use Existing Lambda Function
    // ========================================
    // The Lambda function handles CloudFormation custom resource events
    // and imports saved objects to OpenSearch Dashboards.
    // Uses zip packaging with Docker bundling for proper dependency installation.
    // If an existing Lambda is provided, use it instead of creating a new one.
    if (props.existingLambdaFunction) {
      // Use the pre-created Lambda function
      this.lambdaFunction = props.existingLambdaFunction;
      
      // Update the environment variable if a different endpoint is specified
      // Note: Environment variables for existing Lambda will be updated via custom resource properties
      // The Lambda code will use the OPENSEARCH_ENDPOINT environment variable that was set at creation
    } else {
      // Create a new Lambda function
      const lambdaPath = path.join(__dirname, '../../src/lambda/saved-objects-importer');

      this.lambdaFunction = new lambda.Function(this, 'ImporterFunction', {
        runtime: lambda.Runtime.PYTHON_3_13,
        architecture: lambda.Architecture.ARM_64,
        handler: 'app.handler',
        code: lambda.Code.fromAsset(lambdaPath, {
          bundling: {
            image: lambda.Runtime.PYTHON_3_13.bundlingImage,
            platform: 'linux/arm64',
            command: [
              'bash', '-c',
              'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
            ],
          },
        }),
        timeout: cdk.Duration.minutes(5),
        memorySize: 512,
        environment: {
          // Use workspace-specific endpoint if provided, otherwise fall back to collection endpoint
          // Workspace endpoint format: https://application-{app-name}-{app-id}.{region}.opensearch.amazonaws.com/w/{workspace-id}
          // Collection endpoint format: https://{collection-id}.{region}.aoss.amazonaws.com
          OPENSEARCH_ENDPOINT: props.workspaceEndpoint || props.collectionEndpoint,
          LOG_LEVEL: 'INFO',
          // Data source ID for workspace imports (if provided)
          // This is used to associate saved objects with the correct data source
          ...(props.dataSourceId && { DATASOURCE_ID: props.dataSourceId }),
        },
        description: `Import saved objects to OpenSearch Serverless for ${props.projectName}`,
      });
    }

    // ========================================
    // 4. Grant Permissions to Lambda
    // ========================================
    // Grant S3 read permissions for downloading NDJSON files
    // (always needed regardless of whether Lambda is new or existing)
    this.assetsBucket.grantRead(this.lambdaFunction);

    // KMS decrypt permission if bucket is encrypted with customer-managed key
    if (props.encryptionKey) {
      props.encryptionKey.grantDecrypt(this.lambdaFunction);
    }

    // Only add OpenSearch permissions if we created a new Lambda
    // (existing Lambdas should already have permissions configured)
    if (!props.existingLambdaFunction) {
      // OpenSearch Serverless collection access
      // The Lambda needs to call the Dashboards API for importing saved objects
      this.lambdaFunction.addToRolePolicy(
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "aoss:APIAccessAll",
            "aoss:DashboardsAccessAll",
            "opensearch:ApplicationAccessAll",
          ],
          resources: ["*"],
        })
      );
    }

    // ========================================
    // 5. Create Custom Resource Provider
    // ========================================
    // Single provider shared by all import custom resources.
    // The provider handles the Lambda invocation and response parsing.
    this.provider = new cr.Provider(this, 'Provider', {
      onEventHandler: this.lambdaFunction,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // ========================================
    // 6. Create Custom Resources for Each Import
    // ========================================
    // Create a custom resource for each import in the configuration.
    // Resources are created with explicit dependencies to ensure
    // sequential processing (index patterns before dashboards, etc.).
    // Custom resources are stored in the importCustomResources array
    // to allow external code to add targeted dependencies.
    this.importCustomResources = [];
    let previousResource: cdk.CustomResource | undefined;

    // Determine the endpoint to use for imports
    // Priority: workspaceEndpoint > collectionEndpoint
    const importEndpoint = props.workspaceEndpoint || props.collectionEndpoint;
    
    for (const importConfig of props.config.imports) {
      const resourceId = `Import${importConfig.name}`;

      const resource = new cdk.CustomResource(this, resourceId, {
        serviceToken: this.provider.serviceToken,
        properties: {
          // S3 location of the NDJSON file
          S3Bucket: this.assetsBucket.bucketName,
          S3Key: importConfig.file,
          // Import configuration
          Overwrite: String(importConfig.overwrite ?? true),
          ImportName: importConfig.name,
          // OpenSearch endpoint to use (workspace-specific or collection)
          // This overrides the Lambda's OPENSEARCH_ENDPOINT environment variable
          OpenSearchEndpoint: importEndpoint,
          // Add timestamp to force update on every deployment
          // This ensures saved objects are re-imported even if config unchanged
          Timestamp: Date.now().toString(),
        },
        // Add description as CloudFormation metadata
        resourceType: 'Custom::SavedObjectsImport',
      });

      // Add explicit dependency on BucketDeployment to ensure files are uploaded
      // before the Lambda tries to read them from S3. This is critical because
      // referencing assetsBucket.bucketName only creates a dependency on the bucket
      // resource, not on the deployment that uploads files to it.
      resource.node.addDependency(assetsDeployment);

      // Add explicit dependency on previous import for sequential processing
      // This ensures imports happen in order (index patterns before dashboards)
      if (previousResource) {
        resource.node.addDependency(previousResource);
      }

      // Store reference for external dependency management
      this.importCustomResources.push(resource);
      previousResource = resource;
    }

    // ========================================
    // 7. Stack Outputs
    // ========================================
    // Export useful information for debugging and monitoring
    new cdk.CfnOutput(this, 'AssetsBucketName', {
      value: this.assetsBucket.bucketName,
      description: 'S3 bucket containing saved object NDJSON files',
    });

    new cdk.CfnOutput(this, 'ImporterFunctionName', {
      value: this.lambdaFunction.functionName,
      description: 'Lambda function for importing saved objects',
    });

    new cdk.CfnOutput(this, 'ImportCount', {
      value: props.config.imports.length.toString(),
      description: 'Number of saved object imports configured',
    });
  }
}