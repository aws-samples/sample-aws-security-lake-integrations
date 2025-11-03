# Event Hub Processor - Local Testing

This directory provides comprehensive local testing infrastructure for the Microsoft Defender Event Hub Processor Lambda function using deployed AWS resources.

## Quick Start

1. **Deploy the CDK stack first:**
   ```bash
   cd ../../../ && npm run deploy
   ```

2. **Get the Lambda function ARN from CDK outputs**

3. **Install local development dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Configure Azure Event Hub credentials in Secrets Manager** (for real data testing)

5. **Run local tests against deployed resources:**
   ```bash
   # Test with real Azure Event Hub data (default)
   python local_test.py --lambda-arn arn:aws:lambda:ca-central-1:ACCOUNT:function:mdc-event-hub-processor-dev
   
   # Test with mock data for development (no Azure SDK needed)
   python local_test.py --lambda-arn arn:aws:lambda:ca-central-1:ACCOUNT:function:mdc-event-hub-processor-dev --mock-event
   
   # Interactive mode with deployed resources
   python local_test.py --lambda-arn arn:aws:lambda:ca-central-1:ACCOUNT:function:mdc-event-hub-processor-dev --interactive
   ```

## How It Works

The local test runner:
1. **Fetches Environment Variables**: Retrieves environment variables from your deployed Lambda function
2. **Sets Local Environment**: Uses the deployed resource names (DynamoDB table, SQS queue, etc.)
3. **Uses Real Azure Data**: By default connects to actual Azure Event Hub for authentic testing
4. **Runs Local Code**: Executes your local code against the real deployed AWS resources
5. **Tests Integration**: Validates DynamoDB cursor operations and SQS message sending

## Testing Options

### Command Line Mode
```bash
# Test with real Azure Event Hub data (default) - requires azure-eventhub package
python local_test.py --lambda-arn YOUR_LAMBDA_ARN

# Test with mock data for development (no Azure dependencies needed)
python local_test.py --lambda-arn YOUR_LAMBDA_ARN --mock-event

# JSON output for automation
python local_test.py --lambda-arn YOUR_LAMBDA_ARN --json-output
```

### Interactive Mode
```bash
python local_test.py --lambda-arn YOUR_LAMBDA_ARN --interactive
```

**Available tests:**
- Test with real Azure Event Hub data against deployed resources (Default)
- Test with mock Azure events against deployed resources (for development)
- Test cursor operations against deployed DynamoDB table
- Test SQS message sending to deployed queue
- Generate sample Azure events for development

## Development Dependencies

For local testing, you need:
```bash
pip install -r requirements-dev.txt
```

This installs:
- `azure-eventhub` - For real Azure Event Hub connections
- `python-dotenv` - For configuration management  
- `boto3` - For AWS service interactions
- Development and testing utilities

## Benefits

- **Real Data Testing**: Uses actual Azure Event Hub data by default
- **Real Resource Testing**: Tests against actual deployed DynamoDB and SQS resources
- **Fast Development**: No need to redeploy Lambda for code changes
- **Environment Consistency**: Uses exact same environment variables as deployed function
- **Mock Option Available**: Use `--mock-event` for development without Azure dependencies
- **Interactive Development**: Step-by-step testing and debugging

## Example Usage

```bash
# Deploy the stack
cd ../../../ && npm run deploy

# Install development dependencies
pip install -r requirements-dev.txt

# Copy the Event Hub Processor Lambda ARN from the CDK outputs
# Example: arn:aws:lambda:ca-central-1:061849379246:function:mdc-event-hub-processor-dev

# Test with real Azure Event Hub data (recommended)
python local_test.py --lambda-arn arn:aws:lambda:ca-central-1:061849379246:function:mdc-event-hub-processor-dev

# Or test with mock data for development
python local_test.py --lambda-arn arn:aws:lambda:ca-central-1:061849379246:function:mdc-event-hub-processor-dev --mock-event
```

This will test your local Lambda code using the real deployed DynamoDB table and SQS queue, and by default will connect to the real Azure Event Hub for authentic Microsoft Defender event data.