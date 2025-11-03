/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Integration Module Interface
 * 
 * Defines the contract that all Security Lake integration modules must implement.
 * This ensures consistency, maintainability, and security across all integrations.
 * 
 * @see integrations/security-lake/docs/MODULE_INTERFACE_SPEC.md for complete specification
 */

import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as kms from 'aws-cdk-lib/aws-kms';
import { Construct } from 'constructs';

/**
 * Validation result returned by module config validation
 */
export interface ValidationResult {
  valid: boolean;
  errors?: string[];
  warnings?: string[];
}

/**
 * Health check configuration for module monitoring
 */
export interface HealthCheckConfig {
  enabled: boolean;
  checkInterval: cdk.Duration;
  failureThreshold: number;
  alarmActions?: string[];
}

/**
 * Core resources provided by SecurityLakeStack to modules
 * These are shared resources that modules can utilize
 */
export interface CoreResources {
  /** Main SQS queue for events going to transformer */
  readonly eventTransformerQueue: sqs.IQueue;
  
  /** Dead letter queue for failed transformations */
  readonly eventTransformerDeadLetterQueue: sqs.IQueue;
  
  /** Optional ASFF SQS queue for Security Hub integration */
  readonly asffQueue?: sqs.IQueue;
  
  /** Optional Flow Log SQS queue for Azure flow log processing */
  readonly flowLogQueue?: sqs.IQueue;
  
  /** Optional shared KMS key for encryption */
  readonly sharedKmsKey?: kms.IKey;
  
  /** Security Lake S3 bucket name */
  readonly securityLakeBucket: string;
  
  /** Security Lake custom resource (if enabled) */
  readonly securityLakeCustomResource?: cdk.CustomResource;
  
  /** Project configuration for context */
  readonly projectConfig: any;
}

/**
 * Base interface that all integration modules MUST implement
 * 
 * This interface defines the contract for pluggable integration modules
 * that can be dynamically loaded and registered with the SecurityLakeStack.
 * 
 * @example
 * ```typescript
 * export class AzureIntegrationModule implements IIntegrationModule {
 *   readonly moduleId = 'azure';
 *   readonly moduleName = 'Azure Defender Integration';
 *   readonly moduleVersion = '1.0.0';
 *   // ... implement required methods
 * }
 * ```
 */
export interface IIntegrationModule {
  /**
   * Unique identifier for this module
   * Must be lowercase alphanumeric with hyphens only
   * @example "azure-defender", "aws-guardduty", "gcp-scc"
   */
  readonly moduleId: string;

  /**
   * Human-readable name for this module
   * @example "Azure Defender Integration"
   */
  readonly moduleName: string;

  /**
   * Semantic version of this module
   * Must follow semver: MAJOR.MINOR.PATCH
   * @example "1.0.0"
   */
  readonly moduleVersion: string;

  /**
   * Brief description of module functionality
   * @example "Integrates Azure Defender for Cloud security events with AWS Security Lake"
   */
  readonly moduleDescription: string;

  /**
   * Validate module-specific configuration
   * 
   * Called during stack synthesis before resource creation.
   * Must check all required fields and validate their formats.
   * 
   * @param config - Module-specific configuration object
   * @returns ValidationResult with any errors or warnings
   * 
   * @example
   * ```typescript
   * validateConfig(config: any): ValidationResult {
   *   const errors: string[] = [];
   *   if (!config.required Field) {
   *     errors.push('requiredField is missing');
   *   }
   *   return { valid: errors.length === 0, errors };
   * }
   * ```
   */
  validateConfig(config: any): ValidationResult;

  /**
   * Create module-specific AWS resources
   * 
   * Called during stack synthesis after config validation passes.
   * Should create all Lambda functions, queues, tables, and other
   * resources needed by this integration module.
   * 
   * @param scope - CDK construct scope (typically the SecurityLakeStack)
   * @param coreResources - Shared resources from core stack
   * @param config - Module-specific configuration object
   * 
   * @example
   * ```typescript
   * createResources(scope: Construct, coreResources: CoreResources, config: any): void {
   *   const processor = new lambda.Function(scope, `${this.moduleId}-processor`, {
   *     // ... configuration
   *   });
   *   coreResources.eventTransformerQueue.grantSendMessages(processor);
   * }
   * ```
   */
  createResources(
    scope: Construct,
    coreResources: CoreResources,
    config: any
  ): void;

  /**
   * Get IAM policy statements required by this module
   * 
   * Called during role creation to grant least-privilege permissions.
   * Must return specific permissions with resource ARNs when possible.
   * 
   * @returns Array of IAM PolicyStatement objects
   * 
   * @example
   * ```typescript
   * getRequiredPermissions(): iam.PolicyStatement[] {
   *   return [
   *     new iam.PolicyStatement({
   *       sid: 'ModuleSecretsAccess',
   *       actions: ['secretsmanager:GetSecretValue'],
   *       resources: [`arn:aws:secretsmanager:*:*:secret:${this.moduleId}-*`]
   *     })
   *   ];
   * }
   * ```
   */
  getRequiredPermissions(): iam.PolicyStatement[];

  /**
   * Get health check configuration for module monitoring
   * 
   * Optional method to define health checks for module components.
   * If not implemented, no health checks will be created.
   * 
   * @returns HealthCheckConfig or undefined if not implemented
   */
  getHealthCheckConfig?(): HealthCheckConfig;

  /**
   * Get module-specific CloudFormation outputs
   * 
   * Optional method to export useful values for operators.
   * Common outputs include resource ARNs, URLs, and configuration values.
   * 
   * @returns Record of output names to values
   * 
   * @example
   * ```typescript
   * getModuleOutputs?(): Record<string, any> {
   *   return {
   *     ProcessorFunctionArn: this.processorFunction.functionArn,
   *     QueueUrl: this.moduleQueue.queueUrl
   *   };
   * }
   * ```
   */
  getModuleOutputs?(): Record<string, any>;

  /**
   * Cleanup resources during module deactivation
   * 
   * Optional method called when module is disabled in configuration.
   * Can be used to gracefully shutdown resources or perform cleanup.
   * 
   * @param scope - CDK construct scope
   */
  cleanup?(scope: Construct): void;
}

/**
 * Abstract base class for integration modules
 * 
 * Provides common functionality and validation logic that can be
 * inherited by concrete module implementations.
 */
export abstract class BaseIntegrationModule implements IIntegrationModule {
  abstract readonly moduleId: string;
  abstract readonly moduleName: string;
  abstract readonly moduleVersion: string;
  abstract readonly moduleDescription: string;

  abstract validateConfig(config: any): ValidationResult;
  abstract createResources(scope: Construct, coreResources: CoreResources, config: any): void;
  abstract getRequiredPermissions(): iam.PolicyStatement[];

  /**
   * Validate semantic version format
   * @param version - Version string to validate
   * @returns true if valid semver format
   */
  protected isValidSemver(version: string): boolean {
    const semverRegex = /^\d+\.\d+\.\d+$/;
    return semverRegex.test(version);
  }

  /**
   * Validate module ID format
   * @param id - Module ID to validate
   * @returns true if valid format (lowercase alphanumeric with hyphens)
   */
  protected isValidModuleId(id: string): boolean {
    const idRegex = /^[a-z][a-z0-9-]*$/;
    return idRegex.test(id);
  }

  /**
   * Create standardized resource ID
   * @param scope - CDK scope
   * @param resourceType - Type of resource
   * @returns Standardized ID string
   */
  protected createResourceId(scope: Construct, resourceType: string): string {
    return `${this.moduleId}-${resourceType}`;
  }
}