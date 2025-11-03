© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Security Lake Integration Framework

## Overview

A modular AWS CDK framework for integrating security events from multiple cloud providers and security data sources into AWS Security Lake. The framework provides a pluggable architecture that enables rapid addition of new integrations while maintaining security best practices and operational consistency.

## Architecture

### Modular Design

```
Core Stack (Always Deployed)
├── Event Transformer Lambda
├── Security Hub Processor Lambda
├── Flow Log Processor Lambda
├── Security Lake Custom Resource
├── SQS Queues (with DLQ)
└── Shared KMS Key

Integration Modules (Conditionally Deployed)
├── Azure Module
│   ├── Event Hub Processor
│   └── DynamoDB Checkpoint Store
└── Future Modules (as needed)
```

### Key Features

- **Pluggable Modules**: Add new integrations by implementing IIntegrationModule interface
- **Automatic Migration**: Legacy configurations automatically converted to new format
- **Least Privilege**: Per-module IAM permissions with explicit grants
- **Backward Compatible**: Existing deployments work without changes
- **Type-Safe**: Full TypeScript type safety with comprehensive interfaces
- **Well-Tested**: Unit and integration tests for core framework and modules

## Quick Start

### Prerequisites

**AWS Requirements:**
- Node.js >= 18.0.0
- Python >= 3.9 (for Lambda development and testing)
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- AWS CLI configured with appropriate credentials
- AWS Security Lake enabled in target account/region
- Pre-existing Security Lake S3 bucket
- IAM permissions to create CloudFormation stacks

**Azure Requirements (if using Azure module):**
- Active Azure subscription
- Microsoft Defender for Cloud enabled
- Terraform >= 1.0 (for Azure infrastructure)
- Azure CLI installed and configured

### Installation

#### Step 1: Clone Repository

```bash
git clone <repository-url>
cd security-lake-integrations/integrations/security-lake/cdk
```

#### Step 2: Install Dependencies

```bash
# Install Node.js dependencies
npm install

# Install pre-commit hooks (optional but recommended)
pip install pre-commit
pre-commit install
```

#### Step 3: Configure Project

1. Copy example configuration:
```bash
cp config.example.yaml config.yaml
```

2. Edit `config.yaml` with your settings:
```yaml
projectName: my-security-lake
environment: dev
awsRegion: ca-central-1

# Core Security Lake configuration
securityLake:
  enabled: true
  s3Bucket: aws-security-data-lake-ca-central-1-xxxxx  # REQUIRED: Pre-existing bucket
  externalId: YourSecureRandomString  # REQUIRED: Generate secure random string
  
# Enable integrations as needed
integrations:
  azure:
    enabled: true
    config:
      eventHubProcessor:
        enabled: true
        schedule: rate(5 minutes)
        azureCredentialsSecretName: azure-eventhub-credentials
      flowLogProcessor:
        enabled: false  # Enable if using VNet Flow Logs
```

See [`docs/CONFIG_SCHEMA.md`](docs/CONFIG_SCHEMA.md) for complete configuration reference.

#### Step 4: Build Project

```bash
# Compile TypeScript
npm run build

# Validate configuration
npm run validate-config -- --config config.yaml
```

#### Step 5: Deploy Infrastructure

```bash
# Synthesize CloudFormation template (review before deploying)
npm run synth

# Deploy to AWS
npm run deploy

# Or deploy to specific environment
npm run deploy:dev    # Development
npm run deploy:prod   # Production
```

#### Step 6: Post-Deployment Configuration

**For Azure Integration:**
1. Deploy Azure infrastructure first (if not already done):
```bash
cd ../../../integrations/azure/microsoft_defender_cloud/terraform
terraform init
terraform apply
```

2. Configure AWS Secrets Manager with Azure credentials:
```bash
cd ../scripts
./configure-secrets-manager.sh
```

3. Set up Microsoft Defender continuous export (see Azure module README)

**Verify Deployment:**
```bash
# Check stack status
aws cloudformation describe-stacks --stack-name my-security-lake-dev

# Test Lambda functions
aws lambda invoke \
  --function-name azure-eventhub-processor-dev \
  --payload '{}' \
  response.json

# Monitor logs
aws logs tail /aws/lambda/event-transformer-dev --follow
```

### Quick Start for Specific Use Cases

#### Use Case 1: Azure Defender Integration Only

```yaml
# Minimal configuration for Azure Defender
integrations:
  azure:
    enabled: true
    config:
      eventHubProcessor:
        enabled: true
      flowLogProcessor:
        enabled: false
```

#### Use Case 2: Azure with Flow Logs

```yaml
# Full Azure integration with network visibility
integrations:
  azure:
    enabled: true
    config:
      eventHubProcessor:
        enabled: true
      flowLogProcessor:
        enabled: true
        azureFlowLogsSecretName: azure-flowlogs-credentials
```

#### Use Case 3: CloudTrail Event Data Store Integration

```yaml
# Enable CloudTrail integration
cloudTrailEventDataStore:
  enabled: true
  retentionPeriod: 90

coreProcessing:
  eventTransformer:
    eventDataStoreEnabled: true
    environment:
      CLOUDTRAIL_CHANNEL_ARN: arn:aws:cloudtrail:region:account:channel/id
```

## Project Structure

```
integrations/security-lake/cdk/
├── bin/
│   └── security-lake-integration.ts    # CDK app entry point
├── lib/
│   ├── security-lake-stack.ts          # Main stack
│   ├── core/                            # Core framework
│   │   ├── integration-module-interface.ts
│   │   ├── module-loader.ts
│   │   ├── module-registry.ts
│   │   ├── config-loader.ts
│   │   └── logger.ts
│   └── constructs/                      # Reusable constructs
│       ├── event-transformer-construct.ts
│       ├── securityhub-processor-construct.ts
│       └── security-lake-custom-resource-construct.ts
├── modules/                             # Integration modules
│   ├── azure/                          # Azure integration
│   │   ├── azure-integration-module.ts
│   │   └── src/lambda/

├── src/
│   ├── shared/                         # Shared Lambda libraries
│   │   ├── security-lake-client/
│   │   ├── sqs-client/
│   │   └── secrets-manager-client/
│   └── lambda/                         # Core Lambdas
│       ├── event-transformer/
│       ├── securityhub-processor/
│       └── security-lake-custom-resource/
├── docs/                               # Documentation
│   ├── MODULE_INTERFACE_SPEC.md
│   ├── MODULE_DEVELOPMENT_GUIDE.md
│   ├── CONFIG_SCHEMA.md
│   └── ARCHITECTURE.md
├── package.json
├── tsconfig.json
├── cdk.json
└── config.example.yaml
```

## Adding New Integration Modules

### Quick Start

1. Create module directory:
```bash
mkdir -p modules/my-integration/src/lambda
```

2. Implement IIntegrationModule interface:
```typescript
import { BaseIntegrationModule, ValidationResult, CoreResources } from '../core/integration-module-interface';

export class MyIntegrationModule extends BaseIntegrationModule {
  readonly moduleId = 'my-integration';
  readonly moduleName = 'My Integration';
  readonly moduleVersion = '1.0.0';
  readonly moduleDescription = 'Integrates My Service with Security Lake';

  validateConfig(config: any): ValidationResult {
    // Validate module config
    return { valid: true };
  }

  createResources(scope: Construct, coreResources: CoreResources, config: any): void {
    // Create Lambda functions, queues, etc.
  }

  getRequiredPermissions(): iam.PolicyStatement[] {
    // Return required IAM permissions
    return [];
  }
}
```

3. Register module:
```typescript
// In modules/my-integration/index.ts
import { registerModule } from '../core/module-registry';
import { MyIntegrationModule } from './my-integration-module';

registerModule('my-integration', MyIntegrationModule);
```

4. Configure in `config.yaml`:
```yaml
integrations:
  my-integration:
    enabled: true
    config:
      # Module-specific configuration
```

See [`docs/MODULE_DEVELOPMENT_GUIDE.md`](docs/MODULE_DEVELOPMENT_GUIDE.md) for complete guide.

## Core Components

### Event Transformer Lambda

Transforms security events from various sources into:
- OCSF format for Security Lake
- CloudTrail format (optional)
- ASFF format for Security Hub (optional)

**Key Features**:
- Template-based transformation
- Schema validation
- Batch processing
- DLQ for failed events

### Security Hub Processor Lambda

Imports ASFF findings into AWS Security Hub.

**Key Features**:
- Batch import support
- Rate limit handling
- Automatic retries

### Security Lake Custom Resource

Creates and manages Security Lake custom log sources.

**Key Features**:
- Lake Formation permissions
- Glue table management
- OCSF event class registration

## Integration Modules

### Azure Module

**Supported Data Sources**:
- Microsoft Defender for Cloud (Event Hub)

**Components**:
- Event Hub Processor Lambda
- DynamoDB Checkpoint Store
- Azure Secrets Manager integration

**Note**: Azure VNet Flow Logs are processed by the core Flow Log Processor Lambda, which supports multiple cloud providers.

**Configuration**: See [`modules/azure/README.md`](modules/azure/README.md)

### Future Modules

Additional integrations can be added by implementing the IIntegrationModule interface.

## Configuration

### Core Configuration

```yaml
projectName: security-lake-integration
environment: dev
awsRegion: ca-central-1

securityLake:
  enabled: true
  s3Bucket: aws-security-data-lake-region-hash
  externalId: SecureString
```

### Module Configuration

```yaml
integrations:
  azure:
    enabled: true
    config:
      eventHubProcessor:
        schedule: rate(5 minutes)
        memorySize: 512
```

See [`docs/CONFIG_SCHEMA.md`](docs/CONFIG_SCHEMA.md) for complete schema.

## Security

### Encryption

- All data at rest encrypted with KMS
- All data in transit uses TLS 1.2+
- Shared or per-module KMS keys supported

### IAM Permissions

- Least privilege per module
- Explicit resource ARNs when possible
- No wildcard permissions unless required

### Secrets Management

- Azure credentials stored in AWS Secrets Manager
- Never hardcode secrets
- Automatic rotation support

### Audit Logging

- All API calls logged to CloudTrail
- Lambda execution logs in CloudWatch
- Module-specific log namespacing

## Monitoring

### CloudWatch Alarms

- DLQ message count
- Lambda error rates
- SQS message age
- Module health checks

### Metrics

- Events processed per module
- Transformation success rate
- Security Lake delivery rate

## Testing

### Unit Tests

```bash
npm test
```

### Integration Tests

```bash
npm run test:integration
```

### Validate Configuration

```bash
npm run validate-config -- --config config.yaml
```

## Troubleshooting

### Common Issues

**Issue**: Configuration validation failed
- **Solution**: Check `docs/CONFIG_SCHEMA.md` for required fields

**Issue**: Module failed to load
- **Solution**: Verify module is registered in module-registry.ts

**Issue**: Lambda deployment failed
- **Solution**: Check Python dependencies match ARM64 requirements

**Issue**: Security Lake custom resource failed
- **Solution**: Ensure S3 bucket exists and Lake Formation admin is configured

### Debug Mode

Enable detailed logging:
```yaml
coreProcessing:
  eventTransformer:
    environment:
      LOGGING_LEVEL: DEBUG
```

## Migration from Legacy Version

### Automatic Migration

Legacy configurations are automatically migrated:

```yaml
# Old format (still supported)
azureIntegration:
  enabled: true

# Automatically converted to:
integrations:
  azure:
    enabled: true
```

### Manual Migration

For custom configurations, use migration tool:
```bash
npm run migrate-config -- --input config.old.yaml --output config.yaml
```

## Development

### Build Commands

```bash
npm run build       # Compile TypeScript
npm run watch       # Watch mode
npm test           # Run tests
npm run synth      # Synthesize CloudFormation
```

### CDK Commands

```bash
cdk synth          # Generate CloudFormation template
cdk diff           # Show changes
cdk deploy         # Deploy stack
cdk destroy        # Remove stack
```

### Adding New Module

See [`docs/MODULE_DEVELOPMENT_GUIDE.md`](docs/MODULE_DEVELOPMENT_GUIDE.md)

## Real-World Implementation

### Technical Blog Post

For a detailed walkthrough of implementing cross-cloud security integration with Microsoft Defender for Cloud, see our comprehensive technical blog post:

**[Unify Your Multi-Cloud Security Visibility: Integrating Microsoft Defender for Cloud with AWS Security Lake](../../../BLOG_POST.md)**

This blog post covers:
- Multi-cloud security challenges and solutions
- Step-by-step implementation walkthrough
- Event transformation deep dive with examples
- Querying unified security data across clouds
- Performance optimization and cost strategies
- Real-world use cases including threat hunting
- Troubleshooting common integration issues

The blog post provides practical examples and insights from production deployments, making it an essential companion to this technical documentation.

## Support

### Documentation

- [Module Interface Specification](docs/MODULE_INTERFACE_SPEC.md)
- [Configuration Schema](docs/CONFIG_SCHEMA.md)
- [Module Development Guide](docs/MODULE_DEVELOPMENT_GUIDE.md)
- [Azure Module README](modules/azure/README.md)
- [Threat Model](docs/THREAT_MODEL.md)

### Resources

**Project Documentation:**
- [Technical Blog Post](../../../BLOG_POST.md) - Real-world implementation walkthrough
- [Azure Integration Main README](../../azure/microsoft_defender_cloud/README.md) - Legacy standalone integration
- [GCP Integration Main README](../../google_security_command_center/README.md) - GCP SCC integration
- [GCP VPC Flow Logs](../../../gcp-vpc-flow-logs/README.md) - GCP network visibility

**External Resources:**
- [AWS Security Lake Documentation](https://docs.aws.amazon.com/security-lake/) - Security Lake and OCSF
- [OCSF Schema](https://schema.ocsf.io/) - Open Cybersecurity Schema Framework
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/) - Infrastructure as code
- [CloudTrail Lake Documentation](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake.html) - Event Data Store
- [Microsoft Defender for Cloud Documentation](https://docs.microsoft.com/en-us/azure/defender-for-cloud/) - Azure security
- [Google Security Command Center Documentation](https://cloud.google.com/security-command-center/docs) - GCP security

## Version History

### Version 2.0.0 (2025-01-22)
- Modular architecture with pluggable integrations
- Formal module interface specification
- Automatic legacy config migration
- Module registry system
- Enhanced security with per-module IAM

### Version 1.x (Legacy)
- Monolithic Microsoft Defender integration
- See `integrations/azure/microsoft_defender_cloud/` for legacy code

## License

© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.

## Contributing

This is an AWS Professional Services delivery kit. For enhancements or bug reports, please contact your AWS account team.