/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 *
 * Workspace Creator Construct
 *
 * This construct creates OpenSearch Dashboards workspaces via a Lambda-backed
 * custom resource using the OpenSearch Workspace API.
 */

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';
import { WorkspacesConfig, WorkspaceConfig } from '../core/config-loader';

/**
 * Properties for the WorkspaceCreator construct.
 */
export interface WorkspaceCreatorProps {
  /**
   * OpenSearch Application endpoint URL.
   * Format: https://{application-id}.{region}.aoss.amazonaws.com
   * This is the endpoint for the OpenSearch Application (CfnApplication).
   */
  readonly applicationEndpoint: string;

  /**
   * OpenSearch Serverless collection ARN.
   * Used for data source lookup and granting IAM permissions.
   */
  readonly collectionArn: string;

  /**
   * OpenSearch Serverless collection endpoint URL.
   * Used for registering the collection as a data source.
   */
  readonly collectionEndpoint: string;

  /**
   * Workspaces configuration from config.yaml.
   * Contains the list of workspaces to create and their settings.
   */
  readonly config: WorkspacesConfig;

  /**
   * Project name for resource naming.
   */
  readonly projectName: string;

  /**
   * Environment name for resource naming (e.g., dev, staging, prod).
   */
  readonly environment: string;

  /**
   * Optional: Pre-created Lambda function to use instead of creating a new one.
   * This is used when the Lambda's execution role needs to be added to the
   * OpenSearch Application admin principals before the application is created.
   */
  readonly existingLambdaFunction?: lambda.Function;
}

/**
 * WorkspaceCreator construct creates OpenSearch Dashboards workspaces.
 *
 * This construct:
 * 1. Creates a Lambda function to manage workspaces via the OpenSearch Workspace API
 * 2. Creates custom resources for each workspace with proper dependencies
 * 3. Handles workspace creation, update, and deletion lifecycle
 *
 * The workspaces are created in the order specified in the config.
 *
 * @example
 * ```typescript
 * const workspaces = new WorkspaceCreator(this, 'Workspaces', {
 *   applicationEndpoint: application.attrDashboardEndpoint,
 *   collectionArn: collection.attrArn,
 *   collectionEndpoint: collection.attrCollectionEndpoint,
 *   config: config.workspaces!,
 *   projectName: config.projectName,
 *   environment: config.environment,
 * });
 * ```
 */
export class WorkspaceCreator extends Construct {
  /**
   * The Lambda function that manages workspaces.
   * Can be used to add additional permissions or environment variables.
   */
  public readonly lambdaFunction: lambda.Function;

  /**
   * The custom resource provider used for all workspace operations.
   */
  public readonly provider: cr.Provider;

  /**
   * The custom resources for each workspace operation.
   * Exposed to allow external code to add dependencies on specific workspaces.
   */
  public readonly workspaceCustomResources: cdk.CustomResource[];

  constructor(scope: Construct, id: string, props: WorkspaceCreatorProps) {
    super(scope, id);

    // Validate configuration
    if (!props.config.workspaces || props.config.workspaces.length === 0) {
      throw new Error('WorkspaceCreator requires at least one workspace in config.workspaces');
    }

    // ========================================
    // 1. Create or Use Existing Lambda Function
    // ========================================
    // The Lambda function handles CloudFormation custom resource events
    // and manages workspaces via the OpenSearch Workspace API.
    //
    // If existingLambdaFunction is provided, use it instead of creating a new one.
    // This is used when the Lambda's execution role needs to be added to the
    // OpenSearch Application admin principals before the application is created.
    if (props.existingLambdaFunction) {
      // Use the pre-created Lambda function
      this.lambdaFunction = props.existingLambdaFunction;
      
      // Update the Lambda's environment variables with the actual application endpoint
      // since the Lambda was created with placeholder values
      const cfnFunction = this.lambdaFunction.node.defaultChild as cdk.CfnResource;
      cfnFunction.addPropertyOverride('Environment.Variables.OPENSEARCH_ENDPOINT', props.applicationEndpoint);
    } else {
      // Create a new Lambda function
      const lambdaPath = path.join(__dirname, '../../src/lambda/workspace-creator');

      this.lambdaFunction = new lambda.Function(this, 'WorkspaceFunction', {
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
          OPENSEARCH_ENDPOINT: props.applicationEndpoint,
          COLLECTION_ARN: props.collectionArn,
          COLLECTION_ENDPOINT: props.collectionEndpoint,
          LOG_LEVEL: 'INFO',
        },
        description: `Manage OpenSearch Dashboards workspaces for ${props.projectName}`,
      });

      // ========================================
      // 2. Grant Permissions to Lambda (only if creating new function)
      // ========================================
      // OpenSearch Serverless collection access
      // The Lambda needs to access both the collection and application APIs
      this.lambdaFunction.addToRolePolicy(
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            'aoss:APIAccessAll',
          ],
          resources: [props.collectionArn],
        })
      );

      // OpenSearch Serverless Dashboards access
      // Required for accessing the Dashboards/Workspace API
      this.lambdaFunction.addToRolePolicy(
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['aoss:DashboardsAccessAll'],
          resources: ['*'], // Resource format is arn:aws:aoss:{region}:{account}:dashboards/default
        })
      );
    }

    // ========================================
    // 3. Create Custom Resource Provider
    // ========================================
    // Single provider shared by all workspace custom resources.
    this.provider = new cr.Provider(this, 'Provider', {
      onEventHandler: this.lambdaFunction,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // ========================================
    // 4. Create Custom Resources for Each Workspace
    // ========================================
    // Create a custom resource for each workspace in the configuration.
    // Resources are created with explicit dependencies to ensure
    // sequential processing.
    this.workspaceCustomResources = [];
    let previousResource: cdk.CustomResource | undefined;

    for (const workspaceConfig of props.config.workspaces) {
      const resourceId = `Workspace${this.sanitizeResourceId(workspaceConfig.name)}`;

      // Build workspace properties for the custom resource
      const workspaceProperties = this.buildWorkspaceProperties(workspaceConfig, props);

      const resource = new cdk.CustomResource(this, resourceId, {
        serviceToken: this.provider.serviceToken,
        properties: workspaceProperties,
        resourceType: 'Custom::OpenSearchWorkspace',
      });

      // Add explicit dependency on previous workspace for sequential processing
      if (previousResource) {
        resource.node.addDependency(previousResource);
      }

      // Store reference for external dependency management
      this.workspaceCustomResources.push(resource);
      previousResource = resource;
    }

    // ========================================
    // 5. Stack Outputs
    // ========================================
    // Export useful information for debugging and monitoring
    new cdk.CfnOutput(this, 'WorkspaceCreatorFunctionName', {
      value: this.lambdaFunction.functionName,
      description: 'Lambda function for creating OpenSearch workspaces',
    });

    new cdk.CfnOutput(this, 'WorkspaceCount', {
      value: props.config.workspaces.length.toString(),
      description: 'Number of workspaces configured',
    });
  }

  /**
   * Sanitize a workspace name for use as a CloudFormation resource ID.
   * Removes invalid characters and converts to PascalCase.
   */
  private sanitizeResourceId(name: string): string {
    return name
      .replace(/[^a-zA-Z0-9]/g, '')
      .replace(/^[a-z]/, (c) => c.toUpperCase());
  }

  /**
   * Build the properties object for a workspace custom resource.
   *
   * IMPORTANT: CDK CustomResource properties are serialized automatically.
   * DO NOT use JSON.stringify() for array/object values - pass them directly.
   * Double-serialization causes issues where the Lambda receives escaped strings.
   */
  private buildWorkspaceProperties(
    workspace: WorkspaceConfig,
    props: WorkspaceCreatorProps
  ): Record<string, any> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const properties: Record<string, any> = {
      // Basic workspace settings
      WorkspaceName: workspace.name,
      WorkspaceDescription: workspace.description || '',
      WorkspaceColor: workspace.color || '',
      
      // Data source configuration
      // Priority: DataSourceIds > CollectionArn > DataSourceTitle
      CollectionArn: props.collectionArn,
      
      // Add timestamp to force update on every deployment
      Timestamp: Date.now().toString(),
    };

    // Add data source IDs if explicitly provided
    // Pass array directly - CDK handles serialization
    if (workspace.dataSourceIds && workspace.dataSourceIds.length > 0) {
      properties['DataSourceIds'] = workspace.dataSourceIds;
    }

    // Add data source title for lookup if provided
    if (workspace.dataSourceTitle) {
      properties['DataSourceTitle'] = workspace.dataSourceTitle;
    }

    // Add feature configuration if provided
    // OpenSearch Workspaces API only allows a single feature/use-case per workspace
    if (workspace.feature) {
      console.log('workspace-creator.ts: workspace.feature value:', workspace.feature);
      properties['Feature'] = workspace.feature;
    }

    // Add permissions configuration if provided
    // Pass object directly - CDK handles serialization
    if (workspace.permissions) {
      properties['Permissions'] = workspace.permissions;
    }

    console.log('workspace-creator.ts: Full properties object:', JSON.stringify(properties, null, 2));

    return properties;
  }
}
