# Event Transformer Lambda - Change Log

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