/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Configuration Loader for Security Lake Integration Framework
 *
 * Loads and validates configuration.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'yaml';
import { Logger } from './logger';

const logger = new Logger('ConfigLoader');

/**
 * OCSF Event Class Configuration
 */
export interface OCSFEventClassConfig {
  sourceName: string;
  sourceVersion?: string;
  eventClasses: string[];
}

/**
 * Security Lake Configuration
 */
export interface SecurityLakeConfig {
  enabled: boolean;
  s3Bucket: string;
  externalId: string;
  serviceRole: string;
  OCSFEventClass: OCSFEventClassConfig[];
}

/**
 * Integration Module Configuration
 */
export interface IntegrationConfig {
  enabled: boolean;
  modulePath?: string;
  config: any;
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
  tags: Array<{ key: string; value: string }>;
  
  // Encryption
  encryption?: {
    enabled: boolean;
    keyType: string;
    keyAlias?: string;
    keyDescription?: string;
    keyRotationEnabled?: boolean;
    keyPendingWindowInDays?: number;
  };
  
  // Security Lake
  securityLake?: SecurityLakeConfig;
  
  // Core processing
  coreProcessing?: any;
  
  // SQS configuration
  sqsQueue?: any;
  
  // CloudTrail configuration
  cloudTrailEventDataStore?: any;
  
  // Security Hub configuration
  securityHub?: any;
  
  // Monitoring configuration
  monitoring?: any;
  
  // Integration modules (NEW)
  integrations?: Record<string, IntegrationConfig>;
  
  // Legacy compatibility fields
  azureIntegration?: any;
  lambdaFunctions?: any;
  flowLogQueue?: any;
  dynamoDbCursorTable?: any;
  
  // Environment overrides
  development?: any;
  production?: any;
}

/**
 * Load configuration from YAML file
 */
export async function loadConfig(): Promise<ProjectConfig> {
  try {
    // Determine config file path
    const configFile = process.env.CDK_CONFIG_FILE || 
                      process.argv.find(arg => arg.startsWith('configFile='))?.split('=')[1] ||
                      'config.yaml';
    
    const configPath = path.resolve(configFile);
    
    logger.info(`Loading configuration from: ${configPath}`);
    
    // Check if config file exists
    if (!fs.existsSync(configPath)) {
      throw new Error(`Configuration file not found: ${configPath}`);
    }
    
    // Read and parse YAML
    const configContent = fs.readFileSync(configPath, 'utf8');
    const config = yaml.parse(configContent) as ProjectConfig;
    
    // Validate configuration
    validateConfig(config);
    
    // Apply environment-specific overrides
    applyEnvironmentOverrides(config);
    
    logger.info('Configuration loaded successfully', {
      projectName: config.projectName,
      environment: config.environment,
      awsRegion: config.awsRegion,
      securityLakeEnabled: config.securityLake?.enabled || false,
      enabledModules: config.integrations
        ? Object.entries(config.integrations)
            .filter(([_, cfg]: [string, IntegrationConfig]) => cfg.enabled)
            .map(([id, _]: [string, IntegrationConfig]) => id)
        : []
    });
    
    return config;
    
  } catch (error) {
    logger.error('Failed to load configuration', error);
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
  
  // Validate Security Lake configuration if enabled
  if (config.securityLake?.enabled) {
    validateSecurityLakeConfig(config.securityLake);
  }
  
  // Validate integration modules
  if (config.integrations) {
    validateIntegrationsConfig(config.integrations);
  }
  
  logger.info('Configuration validation passed');
}

/**
 * Validate Security Lake configuration
 */
function validateSecurityLakeConfig(securityLakeConfig: SecurityLakeConfig): void {
  if (!securityLakeConfig.s3Bucket) {
    throw new Error('Security Lake s3Bucket is required when enabled');
  }
  
  if (!securityLakeConfig.externalId) {
    throw new Error('Security Lake externalId is required when enabled');
  }
  
  if (!securityLakeConfig.serviceRole) {
    throw new Error('Security Lake serviceRole is required when enabled');
  }
  
  if (!securityLakeConfig.OCSFEventClass || securityLakeConfig.OCSFEventClass.length === 0) {
    throw new Error('Security Lake OCSFEventClass array is required and must contain at least one configuration');
  }
  
  // Validate S3 bucket name format
  const bucketNamePattern = /^aws-security-data-lake-[a-z0-9-]+$/;
  if (!bucketNamePattern.test(securityLakeConfig.s3Bucket)) {
    logger.warn(`Security Lake S3 bucket name does not follow expected pattern: aws-security-data-lake-{region}-{unique-id}`);
  }
  
  // Validate each OCSF Event Class configuration
  const validEventClasses = [
    'SECURITY_FINDING',
    'VULNERABILITY_FINDING',
    'COMPLIANCE_FINDING',
    'NETWORK_ACTIVITY',
    'AUTHENTICATION',
    'AUTHORIZATION',
    'SYSTEM_ACTIVITY',
    'FILE_ACTIVITY',
    'PROCESS_ACTIVITY',
    'REGISTRY_ACTIVITY'
  ];
  
  const sourceNames = new Set<string>();
  
  securityLakeConfig.OCSFEventClass.forEach((eventClassConfig, index) => {
    if (!eventClassConfig.sourceName) {
      throw new Error(`OCSF Event Class configuration at index ${index} must have a sourceName`);
    }
    
    if (!eventClassConfig.eventClasses || eventClassConfig.eventClasses.length === 0) {
      throw new Error(`OCSF Event Class configuration "${eventClassConfig.sourceName}" must have at least one event class`);
    }
    
    // Check for duplicate source names
    if (sourceNames.has(eventClassConfig.sourceName)) {
      throw new Error(`Duplicate sourceName "${eventClassConfig.sourceName}" found`);
    }
    sourceNames.add(eventClassConfig.sourceName);
    
    // Validate source name format
    const sourceNamePattern = /^[a-zA-Z][a-zA-Z0-9_]*$/;
    if (!sourceNamePattern.test(eventClassConfig.sourceName)) {
      throw new Error(`Invalid sourceName "${eventClassConfig.sourceName}". Must start with letter and contain only letters, numbers, and underscores`);
    }
    
    // Validate event classes
    eventClassConfig.eventClasses.forEach((eventClass) => {
      if (!validEventClasses.includes(eventClass)) {
        logger.warn(`Event class "${eventClass}" is not in standard OCSF list`);
      }
    });
    
    // Validate source version if provided
    if (eventClassConfig.sourceVersion) {
      const versionPattern = /^\d+\.\d+(\.\d+)?$/;
      if (!versionPattern.test(eventClassConfig.sourceVersion)) {
        throw new Error(`Invalid sourceVersion "${eventClassConfig.sourceVersion}". Must be in format x.y or x.y.z`);
      }
    }
  });
}

/**
 * Validate integrations configuration
 */
function validateIntegrationsConfig(integrations: Record<string, IntegrationConfig>): void {
  for (const [moduleId, moduleConfig] of Object.entries(integrations)) {
    // Validate module ID format
    const moduleIdPattern = /^[a-z][a-z0-9-]*$/;
    if (!moduleIdPattern.test(moduleId)) {
      throw new Error(`Invalid module ID "${moduleId}". Must start with lowercase letter and contain only lowercase letters, numbers, and hyphens`);
    }
    
    // Validate module configuration structure
    if (typeof moduleConfig.enabled !== 'boolean') {
      throw new Error(`Module "${moduleId}" must have 'enabled' boolean field`);
    }
    
    if (moduleConfig.enabled && !moduleConfig.config) {
      logger.warn(`Module "${moduleId}" is enabled but has no configuration`);
    }
  }
  
  logger.info(`Validated ${Object.keys(integrations).length} integration module configurations`);
}

/**
 * Apply environment-specific configuration overrides
 */
function applyEnvironmentOverrides(config: ProjectConfig): void {
  const envOverrides = config.environment === 'prod' ? config.production : config.development;
  
  if (envOverrides) {
    logger.info(`Applying ${config.environment} environment overrides`);
    
    // Apply encryption overrides
    if (envOverrides.encryptionKeyType && config.encryption) {
      config.encryption.keyType = envOverrides.encryptionKeyType;
    }
    
    // Apply concurrency overrides
    if (envOverrides.reservedConcurrentExecutions && config.coreProcessing) {
      if (config.coreProcessing.eventTransformer && envOverrides.reservedConcurrentExecutions.transformationLambda) {
        config.coreProcessing.eventTransformer.reservedConcurrentExecutions = 
          envOverrides.reservedConcurrentExecutions.transformationLambda;
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
