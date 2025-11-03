© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Key and Secrets Rotation Guide

## Overview

This document provides comprehensive procedures for rotating encryption keys and secrets in the Security Lake Integration Framework. Following AWS security best practices, the framework implements automatic key rotation for KMS keys and documented procedures for manual secrets rotation.

## Table of Contents

- [KMS Key Rotation](#kms-key-rotation)
- [Secrets Manager Rotation](#secrets-manager-rotation)
- [Azure Integration Secrets](#azure-integration-secrets)
- [Google Cloud Integration Secrets](#google-cloud-integration-secrets)
- [Monitoring and Validation](#monitoring-and-validation)
- [Emergency Rotation Procedures](#emergency-rotation-procedures)

## KMS Key Rotation

### Automatic Rotation (Enabled by Default)

The framework automatically rotates KMS customer-managed keys (CMKs) annually. This is configured in the CDK stack:

```typescript
// From security-lake-stack.ts line 141
enableKeyRotation: this.config.encryption.keyRotationEnabled !== false
```

### Configuration

KMS key rotation is controlled in [`config.yaml`](../cdk/config.yaml):

```yaml
encryption:
  enabled: true
  keyType: CUSTOMER_MANAGED_CMK
  keyAlias: security-lake-integration
  keyRotationEnabled: true  # Default: true
  keyPendingWindowInDays: 30
```

### How Automatic Rotation Works

1. **Annual Schedule**: AWS automatically rotates the key material every 365 days
2. **Backward Compatibility**: Previous key versions are retained for decryption
3. **Transparent Operation**: No application changes or redeployment required
4. **Encrypted Data**: Existing encrypted data remains accessible using old key versions

### Verification

Check key rotation status:

```bash
# Get KMS key ID from stack outputs
KEY_ID=$(aws cloudformation describe-stacks \
  --stack-name <stack-name> \
  --query 'Stacks[0].Outputs[?OutputKey==`SharedKmsKeyArn`].OutputValue' \
  --output text | cut -d'/' -f2)

# Check rotation status
aws kms get-key-rotation-status --key-id $KEY_ID

# View key metadata
aws kms describe-key --key-id $KEY_ID
```

### Manual Key Rotation (Advanced)

If immediate manual rotation is required:

```bash
# Create new key
aws kms create-key \
  --description "Security Lake Integration - Manual Rotation" \
  --key-policy file://key-policy.json

# Update alias to point to new key
aws kms update-alias \
  --alias-name alias/security-lake-integration \
  --target-key-id <new-key-id>

# Schedule old key for deletion (optional, after validation period)
aws kms schedule-key-deletion \
  --key-id <old-key-id> \
  --pending-window-in-days 30
```

**WARNING**: Manual key rotation requires careful planning and may cause service disruption. Use automatic rotation instead.

## Secrets Manager Rotation

### Overview

Cloud provider credentials are stored in AWS Secrets Manager and must be manually rotated according to your organization's security policy and cloud provider requirements.

### Rotation Schedule Recommendations

| Secret Type | Recommended Frequency | Compliance Driver |
|-------------|----------------------|-------------------|
| Azure Service Principal | 90 days | Azure AD Policy |
| Azure Event Hub Connection | On compromise or annually | PCI-DSS, SOC 2 |
| Azure Storage Account Key | 90 days | CIS Azure Benchmark |
| Google Service Account Key | 90 days | GCP Best Practices |

### General Rotation Process

1. Generate new credentials in cloud provider console
2. Update AWS Secrets Manager secret
3. Verify new credentials work
4. Monitor for errors
5. Revoke old credentials after validation period

## Azure Integration Secrets

### Azure Event Hub Credentials

**Secret Name**: `azure-eventhub-credentials` (configurable in config.yaml)

**Rotation Procedure**:

1. **Generate New Connection String** (Azure Portal or CLI):
   ```bash
   # Create new Event Hub authorization rule
   az eventhubs eventhub authorization-rule create \
     --resource-group <resource-group> \
     --namespace-name <namespace> \
     --eventhub-name <eventhub-name> \
     --name <new-rule-name> \
     --rights Listen
   
   # Get new connection string
   az eventhubs eventhub authorization-rule keys list \
     --resource-group <resource-group> \
     --namespace-name <namespace> \
     --eventhub-name <eventhub-name> \
     --name <new-rule-name>
   ```

2. **Update Secrets Manager**:
   ```bash
   cd integrations/azure/microsoft_defender_cloud/scripts
   
   # Edit configure-secrets-manager.sh with new values:
   # - EVENT_HUB_NAMESPACE
   # - EVENT_HUB_NAME
   # - CONNECTION_STRING (new value)
   
   # Run configuration script
   ./configure-secrets-manager.sh
   ```

3. **Verify Integration**:
   ```bash
   # Check CloudWatch Logs for Event Hub Processor
   aws logs tail /aws/lambda/<stack-name>-EventHubProcessor --follow
   ```

4. **Revoke Old Credentials** (after 24-48 hour validation):
   ```bash
   az eventhubs eventhub authorization-rule delete \
     --resource-group <resource-group> \
     --namespace-name <namespace> \
     --eventhub-name <eventhub-name> \
     --name <old-rule-name>
   ```

### Azure Storage Account Credentials (Flow Logs)

**Secret Name**: `azure-flowlogs-credentials` (configurable in config.yaml)

**Rotation Procedure**:

1. **Generate New Service Principal Secret**:
   ```bash
   # Create new client secret for existing service principal
   az ad app credential reset \
     --id <app-id> \
     --append \
     --display-name "Security Lake Integration - $(date +%Y%m%d)"
   ```

2. **Update Secrets Manager**:
   ```bash
   # Get secret value template
   aws secretsmanager get-secret-value \
     --secret-id azure-flowlogs-credentials \
     --query SecretString \
     --output text > secret-template.json
   
   # Edit secret-template.json with new clientSecret
   
   # Update secret
   aws secretsmanager update-secret \
     --secret-id azure-flowlogs-credentials \
     --secret-string file://secret-template.json
   
   # Clean up
   rm secret-template.json
   ```

3. **Verify Flow Log Processing**:
   ```bash
   # Trigger flow log processor
   aws lambda invoke \
     --function-name <stack-name>-FlowLogProcessor \
     --payload '{"test": true}' \
     response.json
   
   # Check logs
   aws logs tail /aws/lambda/<stack-name>-FlowLogProcessor --follow
   ```

4. **Remove Old Secret** (after validation):
   ```bash
   # List all credentials for the app
   az ad app credential list --id <app-id>
   
   # Delete old credential by keyId
   az ad app credential delete \
     --id <app-id> \
     --key-id <old-key-id>
   ```

## Google Cloud Integration Secrets

### Service Account Key Rotation

**Secret Name**: `gcp-pubsub-credentials` (configurable in config.yaml)

**Rotation Procedure**:

1. **Create New Service Account Key**:
   ```bash
   # Create new key for existing service account
   gcloud iam service-accounts keys create new-key.json \
     --iam-account=<service-account-email>
   
   # Verify key creation
   gcloud iam service-accounts keys list \
     --iam-account=<service-account-email>
   ```

2. **Update Secrets Manager**:
   ```bash
   cd integrations/google_security_command_center/scripts
   
   # Run configuration script with new key file
   ./configure-secrets-manager.sh
   # When prompted, provide path to new-key.json
   ```

3. **Verify Integration**:
   ```bash
   # Check Pub/Sub Poller Lambda logs
   aws logs tail /aws/lambda/<stack-name>-PubSubPoller --follow
   ```

4. **Delete Old Service Account Key**:
   ```bash
   # List keys
   gcloud iam service-accounts keys list \
     --iam-account=<service-account-email>
   
   # Delete old key (after validation period)
   gcloud iam service-accounts keys delete <old-key-id> \
     --iam-account=<service-account-email>
   
   # Verify deletion
   gcloud iam service-accounts keys list \
     --iam-account=<service-account-email>
   ```

## Monitoring and Validation

### Pre-Rotation Checklist

- [ ] Document current secret versions and rotation date
- [ ] Verify backup and rollback procedures
- [ ] Schedule rotation during maintenance window
- [ ] Notify operations team
- [ ] Prepare monitoring dashboards

### Post-Rotation Validation

1. **Check Lambda Function Metrics**:
   ```bash
   # Check for invocation errors
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Errors \
     --dimensions Name=FunctionName,Value=<function-name> \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Sum
   ```

2. **Verify Dead Letter Queue**:
   ```bash
   # Check DLQ message count
   aws sqs get-queue-attributes \
     --queue-url <dlq-url> \
     --attribute-names ApproximateNumberOfMessages
   ```

3. **Review CloudWatch Logs**:
   ```bash
   # Search for authentication errors
   aws logs filter-log-events \
     --log-group-name /aws/lambda/<function-name> \
     --start-time $(date -u -d '1 hour ago' +%s)000 \
     --filter-pattern "ERROR"
   ```

4. **Test End-to-End Flow**:
   - Verify events flowing from source to Security Lake
   - Check Security Hub findings if enabled
   - Validate OCSF event format in S3

### Monitoring Dashboards

Create CloudWatch dashboard to monitor rotation impact:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name SecurityLakeIntegrationHealth \
  --dashboard-body file://dashboard-config.json
```

## Emergency Rotation Procedures

### Compromised Credentials

If credentials are compromised:

1. **Immediate Action** (within 1 hour):
   ```bash
   # Disable Lambda functions
   aws lambda update-function-configuration \
     --function-name <function-name> \
     --environment Variables={}
   
   # Or delete secret to force failure
   aws secretsmanager delete-secret \
     --secret-id <secret-name> \
     --force-delete-without-recovery
   ```

2. **Generate New Credentials** (within 2 hours):
   - Follow cloud provider procedures above
   - Use different credential names
   - Document incident

3. **Update and Restore** (within 4 hours):
   - Update Secrets Manager with new credentials
   - Re-enable Lambda functions
   - Monitor closely for 24 hours

4. **Post-Incident**:
   - Complete incident report
   - Review access logs
   - Update rotation schedule if needed
   - Conduct security review

### Rollback Procedure

If rotation causes issues:

1. **Quick Rollback** (if within validation period):
   ```bash
   # Restore previous secret version
   aws secretsmanager update-secret-version-stage \
     --secret-id <secret-name> \
     --version-stage AWSCURRENT \
     --move-to-version-id <previous-version-id>
   ```

2. **Verify Rollback**:
   ```bash
   # Check Lambda functions resume normal operation
   aws logs tail /aws/lambda/<function-name> --follow
   ```

3. **Document Rollback**:
   - Record reason for rollback
   - Identify root cause of rotation failure
   - Update procedures before next attempt

## Best Practices

### General

1. **Always test in non-production first**
2. **Rotate during maintenance windows**
3. **Keep old credentials valid during validation period**
4. **Document all rotations in change management system**
5. **Monitor for 24-48 hours after rotation**

### KMS Keys

1. **Never disable automatic rotation** in production
2. **Use separate keys per environment** (dev/staging/prod)
3. **Monitor key usage with CloudTrail**
4. **Set up CloudWatch alarms for key deletion**

### Secrets Manager

1. **Use strong, unique passwords/keys**
2. **Enable secret versioning**
3. **Implement least privilege access to secrets**
4. **Audit secret access regularly**
5. **Use resource policies to restrict access**

### Cloud Provider Credentials

1. **Follow cloud provider security best practices**
2. **Use service principals/service accounts** (not user credentials)
3. **Implement conditional access policies where possible**
4. **Review and minimize permissions regularly**
5. **Enable MFA on cloud provider accounts**

## Compliance Considerations

### Audit Trail

All key and secret rotations should maintain:

- Date and time of rotation
- Person/system performing rotation
- Old and new credential identifiers (not values)
- Validation results
- Any issues encountered

### Retention Requirements

- CloudTrail logs: Minimum 90 days
- Secret versions: Retain for audit period
- Rotation documentation: Per compliance requirements

### Reporting

Generate quarterly rotation reports:

```bash
# Example: List all secrets and last rotation date
aws secretsmanager list-secrets \
  --query 'SecretList[*].[Name,LastRotatedDate]' \
  --output table
```

## References

- [AWS KMS Key Rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html)
- [AWS Secrets Manager Rotation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [Azure Service Principal Best Practices](https://docs.microsoft.com/en-us/azure/active-directory/develop/howto-create-service-principal-portal)
- [GCP Service Account Key Management](https://cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys)
- [CIS AWS Foundations Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services)

## Change Log

### Version 1.0.0 (2025-10-28)
- Initial key rotation guide
- Documented automatic KMS rotation
- Added manual rotation procedures for all integrations
- Included monitoring and validation steps
- Added emergency rotation procedures