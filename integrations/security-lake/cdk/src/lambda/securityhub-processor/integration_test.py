#!/usr/bin/env python3
"""
Integration Test Script for Security Hub Processor Lambda

This script:
1. Fetches environment variables from a deployed Lambda function
2. Sets up local environment to match the deployed function
3. Runs the Lambda handler locally with real AWS resources
4. Allows specifying which example JSON file to test with

Usage:
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123456789012:function:my-function
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123456789012:function:my-function --test-file sqs_message_123.json
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123456789012:function:my-function --test-file sqs_message_123.json --dry-run
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123456789012:function:my-function --debug
"""

import argparse
import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecurityHubTester:
    """Integration tester for Security Hub Processor Lambda"""
    
    def __init__(self, lambda_arn: str, dry_run: bool = False):
        """
        Initialize the integration tester
        
        Args:
            lambda_arn: ARN of the deployed Lambda function
            dry_run: If True, don't actually send findings to Security Hub
        """
        self.lambda_arn = lambda_arn
        self.dry_run = dry_run
        self.original_env = dict(os.environ)  # Backup original environment
        
        # Parse Lambda ARN to get region and function name
        arn_parts = lambda_arn.split(':')
        if len(arn_parts) != 7 or arn_parts[2] != 'lambda':
            raise ValueError(f"Invalid Lambda ARN format: {lambda_arn}")
        
        self.region = arn_parts[3]
        self.account_id = arn_parts[4]
        self.function_name = arn_parts[6]
        
        logger.info(f"Initializing integration test for Lambda: {self.function_name}")
        logger.info(f"Region: {self.region}, Account: {self.account_id}")
        
        # Initialize AWS clients
        try:
            self.lambda_client = boto3.client('lambda', region_name=self.region)
            logger.info("AWS Lambda client initialized successfully")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please configure AWS credentials.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS client: {str(e)}")
            raise
    
    def fetch_lambda_environment(self) -> Dict[str, str]:
        """
        Fetch environment variables from the deployed Lambda function
        
        Returns:
            Dictionary of environment variables
        """
        try:
            logger.info(f"Fetching environment variables from Lambda: {self.function_name}")
            
            response = self.lambda_client.get_function(FunctionName=self.lambda_arn)
            
            # Extract environment variables
            env_vars = response.get('Configuration', {}).get('Environment', {}).get('Variables', {})
            
            logger.info(f"Retrieved {len(env_vars)} environment variables")
            for key in env_vars.keys():
                logger.info(f"  {key}: {env_vars[key]}")
            
            return env_vars
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.error(f"Lambda function not found: {self.lambda_arn}")
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied to Lambda function: {self.lambda_arn}")
                logger.error("Ensure your AWS credentials have lambda:GetFunction permission")
            else:
                logger.error(f"AWS Error: {error_code} - {e.response['Error']['Message']}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching Lambda environment: {str(e)}")
            raise
    
    def setup_local_environment(self, env_vars: Dict[str, str]):
        """
        Set up local environment variables to match the Lambda function
        
        Args:
            env_vars: Dictionary of environment variables to set
        """
        logger.info("Setting up local environment variables")
        
        # Set Lambda environment variables
        for key, value in env_vars.items():
            os.environ[key] = value
        
        # Set additional Lambda runtime environment variables
        os.environ['AWS_LAMBDA_FUNCTION_NAME'] = self.function_name
        os.environ['AWS_LAMBDA_FUNCTION_VERSION'] = '$LATEST'
        os.environ['AWS_LAMBDA_RUNTIME_API'] = 'localhost:9001'  # Mock runtime API
        os.environ['AWS_REGION'] = self.region
        os.environ['AWS_DEFAULT_REGION'] = self.region
        
        logger.info("Local environment configured to match Lambda function")
    
    def load_test_event(self, test_file: str) -> Dict[str, Any]:
        """
        Load test event from JSON file
        
        Args:
            test_file: Name of the JSON file or path to JSON file
            
        Returns:
            Test event dictionary
        """
        # Handle different path formats
        test_file_path = None
        
        # If it's already a full path or relative path, use it directly
        if test_file.startswith('./') or test_file.startswith('../') or '/' in test_file:
            test_file_path = Path(test_file)
            if not test_file_path.is_absolute():
                test_file_path = current_dir / test_file_path
        else:
            # Just a filename, look in example_sqs directory
            example_sqs_dir = current_dir / 'example_sqs'
            test_file_path = example_sqs_dir / test_file
        
        if not test_file_path.exists():
            # Try alternative locations
            filename = Path(test_file).name
            alt_path = current_dir / 'example_sqs' / filename
            if alt_path.exists():
                test_file_path = alt_path
            else:
                raise FileNotFoundError(f"Test file not found: {test_file_path}")
        
        try:
            with open(test_file_path, 'r', encoding='utf-8') as f:
                sqs_message = json.load(f)
            
            logger.info(f"Loaded test event from: {test_file}")
            
            # Create SQS event structure for Lambda handler
            sqs_event = {
                'Records': [
                    {
                        'messageId': sqs_message.get('MessageId', 'test-message-id'),
                        'receiptHandle': sqs_message.get('ReceiptHandle', 'test-receipt-handle'),
                        'body': sqs_message.get('Body', '{}'),
                        'attributes': {
                            'ApproximateReceiveCount': '1',
                            'SentTimestamp': '1545082649183'
                        },
                        'messageAttributes': {},
                        'md5OfBody': sqs_message.get('MD5OfBody', ''),
                        'eventSource': 'aws:sqs',
                        'eventSourceARN': f'arn:aws:sqs:{self.region}:{self.account_id}:test-queue',
                        'awsRegion': self.region
                    }
                ]
            }
            
            return sqs_event
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in test file {test_file}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error loading test file {test_file}: {str(e)}")
            raise
    
    def create_mock_context(self) -> MagicMock:
        """
        Create a mock Lambda context for testing
        
        Returns:
            Mock Lambda context object
        """
        context = MagicMock()
        context.function_name = self.function_name
        context.function_version = '$LATEST'
        context.invoked_function_arn = self.lambda_arn
        context.memory_limit_in_mb = 512
        context.remaining_time_in_millis = lambda: 30000  # 30 seconds
        context.log_group_name = f'/aws/lambda/{self.function_name}'
        context.log_stream_name = '2024/09/30/[$LATEST]test-stream'
        context.aws_request_id = 'test-request-id-12345'
        
        return context
    
    def run_integration_test(self, test_file: str, debug_mode: bool = False) -> bool:
        """
        Run the full integration test
        
        Args:
            test_file: Name of the test file to use
            debug_mode: Enable debug logging for detailed error analysis
            
        Returns:
            True if test passed, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("STARTING INTEGRATION TEST")
            logger.info("=" * 60)
            
            # Step 1: Fetch Lambda environment variables
            env_vars = self.fetch_lambda_environment()
            
            # Step 2: Set up local environment
            self.setup_local_environment(env_vars)
            
            # Step 3: Load test event
            test_event = self.load_test_event(test_file)
            
            # Step 4: Create mock context
            context = self.create_mock_context()
            
            # Step 5: Import and run the Lambda handler
            logger.info("Importing Lambda handler...")
            from app import lambda_handler
            
            if self.dry_run:
                logger.warning("DRY RUN MODE: Will not actually send findings to Security Hub")
                # Mock the Security Hub client
                import app
                original_client = app.securityhub_client
                
                mock_securityhub = MagicMock()
                mock_securityhub.batch_import_findings.return_value = {
                    'FailedCount': 0,
                    'SuccessCount': 1,
                    'FailedFindings': []
                }
                app.securityhub_client = mock_securityhub
            
            # Step 6: Execute the Lambda handler
            logger.info("Executing Lambda handler with test event...")
            logger.info(f"Test event contains {len(test_event['Records'])} SQS record(s)")
            
            if debug_mode:
                logger.info("DEBUG MODE: Setting detailed logging")
                root_logger = logging.getLogger()
                root_logger.setLevel(logging.DEBUG)
                
                for logger_name in ['app']:
                    module_logger = logging.getLogger(logger_name)
                    module_logger.setLevel(logging.DEBUG)
                    module_logger.propagate = True
            
            result = lambda_handler(test_event, context)
            
            # Step 7: Analyze results
            logger.info("=" * 60)
            logger.info("INTEGRATION TEST RESULTS")
            logger.info("=" * 60)
            
            logger.info(f"Status Code: {result.get('statusCode', 'Unknown')}")
            logger.info(f"Total Messages: {result.get('total_messages', 'Unknown')}")
            logger.info(f"Processed Findings: {result.get('processed_findings', 'Unknown')}")
            logger.info(f"Failed Findings: {result.get('failed_findings', 'Unknown')}")
            
            # Check for batch item failures
            if result.get('batchItemFailures'):
                logger.warning(f"Batch item failures: {len(result['batchItemFailures'])}")
                for failure in result['batchItemFailures']:
                    logger.warning(f"  Failed message: {failure['itemIdentifier']}")
            
            # Determine success
            success = (
                result.get('statusCode') == 200 and
                result.get('processed_findings', 0) > 0 and
                result.get('failed_findings', 0) == 0
            )
            
            if success:
                logger.info("✅ INTEGRATION TEST PASSED!")
            else:
                logger.error("❌ INTEGRATION TEST FAILED!")
            
            return success
            
        except Exception as e:
            logger.error(f"Integration test failed with exception: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
        finally:
            # Restore original environment
            self.restore_environment()
    
    def restore_environment(self):
        """Restore original environment variables"""
        logger.info("Restoring original environment variables")
        
        # Clear all environment variables and restore original
        for key in list(os.environ.keys()):
            if key in os.environ:
                del os.environ[key]
        
        for key, value in self.original_env.items():
            os.environ[key] = value
    
    def list_available_test_files(self) -> list:
        """List available test files in example_sqs directory"""
        example_sqs_dir = current_dir / 'example_sqs'
        if not example_sqs_dir.exists():
            return []
        
        return [f.name for f in example_sqs_dir.glob('*.json')]
    
    def run_batch_cleanup(self, debug_mode: bool = False) -> Dict[str, Any]:
        """
        Process all files in example_sqs directory and delete successful ones
        
        Args:
            debug_mode: Enable debug logging for detailed error analysis
            
        Returns:
            Dictionary with batch processing results
        """
        try:
            logger.info("=" * 60)
            logger.info("STARTING BATCH CLEANUP PROCESSING")
            logger.info("=" * 60)
            
            # Get all test files
            available_files = self.list_available_test_files()
            if not available_files:
                logger.warning("No test files found in example_sqs directory")
                return {
                    'total_files': 0,
                    'processed_files': 0,
                    'successful_files': 0,
                    'failed_files': 0,
                    'deleted_files': 0
                }
            
            logger.info(f"Found {len(available_files)} test files to process")
            
            # Step 1: Fetch Lambda environment variables once
            env_vars = self.fetch_lambda_environment()
            
            # Step 2: Set up local environment
            self.setup_local_environment(env_vars)
            
            # Initialize results tracking
            results = {
                'total_files': len(available_files),
                'processed_files': 0,
                'successful_files': 0,
                'failed_files': 0,
                'deleted_files': 0,
                'successful_file_list': [],
                'failed_file_list': [],
                'deleted_file_list': []
            }
            
            example_sqs_dir = current_dir / 'example_sqs'
            
            # Process each file
            for i, filename in enumerate(available_files, 1):
                logger.info(f"Processing file {i}/{len(available_files)}: {filename}")
                
                try:
                    # Run individual test
                    success = self.run_integration_test(filename, debug_mode=debug_mode)
                    results['processed_files'] += 1
                    
                    if success:
                        results['successful_files'] += 1
                        results['successful_file_list'].append(filename)
                        
                        # Delete the successful file
                        file_path = example_sqs_dir / filename
                        if file_path.exists():
                            file_path.unlink()
                            results['deleted_files'] += 1
                            results['deleted_file_list'].append(filename)
                            logger.info(f"✅ Deleted successful file: {filename}")
                        else:
                            logger.warning(f"File not found for deletion: {filename}")
                    else:
                        results['failed_files'] += 1
                        results['failed_file_list'].append(filename)
                        logger.error(f"❌ Keeping failed file: {filename}")
                        
                except Exception as e:
                    logger.error(f"Error processing file {filename}: {str(e)}")
                    results['failed_files'] += 1
                    results['failed_file_list'].append(filename)
            
            # Final summary
            logger.info("=" * 60)
            logger.info("BATCH CLEANUP RESULTS")
            logger.info("=" * 60)
            logger.info(f"Total files: {results['total_files']}")
            logger.info(f"Processed files: {results['processed_files']}")
            logger.info(f"Successful files: {results['successful_files']}")
            logger.info(f"Failed files: {results['failed_files']}")
            logger.info(f"Deleted files: {results['deleted_files']}")
            
            if results['successful_file_list']:
                logger.info(f"Deleted successful files: {', '.join(results['successful_file_list'])}")
            
            if results['failed_file_list']:
                logger.warning(f"Kept failed files: {', '.join(results['failed_file_list'])}")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch cleanup failed with exception: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'total_files': 0,
                'processed_files': 0,
                'successful_files': 0,
                'failed_files': 0,
                'deleted_files': 0,
                'error': str(e)
            }
        
        finally:
            # Restore original environment
            self.restore_environment()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Integration test for Security Hub Processor Lambda',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test with auto-selected file
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123:function:my-securityhub-processor

  # Test with specific file
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123:function:my-processor --test-file sqs_message_123.json

  # Dry run (doesn't send to Security Hub)
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123:function:my-processor --test-file sqs_message_123.json --dry-run

  # Debug mode (detailed error logging)
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123:function:my-processor --debug

  # Batch cleanup (process all files and delete successful ones)
  python integration_test.py --lambda-arn arn:aws:lambda:us-east-1:123:function:my-processor --batch-cleanup

  # List available test files
  python integration_test.py --list-files
        """
    )
    
    parser.add_argument(
        '--lambda-arn',
        type=str,
        help='ARN of the deployed Lambda function to test'
    )
    
    parser.add_argument(
        '--test-file',
        type=str,
        help='JSON file from example_sqs directory to test with'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run test without actually sending findings to Security Hub'
    )
    
    parser.add_argument(
        '--list-files',
        action='store_true',
        help='List available test files and exit'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Force DEBUG logging for detailed error analysis'
    )
    
    parser.add_argument(
        '--batch-cleanup',
        action='store_true',
        help='Process all files in example_sqs directory and delete successful ones'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("DEBUG mode enabled - will show detailed error information")
    else:
        logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Handle list files option
    if args.list_files:
        tester = SecurityHubTester('arn:aws:lambda:us-east-1:123456789012:function:dummy', dry_run=True)
        available_files = tester.list_available_test_files()
        
        if available_files:
            print("Available test files:")
            for i, filename in enumerate(available_files, 1):
                print(f"  {i}. {filename}")
        else:
            print("No test files found in example_sqs directory")
        return 0
    
    # Handle batch cleanup option
    if args.batch_cleanup:
        if not args.lambda_arn:
            parser.error("--lambda-arn is required for batch cleanup")
        
        try:
            # Initialize tester
            tester = SecurityHubTester(args.lambda_arn, dry_run=args.dry_run)
            
            # Run batch cleanup
            logger.info("Starting batch cleanup processing of all example files")
            results = tester.run_batch_cleanup(debug_mode=args.debug)
            
            # Print final results
            print("=" * 60)
            print("BATCH CLEANUP COMPLETED")
            print("=" * 60)
            print(f"Total files: {results['total_files']}")
            print(f"Processed files: {results['processed_files']}")
            print(f"Successful files: {results['successful_files']}")
            print(f"Failed files: {results['failed_files']}")
            print(f"Deleted files: {results['deleted_files']}")
            
            if results.get('error'):
                print(f"Error: {results['error']}")
                return 1
            
            return 0 if results['failed_files'] == 0 else 1
            
        except Exception as e:
            logger.error(f"Batch cleanup failed: {str(e)}")
            return 1
    
    # Validate required arguments
    if not args.lambda_arn:
        parser.error("--lambda-arn is required")
    
    try:
        # Initialize tester
        tester = SecurityHubTester(args.lambda_arn, dry_run=args.dry_run)
        
        # Determine test file
        test_file = args.test_file
        if not test_file:
            # Auto-select a test file
            available_files = tester.list_available_test_files()
            if not available_files:
                logger.error("No test files available in example_sqs directory")
                return 1
            
            test_file = available_files[0]
            logger.info(f"Auto-selected test file: {test_file}")
        
        # Run the integration test
        logger.info(f"Test file: {test_file}")
        success = tester.run_integration_test(test_file, debug_mode=args.debug)
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)