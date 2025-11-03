# Cross-Cloud Network Flow Dashboard

## Overview
This dashboard provides comprehensive network flow analysis across AWS and Azure cloud environments, with support for future GCP integration. It enables security teams to identify potential threats, analyze traffic patterns, and monitor bandwidth consumption across multi-cloud environments.

## Dashboard File
`cross-cloud-network-dashboard.ndjson`

## Key Security Features

### 1. Threat Detection

**Common Attackers Identification**
- Visualization: "Top Refused Connection Sources"
- Identifies source IPs with the most refused connections
- Helps detect brute force attacks, port scanning attempts, and unauthorized access
- Shows top 20 offending IPs ranked by refused connection count

**Port Scanning Detection**
- Visualization: "Port Scan Detection by Source IP"
- Uses cardinality aggregation to count unique destination ports per source IP
- High port diversity from a single source indicates scanning activity
- Shows top 15 sources ranked by number of unique ports accessed

### 2. Traffic Analysis

**Inbound/Outbound Connection Tracking**
- Top Inbound Connection Sources: Identifies external systems connecting to your infrastructure
- Top Outbound Connection Destinations: Tracks internal systems connecting externally
- Both show top 15 IPs with connection counts

**Most Accessed Ports**
- Shows top 20 destination ports by connection count
- Helps identify service usage patterns
- Detects unusual port activity

### 3. Bandwidth Monitoring

**Bytes Transferred Analysis**
- Bytes Transferred by Direction: Pie chart showing inbound vs outbound traffic volume
- Network Traffic Over Time: Timeline showing bytes transferred by direction
- Top Bandwidth Consumers: Source IPs ranked by total bytes transferred

**Traffic Distribution**
- Traffic by Cloud Provider: Bytes transferred per cloud platform (AWS, Azure, GCP)
- Connection Count Over Time: Timeline of connections per cloud provider

### 4. Protocol and Activity Monitoring

**Protocol Analysis**
- Protocols by Cloud Provider: Stacked bar showing protocol distribution (TCP, UDP, etc.) per cloud
- Traffic by Protocol and Cloud: Bytes transferred by protocol and cloud provider

**Activity Types**
- Connection Activity Types: Donut chart showing Open, Reset, Refuse, Traffic, Unknown activities
- Traffic Direction Distribution: Inbound vs Outbound connection counts
- Traffic Boundary Distribution: Same VPC, Internet Gateway, Unknown boundaries

## Dashboard Layout

### Top Row (3 panels)
1. Top Refused Connection Sources (Horizontal Bar) - Security threat identification
2. Port Scan Detection by Source IP (Bar Chart) - Scanning activity detection
3. Most Accessed Destination Ports (Horizontal Bar) - Service usage patterns

### Middle Rows (4 panels)
4. Top Inbound Connection Sources (Horizontal Bar) - External access tracking
5. Top Outbound Connection Destinations (Horizontal Bar) - Internal system activity
6. Network Traffic Over Time (Line Chart) - Bandwidth trends by direction
7. Top Bandwidth Consumers (Horizontal Bar) - High-volume traffic sources

### Bottom Row (4 panels)
8. Connection Activity Types (Donut) - Activity distribution
9. Traffic Direction Distribution (Donut) - Inbound/Outbound counts
10. Bytes Transferred by Direction (Pie) - Bandwidth by direction
11. Traffic by Cloud Provider (Pie) - Cross-cloud bandwidth distribution

## Field Mappings

All visualizations use the following OCSF 1.1.0 network activity fields:

```
src_endpoint.ip                    - Source IP address [aggregatable]
dst_endpoint.ip                    - Destination IP address [aggregatable]
src_endpoint.port                  - Source port number [aggregatable]
dst_endpoint.port                  - Destination port number [aggregatable]
traffic.bytes                      - Total bytes transferred [aggregatable, numeric]
traffic.bytes_in                   - Bytes received [numeric]
traffic.bytes_out                  - Bytes sent [numeric]
traffic.packets                    - Total packets [numeric]
connection_info.direction          - Inbound/Outbound [aggregatable]
connection_info.protocol_name      - TCP/UDP/etc [aggregatable]
connection_info.boundary           - Same VPC, Internet Gateway, etc [aggregatable]
activity_name                      - Open, Reset, Refuse, Traffic, Unknown [aggregatable]
cloud.provider                     - AWS, Azure, GCP [aggregatable]
time_dt                           - Flow timestamp [date, aggregatable]
```

**Note:** All fields use proper nested object notation (e.g., `src_endpoint.ip` not `src_endpoint_ip`)

## Use Cases

### Security Investigation
1. **Identify Attackers**: Check "Top Refused Connection Sources" for IPs with multiple failed access attempts
2. **Detect Port Scans**: Review "Port Scan Detection" for sources accessing many different ports
3. **Monitor Suspicious Ports**: Check "Most Accessed Ports" for unusual port activity

### Traffic Analysis
1. **Bandwidth Monitoring**: Use timeline and pie charts to track data transfer patterns
2. **Connection Patterns**: Analyze inbound/outbound connections for anomalies
3. **Service Usage**: Review port distribution to understand service access patterns

### Cross-Cloud Visibility
1. **Multi-Cloud Comparison**: Compare traffic patterns across AWS and Azure
2. **Protocol Distribution**: Understand protocol usage per cloud provider
3. **Boundary Analysis**: Track traffic between VPCs, internet gateways, etc.

## Data Sources

This dashboard aggregates network flow logs from:
- **AWS VPC Flow Logs**: Captured via Amazon VPC Flow Logs
- **Azure Network Watcher**: Flow logs from Azure Network Security Groups
- **GCP VPC Flow Logs**: (Future integration)

All data is normalized to OCSF 1.1.0 Network Activity (class_uid: 4001) format.

## Alert Recommendations

Configure OpenSearch alerts for:
1. **Refused Connections**: Alert when source IP exceeds 100 refused connections in 1 hour
2. **Port Scanning**: Alert when source IP accesses > 50 unique ports in 10 minutes
3. **Bandwidth Spikes**: Alert when bytes transferred exceeds normal baseline by 300%
4. **Unusual Ports**: Alert on connections to non-standard ports (not 22, 80, 443, etc.)

## Integration with Security Dashboard

This network flow dashboard complements the `cross-cloud-security-dashboard` by:
- Providing network-level context for security findings
- Identifying source IPs that may correlate with security incidents
- Tracking lateral movement and data exfiltration patterns
- Monitoring network boundaries and exposure

## Performance Considerations

- Default time ranges: Last 24 hours for timelines
- Top N limits: 15-20 items for most visualizations
- Aggregation optimization: Uses appropriate field types without forcing fielddata

## Index Pattern
Requires index pattern: `64fcc7af-17de-4e14-812a-0d76f1d62843` (Network Activity data)

## Import Instructions

```bash
# Method 1: OpenSearch Dashboards UI
Navigate to: Management -> Stack Management -> Saved Objects -> Import
Select: cross-cloud-network-dashboard.ndjson

# Method 2: API Import
curl -X POST "https://OPENSEARCH_URL/_dashboards/api/saved_objects/_import" \
  -H "Content-Type: application/ndjson" \
  -H "osd-xsrf: true" \
  --data-binary @saved_objects/cross-cloud-network-dashboard.ndjson
```

## Validation

The dashboard has been validated for:
- JSON syntax correctness
- Proper index pattern references
- Aggregatable field usage
- Cross-cloud data compatibility