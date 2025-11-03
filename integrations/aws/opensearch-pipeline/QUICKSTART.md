# OpenSearch Pipeline Quick Start

This quick start guide helps you deploy an OpenSearch Ingestion pipeline for Security Lake data in under 30 minutes.

## Prerequisites Check

Before starting, verify you have:
- [ ] AWS Security Lake configured and receiving data
- [ ] OpenSearch domain (managed or serverless) deployed
- [ ] AWS CLI installed and configured
- [ ] Permissions to create IAM roles and OSI pipelines

## Deployment Steps

### Step 1: Get Your Configuration Values (5 minutes)

Run these commands to gather required information:

```bash
# Get your AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $AWS_ACCOUNT_ID"

# Get your region (adjust if needed)
AWS_REGION=$(aws configure get region)
echo "Region: $AWS_REGION"

# List Security Lake SQS queues
aws sqs list-queues --region $AWS_REGION \
  --queue-name-prefix "AmazonSecurityLake" \
  --query 'QueueUrls[]' --output table

# List OpenSearch domains
aws opensearch list-domain-names --region $AWS_REGION \
  --query 'DomainNames[].DomainName' --output table
```

Record these values:
- AWS Account ID: `________________`
- AWS Region: `________________`
- SQS Queue Name: `________________`
- OpenSearch Domain: `________________`

### Step 2: Create IAM Role (5 minutes)

Create the service role with proper permissions:

```bash
# Set your variables
AWS_ACCOUNT_ID="YOUR_ACCOUNT_ID"
AWS_REGION="YOUR_REGION"
OPENSEARCH_DOMAIN="YOUR_DOMAIN_NAME"

# Create trust policy
cat > /tmp/osi-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "osis-pipelines.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name OSI-SecurityLake-ServiceRole \
  --assume-role-policy-document file:///tmp/osi-trust-policy.json

# Create permissions policy
cat > /tmp/osi-permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::aws-security-data-lake-*/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "arn:aws:sqs:${AWS_REGION}:${AWS_ACCOUNT_ID}:*SecurityLake*"
    },
    {
      "Effect": "Allow",
      "Action": ["es:ESHttpPut", "es:ESHttpPost"],
      "Resource": "arn:aws:es:${AWS_REGION}:${AWS_ACCOUNT_ID}:domain/${OPENSEARCH_DOMAIN}/*"
    }
  ]
}
EOF

# Attach permissions
aws iam put-role-policy \
  --role-name OSI-SecurityLake-ServiceRole \
  --policy-name OSI-Permissions \
  --policy-document file:///tmp/osi-permissions.json

echo "IAM Role ARN: arn:aws:iam::${AWS_ACCOUNT_ID}:role/OSI-SecurityLake-ServiceRole"
```

### Step 3: Configure Pipeline (5 minutes)

```bash
# Copy template
cp OSI-pipeline.template.yaml my-pipeline.yaml

# Edit configuration (use your favorite editor)
# Replace these placeholders:
#   <AWS_REGION>
#   <AWS_ACCOUNT_ID>
#   <SQS_QUEUE_NAME>
#   <IAM_ROLE_NAME>
#   <OPENSEARCH_ENDPOINT>
#   <PIPELINE_NAME>

# Quick sed replacements (adjust values):
sed -i '' "s/<AWS_REGION>/${AWS_REGION}/g" my-pipeline.yaml
sed -i '' "s/<AWS_ACCOUNT_ID>/${AWS_ACCOUNT_ID}/g" my-pipeline.yaml
sed -i '' "s/<SQS_QUEUE_NAME>/YOUR_QUEUE_NAME/g" my-pipeline.yaml
sed -i '' "s/<IAM_ROLE_NAME>/OSI-SecurityLake-ServiceRole/g" my-pipeline.yaml
sed -i '' "s|<OPENSEARCH_ENDPOINT>|YOUR_OPENSEARCH_ENDPOINT|g" my-pipeline.yaml
sed -i '' "s/<PIPELINE_NAME>/security-lake-ingestion/g" my-pipeline.yaml
```

### Step 4: Deploy Pipeline (10 minutes)

```bash
# Create pipeline
aws osis create-pipeline \
  --pipeline-name security-lake-osi \
  --min-units 2 \
  --max-units 4 \
  --pipeline-configuration-body file://my-pipeline.yaml \
  --region $AWS_REGION

# Monitor deployment
aws osis get-pipeline \
  --pipeline-name security-lake-osi \
  --region $AWS_REGION \
  --query 'Pipeline.Status.Status' \
  --output text
```

Wait for status to show `ACTIVE` (typically 5-10 minutes).

### Step 5: Verify Data Flow (5 minutes)

Check that data is flowing:

```bash
# Check pipeline metrics
aws osis get-pipeline-change-progress \
  --pipeline-name security-lake-osi \
  --region $AWS_REGION

# Verify OpenSearch indices (requires OpenSearch endpoint access)
curl -XGET "YOUR_OPENSEARCH_ENDPOINT/_cat/indices/ocsf-*?v" -u admin:password
```

Expected output: List of OCSF indices with document counts.

### Step 6: Import Dashboards (5 minutes)

1. Navigate to OpenSearch Dashboards
2. Go to Management → Saved Objects
3. Click Import
4. Select `saved_objects/cross-cloud-security-dashboard.ndjson`
5. Click Import
6. Navigate to Dashboards → Cross-Cloud Security Dashboard

## Common Issues

### Pipeline stuck in CREATING
**Solution**: Check IAM role trust policy allows `osis-pipelines.amazonaws.com`

### No data appearing
**Solution**: Verify SQS queue has messages:
```bash
aws sqs get-queue-attributes \
  --queue-url YOUR_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages
```

### OpenSearch access denied
**Solution**: Update OpenSearch domain access policy to allow IAM role:
```json
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::ACCOUNT:role/OSI-SecurityLake-ServiceRole"
  },
  "Action": "es:*",
  "Resource": "arn:aws:es:REGION:ACCOUNT:domain/DOMAIN/*"
}
```

### High costs
**Solution**: Reduce OCU allocation:
```bash
aws osis update-pipeline \
  --pipeline-name security-lake-osi \
  --min-units 2 \
  --max-units 2
```

## Next Steps

After successful deployment:

1. **Review Data**: Check OpenSearch Dashboards for ingested events
2. **Customize Dashboards**: Modify visualizations for your use case
3. **Set Alerts**: Configure alerting for critical security findings
4. **Optimize Performance**: Monitor metrics and adjust OCUs as needed
5. **Data Retention**: Configure Index State Management policies

## Full Documentation

For detailed information:
- [Complete Setup Guide](SETUP_GUIDE.md)
- [Dashboard Documentation](saved_objects/README.md)
- [Configuration Template](OSI-pipeline.template.yaml)

## Cost Estimate

Typical monthly costs (us-east-1 prices):

| Component | Usage | Monthly Cost |
|-----------|-------|--------------|
| OSI Pipeline (2 OCUs) | 24/7 | ~$480 |
| OpenSearch (2 nodes, r6g.large) | 24/7 | ~$300 |
| S3 Storage (Security Lake) | 100GB | ~$2 |
| Data Transfer | Minimal | ~$10 |
| **Total** | | **~$792** |

Costs scale with:
- Data volume (OCU count)
- OpenSearch instance size
- Data retention period

## Support

For issues or questions:
- AWS OpenSearch Support
- AWS Security Lake Documentation
- Project GitHub Issues