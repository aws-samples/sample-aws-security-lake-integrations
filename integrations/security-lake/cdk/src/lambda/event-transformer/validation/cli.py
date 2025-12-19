# (c) 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
CLI entry point for template validation.

This module provides the main TemplateValidator class and command-line interface
for validating transformation templates.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from .errors import (
    ValidationError,
    ValidationResult,
    AggregatedValidationResult,
    ValidationPhase,
    ValidationSeverity,
)
from .yaml_validator import YamlValidator
from .jsonpath_validator import JsonPathValidator
from .jinja2_validator import Jinja2Validator
from .filter_validator import FilterValidator
from .json_output_validator import JsonOutputValidator


class TemplateValidator:
    """
    Orchestrates all validation phases for transformation templates.
    
    This class coordinates the validation pipeline:
    1. YAML structure validation
    2. JSONPath syntax validation
    3. Jinja2 template syntax validation
    4. Custom filter code validation
    5. JSON output validation
    """
    
    def __init__(
        self,
        strict: bool = True,
        warnings_as_errors: bool = False
    ):
        """
        Initialize the template validator.
        
        Args:
            strict: If True, stop validation on first error (per template)
            warnings_as_errors: If True, treat warnings as errors
        """
        self.strict = strict
        self.warnings_as_errors = warnings_as_errors
    
    def validate_template(self, template_path: str) -> ValidationResult:
        """
        Validate a single template file.
        
        Args:
            template_path: Path to the template YAML file
            
        Returns:
            ValidationResult with all errors and warnings found
        """
        result = ValidationResult(template_file=template_path)
        
        # Check file exists
        if not os.path.exists(template_path):
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.ERROR,
                message=f'Template file not found: {template_path}',
                template_file=template_path,
            ))
            return result
        
        # Read file content
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.ERROR,
                message=f'Failed to read template file: {str(e)}',
                template_file=template_path,
            ))
            return result
        
        # Phase 1: YAML structure validation
        yaml_validator = YamlValidator(template_path)
        yaml_result = yaml_validator.validate(content)
        result.merge(yaml_result)
        
        if self.strict and not yaml_result.valid:
            return result
        
        # Get parsed data for subsequent phases
        parsed_data = yaml_validator.get_parsed_data()
        if parsed_data is None:
            return result
        
        extractors = yaml_validator.get_extractors()
        template_content = yaml_validator.get_template_content()
        custom_filters = yaml_validator.get_filters()
        line_map = yaml_validator.line_map
        template_start_line = yaml_validator.get_template_start_line()
        
        # Phase 2: JSONPath validation
        if extractors:
            jsonpath_validator = JsonPathValidator(template_path, line_map)
            jsonpath_result = jsonpath_validator.validate(extractors)
            result.merge(jsonpath_result)
            
            if self.strict and not jsonpath_result.valid:
                return result
        
        # Phase 3: Jinja2 template validation
        if template_content:
            jinja2_validator = Jinja2Validator(
                template_path,
                template_start_line,
                line_map
            )
            jinja2_result = jinja2_validator.validate(
                template_content,
                extractors,
                custom_filters
            )
            result.merge(jinja2_result)
            
            if self.strict and not jinja2_result.valid:
                return result
        
        # Phase 4: Custom filter code validation
        if custom_filters:
            filter_validator = FilterValidator(template_path, line_map)
            filter_result = filter_validator.validate(custom_filters)
            result.merge(filter_result)
            
            if self.strict and not filter_result.valid:
                return result
        
        # Phase 5: JSON output validation
        if template_content and extractors:
            json_validator = JsonOutputValidator(template_path, template_start_line)
            json_result = json_validator.validate(
                template_content,
                extractors,
                custom_filters
            )
            result.merge(json_result)
        
        # Apply warnings_as_errors if enabled
        if self.warnings_as_errors and result.warnings:
            for warning in result.warnings:
                warning.severity = ValidationSeverity.ERROR
                result.errors.append(warning)
            result.warnings = []
            result.valid = len(result.errors) == 0
        
        return result
    
    def validate_directory(
        self,
        templates_dir: str,
        pattern: str = '*.yaml'
    ) -> AggregatedValidationResult:
        """
        Validate all template files in a directory.
        
        Args:
            templates_dir: Path to directory containing templates
            pattern: Glob pattern for template files
            
        Returns:
            AggregatedValidationResult with all template results
        """
        aggregated = AggregatedValidationResult()
        
        if not os.path.isdir(templates_dir):
            # Create a result for the missing directory
            result = ValidationResult(template_file=templates_dir)
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.ERROR,
                message=f'Templates directory not found: {templates_dir}',
                template_file=templates_dir,
            ))
            aggregated.add_result(result)
            return aggregated
        
        # Find all template files
        templates_path = Path(templates_dir)
        template_files = sorted(templates_path.glob(pattern))
        
        if not template_files:
            result = ValidationResult(template_file=templates_dir)
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.WARNING,
                message=f'No template files found in {templates_dir} matching pattern {pattern}',
                template_file=templates_dir,
            ))
            aggregated.add_result(result)
            return aggregated
        
        # Validate each template
        for template_file in template_files:
            template_path = str(template_file)
            result = self.validate_template(template_path)
            aggregated.add_result(result)
        
        return aggregated


def format_text_output(
    aggregated: AggregatedValidationResult,
    use_color: bool = True
) -> str:
    """
    Format validation results as human-readable text.
    
    Args:
        aggregated: Aggregated validation results
        use_color: Whether to use ANSI color codes
        
    Returns:
        Formatted text output
    """
    lines = []
    
    # Add summary header
    lines.append(aggregated.format_summary(use_color))
    lines.append('')
    
    # Add details for each template with issues
    for template_path, result in aggregated.results.items():
        if not result.valid or result.warnings:
            # Show template path
            lines.append(f'{os.path.basename(template_path)}:')
            
            # Show all issues
            for error in result.all_issues():
                lines.append(error.format_for_console(use_color))
                lines.append('')
    
    return '\n'.join(lines)


def format_json_output(aggregated: AggregatedValidationResult) -> str:
    """
    Format validation results as JSON.
    
    Args:
        aggregated: Aggregated validation results
        
    Returns:
        JSON string
    """
    return json.dumps(aggregated.to_dict(), indent=2)


def main(args: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point.
    
    Args:
        args: Command-line arguments (uses sys.argv if None)
        
    Returns:
        Exit code (0 for success, 1 for failures)
    """
    parser = argparse.ArgumentParser(
        description='Validate event-transformer templates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Validate all templates in a directory
  python -m validation.cli --templates-dir templates/
  
  # Validate a single template
  python -m validation.cli --template templates/security_alert_ocsf.yaml
  
  # Output as JSON
  python -m validation.cli --templates-dir templates/ --output-format json
  
  # Treat warnings as errors
  python -m validation.cli --templates-dir templates/ --warnings-as-errors
'''
    )
    
    parser.add_argument(
        '--templates-dir',
        type=str,
        default=None,
        help='Directory containing template files (default: ../templates relative to this script)'
    )
    
    parser.add_argument(
        '--template',
        type=str,
        default=None,
        help='Path to a single template file to validate'
    )
    
    parser.add_argument(
        '--output-format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    parser.add_argument(
        '--strict',
        action='store_true',
        default=True,
        help='Stop validation on first error per template (default: true)'
    )
    
    parser.add_argument(
        '--no-strict',
        action='store_false',
        dest='strict',
        help='Continue validation after errors to find all issues'
    )
    
    parser.add_argument(
        '--warnings-as-errors',
        action='store_true',
        default=False,
        help='Treat warnings as errors'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        default=False,
        help='Disable colored output'
    )
    
    parsed_args = parser.parse_args(args)
    
    # Determine templates to validate
    if parsed_args.template:
        # Single template mode
        validator = TemplateValidator(
            strict=parsed_args.strict,
            warnings_as_errors=parsed_args.warnings_as_errors
        )
        result = validator.validate_template(parsed_args.template)
        aggregated = AggregatedValidationResult()
        aggregated.add_result(result)
    elif parsed_args.templates_dir:
        # Directory mode with explicit path
        validator = TemplateValidator(
            strict=parsed_args.strict,
            warnings_as_errors=parsed_args.warnings_as_errors
        )
        aggregated = validator.validate_directory(parsed_args.templates_dir)
    else:
        # Default directory mode - look for templates relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_templates_dir = os.path.join(script_dir, '..', 'templates')
        
        if not os.path.isdir(default_templates_dir):
            print(f'Error: Templates directory not found at {default_templates_dir}', file=sys.stderr)
            print('Please specify --templates-dir or --template', file=sys.stderr)
            return 1
        
        validator = TemplateValidator(
            strict=parsed_args.strict,
            warnings_as_errors=parsed_args.warnings_as_errors
        )
        aggregated = validator.validate_directory(default_templates_dir)
    
    # Format output
    use_color = not parsed_args.no_color and sys.stdout.isatty()
    
    if parsed_args.output_format == 'json':
        output = format_json_output(aggregated)
    else:
        output = format_text_output(aggregated, use_color)
    
    print(output)
    
    # Return exit code
    return 0 if aggregated.all_valid else 1


if __name__ == '__main__':
    sys.exit(main())