#!/usr/bin/env node
/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Security Lake Integration Framework
 * CDK Application Entry Point
 *
 * This CDK app creates a modular AWS infrastructure for Security Lake integrations
 * from multiple cloud providers and security data sources.
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { SecurityLakeStack } from '../lib/security-lake-stack';
import { loadConfig } from '../lib/core/config-loader';
import { Logger } from '../lib/core/logger';
import { ModuleRegistry } from '../lib/core/module-registry';
import { AzureIntegrationModule } from '../modules/azure/azure-integration-module';
import { GoogleSccIntegrationModule } from '../modules/google-scc/google-scc-integration-module';

// Initialize logger
const logger = new Logger('CDK-App');

async function main() {
  try {
    // Register integration modules
    logger.info('Registering integration modules');
    ModuleRegistry.register('azure', () => new AzureIntegrationModule());
    ModuleRegistry.register('google-scc', () => new GoogleSccIntegrationModule());
    
    // Load configuration
    logger.info('Loading configuration');
    const config = await loadConfig();
    
    logger.info('Configuration loaded successfully', { 
      projectName: config.projectName, 
      environment: config.environment,
      awsRegion: config.awsRegion,
      securityLakeEnabled: config.securityLake?.enabled,
      configuredIntegrations: config.integrations 
        ? Object.keys(config.integrations)
        : []
    });

    // Create CDK app
    const app = new cdk.App();

    // Environment configuration
    const env = {
      account: config.accountId || process.env.CDK_DEFAULT_ACCOUNT,
      region: config.awsRegion || process.env.CDK_DEFAULT_REGION || 'ca-central-1'
    };

    logger.info('CDK Environment', env);

    // Create the main stack
    const stackName = `${config.projectName}-${config.environment}`;
    
    new SecurityLakeStack(app, stackName, {
      env,
      description: `Security Lake Integration Framework (${config.environment}) - Modular multi-cloud security integration`,
      stackName: stackName,
      terminationProtection: config.environment === 'prod',
      config: config,
      
      // Stack-level tags
      tags: {
        Project: config.projectName,
        Environment: config.environment,
        ManagedBy: 'CDK',
        Framework: 'Security-Lake-Integration',
        Version: '2.0.0',
        Source: config.tagSource,
        Product: config.tagProduct,
        KitVersion: config.tagKitVersion,
        DeploymentTimestamp: new Date().toISOString()
      }
    });

    logger.info('Security Lake Integration Stack created successfully', { 
      stackName,
      framework: 'Modular',
      version: '2.0.0'
    });

  } catch (error) {
    logger.error('Failed to create CDK app', {
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined
    });
    console.error('Full error details:', error);
    process.exit(1);
  }
}

// Execute main function
main().catch((error) => {
  logger.error('Unhandled error in CDK app', {
    error: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack : undefined
  });
  console.error('Full error details:', error);
  process.exit(1);
});