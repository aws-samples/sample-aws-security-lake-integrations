# Debugging Failed Events - Azure to CloudTrail Transformer

This document explains how to debug and troubleshoot failed events in the Azure to CloudTrail event transformer.

## Environment Variables for Enhanced Logging

### `LOGGING_LEVEL=DEBUG`
Sets the overall logging level to DEBUG for maximum detail:
```bash
# In Lambda environment variables:
LOGGING_LEVEL=DEBUG
```

This enables comprehensive debug logging including:
- Full Azure event JSON data and template rendering context
- Detailed transformation failure reasons with character-level error positions
- Complete message body contents and processing pipeline details
- Step-by-step template rendering with JSONPath extraction results
- Third-party library debug suppression (PyArrow, boto3, botocore)

### Recent Logging Improvements (v3.1.1)
- **Structured Log Levels**: INFO for successful operations, WARN for failures, DEBUG for diagnostics
- **PyArrow Suppression**: Debug logs from PyArrow moved to DEBUG level to reduce noise
- **Message Lifecycle Tracking**: Complete visibility from queue fetch to deletion
- **Enhanced JSON Error Diagnostics**: Character position and context for JSON parsing failures

## Types of Event Failures

### 1. Transformation Failures
When Azure events cannot be mapped to CloudTrail format.

**Log Messages to Look For:**
```
TRANSFORMATION FAILURE - No CloudTrail events generated from message [message-id]
FAILED TO MAP AZURE EVENT - [Error Type]: [Error Message]
```

**Debug Information Logged:**
- Original Azure event structure
- Event type determination
- Field validation results
- Complete Azure event JSON

### 2. CloudTrail API Failures
When events fail to be sent to CloudTrail Event Data Store.

**Log Messages to Look For:**
```
FAILED EVENTS DETECTED - Batch [batch-number]
FAILED EVENT #[number] in batch [batch-number]
```

**Debug Information Logged:**
- CloudTrail API error codes and messages
- Original eventData that failed
- Event source, name, and timing information
- Complete audit event structure

### 3. SQS Message Processing Failures
When SQS messages cannot be parsed or processed.

**Log Messages to Look For:**
```
DETAILED ERROR processing SQS message [message-id]
CRITICAL ERROR in Lambda handler
```

**Debug Information Logged:**
- Full SQS message structure
- JSON parsing errors
- Exception tracebacks
- Message retry information

## Debugging Tools

### 1. Interactive Debug Script
Use the interactive debugging script for detailed event analysis:

```bash
cd integrations/azure/microsoft_defender_cloud/cdk/src/lambda/event-transformer
python debug_failed_events.py
```

**Options:**
- **Option 1**: Debug all example events - Tests all events in `example_events/` directory
- **Option 2**: Debug specific SQS message file - Analyze a particular JSON file
- **Option 3**: Simulate Lambda handler - Test the full processing pipeline
- **Option 4**: Debug manual event input - Paste Azure event JSON for analysis

### 2. Local Testing Script
Run comprehensive tests with detailed output:

```bash
cd integrations/azure/microsoft_defender_cloud/cdk/src/lambda/event-transformer
python local_test.py
```

This will show:
- Transformation success/failure rates
- Event type classification
- CloudTrail format validation results
- Error handling capabilities

## Common Failure Scenarios and Solutions

### Scenario 1: Missing Required Fields
**Error**: `Missing required eventData field: [field-name]`

**Cause**: Azure event is missing fields required by CloudTrail schema

**Solution**: Check if Azure event has expected structure:
- Security alerts need: `AlertType`, `SystemAlertId`, etc.
- Secure score events need: `type`, `properties.score`, etc.

### Scenario 2: Invalid Timestamp Format
**Error**: `Could not parse timestamp '[timestamp]'`

**Cause**: Azure timestamp format doesn't match expected patterns

**Solution**: The transformer handles multiple timestamp formats automatically. If this fails, check:
- `TimeGenerated` field in Azure alerts
- `enqueued_time` in event metadata
- `processed_timestamp` in processing metadata

### Scenario 3: CloudTrail Channel Issues
**Error**: `ChannelNotFound` or `InvalidChannelARN`

**Cause**: CloudTrail Channel ARN is incorrect or Channel doesn't exist

**Solution**: Verify `CLOUDTRAIL_CHANNEL_ARN` environment variable:
```bash
# Valid format:
arn:aws:cloudtrail:us-east-1:123456789012:channel/01234567-abcd-1234-5678-123456789012
```

### Scenario 4: Event Data Size Limits
**Error**: `FieldTooLong` or `InvalidData`

**Cause**: Event data exceeds CloudTrail limits:
- `requestParameters`: max 100kB
- `responseElements`: max 100kB  
- `additionalEventData`: max 28kB

**Solution**: The transformer automatically truncates large fields, but you may need to adjust the mapping logic.

## Monitoring Failed Events

### CloudWatch Logs Insights Queries

**Find all transformation failures:**
```
fields @timestamp, @message
| filter @message like /TRANSFORMATION FAILURE/
| sort @timestamp desc
| limit 100
```

**Find CloudTrail API failures:**
```
fields @timestamp, @message, error_code, error_message
| filter @message like /FAILED EVENTS DETECTED/
| sort @timestamp desc
| limit 50
```

**Find specific event types failing:**
```
fields @timestamp, @message, event_type
| filter @message like /FAILED TO MAP AZURE EVENT/
| stats count() by event_type
```

### Lambda Metrics to Monitor
- **Duration**: High duration may indicate processing issues
- **Errors**: Total error count
- **Throttles**: May indicate CloudTrail API limits
- **DeadLetterQueue**: Events that couldn't be processed after retries

## CloudTrail Event Data Store Query Examples

**Check if transformed events are being stored:**
```sql
SELECT eventTime, eventSource, eventName, recipientAccountId
FROM your_event_data_store
WHERE eventSource LIKE 'azure.%'
ORDER BY eventTime DESC
LIMIT 10;
```

**Find events by specific Azure alert types:**
```sql
SELECT eventTime, eventName, json_extract(eventData, '$.additionalEventData.alertDisplayName') as alert_name
FROM your_event_data_store  
WHERE eventSource = 'azure.defendercloud'
AND eventName = 'ARM_AnomalousRBACRoleAssignment'
ORDER BY eventTime DESC;
```

## Quick Debugging Checklist

When events are failing, check these items in order:

1. **Environment Variables**
   - [ ] `EVENT_DATA_STORE_ARN` is set and valid
   - [ ] `CLOUDTRAIL_CHANNEL_ARN` is set and valid
   - [ ] `DEBUG_FAILED_EVENTS=true` for enhanced logging

2. **CloudWatch Logs**
   - [ ] Check for "TRANSFORMATION FAILURE" messages
   - [ ] Check for "FAILED EVENTS DETECTED" messages  
   - [ ] Look for AWS API error codes in failed events

3. **Event Structure**
   - [ ] Azure events have `event_data` field
   - [ ] Event data has required fields (id, type, etc.)
   - [ ] Timestamps are in valid format

4. **CloudTrail Configuration**
   - [ ] Channel ARN exists and is associated with Event Data Store
   - [ ] Lambda has `cloudtrail-data:PutAuditEvents` permissions
   - [ ] Event Data Store is active and accessible

5. **Testing**
   - [ ] Run `python local_test.py` to verify transformation logic
   - [ ] Use `python debug_failed_events.py` for detailed analysis

## Getting Help

If you're still experiencing issues after following this guide:

1. **Enable full debug logging**:
   ```bash
   DEBUG_FAILED_EVENTS=true
   LOGGING_LEVEL=DEBUG
   ```

2. **Run the debug script** on your specific failing events:
   ```bash
   python debug_failed_events.py
   ```

3. **Check CloudWatch Logs** for the specific error patterns mentioned above

4. **Verify CloudTrail setup** using AWS CLI:
   ```bash
   aws cloudtrail describe-event-data-store --event-data-store [your-arn]
   aws cloudtrail list-channels --event-data-store [your-arn]
   ```

The enhanced logging will provide detailed information about exactly which events are failing and why, making it much easier to diagnose and fix transformation issues.