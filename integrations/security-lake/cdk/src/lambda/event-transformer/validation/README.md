# Template Validation Tool

Validates YAML templates that transform cloud security events (Azure, GCP) into OCSF format for AWS Security Lake. The validation tool catches broken templates before deployment, running automatically during CDK synth.

## Table of Contents

- [Overview](#overview)
- [Validation Phases](#validation-phases)
- [Error Messages](#error-messages)
- [Usage Instructions](#usage-instructions)
- [CDK Integration](#cdk-integration)
- [Common Errors and Solutions](#common-errors-and-solutions)
- [Built-in Filters](#built-in-filters)
- [Custom Filters](#custom-filters)
- [Exit Codes](#exit-codes)
- [Programmatic Usage](#programmatic-usage)

## Overview

### Purpose

The template validation tool ensures transformation templates are correct before deployment:

- Validates YAML structure and required fields
- Verifies JSONPath extractor syntax
- Checks Jinja2 template syntax, variable references, and filter usage
- Validates custom Python filter code
- Renders templates with mock data to verify JSON output validity

### When It Runs

| Context | Behavior |
|---------|----------|
| CDK synth/deploy | Runs automatically at start, stops deployment on error |
| Standalone CLI | Manual validation for development and debugging |
| CI/CD Pipeline | Integration with pre-commit hooks |

### What It Validates

Templates define how cloud security events transform to OCSF format. Each template contains:

- **name**: Template identifier
- **input_schema**: Source event schema (e.g., `azure_security_alert`)
- **output_schema**: Target schema (e.g., `ocsf_event`)
- **extractors**: JSONPath expressions to extract source data
- **template**: Jinja2 template producing JSON output
- **filters**: Optional custom Python filter functions

## Validation Phases

The validator runs templates through six sequential phases. In strict mode (default), validation stops on the first error per template.

### Phase 1: YAML Structure

Validates the template file structure:

- Parses YAML content
- Checks for required fields: `name`, `input_schema`, `output_schema`, `extractors`, `template`
- Validates field types (strings, dictionaries)
- Builds line number map for accurate error reporting

**Required Fields:**

```yaml
name: security_alert_ocsf
input_schema: azure_security_alert
output_schema: ocsf_event
extractors:
  alert_id: $.event_data.SystemAlertId
  # ... more extractors
template: |
  {
    "class_uid": 2001,
    "finding_info": {
      "uid": "{{ extractors.alert_id }}"
    }
  }
```

### Phase 2: JSONPath Syntax

Validates all JSONPath expressions in the `extractors` section:

- Parses expressions using jsonpath-ng library
- Verifies expressions start with `$`
- Checks for balanced brackets
- Validates syntax against JSONPath grammar

**Valid JSONPath Examples:**

```yaml
extractors:
  alert_id: $.event_data.SystemAlertId
  severity: $.event_data.Severity
  entities: $.event_data.Entities[*]
  nested_value: $.event_data.properties.nestedField
```

### Phase 3: Jinja2 Syntax

Validates the Jinja2 template content:

- Parses template using Jinja2's parser
- Validates variable references against defined extractors
- Checks filter usage against known filters (built-in and custom)
- Verifies block closure (if/endif, for/endfor)

**Validated Elements:**

- Variable references: `{{ extractors.field_name }}`
- Filter chains: `{{ value | filter1 | filter2 }}`
- Control blocks: `{% if condition %}...{% endif %}`
- Loop blocks: `{% for item in list %}...{% endfor %}`

### Phase 4: Filter Code

Validates custom Python filter functions in the `filters` section:

- Parses Python code using AST
- Verifies function name matches filter key
- Checks function has at least one parameter
- Validates presence of return statement

**Filter Requirements:**

```yaml
filters:
  extract_project_id: |
    def extract_project_id(value):
        if not value:
            return ''
        # Function MUST match key name
        # MUST have at least one parameter
        # SHOULD return a value
        return value.split('/')[0]
```

### Phase 5: JSON Output

Validates the template produces valid JSON:

- Renders template with intelligent mock data
- Attempts to parse rendered output as JSON
- Reports parsing errors with context

Mock data generation is based on extractor field names:

- `*_id`, `*_uid`: String IDs
- `*_timestamp`, `*_time`: ISO 8601 timestamps
- `*_severity`: Severity strings
- `*_score`, `*_count`: Numeric values
- `*_entities`, `*_resources`: Arrays

### Phase 6: OCSF Schema (Future)

Optional schema compliance validation against OCSF specification.

- Currently not implemented
- Reserved for future OCSF schema validation

## Error Messages

### Error Format

All validation errors follow a consistent format:

```
[ERROR] template_file.yaml:line_number
  Phase: Phase Name
  Error message describing the issue
  Field: field_path (if applicable)
  Suggestion: helpful suggestion (if applicable)
```

### Severity Levels

| Level | Description | Impact |
|-------|-------------|--------|
| ERROR | Critical issues preventing template use | Validation fails |
| WARNING | Potential issues worth investigating | Validation passes |
| INFO | Informational messages | No impact |

### Example Error Output

```
============================================================
TEMPLATE VALIDATION REPORT
============================================================
Total templates: 15
Valid templates: 14
Invalid templates: 1
Total errors: 2
Total warnings: 0
============================================================

security_alert_ocsf.yaml:
[ERROR] :45
  Phase: Jinja2 Syntax
  Unknown filter: 'undefined_filter'
  Field: template
  Value: undefined_filter
  Suggestion: Did you mean 'default_if_invalid'?

[ERROR] :67
  Phase: Json Output
  Invalid JSON output: Expecting property name enclosed in double quotes
  Field: template
  Suggestion: Check for trailing commas before closing braces } or ]
```

## Usage Instructions

### Command-Line Interface

Run validation from the event-transformer directory:

```bash
cd integrations/security-lake/cdk/src/lambda/event-transformer
```

**Validate all templates in directory:**

```bash
python -m validation.cli --templates-dir templates/
```

**Validate single template:**

```bash
python -m validation.cli --template templates/security_alert_ocsf.yaml
```

**JSON output format:**

```bash
python -m validation.cli --templates-dir templates/ --output-format json
```

**Show all errors (non-strict mode):**

```bash
python -m validation.cli --templates-dir templates/ --no-strict
```

**Treat warnings as errors:**

```bash
python -m validation.cli --templates-dir templates/ --warnings-as-errors
```

**Disable colored output:**

```bash
python -m validation.cli --templates-dir templates/ --no-color
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--templates-dir` | Directory containing template files | `../templates` relative to script |
| `--template` | Path to single template file | None |
| `--output-format` | Output format: `text` or `json` | `text` |
| `--strict` | Stop on first error per template | `true` |
| `--no-strict` | Continue after errors to find all issues | `false` |
| `--warnings-as-errors` | Treat warnings as errors | `false` |
| `--no-color` | Disable ANSI color codes | `false` |

### NPM Scripts

From the CDK directory:

```bash
cd integrations/security-lake/cdk/

# Validate all templates with text output
npm run validate-templates

# Validate all templates with JSON output
npm run validate-templates:json
```

## CDK Integration

### Automatic Validation

Template validation runs automatically during CDK operations:

- Executes at the start of `cdk synth` and `cdk deploy`
- Validates all templates in the templates directory
- Stops deployment if any template has errors (exit code 1)
- Passes deployment if all templates valid (exit code 0)

### Strict Validation Mode

Control validation strictness via environment variable:

```bash
# Treat warnings as errors (recommended for production)
STRICT_VALIDATION=true cdk deploy -c configFile=config.yaml

# Standard validation (warnings allowed)
cdk deploy -c configFile=config.yaml
```

### Pre-commit Hook Integration

Add template validation to pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: validate-templates
        name: Validate Event Transformer Templates
        entry: bash -c 'cd integrations/security-lake/cdk/src/lambda/event-transformer && python -m validation.cli --templates-dir templates/'
        language: system
        pass_filenames: false
        files: 'templates/.*\.yaml$'
```

## Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| Missing required field | Template missing `name`, `extractors`, `template`, etc. | Add the required field to template YAML |
| Invalid JSONPath syntax | Malformed JSONPath expression | Check syntax; ensure expression starts with `$` |
| Undefined extractor reference | `{{ extractors.undefined_field }}` in template | Add the extractor or fix the variable reference |
| Unknown filter | Using filter not in built-in set | Define in `filters:` section or use a built-in filter |
| Unclosed block | Missing `{% endif %}` or `{% endfor %}` | Add the closing tag to match opening block |
| Invalid JSON output | Trailing comma, unescaped characters | Fix JSON syntax in template; use `json_escape` filter |
| Filter function mismatch | Function name doesn't match filter key | Rename function to match the filter key name |
| Missing return statement | Filter function doesn't return value | Add return statement to filter function |
| Empty extractor expression | Extractor has blank value | Provide valid JSONPath expression |
| YAML parsing error | Invalid YAML syntax | Check indentation, quotes, and special characters |

### Debugging Tips

**Enable debug logging:**

```bash
LOGGING_LEVEL=DEBUG python -m validation.cli --templates-dir templates/
```

**Validate with all errors shown:**

```bash
python -m validation.cli --templates-dir templates/ --no-strict
```

**Check specific template:**

```bash
python -m validation.cli --template templates/security_alert_ocsf.yaml --no-strict
```

## Built-in Filters

The template engine provides 44 built-in filters from [`template_transformer.py`](../core/template_transformer.py:139).

### Timestamp Filters

| Filter | Description |
|--------|-------------|
| `normalize_timestamp` | Normalize to CloudTrail format (YYYY-MM-DDTHH:MM:SSZ) |
| `to_unix_timestamp` | Convert to Unix epoch milliseconds |
| `to_unix_timestamp_ms` | Convert to Unix epoch milliseconds |
| `add_one_second` | Add 1 second to ISO8601 timestamp |

### String Filters

| Filter | Description |
|--------|-------------|
| `json_escape` | Escape string for JSON (handles newlines, quotes) |
| `truncate` | Truncate string to specified length |
| `safe_string` | Convert to string, return 'Unknown' for None |
| `slugify` | Convert text to URL-safe slug format |

### Azure Extraction Filters

| Filter | Description |
|--------|-------------|
| `extract_azure_subscription` | Extract subscription ID from resource identifiers |
| `extract_azure_tenant` | Extract tenant ID from resource identifiers |
| `extract_azure_region` | Extract region from Azure resource ID |
| `extract_resource_name` | Extract resource name from resource path |
| `extract_subscription_id` | Extract subscription ID from resource ID |
| `extract_azure_resource_type` | Extract resource type from resource ID |
| `extract_source_ip` | Extract source IP from Azure alert entities |
| `extract_ip` | Extract IP address from address:port format |
| `extract_port` | Extract port number from address:port format |

### Mapping Filters

| Filter | Description |
|--------|-------------|
| `map_azure_severity_to_ocsf` | Map Azure severity to OCSF severity_id |
| `map_alert_status` | Map Azure alert status to OCSF status_id |
| `map_confidence_level` | Map confidence level to OCSF confidence_id |
| `map_mitre_tactic` | Map Azure intent to MITRE tactic ID |
| `map_compliance_status` | Map Azure status to OCSF compliance status |
| `map_compliance_status_id` | Map Azure status to OCSF status_id |

### Severity Filters

| Filter | Description |
|--------|-------------|
| `format_severity` | Standardize severity values |
| `calculate_compliance_severity` | Calculate OCSF severity_id from compliance score |
| `calculate_compliance_severity_name` | Calculate OCSF severity name from compliance score |
| `asff_severity_label` | Convert Azure severity to ASFF label |
| `asff_severity_normalized` | Convert Azure severity to ASFF normalized (0-100) |
| `score_to_severity` | Convert score to ASFF severity label |
| `score_to_severity_normalized` | Convert score to ASFF normalized severity |

### Validation Filters

| Filter | Description |
|--------|-------------|
| `is_valid` | Check if value is valid (not None, empty, or 'None') |
| `default_if_invalid` | Return default if value is invalid |
| `omit_if_invalid` | Return None if value is invalid |

### JSON Filters

| Filter | Description |
|--------|-------------|
| `to_json` | Convert object to JSON string |
| `safe_get` | Safely get dictionary key with default |

### ASFF-Specific Filters

| Filter | Description |
|--------|-------------|
| `to_asff_types` | Convert alert type to ASFF Types array |
| `compliance_status` | Convert Azure state to ASFF compliance status |
| `asff_record_state` | Convert state to ASFF RecordState |
| `score_to_compliance_status` | Convert score to ASFF compliance status |
| `score_to_reason_code` | Convert score to Security Hub ReasonCode |
| `compliance_reason_code` | Convert Azure state to Security Hub ReasonCode |

### Utility Filters

| Filter | Description |
|--------|-------------|
| `generate_uuid` | Generate random UUID string |

### Jinja2 Built-in Filters

Standard Jinja2 filters are also available:

`abs`, `attr`, `batch`, `capitalize`, `center`, `count`, `default`, `d`, `dictsort`, `e`, `escape`, `filesizeformat`, `first`, `float`, `forceescape`, `format`, `groupby`, `indent`, `int`, `join`, `last`, `length`, `list`, `lower`, `map`, `max`, `min`, `pprint`, `random`, `reject`, `rejectattr`, `replace`, `reverse`, `round`, `safe`, `select`, `selectattr`, `slice`, `sort`, `string`, `striptags`, `sum`, `title`, `trim`, `truncate`, `unique`, `upper`, `urlencode`, `urlize`, `wordcount`, `wordwrap`, `xmlattr`, `tojson`

## Custom Filters

Define custom filters in the template `filters` section when built-in filters don't meet requirements.

### Filter Definition Syntax

```yaml
filters:
  filter_name: |
    def filter_name(value, optional_param=None):
        """
        Filter description.
        
        Args:
            value: Input value from template
            optional_param: Optional parameter
            
        Returns:
            Transformed value
        """
        if not value:
            return ''
        
        # Custom transformation logic
        result = value.upper()
        
        return result
```

### Filter Requirements

1. **Function name must match key**: The `def` function name must exactly match the filter key
2. **At least one parameter**: Filter functions receive the piped value as first argument
3. **Return value**: Functions should return a value for use in templates
4. **Python syntax**: Code must be valid Python

### Example: Custom Extraction Filter

```yaml
filters:
  extract_project_id: |
    def extract_project_id(resource_name):
        """Extract GCP project ID from resource name."""
        if not resource_name:
            return ''
        
        # Resource format: projects/PROJECT_ID/...
        parts = resource_name.split('/')
        if len(parts) >= 2 and parts[0] == 'projects':
            return parts[1]
        
        return ''

template: |
  {
    "cloud": {
      "project_uid": "{{ extractors.resource_name | extract_project_id }}"
    }
  }
```

### Example: Mapping Filter

```yaml
filters:
  map_status_to_ocsf: |
    def map_status_to_ocsf(status):
        """Map source status to OCSF status_id."""
        mapping = {
            'active': 1,
            'resolved': 2,
            'dismissed': 3
        }
        if not status:
            return 99  # Unknown
        return mapping.get(status.lower(), 99)
```

### Filter Interdependencies

Filters can call other filters defined in the same template:

```yaml
filters:
  get_severity_name: |
    def get_severity_name(severity_id):
        mapping = {1: 'Low', 2: 'Medium', 3: 'High'}
        return mapping.get(severity_id, 'Unknown')
  
  format_severity_display: |
    def format_severity_display(severity_id):
        name = get_severity_name(severity_id)  # Calls other filter
        return f"Severity: {name} ({severity_id})"
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All templates valid |
| 1 | One or more templates have errors |

Use exit codes in CI/CD pipelines:

```bash
python -m validation.cli --templates-dir templates/
if [ $? -ne 0 ]; then
    echo "Template validation failed"
    exit 1
fi
```

## Programmatic Usage

Use the validator in Python code for custom validation workflows.

### Basic Usage

```python
from validation import TemplateValidator

# Initialize validator
validator = TemplateValidator(
    strict=True,  # Stop on first error per template
    warnings_as_errors=False
)

# Validate single template
result = validator.validate_template('templates/security_alert_ocsf.yaml')

if result.valid:
    print(f"Template valid: {result.template_file}")
else:
    for error in result.errors:
        print(error.format_for_console())
```

### Validate Directory

```python
from validation import TemplateValidator

validator = TemplateValidator()
aggregated = validator.validate_directory(
    templates_dir='templates/',
    pattern='*.yaml'
)

print(f"Total: {aggregated.total_templates}")
print(f"Valid: {aggregated.valid_templates}")
print(f"Invalid: {aggregated.invalid_templates}")

if not aggregated.all_valid:
    for template_path, result in aggregated.results.items():
        if not result.valid:
            print(f"\n{template_path}:")
            for error in result.errors:
                print(error.format_for_console())
```

### Custom Error Handling

```python
from validation import (
    TemplateValidator,
    ValidationPhase,
    ValidationSeverity
)

validator = TemplateValidator(strict=False)
result = validator.validate_template('templates/my_template.yaml')

# Filter errors by phase
jsonpath_errors = [
    e for e in result.errors 
    if e.phase == ValidationPhase.JSONPATH_SYNTAX
]

# Filter by severity
critical_errors = [
    e for e in result.all_issues()
    if e.severity == ValidationSeverity.ERROR
]

# Get JSON representation
result_dict = result.to_dict()
```

### JSON Output

```python
from validation import TemplateValidator
import json

validator = TemplateValidator()
aggregated = validator.validate_directory('templates/')

# Get structured JSON output
output = aggregated.to_dict()
print(json.dumps(output, indent=2))
```

**JSON Output Structure:**

```json
{
  "summary": {
    "total_templates": 15,
    "valid_templates": 14,
    "invalid_templates": 1,
    "total_errors": 2,
    "total_warnings": 0,
    "all_valid": false
  },
  "results": {
    "templates/security_alert_ocsf.yaml": {
      "template_file": "templates/security_alert_ocsf.yaml",
      "valid": false,
      "error_count": 2,
      "warning_count": 0,
      "info_count": 0,
      "errors": [
        {
          "phase": "Jinja2 Syntax",
          "severity": "ERROR",
          "message": "Unknown filter: 'undefined_filter'",
          "template_file": "templates/security_alert_ocsf.yaml",
          "line_number": 45,
          "field_path": "template",
          "raw_value": "undefined_filter",
          "suggestion": "Did you mean 'default_if_invalid'?"
        }
      ],
      "warnings": [],
      "info": []
    }
  }
}
```

## Related Documentation

- [Event Transformer README](../README.md) - Lambda function overview
- [Template Transformer](../core/template_transformer.py) - Template engine implementation
- [OCSF Templates](../templates/) - Transformation template examples
- [DEBUGGING_FAILED_EVENTS.md](../DEBUGGING_FAILED_EVENTS.md) - Troubleshooting guide