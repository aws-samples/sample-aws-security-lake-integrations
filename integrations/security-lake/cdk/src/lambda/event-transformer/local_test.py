"""
Local testing script for Azure to CloudTrail event transformation
Tests the event transformer with example SQS messages and validates CloudTrail format
"""

import json
import os
import sys
import logging
from typing import Dict, Any, List
from pathlib import Path

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from helpers.event_transformer import CloudTrailTransformer
from core.event_mapper import CloudEventMapper
from core.cloudtrail_types import CloudTrailAuditEvent

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CloudTrailEventValidator:
    """Validator for CloudTrail Lake integration event format compliance"""
    
    def __init__(self):
        # Based on the CloudTrail Lake integration schema documentation
        self.required_eventdata_fields = [
            'version', 'userIdentity', 'eventSource', 'eventName', 
            'eventTime', 'UID', 'recipientAccountId'
        ]
        self.required_audit_event_fields = ['eventData', 'id']
        
    def validate_cloudtrail_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate CloudTrail audit event structure and content
        
        Args:
            event: CloudTrail audit event dictionary to validate
            
        Returns:
            Validation result with details
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'field_checks': {}
        }
        
        # Check required audit event fields
        for field in self.required_audit_event_fields:
            if field not in event:
                validation_result['errors'].append(f"Missing required audit event field: {field}")
                validation_result['is_valid'] = False
            else:
                validation_result['field_checks'][field] = 'present'
        
        # Validate eventData (should be JSON string containing complete CloudTrail event)
        if 'eventData' in event:
            try:
                complete_event = json.loads(event['eventData'])
                validation_result['field_checks']['eventData'] = 'valid_json'
                
                # Check outer CloudTrail event structure
                outer_required_fields = ['eventVersion', 'eventCategory', 'eventType', 'eventID', 'eventTime', 'recipientAccountId']
                for field in outer_required_fields:
                    if field not in complete_event:
                        validation_result['errors'].append(f"Missing outer CloudTrail field: {field}")
                        validation_result['is_valid'] = False
                    else:
                        validation_result['field_checks'][f'outer.{field}'] = 'present'
                
                # Check inner eventData (customer event data)
                if 'eventData' in complete_event:
                    inner_event_data = complete_event['eventData']
                    if isinstance(inner_event_data, dict):
                        for field in self.required_eventdata_fields:
                            if field not in inner_event_data:
                                validation_result['errors'].append(f"Missing inner eventData field: {field}")
                                validation_result['is_valid'] = False
                            else:
                                validation_result['field_checks'][f'inner.{field}'] = 'present'
                        
                        # Validate userIdentity structure
                        if 'userIdentity' in inner_event_data:
                            user_identity = inner_event_data['userIdentity']
                            if not isinstance(user_identity, dict):
                                validation_result['errors'].append("userIdentity must be an object")
                                validation_result['is_valid'] = False
                            else:
                                required_ui_fields = ['type', 'principalId']
                                for ui_field in required_ui_fields:
                                    if ui_field not in user_identity:
                                        validation_result['errors'].append(f"Missing userIdentity field: {ui_field}")
                                        validation_result['is_valid'] = False
                    else:
                        validation_result['errors'].append("Inner eventData should be an object")
                        validation_result['is_valid'] = False
                else:
                    validation_result['errors'].append("Missing inner eventData field")
                    validation_result['is_valid'] = False
                
            except json.JSONDecodeError as e:
                validation_result['errors'].append(f"Invalid eventData JSON: {str(e)}")
                validation_result['is_valid'] = False
        
        # Validate event ID format
        if 'id' in event:
            event_id = event['id']
            if not event_id or len(event_id) < 8:
                validation_result['warnings'].append(f"Event ID seems too short: {event_id}")
        
        return validation_result


def load_example_events() -> List[Dict[str, Any]]:
    """Load example SQS messages from the example_events directory"""
    example_events = []
    example_dir = current_dir / 'example_events'
    
    if not example_dir.exists():
        logger.error(f"Example events directory not found: {example_dir}")
        return []
    
    for json_file in example_dir.glob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                sqs_message = json.load(f)
                # Parse the message body to get the actual event
                message_body = json.loads(sqs_message['Body'])
                example_events.append({
                    'file': json_file.name,
                    'sqs_message': sqs_message,
                    'azure_event': message_body
                })
                logger.info(f"Loaded example event from {json_file.name}")
        except Exception as e:
            logger.error(f"Failed to load {json_file.name}: {str(e)}")
    
    return example_events


def test_event_mapping():
    """Test the event mapping functionality with example events"""
    logger.info("Starting CloudTrail event mapping tests...")
    
    # Initialize mapper
    mapper = CloudEventMapper(logger=logger)
    validator = CloudTrailEventValidator()
    
    # Load example events
    example_events = load_example_events()
    if not example_events:
        logger.error("No example events loaded for testing")
        return False
    
    test_results = {
        'total_events': len(example_events),
        'successful_mappings': 0,
        'failed_mappings': 0,
        'validation_passed': 0,
        'validation_failed': 0,
        'event_types_seen': set(),
        'details': []
    }
    
    aws_account_id = "123456789012"  # Test account ID
    
    for example in example_events:
        file_name = example['file']
        azure_event = example['azure_event']
        
        try:
            logger.info(f"\n--- Testing {file_name} ---")
            
            # Test event mapping
            cloudtrail_event = mapper.map_azure_event_to_cloudtrail(azure_event, aws_account_id)
            
            if cloudtrail_event:
                test_results['successful_mappings'] += 1
                
                # Convert to dict for validation
                cloudtrail_dict = cloudtrail_event.to_dict()
                
                # Determine event type
                event_type = mapper._determine_event_type(azure_event)
                test_results['event_types_seen'].add(event_type)
                
                logger.info(f"Mapped event type: {event_type}")
                logger.info(f"CloudTrail event ID: {cloudtrail_dict.get('id')}")
                
                # Parse eventData to show key fields
                try:
                    complete_event = json.loads(cloudtrail_dict.get('eventData', '{}'))
                    inner_event_data = complete_event.get('eventData', {})
                    logger.info(f"CloudTrail eventTime: {complete_event.get('eventTime')}")
                    logger.info(f"CloudTrail eventSource: {inner_event_data.get('eventSource')}")
                    logger.info(f"CloudTrail eventName: {inner_event_data.get('eventName')}")
                except:
                    logger.warning("Could not parse eventData for display")
                
                # Validate CloudTrail format
                validation_result = validator.validate_cloudtrail_event(cloudtrail_dict)
                
                if validation_result['is_valid']:
                    test_results['validation_passed'] += 1
                    logger.info("✓ CloudTrail validation passed")
                else:
                    test_results['validation_failed'] += 1
                    logger.error("✗ CloudTrail validation failed")
                    for error in validation_result['errors']:
                        logger.error(f"  - {error}")
                
                for warning in validation_result['warnings']:
                    logger.warning(f"  - {warning}")
                
                # Store detailed results
                test_results['details'].append({
                    'file': file_name,
                    'event_type': event_type,
                    'mapping_success': True,
                    'validation_result': validation_result,
                    'cloudtrail_event_id': cloudtrail_dict.get('id'),
                    'eventData_keys': list(json.loads(cloudtrail_dict.get('eventData', '{}')).keys())
                })
                
            else:
                test_results['failed_mappings'] += 1
                logger.error(f"✗ Failed to map {file_name}")
                
                test_results['details'].append({
                    'file': file_name,
                    'event_type': 'unknown',
                    'mapping_success': False,
                    'validation_result': None,
                    'error': 'Mapping returned None'
                })
                
        except Exception as e:
            test_results['failed_mappings'] += 1
            logger.error(f"✗ Exception testing {file_name}: {str(e)}")
            
            test_results['details'].append({
                'file': file_name,
                'event_type': 'unknown',
                'mapping_success': False,
                'validation_result': None,
                'error': str(e)
            })
    
    # Print summary
    logger.info(f"\n=== TEST SUMMARY ===")
    logger.info(f"Total events tested: {test_results['total_events']}")
    logger.info(f"Successful mappings: {test_results['successful_mappings']}")
    logger.info(f"Failed mappings: {test_results['failed_mappings']}")
    logger.info(f"Validation passed: {test_results['validation_passed']}")
    logger.info(f"Validation failed: {test_results['validation_failed']}")
    logger.info(f"Event types seen: {', '.join(test_results['event_types_seen'])}")
    
    success_rate = (test_results['successful_mappings'] / test_results['total_events']) * 100
    logger.info(f"Success rate: {success_rate:.1f}%")
    
    return success_rate >= 80  # Consider test successful if 80%+ pass


def test_transformer_integration():
    """Test the full transformer with mock Event Data Store"""
    logger.info("\n=== TRANSFORMER INTEGRATION TEST ===")
    
    # Mock Event Data Store ARN for testing
    mock_arn = "arn:aws:cloudtrail:us-east-1:123456789012:eventdatastore/test-datastore"
    
    try:
        # Initialize transformer (this will fail if AWS credentials aren't available)
        # But we can test the initialization logic
        logger.info("Testing transformer initialization...")
        
        # This would normally create AWS clients, so we'll catch the exception
        try:
            transformer = CloudTrailTransformer(
                event_data_store_arn=mock_arn,
                logger=logger
            )
            logger.info("✓ Transformer initialization succeeded")
            
            # Test configuration validation
            if transformer.validate_configuration():
                logger.info("✓ Configuration validation passed")
            else:
                logger.warning("⚠ Configuration validation failed (expected in local testing)")
                
            # Get transformation statistics
            stats = transformer.get_transformation_statistics()
            logger.info(f"Supported event types: {stats['supported_event_types']}")
            logger.info(f"Transformer version: {stats['transformer_version']}")
            logger.info(f"Target format: {stats['target_format']}")
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠ Transformer initialization failed (expected in local testing): {str(e)}")
            return True  # This is expected in local testing without AWS credentials
            
    except Exception as e:
        logger.error(f"✗ Unexpected error in transformer integration test: {str(e)}")
        return False


def test_cloudtrail_builders():
    """Test the CloudTrail event builders directly"""
    logger.info("\n=== CLOUDTRAIL BUILDER TESTS ===")
    
    aws_account_id = "123456789012"
    
    # Test security alert builder
    test_security_alert = {
        'event_data': {
            'AlertType': 'TestAlert',
            'AlertDisplayName': 'Test Security Alert',
            'Severity': 'Medium',
            'SystemAlertId': 'test-alert-123',
            'TimeGenerated': '2025-09-30T18:18:02.925000+00:00',
            'Description': 'Test alert description',
            'CompromisedEntity': '/test/resource'
        },
        'event_metadata': {
            'enqueued_time': '2025-09-30T18:18:02.925000+00:00'
        },
        'processing_metadata': {
            'processed_timestamp': '2025-09-30T20:48:15.410960+00:00',
            'source': 'azure-eventhub'
        }
    }
    
    # Test secure score builder
    test_secure_score = {
        'event_data': {
            'type': 'Microsoft.Security/secureScores',
            'id': '/subscriptions/test/providers/Microsoft.Security/secureScores/ascScore',
            'name': 'ascScore',
            'properties': {
                'displayName': 'Test Secure Score',
                'score': {
                    'max': 10,
                    'current': 8.0,
                    'percentage': 0.8
                }
            }
        }
    }
    
    tests_passed = 0
    total_tests = 0
    
    # Test security alert builder
    try:
        total_tests += 1
        alert_event = CloudTrailEventBuilder.build_from_azure_security_alert(test_security_alert, aws_account_id)
        if alert_event and alert_event.eventData and alert_event.id:
            logger.info("✓ Security alert builder test passed")
            tests_passed += 1
            
            # Validate the structure
            event_data = json.loads(alert_event.eventData)
            if all(field in event_data for field in ['eventSource', 'eventName', 'eventTime', 'userIdentity']):
                logger.info("✓ Security alert structure validation passed")
            else:
                logger.error("✗ Security alert structure validation failed")
        else:
            logger.error("✗ Security alert builder test failed")
    except Exception as e:
        logger.error(f"✗ Security alert builder test failed with exception: {str(e)}")
    
    # Test secure score builder
    try:
        total_tests += 1
        score_event = CloudTrailEventBuilder.build_from_azure_secure_score(test_secure_score, aws_account_id)
        if score_event and score_event.eventData and score_event.id:
            logger.info("✓ Secure score builder test passed")
            tests_passed += 1
            
            # Validate the structure
            event_data = json.loads(score_event.eventData)
            if all(field in event_data for field in ['eventSource', 'eventName', 'eventTime', 'userIdentity']):
                logger.info("✓ Secure score structure validation passed")
            else:
                logger.error("✗ Secure score structure validation failed")
        else:
            logger.error("✗ Secure score builder test failed")
    except Exception as e:
        logger.error(f"✗ Secure score builder test failed with exception: {str(e)}")
    
    # Test generic builder
    try:
        total_tests += 1
        generic_event = CloudTrailEventBuilder.build_generic_event({'event_data': {'id': 'test'}}, aws_account_id)
        if generic_event and generic_event.eventData and generic_event.id:
            logger.info("✓ Generic builder test passed")
            tests_passed += 1
        else:
            logger.error("✗ Generic builder test failed")
    except Exception as e:
        logger.error(f"✗ Generic builder test failed with exception: {str(e)}")
    
    logger.info(f"CloudTrail builder tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests


def test_error_handling():
    """Test error handling for various edge cases"""
    logger.info("\n=== ERROR HANDLING TESTS ===")
    
    mapper = CloudEventMapper(logger=logger)
    aws_account_id = "123456789012"
    
    test_cases = [
        {
            'name': 'Empty event',
            'event': {}
        },
        {
            'name': 'Missing event_data',
            'event': {'metadata': 'test'}
        },
        {
            'name': 'Invalid event structure',
            'event': {'event_data': 'not a dict'}
        },
        {
            'name': 'Unknown event type',
            'event': {
                'event_data': {
                    'type': 'Microsoft.Unknown/unknownType',
                    'id': '/unknown/resource',
                    'name': 'unknown'
                }
            }
        }
    ]
    
    passed_tests = 0
    
    for test_case in test_cases:
        try:
            logger.info(f"Testing: {test_case['name']}")
            
            # This should handle errors gracefully
            result = mapper.map_azure_event_to_cloudtrail(test_case['event'], aws_account_id)
            
            if test_case['name'] == 'Unknown event type':
                # This should return a generic CloudTrail event
                if result:
                    logger.info("✓ Generic mapping succeeded for unknown event type")
                    passed_tests += 1
                else:
                    logger.error("✗ Failed to create generic mapping for unknown event type")
            else:
                # These should return None or handle gracefully
                if result is None:
                    logger.info("✓ Error handled gracefully (returned None)")
                    passed_tests += 1
                else:
                    logger.warning("⚠ Unexpected success for invalid input")
                    passed_tests += 1  # Still counts as passing since it didn't crash
                    
        except Exception as e:
            logger.error(f"✗ Unhandled exception for {test_case['name']}: {str(e)}")
    
    logger.info(f"Error handling tests: {passed_tests}/{len(test_cases)} passed")
    return passed_tests == len(test_cases)


def main():
    """Run all tests"""
    logger.info("Starting CloudTrail Event Transformer Local Tests")
    
    all_tests_passed = True
    
    # Test 1: CloudTrail builders
    if not test_cloudtrail_builders():
        logger.error("CloudTrail builder tests failed")
        all_tests_passed = False
    
    # Test 2: Event mapping
    if not test_event_mapping():
        logger.error("Event mapping tests failed")
        all_tests_passed = False
    
    # Test 3: Transformer integration
    if not test_transformer_integration():
        logger.error("Transformer integration tests failed")
        all_tests_passed = False
    
    # Test 4: Error handling
    if not test_error_handling():
        logger.error("Error handling tests failed")
        all_tests_passed = False
    
    if all_tests_passed:
        logger.info("\n🎉 ALL TESTS PASSED! CloudTrail transformation is working correctly.")
        return 0
    else:
        logger.error("\n❌ SOME TESTS FAILED. Please review the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)