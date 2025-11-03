# OpenSearch Ingestion Pipeline Setup Guide

This guide explains how to deploy an OpenSearch Ingestion (OSI) pipeline to ingest data from AWS Security Lake into OpenSearch for analysis and visualization.

## Overview

The OpenSearch Ingestion pipeline:
- Reads OCSF-formatted data from Security Lake S3 buckets via SQS notifications
- Processes and transforms the data (lowercasing, string manipulation, field extraction)
- Ingests data into OpenSearch with dynamic index naming based on OCSF class
- Supports multiple OCSF event classes (CloudTrail, WAF, EKS, Network Activity, etc.)

## Prerequisites

### Required AWS Resources
1. **Amazon Security Lake** - Active Security Lake with data sources configured
2. **OpenSearch Domain** - Deployed OpenSearch or OpenSearch Serverless domain
3. **SQS Queue** - Queue receiving S3 event notifications from Security Lake
4. **IAM Role** - Service role for OpenSearch Ingestion with appropriate permissions

### Required Permissions
- `s3:GetObject` on Security Lake S3 buckets
- `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:ChangeMessageVisibility` on SQS queue
- `es:ESHttpPut`, `es:ESHttpPost` on OpenSearch domain
- `sts:AssumeRole` for cross-account access (if applicable)

### Tools Required
- AWS CLI configured with appropriate credentials
- Access to AWS Console (OpenSearch Ingestion, Security Lake, IAM)
- Text editor for YAML configuration

## Step 1: Gather Required Information

Before deploying, collect the following information:

| Parameter | Description | Example | Where to Find |
|-----------|-------------|---------|---------------|
| AWS_REGION | AWS region for deployment | `us-east-1` | Your Security Lake region |
| AWS_ACCOUNT_ID | Your AWS account ID | `123456789012` | AWS Console → Account Settings |
| SQS_QUEUE_URL | Security Lake SQS queue URL | `https://sqs.us-east-1.amazonaws.com/123456789012/queue-name` | SQS Console → Queue Details |
| OPENSEARCH_ENDPOINT | OpenSearch domain endpoint | `https://search-domain.us-east-1.es.amazonaws.com` | OpenSearch Console → Domain Details |
| IAM_ROLE_ARN | OSI service role ARN | `arn:aws:iam::123456789012:role/OSI-ServiceRole` | IAM Console → Roles |
| PIPELINE_NAME | Unique pipeline name | `security-lake-osi-pipeline` | Choose a descriptive name |

## Step 2: Create IAM Service Role

Create an IAM role for OpenSearch Ingestion with the following trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "osis-pipelines.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Attach the following inline policy (replace placeholders):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::aws-security-data-lake-*/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "arn:aws:sqs:AWS_REGION:AWS_ACCOUNT_ID:*SecurityLake*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "es:ESHttpPut",
        "es:ESHttpPost"
      ],
      "Resource": "arn:aws:es:AWS_REGION:AWS_ACCOUNT_ID:domain/OPENSEARCH_DOMAIN_NAME/*"
    }
  ]
}
```

## Step 3: Configure the Pipeline

### Option A: Using the Template File

1. Copy the template file:
```bash
cp OSI-pipeline.template.yaml my-pipeline-config.yaml
```

2. Edit `my-pipeline-config.yaml` and replace all placeholders:
   - `<AWS_REGION>` - Your AWS region
   - `<AWS_ACCOUNT_ID>` - Your AWS account ID
   - `<SQS_QUEUE_NAME>` - Your Security Lake SQS queue name
   - `<IAM_ROLE_NAME>` - Your OSI service role name
   - `<OPENSEARCH_ENDPOINT>` - Your OpenSearch domain endpoint
   - `<PIPELINE_NAME>` - Your chosen pipeline name

### Option B: Manual Configuration

Create a new YAML file with the following structure (see `OSI-pipeline.template.yaml` for full template):

Key sections to configure:
- **Source**: SQS queue URL and region
- **AWS STS Role**: IAM role ARN for pipeline
- **Sink**: OpenSearch endpoint and region
- **Workers**: Number of parallel workers (default: 2)

## Step 4: Deploy the Pipeline

### Using AWS Console

1. Navigate to **Amazon OpenSearch Service** → **Ingestion** → **Pipelines**
2. Click **Create pipeline**
3. Choose **Blueprint**: Custom
4. Paste your configured YAML content
5. Set **Pipeline name**: Your chosen pipeline name
6. Configure **Network settings**:
   - VPC access: Choose if OpenSearch is in VPC
   - Public access: Choose if using public endpoint
7. Set **Compute capacity**:
   - Minimum OCUs: 2
   - Maximum OCUs: 4 (adjust based on data volume)
8. Review and click **Create pipeline**

### Using AWS CLI

```bash
aws osis create-pipeline \
  --region AWS_REGION \
  --pipeline-name PIPELINE_NAME \
  --min-units 2 \
  --max-units 4 \
  --pipeline-configuration-body file://my-pipeline-config.yaml
```

## Step 5: Verify Pipeline Operation

### Check Pipeline Status

```bash
aws osis get-pipeline \
  --pipeline-name PIPELINE_NAME \
  --region AWS_REGION
```

Expected status: `ACTIVE`

### Monitor Pipeline Metrics

1. Go to **OpenSearch Service** → **Ingestion** → **Pipelines** → Select your pipeline
2. Click **Monitoring** tab
3. Check metrics:
   - Records ingested
   - Record processing rate
   - Pipeline errors
   - SQS message processing

### Verify Data in OpenSearch

1. Navigate to OpenSearch Dashboards
2. Go to **Dev Tools** → **Console**
3. Run query to check indices:

```
GET _cat/indices/ocsf-*?v
```

4. Query sample data:

```
GET ocsf-*/_search
{
  "size": 10,
  "query": {
    "match_all": {}
  }
}
```

## Step 6: Import Dashboards

After data is flowing, import pre-built dashboards:

1. Navigate to **OpenSearch Dashboards** → **Management** → **Saved Objects**
2. Click **Import**
3. Select dashboard file:
   - `saved_objects/cross-cloud-security-dashboard.ndjson` (recommended)
   - `saved_objects/cross-cloud-threat-hunting-dashboard.ndjson`
   - `saved_objects/cross-cloud-network-dashboard.ndjson`
4. Click **Import**

See [saved_objects/README.md](saved_objects/README.md) for dashboard details.

## Configuration Details

### Processing Pipeline Explained

The pipeline performs the following transformations:

1. **Lowercase conversion**: Normalizes product names and class names
   ```yaml
   lowercase_string:
     with_keys: ["/metadata/product/name", "/class_name"]
   ```

2. **String trimming**: Removes whitespace from cloud provider field
   ```yaml
   trim_string:
     with_keys: ["/cloud/provider"]
   ```

3. **Grok pattern extraction**: Extracts cloud metadata from resource identifiers
   - AWS WAF: Extracts region and account from resource ARN
   - Amazon EKS: Extracts region and account from S3 key path
   
4. **Field manipulation**: Copies/deletes fields based on product type
   - CloudTrail: Copies account ID from unmapped fields
   - EKS: Removes cloud account field to allow re-extraction

5. **String substitution**: Cleans up data formatting
   - Replaces spaces with underscores in class names
   - Replaces hyphen placeholders with 0.0.0.0 for IP addresses

### Index Naming Strategy

Data is indexed dynamically based on OCSF class:
```
ocsf-1.1.0-${class_uid}-${class_name}
```

Examples:
- `ocsf-1.1.0-4002-http_activity` (HTTP Activity)
- `ocsf-1.1.0-2001-compliance_finding` (Compliance Finding)
- `ocsf-1.1.0-6003-api_activity` (API Activity)

This allows:
- Efficient querying by event type
- Separate retention policies per event class
- Optimized field mappings per schema

### Performance Tuning

Adjust these settings based on your data volume:

| Setting | Low Volume (<1GB/day) | Medium Volume (1-10GB/day) | High Volume (>10GB/day) |
|---------|----------------------|---------------------------|------------------------|
| Workers | 2 | 4 | 6-8 |
| Min OCUs | 2 | 4 | 8 |
| Max OCUs | 4 | 8 | 16 |
| Visibility Timeout | 600s | 900s | 1200s |

## Troubleshooting

### Pipeline Creation Fails

**Error**: "Invalid IAM role"
- Verify trust policy allows `osis-pipelines.amazonaws.com`
- Check role has required S3, SQS, and OpenSearch permissions
- Ensure role ARN is correct in YAML

**Error**: "Invalid SQS queue"
- Verify queue URL is correct
- Check queue exists in specified region
- Ensure queue is receiving Security Lake notifications

### No Data Flowing

**Check 1: SQS Messages**
```bash
aws sqs get-queue-attributes \
  --queue-url SQS_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages
```

If no messages, verify Security Lake is writing to S3 and EventBridge is triggering SQS.

**Check 2: Pipeline Logs**
1. Go to OpenSearch Ingestion → Pipelines → Select pipeline
2. Click **Monitoring** → **Logs**
3. Check for errors in CloudWatch Logs

**Check 3: S3 Bucket Access**
```bash
aws s3 ls s3://SECURITY_LAKE_BUCKET/ --profile YOUR_PROFILE
```

If access denied, update IAM role permissions.

### Data Not Appearing in OpenSearch

**Check 1: Index Creation**
```
GET _cat/indices?v
```

If no `ocsf-*` indices, check pipeline processing errors.

**Check 2: Field Mappings**
```
GET ocsf-*/_mapping
```

Verify fields match OCSF schema expectations.

**Check 3: Search Restrictions**
- Verify OpenSearch domain access policy allows pipeline role
- Check VPC settings if domain is VPC-enabled
- Ensure fine-grained access control (if enabled) grants permissions

### High Error Rate

**DLQ Processing**: Check SQS dead-letter queue
```bash
aws sqs get-queue-attributes \
  --queue-url DLQ_URL \
  --attribute-names ApproximateNumberOfMessages
```

**Common Causes**:
- Malformed Parquet files: Check S3 object integrity
- Schema mismatches: Verify OCSF schema version compatibility
- Resource limits: Increase OCUs or worker count

## Advanced Configuration

### Multiple Data Sources

To ingest from multiple Security Lake regions:

1. Create separate pipelines per region
2. Use region-specific naming: `pipeline-us-east-1`, `pipeline-eu-west-1`
3. Configure each with region-specific SQS queues

### Custom Processing Rules

Add custom processors for your use case:

```yaml
processor:
  # Enrich with custom fields
  - add_entries:
      entries:
        - key: "/unmapped/custom_field"
          value: "custom_value"
          
  # Filter out unwanted events
  - delete_entries:
      with_keys: ["/field_to_remove"]
      delete_when: '/severity_id < 40'  # Remove low severity
```

### OpenSearch Serverless

For serverless deployment, modify sink configuration:

```yaml
sink:
  - opensearch:
      hosts: ["https://COLLECTION_ID.REGION.aoss.amazonaws.com"]
      aws:
        serverless: true
        region: AWS_REGION
        sts_role_arn: IAM_ROLE_ARN
      index_type: custom
      index: "ocsf-1.1.0-${/class_uid}-${/class_name}"
```

## Cost Optimization

### OCU Sizing
- Start with minimum OCUs (2) and monitor performance
- Set max OCUs 2x minimum for burst capacity
- Review CloudWatch metrics weekly and adjust

### Data Lifecycle
- Implement Index State Management (ISM) policies
- Warm tier after 7 days (frequently accessed)
- Cold tier after 30 days (infrequent access)
- Delete after 90 days (compliance dependent)

Example ISM policy:
```json
{
  "policy": {
    "description": "OCSF data lifecycle",
    "default_state": "hot",
    "states": [
      {
        "name": "hot",
        "actions": [],
        "transitions": [
          {
            "state_name": "warm",
            "conditions": {
              "min_index_age": "7d"
            }
          }
        ]
      },
      {
        "name": "warm",
        "actions": [
          {
            "warm_migration": {}
          }
        ],
        "transitions": [
          {
            "state_name": "delete",
            "conditions": {
              "min_index_age": "90d"
            }
          }
        ]
      },
      {
        "name": "delete",
        "actions": [
          {
            "delete": {}
          }
        ]
      }
    ]
  }
}
```

## Security Best Practices

1. **Encryption in Transit**: Pipeline uses HTTPS for OpenSearch connections
2. **Encryption at Rest**: Enable OpenSearch domain encryption
3. **IAM Roles**: Use service roles with least privilege
4. **VPC Endpoints**: Deploy pipeline in VPC for private connectivity
5. **Access Logging**: Enable CloudTrail for pipeline API calls
6. **Network Security**: Use security groups to restrict OpenSearch access

## Support and Resources

- [OpenSearch Ingestion Documentation](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ingestion.html)
- [OCSF Schema Reference](https://schema.ocsf.io/)
- [Security Lake Documentation](https://docs.aws.amazon.com/security-lake/latest/userguide/)
- [Dashboard Documentation](saved_objects/README.md)

## Next Steps

After successful deployment:

1. Review ingested data in OpenSearch Dashboards
2. Customize dashboards for your security use cases
3. Set up alerting rules for critical findings
4. Configure data retention policies
5. Monitor pipeline performance and optimize as needed