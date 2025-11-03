# Flow Log Processor Lambda

AWS Lambda function that processes Azure VNet Flow Log blob creation events, downloads flow log data from Azure Storage, transforms to OCSF Network Activity format, and writes to AWS Security Lake as Parquet files.

## Overview

This Lambda function provides production-ready processing of Azure VNet Flow Logs for unified network visibility in AWS Security Lake. It integrates with Azure Event Grid to receive real-time blob creation notifications and processes flow logs using the OCSF (Open Cybersecurity Schema Framework) v1.0.0 standard.

## Architecture

### Event Flow

```
Azure NSG Flow Log Created
  → Azure Storage Account (PT1H.json files)
  → Event Grid (Microsoft.Storage.BlobCreated)
  → Azure EventHub
  → Event Transformer Lambda (detection + routing)
  → Flow Log SQS Queue
  → Flow Log Processor Lambda (THIS FUNCTION)
  → Security Lake S3 (OCSF Parquet files)
```

### Key Features

- **Azure Storage Integration**: Service principal authentication for secure blob access
- **OCSF Transformation**: Converts NSG flow logs to OCSF Network Activity (Class UID 4001)
- **Parquet Output**: Writes to Security Lake S3 with proper partitioning
- **Batch Processing**: Handles multiple flow log blobs efficiently
- **Error Handling**: DLQ routing for failed transformations with SQS retry logic

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_REGION` | Yes | AWS region for Lambda execution |
| `LOGGING_LEVEL` | No | Log level (INFO recommended, DEBUG for troubleshooting) |
| `AZURE_FLOWLOG_CREDENTIALS_SECRET_NAME` | Yes | Secrets Manager secret containing Azure credentials |
| `SECURITY_LAKE_S3_BUCKET` | Yes | Security Lake S3 bucket name |
| `SECURITY_LAKE_PATH` | No | S3 path prefix for Security Lake data |
| `SECURITY_LAKE_ENABLED` | No | Enable/disable Security Lake write (default: true) |

### CDK Configuration

Configured in main stack [`config.yaml`](../../config.yaml):

```yaml
coreProcessing:
  flowLogProcessor:
    enabled: true
    functionName: azure-flowlog-processor
    runtime: python3.13
    memorySize: 1024
    timeout: 600
    reservedConcurrentExecutions: 5
    batchSize: 10
    maximumBatchingWindowInSeconds: 5
    environment:
      LOGGING_LEVEL: INFO
      SECURITY_LAKE_ENABLED: true
```

### Azure Credentials Secret Format

The secret in AWS Secrets Manager must contain:

```json
{
  "tenantId": "azure-tenant-id",
  "clientId": "app-registration-client-id",
  "clientSecret": "app-registration-client-secret",
  "subscriptionId": "azure-subscription-id",
  "storageAccountName": "flowlogsstorageaccount",
  "storageAccountResourceId": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Storage/storageAccounts/{name}"
}
```

## Components

### Main Handler ([`app.py`](app.py))

**Purpose**: Lambda entry point and orchestration

**Key Functions**:
- `lambda_handler()`: Main Lambda handler, processes SQS batch
- `parse_event_grid_event()`: Extracts Event Grid BlobCreated events
- `extract_blob_info()`: Parses Azure Storage container and blob details
- `extract_subscription_id()`: Extracts subscription ID for partitioning
- `process_flow_log_blob()`: Orchestrates download, transform, and write operations

**Processing Logic**:
1. Receives SQS messages containing Event Grid events
2. Validates event type is Microsoft.Storage.BlobCreated
3. Extracts blob container and name from event subject
4. Downloads blob content from Azure Storage
5. Transforms JSON flow log to OCSF records
6. Writes OCSF records to Security Lake as Parquet
7. Returns batch item failures for SQS retry

### Azure Blob Client ([`helpers/azure_blob_client.py`](helpers/azure_blob_client.py))

**Purpose**: Azure Storage authentication and blob operations

**Key Features**:
- Service principal (ClientSecretCredential) authentication
- Blob download with error handling
- Blob listing capabilities

**Methods**:
- `__init__()`: Initialize with Azure AD credentials
- `download_blob()`: Download blob content as bytes
- `list_blobs()`: List blobs in container with optional prefix

### Flow Log Transformer ([`helpers/flow_log_transformer.py`](helpers/flow_log_transformer.py))

**Purpose**: Transform Azure NSG Flow Logs to OCSF Network Activity format

**OCSF Mapping**:
- **Class**: Network Activity (4001)
- **Category**: Network Activity (4)
- **Flow States**: B(Begin)=Open, C(Continue)=Traffic, E(End)=Reset, D(Deny)=Refuse
- **Protocols**: 6=TCP, 17=UDP
- **Direction**: I=Inbound, O=Outbound

**Key Methods**:
- `parse_flow_tuple()`: Parse comma-separated flow tuple string
- `convert_tuple_to_ocsf()`: Convert single tuple to OCSF event
- `transform_to_ocsf()`: Transform complete flow log with all tuples

**Flow Tuple Format**:
```
timestamp,src_ip,dest_ip,src_port,dest_port,protocol,direction,flow_state,encryption,packets_out,bytes_out,packets_in,bytes_in
```

### Security Lake Client ([`helpers/security_lake_client.py`](helpers/security_lake_client.py))

**Purpose**: Write OCSF records to Security Lake S3 as Parquet

**Key Features**:
- PyArrow-based Parquet generation
- Security Lake partitioning (region/accountid/eventday)
- GZIP compression for storage efficiency
- Batch writing for optimal performance

**Methods**:
- `write_ocsf_records()`: Write batch of OCSF records to S3
- `_create_parquet_file()`: Generate Parquet file from OCSF records
- `_get_partition_path()`: Calculate Security Lake partition path

## Azure NSG Flow Log Structure

### Input Format

Azure NSG Flow Logs are JSON files with this structure:

```json
{
  "records": [
    {
      "time": "2024-01-15T10:30:00.000Z",
      "flowLogGUID": "uuid",
      "macAddress": "00:0D:3A:1B:C0:9E",
      "category": "NetworkSecurityGroupFlowEvent",
      "flowLogResourceID": "/SUBSCRIPTIONS/.../FLOWLOGS/...",
      "targetResourceID": "/SUBSCRIPTIONS/.../NETWORKINTERFACES/...",
      "operationName": "NetworkSecurityGroupFlowEvents",
      "flowLogVersion": 4,
      "flowRecords": {
        "flows": [
          {
            "aclID": "/SUBSCRIPTIONS/.../NETWORKSECURITYGROUPS/.../SECURITYRULES/...",
            "flowGroups": [
              {
                "rule": "DefaultRule_AllowInternetOutBound",
                "flowTuples": [
                  "1705316400,10.0.1.5,20.190.151.10,54321,443,6,O,B,NX,1,60,0,0",
                  "1705316405,10.0.1.5,20.190.151.10,54321,443,6,O,C,NX,15,900,10,600"
                ]
              }
            ]
          }
        ]
      }
    }
  ]
}
```

### OCSF Output Format

Each flow tuple is converted to an OCSF Network Activity event:

```json
{
  "time": 1705316400000,
  "end_time": 1705316400000,
  "class_uid": 4001,
  "class_name": "Network Activity",
  "category_uid": 4,
  "category_name": "Network Activity",
  "activity_id": 1,
  "activity_name": "Open",
  "severity": "Informational",
  "severity_id": 1,
  "metadata": {
    "version": "1.0.0",
    "product": {
      "name": "Microsoft Azure Network Watcher",
      "vendor_name": "Microsoft Azure",
      "version": "4"
    }
  },
  "connection_info": {
    "direction_id": 2,
    "direction": "Outbound",
    "protocol_num": 6,
    "protocol_name": "TCP"
  },
  "src_endpoint": {
    "ip": "10.0.1.5",
    "port": 54321,
    "mac": "00:0D:3A:1B:C0:9E"
  },
  "dst_endpoint": {
    "ip": "20.190.151.10",
    "port": 443
  },
  "traffic": {
    "bytes": 60,
    "packets": 1
  },
  "cloud": {
    "provider": "Azure",
    "account": {
      "uid": "subscription-id"
    }
  }
}
```

## Local Testing

### Prerequisites
- Python 3.13+
- Azure Storage credentials configured
- AWS credentials with Security Lake access

### Setup

```bash
cd integrations/security-lake/cdk/src/lambda/flow-log-processor

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export AZURE_FLOWLOG_CREDENTIALS_SECRET_NAME=azure-flowlogs-credentials
export SECURITY_LAKE_S3_BUCKET=aws-security-data-lake-region-hash
export SECURITY_LAKE_PATH=ext/securitylake.../1.0/
export SECURITY_LAKE_ENABLED=true
export LOGGING_LEVEL=DEBUG
```

### Run Local Test

```bash
python local_test.py
```

## Monitoring

### CloudWatch Logs

Log group: `/aws/lambda/azure-flowlog-processor-{environment}`

**Key Log Messages**:
```
Flow Log Processor started - Processing {count} messages
Downloaded {bytes} bytes
Parsed flow log with {count} records
Transformed {count} flow tuples to OCSF format
Successfully wrote {count} records to Security Lake
Flow Log Processor complete - Processed: {success}/{total}
```

### CloudWatch Metrics

Monitor these key metrics:
- **Invocations**: Lambda execution count
- **Duration**: Processing time per batch
- **Errors**: Failed executions
- **Throttles**: Concurrent execution limits hit

### SQS Queue Metrics

- **ApproximateNumberOfMessages**: Messages waiting for processing
- **ApproximateAgeOfOldestMessage**: Processing lag indicator

## Error Handling

### Batch Item Failures

The Lambda returns `batchItemFailures` containing message IDs that failed processing. SQS will:
1. Retry failed messages up to 3 times (configurable)
2. Send to Dead Letter Queue after max retries
3. Delete successfully processed messages automatically

### Common Failure Scenarios

| Failure Type | Cause | Resolution |
|--------------|-------|------------|
| Azure authentication failed | Invalid/expired credentials | Update Secrets Manager with valid credentials |
| Blob download failed | Storage account permissions | Verify service principal has Storage Blob Data Reader role |
| JSON parsing failed | Corrupted flow log file | Message sent to DLQ for investigation |
| OCSF transformation failed | Unexpected flow log format | Check flow log version compatibility |
| S3 write failed | Permissions or bucket access | Verify Lambda IAM role and bucket existence |

### Dead Letter Queue

Failed messages are sent to DLQ after 3 retry attempts. Monitor DLQ depth:

```bash
# Check DLQ message count
aws sqs get-queue-attributes \
  --queue-url <DLQ_URL> \
  --attribute-names ApproximateNumberOfMessages

# Retrieve DLQ messages for investigation
aws sqs receive-message \
  --queue-url <DLQ_URL> \
  --max-number-of-messages 10
```

## Performance Tuning

### High Volume Environments (>100 blobs/hour)

```yaml
flowLogProcessor:
  memorySize: 2048
  timeout: 900
  reservedConcurrentExecutions: 10
  batchSize: 5
```

### Low Volume Environments (<20 blobs/hour)

```yaml
flowLogProcessor:
  memorySize: 512
  timeout: 300
  reservedConcurrentExecutions: 2
  batchSize: 10
```

## Security Lake Output

### S3 Partition Structure

Files are written with Security Lake-compatible partitioning:

```
s3://{bucket}/{path}/
  region=ca-central-1/
    accountid={azure-subscription-id}/
      eventday=YYYYMMDD/
        azure-flowlogs-{timestamp}-{uuid}.parquet
```

### Parquet File Metadata

Each Parquet file includes metadata:
- `source`: azure-flowlogs
- `account_id`: Azure subscription ID
- `ocsf_version`: 1.0.0
- `format`: parquet
- `compression`: gzip

## Troubleshooting

### Enable Debug Logging

```yaml
coreProcessing:
  flowLogProcessor:
    environment:
      LOGGING_LEVEL: DEBUG
```

### Check Processing Pipeline

```bash
# Monitor Lambda execution
aws logs tail /aws/lambda/azure-flowlog-processor-dev --follow

# Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url <QUEUE_URL> \
  --attribute-names ApproximateNumberOfMessages

# Verify Security Lake files
aws s3 ls s3://{bucket}/ext/.../region=ca-central-1/ --recursive
```

### Common Issues

**Issue**: No flow logs being processed
- Verify Event Grid subscription is configured for BlobCreated events
- Check Azure EventHub is receiving events
- Confirm Event Transformer is routing flow log events correctly

**Issue**: Azure authentication failures
- Verify service principal credentials in Secrets Manager
- Check Storage Account permissions (Storage Blob Data Reader required)
- Ensure credentials haven't expired

**Issue**: OCSF transformation errors
- Verify flow log version is 4 (currently supported)
- Check flow tuple format matches expected structure
- Review transformation logs for specific field errors

## Dependencies

### Python Packages

From [`requirements.txt`](requirements.txt):
- `azure-identity>=1.15.0`: Azure AD authentication
- `azure-storage-blob>=12.19.0`: Azure Blob Storage access
- `boto3>=1.28.0`: AWS SDK
- `pyarrow>=15.0.0,<21.0.0`: Parquet file generation (ARM64 compatible)

### AWS Resources

- SQS Queue (flow log events)
- Secrets Manager (Azure credentials)
- Security Lake S3 bucket
- IAM role with appropriate permissions

## Version History

- **v2.0.1** (2024-10): Full OCSF conversion and Parquet output
- **v2.0.0** (2024-10): Production implementation with Azure Storage integration
- **v1.0.0** (2024-09): Initial implementation

## Related Documentation

- [Event Transformer README](../event-transformer/README.md) - Upstream routing logic
- [Azure Module README](../../modules/azure/README.md) - Azure integration overview
- [OCSF Network Activity Class](https://schema.ocsf.io/classes/network_activity) - OCSF schema reference
- [Azure NSG Flow Logs](https://docs.microsoft.com/azure/network-watcher/network-watcher-nsg-flow-logging-overview) - Azure documentation

## Support

For issues:
1. Enable DEBUG logging and review CloudWatch Logs
2. Check DLQ for failed messages
3. Verify Azure credentials and permissions
4. Consult troubleshooting section above
5. Review related documentation