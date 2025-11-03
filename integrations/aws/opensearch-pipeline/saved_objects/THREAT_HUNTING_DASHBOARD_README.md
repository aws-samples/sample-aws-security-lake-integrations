# Cross-Cloud Threat Hunting Dashboard

## Overview
Advanced threat hunting dashboard that correlates security findings with network activity across AWS, Azure, and GCP environments. This dashboard combines data from both security event logs and network flow logs to provide comprehensive threat intelligence and investigation capabilities.

## Dashboard File
`cross-cloud-threat-hunting-dashboard.ndjson`

## Index Pattern
Uses unified index pattern: `f2ba75ac-1a82-4106-91b4-af36bb226463` which includes:
- Security findings (Compliance, Detection, Vulnerability)
- Network activity (Flow logs from AWS VPC, Azure NSG, GCP)
- API operations (CloudTrail, Azure Activity, GCP Audit)

## Key Features

### 1. Interactive Filter Controls (Top Bar)
**Control Group with 5 Filters:**
- **Cloud Provider**: Filter by AWS, Azure, or GCP
- **Account**: Select specific cloud accounts
- **Region**: Filter by cloud regions
- **Severity**: Focus on specific severity levels (Informational, Low, Medium, High, Critical)
- **Event Class**: Filter by event types (Network Activity, Security Finding, API Activity, etc.)

**Usage:** Controls cascade hierarchically - selecting a cloud provider auto-updates available accounts and regions.

### 2. Threat Identification Visualizations

**Severity by Cloud Provider** (Stacked Bar)
- Shows severity distribution across all cloud platforms
- Enables quick identification of which clouds have critical issues
- Helps prioritize investigation efforts

**Activity Timeline by Class** (Line Chart)
- 7-day timeline of all security and network events
- Groups by event class (Network Activity, Security Finding, API Activity)
- Identifies temporal patterns and anomalies

**Top Source and Destination IPs** (Table)
- Lists top 15 IPs by event count
- Groups by event class to show if IPs appear in both security findings and network flows
- Correlation key: Same IP in multiple event classes indicates potential threat actor

### 3. Security and Network Correlation

**Network Security Correlation** (Table)
- Filters for Refuse/Traffic activities
- Shows source IPs with refused connection counts
- Includes cardinality of unique destination ports (port scanning indicator)
- Key columns: Source IP, Activity (Refuse/Traffic), Unique Ports, Event Count

**Detection Logic:**
- High event count + High unique ports = Port scanning
- High refuse count + Low ports = Targeted attack/Brute force
- Mix of Refuse and Traffic = Successful penetration after reconnaissance

### 4. API and User Activity Analysis

**Top API Operations** (Horizontal Bar)
- Shows top 15 API operations across all clouds
- Identifies unusual or high-volume API activity
- Detects API abuse, privilege escalation attempts, data exfiltration

**User Activity Correlation** (Table)
- Tracks users across all cloud providers
- Shows unique API count per user
- Columns: User, Cloud Provider, Event Count, Unique APIs
- High unique API count indicates exploration/reconnaissance

### 5. Data Exfiltration Monitoring

**Data Transfer by Cloud** (Stacked Bar)
- Sum of bytes transferred per cloud provider
- Groups by direction (Inbound/Outbound)
- Monitors for unusual data transfer patterns

**Action and Status Distribution** (Donut)
- Shows distribution of connection statuses
- Identifies failed attempts vs successful connections
- Monitors authentication and authorization patterns

### 6. Resource Access Patterns

**Resource Access by Cloud** (Table)
- Account-level access summary
- Groups by cloud provider
- Shows unique IP count per account
- Detects lateral movement across accounts

### 7. Raw Event Data

**Threat Hunt - Event Details** (Saved Search)
- Complete event data in tabular format
- Key columns: Cloud Provider, Account, Event Class, Severity, Source/Dest IPs, API Operation, User, Activity, Bytes
- Sortable and filterable for deep investigation
- Export capability for offline analysis

## Threat Hunting Workflows

### Workflow 1: Identify Compromised Accounts
1. Set Cloud Provider filter
2. Review "Severity by Cloud Provider" for critical findings
3. Check "User Activity Correlation" for users with abnormal API diversity
4. Investigate suspicious users in "Event Details" table

### Workflow 2: Detect Port Scanning and Reconnaissance
1. Review "Network Security Correlation" 
2. Look for IPs with:
   - High unique port count (>10 ports)
   - High refuse count
3. Cross-reference IPs in "Top Source and Destination IPs"
4. If same IP appears in security findings, escalate investigation

### Workflow 3: Data Exfiltration Detection
1. Check "Data Transfer by Cloud" for anomalous outbound traffic
2. Filter by suspicious account using controls
3. Review "Top API Operations" for data access APIs (S3 GetObject, Blob Download)
4. Correlate with "User Activity" to identify responsible identity

### Workflow 4: Lateral Movement Detection
1. Review "Resource Access by Cloud" for accounts with many unique IPs
2. Check "Activity Timeline" for temporal correlation
3. Look for same user accessing multiple accounts
4. Cross-reference network connections between accounts

### Workflow 5: API Abuse Investigation
1. Review "Top API Operations" for unusual patterns
2. Filter by specific operation using Event Details search
3. Check "User Activity Correlation" for users making those calls
4. Correlate with network activity from same source IPs

## Field Mappings

### Common Fields (Available in All Data)
```
cloud.provider                  - Cloud platform (AWS, Azure, GCP)
cloud.account.uid               - Account identifier
cloud.region                    - Cloud region
cloud.zone                      - Availability zone
time_dt                         - Event timestamp
class_name                      - OCSF event class
category_name                   - OCSF category
severity                        - Severity label
severity_id                     - Numeric severity
status                          - Event status
```

### Network Activity Fields
```
src_endpoint.ip                 - Source IP address
dst_endpoint.ip                 - Destination IP address
src_endpoint.port               - Source port
dst_endpoint.port               - Destination port
traffic.bytes                   - Total bytes transferred
traffic.bytes_in                - Inbound bytes
traffic.bytes_out               - Outbound bytes
connection_info.direction       - Inbound/Outbound
connection_info.protocol_name   - TCP/UDP/etc
connection_info.boundary        - VPC boundary type
activity_name                   - Open/Reset/Refuse/Traffic
disposition                     - Allowed/Blocked
```

### API Activity Fields
```
api.operation                   - API operation name
api.service.name                - Service name
api.request.uid                 - Request ID
api.response.error              - Error message
actor.user.name                 - User identity
actor.user.account.uid          - User account ID
actor.session.is_mfa            - MFA status
actor.invoked_by                - Invoking service
```

### Security Finding Fields
```
type_name                       - Finding type
type_uid                        - Finding type ID
resource.type                   - Resource type
compliance.status               - Compliance status
compliance.control              - Control ID
```

## Investigation Scenarios

### Scenario 1: Brute Force Attack Detection
**Indicators:**
- Many refused connections from single IP
- Low port diversity (focused on 22, 3389, etc.)
- Multiple failed API authentications

**Investigation Steps:**
1. Filter: `activity_name:Refuse`
2. Review "Network Security Correlation"
3. Check "Top IPs" for same IP in security findings
4. Examine "Event Details" for authentication failures

### Scenario 2: Cryptocurrency Mining
**Indicators:**
- High outbound traffic to unusual IPs
- Connections to mining pools (ports 3333, 4444, 8333)
- High CPU usage (from security findings)

**Investigation Steps:**
1. Review "Data Transfer by Cloud" for anomalies
2. Filter by suspicious account
3. Check "Network Security Correlation" for mining pool IPs
4. Correlate with resource utilization alerts

### Scenario 3: Insider Threat
**Indicators:**
- User accessing resources across multiple accounts
- Unusual API operations for user's role
- Data downloads during off-hours

**Investigation Steps:**
1. Review "User Activity Correlation"
2. Look for users with high API diversity
3. Filter by user using Event Details search
4. Check "Activity Timeline" for timing patterns
5. Review "Data Transfer" for unusual volumes

### Scenario 4: Supply Chain Attack
**Indicators:**
- Unusual container image sources
- New API operations from automated systems
- Network connections to command & control IPs

**Investigation Steps:**
1. Filter: `class_name:"Network Activity"`
2. Review external connections in "Network Security Correlation"
3. Check "API Operations" for deployment-related calls
4. Correlate with security findings about container vulnerabilities

## Alert Configuration Recommendations

Configure OpenSearch alerts for:

### High-Priority Alerts
1. **Port Scanning**: Unique ports > 50 from single IP in 15 minutes
2. **Brute Force**: Refused connections > 100 from single IP in 1 hour
3. **Data Exfiltration**: Outbound bytes > 10GB from single source in 1 hour
4. **Privilege Escalation**: IAM/RBAC changes combined with API errors
5. **Lateral Movement**: Same user across 5+ accounts in 1 hour

### Medium-Priority Alerts
1. **Unusual API Activity**: Cardinality of API operations > 50 per user in 1 hour
2. **Off-Hours Activity**: API calls between 00:00-06:00 local time
3. **Failed Authentications**: Login failures > 10 per user in 15 minutes
4. **Compliance Violations**: New critical compliance findings
5. **Anomalous Traffic**: Bytes transferred > 3x baseline

## Control Group Features

The dashboard includes a hierarchical control group that provides:
- **Cascading Filters**: Selecting cloud provider auto-updates dependent filters
- **Multi-Select**: Choose multiple values per filter
- **Exists/Not Exists**: Find events with/without specific fields
- **Exclude Mode**: Invert filter logic for negative matching
- **Persistent State**: Filter selections persist across page refreshes

## Performance Optimization

- **Time Range**: Default 7 days for timeline visualizations
- **Table Limits**: 10-20 rows for tabular data
- **Top N Limits**: 15 items for ranking visualizations
- **Cardinality**: Used strategically for unique count metrics
- **Index Pattern**: Single unified pattern reduces query complexity

## Integration with Other Dashboards

This threat hunting dashboard complements:
- **Cross-Cloud Security Dashboard**: Provides context for security findings
- **Cross-Cloud Network Dashboard**: Detailed network flow analysis

**Recommended Workflow:**
1. Start with Threat Hunting Dashboard for broad investigation
2. Drill into Security Dashboard for finding details
3. Deep-dive Network Dashboard for flow analysis

## Export and Reporting

Use the Event Details saved search to:
- Export investigation results to CSV
- Create custom visualizations
- Build automated reports
- Share findings with security teams

## Index Pattern Requirements

Requires unified index pattern `f2ba75ac-1a82-4106-91b4-af36bb226463` that includes indices:
- `ocsf-1.1.0-2003-*` (API Activity)
- `ocsf-1.1.0-2004-*` (Detection Findings)
- `ocsf-1.1.0-4001-*` (Network Activity)

## Validation Status

- JSON syntax: PASS
- Object count: 11 (9 visualizations + 1 search + 1 dashboard with control group)
- Filter controls: 5 hierarchical filters
- Index pattern: Correctly referenced throughout

## Security Considerations

This dashboard accesses sensitive data including:
- User identities and authentication details
- Network traffic patterns
- Resource access logs
- Security vulnerabilities

**Access Control:** Restrict dashboard access to authorized security personnel only.