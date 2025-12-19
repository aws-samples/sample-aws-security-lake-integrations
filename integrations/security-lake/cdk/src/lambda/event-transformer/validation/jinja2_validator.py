# (c) 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
Jinja2 template syntax validator for transformation templates.

This module validates Jinja2 template syntax, checks variable references
against defined extractors, and validates filter usage.
"""

import re
from typing import Dict, Set, List, Optional, Tuple

from .errors import (
    ValidationError,
    ValidationResult,
    ValidationPhase,
    ValidationSeverity,
)


# Built-in filters from template_transformer.py
BUILTIN_FILTERS = {
    'normalize_timestamp', 'format_severity', 'generate_uuid', 'to_json',
    'safe_get', 'json_escape', 'to_unix_timestamp', 'map_azure_severity_to_ocsf',
    'map_alert_status', 'map_confidence_level', 'extract_subscription_id',
    'extract_azure_region', 'extract_resource_name', 'extract_azure_resource_type',
    'map_mitre_tactic', 'truncate', 'extract_azure_subscription',
    'extract_source_ip', 'to_unix_timestamp_ms', 'extract_azure_tenant',
    'calculate_compliance_severity', 'calculate_compliance_severity_name',
    'safe_string', 'asff_severity_label', 'asff_severity_normalized',
    'to_asff_types', 'compliance_status', 'asff_record_state',
    'score_to_severity', 'score_to_severity_normalized',
    'score_to_compliance_status', 'score_to_reason_code',
    'compliance_reason_code', 'is_valid', 'default_if_invalid',
    'omit_if_invalid', 'add_one_second', 'extract_ip', 'extract_port',
    'map_compliance_status', 'map_compliance_status_id', 'slugify'
}

# Built-in Jinja2 filters
JINJA2_BUILTIN_FILTERS = {
    'abs', 'attr', 'batch', 'capitalize', 'center', 'count',
    'default', 'd', 'dictsort', 'e', 'escape', 'filesizeformat',
    'first', 'float', 'forceescape', 'format', 'groupby', 'indent',
    'int', 'join', 'last', 'length', 'list', 'lower', 'map', 'max',
    'min', 'pprint', 'random', 'reject', 'rejectattr', 'replace',
    'reverse', 'round', 'safe', 'select', 'selectattr', 'slice',
    'sort', 'string', 'striptags', 'sum', 'title', 'trim', 'truncate',
    'unique', 'upper', 'urlencode', 'urlize', 'wordcount', 'wordwrap',
    'xmlattr', 'tojson'
}

# Combined set of all recognized filters
ALL_KNOWN_FILTERS = BUILTIN_FILTERS | JINJA2_BUILTIN_FILTERS


class Jinja2Validator:
    """
    Validates Jinja2 template syntax in transformation templates.
    
    This validator:
    - Parses the Jinja2 template using Jinja2's parser
    - Validates variable references point to defined extractors
    - Validates filter references exist (built-in or custom-defined)
    - Checks for unclosed blocks (if/endif, for/endfor)
    """
    
    # Jinja2 block pairs
    BLOCK_PAIRS = {
        'if': 'endif',
        'for': 'endfor',
        'macro': 'endmacro',
        'call': 'endcall',
        'filter': 'endfilter',
        'block': 'endblock',
        'raw': 'endraw',
        'set': None,  # set doesn't always need closing
    }
    
    def __init__(
        self, 
        template_file: str,
        template_start_line: Optional[int] = None,
        line_map: Optional[Dict[str, int]] = None
    ):
        """
        Initialize the Jinja2 validator.
        
        Args:
            template_file: Path to the template file being validated
            template_start_line: Line number where the template field begins
            line_map: Optional mapping of field paths to line numbers
        """
        self.template_file = template_file
        self.template_start_line = template_start_line or 0
        self.line_map = line_map or {}
        self._jinja2_available = False
        self._import_jinja2()
    
    def _import_jinja2(self) -> None:
        """Attempt to import the Jinja2 library."""
        try:
            from jinja2 import Environment, TemplateSyntaxError
            from jinja2.sandbox import SandboxedEnvironment
            self._Environment = Environment
            self._SandboxedEnvironment = SandboxedEnvironment
            self._TemplateSyntaxError = TemplateSyntaxError
            self._jinja2_available = True
        except ImportError:
            self._Environment = None
            self._SandboxedEnvironment = None
            self._TemplateSyntaxError = Exception
            self._jinja2_available = False
    
    def validate(
        self,
        template_content: str,
        extractors: Dict[str, str],
        custom_filters: Optional[Dict[str, str]] = None
    ) -> ValidationResult:
        """
        Validate a Jinja2 template.
        
        Args:
            template_content: The Jinja2 template string
            extractors: Dictionary of extractor names (for variable validation)
            custom_filters: Optional dictionary of custom filter names to code
            
        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(template_file=self.template_file)
        
        if not self._jinja2_available:
            result.add_error(ValidationError(
                phase=ValidationPhase.JINJA2_SYNTAX,
                severity=ValidationSeverity.WARNING,
                message='Jinja2 library not available - skipping template validation',
                template_file=self.template_file,
                suggestion='Install Jinja2: pip install Jinja2',
            ))
            return result
        
        if not template_content:
            result.add_error(ValidationError(
                phase=ValidationPhase.JINJA2_SYNTAX,
                severity=ValidationSeverity.ERROR,
                message='Template content is empty',
                template_file=self.template_file,
                field_path='template',
                line_number=self.template_start_line,
            ))
            return result
        
        # Build set of known filter names
        known_filters = ALL_KNOWN_FILTERS.copy()
        if custom_filters:
            known_filters.update(custom_filters.keys())
        
        # Validate syntax using Jinja2 parser
        syntax_errors = self._validate_syntax(template_content)
        for error in syntax_errors:
            result.add_error(error)
        
        # Check for unclosed blocks
        block_errors = self._check_unclosed_blocks(template_content)
        for error in block_errors:
            result.add_error(error)
        
        # Extract and validate variable references
        variable_errors = self._validate_variables(template_content, extractors)
        for error in variable_errors:
            result.add_error(error)
        
        # Extract and validate filter references
        filter_errors = self._validate_filters(template_content, known_filters)
        for error in filter_errors:
            result.add_error(error)
        
        return result
    
    def _validate_syntax(self, template_content: str) -> List[ValidationError]:
        """Validate template syntax using Jinja2 parser."""
        errors = []
        
        try:
            env = self._SandboxedEnvironment()
            # Add placeholder filters to prevent unknown filter errors during parsing
            for filter_name in ALL_KNOWN_FILTERS:
                env.filters[filter_name] = lambda x, *args, **kwargs: x
            
            env.parse(template_content)
        except self._TemplateSyntaxError as e:
            line_num = e.lineno
            if self.template_start_line and line_num:
                line_num = self.template_start_line + line_num - 1
            
            errors.append(ValidationError(
                phase=ValidationPhase.JINJA2_SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=f'Jinja2 syntax error: {e.message}',
                template_file=self.template_file,
                line_number=line_num,
                field_path='template',
                suggestion=self._get_syntax_suggestion(str(e.message)),
            ))
        except Exception as e:
            errors.append(ValidationError(
                phase=ValidationPhase.JINJA2_SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=f'Failed to parse Jinja2 template: {str(e)}',
                template_file=self.template_file,
                field_path='template',
            ))
        
        return errors
    
    def _check_unclosed_blocks(self, template_content: str) -> List[ValidationError]:
        """Check for unclosed Jinja2 blocks."""
        errors = []
        
        # Track block openings and closings
        block_stack: List[Tuple[str, int]] = []  # (block_type, line_number)
        lines = template_content.split('\n')
        
        # Regex patterns for block detection
        block_start_pattern = re.compile(r'\{%[-+]?\s*(if|for|macro|call|filter|block|raw)\s')
        block_end_pattern = re.compile(r'\{%[-+]?\s*(endif|endfor|endmacro|endcall|endfilter|endblock|endraw)\s*[-+]?%\}')
        elif_pattern = re.compile(r'\{%[-+]?\s*el(?:se|if)\s')
        
        for line_idx, line in enumerate(lines, 1):
            # Check for block starts
            for match in block_start_pattern.finditer(line):
                block_type = match.group(1)
                block_stack.append((block_type, line_idx))
            
            # Check for block ends
            for match in block_end_pattern.finditer(line):
                end_type = match.group(1)
                expected_start = end_type[3:]  # Remove 'end' prefix
                
                if not block_stack:
                    actual_line = line_idx
                    if self.template_start_line:
                        actual_line += self.template_start_line - 1
                    
                    errors.append(ValidationError(
                        phase=ValidationPhase.JINJA2_SYNTAX,
                        severity=ValidationSeverity.ERROR,
                        message=f"Unexpected '{end_type}' without matching '{expected_start}'",
                        template_file=self.template_file,
                        line_number=actual_line,
                        field_path='template',
                    ))
                elif block_stack[-1][0] != expected_start:
                    start_type, start_line = block_stack[-1]
                    actual_line = line_idx
                    if self.template_start_line:
                        actual_line += self.template_start_line - 1
                    
                    errors.append(ValidationError(
                        phase=ValidationPhase.JINJA2_SYNTAX,
                        severity=ValidationSeverity.ERROR,
                        message=f"Mismatched block: found '{end_type}' but expected 'end{start_type}'",
                        template_file=self.template_file,
                        line_number=actual_line,
                        field_path='template',
                        suggestion=f"Check the '{start_type}' block that started around line {start_line}",
                    ))
                else:
                    block_stack.pop()
        
        # Report unclosed blocks
        for block_type, start_line in block_stack:
            actual_line = start_line
            if self.template_start_line:
                actual_line += self.template_start_line - 1
            
            errors.append(ValidationError(
                phase=ValidationPhase.JINJA2_SYNTAX,
                severity=ValidationSeverity.ERROR,
                message=f"Unclosed '{block_type}' block - missing 'end{block_type}'",
                template_file=self.template_file,
                line_number=actual_line,
                field_path='template',
                suggestion=f"Add '{{% end{block_type} %}}' to close the block",
            ))
        
        return errors
    
    def _validate_variables(
        self, 
        template_content: str, 
        extractors: Dict[str, str]
    ) -> List[ValidationError]:
        """Validate variable references in the template."""
        errors = []
        
        # Pattern to match extractors.field_name references
        extractor_pattern = re.compile(r'extractors\.([a-zA-Z_][a-zA-Z0-9_]*)')
        
        # Find all extractor references
        for match in extractor_pattern.finditer(template_content):
            field_name = match.group(1)
            
            if field_name not in extractors:
                # Find the line number
                pos = match.start()
                line_num = template_content[:pos].count('\n') + 1
                if self.template_start_line:
                    line_num += self.template_start_line - 1
                
                # Suggest similar names
                suggestion = self._suggest_similar_name(field_name, extractors.keys())
                
                errors.append(ValidationError(
                    phase=ValidationPhase.JINJA2_SYNTAX,
                    severity=ValidationSeverity.WARNING,
                    message=f"Reference to undefined extractor: 'extractors.{field_name}'",
                    template_file=self.template_file,
                    line_number=line_num,
                    field_path='template',
                    raw_value=f'extractors.{field_name}',
                    suggestion=suggestion,
                ))
        
        return errors
    
    def _validate_filters(
        self, 
        template_content: str, 
        known_filters: Set[str]
    ) -> List[ValidationError]:
        """Validate filter references in the template."""
        errors = []
        
        # Pattern to match filter usage: value | filter_name
        # Handles chained filters: value | filter1 | filter2
        filter_pattern = re.compile(r'\|\s*([a-zA-Z_][a-zA-Z0-9_]*)')
        
        # Find all filter references
        for match in filter_pattern.finditer(template_content):
            filter_name = match.group(1)
            
            if filter_name not in known_filters:
                # Find the line number
                pos = match.start()
                line_num = template_content[:pos].count('\n') + 1
                if self.template_start_line:
                    line_num += self.template_start_line - 1
                
                # Suggest similar names
                suggestion = self._suggest_similar_name(filter_name, known_filters)
                
                errors.append(ValidationError(
                    phase=ValidationPhase.JINJA2_SYNTAX,
                    severity=ValidationSeverity.ERROR,
                    message=f"Unknown filter: '{filter_name}'",
                    template_file=self.template_file,
                    line_number=line_num,
                    field_path='template',
                    raw_value=filter_name,
                    suggestion=suggestion,
                ))
        
        return errors
    
    def _get_syntax_suggestion(self, error_message: str) -> Optional[str]:
        """Generate a suggestion based on the syntax error message."""
        error_lower = error_message.lower()
        
        if 'unexpected' in error_lower and 'end of' in error_lower:
            return 'Check for unclosed braces {{ }} or {% %}'
        
        if 'expected token' in error_lower:
            return 'Check for missing closing delimiters or syntax errors'
        
        if 'undefined' in error_lower:
            return 'Ensure all variables are defined in extractors or template context'
        
        if 'unexpected char' in error_lower:
            return 'Check for special characters that need escaping'
        
        return None
    
    def _suggest_similar_name(
        self, 
        name: str, 
        valid_names: Set[str]
    ) -> Optional[str]:
        """Suggest similar names using simple string matching."""
        if not valid_names:
            return None
        
        # Calculate similarity scores
        scores = []
        name_lower = name.lower()
        
        for valid_name in valid_names:
            valid_lower = valid_name.lower()
            
            # Exact prefix match gets high score
            if valid_lower.startswith(name_lower) or name_lower.startswith(valid_lower):
                scores.append((valid_name, 0.8))
            # Contains match
            elif name_lower in valid_lower or valid_lower in name_lower:
                scores.append((valid_name, 0.6))
            # Character overlap
            else:
                common = set(name_lower) & set(valid_lower)
                score = len(common) / max(len(name_lower), len(valid_lower))
                if score > 0.4:
                    scores.append((valid_name, score))
        
        if not scores:
            return None
        
        # Sort by score and return best match
        scores.sort(key=lambda x: x[1], reverse=True)
        best_match, best_score = scores[0]
        
        if best_score > 0.4:
            return f"Did you mean '{best_match}'?"
        
        return None
    
    def get_referenced_extractors(self, template_content: str) -> Set[str]:
        """
        Get the set of extractor names referenced in the template.
        
        Args:
            template_content: The Jinja2 template string
            
        Returns:
            Set of extractor field names referenced in the template
        """
        extractor_pattern = re.compile(r'extractors\.([a-zA-Z_][a-zA-Z0-9_]*)')
        return {match.group(1) for match in extractor_pattern.finditer(template_content)}
    
    def get_used_filters(self, template_content: str) -> Set[str]:
        """
        Get the set of filter names used in the template.
        
        Args:
            template_content: The Jinja2 template string
            
        Returns:
            Set of filter names used in the template
        """
        filter_pattern = re.compile(r'\|\s*([a-zA-Z_][a-zA-Z0-9_]*)')
        return {match.group(1) for match in filter_pattern.finditer(template_content)}