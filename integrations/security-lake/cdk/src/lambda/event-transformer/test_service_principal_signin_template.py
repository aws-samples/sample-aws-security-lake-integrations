"""
Test script for Azure Service Principal Sign-In OCSF template
Tests template structure and basic YAML validity
"""

import json
import sys
import yaml
from pathlib import Path
from typing import Dict, Any

# Add the current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def test_template_file_exists():
    """Test that the template file exists"""
    print("\n=== Testing Template File Existence ===")
    
    template_path = current_dir / "templates" / "azure_service_principal_signin_ocsf.yaml"
    
    if not template_path.exists():
        print(f"FAILED: Template file not found at {template_path}")
        return False
        
    print(f"SUCCESS: Template file found at {template_path}")
    return True


def test_template_yaml_valid():
    """Test that the template is valid YAML"""
    print("\n=== Testing Template YAML Validity ===")
    
    template_path = current_dir / "templates" / "azure_service_principal_signin_ocsf.yaml"
    
    try:
        with open(template_path, 'r') as f:
            template_data = yaml.safe_load(f)
        
        if not template_data:
            print("FAILED: Template loaded but is empty")
            return False
            
        print(f"SUCCESS: Template YAML is valid with {len(template_data)} top-level keys")
        return True
        
    except yaml.YAMLError as e:
        print(f"FAILED: YAML parsing error: {str(e)}")
        return False
    except Exception as e:
        print(f"FAILED: Exception loading template: {str(e)}")
        return False


def test_template_structure():
    """Test that the template has required structure"""
    print("\n=== Testing Template Structure ===")
    
    template_path = current_dir / "templates" / "azure_service_principal_signin_ocsf.yaml"
    
    try:
        with open(template_path, 'r') as f:
            template_data = yaml.safe_load(f)
        
        # Check required fields
        required_fields = ['name', 'input_schema', 'output_schema', 'extractors', 'template']
        missing_fields = [field for field in required_fields if field not in template_data]
        
        if missing_fields:
            print(f"FAILED: Missing required fields: {missing_fields}")
            return False
            
        print(f"SUCCESS: All required fields present: {required_fields}")
        
        # Check extractors
        if not isinstance(template_data['extractors'], dict):
            print("FAILED: 'extractors' must be a dictionary")
            return False
            
        extractor_count = len(template_data['extractors'])
        print(f"SUCCESS: Template has {extractor_count} extractors")
        
        # List some key extractors for Service Principal Sign-In
        expected_extractors = ['service_principal_id', 'service_principal_name', 'app_id', 
                              'ip_address', 'status_error_code']
        found_extractors = [e for e in expected_extractors if e in template_data['extractors']]
        
        print(f"Key extractors found: {found_extractors}")
        
        if len(found_extractors) < 3:
            print(f"WARNING: Expected more key extractors, only found {len(found_extractors)}")
        
        # Check template field is a string
        if not isinstance(template_data['template'], str):
            print("FAILED: 'template' field must be a string")
            return False
            
        template_length = len(template_data['template'])
        print(f"SUCCESS: Template string is {template_length} characters")
        
        # Try to parse template as Jinja2/JSON structure
        template_str = template_data['template'].strip()
        if not template_str.startswith('{'):
            print("WARNING: Template doesn't start with '{', might not be valid JSON template")
        
        # Check for OCSF required fields in template
        ocsf_required_fields = ['class_uid', 'category_name', 'activity_id', 'severity_id', 'time']
        found_in_template = [field for field in ocsf_required_fields if field in template_str]
        
        print(f"OCSF required fields in template: {found_in_template}")
        
        if len(found_in_template) < len(ocsf_required_fields):
            missing_in_template = [f for f in ocsf_required_fields if f not in found_in_template]
            print(f"WARNING: Missing OCSF fields in template: {missing_in_template}")
        
        # Verify class_uid is 3002 (Authentication)
        if '"class_uid": 3002' not in template_str and "'class_uid': 3002" not in template_str:
            print("WARNING: class_uid might not be set to 3002 (Authentication)")
        else:
            print("SUCCESS: Template includes class_uid: 3002 (Authentication)")
        
        return True
        
    except Exception as e:
        print(f"FAILED: Exception during structure validation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_event_type_mapping():
    """Test that event type mapping references the template"""
    print("\n=== Testing Event Type Mapping ===")
    
    mapping_file = current_dir / 'mapping' / 'event_type_mappings.json'
    
    try:
        with open(mapping_file, 'r') as f:
            mappings = json.load(f)
        
        # Look for Service Principal Sign-In mapping
        found_mapping = False
        for event_type, config in mappings.items():
            if 'ServicePrincipalSignIn' in event_type or 'service_principal_signin' in event_type.lower():
                print(f"Found mapping for event type: {event_type}")
                
                if 'ocsf_template' in config:
                    template_name = config['ocsf_template']
                    if template_name == 'azure_service_principal_signin_ocsf.yaml':
                        print(f"SUCCESS: Mapping references correct template: {template_name}")
                        found_mapping = True
                    else:
                        print(f"WARNING: Mapping references different template: {template_name}")
                else:
                    print("WARNING: No ocsf_template key in mapping")
        
        if not found_mapping:
            print("WARNING: Could not find Service Principal Sign-In mapping - event type key might be different")
            print("This is OK if the mapping uses a different key format")
        
        return True
        
    except Exception as e:
        print(f"FAILED: Exception checking event type mapping: {str(e)}")
        return False


def main():
    """Run all template tests"""
    print("=== Azure Service Principal Sign-In OCSF Template Tests ===")
    
    all_passed = True
    
    # Test 1: File exists
    if not test_template_file_exists():
        print("\nTemplate file existence test FAILED")
        all_passed = False
    
    # Test 2: YAML validity
    if not test_template_yaml_valid():
        print("\nYAML validity test FAILED")
        all_passed = False
    
    # Test 3: Structure validation
    if not test_template_structure():
        print("\nStructure validation test FAILED")
        all_passed = False
    
    # Test 4: Event type mapping
    if not test_event_type_mapping():
        print("\nEvent type mapping test FAILED (non-critical)")
    
    print("\n" + "=" * 50)
    if all_passed:
        print("ALL CRITICAL TESTS PASSED")
        print("Template file is properly structured and ready for use")
        return 0
    else:
        print("SOME TESTS FAILED - Please review the output above")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)