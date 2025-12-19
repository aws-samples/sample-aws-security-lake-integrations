/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Configuration Loader for OpenSearch Serverless CDK
 * 
 * Loads and validates YAML configuration files.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'yaml';

/**
 * OpenSearch Serverless Collection Configuration
 */
export interface CollectionConfig {
  name: string;
  type: 'SEARCH' | 'TIMESERIES' | 'VECTORSEARCH';
  description?: string;
  standbyReplicas?: 'ENABLED' | 'DISABLED';
}

/**
 * Encryption Configuration
 */
export interface EncryptionConfig {
  enabled: boolean;
  keyType: 'AWS_OWNED_CMK' | 'CUSTOMER_MANAGED_CMK';
  kmsKeyId?: string;
  useSharedKey?: boolean;
  existingKeyArn?: string;
}

/**
 * Network Access Configuration
 */
export interface NetworkConfig {
  accessType: 'Public' | 'VPC';
  vpcEndpoints?: string[];
  allowFromPublic?: boolean;
}

/**
 * Data Access Configuration
 */
export interface DataAccessConfig {
  principals: string[];
  permissions: string[];
}

/**
 * Kinesis Data Stream Configuration
 */
export interface KinesisConfig {
  streamName: string;
  retentionPeriodHours?: number;  // Default: 24 hours
  streamMode?: 'ON_DEMAND' | 'PROVISIONED';  // Default: ON_DEMAND
  shardCount?: number;  // Only for PROVISIONED mode
  encryption?: {
    enabled?: boolean;  // Default: true
    useSharedKey?: boolean;  // Use the shared KMS key created for OpenSearch
    existingKeyArn?: string;  // Override with specific key ARN
  };
}

/**
 * S3 DLQ Bucket Configuration
 * Configuration for S3 bucket used as Dead Letter Queue by OpenSearch Ingestion pipeline
 */
export interface S3DlqBucketConfig {
  enabled?: boolean;  // Default: true if pipeline configured
  bucketName?: string;  // Optional: auto-generate if not provided
  lifecycleRetentionDays?: number;  // Default: 2 days
  encryption?: {
    useSharedKey?: boolean;  // Use shared KMS key
    existingKeyArn?: string;  // Use specific KMS key
  };
}

/**
 * OpenSearch Ingestion Pipeline Configuration
 */
export interface PipelineConfig {
  enabled: boolean;
  pipelineName?: string;
  minCapacity?: number;  // Default: 2 OCUs
  maxCapacity?: number;  // Default: 4 OCUs
  logGroupPattern?: string;  // Regex pattern for log groups (default: '.*')
  dlqBucket?: S3DlqBucketConfig;
}

/**
 * Security Lake Pipeline Configuration
 * Configuration for OpenSearch Ingestion pipeline that reads from Security Lake SQS queue
 */
export interface SecurityLakePipelineConfig {
  enabled?: boolean;  // Default: true if securityLakePipeline configured
  pipelineName?: string;  // Default: {project.name}-security-lake-pipeline
  queueUrl: string;  // REQUIRED: SQS queue URL from Security Lake
  minCapacity?: number;  // Default: 2 OCUs
  maxCapacity?: number;  // Default: 4 OCUs
  visibilityTimeout?: string;  // Default: '60s'
  workers?: string;  // Default: '1'
}

/**
 * IAM Identity Center Configuration for OpenSearch Application
 */
export interface IamIdentityCenterConfig {
  enabled: boolean;
  instanceArn?: string;  // Required when enabled: true
  roleArn?: string;      // Required when enabled: true
  adminGroups?: string[];  // IAM Identity Center group IDs for dashboard admins
}

/**
 * Administrator Configuration for OpenSearch Application
 */
export interface ApplicationAdminsConfig {
  iamPrincipals?: string[];  // IAM role/user ARNs
}

/**
 * Data Source Configuration for OpenSearch Application
 */
export interface ApplicationDataSourceConfig {
  autoAddCollection: boolean;  // Default: true
  description?: string;
}

/**
 * OpenSearch Application (UI) Configuration
 */
export interface ApplicationConfig {
  enabled: boolean;
  name: string;  // 3-30 chars, lowercase, numbers, hyphens
  iamIdentityCenter?: IamIdentityCenterConfig;
  admins?: ApplicationAdminsConfig;
  dataSource?: ApplicationDataSourceConfig;
}

/**
 * Configuration for a single saved object import
 */
export interface SavedObjectImport {
  /** Display name for CloudFormation resource */
  name: string;
  /** NDJSON filename in assets/ directory */
  file: string;
  /** Optional description */
  description?: string;
  /** Overwrite existing objects (default: true) */
  overwrite?: boolean;
}

/**
 * Configuration for saved objects import feature
 */
export interface SavedObjectsConfig {
  /** Enable/disable saved objects import */
  enabled?: boolean;
  /** Array of objects to import (processed in order) */
  imports: SavedObjectImport[];
}

/**
 * Configuration for workspace permissions
 */
export interface WorkspacePermissionsConfig {
  /** Permission modes (e.g., 'library_write', 'library_read') */
  library_write?: {
    users?: string[];
    groups?: string[];
  };
  library_read?: {
    users?: string[];
    groups?: string[];
  };
  write?: {
    users?: string[];
    groups?: string[];
  };
  read?: {
    users?: string[];
    groups?: string[];
  };
}

/**
 * Configuration for a single workspace
 */
export interface WorkspaceConfig {
  /** Workspace display name */
  name: string;
  /** Workspace description */
  description?: string;
  /** Workspace UI color (CSS color format) */
  color?: string;
  /** Single workspace feature/use-case to enable (only one allowed per workspace) */
  feature?: string;
  /** Permissions configuration */
  permissions?: WorkspacePermissionsConfig;
  /** Title to identify the data source (alternative to explicit ID lookup) */
  dataSourceTitle?: string;
  /** Explicit data source IDs to associate with this workspace */
  dataSourceIds?: string[];
}

/**
 * Configuration for OpenSearch Workspaces feature
 */
export interface WorkspacesConfig {
  /** Enable/disable workspace creation */
  enabled?: boolean;
  /** Array of workspaces to create */
  workspaces: WorkspaceConfig[];
}

/**
 * Complete Project Configuration
 */
export interface ProjectConfig {
  // Basic settings
  projectName: string;
  environment: string;
  awsRegion: string;
  accountId?: string;
  
  // Tagging
  tagSource: string;
  tagProduct: string;
  tagKitVersion: string;
  tags?: Array<{ key: string; value: string }>;
  
  // OpenSearch Serverless Configuration
  collection: CollectionConfig;
  encryption?: EncryptionConfig;
  network?: NetworkConfig;
  dataAccess?: DataAccessConfig;
  
  // Kinesis Data Stream Configuration (Optional)
  kinesis?: KinesisConfig;
  
  // OpenSearch Ingestion Pipeline Configuration (Optional)
  pipeline?: PipelineConfig;
  
  // Security Lake Pipeline Configuration (Optional)
  securityLakePipeline?: SecurityLakePipelineConfig;
  
  // Saved Objects Import Configuration (Optional)
  savedObjects?: SavedObjectsConfig;
  
  // OpenSearch Application (UI) Configuration (Optional)
  application?: ApplicationConfig;
  
  // OpenSearch Workspaces Configuration (Optional)
  workspaces?: WorkspacesConfig;
}

/**
 * Load configuration from YAML file
 */
export function loadConfig(cdkApp?: any): ProjectConfig {
  try {
    // Determine config file path from CDK context or default
    let configFile = 'config.yaml';
    
    if (cdkApp) {
      configFile = cdkApp.node.tryGetContext('configFile') || 'config.yaml';
    } else {
      // Fallback: Try to get from process arguments
      const argIndex = process.argv.indexOf('-c');
      if (argIndex !== -1 && process.argv[argIndex + 1] === 'configFile') {
        configFile = process.argv[argIndex + 2] || 'config.yaml';
      }
    }
    
    const configPath = path.resolve(configFile);
    
    console.log(`Loading configuration from: ${configPath}`);
    
    // Check if config file exists
    if (!fs.existsSync(configPath)) {
      throw new Error(`Configuration file not found: ${configPath}`);
    }
    
    // Read and parse YAML
    const configContent = fs.readFileSync(configPath, 'utf8');
    const config = yaml.parse(configContent) as ProjectConfig;
    
    // Validate configuration
    validateConfig(config);
    
    // Output the full configuration for debugging
    console.log('Configuration loaded successfully');
    console.log(JSON.stringify(config, null, 2));
    
    return config;
    
  } catch (error) {
    console.error('Failed to load configuration:', error);
    throw error;
  }
}

/**
 * Validate configuration structure and required fields
 */
function validateConfig(config: ProjectConfig): void {
  const requiredFields = [
    'projectName',
    'environment',
    'awsRegion',
    'tagSource',
    'tagProduct',
    'tagKitVersion'
  ];
  
  for (const field of requiredFields) {
    if (!config[field as keyof ProjectConfig]) {
      throw new Error(`Required configuration field missing: ${field}`);
    }
  }
  
  // Validate environment
  if (!['dev', 'staging', 'prod'].includes(config.environment)) {
    throw new Error('Environment must be one of: dev, staging, prod');
  }
  
  // Validate project name format
  const projectNamePattern = /^[a-z][a-z0-9-]*$/;
  if (!projectNamePattern.test(config.projectName)) {
    throw new Error('projectName must start with lowercase letter and contain only lowercase letters, numbers, and hyphens');
  }
  
  // Validate collection configuration
  if (config.collection) {
    validateCollectionConfig(config.collection);
  } else {
    throw new Error('Collection configuration is required');
  }
  
  // Validate Kinesis configuration if provided
  if (config.kinesis) {
    validateKinesisConfig(config.kinesis);
  }
  
  // Validate Pipeline configuration if provided
  if (config.pipeline) {
    validatePipelineConfig(config.pipeline);
  }
  
  // Validate Security Lake Pipeline configuration if provided
  if (config.securityLakePipeline) {
    validateSecurityLakePipelineConfig(config.securityLakePipeline, config);
  }
  
  // Validate Saved Objects configuration if provided
  if (config.savedObjects) {
    validateSavedObjectsConfig(config.savedObjects);
  }
  
  // Validate Application configuration if provided
  if (config.application) {
    validateApplicationConfig(config.application);
  }
  
  // Validate Workspaces configuration if provided
  if (config.workspaces) {
    validateWorkspacesConfig(config.workspaces);
  }
  
  console.log('Configuration validation passed');
}

/**
 * Validate collection configuration
 */
function validateCollectionConfig(collection: CollectionConfig): void {
  if (!collection.name) {
    throw new Error('Collection name is required');
  }
  
  // Validate collection name format (lowercase, numbers, hyphens only)
  const collectionNamePattern = /^[a-z][a-z0-9-]*$/;
  if (!collectionNamePattern.test(collection.name)) {
    throw new Error('Collection name must start with lowercase letter and contain only lowercase letters, numbers, and hyphens');
  }
  
  // Validate collection type
  const validTypes = ['SEARCH', 'TIMESERIES', 'VECTORSEARCH'];
  if (!collection.type || !validTypes.includes(collection.type)) {
    throw new Error(`Collection type must be one of: ${validTypes.join(', ')}`);
  }
  
  // Validate standby replicas if provided
  if (collection.standbyReplicas && !['ENABLED', 'DISABLED'].includes(collection.standbyReplicas)) {
    throw new Error('Standby replicas must be either ENABLED or DISABLED');
  }
}

/**
 * Validate Kinesis configuration
 */
function validateKinesisConfig(kinesis: KinesisConfig): void {
  // Stream name is required
  if (!kinesis.streamName) {
    throw new Error('kinesis.streamName is required when kinesis is configured');
  }
  
  // Validate stream name format (alphanumeric, hyphens, underscores)
  const streamNamePattern = /^[a-zA-Z0-9_-]+$/;
  if (!streamNamePattern.test(kinesis.streamName)) {
    throw new Error('kinesis.streamName must contain only alphanumeric characters, hyphens, and underscores');
  }
  
  // Validate stream mode
  if (kinesis.streamMode && !['ON_DEMAND', 'PROVISIONED'].includes(kinesis.streamMode)) {
    throw new Error('kinesis.streamMode must be either ON_DEMAND or PROVISIONED');
  }
  
  // Validate shard count for PROVISIONED mode
  if (kinesis.streamMode === 'PROVISIONED' && !kinesis.shardCount) {
    throw new Error('kinesis.shardCount is required when streamMode is PROVISIONED');
  }
  
  // Ensure shard count is only specified for PROVISIONED mode
  if (kinesis.streamMode !== 'PROVISIONED' && kinesis.shardCount) {
    throw new Error('kinesis.shardCount can only be specified when streamMode is PROVISIONED');
  }
  
  // Validate retention period (1-8760 hours)
  if (kinesis.retentionPeriodHours !== undefined) {
    if (kinesis.retentionPeriodHours < 1 || kinesis.retentionPeriodHours > 8760) {
      throw new Error('kinesis.retentionPeriodHours must be between 1 and 8760 hours');
    }
  }
}

/**
 * Validate Pipeline configuration
 */
function validatePipelineConfig(pipeline: PipelineConfig): void {
  // Validate pipeline DLQ bucket config if provided
  if (pipeline.dlqBucket) {
    if (pipeline.dlqBucket.lifecycleRetentionDays !== undefined) {
      if (pipeline.dlqBucket.lifecycleRetentionDays < 1 || pipeline.dlqBucket.lifecycleRetentionDays > 365) {
        throw new Error('pipeline.dlqBucket.lifecycleRetentionDays must be between 1 and 365');
      }
    }
    
    // Validate bucket name format if provided (lowercase alphanumeric and hyphens only, 3-63 chars)
    if (pipeline.dlqBucket.bucketName) {
      const bucketNamePattern = /^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/;
      if (!bucketNamePattern.test(pipeline.dlqBucket.bucketName)) {
        throw new Error('pipeline.dlqBucket.bucketName must be 3-63 characters, start and end with lowercase letter or number, and contain only lowercase letters, numbers, and hyphens');
      }
    }
  }
  
  // Validate pipeline name if provided
  if (pipeline.pipelineName) {
    const pipelineNamePattern = /^[a-z][a-z0-9-]*$/;
    if (!pipelineNamePattern.test(pipeline.pipelineName)) {
      throw new Error('pipeline.pipelineName must start with lowercase letter and contain only lowercase letters, numbers, and hyphens');
    }
  }
  
  // Validate capacity if provided
  if (pipeline.minCapacity !== undefined && (pipeline.minCapacity < 1 || pipeline.minCapacity > 96)) {
    throw new Error('pipeline.minCapacity must be between 1 and 96');
  }
  
  if (pipeline.maxCapacity !== undefined && (pipeline.maxCapacity < 1 || pipeline.maxCapacity > 96)) {
    throw new Error('pipeline.maxCapacity must be between 1 and 96');
  }
  
  if (pipeline.minCapacity !== undefined && pipeline.maxCapacity !== undefined) {
    if (pipeline.minCapacity > pipeline.maxCapacity) {
      throw new Error('pipeline.minCapacity must be less than or equal to pipeline.maxCapacity');
    }
  }
}

/**
 * Validate Security Lake Pipeline configuration
 */
function validateSecurityLakePipelineConfig(securityLakePipeline: SecurityLakePipelineConfig, config: ProjectConfig): void {
  // Queue URL is required
  if (!securityLakePipeline.queueUrl) {
    throw new Error('securityLakePipeline.queueUrl is required when securityLakePipeline is configured');
  }
  
  // Validate queue URL format
  if (!securityLakePipeline.queueUrl.startsWith('https://sqs.')) {
    throw new Error('securityLakePipeline.queueUrl must be a valid SQS queue URL starting with https://sqs.');
  }
  
  // Validate pipeline name if provided, or generate default and validate it
  const pipelineName = securityLakePipeline.pipelineName ||
    `${config.projectName.substring(0, 19)}-sl-pipe`;
  
  const pipelineNamePattern = /^[a-z][a-z0-9-]*$/;
  if (!pipelineNamePattern.test(pipelineName)) {
    throw new Error('securityLakePipeline.pipelineName must start with lowercase letter and contain only lowercase letters, numbers, and hyphens');
  }
  
  // Enforce AWS OpenSearch Ingestion 28-character limit
  if (pipelineName.length > 28) {
    throw new Error(`securityLakePipeline.pipelineName must be <= 28 characters. Current length: ${pipelineName.length}. Name: "${pipelineName}". Consider using a shorter pipelineName in config.yaml.`);
  }
  
  // Validate capacity if provided
  if (securityLakePipeline.minCapacity !== undefined && (securityLakePipeline.minCapacity < 1 || securityLakePipeline.minCapacity > 96)) {
    throw new Error('securityLakePipeline.minCapacity must be between 1 and 96');
  }
  
  if (securityLakePipeline.maxCapacity !== undefined && (securityLakePipeline.maxCapacity < 1 || securityLakePipeline.maxCapacity > 96)) {
    throw new Error('securityLakePipeline.maxCapacity must be between 1 and 96');
  }
  
  if (securityLakePipeline.minCapacity !== undefined && securityLakePipeline.maxCapacity !== undefined) {
    if (securityLakePipeline.minCapacity > securityLakePipeline.maxCapacity) {
      throw new Error('securityLakePipeline.minCapacity must be less than or equal to securityLakePipeline.maxCapacity');
    }
  }
}

/**
 * Validate Saved Objects configuration
 */
function validateSavedObjectsConfig(savedObjects: SavedObjectsConfig): void {
  // If enabled is true (or not specified, defaulting to enabled), imports must be non-empty
  const isEnabled = savedObjects.enabled !== false;
  
  if (isEnabled) {
    if (!savedObjects.imports || savedObjects.imports.length === 0) {
      throw new Error('savedObjects.imports must be a non-empty array when saved objects import is enabled');
    }
  }
  
  // Skip further validation if disabled or no imports
  if (!savedObjects.imports || savedObjects.imports.length === 0) {
    return;
  }
  
  // CloudFormation logical ID pattern: alphanumeric only
  const cfnLogicalIdPattern = /^[A-Za-z0-9]+$/;
  
  // Track names to ensure uniqueness
  const seenNames = new Set<string>();
  
  for (let i = 0; i < savedObjects.imports.length; i++) {
    const importConfig = savedObjects.imports[i];
    
    // Validate name is provided
    if (!importConfig.name) {
      throw new Error(`savedObjects.imports[${i}].name is required`);
    }
    
    // Validate name is a valid CloudFormation logical ID (alphanumeric only)
    if (!cfnLogicalIdPattern.test(importConfig.name)) {
      throw new Error(`savedObjects.imports[${i}].name must be alphanumeric only (valid CloudFormation logical ID). Got: "${importConfig.name}"`);
    }
    
    // Validate name uniqueness
    if (seenNames.has(importConfig.name)) {
      throw new Error(`savedObjects.imports[${i}].name must be unique. Duplicate name found: "${importConfig.name}"`);
    }
    seenNames.add(importConfig.name);
    
    // Validate file is provided
    if (!importConfig.file) {
      throw new Error(`savedObjects.imports[${i}].file is required`);
    }
    
    // Validate file ends with .ndjson
    if (!importConfig.file.endsWith('.ndjson')) {
      throw new Error(`savedObjects.imports[${i}].file must end with .ndjson extension. Got: "${importConfig.file}"`);
    }
  }
}

/**
 * Validate Application name
 * Must be 3-30 characters, lowercase letters/numbers/hyphens, start with lowercase letter
 */
export function validateApplicationName(name: string): void {
  // Length check: 3-30 characters
  if (name.length < 3 || name.length > 30) {
    throw new Error(
      `application.name must be between 3 and 30 characters. Got: ${name.length}`
    );
  }
  
  // Pattern check: lowercase letters, numbers, hyphens only
  // Must start with lowercase letter, cannot end with hyphen
  const pattern = /^[a-z][a-z0-9-]*[a-z0-9]$/;
  if (!pattern.test(name)) {
    throw new Error(
      'application.name must start with a lowercase letter, contain only ' +
      'lowercase letters, numbers, and hyphens, and not end with a hyphen'
    );
  }
  
  // No consecutive hyphens
  if (name.includes('--')) {
    throw new Error('application.name cannot contain consecutive hyphens');
  }
}

/**
 * Validate Application configuration
 */
export function validateApplicationConfig(application: ApplicationConfig): void {
  // Only validate when enabled
  if (!application.enabled) {
    return;
  }
  
  // Name is required when enabled
  if (!application.name) {
    throw new Error('application.name is required when application is enabled');
  }
  
  // Validate application name format
  validateApplicationName(application.name);
  
  // Validate IAM Identity Center configuration if provided
  if (application.iamIdentityCenter?.enabled) {
    // Instance ARN is required when IAM Identity Center is enabled
    if (!application.iamIdentityCenter.instanceArn) {
      throw new Error(
        'application.iamIdentityCenter.instanceArn is required when ' +
        'IAM Identity Center is enabled'
      );
    }
    
    // Validate IAM Identity Center instance ARN format
    const instanceArnPattern = /^arn:aws:sso:::instance\/ssoins-[a-f0-9]+$/;
    if (!instanceArnPattern.test(application.iamIdentityCenter.instanceArn)) {
      throw new Error(
        'application.iamIdentityCenter.instanceArn must be a valid IAM ' +
        'Identity Center instance ARN (format: arn:aws:sso:::instance/ssoins-xxxxx)'
      );
    }
    
    // Role ARN is required when IAM Identity Center is enabled
    if (!application.iamIdentityCenter.roleArn) {
      throw new Error(
        'application.iamIdentityCenter.roleArn is required when ' +
        'IAM Identity Center is enabled'
      );
    }
    
    // Validate IAM role ARN format
    const roleArnPattern = /^arn:aws:iam::[0-9]{12}:role\/.+$/;
    if (!roleArnPattern.test(application.iamIdentityCenter.roleArn)) {
      throw new Error(
        'application.iamIdentityCenter.roleArn must be a valid IAM role ARN'
      );
    }
  }
  
  // Validate admins configuration
  const hasIamPrincipals = application.admins?.iamPrincipals &&
    application.admins.iamPrincipals.length > 0;
  
  // At least one admin must be configured when application is enabled
  if (!hasIamPrincipals) {
    throw new Error(
      'At least one administrator must be configured in ' +
      'application.admins.iamPrincipals when application is enabled'
    );
  }
  
  // Validate IAM principal ARNs
  // Accepts: arn:aws:iam::ACCOUNT:role/NAME, arn:aws:iam::ACCOUNT:user/NAME,
  //          arn:aws:sts::ACCOUNT:assumed-role/ROLE/SESSION
  //          "*" (wildcard for all authenticated users)
  if (application.admins?.iamPrincipals) {
    const iamArnPattern = /^arn:aws:(iam|sts)::[0-9]{12}:(role|user|assumed-role)\/[\w+=,.@\/-]+$/;
    for (const principal of application.admins.iamPrincipals) {
      // Allow "*" as wildcard principal (all authenticated users)
      if (principal === '*') {
        continue;
      }
      if (!iamArnPattern.test(principal)) {
        throw new Error(
          `Invalid IAM principal ARN: ${principal}. ` +
          'Must be a valid IAM role, user, STS assumed-role ARN, or "*" for all users.'
        );
      }
    }
  }
}

/**
 * Validate Workspaces configuration
 */
export function validateWorkspacesConfig(workspaces: WorkspacesConfig): void {
  // Skip validation if disabled
  const isEnabled = workspaces.enabled !== false;
  
  if (isEnabled) {
    if (!workspaces.workspaces || workspaces.workspaces.length === 0) {
      throw new Error(
        'workspaces.workspaces must be a non-empty array when workspaces feature is enabled'
      );
    }
  }
  
  // Skip further validation if disabled or no workspaces
  if (!workspaces.workspaces || workspaces.workspaces.length === 0) {
    return;
  }
  
  // Track names to ensure uniqueness
  const seenNames = new Set<string>();
  
  for (let i = 0; i < workspaces.workspaces.length; i++) {
    const workspace = workspaces.workspaces[i];
    
    // Validate name is provided
    if (!workspace.name) {
      throw new Error(`workspaces.workspaces[${i}].name is required`);
    }
    
    // Validate name uniqueness
    if (seenNames.has(workspace.name)) {
      throw new Error(
        `workspaces.workspaces[${i}].name must be unique. ` +
        `Duplicate name found: "${workspace.name}"`
      );
    }
    seenNames.add(workspace.name);
    
    // Validate color format if provided (CSS color)
    if (workspace.color) {
      // Allow hex colors, CSS color names, or rgb/rgba formats
      const colorPattern = /^(#[0-9A-Fa-f]{3,8}|[a-zA-Z]+|rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)|rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*[\d.]+\s*\))$/;
      if (!colorPattern.test(workspace.color)) {
        throw new Error(
          `workspaces.workspaces[${i}].color must be a valid CSS color ` +
          `(hex, name, or rgb/rgba). Got: "${workspace.color}"`
        );
      }
    }
  }
}

/**
 * Get configuration value with fallback
 */
export function getConfigValue<T>(
  config: ProjectConfig,
  path: string,
  defaultValue: T
): T {
  const keys = path.split('.');
  let current: any = config;
  
  for (const key of keys) {
    if (current && typeof current === 'object' && key in current) {
      current = current[key];
    } else {
      return defaultValue;
    }
  }
  
  return current as T;
}