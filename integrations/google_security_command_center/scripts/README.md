# GCP Security Command Center Integration - Automation Scripts

This directory contains automation scripts for configuring and managing the GCP Security Command Center integration with AWS Security Lake.

## Available Scripts

### configure-secrets-manager.sh

Automates the configuration of AWS Secrets Manager with GCP service account credentials required for the Pub/Sub integration.

**Purpose:**
- Creates or updates AWS Secrets Manager secret with GCP credentials
- Validates service account key format
- Verifies secret configuration

**Usage:**

```bash
./configure-secrets-manager.sh \
  --secret-name "gcp-scc-pubsub-credentials-dev" \
  --gcp-project-id "your-gcp-project-id" \
  --gcp-subscription-id "scc-findings-aws-subscription" \
  --gcp-topic-id "scc-findings-topic" \
  --service-account-key "/path/to/gcp-sa-key.json" \
  --region "us-east-1"
```

**Options:**

| Option | Required | Description |
|--------|----------|-------------|
| `--secret-name` | Yes | AWS Secrets Manager secret name |
| `--gcp-project-id` | Yes | GCP project ID |
| `--gcp-subscription-id` | Yes | GCP Pub/Sub subscription ID |
| `--gcp-topic-id` | Yes | GCP Pub/Sub topic ID |
| `--service-account-key` | Yes | Path to GCP service account JSON key file |
| `--region` | Yes | AWS region |
| `--dry-run` | No | Validate inputs without making changes |
| `--verbose` | No | Enable verbose output |
| `-h, --help` | No | Display help message |

**Examples:**

1. **Basic configuration:**
   ```bash
   ./configure-secrets-manager.sh \
     --secret-name "gcp-scc-pubsub-credentials-dev" \
     --gcp-project-id "my-gcp-project" \
     --gcp-subscription-id "scc-findings-sub" \
     --gcp-topic-id "scc-findings-topic" \
     --service-account-key "./gcp-sa-key.json" \
     --region "us-east-1"
   ```

2. **Dry run (validate without making changes):**
   ```bash
   ./configure-secrets-manager.sh \
     --dry-run \
     --secret-name "gcp-scc-pubsub-credentials-dev" \
     --gcp-project-id "my-gcp-project" \
     --gcp-subscription-id "scc-findings-sub" \
     --gcp-topic-id "scc-findings-topic" \
     --service-account-key "./gcp-sa-key.json" \
     --region "us-east-1"
   ```

3. **Verbose output for debugging:**
   ```bash
   ./configure-secrets-manager.sh \
     --verbose \
     --secret-name "gcp-scc-pubsub-credentials-dev" \
     --gcp-project-id "my-gcp-project" \
     --gcp-subscription-id "scc-findings-sub" \
     --gcp-topic-id "scc-findings-topic" \
     --service-account-key "./gcp-sa-key.json" \
     --region "us-east-1"
   ```

4. **Using Terraform outputs:**
   ```bash
   cd ../terraform
   
   ./configure-secrets-manager.sh \
     --secret-name "gcp-scc-pubsub-credentials-prod" \
     --gcp-project-id "$(terraform output -raw project_id)" \
     --gcp-subscription-id "$(terraform output -raw pubsub_subscription_id)" \
     --gcp-topic-id "$(terraform output -raw pubsub_topic_id)" \
     --service-account-key "gcp-sa-key.json" \
     --region "us-east-1"
   ```

**Prerequisites:**

1. **AWS CLI** installed and configured:
   ```bash
   aws --version
   aws configure
   ```

2. **jq** installed (for JSON parsing):
   ```bash
   # macOS
   brew install jq
   
   # Ubuntu/Debian
   sudo apt-get install jq
   
   # Amazon Linux
   sudo yum install jq
   ```

3. **GCP Service Account Key:**
   - Downloaded from GCP Console or Terraform output
   - Valid JSON format
   - Contains all required fields

4. **AWS Permissions:**
   - `secretsmanager:CreateSecret`
   - `secretsmanager:UpdateSecret`
   - `secretsmanager:DescribeSecret`
   - `secretsmanager:GetSecretValue`
   - `secretsmanager:TagResource`

**Secret Structure:**

The script creates a secret with the following JSON structure:

```json
{
  "projectId": "your-gcp-project-id",
  "subscriptionId": "scc-findings-aws-subscription",
  "topicId": "scc-findings-topic",
  "serviceAccountKey": {
    "type": "service_account",
    "project_id": "your-gcp-project",
    "private_key_id": "...",
    "private_key": "...n",
    "client_email": "aws-integration@your-project.iam.gserviceaccount.com",
    "client_id": "...",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "..."
  }
}
```

**Validation:**

The script performs the following validations:

1. **Dependency Check:**
   - AWS CLI installed
   - jq installed

2. **Input Validation:**
   - All required parameters provided
   - Service account key file exists
   - Key file is valid JSON

3. **AWS Credential Check:**
   - AWS credentials configured
   - Credentials have necessary permissions

4. **Secret Verification:**
   - Secret can be retrieved
   - JSON structure is valid
   - All required fields present

**Error Handling:**

The script exits with appropriate error codes:

- `0` - Success
- `1` - Validation error, missing dependencies, or AWS operation failure

**Troubleshooting:**

1. **Missing AWS CLI:**
   ```
   [ERROR] Missing required dependencies: aws-cli
   ```
   **Solution:** Install AWS CLI from https://aws.amazon.com/cli/

2. **Missing jq:**
   ```
   [ERROR] Missing required dependencies: jq
   ```
   **Solution:** Install jq using your package manager

3. **Invalid JSON key:**
   ```
   [ERROR] Service account key file is not valid JSON
   ```
   **Solution:** Verify the key file with `cat key.json | jq .`

4. **AWS Permission denied:**
   ```
   [ERROR] Failed to create secret 'gcp-scc-pubsub-credentials-dev'
   ```
   **Solution:** Verify AWS credentials have Secrets Manager permissions

5. **File not found:**
   ```
   [ERROR] Service account key file not found: ./gcp-sa-key.json
   ```
   **Solution:** Check the path to the service account key file

## Workflow Integration

### With Terraform Deployment

After deploying GCP infrastructure with Terraform:

```bash
# 1. Navigate to Terraform directory
cd ../terraform

# 2. Extract service account key
terraform output -raw service_account_key > gcp-sa-key.json
chmod 600 gcp-sa-key.json

# 3. Run configuration script
cd ../scripts
./configure-secrets-manager.sh \
  --secret-name "gcp-scc-pubsub-credentials-prod" \
  --gcp-project-id "$(cd ../terraform && terraform output -raw project_id)" \
  --gcp-subscription-id "$(cd ../terraform && terraform output -raw pubsub_subscription_id)" \
  --gcp-topic-id "$(cd ../terraform && terraform output -raw pubsub_topic_id)" \
  --service-account-key "../terraform/gcp-sa-key.json" \
  --region "us-east-1"

# 4. Clean up local key file
rm ../terraform/gcp-sa-key.json
```

### With CDK Deployment

After deploying AWS infrastructure with CDK:

```bash
# 1. Get secret name from CDK outputs
SECRET_NAME=$(aws cloudformation describe-stacks \
  --stack-name GcpSccSecurityLakeStack \
  --query 'Stacks[0].Outputs[?OutputKey==`SecretName`].OutputValue' \
  --output text)

# 2. Run configuration script
./configure-secrets-manager.sh \
  --secret-name "$SECRET_NAME" \
  --gcp-project-id "your-gcp-project" \
  --gcp-subscription-id "scc-findings-sub" \
  --gcp-topic-id "scc-findings-topic" \
  --service-account-key "./gcp-sa-key.json" \
  --region "us-east-1"
```

## Security Best Practices

1. **Service Account Key Protection:**
   ```bash
   # Set restrictive permissions on key files
   chmod 600 gcp-sa-key.json
   
   # Never commit keys to version control
   echo "*.json" >> .gitignore
   echo "gcp-sa-key*" >> .gitignore
   ```

2. **Secure Key Storage:**
   - Delete local copies after uploading to Secrets Manager
   - Rotate keys regularly (at least annually)
   - Use separate service accounts for dev/staging/prod

3. **Audit Trail:**
   ```bash
   # Enable CloudTrail for Secrets Manager operations
   aws cloudtrail lookup-events \
     --lookup-attributes AttributeKey=ResourceName,AttributeValue=$SECRET_NAME \
     --max-results 10
   ```

4. **Access Control:**
   ```bash
   # Restrict secret access to specific Lambda execution role
   aws secretsmanager put-resource-policy \
     --secret-id $SECRET_NAME \
     --resource-policy file://policy.json
   ```

## Verification

After running the configuration script:

1. **Verify secret exists:**
   ```bash
   aws secretsmanager describe-secret \
     --secret-id gcp-scc-pubsub-credentials-dev \
     --region us-east-1
   ```

2. **Retrieve and validate secret (careful with credentials):**
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id gcp-scc-pubsub-credentials-dev \
     --region us-east-1 \
     --query 'SecretString' \
     --output text | jq .
   ```

3. **Test Lambda can access secret:**
   ```bash
   aws lambda invoke \
     --function-name gcp-scc-pubsub-poller-dev \
     --region us-east-1 \
     response.json
   
   cat response.json
   ```

## Maintenance

### Rotating Service Account Keys

```bash
# 1. Create new key in GCP
gcloud iam service-accounts keys create new-key.json \
  --iam-account=aws-integration@PROJECT_ID.iam.gserviceaccount.com

# 2. Update secret with new key
./configure-secrets-manager.sh \
  --secret-name "gcp-scc-pubsub-credentials-prod" \
  --gcp-project-id "your-gcp-project" \
  --gcp-subscription-id "scc-findings-sub" \
  --gcp-topic-id "scc-findings-topic" \
  --service-account-key "new-key.json" \
  --region "us-east-1"

# 3. Test with new key
aws lambda invoke \
  --function-name gcp-scc-pubsub-poller-prod \
  response.json

# 4. Delete old key in GCP Console
# 5. Delete local key file
rm new-key.json
```

### Updating Configuration

To update GCP project ID, subscription ID, or topic ID:

```bash
./configure-secrets-manager.sh \
  --secret-name "gcp-scc-pubsub-credentials-prod" \
  --gcp-project-id "new-gcp-project" \
  --gcp-subscription-id "new-subscription" \
  --gcp-topic-id "new-topic" \
  --service-account-key "./gcp-sa-key.json" \
  --region "us-east-1"
```

## Troubleshooting Common Issues

### Issue: Script hangs or times out

**Cause:** AWS CLI waiting for credentials or network issues

**Solution:**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Test AWS connectivity
aws secretsmanager list-secrets --region us-east-1 --max-results 1
```

### Issue: Permission denied errors

**Cause:** Insufficient AWS IAM permissions

**Solution:**
```bash
# Check current permissions
aws sts get-caller-identity

# Required IAM policy
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:UpdateSecret",
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:TagResource"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:gcp-scc-*"
    }
  ]
}
```

### Issue: Invalid JSON in service account key

**Cause:** Corrupted or incorrectly formatted key file

**Solution:**
```bash
# Validate JSON
cat gcp-sa-key.json | jq .

# Re-download key from GCP
gcloud iam service-accounts keys create gcp-sa-key.json \
  --iam-account=SERVICE_ACCOUNT_EMAIL
```

## Additional Resources

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [GCP Service Account Keys](https://cloud.google.com/iam/docs/creating-managing-service-account-keys)
- [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [jq Manual](https://stedolan.github.io/jq/manual/)

## Support

For issues or questions:
- Check the [main README](../README.md) for overall documentation
- Review [CDK DEPLOYMENT_GUIDE](../cdk/DEPLOYMENT_GUIDE.md) for deployment steps
- Open an issue in the project repository