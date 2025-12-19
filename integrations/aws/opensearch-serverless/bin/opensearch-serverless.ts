#!/usr/bin/env node
/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 *
 * CDK Application Entry Point for OpenSearch Serverless
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { OpenSearchServerlessStack } from '../lib/opensearch-serverless-stack';
import { loadConfig } from '../lib/core/config-loader';

const app = new cdk.App();

try {
  // Load configuration from YAML file, passing the app for context
  const config = loadConfig(app);
  
  // Create stack with configuration
  new OpenSearchServerlessStack(app, `${config.projectName}-${config.environment}`, {
    env: {
      account: config.accountId || process.env.CDK_DEFAULT_ACCOUNT,
      region: config.awsRegion || process.env.CDK_DEFAULT_REGION,
    },
    description: `OpenSearch Serverless collection for ${config.projectName} (${config.environment})`,
    tags: {
      Environment: config.environment,
      Project: config.projectName,
      Source: config.tagSource,
      Product: config.tagProduct,
      Version: config.tagKitVersion,
      ...Object.fromEntries(config.tags?.map(tag => [tag.key, tag.value]) || [])
    }
  }, config);
} catch (error) {
  console.error('Failed to initialize CDK application:', error);
  process.exit(1);
}