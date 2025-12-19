# Event Transformer Scripts

This directory contains utility scripts for managing and maintaining the event-transformer Lambda function.

## redrive_dlq_messages.py

Redrives (reprocesses) messages from a Dead Letter Queue (DLQ) back to the source queue for reprocessing. This is particularly useful after deploying fixes to handle messages that previously failed.

### Prerequisites

- AWS credentials configured with permissions to:
  - Read messages from the DLQ (sqs:ReceiveMessage, sqs:GetQueueAttributes)
  - Send messages to the source queue (sqs:SendMessage)
  - Delete messages from the DLQ (sqs:DeleteMessage)
- Python 3.x with boto3 installed

### Usage

#### Basic Usage with Confirmation

```bash
python redrive_dlq_messages.py \
  --dlq-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-dlq \
  --source-queue-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-queue
```

This will prompt for confirmation before proceeding.

#### Dry Run Mode

Preview what would happen without making any changes:

```bash
python redrive_dlq_messages.py \
  --dlq-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-dlq \
  --source-queue-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-queue \
  --dry-run
```

#### Skip Confirmation Prompt

Use the `--yes` flag to skip the confirmation prompt:

```bash
python redrive_dlq_messages.py \
  --dlq-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-dlq \
  --source-queue-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-queue \
  --yes
```

#### Advanced Options

```bash
python redrive_dlq_messages.py \
  --dlq-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-dlq \
  --source-queue-url https://sqs.us-east-1.amazonaws.com/123456789012/event-transformer-queue \
  --batch-size 5 \
  --max-messages 100 \
  --visibility-timeout 60 \
  --log-level DEBUG \
  --yes
```

### Command-Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--dlq-url` | Yes | - | URL of the Dead Letter Queue |
| `--source-queue-url` | Yes | - | URL of the source queue to redrive messages to |
| `--batch-size` | No | 10 | Number of messages to receive in each batch (max: 10) |
| `--max-messages` | No | All | Maximum number of messages to process |
| `--dry-run` | No | False | Show what would happen without making changes |
| `--yes` | No | False | Skip confirmation prompt |
| `--visibility-timeout` | No | 30 | Visibility timeout for received messages in seconds |
| `--log-level` | No | INFO | Set logging level (DEBUG, INFO, WARNING, ERROR) |

### Output

The script provides:
- Real-time progress updates showing each message being processed
- Summary statistics at completion:
  - Total messages received from DLQ
  - Total messages sent to source queue
  - Total messages deleted from DLQ
  - Total messages failed
- Detailed error information for any failed messages

### Exit Codes

- `0`: Success - all messages processed successfully
- `1`: Failure - some messages failed or an error occurred

### Safety Features

1. **Dry Run Mode**: Preview operations without making changes
2. **Confirmation Prompt**: Requires explicit confirmation before proceeding
3. **Visibility Timeout**: Prevents message loss if script fails mid-operation
4. **Atomic Operations**: Only deletes from DLQ if send to source queue succeeds
5. **Error Tracking**: Records all failures with message IDs and error details

### Example Workflow

After deploying a template fix to resolve DLQ messages:

```bash
# Step 1: Preview what will happen
python redrive_dlq_messages.py \
  --dlq-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/event-transformer-dlq \
  --source-queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/event-transformer-queue \
  --dry-run

# Step 2: Redrive messages with confirmation
python redrive_dlq_messages.py \
  --dlq-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/event-transformer-dlq \
  --source-queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT/event-transformer-queue

# Step 3: Verify messages are processed
# Check CloudWatch Logs for the event-transformer Lambda function
```

### Troubleshooting

**Issue: Permission Denied Errors**
- Ensure your AWS credentials have the required SQS permissions
- Verify the queue URLs are correct

**Issue: Messages Reappear in DLQ**
- This indicates the Lambda is still failing to process them
- Check CloudWatch Logs to identify the root cause
- Verify the template fix has been deployed

**Issue: Script Hangs or Runs Very Slowly**
- Reduce batch-size if experiencing throttling
- Check network connectivity to AWS
- Verify the DLQ contains messages (script shows count at start)

### Best Practices

1. Always run with `--dry-run` first to preview operations
2. Use `--max-messages` to process messages in smaller batches for large DLQs
3. Monitor CloudWatch Logs during redriving to verify messages are processed successfully
4. Keep a record of the summary statistics for audit purposes
5. If many messages fail again, stop and investigate rather than repeatedly redriving