# OpenSearch Serverless Assets

## Overview

This directory contains OpenSearch Saved Objects in NDJSON (Newline Delimited JSON) format that are automatically imported into OpenSearch Serverless during CDK deployment via the Saved Objects Importer Lambda function.

## Purpose

These assets provide pre-configured OpenSearch objects that enable immediate visualization and analysis of security data without manual setup. During deployment:

1. Files are uploaded to a temporary S3 bucket
2. A Lambda function downloads each file from S3
3. The Lambda imports saved objects via the OpenSearch Dashboards API
4. CloudFormation tracks import success/failure

## Current Assets

### index-patterns.ndjson

Defines OpenSearch index patterns that map to the data ingested from CloudWatch Logs and Security Lake sources.

**Contents:**
- Index pattern definitions for OCSF security data
- Field mappings and data type configurations
- Default time field settings (`time` for OCSF data)
- Index pattern metadata

**Usage:**
This file is essential for OpenSearch to understand the structure of ingested data and enables:
- Field-based searching and filtering
- Time-series data visualization
- Dashboard creation and saved searches
- Query optimization through field type awareness

## NDJSON File Format

NDJSON (Newline Delimited JSON) is the standard format for OpenSearch saved object bulk operations. Each line must be a complete, valid JSON object.

### File Structure

```json
{"id":"pattern-id-1","type":"index-pattern","attributes":{"title":"security-*","timeFieldName":"time"}}
{"id":"viz-id-1","type":"visualization","attributes":{"title":"Event Count","visState":"{...}"}}
{"id":"dashboard-id-1","type":"dashboard","attributes":{"title":"Security Dashboard","panelsJSON":"[...]"}}
```

### Required Fields

Each saved object must include:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier for the object |
| `type` | string | Object type (see Supported Types below) |
| `attributes` | object | Type-specific configuration and settings |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Object version for conflict detection |
| `references` | array | Dependencies on other saved objects |
| `migrationVersion` | object | Schema version tracking |

### Supported Object Types

OpenSearch Serverless supports these saved object types:

| Type | Description | Common Use Case |
|------|-------------|-----------------|
| `index-pattern` | Defines index structure | Data discovery and field mapping |
| `visualization` | Single chart or graph | Individual data visualizations |
| `dashboard` | Collection of visualizations | Combined analytics view |
| `search` | Saved search query | Reusable search filters |
| `query` | Saved query string | Quick filters |
| `lens` | Lens visualization | Drag-and-drop visualizations |
| `map` | Geographic visualization | Location-based data |

## Adding New Assets

### Step 1: Export from OpenSearch Dashboards

**Via UI:**
1. Navigate to **Stack Management** > **Saved Objects**
2. Select objects to export (check boxes)
3. Click **Export** button
4. Choose **Include related objects** if needed
5. Download the NDJSON file

**Via API:**
```bash
# Export all objects
curl -X POST \
  "https://your-endpoint/_dashboards/api/saved_objects/_export" \
  -H "Content-Type: application/json" \
  -H "osd-xsrf: true" \
  --aws-sigv4 "aws:amz:us-east-1:aoss" \
  -d '{"type": ["index-pattern", "visualization", "dashboard"]}' \
  -o my-objects.ndjson

# Export specific objects by ID
curl -X POST \
  "https://your-endpoint/_dashboards/api/saved_objects/_export" \
  -H "Content-Type: application/json" \
  -H "osd-xsrf: true" \
  --aws-sigv4 "aws:amz:us-east-1:aoss" \
  -d '{"objects": [{"type": "dashboard", "id": "my-dashboard-id"}], "includeReferencesDeep": true}' \
  -o dashboard-with-deps.ndjson
```

### Step 2: Save to Assets Directory

Save the exported file to this `assets/` directory with a descriptive filename:

```
assets/
  index-patterns.ndjson
  security-dashboard.ndjson
  threat-hunting.ndjson
  network-monitoring.ndjson
```

### Step 3: Configure Import

Add the file to your `config.yaml`:

```yaml
savedObjects:
  enabled: true
  imports:
    # Existing imports
    - name: "IndexPatterns"
      file: "index-patterns.ndjson"
      description: "Base index patterns"
      overwrite: true
    
    # New import
    - name: "SecurityDashboard"
      file: "security-dashboard.ndjson"
      description: "Main security dashboard"
      overwrite: true
```

### Step 4: Validate and Deploy

```bash
# Validate NDJSON format (each line must be valid JSON)
cat assets/security-dashboard.ndjson | jq empty

# Build and deploy
npm run build
cdk deploy -c configFile=config.yaml
```

## File Naming Convention

Use descriptive, kebab-case filenames:

| Pattern | Description | Example |
|---------|-------------|---------|
| `index-patterns.ndjson` | Index pattern definitions | Base requirement |
| `{purpose}-dashboard.ndjson` | Dashboard with related objects | `security-dashboard.ndjson` |
| `{category}-visualizations.ndjson` | Visualization library | `network-visualizations.ndjson` |
| `{feature}-{type}.ndjson` | Specific feature objects | `threat-hunting-searches.ndjson` |

## Import Order Considerations

The Saved Objects Importer processes files in the order specified in `config.yaml`. Dependencies must be imported before dependents:

**Correct Order:**
```yaml
imports:
  # 1. Index patterns (no dependencies)
  - name: "IndexPatterns"
    file: "index-patterns.ndjson"
  
  # 2. Saved searches (depend on index patterns)
  - name: "SavedSearches"
    file: "saved-searches.ndjson"
  
  # 3. Visualizations (depend on index patterns, may use searches)
  - name: "Visualizations"
    file: "visualizations.ndjson"
  
  # 4. Dashboards (depend on all of the above)
  - name: "Dashboards"
    file: "dashboards.ndjson"
```

**Incorrect Order (will cause errors):**
```yaml
imports:
  # Dashboard imported before its visualizations - will fail
  - name: "Dashboards"
    file: "dashboards.ndjson"
  - name: "Visualizations"
    file: "visualizations.ndjson"
```

## Validation

Before deploying new assets, validate the files:

### JSON Syntax Validation

```bash
# Validate each line is valid JSON
cat assets/your-file.ndjson | while read line; do
  echo "$line" | jq empty || echo "Invalid JSON: $line"
done

# Quick validation with jq
cat assets/your-file.ndjson | jq -s '.' > /dev/null && echo "Valid NDJSON"
```

### Object Structure Validation

```bash
# Check required fields exist
cat assets/your-file.ndjson | jq -r 'select(.id == null or .type == null or .attributes == null) | "Missing required field"'
```

### Dependency Check

Ensure referenced objects exist:

```bash
# List all object IDs and types
cat assets/*.ndjson | jq -r '"\(.type):\(.id)"'

# Check references in visualizations/dashboards
cat assets/dashboards.ndjson | jq -r '.references[]? | "\(.type):\(.id)"' | sort -u
```

### Manual Test Import

Test import to a development OpenSearch instance before deployment:

```bash
curl -X POST \
  "https://dev-endpoint/_dashboards/api/saved_objects/_import?overwrite=true" \
  -H "osd-xsrf: true" \
  --aws-sigv4 "aws:amz:us-east-1:aoss" \
  --data-binary @assets/your-file.ndjson
```

## Troubleshooting

### Import Failures

**Problem:** Import succeeds but objects don't appear in OpenSearch Dashboards.

**Causes and Solutions:**
1. **Object type not supported**: Verify the object type is supported by OpenSearch Serverless
2. **Missing dependencies**: Check that referenced objects (index patterns for visualizations) exist
3. **Browser cache**: Clear browser cache and refresh Saved Objects page

**Problem:** Import fails with "conflict" errors.

**Causes and Solutions:**
1. **Duplicate IDs**: Each object ID must be unique within its type
2. **Overwrite disabled**: Set `overwrite: true` in config to replace existing objects

**Problem:** Field not found errors in visualizations.

**Causes and Solutions:**
1. **Index pattern mismatch**: Ensure index patterns match actual data indices
2. **Field name changes**: Update visualization field references to match current schema
3. **Time field issues**: Verify `timeFieldName` in index patterns matches data

### Common NDJSON Issues

**Problem:** "Unexpected token" JSON parse errors.

**Causes and Solutions:**
1. **Multi-line JSON**: Each object must be on a single line
2. **Trailing commas**: Remove trailing commas from objects
3. **Invalid characters**: Check for invisible or special characters

**Problem:** "Cannot read property 'attributes' of undefined".

**Causes and Solutions:**
1. **Missing attributes field**: Every saved object requires an `attributes` object
2. **Empty file**: Verify file contains content

## File Exclusions

The following files are excluded from S3 upload:
- `README.md` - Documentation files
- `*.txt` - Text files
- `.gitkeep` - Git placeholder files

Only `.ndjson` files are processed by the Saved Objects Importer.

## Integration with Saved Objects Importer

### How Files Are Processed

1. **S3 Upload**: During CDK deployment, `BucketDeployment` uploads all `.ndjson` files to S3
2. **Lambda Trigger**: CloudFormation custom resource triggers the Lambda function
3. **Download**: Lambda downloads the specified file from S3
4. **Import**: Lambda POSTs content to `/_dashboards/api/saved_objects/_import`
5. **Response**: Import results returned to CloudFormation (success/failure counts)

### Lambda Environment

The Lambda function runs with:
- **Runtime**: Python 3.13 on ARM64
- **Authentication**: AWS SigV4 for OpenSearch Serverless (`aoss` service)
- **Timeout**: 5 minutes per import
- **Memory**: 512 MB

### Import API Details

The Lambda uses the OpenSearch Dashboards Saved Objects Import API:

```
POST /_dashboards/api/saved_objects/_import?overwrite=true
Content-Type: application/ndjson
osd-xsrf: true
```

Response format:
```json
{
  "success": true,
  "successCount": 5,
  "errors": []
}
```

## Security Considerations

- NDJSON files may contain sensitive configuration; review before committing
- Avoid including credentials or secrets in saved object attributes
- Index patterns should not expose sensitive field names unnecessarily
- Review dashboard queries for potential data exposure

## References

- [OpenSearch Saved Objects API](https://opensearch.org/docs/latest/dashboards/management/saved-objects/)
- [OpenSearch Serverless Documentation](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html)
- [NDJSON Format Specification](http://ndjson.org/)
- [OpenSearch Dashboards Import/Export](https://opensearch.org/docs/latest/dashboards/management/saved-objects/#exporting-saved-objects)

## Future Enhancements

Planned additions to this assets directory:

1. **Security Dashboards**: Pre-built dashboards for security monitoring
2. **Threat Hunting Views**: Specialized views for threat detection
3. **Network Monitoring**: Network traffic analysis dashboards
4. **Compliance Reporting**: Compliance-focused visualizations
5. **OCSF Class Dashboards**: Class-specific dashboards for each OCSF event type

Each addition will be documented in this README with usage instructions and dependencies.