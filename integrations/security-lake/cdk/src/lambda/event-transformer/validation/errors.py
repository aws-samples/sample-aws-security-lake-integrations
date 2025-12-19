# (c) 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
Error classes and result types for template validation.

This module defines the error hierarchy, severity levels, validation phases,
and result aggregation types used throughout the template validation system.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Optional, List, Dict, Any


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = auto()
    WARNING = auto()
    INFO = auto()
    
    def __str__(self) -> str:
        return self.name


class ValidationPhase(Enum):
    """Phases of the validation pipeline."""
    YAML_STRUCTURE = auto()
    JSONPATH_SYNTAX = auto()
    JINJA2_SYNTAX = auto()
    FILTER_CODE = auto()
    JSON_OUTPUT = auto()
    OCSF_SCHEMA = auto()
    
    def __str__(self) -> str:
        return self.name.replace('_', ' ').title()


@dataclass
class ValidationError:
    """
    Represents a single validation error or warning.
    
    Attributes:
        phase: The validation phase where this error was detected
        severity: The severity level of the error
        message: Human-readable error description
        template_file: Path to the template file containing the error
        line_number: Optional line number in the source file
        column_number: Optional column number in the source file
        field_path: Optional path to the field (e.g., "extractors.alert_id")
        suggestion: Optional suggestion for fixing the error
        raw_value: Optional raw value that caused the error
    """
    phase: ValidationPhase
    severity: ValidationSeverity
    message: str
    template_file: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    field_path: Optional[str] = None
    suggestion: Optional[str] = None
    raw_value: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary representation."""
        result = {
            'phase': str(self.phase),
            'severity': str(self.severity),
            'message': self.message,
            'template_file': self.template_file,
        }
        
        if self.line_number is not None:
            result['line_number'] = self.line_number
        if self.column_number is not None:
            result['column_number'] = self.column_number
        if self.field_path is not None:
            result['field_path'] = self.field_path
        if self.suggestion is not None:
            result['suggestion'] = self.suggestion
        if self.raw_value is not None:
            result['raw_value'] = self.raw_value
            
        return result
    
    def format_for_console(self, use_color: bool = True) -> str:
        """
        Format the error for console output.
        
        Args:
            use_color: Whether to use ANSI color codes
            
        Returns:
            Formatted string for console display
        """
        # Color codes
        if use_color:
            colors = {
                ValidationSeverity.ERROR: '\033[91m',    # Red
                ValidationSeverity.WARNING: '\033[93m',  # Yellow
                ValidationSeverity.INFO: '\033[94m',     # Blue
            }
            reset = '\033[0m'
            bold = '\033[1m'
        else:
            colors = {s: '' for s in ValidationSeverity}
            reset = ''
            bold = ''
        
        color = colors.get(self.severity, '')
        
        # Build location string
        location = ''
        if self.line_number is not None:
            location = f':{self.line_number}'
            if self.column_number is not None:
                location += f':{self.column_number}'
        
        lines = []
        lines.append(f'{color}[{self.severity.name}]{reset} {location}')
        lines.append(f'  {bold}Phase:{reset} {self.phase}')
        lines.append(f'  {self.message}')
        
        if self.field_path:
            lines.append(f'  {bold}Field:{reset} {self.field_path}')
        
        if self.raw_value:
            # Truncate long raw values
            value_display = self.raw_value
            if len(value_display) > 60:
                value_display = value_display[:57] + '...'
            lines.append(f'  {bold}Value:{reset} {value_display}')
        
        if self.suggestion:
            lines.append(f'  {bold}Suggestion:{reset} {self.suggestion}')
        
        return '\n'.join(lines)


@dataclass
class ValidationResult:
    """
    Result of validating a single template.
    
    Attributes:
        template_file: Path to the validated template file
        valid: Whether the template passed validation (no errors)
        errors: List of validation errors found
        warnings: List of validation warnings found
        info: List of informational messages
    """
    template_file: str
    valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    info: List[ValidationError] = field(default_factory=list)
    
    def add_error(self, error: ValidationError) -> None:
        """Add a validation error to the result."""
        if error.severity == ValidationSeverity.ERROR:
            self.errors.append(error)
            self.valid = False
        elif error.severity == ValidationSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.info.append(error)
    
    def merge(self, other: 'ValidationResult') -> None:
        """Merge another validation result into this one."""
        if other.template_file != self.template_file:
            raise ValueError("Cannot merge results from different templates")
        
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)
        
        if other.errors:
            self.valid = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary representation."""
        return {
            'template_file': self.template_file,
            'valid': self.valid,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'info_count': len(self.info),
            'errors': [e.to_dict() for e in self.errors],
            'warnings': [w.to_dict() for w in self.warnings],
            'info': [i.to_dict() for i in self.info],
        }
    
    def all_issues(self) -> List[ValidationError]:
        """Get all issues (errors, warnings, and info) combined."""
        return self.errors + self.warnings + self.info


@dataclass
class AggregatedValidationResult:
    """
    Aggregated result of validating multiple templates.
    
    Attributes:
        results: Dictionary mapping template file paths to their validation results
        total_templates: Total number of templates validated
        valid_templates: Number of templates that passed validation
        invalid_templates: Number of templates that failed validation
        total_errors: Total number of errors across all templates
        total_warnings: Total number of warnings across all templates
    """
    results: Dict[str, ValidationResult] = field(default_factory=dict)
    
    @property
    def total_templates(self) -> int:
        """Get the total number of templates validated."""
        return len(self.results)
    
    @property
    def valid_templates(self) -> int:
        """Get the number of valid templates."""
        return sum(1 for r in self.results.values() if r.valid)
    
    @property
    def invalid_templates(self) -> int:
        """Get the number of invalid templates."""
        return sum(1 for r in self.results.values() if not r.valid)
    
    @property
    def total_errors(self) -> int:
        """Get the total number of errors across all templates."""
        return sum(len(r.errors) for r in self.results.values())
    
    @property
    def total_warnings(self) -> int:
        """Get the total number of warnings across all templates."""
        return sum(len(r.warnings) for r in self.results.values())
    
    @property
    def all_valid(self) -> bool:
        """Check if all templates passed validation."""
        return all(r.valid for r in self.results.values())
    
    def add_result(self, result: ValidationResult) -> None:
        """Add a template validation result."""
        self.results[result.template_file] = result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the aggregated result to a dictionary representation."""
        return {
            'summary': {
                'total_templates': self.total_templates,
                'valid_templates': self.valid_templates,
                'invalid_templates': self.invalid_templates,
                'total_errors': self.total_errors,
                'total_warnings': self.total_warnings,
                'all_valid': self.all_valid,
            },
            'results': {k: v.to_dict() for k, v in self.results.items()},
        }
    
    def format_summary(self, use_color: bool = True) -> str:
        """
        Format a summary for console output.
        
        Args:
            use_color: Whether to use ANSI color codes
            
        Returns:
            Formatted summary string
        """
        if use_color:
            green = '\033[92m'
            red = '\033[91m'
            yellow = '\033[93m'
            reset = '\033[0m'
            bold = '\033[1m'
        else:
            green = red = yellow = reset = bold = ''
        
        separator = '=' * 60
        lines = [
            separator,
            f'{bold}TEMPLATE VALIDATION REPORT{reset}',
            separator,
            f'Total templates: {self.total_templates}',
            f'Valid templates: {green}{self.valid_templates}{reset}',
            f'Invalid templates: {red}{self.invalid_templates}{reset}',
            f'Total errors: {red if self.total_errors > 0 else ""}{self.total_errors}{reset}',
            f'Total warnings: {yellow if self.total_warnings > 0 else ""}{self.total_warnings}{reset}',
            separator,
        ]
        
        return '\n'.join(lines)