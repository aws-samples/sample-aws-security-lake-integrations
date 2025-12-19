# (c) 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
YAML structure validator for transformation templates.

This module validates the YAML structure of transformation templates,
checking for required fields, correct types, and building a line number map
for error reporting.
"""

import re
from typing import Dict, Any, List, Optional, Tuple

import yaml

from .errors import (
    ValidationError,
    ValidationResult,
    ValidationPhase,
    ValidationSeverity,
)


class YamlValidator:
    """
    Validates the YAML structure of transformation templates.
    
    This validator:
    - Loads YAML content and parses it
    - Builds a line number map for accurate error reporting
    - Validates required fields exist
    - Validates field types are correct
    - Checks for template-specific structural requirements
    """
    
    REQUIRED_FIELDS = ['name', 'input_schema', 'output_schema', 'extractors', 'template']
    
    FIELD_TYPES = {
        'name': str,
        'input_schema': str,
        'output_schema': str,
        'extractors': dict,
        'template': str,
        'filters': dict,
        'conditionals': dict,
    }
    
    def __init__(self, template_file: str):
        """
        Initialize the YAML validator.
        
        Args:
            template_file: Path to the template file being validated
        """
        self.template_file = template_file
        self.line_map: Dict[str, int] = {}
        self.content: str = ''
        self.parsed_data: Optional[Dict[str, Any]] = None
    
    def validate(self, content: str) -> ValidationResult:
        """
        Validate YAML content from a template file.
        
        Args:
            content: Raw YAML content to validate
            
        Returns:
            ValidationResult with any errors found
        """
        self.content = content
        result = ValidationResult(template_file=self.template_file)
        
        # Build line number map first
        self._build_line_map(content)
        
        # Parse YAML
        try:
            self.parsed_data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            error_msg = str(e)
            line_num = None
            
            # Extract line number from YAML error if available
            if hasattr(e, 'problem_mark') and e.problem_mark:
                line_num = e.problem_mark.line + 1
            
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.ERROR,
                message=f'YAML parsing error: {error_msg}',
                template_file=self.template_file,
                line_number=line_num,
            ))
            return result
        
        if self.parsed_data is None:
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.ERROR,
                message='Template file is empty or contains only whitespace',
                template_file=self.template_file,
            ))
            return result
        
        if not isinstance(self.parsed_data, dict):
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.ERROR,
                message=f'Template must be a YAML mapping, got {type(self.parsed_data).__name__}',
                template_file=self.template_file,
            ))
            return result
        
        # Validate required fields
        self._validate_required_fields(result)
        
        # Validate field types
        self._validate_field_types(result)
        
        # Validate extractors structure
        if 'extractors' in self.parsed_data and isinstance(self.parsed_data['extractors'], dict):
            self._validate_extractors(result)
        
        # Validate filters structure if present
        if 'filters' in self.parsed_data and self.parsed_data['filters'] is not None:
            self._validate_filters(result)
        
        return result
    
    def _build_line_map(self, content: str) -> None:
        """
        Build a map of field paths to their line numbers in the YAML file.
        
        This uses a simple parsing approach that tracks indentation levels
        to determine the current path in the document.
        
        Args:
            content: Raw YAML content
        """
        self.line_map = {}
        lines = content.split('\n')
        
        # Stack to track current path and indentation
        path_stack: List[Tuple[int, str]] = []  # (indent_level, key)
        
        for line_num, line in enumerate(lines, 1):
            # Skip empty lines and comments
            stripped = line.lstrip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # Calculate indentation level
            indent = len(line) - len(stripped)
            
            # Check if this line defines a key
            key_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*:', stripped)
            if key_match:
                key = key_match.group(1)
                
                # Pop path_stack until we find a lower indentation level
                while path_stack and path_stack[-1][0] >= indent:
                    path_stack.pop()
                
                # Build current path
                if path_stack:
                    current_path = '.'.join(p[1] for p in path_stack) + '.' + key
                else:
                    current_path = key
                
                # Record line number for this path
                self.line_map[current_path] = line_num
                
                # Push to stack for nested keys
                path_stack.append((indent, key))
    
    def get_line_number(self, field_path: str) -> Optional[int]:
        """
        Get the line number for a given field path.
        
        Args:
            field_path: Dot-separated path to the field (e.g., "extractors.alert_id")
            
        Returns:
            Line number or None if not found
        """
        return self.line_map.get(field_path)
    
    def get_template_start_line(self) -> Optional[int]:
        """
        Get the line number where the 'template:' field starts.
        
        This is useful for calculating line offsets when reporting
        Jinja2 template errors.
        
        Returns:
            Line number where template field begins, or None if not found
        """
        return self.line_map.get('template')
    
    def _validate_required_fields(self, result: ValidationResult) -> None:
        """Validate that all required fields are present."""
        for field in self.REQUIRED_FIELDS:
            if field not in self.parsed_data:
                result.add_error(ValidationError(
                    phase=ValidationPhase.YAML_STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing required field '{field}'",
                    template_file=self.template_file,
                    field_path=field,
                    suggestion=f"Add the '{field}' field to the template",
                ))
    
    def _validate_field_types(self, result: ValidationResult) -> None:
        """Validate that fields have the correct types."""
        for field, expected_type in self.FIELD_TYPES.items():
            if field not in self.parsed_data:
                continue
            
            value = self.parsed_data[field]
            
            # Allow None for optional fields
            if value is None and field not in self.REQUIRED_FIELDS:
                continue
            
            if not isinstance(value, expected_type):
                actual_type = type(value).__name__ if value is not None else 'None'
                line_num = self.get_line_number(field)
                
                result.add_error(ValidationError(
                    phase=ValidationPhase.YAML_STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Field '{field}' must be of type {expected_type.__name__}, got {actual_type}",
                    template_file=self.template_file,
                    line_number=line_num,
                    field_path=field,
                ))
    
    def _validate_extractors(self, result: ValidationResult) -> None:
        """Validate the extractors section structure."""
        extractors = self.parsed_data.get('extractors', {})
        
        if not extractors:
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.ERROR,
                message='Extractors section is empty - at least one extractor is required',
                template_file=self.template_file,
                field_path='extractors',
                line_number=self.get_line_number('extractors'),
            ))
            return
        
        for name, jsonpath_expr in extractors.items():
            field_path = f'extractors.{name}'
            line_num = self.get_line_number(field_path)
            
            if not isinstance(jsonpath_expr, str):
                result.add_error(ValidationError(
                    phase=ValidationPhase.YAML_STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Extractor '{name}' must have a string value (JSONPath expression)",
                    template_file=self.template_file,
                    line_number=line_num,
                    field_path=field_path,
                    raw_value=str(jsonpath_expr)[:100] if jsonpath_expr else None,
                ))
            elif not jsonpath_expr.strip():
                result.add_error(ValidationError(
                    phase=ValidationPhase.YAML_STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Extractor '{name}' has an empty JSONPath expression",
                    template_file=self.template_file,
                    line_number=line_num,
                    field_path=field_path,
                ))
    
    def _validate_filters(self, result: ValidationResult) -> None:
        """Validate the filters section structure."""
        filters = self.parsed_data.get('filters')
        
        if filters is None:
            return
        
        if not isinstance(filters, dict):
            result.add_error(ValidationError(
                phase=ValidationPhase.YAML_STRUCTURE,
                severity=ValidationSeverity.ERROR,
                message='Filters must be a dictionary mapping filter names to code',
                template_file=self.template_file,
                line_number=self.get_line_number('filters'),
                field_path='filters',
            ))
            return
        
        for name, code in filters.items():
            field_path = f'filters.{name}'
            line_num = self.get_line_number(field_path)
            
            if not isinstance(code, str):
                result.add_error(ValidationError(
                    phase=ValidationPhase.YAML_STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message=f"Filter '{name}' must have a string value (Python code)",
                    template_file=self.template_file,
                    line_number=line_num,
                    field_path=field_path,
                ))
            elif not code.strip():
                result.add_error(ValidationError(
                    phase=ValidationPhase.YAML_STRUCTURE,
                    severity=ValidationSeverity.WARNING,
                    message=f"Filter '{name}' has empty code",
                    template_file=self.template_file,
                    line_number=line_num,
                    field_path=field_path,
                ))
    
    def get_parsed_data(self) -> Optional[Dict[str, Any]]:
        """
        Get the parsed YAML data.
        
        Returns:
            Parsed YAML as a dictionary, or None if parsing failed
        """
        return self.parsed_data
    
    def get_extractors(self) -> Dict[str, str]:
        """
        Get the extractors from the parsed template.
        
        Returns:
            Dictionary of extractor names to JSONPath expressions
        """
        if self.parsed_data:
            return self.parsed_data.get('extractors', {})
        return {}
    
    def get_template_content(self) -> Optional[str]:
        """
        Get the template content from the parsed data.
        
        Returns:
            Template string or None if not found
        """
        if self.parsed_data:
            return self.parsed_data.get('template')
        return None
    
    def get_filters(self) -> Dict[str, str]:
        """
        Get the custom filters from the parsed template.
        
        Returns:
            Dictionary of filter names to Python code
        """
        if self.parsed_data:
            return self.parsed_data.get('filters', {}) or {}
        return {}