# (c) 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
Custom filter code validator for transformation templates.

This module validates Python code defined in custom filters,
ensuring it has valid syntax and the function name matches the filter key.
"""

import ast
import re
from typing import Dict, List, Optional

from .errors import (
    ValidationError,
    ValidationResult,
    ValidationPhase,
    ValidationSeverity,
)


class FilterValidator:
    """
    Validates custom filter Python code in transformation templates.
    
    This validator:
    - Uses ast.parse() to validate Python syntax
    - Verifies the defined function name matches the filter key
    - Checks for basic code quality issues
    """
    
    def __init__(
        self,
        template_file: str,
        line_map: Optional[Dict[str, int]] = None
    ):
        """
        Initialize the filter validator.
        
        Args:
            template_file: Path to the template file being validated
            line_map: Optional mapping of field paths to line numbers
        """
        self.template_file = template_file
        self.line_map = line_map or {}
    
    def validate(self, filters: Dict[str, str]) -> ValidationResult:
        """
        Validate all custom filter code in the filters dictionary.
        
        Args:
            filters: Dictionary mapping filter names to Python code strings
            
        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(template_file=self.template_file)
        
        if not filters:
            return result
        
        for filter_name, filter_code in filters.items():
            field_path = f'filters.{filter_name}'
            line_num = self.line_map.get(field_path)
            
            # Skip non-string values (should be caught by YAML validator)
            if not isinstance(filter_code, str):
                continue
            
            # Validate the filter code
            errors = self._validate_filter(filter_name, filter_code, field_path, line_num)
            for error in errors:
                result.add_error(error)
        
        return result
    
    def _validate_filter(
        self,
        filter_name: str,
        filter_code: str,
        field_path: str,
        line_num: Optional[int]
    ) -> List[ValidationError]:
        """
        Validate a single filter's Python code.
        
        Args:
            filter_name: Expected function name
            filter_code: Python code defining the filter
            field_path: Full path to the field for error reporting
            line_num: Line number in the source file
            
        Returns:
            List of validation errors
        """
        errors = []
        code_stripped = filter_code.strip()
        
        # Check for empty code
        if not code_stripped:
            errors.append(ValidationError(
                phase=ValidationPhase.FILTER_CODE,
                severity=ValidationSeverity.WARNING,
                message=f"Filter '{filter_name}' has empty code",
                template_file=self.template_file,
                line_number=line_num,
                field_path=field_path,
            ))
            return errors
        
        # Parse the code using AST
        try:
            tree = ast.parse(code_stripped)
        except SyntaxError as e:
            error_line = line_num
            if error_line and e.lineno:
                error_line = line_num + e.lineno - 1
            
            errors.append(ValidationError(
                phase=ValidationPhase.FILTER_CODE,
                severity=ValidationSeverity.ERROR,
                message=f"Python syntax error in filter '{filter_name}': {e.msg}",
                template_file=self.template_file,
                line_number=error_line,
                column_number=e.offset,
                field_path=field_path,
                suggestion=self._get_syntax_suggestion(str(e.msg)),
            ))
            return errors
        
        # Find function definitions in the code
        function_defs = [
            node for node in ast.walk(tree) 
            if isinstance(node, ast.FunctionDef)
        ]
        
        if not function_defs:
            errors.append(ValidationError(
                phase=ValidationPhase.FILTER_CODE,
                severity=ValidationSeverity.ERROR,
                message=f"Filter '{filter_name}' does not define a function",
                template_file=self.template_file,
                line_number=line_num,
                field_path=field_path,
                suggestion=f"Add a function definition: def {filter_name}(value):",
            ))
            return errors
        
        # Check if the expected function name is defined
        defined_names = [f.name for f in function_defs]
        
        if filter_name not in defined_names:
            # Function name mismatch
            errors.append(ValidationError(
                phase=ValidationPhase.FILTER_CODE,
                severity=ValidationSeverity.ERROR,
                message=f"Filter '{filter_name}' defines function(s) {defined_names} instead of '{filter_name}'",
                template_file=self.template_file,
                line_number=line_num,
                field_path=field_path,
                suggestion=f"Rename the function to '{filter_name}' or change the filter key to match the function name",
            ))
        
        # Check for the expected function
        for func_def in function_defs:
            if func_def.name == filter_name:
                # Note: Some filters are generator functions that don't need parameters
                # (e.g., generate_uuid). We no longer warn about missing parameters
                # as this is a valid pattern for generator-style filters.
                
                # Check for return statement
                has_return = any(
                    isinstance(node, ast.Return) and node.value is not None
                    for node in ast.walk(func_def)
                )
                
                if not has_return:
                    errors.append(ValidationError(
                        phase=ValidationPhase.FILTER_CODE,
                        severity=ValidationSeverity.WARNING,
                        message=f"Filter function '{filter_name}' may not return a value",
                        template_file=self.template_file,
                        line_number=line_num,
                        field_path=field_path,
                        suggestion='Ensure the function returns a value to be used in the template',
                    ))
                
                break
        
        return errors
    
    def _get_syntax_suggestion(self, error_msg: str) -> Optional[str]:
        """Generate a suggestion based on the syntax error message."""
        error_lower = error_msg.lower()
        
        if 'unexpected indent' in error_lower:
            return 'Check indentation - Python uses consistent indentation for blocks'
        
        if 'expected an indented block' in error_lower:
            return 'Add an indented body after the function definition'
        
        if 'invalid syntax' in error_lower:
            return 'Check for missing colons, parentheses, or quotes'
        
        if 'unexpected eof' in error_lower or 'unexpected end of file' in error_lower:
            return 'Check for incomplete statements or missing closing brackets'
        
        if 'name' in error_lower and 'not defined' in error_lower:
            return 'Ensure all variables are defined before use'
        
        return 'Review the Python code for syntax errors'
    
    def extract_function_names(self, filter_code: str) -> List[str]:
        """
        Extract function names defined in the filter code.
        
        Args:
            filter_code: Python code string
            
        Returns:
            List of function names defined in the code
        """
        try:
            tree = ast.parse(filter_code.strip())
            return [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            ]
        except SyntaxError:
            return []
    
    def get_function_signature(self, filter_code: str, func_name: str) -> Optional[str]:
        """
        Get the signature of a function defined in the filter code.
        
        Args:
            filter_code: Python code string
            func_name: Name of the function to get signature for
            
        Returns:
            Function signature string or None if not found
        """
        try:
            tree = ast.parse(filter_code.strip())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == func_name:
                    args = node.args
                    
                    # Build parameter list
                    params = []
                    
                    # Regular arguments
                    for arg in args.args:
                        params.append(arg.arg)
                    
                    # *args
                    if args.vararg:
                        params.append(f'*{args.vararg.arg}')
                    
                    # **kwargs
                    if args.kwarg:
                        params.append(f'**{args.kwarg.arg}')
                    
                    return f"def {func_name}({', '.join(params)})"
            
            return None
        except SyntaxError:
            return None