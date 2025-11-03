# Microsoft Defender for Cloud - Configuration Scripts

## configure-secrets-manager.sh

Automated script that configures AWS Secrets Manager with Azure Event Hub credentials extracted from Terraform outputs.

### What It Does
1. Extracts Azure Event Hub connection details from Terraform outputs
2. Retrieves AWS Secrets Manager secret name from CDK outputs  
3. Automatically updates Secrets Manager with Azure credentials
4. Provides clear success/error feedback

### Prerequisites
- Terraform applied successfully (terraform.tfstate exists)
- CDK stack deployed successfully
- AWS CLI configured with appropriate permissions
- `jq` installed for JSON processing

### Usage
```bash
# Navigate to the scripts directory
cd integrations/azure/microsoft_defender_cloud/scripts

# Run the configuration script
./configure-secrets-manager.sh
```

### Expected Output
```
Microsoft Defender - Secrets Manager Configuration
==================================================================
Checking required tools...
Changed to Terraform directory: .../terraform
Extracting Azure Event Hub configuration from Terraform...
Azure Event Hub configuration extracted:
   • Namespace: mdc-integration-dev-dev-ehns-canadacentral
   • Event Hub: securesight-dev-events
   • Consumer Group: $Default
   • Connection String: [REDACTED for security]
Changed to CDK directory: .../cdk
Extracting AWS Secrets Manager configuration from CDK...
AWS Secrets Manager configuration found:
   • Secret Name: AzureEventHubCredentials3FF-QKhlpY7Djghw
   • AWS Region: ca-central-1
Updating AWS Secrets Manager with Azure Event Hub credentials...
AWS Secrets Manager successfully configured!

Configuration Summary:
   • Secret Name: AzureEventHubCredentials3FF-QKhlpY7Djghw
   • Event Hub: mdc-integration-dev-dev-ehns-canadacentral/securesight-dev-events
   • Consumer Group: $Default
   • AWS Region: ca-central-1

Ready for Lambda function deployment and testing!

Next Steps:
1. Verify Lambda functions are processing events correctly
2. Monitor CloudWatch logs for both Event Hub Processor and Event Transformer
3. Test integration: Check CloudTrail Event Data Store for transformed events
4. Validate end-to-end flow: Azure Event Hub → SQS → CloudTrail
==================================================================
```

### Error Handling
The script includes comprehensive error checking for:
- Missing required tools (terraform, aws, jq)
- Missing terraform.tfstate file
- Missing Terraform outputs
- Missing CDK stack or outputs
- AWS CLI authentication issues

### Security
- Connection strings are redacted in console output for security
- Uses secure JSON parsing to prevent injection attacks
- Validates all inputs before AWS API calls