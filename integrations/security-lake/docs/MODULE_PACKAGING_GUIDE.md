© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Integration Module Packaging and Deployment Guide

## Version 1.0.0

## Overview

This guide covers packaging, testing, and deploying Security Lake integration modules. Follow these procedures to ensure consistent, reliable module deployment.

## Module Packaging Structure

### Required Files

Every integration module MUST include:

```
modules/your-module/
├── index.ts                        # Module exports
├── your-module-module.ts           # Module implementation
├── README.md                       # Module documentation
├── config.schema.json              # JSON schema for validation
├── CHANGELOG.md                    # Version history
└── src/
    └── lambda/
        └── processor/
            ├── app.py              # Lambda handler
            ├── local_test.py       # Local testing
            ├── test_lambda.py      # Unit tests
            ├── requirements.txt    # Python dependencies
            └── helpers/            # Helper classes
```

### Optional Files

```
modules/your-module/
├── integration_test.py             # Integration tests
├── docs/                           # Additional documentation
│   ├── ARCHITECTURE.md
│   └── TROUBLESHOOTING.md
└── scripts/                        # Module-specific scripts
    └── configure-secrets.sh
```

## Packaging Process

### Step 1: Verify Module Completeness

Run the module checklist:

```bash
cd integrations/security-lake/cdk
npm run module-checklist -- --module your-module
```

Checklist items:
- [ ] Implements IIntegrationModule interface
- [ ] Config validation with clear error messages
- [ ] IAM permissions follow least privilege
- [ ] Lambda code includes error handling
- [ ] AWS Powertools used for logging/tracing
- [ ] Unit tests with >80% coverage
- [ ] Local testing script provided
- [ ] README documents configuration
- [ ] NO emotes in code or documentation
- [ ] Copyright headers in all files
- [ ] Module registered in registry

### Step 2: Validate Configuration Schema

Test configuration validation:

```bash
cd modules/your-module
# Create test config
cat > test-config.yaml <<EOF
integrations:
  your-module:
    enabled: true
    config:
      # Add test configuration
EOF

# Validate
npm run validate-config -- --config test-config.yaml
```

### Step 3: Run Unit Tests

```bash
cd modules/your-module/src/lambda/processor
pytest test_lambda.py -v --cov=. --cov-report=term-missing
```

Requirements:
- Minimum 80% code coverage
- All tests pass
- No actual AWS service calls (use mocks)

### Step 4: Test Local Execution

```bash
cd modules/your-module/src/lambda/processor
python local_test.py
```

Verify:
- Lambda executes without errors
- Logs are structured correctly
- Mock data processed successfully

### Step 5: Integration Testing

```bash
# Set up test environment
export AWS_PROFILE=test-account
export AWS_REGION=us-east-1

# Run integration tests
cd modules/your-module
pytest integration_test.py -v
```

Integration tests should:
- Deploy to isolated test stack
- Verify IAM permissions work
- Test end-to-end flow
- Clean up resources after

### Step 6: Security Scan

Run security checks:

```bash
# Check for hardcoded secrets
npm run security-scan -- --module your-module

# Verify IAM least privilege
npm run iam-analyzer -- --module your-module

# Check for vulnerabilities
npm audit
pip-audit -r modules/your-module/src/lambda/processor/requirements.txt
```

### Step 7: Build and Package

```bash
cd integrations/security-lake/cdk
npm run build
npm run synth -- -c configFile=config.test.yaml
```

Verify:
- TypeScript compiles without errors
- CDK synthesis succeeds
- CloudFormation template is valid

## Deployment Process

### Pre-Deployment Checklist

- [ ] All tests pass
- [ ] Security scan clean
- [ ] Documentation complete
- [ ] Configuration validated
- [ ] Secrets configured in Secrets Manager
- [ ] Security Lake S3 bucket exists
- [ ] IAM permissions reviewed

### Development Deployment

```bash
cd integrations/security-lake/cdk

# Create dev config
cp config.example.yaml config.dev.yaml
# Edit config.dev.yaml with dev settings

# Deploy to development
npm run deploy:dev
```

### Staging Deployment

```bash
# Create staging config
cp config.example.yaml config.staging.yaml
# Edit config.staging.yaml with staging settings

# Deploy to staging
cdk deploy -c configFile=config.staging.yaml
```

### Production Deployment

```bash
# Create production config (with strict settings)
cp config.example.yaml config.prod.yaml
# Edit config.prod.yaml:
# - environment: prod
# - encryption: CUSTOMER_MANAGED_CMK
# - terminationProtection: true
# - monitoring alarms: enabled

# Review changes
cdk diff -c configFile=config.prod.yaml

# Deploy to production
cdk deploy -c configFile=config.prod.yaml --require-approval broadening
```

## Post-Deployment Verification

### Step 1: Verify Stack Deployment

```bash
aws cloudformation describe-stacks \
  --stack-name security-lake-integration-prod \
  --query 'Stacks[0].StackStatus'
```

Expected: `CREATE_COMPLETE` or `UPDATE_COMPLETE`

### Step 2: Check Lambda Functions

```bash
# List deployed functions
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `your-module`)].FunctionName'

# Check function configuration
aws lambda get-function-configuration \
  --function-name your-module-processor
```

### Step 3: Verify Module Secrets

```bash
# List secrets
aws secretsmanager list-secrets \
  --filters Key=name,Values=your-module

# Test secret retrieval (without showing value)
aws secretsmanager describe-secret \
  --secret-id your-module-credentials
```

### Step 4: Monitor Initial Execution

```bash
# Tail Lambda logs
aws logs tail /aws/lambda/your-module-processor --follow

# Check for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/your-module-processor \
  --filter-pattern "ERROR"
```

### Step 5: Verify Events Flow

```bash
# Check SQS queue metrics
aws sqs get-queue-attributes \
  --queue-url <QUEUE_URL> \
  --attribute-names ApproximateNumberOfMessages

# Check Security Lake S3
aws s3 ls s3://your-security-lake-bucket/ext/ --recursive | head -20
```

## Rollback Procedures

### Immediate Rollback

```bash
# Roll back to previous version
cdk deploy -c configFile=config.prod.yaml --previous-version
```

### Disable Module

```yaml
# In config.prod.yaml
integrations:
  your-module:
    enabled: false  # Disable without undeploying
```

```bash
cdk deploy -c configFile=config.prod.yaml
```

### Complete Removal

```bash
# Destroy stack
cdk destroy -c configFile=config.prod.yaml

# Or remove just the module (if independently deployed)
cdk destroy -c configFile=config.prod.yaml --stack your-module-stack
```

## Troubleshooting Deployment Issues

### Issue: CDK Synthesis Fails

**Symptoms**: `cdk synth` fails with TypeScript errors

**Solutions**:
1. Run `npm run build` to compile TypeScript
2. Check for syntax errors in module code
3. Verify all imports are correct
4. Check tsconfig.json includes module path

### Issue: Lambda Deployment Fails

**Symptoms**: Lambda function fails to create

**Solutions**:
1. Check requirements.txt for compatible versions
2. Verify Python 3.13 ARM64 compatibility
3. Check Lambda package size (<250MB)
4. Review bundling commands in module code

### Issue: IAM Permission Errors

**Symptoms**: Lambda execution fails with AccessDenied

**Solutions**:
1. Review getRequiredPermissions() in module
2. Check resource ARNs are correct
3. Verify principal trust relationships
4. Test permissions with AWS IAM Policy Simulator

### Issue: Secrets Not Found

**Symptoms**: SecretsManager GetSecretValue fails

**Solutions**:
1. Verify secret was created: `aws secretsmanager list-secrets`
2. Check secret name matches config
3. Verify Lambda has secretsmanager:GetSecretValue permission
4. Ensure secret is in same region as Lambda

## Monitoring Post-Deployment

### Key Metrics to Monitor

1. **Lambda Invocations**
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Invocations \
     --dimensions Name=FunctionName,Value=your-module-processor \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Sum
   ```

2. **Lambda Errors**
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Errors \
     --dimensions Name=FunctionName,Value=your-module-processor \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Sum
   ```

3. **SQS Queue Depth**
   ```bash
   aws sqs get-queue-attributes \
     --queue-url <QUEUE_URL> \
     --attribute-names ApproximateNumberOfMessages,ApproximateAgeOfOldestMessage
   ```

4. **DLQ Messages**
   ```bash
   aws sqs get-queue-attributes \
     --queue-url <DLQ_URL> \
     --attribute-names ApproximateNumberOfMessages
   ```

### CloudWatch Dashboards

Create module-specific dashboard:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name your-module-dashboard \
  --dashboard-body file://dashboard-config.json
```

## Module Version Management

### Semantic Versioning

Modules follow semver: MAJOR.MINOR.PATCH

- **MAJOR**: Breaking changes to interface or config
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, no interface changes

### Updating Module Version

1. Update `moduleVersion` in module class
2. Update CHANGELOG.md with changes
3. Update tests for new functionality
4. Deploy and test in dev/staging
5. Deploy to production with approval

### Deprecation Process

When deprecating module features:

1. Add deprecation warnings in validateConfig()
2. Document in CHANGELOG.md
3. Maintain for 2 major versions
4. Remove in next major version

## Best Practices

### Deployment

1. Always deploy to dev first
2. Run integration tests in staging
3. Use `--require-approval` for production
4. Monitor for 24 hours after production deployment
5. Have rollback plan ready

### Configuration

1. Use separate config files per environment
2. Never commit secrets to version control
3. Use parameter store for environment-specific values
4. Validate config before deployment

### Monitoring

1. Set up CloudWatch alarms before deployment
2. Configure SNS notifications for ops team
3. Monitor Lambda duration and memory usage
4. Track DLQ message counts

### Security

1. Review IAM permissions before each deployment
2. Rotate secrets regularly
3. Enable CloudTrail logging
4. Use KMS encryption for all data

## Module Distribution

### Internal Distribution

For internal teams:
1. Tag release in version control
2. Update module registry
3. Document in team wiki
4. Notify stakeholders

### External Distribution

For public modules:
1. Create GitHub release
2. Update npm package (if applicable)
3. Publish documentation
4. Update examples

## References

- [Module Interface Specification](./MODULE_INTERFACE_SPEC.md)
- [Module Development Guide](./MODULE_DEVELOPMENT_GUIDE.md)
- [Configuration Schema](./CONFIG_SCHEMA.md)
- [AWS CDK Best Practices](https://docs.aws.amazon.com/cdk/latest/guide/best-practices.html)