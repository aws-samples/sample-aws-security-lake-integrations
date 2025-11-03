# AWS OpenSearch Pipeline for Security Lake Integration

This directory contains configuration and documentation for deploying an OpenSearch Ingestion (OSI) pipeline that ingests OCSF-formatted security data from AWS Security Lake into OpenSearch for analysis and visualization.

## Quick Links

- **[Quick Start Guide](QUICKSTART.md)** - Deploy in 30 minutes with step-by-step commands
- **[Complete Setup Guide](SETUP_GUIDE.md)** - Comprehensive deployment and configuration documentation
- **[Configuration Template](OSI-pipeline.template.yaml)** - Parameterized pipeline configuration
- **[Dashboard Documentation](saved_objects/README.md)** - Pre-built security dashboards

## Overview

The OpenSearch Ingestion pipeline provides a fully managed solution for ingesting Security Lake data into OpenSearch:

**Data Flow:**
```
Security Lake S3 → EventBridge → SQS → OSI Pipeline → OpenSearch
```

**Key Features:**
- Automatic Parquet file processing from Security Lake
- OCSF schema transformation and enrichment
- Dynamic index creation per event class
- Pre-built security dashboards
- Scalable parallel processing
- Support for multiple cloud providers (AWS, Azure, GCP)

## Files in This Directory

### Configuration Files
- `OSI-pipeline.yaml` - Example production pipeline configuration
- `OSI-pipeline.template.yaml` - Parameterized template for deployment
- `validate-dashboard.sh` - Script to validate dashboard JSON syntax

### Documentation
- `SETUP_GUIDE.md` - Complete deployment and configuration guide
- `QUICKSTART.md` - Fast-track deployment instructions
- `IAM_Center_Auth.md` - Identity Center authentication setup
- `DASHBOARD_MIGRATION_GUIDE.md` - Dashboard version migration

### Dashboard Configurations (`saved_objects/`)
- `cross-cloud-security-dashboard.ndjson` - Primary security findings dashboard
- `cross-cloud-threat-hunting-dashboard.ndjson` - Threat hunting visualizations
- `cross-cloud-network-dashboard.ndjson` - Network activity analysis
- `DASHBOARD_CHANGELOG.md` - Dashboard version history
- Additional specialized dashboards and schemas

### Sample Data
- `cloudtrail_summary.ndjson` - CloudTrail event samples
- `example.csv` - Sample security findings data
- `network-example.csv` - Network flow log samples
- `OCSF_2.0.0_objects.ndjson` - OCSF schema mappings

## Getting Started

### Prerequisites

1. **AWS Security Lake** deployed with active data sources
2. **OpenSearch Domain** (managed or serverless)
3. **IAM Permissions** for creating roles and pipelines
4. **AWS CLI** configured with appropriate credentials

### Deployment Options

**Option 1: Quick Start (30 minutes)**
```bash
cd integrations/aws/opensearch-pipeline
# Follow instructions in QUICKSTART.md
```

**Option 2: Complete Setup (detailed configuration)**
```bash
cd integrations/aws/opensearch-pipeline
# Follow instructions in SETUP_GUIDE.md
```

## Architecture

### Pipeline Components

**Source Configuration:**
- Reads from Security Lake S3 buckets via SQS notifications
- Processes Parquet files with gzip compression
- Configurable parallel worker processing
- Automatic acknowledgment and retry handling

**Processing Pipeline:**
- Lowercase normalization for product names
- Cloud metadata extraction from resource identifiers
- Field mapping for CloudTrail, EKS, and WAF events
- String substitution for data cleanup
- Dynamic field routing based on event type

**Sink Configuration:**
- Writes to OpenSearch with dynamic index naming
- Index pattern: `ocsf-1.1.0-{class_uid}-{class_name}`
- Support for both managed and serverless OpenSearch
- Automatic index creation with proper mappings

### OCSF Event Classes Supported

| Class UID | Class Name | Description |
|-----------|------------|-------------|
| 2001 | compliance_finding | Security compliance assessments |
| 3001 | account_change | Account modification events |
| 4002 | http_activity | HTTP web traffic |
| 6001 | authentication | Authentication events |
| 6003 | api_activity | API calls (CloudTrail, EKS) |

## Dashboard Features

### Cross-Cloud Security Dashboard

Primary dashboard for security analysis:
- Severity distribution across findings
- Multi-cloud provider timeline
- Account-level finding breakdown
- Compliance status overview
- Top security findings
- Regional distribution
- High-priority alerts

**View Sample**: [Dashboard Preview](saved_objects/README.md)

### Threat Hunting Dashboard

Advanced threat detection visualizations:
- Anomaly detection patterns
- User behavior analytics
- Resource access patterns
- Network traffic analysis

### Network Dashboard

Network activity monitoring:
- Traffic flow visualization (Sankey diagrams)
- Source/destination analysis
- Protocol distribution
- Geographic traffic patterns

## Configuration Customization

### Adjusting Performance

Edit worker count and OCU allocation:
```yaml
source:
  s3:
    workers: "2"  # Increase for higher throughput

# During deployment:
aws osis create-pipeline \
  --min-units 4 \
  --max-units 8  # Scale up for large data volumes
```

### Custom Processing Rules

Add custom field transformations:
```yaml
processor:
  # Add custom field
  - add_entries:
      entries:
        - key: "/unmapped/custom_field"
          value: "custom_value"
  
  # Filter events
  - delete_entries:
      with_keys: ["/field_to_remove"]
      delete_when: '/severity_id < 40'  # Remove low severity
```

### Index Customization

Modify index naming strategy:
```yaml
sink:
  - opensearch:
      index: "custom-prefix-${/class_uid}-${/class_name}"
```

## Monitoring and Operations

### Key Metrics to Monitor

1. **Pipeline Health**
   - Status: ACTIVE vs ERROR
   - Records ingested per minute
   - Processing latency

2. **Queue Metrics**
   - SQS messages in flight
   - Dead letter queue depth
   - Message age

3. **OpenSearch Metrics**
   - Index count and size
   - Ingestion rate
   - Search performance

### Troubleshooting

Common issues and solutions:

**No data flowing:**
- Check SQS queue has messages
- Verify IAM role permissions
- Review CloudWatch logs for errors

**High latency:**
- Increase worker count
- Scale up OCUs
- Check OpenSearch cluster health

**Missing fields:**
- Verify OCSF schema compatibility
- Check field mapping in OpenSearch
- Review processor configuration

See [SETUP_GUIDE.md](SETUP_GUIDE.md#troubleshooting) for detailed troubleshooting.

## Cost Optimization

### Typical Monthly Costs (us-east-1)

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| OSI Pipeline | 2 OCUs, 24/7 | $480 |
| OpenSearch | 2 x r6g.large | $300 |
| S3 Storage | 100GB | $2 |
| Data Transfer | Minimal | $10 |
| **Total** | | **$792** |

### Optimization Strategies

1. **Right-size OCUs**: Start with minimum (2) and scale based on metrics
2. **Use Serverless**: Consider OpenSearch Serverless for variable workloads
3. **Implement ISM**: Archive old data to warm/cold tiers
4. **Filter events**: Process only required severity levels
5. **Batch processing**: Use larger visibility timeout for fewer API calls

## Security Best Practices

1. **Encryption**: Enable at-rest and in-transit encryption
2. **Network**: Deploy in VPC with private subnets
3. **Access Control**: Use fine-grained access control in OpenSearch
4. **IAM Roles**: Follow principle of least privilege
5. **Logging**: Enable CloudTrail for API auditing
6. **Monitoring**: Set up alerting for security events

## Support and Resources

### AWS Documentation
- [OpenSearch Ingestion](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ingestion.html)
- [Security Lake](https://docs.aws.amazon.com/security-lake/latest/userguide/)
- [OCSF Schema](https://schema.ocsf.io/)

### Project Resources
- [Complete Setup Guide](SETUP_GUIDE.md)
- [Quick Start Guide](QUICKSTART.md)
- [Dashboard Documentation](saved_objects/README.md)

### Getting Help
- Review troubleshooting section in setup guide
- Check AWS OpenSearch Service documentation
- Consult OCSF community resources

## Version History

- **v1.0** - Initial release with Security Lake integration
- **v1.1** - Added cross-cloud dashboard support
- **v1.2** - Enhanced threat hunting capabilities
- **v1.3** - Network flow visualization

## License

See [LICENSE](../../LICENSE) file in project root.

## Contributing

Contributions welcome. See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.