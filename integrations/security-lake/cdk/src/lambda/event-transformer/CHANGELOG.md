# Event Transformer Lambda - Change Log

## Version 3.2.0 (2025-11-07)

### New Features

#### Azure Regulatory Compliance Assessment OCSF Template

**Added comprehensive OCSF template for Azure regulatory compliance events**

- **Template File**: [`templates/regulatory_compliance_assessment_ocsf.yaml`](templates/regulatory_compliance_assessment_ocsf.yaml)
- **OCSF Class**: 2003 (Compliance Finding)
- **OCSF Version**: 1.1.0

**Supported Event Types:**
- `Microsoft.Security/regulatoryComplianceStandards/regulatoryComplianceControls/regulatoryComplianceAssessments`

**Action Mappings:**
- Insert → OCSF Activity ID 1 (Create, Type UID 200301)
- Write → OCSF Activity ID 2 (Update, Type UID 200302)
- Delete → OCSF Activity ID 3 (Delete, Type UID 200303)

**Custom Filters (9 total):**
1. `map_action_to_activity_id` - Azure action to OCSF activity_id mapping
2. `map_action_to_activity_name` - Action to human-readable name conversion
3. `map_action_to_type_uid` - Type UID calculation (200300 + activity_id)
4. `map_compliance_status` - Azure state to OCSF status string mapping
5. `map_compliance_status_id` - State to OCSF status_id conversion
6. `extract_compliance_standard` - Standard name extraction from resource ID
7. `format_resource_count_status` - Resource count formatting (passed/failed/skipped)
8. `derive_severity_from_state` - Intelligent severity calculation based on failure percentage
9. `derive_severity_id_from_state` - Severity name to ID mapping

**Key Features:**
- Automatic compliance standard extraction (Azure CSPM, NIST, PCI-DSS, ISO, SOC, etc.)
- Intelligent severity calculation based on resource failure percentages
- Assessment details link mapping to `finding_info.src_url`
- Resource count status details (Passed: X | Failed: Y | Skipped: Z format)
- Comprehensive test suite with 28 tests covering all filters and edge cases

**Event Type Mapping:**
- Updated [`mapping/event_type_mappings.json`](mapping/event_type_mappings.json) with `azure_compliance_assessment` entry
- Match mode: "contains" for flexible event type detection
- Routes to `regulatory_compliance_assessment_ocsf.yaml` template

**Testing:**
- Test file: [`test_regulatory_compliance_template.py`](test_regulatory_compliance_template.py)
- 28 comprehensive test cases including custom filter tests, integration tests, and edge cases
- Run script: `run_regulatory_compliance_tests.sh`

### Bug Fixes

#### Template Transformer Filter Interdependency

**Fixed filter registration to support interdependent filters**

- **Issue**: `derive_severity_id_from_state` filter could not call `derive_severity_from_state`
- **Location**: [`core/template_transformer.py`](core/template_transformer.py) - filter registration logic
- **Root Cause**: Filters executed in isolated namespaces without access to other filters
- **Fix**: Modified filter registration to execute all filters in shared namespace
- **Impact**: Enables complex filters that call other filters (e.g., severity calculation hierarchy)

**Implementation Details:**
- All template filters now registered in shared execution namespace
- Filters can reference each other during execution
- Namespace includes standard Python functions and datetime module
- Maintains backward compatibility with existing templates

### Documentation Updates

**README.md:**
- Added comprehensive section documenting Azure Regulatory Compliance Assessment template
- Documented all 9 custom filters with descriptions and examples
- Included event structure examples (input and OCSF output)
- Added action mapping table and supported regulatory standards list
- Documented testing procedures and configuration requirements

**CHANGELOG.md:**
- Added this version entry documenting template addition and bug fix

### Files Modified

**Template System:**
- [`templates/regulatory_compliance_assessment_ocsf.yaml`](templates/regulatory_compliance_assessment_ocsf.yaml) - New template file
- [`mapping/event_type_mappings.json`](mapping/event_type_mappings.json) - Added azure_compliance_assessment mapping
- [`core/template_transformer.py`](core/template_transformer.py) - Fixed filter interdependency issue

**Testing:**
- [`test_regulatory_compliance_template.py`](test_regulatory_compliance_template.py) - New comprehensive test suite
- [`run_regulatory_compliance_tests.sh`](run_regulatory_compliance_tests.sh) - Test execution script

**Documentation:**
- [`README.md`](README.md) - Added regulatory compliance template section
- [`CHANGELOG.md`](CHANGELOG.md) - This version entry

### Compatibility

**No Breaking Changes:**
- All changes are additive and backward compatible
- Existing templates continue to function without modification
- Filter namespace changes improve functionality without affecting existing filters

**Requirements:**
- Python 3.11+
- No new dependencies required
- Uses existing Jinja2, YAML, and JSON modules

### Migration Notes

**For New Deployments:**
- Template automatically available via event type mapping
- No configuration changes required
- Events matching `Microsoft.Security/regulatoryComplianceStandards` route automatically

**For Testing:**
```bash
# Run regulatory compliance template tests
pytest test_regulatory_compliance_template.py -v

# Or use convenience script
./run_regulatory_compliance_tests.sh
```

## Version 3.1.1 (2024-10-08)

### Critical Bug Fixes

#### 1. JSON Parsing Error Resolution
- **Fixed**: Template rendering failures causing "Expecting ',' delimiter" errors
- **Location**: [`templates/*.yaml`](templates/) files - `raw_data` fields
- **Change**: Removed double escaping `| replace('\"', '\\\"')` - `to_json` filter handles escaping
- **Files Modified**:
  - [`templates/compliance_assessment_ocsf.yaml`](templates/compliance_assessment_ocsf.yaml)
  - [`templates/security_alert_ocsf.yaml`](templates/security_alert_ocsf.yaml) 
  - [`templates/secure_score_ocsf.yaml`](templates/secure_score_ocsf.yaml)

#### 2. Queue Message Deletion Logic Fix  
- **Fixed**: Successfully processed messages not being deleted from custom queues
- **Location**: [`app.py`](app.py) line 588 - variable name conflict
- **Change**: Renamed `event_type` to `azure_event_type` in Azure event processing loop
- **Impact**: Messages now deleted immediately after successful processing

#### 3. DLQ Cycle Prevention
- **Added**: Source queue detection to prevent infinite message loops
- **Location**: [`app.py`](app.py) - `send_failed_event_to_dlq()` function
- **Change**: Added `source_queue_url` parameter and cycle detection logic
- **Impact**: Failed DLQ messages no longer sent back to same DLQ

#### 4. Smart Queue Processing
- **Fixed**: Function processing non-existent messages beyond queue capacity
- **Location**: [`app.py`](app.py) - `fetch_messages_from_queue()` function  
- **Change**: Set `WaitTimeSeconds=0` and immediate break on empty queue
- **Impact**: Only processes actual messages, improves performance

### Enhancements

#### Enhanced Logging System
- **Structured Log Levels**: INFO for operations, WARN for issues, DEBUG for diagnostics
- **Third-Party Suppression**: PyArrow, boto3, botocore debug logs suppressed
- **Message Lifecycle**: Complete tracking from queue fetch to deletion
- **Diagnostic Capabilities**: Enhanced template rendering and JSON parsing diagnostics

#### Immediate Message Processing
- **Custom Queue Processing**: Messages deleted immediately after successful processing
- **Fallback Handling**: Batch deletion for messages that fail immediate deletion
- **Comprehensive Statistics**: Tracking immediate vs batch deletions

### Code Quality Improvements

#### Variable Scope Management
- **Isolation**: Separated Lambda event types from Azure event types
- **Naming**: Clear distinction between `event_type` (Lambda) and `azure_event_type` (Azure)
- **Context Preservation**: Invocation context maintained throughout function execution

#### Error Handling Robustness
- **Failure State Management**: Proper initialization and preservation of message failure state
- **Exception Handling**: Comprehensive error catching with detailed logging
- **Graceful Degradation**: Continue processing valid events despite individual failures

## Files Modified

### Core Lambda Function
- [`app.py`](app.py): Main Lambda handler with queue processing and error handling fixes

### Template System
- [`core/template_transformer.py`](core/template_transformer.py): Enhanced JSON parsing diagnostics
- [`helpers/security_lake_client.py`](helpers/security_lake_client.py): PyArrow debug log suppression

### Transformation Templates
- [`templates/compliance_assessment_ocsf.yaml`](templates/compliance_assessment_ocsf.yaml): Fixed JSON escaping
- [`templates/security_alert_ocsf.yaml`](templates/security_alert_ocsf.yaml): Fixed JSON escaping
- [`templates/secure_score_ocsf.yaml`](templates/secure_score_ocsf.yaml): Fixed JSON escaping
- [`templates/security_alert_cloudtrail.yaml`](templates/security_alert_cloudtrail.yaml): Fixed conditional comma logic
- [`templates/secure_score_cloudtrail.yaml`](templates/secure_score_cloudtrail.yaml): Fixed conditional comma logic

### Documentation Updates
- [`README.md`](README.md): Updated features, environment variables, processing flow, and bug fix documentation
- [`DEBUGGING_FAILED_EVENTS.md`](DEBUGGING_FAILED_EVENTS.md): Enhanced logging capabilities and diagnostic procedures
- [`dlq_processing_guide.md`](dlq_processing_guide.md): DLQ cycle prevention and enhanced logging documentation
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md): Comprehensive troubleshooting guide for resolved issues

## Migration Notes

### For Existing Deployments
1. **No Breaking Changes**: All fixes are backward compatible
2. **Template Updates**: OCSF templates now generate valid JSON for complex content
3. **Log Volume**: Third-party debug logs suppressed - enable with LOGGING_LEVEL=DEBUG if needed
4. **Queue Processing**: Custom queue processing now more efficient and reliable

### Monitoring Updates
- **New Metrics**: `messages_deleted_immediately`, `messages_deleted_total`, `deletion_failures`
- **Log Patterns**: Updated log levels - adjust CloudWatch filters accordingly
- **Alerting**: Consider alerts for DLQ cycle prevention warnings

## Compatibility

### Python Dependencies
- No new dependencies added
- Enhanced compatibility with existing boto3, json, logging modules
- Template system uses existing yaml, jinja2 dependencies

### AWS Services
- **CloudTrail**: No changes to Event Data Store or Channel integration
- **SQS**: Enhanced message deletion reliability
- **Security Lake**: Improved OCSF template reliability
- **CloudWatch**: Enhanced structured logging

## Testing Recommendations

### Regression Testing
- Verify OCSF template rendering with complex HTML content
- Test custom queue processing with immediate message deletion
- Validate DLQ processing without message cycling
- Confirm smart queue polling stops at actual queue capacity

### Performance Testing  
- Monitor reduced log volume with third-party suppression
- Validate improved queue processing efficiency
- Test immediate message deletion performance
- Verify template caching effectiveness