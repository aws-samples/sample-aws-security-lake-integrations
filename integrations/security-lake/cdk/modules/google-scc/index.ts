/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * 
 * Google Security Command Center Integration Module
 * Module Registration
 */

import { registerModule } from '../../lib/core/module-registry';
import { GoogleSccIntegrationModule } from './google-scc-integration-module';

// Register module on import
registerModule('google-scc', GoogleSccIntegrationModule);

// Export module for direct use if needed
export { GoogleSccIntegrationModule };