# Dead Letter Queue Processing Guide

## Overview

The Event Transformer Lambda automatically sends failed transformation events to the Dead Letter Queue (DLQ) for manual investigation and reprocessing.

## Key Features

- **Exact Message Preservation**: DLQ messages are identical to the original incoming messages
- **No Metadata Addition**: Only the original message body and attributes are preserved
- **Failure-Only**: Only messages that fail transformation are sent to DLQ
- **DLQ Cycle Prevention**: Prevents sending messages back to the same DLQ they originated from
- **Detailed Logging**: Failure reasons are logged at WARN level for visibility
- **Immediate Processing**: Messages are deleted immediately upon successful processing

## Failure Types That Trigger DLQ

### 1. CloudTrail Transformation Failures
```python
# When Azure events fail to convert to CloudTrail format
# Original message body sent to DLQ exactly as received
```

### 2. OCSF Transformation Failures
```python
# When Azure events fail to convert to Security Lake OCSF format
# Original message body sent to DLQ exactly as received
```

### 3. JSON Parsing Errors
```python
# When SQS message body cannot be parsed as JSON
# Original message body sent to DLQ exactly as received
```

### 4. General Processing Exceptions
```python
# When unexpected errors occur during processing
# Original message body sent to DLQ exactly as received
```

## DLQ Message Structure

DLQ messages have **exactly the same structure** as the original incoming messages:

```json
{
  "event_data": {
    "properties": {
      "operationName": "Microsoft.Security/alerts/write",
      "eventSource": "defender.microsoft.com"
    }
  }
}
```

## Processing DLQ Messages

### Manual Investigation
```bash
# Use the SQS dumper tool to analyze DLQ messages
python tools/sqs_message_dumper.py <DLQ_URL> --output-dir ./dlq_investigation

# Review the failed messages
ls -la dlq_investigation/
cat dlq_investigation/sqs_message_*.json
```

### Reprocessing DLQ Messages
```bash
# Use the transformer Lambda's custom processing mode
aws lambda invoke \
  --function-name mdc-event-transformer-dev \
  --payload '{
    "queue_url": "<DLQ_URL>",
    "max_messages": 10
  }' \
  response.json

# Check the results
cat response.json
```

### DLQ Monitoring
```bash
# Check DLQ depth
aws sqs get-queue-attributes \
  --queue-url <DLQ_URL> \
  --attribute-names ApproximateNumberOfMessages

# Monitor DLQ in real-time
aws sqs receive-message --queue-url <DLQ_URL> --wait-time-seconds 20
```

## Environment Configuration

The DLQ functionality uses the `EVENT_DLQ` environment variable:

```yaml
# In CDK configuration
EVENT_DLQ: deadLetterQueue.queueUrl
```

## DLQ Cycle Prevention

**New Feature (v3.1.1)**: The Lambda now prevents infinite message cycling:

### How It Works
- When processing a DLQ and a message fails again, it checks if the source queue is the same DLQ
- If so, the message is **not** sent back to the DLQ to prevent infinite loops
- A warning is logged instead: `DLQ CYCLE PREVENTION: Not sending message back to same DLQ`

### Benefits
- Eliminates infinite message loops that could cause high costs and processing overhead
- Failed DLQ messages are logged but not re-queued, allowing for manual investigation
- Maintains message processing stability when DLQ contains consistently failing messages

## Logging

Failure reasons are logged at appropriate levels for operational visibility:

```
[WARNING] Message abc123 sent to DLQ: NewMessageId=xyz789, Reason=CloudTrail transformation failed
[WARNING] DLQ CYCLE PREVENTION: Not sending message back to same DLQ it came from. Original failure: OCSF transformation failed
[INFO] Successfully deleted processed message def456 from queue (processed 3 events)
[INFO] Successfully deleted empty message ghi789 from queue
[DEBUG] DLQ failure details for abc123: Failed to transform 2 out of 5 Azure events to CloudTrail format
```

### Log Level Guide
- **WARN**: DLQ sends, deletion failures, cycle prevention
- **INFO**: Successful message deletions, processing summaries
- **DEBUG**: Detailed failure context, template rendering details, PyArrow operations

## Best Practices

1. **Monitor DLQ Regularly**: Set up CloudWatch alarms for DLQ message count
2. **Investigate Patterns**: Look for common failure reasons in logs
3. **Batch Reprocessing**: Process multiple DLQ messages at once using custom events
4. **Original State**: DLQ messages can be reprocessed exactly as they were originally received

## Integration with Checkpoint System

- DLQ messages preserve checkpoint information from the original message
- Failed messages don't update checkpoints to prevent data loss
- Reprocessed DLQ messages will update checkpoints normally upon success