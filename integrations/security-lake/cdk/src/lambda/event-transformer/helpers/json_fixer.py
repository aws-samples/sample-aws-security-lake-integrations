# © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
Cloud Provider JSON Malformation Fixer

Cloud providers may send JSON with various malformations that break standard JSON parsing:
1. Double braces: {"event_data": {{ ... }}}}} 
2. URL spaces: "https: //docs.microsoft.com"
3. HTML anchor quotes: <a target="_blank" href="url">
4. Escaped single quotes: \'

This module provides functions to fix these issues and parse cloud provider JSON successfully.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Tuple


def fix_json(json_string: str, logger: Optional[logging.Logger] = None) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
    """
    Attempt to parse cloud provider JSON, applying fixes for known malformations
    
    Args:
        json_string: JSON string from cloud provider that may be malformed
        logger: Optional logger for diagnostic output
        
    Returns:
        Tuple of (parsed_dict, exception):
            - (parsed_dict, None) if successful
            - (None, original_exception) if all fixes failed
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Try parsing original first
    try:
        return json.loads(json_string), None
    except json.JSONDecodeError as original_error:
        logger.warning("Initial JSON parse failed, attempting to fix common cloud provider malformations")
        
        # Apply fixes
        fixed_body = _apply_all_fixes(json_string, logger)
        
        # Try parsing fixed version
        try:
            parsed = json.loads(fixed_body)
            logger.info("Successfully parsed JSON after applying cloud provider malformation fixes")
            return parsed, None
        except json.JSONDecodeError as fix_error:
            logger.error(f"JSON parsing failed even after applying fixes")
            logger.error(f"Original error: {original_error}")
            logger.error(f"After fix error: {fix_error}")
            logger.debug(f"Original snippet (first 200 chars): {json_string[:200]}")
            logger.debug(f"Original snippet (last 200 chars): {json_string[-200:]}")
            logger.debug(f"Fixed snippet (first 200 chars): {fixed_body[:200]}")
            logger.debug(f"Fixed snippet (last 200 chars): {fixed_body[-200:]}")
            
            # Log exact error location
            if fix_error.pos < len(fixed_body):
                logger.error(f"Error at char {fix_error.pos}: {repr(fixed_body[max(0, fix_error.pos-100):fix_error.pos+100])}")
            
            return None, original_error


def _apply_all_fixes(text: str, logger: logging.Logger) -> str:
    """
    Apply all known fixes for cloud provider JSON malformations in optimal order
    
    Order matters - fixes that change character positions must go first
    
    Args:
        text: Malformed JSON string
        logger: Logger for diagnostics
        
    Returns:
        Fixed JSON string
    """
    fixed = text
    
    # Fix 1: Control characters (must be first - affects all string content)
    fixed = _fix_control_characters(fixed, logger)
    
    # Fix 2: Double braces (changes positions, so do early)
    fixed = _fix_double_braces(fixed, logger)
    
    # Fix 3: URL spaces
    fixed = _fix_url_spaces(fixed, logger)
    
    # Fix 4: Escaped single quotes
    fixed = _fix_escaped_single_quotes(fixed, logger)
    
    # Fix 5: HTML anchor tag quotes
    fixed = _fix_html_anchor_quotes(fixed, logger)
    
    return fixed


def _fix_double_braces(text: str, logger: logging.Logger) -> str:
    """
    Fix double opening braces and balance closing braces
    
    Cloud providers may send: {"event_data": {{ ... }}}}}
    Should be: {"event_data": { ... }}
    
    Args:
        text: JSON string
        logger: Logger
        
    Returns:
        Fixed JSON string
    """
    # Check if we have double opening braces
    has_double_open = bool(re.search(r'("event_data":\s*){{', text))
    
    if not has_double_open:
        return text
    
    # Fix opening double braces: "event_data": {{ -> "event_data": {
    fixed = re.sub(r'("event_data":\s*){{', r'\1{', text)
    logger.debug("Fixed double opening braces")
    
    # Balance braces by counting total opening and closing braces
    open_count = fixed.count('{')
    close_count = fixed.count('}')
    
    if close_count > open_count:
        # Remove extra closing braces from the end
        extra_braces = close_count - open_count
        # Count consecutive closing braces at end
        trailing_closes = len(fixed) - len(fixed.rstrip('}'))
        
        if extra_braces <= trailing_closes:
            # Remove exactly the number of extra braces from the end
            fixed = fixed[:-extra_braces]
            logger.debug(f"Balanced braces by removing {extra_braces} extra closing braces from end")
        else:
            logger.warning(f"Cannot balance braces: {extra_braces} extra but only {trailing_closes} at end")
    
    return fixed


def _fix_url_spaces(text: str, logger: logging.Logger) -> str:
    """
    Remove spaces in URLs
    
    Cloud providers may send: "https: //docs.microsoft.com"
    Should be: "https://docs.microsoft.com"
    
    Args:
        text: JSON string
        logger: Logger
        
    Returns:
        Fixed JSON string
    """
    fixed = text.replace('https: //', 'https://')
    fixed = fixed.replace('http: //', 'http://')
    return fixed


def _fix_escaped_single_quotes(text: str, logger: logging.Logger) -> str:
    """
    Remove incorrectly escaped single quotes
    
    Cloud providers may send: machine\'s configuration
    Should be: machine's configuration (single quotes don't need escaping in JSON)
    
    Args:
        text: JSON string
        logger: Logger
        
    Returns:
        Fixed JSON string
    """
    fixed = text.replace(r"\'", "'")
    return fixed


def _fix_control_characters(text: str, logger: logging.Logger) -> str:
    """
    Escape unescaped control characters (0x00-0x1F) within JSON string values
    
    Cloud providers may send string values containing literal newlines, tabs, etc:
    "description": "Line 1
    Line 2"
    
    Should be:
    "description": "Line 1\\nLine 2"
    
    Args:
        text: JSON string
        logger: Logger
        
    Returns:
        Fixed JSON string with control characters properly escaped
    """
    # Control character mapping for JSON escaping
    control_char_map = {
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
        '\b': '\\b',
        '\f': '\\f',
    }
    
    # Additional control characters (0x00-0x1F) not covered above
    for i in range(0x20):
        char = chr(i)
        if char not in control_char_map:
            # Escape as unicode for other control characters
            control_char_map[char] = f'\\u{i:04x}'
    
    result = []
    in_string = False
    escape_next = False
    fixed_count = 0
    
    for i, char in enumerate(text):
        # Track if we're inside a JSON string value
        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            escape_next = False
        elif char == '\\' and not escape_next:
            escape_next = True
            result.append(char)
        elif in_string and char in control_char_map and not escape_next:
            # Found an unescaped control character in a string value
            result.append(control_char_map[char])
            fixed_count += 1
            escape_next = False
        else:
            result.append(char)
            escape_next = False
    
    if fixed_count > 0:
        logger.info(f"Escaped {fixed_count} unescaped control characters in JSON strings")
    
    return ''.join(result)


def _fix_html_anchor_quotes(text: str, logger: logging.Logger) -> str:
    """
    Convert double quotes to single quotes within HTML anchor tags
    
    Cloud providers may send: <a target="_blank" href="url">
    Should be: <a target='_blank' href='url'>
    
    The double quotes in HTML attributes conflict with JSON string delimiters
    
    Args:
        text: JSON string
        logger: Logger
        
    Returns:
        Fixed JSON string
    """
    anchor_count = 0
    
    def fix_single_tag(match):
        nonlocal anchor_count
        anchor_count += 1
        tag = match.group(0)
        # Within this isolated tag, convert all attribute="value" to attribute='value'
        fixed_tag = re.sub(r'(\w+)="([^"]*)"', r"\1='\2'", tag)
        logger.debug(f"Fixed anchor tag #{anchor_count}: {repr(tag[:50])} -> {repr(fixed_tag[:50])}")
        return fixed_tag
    
    # Find all <a ...> opening tags and fix quotes within each one
    result = re.sub(r'<a\s+[^>]+>', fix_single_tag, text)
    
    if anchor_count > 0:
        logger.info(f"Fixed {anchor_count} anchor tags total")
    
    return result


# Backward compatibility alias
fix_azure_json = fix_json