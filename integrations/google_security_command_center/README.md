# Google Security Command Center → AWS Security Lake Integration

A complete cross-cloud security integration solution that connects Google Security Command Center with AWS Security Lake and CloudTrail Event Data Store for unified security monitoring and compliance reporting.

## Architecture Overview

This solution creates a reliable, scalable integration between Google Cloud Platform and AWS, enabling organizations to centralize Google SCC security findings in AWS Security Lake using OCSF v1.7.0 format, alongside AWS CloudTrail for unified analysis.

### Key Components

- **GCP Infrastructure**: Pub/Sub Topic and Subscription for receiving Google SCC findings
- **AWS Infrastructure**: Lambda functions, SQS queues, DynamoDB cursor store, and Security Lake integration
- **Cross-Cloud Integration**: Secure credential management and reliable event processing
- **OCSF Compliance**: Full OCSF v1.7.0 schema compliance with rich vulnerability and compliance data
- **Monitoring**: Comprehensive CloudWatch alarms and logging for operational visibility

## Solution Architecture

The integration follows a polling-based processing pipeline:

```
Google SCC → GCP Pub/Sub Topic/Subscription → AWS Lambda (Pub/Sub Poller) →
SQS Queue → AWS Lambda (Event Transformer) → Security Lake (OCSF Parquet)
```

**Note:** GCP Pub/Sub subscriptions handle message tracking natively - no client-side cursor needed!

### Data Flow Process

1. **Google SCC Continuous Export**: Security findings sent to GCP Pub/Sub Topic
2. **Scheduled Polling**: AWS Lambda polls Pub/Sub subscription every 5 minutes
3. **Native Message Tracking**: Pub/Sub subscription maintains message position automatically
4. **Message Acknowledgment**: Successfully processed messages acknowledged to Pub/Sub
5. **Message Queuing**: Events forwarded to SQS for decoupled processing
6. **Event Transformation**: GCP events converted to OCSF v1.7.0 format
7. **Security Lake Storage**: Events delivered to AWS Security Lake as OCSF Parquet files
8. **Unified Analysis**: Events queryable via Athena alongside other security data

**Optional**: CloudTrail Event Data Store can be enabled for dual-destination mode

## Deployment Components

### GCP Infrastructure (Terraform)

Located in [`terraform/`](terraform/) directory:

- **Pub/Sub Topic**: Receives findings from Google Security Command Center
- **Pub/Sub Subscription**: Pull subscription for AWS Lambda polling
- **Service Account**: Dedicated service account with subscriber permissions
- **IAM Bindings**: Least-privilege access controls

**Documentation**: [`terraform/README.md`](terraform/README.md)

### AWS Infrastructure (CDK)

Located in [`cdk/`](cdk/) directory:

- **Pub/Sub Poller Lambda**: Scheduled GCP Pub/Sub polling function
- **Event Transformer Lambda**: OCSF/CloudTrail format conversion
- **DynamoDB Cursor Store**: Reliable message ID tracking for resumption
- **SQS Queue with DLQ**: Reliable message processing with retry handling
- **CloudTrail Event Data Store**: Unified security event storage (optional)
- **CloudTrail Channel**: External event ingestion pathway (optional)
- **Security Lake Integration**: OCSF Parquet file generation (optional)
- **Secrets Manager**: Secure GCP service account credential storage
- **CloudWatch Monitoring**: Comprehensive logging and alerting

**Documentation**: [`cdk/README.md`](cdk/README.md)

### Configuration Scripts

Located in [`scripts/`](scripts/) directory:

- **Automated Configuration**: Scripts for cross-cloud credential synchronization
- **Setup Automation**: Streamlined deployment workflow scripts

**Documentation**: [`scripts/README.md`](scripts/README.md)

## Quick Start

### Prerequisites

**GCP Requirements**:
- Google Cloud project with Security Command Center enabled
- Terraform >= 1.0
- gcloud CLI configured

**AWS Requirements**:
- AWS account with deployment permissions
- AWS CDK 2.x
- Node.js 18+
- Python 3.11+

### Deployment Sequence

#### 1. Deploy GCP Infrastructure First

```bash
cd terraform
terraform init
terraform apply -var-file="terraform.tfvars"
```

#### 2. Deploy AWS Infrastructure

```bash
cd ../cdk
npm install
cdk bootstrap  # First time only
cdk deploy
```

#### 3. Configure Cross-Cloud Integration

```bash
cd ../scripts
./configure-secrets-manager.sh
```

#### 4. Configure Google SCC Export

1. Navigate to Security Command Center in GCP Console
2. Go to Settings > Continuous Exports > Pub/Sub Exports
3. Create new export to your deployed Pub/Sub topic
4. Select finding types: Security findings, Vulnerabilities, Misconfigurations

## Key Features

### Enterprise Security
- **Cross-Cloud Authentication**: Secure credential management with AWS Secrets Manager
- **Encryption**: Customer-managed KMS keys for all data at rest
- **Network Security**: TLS 1.2+ for all communications
- **Access Controls**: IAM least-privilege principles throughout

### High Performance
- **Scheduled Polling**: Configurable polling intervals (default: 5 minutes)
- **Native Pub/Sub Tracking**: Subscription-based message acknowledgment (no cursor needed)
- **Batch Processing**: Efficient Pub/Sub and SQS batch processing
- **Parallel Processing**: Configurable Lambda concurrency for throughput

### OCSF v1.7.0 Compliance
- **Vulnerability Finding (2002)**: Full CVE and CVSS v3 details
- **Compliance Finding (2003)**: Rich compliance framework mappings (CIS, ISO, PCI, NIST, HIPAA, SOC2)
- **Detection Finding (2004)**: Threat and observation events
- **Template-Driven**: Jinja2 templates for flexible, maintainable transformations

### Comprehensive Monitoring
- **CloudWatch Integration**: Detailed logging and metrics for all components
- **Proactive Alerting**: SNS notifications for errors and performance issues
- **Dead Letter Queue**: Failed event capture and analysis
- **Operational Metrics**: Processing rates, success rates, and latency tracking

## Configuration Management

### Core Configuration Files

- **[`cdk/config.yaml`](cdk/config.yaml)**: Main CDK configuration
- **[`cdk/config.example.yaml`](cdk/config.example.yaml)**: Template with inline documentation
- **[`terraform/terraform.tfvars.example`](terraform/terraform.tfvars.example)**: Terraform configuration template

### Configuration Documentation

- **[`cdk/CONFIGURATION.md`](cdk/CONFIGURATION.md)**: Complete configuration reference guide
- Environment-specific examples and best practices included
- Security and performance tuning guidance provided

## GCP SCC Event Types Supported

### Vulnerability Findings (OCSF 2002)
- CVE vulnerabilities with full CVSS v3 details
- OS vulnerabilities from VM Manager
- Container vulnerabilities
- Attack vector, complexity, privileges, and impact scores
- Exploitation activity tracking

### Misconfiguration Findings (OCSF 2003)
- Security Health Analytics findings
- Policy violations
- Configuration best practices
- Rich compliance mappings across 6+ frameworks

### Threat Findings (OCSF 2004)
- Event Threat Detection findings
- Container threat detection
- Anomalous activity detection

## Monitoring and Troubleshooting

**CloudWatch Logs**:
```bash
# Monitor Pub/Sub Poller
aws logs tail "/aws/lambda/gscc-pubsub-poller-dev" --follow

# Monitor Event Transformer
aws logs tail "/aws/lambda/gscc-event-transformer-dev" --follow
```

**Queue Monitoring**:
```bash
# Check main queue status
aws sqs get-queue-attributes --queue-url <QUEUE_URL> --attribute-names All

# Check dead letter queue
aws sqs receive-message --queue-url <DLQ_URL>
```

**CloudTrail Event Data Store**:
```bash
# Query recent events
aws cloudtrail start-query \
  --query-statement "SELECT * FROM <EVENT_DATA_STORE_ID> WHERE eventSource = 'gcp.securitycommandcenter' ORDER BY eventTime DESC LIMIT 10"
```

## Security Considerations

### Data Protection
- **Encryption in Transit**: TLS 1.2+ for all cross-cloud communications
- **Encryption at Rest**: KMS encryption for all AWS storage components
- **Credential Security**: GCP service account keys stored in AWS Secrets Manager
- **Access Logging**: Complete audit trail for all data access

### Network Security
- **GCP Network Rules**: Configurable VPC and firewall rules
- **AWS VPC Integration**: Optional VPC endpoints for private connectivity
- **TLS Enforcement**: Minimum TLS 1.2 for GCP Pub/Sub connections

### Compliance Features
- **Audit Trails**: Complete logging of all data processing activities
- **Retention Policies**: Configurable data retention for compliance requirements
- **Data Classification**: Maintains security classifications through processing pipeline
- **Change Tracking**: CloudFormation and Terraform state management

## Cost Optimization

### Development Costs
- **Lambda**: Pay-per-execution (5-minute intervals)
- **DynamoDB**: On-demand billing for cursor storage
- **SQS**: Pay-per-message processing
- **Pub/Sub**: Pay per message and storage
- **Estimated**: $20-75/month for typical development workloads

### Production Optimization
- **Reserved Concurrency**: Control Lambda costs and performance
- **Provisioned Capacity**: DynamoDB provisioned capacity for predictable workloads
- **Log Retention**: Configure appropriate CloudWatch log retention periods
- **Data Lifecycle**: Implement Event Data Store and Security Lake retention policies

## Support and Documentation

### Component Documentation
- **[CDK Infrastructure](cdk/README.md)**: AWS infrastructure deployment and configuration
- **[Terraform Infrastructure](terraform/README.md)**: GCP infrastructure deployment
- **[Configuration Scripts](scripts/README.md)**: Automated setup and configuration tools

### Lambda Function Documentation
- **[Pub/Sub Poller](../security-lake/cdk/modules/google-scc/src/lambda/pubsub-poller/app.py)**: GCP Pub/Sub polling function (see also: [Google SCC Module README](../security-lake/cdk/modules/google-scc/README.md))
- **[Event Transformer](../security-lake/cdk/src/lambda/event-transformer/README.md)**: OCSF/CloudTrail transformation function
  - [Debugging Failed Events](../security-lake/cdk/src/lambda/event-transformer/DEBUGGING_FAILED_EVENTS.md) - Troubleshooting guide
  - [DLQ Processing](../security-lake/cdk/src/lambda/event-transformer/dlq_processing_guide.md) - Failed event recovery

### Framework Documentation
- **[Security Lake Integration Framework](../security-lake/cdk/README.md)**: Core framework and modular architecture
- **[Module Interface Specification](../security-lake/docs/MODULE_INTERFACE_SPEC.md)**: Integration module standards
- **[Configuration Schema](../security-lake/docs/CONFIG_SCHEMA.md)**: Complete configuration reference

### Additional Resources
- **[AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)**: Official CDK guidance
- **[CloudTrail Lake Documentation](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake.html)**: CloudTrail Event Data Store documentation
- **[OCSF Documentation](https://schema.ocsf.io/)**: Open Cybersecurity Schema Framework
- **[Google SCC Documentation](https://cloud.google.com/security-command-center/docs)**: Security Command Center configuration

## Version Information
- **Architecture**: Polling-based Pub/Sub integration with OCSF v1.7.0
- **Python Runtime**: 3.11
- **CDK Version**: 2.95.1
- **Terraform Version**: >= 1.0
- **OCSF Version**: 1.7.0

This solution provides enterprise-grade cross-cloud security integration with comprehensive monitoring, reliable processing, and unified event storage for enhanced security visibility across GCP and AWS environments.