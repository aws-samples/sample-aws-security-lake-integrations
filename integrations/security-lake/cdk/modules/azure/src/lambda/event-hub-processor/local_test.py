#!/usr/bin/env python3
"""
Local Test Runner for Event Hub Processor Lambda
Provides local development and testing environment using deployed Lambda's environment variables.
By default uses real Azure Event Hub data. Use --mock-event for sample data testing.
"""

import sys
import json
import argparse
import traceback
import uuid
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MockLambdaContext:
    """Mock Lambda context for local testing."""
    function_name: str = "mdc-event-hub-processor-local"
    function_version: str = "$LATEST"
    invoked_function_arn: str = "arn:aws:lambda:ca-central-1:123456789012:function:mdc-event-hub-processor-local"
    memory_limit_in_mb: int = 512
    remaining_time_in_millis: int = 300000  # 5 minutes
    log_group_name: str = "/aws/lambda/mdc-event-hub-processor-local"
    log_stream_name: str = f"2024/01/01/[$LATEST]{datetime.now().strftime('%Y%m%d%H%M%S')}"
    aws_request_id: str = f"local-request-{uuid.uuid4().hex[:8]}"
    
    def get_remaining_time_in_millis(self) -> int:
        """Return remaining execution time in milliseconds."""
        return self.remaining_time_in_millis


class EventHubProcessorLocalTest:
    """Local development and testing runner that uses deployed Lambda's environment variables."""
    
    def __init__(self, lambda_arn: Optional[str] = None):
        """
        Initialize the local test runner.
        
        Args:
            lambda_arn: ARN of deployed Lambda function to get env vars from
        """
        self.lambda_arn = lambda_arn
        self.deployed_env_vars = {}
        
        if lambda_arn:
            self.deployed_env_vars = self._fetch_lambda_env_vars(lambda_arn)
            self._set_environment_variables(self.deployed_env_vars)
        
        logger.info("Event Hub Processor local test runner initialized")
        if lambda_arn:
            logger.info(f"Using environment variables from deployed Lambda: {lambda_arn}")
    
    def _fetch_lambda_env_vars(self, lambda_arn: str) -> Dict[str, str]:
        """
        Fetch environment variables from deployed Lambda function.
        
        Args:
            lambda_arn: ARN of the Lambda function
            
        Returns:
            Dictionary of environment variables
        """
        try:
            # Extract function name and region from ARN
            # ARN format: arn:aws:lambda:region:account:function:function-name
            arn_parts = lambda_arn.split(':')
            region = arn_parts[3]
            function_name = arn_parts[6]
            
            logger.info(f"Fetching environment variables from {function_name} in {region}")
            
            # Create Lambda client
            lambda_client = boto3.client('lambda', region_name=region)
            
            # Get function configuration
            response = lambda_client.get_function_configuration(FunctionName=function_name)
            
            env_vars = response.get('Environment', {}).get('Variables', {})
            
            logger.info(f"Retrieved {len(env_vars)} environment variables from deployed Lambda")
            
            # Log the variable names (not values for security)
            logger.info(f"Environment variables: {list(env_vars.keys())}")
            
            return env_vars
            
        except ClientError as e:
            error_msg = f"Failed to fetch Lambda configuration: {e.response['Error']['Message']}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error fetching Lambda environment: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _set_environment_variables(self, env_vars: Dict[str, str]):
        """
        Set environment variables for local execution.
        
        Args:
            env_vars: Environment variables to set
        """
        for key, value in env_vars.items():
            os.environ[key] = value
        
        # Extract and set AWS_REGION from Lambda ARN if not provided
        if 'AWS_REGION' not in env_vars and self.lambda_arn:
            # ARN format: arn:aws:lambda:region:account:function:function-name
            arn_parts = self.lambda_arn.split(':')
            region = arn_parts[3]
            os.environ['AWS_REGION'] = region
            env_vars['AWS_REGION'] = region  # Add to our tracking dict
            logger.info(f"Extracted AWS_REGION from Lambda ARN: {region}")
        
        logger.info(f"Set {len(env_vars)} environment variables for local execution")
    
    def create_sample_azure_defender_events(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Create sample Azure Defender for Cloud events for testing.
        
        Args:
            count: Number of sample events to generate
            
        Returns:
            List of sample Azure Defender events
        """
        now = datetime.now(timezone.utc)
        events = []
        
        alert_types = [
            "Suspicious authentication activity",
            "Potential malware detected",
            "Unusual network traffic",
            "Privileged account activity",
            "Data exfiltration attempt"
        ]
        
        severities = ["High", "Medium", "Low", "Informational"]
        
        for i in range(count):
            event = {
                "id": f"/subscriptions/12345678-1234-1234-1234-123456789012/providers/Microsoft.Security/alerts/{uuid.uuid4()}",
                "alertDisplayName": alert_types[i % len(alert_types)],
                "alertType": f"VM_{alert_types[i % len(alert_types)].replace(' ', '_').upper()}",
                "description": f"Sample alert description for {alert_types[i % len(alert_types)]}",
                "severity": severities[i % len(severities)],
                "intent": "Execution",
                "startTimeUtc": (now - timedelta(minutes=30 + i*5)).isoformat() + "Z",
                "endTimeUtc": (now - timedelta(minutes=25 + i*5)).isoformat() + "Z",
                "timeGenerated": (now - timedelta(minutes=30 + i*5)).isoformat() + "Z",
                "subscriptionId": "12345678-1234-1234-1234-123456789012",
                "resourceDetails": {
                    "resourceType": "VirtualMachine",
                    "resourceId": f"/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm-{i}",
                    "location": "canadacentral"
                },
                "compromisedEntity": f"test-vm-{i}",
                "remediationSteps": [
                    "Review the alert details",
                    "Investigate the affected resource",
                    "Apply security patches if needed",
                    "Update security policies"
                ],
                "entities": [
                    {
                        "$id": "host",
                        "type": "host",
                        "hostName": f"test-vm-{i}",
                        "azureID": f"/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm-{i}"
                    },
                    {
                        "$id": "ip",
                        "type": "ip",
                        "address": f"192.168.1.{100 + i}"
                    }
                ],
                "extendedProperties": {
                    "resourceLocation": "Canada Central",
                    "sourceIpAddress": f"203.0.113.{i + 10}",
                    "threatIntelligence": "Low confidence",
                    "processName": "suspicious_process.exe",
                    "commandLine": "powershell.exe -enc ZQBjAGgAbw..."
                }
            }
            events.append(event)
        
        logger.info(f"Generated {len(events)} sample Azure Defender events")
        return events
    
    def create_sample_lambda_event(self) -> Dict[str, Any]:
        """
        Create a sample CloudWatch Events trigger for the Lambda.
        
        Returns:
            Sample Lambda event (scheduled trigger)
        """
        return {
            "version": "0",
            "id": f"local-event-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "detail-type": "Scheduled Event",
            "source": "aws.events",
            "account": "123456789012",
            "time": datetime.now(timezone.utc).isoformat() + "Z",
            "region": os.getenv('AWS_REGION', 'ca-central-1'),
            "detail": {}
        }
    
    def run_event_hub_processor_local(self, 
                                     context: Optional[MockLambdaContext] = None,
                                     use_mock_events: bool = False) -> Dict[str, Any]:
        """
        Run the Event Hub processor Lambda locally using deployed environment variables.
        By default uses real Azure Event Hub. Use use_mock_events=True for sample data.
        
        Args:
            context: Lambda context (will create mock if not provided)
            use_mock_events: If True, use mock Azure events; if False, use real Azure Event Hub
            
        Returns:
            Processing results
        """
        if context is None:
            context = MockLambdaContext()
        
        data_source = "mock Azure events" if use_mock_events else "real Azure Event Hub"
        logger.info(f"Starting Event Hub processor local test with deployed environment variables using {data_source}")
        
        # Display current environment variables being used
        env_vars = ['AWS_REGION', 'DYNAMODB_TABLE_NAME', 'SQS_QUEUE_URL', 'AZURE_CREDENTIALS_SECRET_NAME']
        logger.info("Using environment variables:")
        for var in env_vars:
            value = os.getenv(var, 'NOT_SET')
            # Mask sensitive values
            if 'SECRET' in var or 'KEY' in var:
                display_value = f"{value[:10]}..." if len(value) > 10 else "***"
            else:
                display_value = value
            logger.info(f"  {var}: {display_value}")
        
        try:
            # Setup mock Azure events only if requested
            if use_mock_events:
                mock_azure_events = self.create_sample_azure_defender_events(5)
                self._setup_mock_azure_events(mock_azure_events)
                logger.info(f"Using {len(mock_azure_events)} mock Azure events")
            else:
                logger.info("Using real Azure Event Hub data (configured in Secrets Manager)")
            
            # Import and run the Lambda handler locally
            from app import lambda_handler
            
            event = self.create_sample_lambda_event()
            result = lambda_handler(event, context)
            
            logger.info("Event Hub processor local test completed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Event Hub processor local test failed: {str(e)}"
            logger.error(error_msg, extra={"error": str(e), "traceback": traceback.format_exc()})
            
            return {
                "statusCode": 500,
                "error": error_msg,
                "traceback": traceback.format_exc()
            }
    
    def _setup_mock_azure_events(self, mock_events: List[Dict]):
        """
        Setup mock Azure Event Hub events for testing.
        
        Args:
            mock_events: Mock events to return
        """
        # Monkey patch the EventHubClient to return mock data
        from helpers import eventhub_client
        
        def mock_receive_events(self, max_events=100, max_wait_time=30):
            """Mock implementation of receive_events."""
            logger.info(f"Mock Azure Event Hub - returning {len(mock_events)} sample events")
            return mock_events[:min(max_events, len(mock_events))]
        
        eventhub_client.EventHubClient.receive_events = mock_receive_events
        logger.info(f"Azure Event Hub mocked with {len(mock_events)} sample events")
    
    def print_deployed_configuration(self):
        """Print the configuration retrieved from deployed Lambda."""
        print("\n" + "="*70)
        print("DEPLOYED LAMBDA CONFIGURATION")
        print("="*70)
        
        if self.lambda_arn:
            print(f"Lambda ARN: {self.lambda_arn}")
            print("\nEnvironment Variables:")
            
            for key, value in self.deployed_env_vars.items():
                # Mask sensitive values
                if any(secret in key.upper() for secret in ['SECRET', 'KEY', 'PASSWORD']):
                    display_value = f"{value[:10]}..." if len(value) > 10 else "***"
                else:
                    display_value = value
                print(f"  {key}: {display_value}")
        else:
            print("No Lambda ARN provided - using default/fallback values")
            
        print("="*70)
    
    def interactive_mode(self):
        """Run in interactive mode for development and testing."""
        print("\n" + "="*80)
        print("EVENT HUB PROCESSOR LAMBDA - LOCAL TEST WITH DEPLOYED RESOURCES")
        print("="*80)
        
        # Display configuration
        self.print_deployed_configuration()
        
        while True:
            print(f"\n" + "-"*70)
            print("LOCAL TESTING OPTIONS:")
            print("1. Test with real Azure Event Hub data (using deployed AWS resources)")
            print("2. Test with mock Azure events (using deployed AWS resources)")
            print("3. Test cursor operations against deployed DynamoDB table")
            print("4. Test SQS message sending to deployed queue")
            print("5. Show deployed environment configuration")
            print("6. Generate sample Azure events file")
            print("7. Exit")
            print("-"*70)
            
            choice = input("\nSelect option (1-7): ").strip()
            
            if choice == "1":
                print("\n🔗 Testing with real Azure Event Hub data against deployed AWS resources...")
                result = self.run_event_hub_processor_local(use_mock_events=False)
                print(f"Result: {json.dumps(result, indent=2, default=str)}")
                
            elif choice == "2":
                print("\n🎭 Testing with mock Azure events against deployed AWS resources...")
                result = self.run_event_hub_processor_local(use_mock_events=True)
                print(f"Result: {json.dumps(result, indent=2, default=str)}")
                
            elif choice == "3":
                print("\n🗄️ Testing DynamoDB cursor operations...")
                self._test_deployed_dynamodb()
                
            elif choice == "4":
                print("\n📬 Testing SQS message sending...")
                self._test_deployed_sqs()
                
            elif choice == "5":
                self.print_deployed_configuration()
                
            elif choice == "6":
                sample_events = self.create_sample_azure_defender_events(10)
                sample_file = Path(__file__).parent / "sample_azure_events.json"
                
                with open(sample_file, 'w', encoding='utf-8') as f:
                    json.dump(sample_events, f, indent=2, default=str)
                
                print(f"\n📄 Sample Azure events saved to: {sample_file}")
                
            elif choice == "7":
                print("\n👋 Exiting local development mode...")
                break
                
            else:
                print("\n❌ Invalid choice. Please select 1-7.")
    
    def _test_deployed_dynamodb(self):
        """Test operations against deployed DynamoDB table."""
        try:
            table_name = os.getenv('DYNAMODB_TABLE_NAME')
            if not table_name:
                print("   ❌ DYNAMODB_TABLE_NAME not set - deploy Lambda first or provide ARN")
                return
                
            from helpers.dynamodb_cursor_client import DynamoDBCursorClient
            
            cursor_client = DynamoDBCursorClient(
                table_name=table_name,
                region_name=os.getenv('AWS_REGION', 'ca-central-1'),
                logger=logger
            )
            
            test_cursor_id = "test:local_deployment_test"
            test_cursor_value = datetime.now(timezone.utc).isoformat()
            
            # Test saving cursor
            cursor_client.save_cursor(
                cursor_id=test_cursor_id,
                cursor_value=test_cursor_value,
                messages_processed_batch=5,
                last_batch_size=5,
                processing_time_ms=1500
            )
            print(f"   ✅ Cursor saved to deployed table: {table_name}")
            
            # Test retrieving cursor
            retrieved_cursor = cursor_client.get_cursor(test_cursor_id)
            if retrieved_cursor:
                print(f"   ✅ Cursor retrieved: {retrieved_cursor.get('cursor_value')}")
            else:
                print(f"   ❌ Failed to retrieve cursor")
            
            # Clean up test cursor
            cursor_client.delete_cursor(test_cursor_id)
            print(f"   ✅ Test cursor cleaned up from deployed table")
            
        except Exception as e:
            print(f"   ❌ DynamoDB test failed: {str(e)}")
            logger.error(f"DynamoDB test error: {str(e)}")
    
    def _test_deployed_sqs(self):
        """Test SQS operations against deployed queue."""
        try:
            queue_url = os.getenv('SQS_QUEUE_URL')
            if not queue_url:
                print("   ❌ SQS_QUEUE_URL not set - deploy Lambda first or provide ARN")
                return
                
            from helpers.sqs_client import SQSClient
            
            sqs_client = SQSClient(
                region_name=os.getenv('AWS_REGION', 'ca-central-1'),
                logger=logger
            )
            
            # Create test message
            test_events = self.create_sample_azure_defender_events(2)
            sqs_entries = sqs_client.create_batch_entries(test_events, "local_deployment_test")
            
            # Send test messages to deployed queue
            response = sqs_client.send_message_batch(queue_url, sqs_entries)
            
            successful = len(response.get('Successful', []))
            failed = len(response.get('Failed', []))
            
            print(f"   ✅ SQS test completed against deployed queue:")
            print(f"      Queue: {queue_url.split('/')[-1]}")
            print(f"      Messages sent: {successful}, failed: {failed}")
            
        except Exception as e:
            print(f"   ❌ SQS test failed: {str(e)}")
            logger.error(f"SQS test error: {str(e)}")


def main():
    """Main entry point for the local test runner."""
    parser = argparse.ArgumentParser(
        description="Local Test Runner for Event Hub Processor Lambda using deployed resources"
    )
    
    parser.add_argument(
        "--lambda-arn", "-l",
        required=True,
        help="ARN of deployed Lambda function to get environment variables from"
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    
    parser.add_argument(
        "--mock-event", "-m",
        action="store_true",
        help="Use mock Azure events instead of real Azure Event Hub data"
    )
    
    parser.add_argument(
        "--json-output", "-j",
        action="store_true",
        help="Output results in JSON format"
    )
    
    args = parser.parse_args()
    
    try:
        # Create test runner with deployed Lambda ARN
        runner = EventHubProcessorLocalTest(args.lambda_arn)
        
        if args.interactive:
            runner.interactive_mode()
        else:
            data_source = "mock Azure events" if args.mock_event else "real Azure Event Hub"
            print(f"\n>> Running Event Hub Processor Local Test...")
            print(f"Using environment variables from: {args.lambda_arn}")
            print(f"Data source: {data_source}")
            
            # Run the processor locally with deployed resources
            result = runner.run_event_hub_processor_local(use_mock_events=args.mock_event)
            
            # Output results
            if args.json_output:
                print(json.dumps(result, indent=2, default=str))
            else:
                print(f"\n>> Event Hub Processor local test completed!")
                
                if isinstance(result, dict):
                    status_code = result.get('statusCode', 'unknown')
                    print(f"Status Code: {status_code}")
                    
                    if status_code == 200:
                        body = json.loads(result.get('body', '{}'))
                        stats = body.get('stats', {})
                        
                        print(f"\n>> Processing Summary (using deployed resources):")
                        print(f"   Events Received: {stats.get('events_received', 0)}")
                        print(f"   Events Sent to SQS: {stats.get('events_sent_to_sqs', 0)}")
                        print(f"   Cursor Updated: {stats.get('cursor_updated', False)}")
                        print(f"   Processing Time: {stats.get('processing_duration_ms', 0)} ms")
                        print(f"   Status: {stats.get('status', 'unknown')}")
                        print(f"\n>> This test used the actual deployed DynamoDB table and SQS queue!")
                        if not args.mock_event:
                            print(f">> And connected to real Azure Event Hub for authentic data!")
                    else:
                        body = json.loads(result.get('body', '{}'))
                        print(f"Error: {body.get('error', 'Unknown error')}")
    
    except ValueError as e:
        print(f"\nERROR: Lambda ARN Error: {e}")
        print("   Make sure the Lambda function is deployed and you have permissions to access it")
        sys.exit(1)
    except NoCredentialsError:
        print(f"\nERROR: AWS Credentials Error: No AWS credentials found")
        print("   Configure AWS CLI credentials or set AWS_PROFILE environment variable")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: Unexpected Error: {e}")
        if not args.json_output:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()