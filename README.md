# Security Lake Integrations

This repository provides production-ready solutions for integrating third-party security tools with AWS Security Lake and CloudTrail. It delivers a modular, AWS CDK-based framework that enables organizations to unify security event data from multiple cloud providers and security tools into AWS Security Lake for centralized analysis, threat detection, and compliance monitoring.

The solution provides production-ready integrations for Microsoft Defender for Cloud (Azure) and Google Security Command Center (GCP), with an extensible pattern for adding additional security data sources. All components are deployed as AWS managed services with comprehensive security controls, encryption, and monitoring.

## Architecture

The framework uses a plugin-based architecture where integrations are self-contained modules that connect to the core Security Lake processing pipeline.

### Core Components

The core stack is always deployed and provides the foundation for all integrations:

- **Event Transformer Lambda**: Converts events to OCSF, CloudTrail, or ASFF formats
- **Security Hub Processor Lambda**: Processes AWS Security Hub findings
- **Flow Log Processor Lambda**: Handles VPC flow logs from multiple cloud providers
- **Security Lake Custom Resource**: Manages Security Lake configuration
- **SQS Queues with DLQ**: Reliable event queuing with dead letter queue for failed messages
- **Shared KMS Key**: Customer-managed encryption for all data at rest

### Integration Modules

Integration modules are conditionally deployed based on configuration:

**Azure Integration Module** (Production-Ready)
- Event Hub Processor Lambda for Microsoft Defender alerts
- DynamoDB checkpoint store for Event Hub consumer tracking
- Support for security assessments, alerts, secure scores, and VNet flow logs
- Full OCSF v1.1.0 transformation with ASFF and CloudTrail format support

**Google SCC Integration Module** (Production-Ready)
- Pub/Sub Poller Lambda for Security Command Center findings
- Native Pub/Sub subscription tracking (no external checkpoint store needed)
- Support for vulnerability findings, compliance findings, and threat detection
- Rich OCSF v1.1.0 metadata including CVE details and compliance framework mappings

**Custom Integration Modules**
- Additional modules can be added by implementing the IIntegrationModule interface
- Follow proven pattern demonstrated by Azure and Google SCC integrations
- See Module Development Guide for step-by-step instructions

### Architectural Benefits

- Rapid addition of new integrations without modifying core infrastructure
- Automatic legacy configuration migration for backward compatibility
- Per-module IAM permissions following least privilege principle
- Type-safe implementation with full TypeScript interfaces
- Comprehensive monitoring and alerting for all components

## Deployment

### Prerequisites

Before deploying the solution, ensure you have the following in your AWS account:

- **AWS CLI**: [Install AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)
- **Node.js**: Version 18.x or later
- **AWS CDK**: Install globally with `npm install -g aws-cdk`
- **Security Lake**: Pre-configured Amazon Security Lake instance with S3 bucket
- **Lake Formation**: Admin role configured for Security Lake operations
- **IAM Permissions**: Sufficient permissions to create Lambda functions, SQS queues, KMS keys, and IAM roles

For cloud provider integrations, you will also need:

**For Azure Integration:**
- Azure Event Hub namespace and connection strings
- Microsoft Defender for Cloud continuous export configured
- Service principal with appropriate permissions

**For Google Cloud Integration:**
- Google Cloud Pub/Sub subscription configured
- Service account credentials with Security Command Center permissions
- Organization-level or project-level access

### Steps

Follow these steps to deploy the Security Lake integration framework:

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd security-lake-integrations
   ```

2. **Navigate to the CDK directory**

   ```bash
   cd integrations/security-lake/cdk
   ```

3. **Install dependencies**

   ```bash
   npm install
   ```

4. **Configure your integration**

   Copy the example configuration and customize it for your environment:

   ```bash
   cp config.example.yaml config.yaml
   ```

   Edit [`config.yaml`](integrations/security-lake/cdk/config.yaml) to configure:
   - Security Lake bucket and region
   - Module enablement (azure, google-scc)
   - Encryption settings (shared KMS key or per-resource CMKs)
   - Event Hub or Pub/Sub connection details
   - Alert thresholds and monitoring configuration

   See [`CONFIG_SCHEMA.md`](integrations/security-lake/docs/CONFIG_SCHEMA.md) for detailed configuration options.

5. **Build the CDK application**

   ```bash
   npm run build
   ```

6. **Synthesize CloudFormation template (optional)**

   Review the generated CloudFormation template before deployment:

   ```bash
   cdk synth -c configFile=config.yaml
   ```

7. **Deploy the stack**

   ```bash
   cdk deploy -c configFile=config.yaml
   ```

   Review the changes and confirm when prompted.

8. **Configure cloud provider credentials**

   After deployment, configure secrets for your cloud provider integrations:

   **For Azure:**
   ```bash
   cd integrations/azure/microsoft_defender_cloud
   ./scripts/configure-secrets-manager.sh
   ```

   **For Google Cloud:**
   ```bash
   cd integrations/google_security_command_center
   ./scripts/configure-secrets-manager.sh
   ```

9. **Verify deployment**

   Monitor CloudWatch Logs for the Lambda functions to verify events are being processed:
   - `/aws/lambda/<stack-name>-EventTransformer`
   - `/aws/lambda/<stack-name>-EventHubProcessor` (if Azure enabled)
   - `/aws/lambda/<stack-name>-PubSubPoller` (if Google SCC enabled)

### Clean Up

To remove all deployed resources:

```bash
cd integrations/security-lake/cdk
cdk destroy -c configFile=config.yaml
```

Note: Security Lake configuration and S3 data are not automatically deleted. Remove these manually if needed.

## Integration-Specific Documentation

Each integration has comprehensive documentation for setup and troubleshooting:

### Security Lake Framework
- [Framework README](integrations/security-lake/cdk/README.md) - Core framework documentation
- [Installation Guide](integrations/security-lake/INSTALLATION_GUIDE.md) - Complete installation walkthrough
- [Module Development Guide](integrations/security-lake/docs/MODULE_DEVELOPMENT_GUIDE.md) - Creating custom modules
- [Module Interface Specification](integrations/security-lake/docs/MODULE_INTERFACE_SPEC.md) - Module interface details
- [Configuration Schema](integrations/security-lake/docs/CONFIG_SCHEMA.md) - Complete configuration reference
- [Technical Blog Post](BLOG_POST.md) - Extensible pattern and implementation walkthrough

### Microsoft Defender for Cloud (Azure)
- [Azure Module README](integrations/security-lake/cdk/modules/azure/README.md) - Modular Azure integration
- [Azure Integration README](integrations/azure/microsoft_defender_cloud/README.md) - Standalone Azure solution
- [Azure Terraform Setup](integrations/azure/microsoft_defender_cloud/terraform/README.md) - Azure infrastructure

### Google Security Command Center (GCP)
- [Google SCC Module README](integrations/security-lake/cdk/modules/google-scc/README.md) - Modular GCP integration
- [Google SCC README](integrations/google_security_command_center/README.md) - GCP integration details
- [GCP Terraform Setup](integrations/google_security_command_center/terraform/README.md) - GCP infrastructure

### OpenSearch Serverless Security Analytics
- [OpenSearch Serverless README](integrations/aws/opensearch-serverless/README.md) - Complete stack documentation
- [Quick Start Guide](integrations/aws/opensearch-serverless/quickstart.md) - Rapid deployment walkthrough
- [Configuration Example](integrations/aws/opensearch-serverless/config.yaml.example) - Full configuration reference

## Limitations

- **Lambda Memory and Timeout**: Flow log processing may require increased memory allocation for large files. Current default is 512 MB with 5-minute timeout.
- **PyArrow Compatibility**: Lambda functions require Python 3.13 with ARM64 architecture for PyArrow version compatibility.
- **Security Lake Prerequisites**: Security Lake S3 bucket must pre-exist and be configured before deployment.
- **Event Hub Checkpointing**: Azure Event Hub integration uses DynamoDB for checkpointing. Consumer group state is eventually consistent.
- **API Rate Limits**: Google Cloud Pub/Sub and Azure Event Hub have API rate limits that may require polling interval adjustment under high load.
- **Custom Module Development**: New modules must implement the IIntegrationModule interface and follow the module packaging guidelines.

## Development

### Pre-Commit Hooks

Install pre-commit hooks for automated code quality checks:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Configured checks include:
- Prettier formatting (TypeScript, JavaScript)
- ShellCheck validation
- YAML/JSON validation
- License header insertion
- Private key detection

### Testing

Each Lambda function includes local testing capability:

```bash
cd integrations/security-lake/cdk/src/lambda/<function-name>
python local_test.py              # Local execution
pytest test_lambda.py             # Unit tests
pytest integration_test.py        # Integration tests (if present)
```

### Project Structure

```
security-lake-integrations/
├── integrations/
│   ├── security-lake/cdk/                    # Modular CDK framework (primary)
│   │   ├── modules/                          # Integration modules
│   │   │   ├── azure/                        # Azure Defender module
│   │   │   ├── google-scc/                   # Google SCC module
│   │   │   └── example-skeleton/             # Template for new modules
│   │   ├── src/lambda/                       # Core Lambda functions
│   │   │   ├── event-transformer/            # OCSF/CloudTrail/ASFF transformation
│   │   │   ├── flow-log-processor/           # Multi-cloud network flow logs
│   │   │   ├── securityhub-processor/        # ASFF finding import
│   │   │   └── security-lake-custom-resource/ # Security Lake management
│   │   └── lib/                              # CDK stack definitions
│   ├── azure/                                # Azure-specific infrastructure
│   │   └── microsoft_defender_cloud/
│   │       ├── terraform/                    # Azure Event Hub and Defender config
│   │       └── scripts/                      # Azure configuration automation
│   ├── google_security_command_center/       # GCP-specific infrastructure
│   │   ├── terraform/                        # GCP Pub/Sub and SCC config
│   │   └── scripts/                          # GCP configuration automation
│   └── aws/opensearch-serverless/            # OpenSearch Serverless CDK stack
│       ├── assets/                           # Dashboard NDJSON files
│       ├── lib/                              # CDK constructs
│       └── src/lambda/                       # Lambda functions
└── docs/                                     # Additional documentation
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md) for more information on reporting security issues.

### Encryption and Key Management

All data is encrypted in transit and at rest using AWS KMS customer-managed keys:

- **KMS Key Rotation**: Automatic key rotation is enabled by default for all customer-managed CMKs, rotating keys annually per AWS best practices
- **Encryption at Rest**: SQS queues, S3 buckets, DynamoDB tables, and Secrets Manager secrets use KMS encryption
- **Encryption in Transit**: All AWS service communications use TLS 1.2 or higher

### IAM Security

IAM roles follow the principle of least privilege:
- Explicit resource ARNs in all IAM policies (no wildcards except where required by AWS services)
- Separate IAM roles per Lambda function and integration module
- No cross-module resource access

### Secrets Management

Cloud provider credentials stored in AWS Secrets Manager:
- All secrets encrypted with KMS customer-managed keys
- Secrets must be manually rotated following cloud provider security policies
- Placeholder values in secrets after deployment require configuration via provided scripts
- See integration-specific documentation for secret rotation procedures

### Key Rotation Procedures

**KMS Keys (Automatic)**
- Customer-managed keys rotate automatically every 365 days
- Previous key versions retained for decryption of existing encrypted data
- No manual intervention required

**Secrets Manager Secrets (Manual)**
- Azure Event Hub connection strings: Rotate when credentials are compromised or per security policy
- Azure Storage Account credentials: Rotate service principal client secrets per Azure AD policy
- Google Cloud service account keys: Follow GCP recommended 90-day rotation schedule

For detailed rotation procedures, see:
- Azure Integration: `integrations/azure/microsoft_defender_cloud/scripts/configure-secrets-manager.sh`
- Google SCC Integration: `integrations/google_security_command_center/scripts/configure-secrets-manager.sh`

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT-0