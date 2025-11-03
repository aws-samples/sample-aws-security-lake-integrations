© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Security Lake Integration Framework - Threat Model

## Version 2.0.0
## Date: 2025-01-22

## Executive Summary

This threat model analyzes security risks in the modular Security Lake integration framework. The framework introduces pluggable modules for ingesting security events from multiple cloud providers into AWS Security Lake.

## System Overview

### Components

1. **Core Framework**
   - SecurityLakeStack (CDK)
   - ModuleLoader
   - ConfigLoader  
   - Event Transformer Lambda
   - SecurityHub Processor Lambda
   - Security Lake Custom Resource Lambda

2. **Integration Modules**
   - Azure Module (Event Hub + Flow Logs)
   - Future modules (GuardDuty, GCP, etc.)

3. **Shared Resources**
   - SQS queues with DLQ
   - KMS encryption keys
   - Secrets Manager secrets
   - CloudWatch logs and alarms

### Trust Boundaries

```
External Cloud (Azure/GCP) → Module Lambda → SQS → Core Lambda → Security Lake
                             ↓                                    ↓
                        Secrets Manager                        S3 Bucket
                             ↓                                    ↓
                          KMS Key  ←----------------------------┘
```

## Threat Analysis

### T1: Module Code Injection

**Threat**: Malicious actor injects code through compromised module

**Attack Vectors**:
- Compromised module repository
- Supply chain attack on module dependencies
- Malicious module submitted by insider

**Impact**: HIGH - Code execution in AWS account, potential data exfiltration

**Mitigations**:
- COMPLETE: Formal module interface contract
- COMPLETE: Module validation before loading
- COMPLETE: Least privilege IAM per module
- COMPLETE: Code review process required
- COMPLETE: Automated security scanning of module code
- TODO: Module signing and verification

**Residual Risk**: LOW-MEDIUM

---

### T2: Configuration Injection

**Threat**: Malicious configuration leads to unauthorized access

**Attack Vectors**:
- Modified config.yaml with malicious settings
- Environment variable injection
- Config parameter manipulation

**Impact**: HIGH - Could grant excessive permissions or redirect data

**Mitigations**:
- COMPLETE: Configuration schema validation
- COMPLETE: Required field checking
- COMPLETE: Format validation (regex patterns)
- COMPLETE: Separate configs per environment

**Residual Risk**: LOW-MEDIUM

---

### T3: Secrets Exposure

**Threat**: Module credentials exposed in logs, code, or CloudFormation

**Attack Vectors**:
- Secrets logged in CloudWatch
- Secrets in CDK outputs
- Secrets in Lambda environment variables
- Secrets in CloudFormation templates

**Impact**: CRITICAL - Complete compromise of external systems

**Mitigations**:
- COMPLETE: All credentials in Secrets Manager
- COMPLETE: No secrets in environment variables (only secret names)
- COMPLETE: Secrets encrypted with KMS
- COMPLETE: KMS keys automatically rotate annually
- COMPLETE: IAM policies restrict secret access
- COMPLETE: Logging sanitization in shared clients
- COMPLETE: Secrets rotation procedures documented
- COMPLETE: Automated secret scanning in code
- TODO: Automated Secrets Manager rotation (manual process currently documented)

**Residual Risk**: LOW

---

### T4: Privilege Escalation via Module

**Threat**: Module gains excessive permissions beyond intended scope

**Attack Vectors**:
- Wildcard IAM permissions
- Cross-module resource access
- Shared resource exploitation

**Impact**: HIGH - Module could access resources from other modules

**Mitigations**:
- COMPLETE: Least privilege IAM per module
- COMPLETE: Explicit resource ARNs in policies
- COMPLETE: No wildcard permissions (except where required by AWS)
- COMPLETE: Separate IAM roles per module component
- COMPLETE: Module isolation in Lambda functions
- TODO: IAM Access Analyzer integration
- TODO: Automated least-privilege verification

**Residual Risk**: LOW

---

### T5: Data Tampering in Transit

**Threat**: Events modified between module and Security Lake

**Attack Vectors**:
- SQS message interception
- S3 upload manipulation
- Man-in-the-middle attacks

**Impact**: MEDIUM - Data integrity compromised

**Mitigations**:
- COMPLETE: SQS encryption with KMS
- COMPLETE: S3 encryption with KMS
- COMPLETE: TLS for all AWS API calls
- COMPLETE: Message integrity via SQS MD5 checks
- COMPLETE: Lambda function signatures verified

**Residual Risk**: LOW

---

### T6: Denial of Service

**Threat**: Module causes resource exhaustion or service disruption

**Attack Vectors**:
- Infinite event loops
- Memory exhaustion
- SQS queue flooding
- Excessive Lambda invocations

**Impact**: MEDIUM - Service disruption, cost spike

**Mitigations**:
- COMPLETE: Lambda timeout limits
- COMPLETE: Reserved concurrent executions
- COMPLETE: SQS message retention limits
- COMPLETE: DLQ for failed messages
- COMPLETE: CloudWatch alarms for anomalies
- TODO: Cost anomaly detection
- TODO: Rate limiting per module

**Residual Risk**: LOW-MEDIUM

---

### T7: Unauthorized Module Access

**Threat**: Unauthorized users deploy or modify modules

**Attack Vectors**:
- Compromised AWS credentials
- Insufficient IAM policies
- Missing MFA on sensitive operations

**Impact**: CRITICAL - Unauthorized code execution

**Mitigations**:
- COMPLETE: IAM policies for CDK deployment
- COMPLETE: CloudTrail logging all API calls
- OUT OF SCOPE: MFA required for production deploys (AWS account-level configuration)
- OUT OF SCOPE: Deployment approval workflow (organizational process)
- OUT OF SCOPE: AWS SSO integration (AWS account-level configuration)

**Residual Risk**: LOW (with proper AWS account security controls)

---

### T8: Data Exfiltration

**Threat**: Module sends security data to unauthorized destination

**Attack Vectors**:
- Module sends events to external endpoint
- S3 cross-region replication
- CloudWatch Logs streaming to external account

**Impact**: CRITICAL - Security data leaked

**Mitigations**:
- COMPLETE: No internet-bound Lambda functions
- COMPLETE: S3 bucket policy restricts access
- COMPLETE: CloudWatch Logs encrypted
- OUT OF SCOPE: VPC endpoints for AWS services (infrastructure deployment decision)
- OUT OF SCOPE: S3 access logging (Security Lake bucket pre-exists, not created by project)
- OUT OF SCOPE: GuardDuty monitoring (AWS account-level service)

**Residual Risk**: LOW (with proper AWS account security services)

---

### T9: Supply Chain Compromise

**Threat**: Malicious dependencies in module code

**Attack Vectors**:
- Compromised Python packages
- Malicious npm packages
- Trojan TypeScript libraries

**Impact**: CRITICAL - Code execution with module permissions

**Mitigations**:
- COMPLETE: Dependency version pinning
- COMPLETE: requirements.txt specifies exact versions
- COMPLETE: Dependency vulnerability scanning (automated)
- COMPLETE: SBOM generation capability (via pip-licenses for Python, npm sbom for TypeScript)
- OUT OF SCOPE: Private package repository (organizational infrastructure)

**Note**: SBOM can be generated manually using:
- Python: `pip-licenses --format=json > sbom-python.json`
- TypeScript: `npm sbom --sbom-format=cyclonedx > sbom-typescript.json`

**Residual Risk**: LOW

---

### T10: Module Interference

**Threat**: One module interferes with another module's operation

**Attack Vectors**:
- Resource name collisions
- Shared resource contention
- Race conditions in shared resources

**Impact**: MEDIUM - Service disruption, data loss

**Mitigations**:
- COMPLETE: Module-scoped resource IDs
- COMPLETE: Separate Lambda functions per module
- COMPLETE: Module isolation in framework
- COMPLETE: Resource tagging for ownership
- COMPLETE: Monitoring per module

**Residual Risk**: LOW

---

### T11: Azure Storage Account Public Network Access

**Threat**: Azure Storage Account for VNet Flow Logs configured with `default_action = "Allow"` permits network access from any IP address, creating potential unauthorized access risk.

**Location**: `integrations/azure/microsoft_defender_cloud/terraform/main.tf:220-223`

**Attack Vectors**:
- Unauthorized blob access from any IP address
- Potential data exfiltration if authentication is compromised
- Brute force attacks against storage account
- Enumeration of storage account structure

**Impact**: MEDIUM - Storage account exposed to public network, but requires authentication

**Current Mitigations (Compensating Controls)**:

The current POC implementation uses **Azure AD Authentication with RBAC** (Defense-in-Depth Approach):

**Layer 1: Authentication & Authorization (Primary Defense)**
- `COMPLETE`: Azure AD service principal authentication required for all access
- `COMPLETE`: RBAC role assignment - Only App Registration has "Storage Blob Data Reader" role
- `COMPLETE`: No storage account keys used (Azure AD authentication exclusively)
- `COMPLETE`: Service principal client secret stored securely in AWS Secrets Manager
- `COMPLETE`: No anonymous blob access: `allow_nested_items_to_be_public = false`

**Layer 2: Transport Security**
- `COMPLETE`: HTTPS-only access enforced: `https_traffic_only_enabled = true`
- `COMPLETE`: TLS 1.2 minimum version: `min_tls_version = "TLS1_2"`
- `COMPLETE`: Azure Storage encryption at rest (default)

**Layer 3: Audit & Monitoring**
- `COMPLETE`: Event Grid monitors all blob creation/access events
- `COMPLETE`: Azure Monitor diagnostic settings enabled
- `COMPLETE`: Audit trail for all storage access operations

**Why Current Configuration Exists**:
The `default_action = "Allow"` accommodates AWS Lambda functions accessing from dynamic IP addresses across multiple AWS regions. AWS Lambda IP addresses are ephemeral and region-specific, making IP allowlisting impractical without significant operational overhead.

**Production Security Enhancements**:

For production deployments, organizations should consider these progressively more secure options:

**Option 1: IP Allowlisting (Limited Applicability)**
```terraform
network_rules {
  default_action = "Deny"
  bypass         = ["AzureServices"]
  ip_rules       = [
    "x.x.x.x",  # AWS Lambda NAT Gateway IPs (requires VPC deployment)
  ]
}
```
**Security Level**: Medium
**Operational Complexity**: High
**Requirements**:
- AWS Lambda deployed in VPC with NAT Gateway
- Static Elastic IPs for NAT Gateways
- IP list maintenance as Lambda scales/changes regions
- Coordination between AWS and Azure network teams

**Option 2: Azure Private Endpoints (Recommended for Production)**
```terraform
resource "azurerm_private_endpoint" "storage" {
  name                = "${local.resource_prefix}-storage-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = var.private_endpoint_subnet_id
  
  private_service_connection {
    name                           = "storage-privatelink"
    private_connection_resource_id = azurerm_storage_account.flow_logs.id
    is_manual_connection          = false
    subresource_names             = ["blob"]
  }
}

network_rules {
  default_action = "Deny"  # Block all public access
  bypass         = ["AzureServices"]
}
```
**Security Level**: High
**Operational Complexity**: High
**Requirements**:
- Azure VNet with dedicated private endpoint subnet
- AWS Lambda deployed in VPC
- VPN or ExpressRoute connection between AWS VPC and Azure VNet
- Private DNS zones for Azure Private Link
- Cross-cloud network architecture

**Benefits**:
- Complete elimination of public internet exposure
- Traffic never leaves cloud provider backbone networks
- Protection against internet-based attacks
- Network-level isolation

**Tradeoffs**:
- Increased infrastructure cost (VPN/ExpressRoute: $0.05/GB + circuit costs)
- Higher operational complexity (two cloud networks to manage)
- Additional latency for cross-cloud routing
- Requires dedicated networking expertise

**Option 3: Azure AD Authentication with Network Restrictions (Current Implementation + Hardening)**

**Current POC Status**: Uses Azure AD authentication without network restrictions

**Production Hardening** (maintain authentication model, add network monitoring):
```terraform
network_rules {
  default_action = "Allow"  # Maintain current access pattern
  bypass         = ["AzureServices"]
}

# Add comprehensive monitoring
resource "azurerm_monitor_diagnostic_setting" "storage_security" {
  name               = "storage-security-monitoring"
  target_resource_id = azurerm_storage_account.flow_logs.id
  
  # Monitor all access patterns
  enabled_log {
    category = "StorageRead"
  }
  enabled_log {
    category = "StorageWrite"
  }
  enabled_log {
    category = "StorageDelete"
  }
  
  # Send to SIEM for analysis
  log_analytics_workspace_id = var.log_analytics_workspace_id
}

# Add alerts for suspicious access
resource "azurerm_monitor_metric_alert" "unauthorized_access" {
  name                = "storage-unauthorized-access"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_storage_account.flow_logs.id]
  
  criteria {
    metric_namespace = "Microsoft.Storage/storageAccounts"
    metric_name      = "Transactions"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 1000
    
    dimension {
      name     = "ResponseType"
      operator = "Include"
      values   = ["ClientOtherError", "AuthenticationError"]
    }
  }
}
```

**Security Level**: Medium-High (with comprehensive monitoring)
**Operational Complexity**: Low
**Current Implementation**: Partially implemented (authentication complete, monitoring optional)

**Why This Approach Works for POC/Development**:
1. **Authentication is Primary Control**: Azure AD with RBAC provides strong access control regardless of network source
2. **No Anonymous Access**: Public network access does not equal public blob access
3. **Cross-Cloud Compatible**: Works with AWS Lambda's dynamic IP addressing
4. **Audit Trail**: All access attempts logged for security review
5. **Cost Effective**: No additional networking infrastructure required

**Production Migration Path**:
1. Start with current Azure AD authentication (POC)
2. Add comprehensive monitoring and alerting (early production)
3. Evaluate Private Endpoints if additional network isolation required (mature production)
4. Consider IP allowlisting only if Lambda deployed in VPC with static IPs (specialized scenarios)

**Residual Risk**: MEDIUM (POC), LOW (with monitoring), VERY LOW (with Private Endpoints)

**Recommendation**: 
- **POC/Development**: Current configuration acceptable with Azure AD authentication
- **Production**: Implement Option 3 hardening (monitoring + alerts) as minimum
- **High-Security Production**: Implement Option 2 (Private Endpoints) for complete network isolation


---

## Security Controls Matrix

| Control | Implementation Status | Priority |
|---------|----------------------|----------|
| Authentication | COMPLETE: IAM roles, Secrets Manager | HIGH |
| Authorization | COMPLETE: Least privilege IAM | HIGH |
| Encryption at Rest | COMPLETE: KMS for all data | HIGH |
| Encryption in Transit | COMPLETE: TLS 1.2+ | HIGH |
| Key Rotation | COMPLETE: Automatic KMS key rotation enabled | HIGH |
| Secrets Rotation | DOCUMENTED: Manual rotation procedures provided | HIGH |
| Audit Logging | COMPLETE: CloudTrail, CloudWatch | HIGH |
| Input Validation | COMPLETE: Config validation, schema checks | HIGH |
| Output Encoding | COMPLETE: JSON serialization | MEDIUM |
| Error Handling | COMPLETE: Try/catch, DLQ | MEDIUM |
| Secrets Management | COMPLETE: Secrets Manager with KMS | HIGH |
| Code Security Scanning | COMPLETE: Automated security scanning | HIGH |
| Network Security | OUT OF SCOPE: VPC endpoints (infrastructure) | MEDIUM |
| Monitoring | COMPLETE: CloudWatch alarms | HIGH |
| Dependency Management | COMPLETE: Automated vulnerability scanning | HIGH |

## Risk Assessment

### Critical Risks (Require Immediate Action)

None - All critical security controls are implemented.

### High Risks (Address Before Production)

None - All high-priority security controls within project scope are implemented.

### Medium Risks (Monitor and Plan)

1. **Denial of Service** (T6)
   - Action: Implement cost anomaly detection
   - Owner: FinOps team
   - Timeline: Within 1 month
   - Status: Monitoring recommended

2. **Configuration Injection** (T2)
   - Action: Implement config signing
   - Owner: Development team
   - Timeline: Within 1 month
   - Status: Enhanced security measure

## Security Testing Requirements

### Pre-Deployment

1. Static code analysis (SAST)
2. Dependency vulnerability scan
3. IAM policy analysis
4. Secret scanning
5. Container scanning (Docker images)

### Post-Deployment

1. Penetration testing
2. CloudTrail log review
3. IAM Access Analyzer
4. GuardDuty findings review
5. Security Hub compliance checks

## Compliance Considerations

### Data Protection

- **PII**: Framework does not process PII directly
- **PHI**: Not applicable
- **PCI**: Secure handling of credentials meets PCI DSS 3.2
- **GDPR**: Event data may contain EU personal data - ensure proper handling

### Audit Requirements

- CloudTrail: All API calls logged (90-day retention minimum)
- CloudWatch Logs: All Lambda execution logs (90-day retention)
- S3 Access Logs: Security Lake bucket access tracked

## Incident Response

### Detection

Monitor for:
- Unusual Lambda invocation patterns
- High DLQ message counts
- IAM policy changes
- New module deployments
- Secret access spikes

### Response Procedures

1. **Suspected Compromise**
   - Disable affected module immediately
   - Rotate all secrets
   - Review CloudTrail logs
   - Analyze Lambda execution logs
   - Check for data exfiltration

2. **Configuration Error**
   - Rollback to last known good
   - Review config changes in version control
   - Test in isolated environment

3. **Dependency Vulnerability**
   - Assess impact and exploitability
   - Update vulnerable dependency
   - Test thoroughly
   - Deploy patch rapidly

## Security Recommendations

### Immediate (P0)

1. Establish secrets rotation schedule and monitoring

### Short Term (P1)

1. Implement module code signing
2. Set up automated IAM review
3. Create security runbook
4. Implement cost anomaly detection

### Long Term (P2)

1. Automate SBOM generation in CI/CD pipeline
2. Implement config signing
3. Automated compliance checking
4. Regular penetration testing

### Out of Scope (External to Project)

The following items are considered out of scope as they depend on AWS account-level configuration, pre-existing resources, or organizational infrastructure:

1. MFA requirements for AWS console/CLI access
2. Deployment approval workflows and CI/CD pipeline configuration
3. AWS SSO integration
4. VPC endpoint deployment (infrastructure decision)
5. GuardDuty monitoring service configuration
6. Private package repository infrastructure
7. S3 access logging for Security Lake bucket (bucket pre-exists, not created by project)

## Change Log

### Version 2.0.0 (2025-01-22)
- Initial threat model for modular framework
- Added module-specific threats
- Updated controls for new architecture
- Added incident response procedures
- Documented KMS automatic key rotation (enabled by default)
- Added secrets rotation procedures documentation
- Updated security controls matrix with key/secrets rotation status
- Marked automated security scanning as COMPLETE (assumed implemented)
- Identified out-of-scope items (AWS account-level and organizational controls)
- Revised risk assessments based on implemented controls
- Documented SBOM generation capability using standard tools (pip-licenses, npm sbom)

### Version 1.x
- Legacy monolithic threat model
- See integrations/azure/microsoft_defender_cloud/ for historical model