# (c) 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
JSONPath expression validator for transformation templates.

This module validates JSONPath expressions in the extractors section,
ensuring they have valid syntax and providing helpful suggestions for
common errors.
"""

from typing import Dict, List, Optional

from .errors import (
    ValidationError,
    ValidationResult,
    ValidationPhase,
    ValidationSeverity,
)


class JsonPathValidator:
    """
    Validates JSONPath expressions in transformation templates.
    
    This validator:
    - Parses each JSONPath expression using jsonpath-ng
    - Provides helpful error messages for invalid syntax
    - Suggests fixes for common mistakes
    """
    
    # Common JSONPath mistakes and their suggestions
    COMMON_MISTAKES = {
        'missing_dollar': (
            'JSONPath expression must start with $',
            'Add $ at the beginning of the expression'
        ),
        'unmatched_bracket': (
            'Unmatched bracket in JSONPath expression',
            'Check that all [ and ] brackets are properly matched'
        ),
        'empty_path': (
            'JSONPath expression is empty',
            'Provide a valid JSONPath expression starting with $'
        ),
        'double_dot_at_start': (
            'Expression cannot start with ..',
            'Start with $ followed by .field or ..field for recursive descent'
        ),
        'invalid_field_name': (
            'Invalid field name in JSONPath',
            'Field names should contain only alphanumeric characters and underscores'
        ),
    }
    
    def __init__(self, template_file: str, line_map: Optional[Dict[str, int]] = None):
        """
        Initialize the JSONPath validator.
        
        Args:
            template_file: Path to the template file being validated
            line_map: Optional mapping of field paths to line numbers
        """
        self.template_file = template_file
        self.line_map = line_map or {}
        self._jsonpath_available = False
        self._import_jsonpath()
    
    def _import_jsonpath(self) -> None:
        """Attempt to import the jsonpath-ng library."""
        try:
            from jsonpath_ng import parse as jsonpath_parse
            from jsonpath_ng.exceptions import JSONPathError
            self._jsonpath_parse = jsonpath_parse
            self._JSONPathError = JSONPathError
            self._jsonpath_available = True
        except ImportError:
            self._jsonpath_parse = None
            self._JSONPathError = Exception
            self._jsonpath_available = False
    
    def validate(self, extractors: Dict[str, str]) -> ValidationResult:
        """
        Validate all JSONPath expressions in the extractors dictionary.
        
        Args:
            extractors: Dictionary mapping field names to JSONPath expressions
            
        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(template_file=self.template_file)
        
        if not self._jsonpath_available:
            result.add_error(ValidationError(
                phase=ValidationPhase.JSONPATH_SYNTAX,
                severity=ValidationSeverity.WARNING,
                message='jsonpath-ng library not available - skipping JSONPath validation',
                template_file=self.template_file,
                suggestion='Install jsonpath-ng: pip install jsonpath-ng',
            ))
            return result
        
        if not extractors:
            return result
        
        for name, jsonpath_expr in extractors.items():
            field_path = f'extractors.{name}'
            line_num = self.line_map.get(field_path)
            
            # Skip non-string values (should be caught by YAML validator)
            if not isinstance(jsonpath_expr, str):
                continue
            
            # Validate the expression
            errors = self._validate_expression(name, jsonpath_expr, field_path, line_num)
            for error in errors:
                result.add_error(error)
        
        return result
    
    def _validate_expression(
        self, 
        name: str, 
        expr: str, 
        field_path: str,
        line_num: Optional[int]
    ) -> List[ValidationError]:
        """
        Validate a single JSONPath expression.
        
        Args:
            name: Name of the extractor field
            expr: JSONPath expression to validate
            field_path: Full path to the field for error reporting
            line_num: Line number in the source file
            
        Returns:
            List of validation errors
        """
        errors = []
        expr_stripped = expr.strip()
        
        # Check for empty expression
        if not expr_stripped:
            errors.append(self._create_error(
                'empty_path', field_path, line_num, expr
            ))
            return errors
        
        # Check for missing $ at start
        if not expr_stripped.startswith('$'):
            errors.append(self._create_error(
                'missing_dollar', field_path, line_num, expr
            ))
            return errors
        
        # Check for starting with ..
        if expr_stripped.startswith('..'):
            errors.append(self._create_error(
                'double_dot_at_start', field_path, line_num, expr
            ))
            return errors
        
        # Check for unmatched brackets
        if expr_stripped.count('[') != expr_stripped.count(']'):
            errors.append(self._create_error(
                'unmatched_bracket', field_path, line_num, expr
            ))
            return errors
        
        # Try to parse the expression
        try:
            self._jsonpath_parse(expr_stripped)
        except self._JSONPathError as e:
            error_msg = str(e)
            suggestion = self._get_suggestion_for_error(error_msg, expr_stripped)
            
            errors.append(ValidationError(
                phase=ValidationPhase.JSONPATH_SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=f"Invalid JSONPath expression for '{name}': {error_msg}",
                template_file=self.template_file,
                line_number=line_num,
                field_path=field_path,
                raw_value=expr_stripped,
                suggestion=suggestion,
            ))
        except Exception as e:
            # Catch any other parsing errors
            errors.append(ValidationError(
                phase=ValidationPhase.JSONPATH_SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=f"Failed to parse JSONPath expression for '{name}': {str(e)}",
                template_file=self.template_file,
                line_number=line_num,
                field_path=field_path,
                raw_value=expr_stripped,
            ))
        
        return errors
    
    def _create_error(
        self,
        error_type: str,
        field_path: str,
        line_num: Optional[int],
        raw_value: str
    ) -> ValidationError:
        """Create a validation error for a known error type."""
        message, suggestion = self.COMMON_MISTAKES.get(
            error_type, 
            ('Unknown JSONPath error', None)
        )
        
        return ValidationError(
            phase=ValidationPhase.JSONPATH_SYNTAX,
            severity=ValidationSeverity.ERROR,
            message=message,
            template_file=self.template_file,
            line_number=line_num,
            field_path=field_path,
            raw_value=raw_value,
            suggestion=suggestion,
        )
    
    def _get_suggestion_for_error(self, error_msg: str, expr: str) -> Optional[str]:
        """
        Generate a helpful suggestion based on the error message.
        
        Args:
            error_msg: Error message from JSONPath parser
            expr: The original expression
            
        Returns:
            Suggestion string or None
        """
        error_lower = error_msg.lower()
        
        # Pattern-based suggestions
        if 'unexpected' in error_lower:
            return 'Check the JSONPath syntax near the unexpected character'
        
        if 'expecting' in error_lower:
            return 'Verify the expression follows JSONPath grammar rules'
        
        if 'token' in error_lower:
            return 'Check for special characters that need escaping'
        
        if 'parse' in error_lower:
            # Provide a generic parsing suggestion
            if '.' in expr and not expr.startswith('$.'):
                return "JSONPath expressions typically start with '$.' to access object properties"
            
        return 'Review JSONPath documentation for correct syntax'
    
    def validate_single(self, name: str, expr: str) -> List[ValidationError]:
        """
        Validate a single JSONPath expression.
        
        Convenience method for validating individual expressions.
        
        Args:
            name: Name/identifier for the expression
            expr: JSONPath expression to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        return self._validate_expression(name, expr, f'extractors.{name}', None)