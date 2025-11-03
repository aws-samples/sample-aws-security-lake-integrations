# OpenSearch Dashboards for Cross-Cloud Security

This directory contains OpenSearch dashboard configurations for visualizing security findings across multiple cloud providers (AWS, Azure, GCP).

## Dashboard Files

### cross-cloud-security-dashboard.ndjson
A comprehensive dashboard for analyzing security findings across cloud environments with the following visualizations:

1. **Security Findings by Severity** - Pie chart showing distribution of findings by severity (Critical, High, Medium, Low, Informational)

2. **Findings by Cloud Provider Timeline** - Line chart tracking security findings over time across AWS, Azure, and Microsoft providers

3. **Findings by Cloud Account** - Stacked bar chart showing findings distribution across different cloud accounts, colored by severity

4. **Compliance vs Detection Findings** - Pie chart comparing compliance_finding vs detection_finding types

5. **Top Security Findings** - Horizontal bar chart displaying the top 15 most common security finding titles

6. **Findings by Region** - Bar chart showing geographic distribution of findings across cloud regions

7. **Compliance Status Overview** - Pie chart showing PASSED vs FAILED compliance status (filtered to compliance findings only)

8. **Findings by Resource Type** - Horizontal bar chart showing which AWS resource types have the most security findings

9. **High Priority Security Findings** - Timeline of critical, high, and medium severity findings requiring immediate attention

### ocsf-network.ndjson (Legacy)
Network activity visualizations - contains visualizations that may not have data in compliance-focused datasets.

## Importing Dashboards

### Method 1: OpenSearch Dashboards UI

1. Navigate to OpenSearch Dashboards
2. Go to **Management** → **Stack Management** → **Saved Objects**
3. Click **Import**
4. Select `cross-cloud-security-dashboard.ndjson`
5. Click **Import**

### Method 2: API Import

```bash
curl -X POST "https://your-opensearch-domain:9200/_dashboards/api/saved_objects/_import" \
  -H "Content-Type: application/json" \
  -H "osd-xsrf: true" \
  --data-binary @cross-cloud-security-dashboard.ndjson
```

## Data Requirements

The dashboard expects data with the following OCSF schema fields:

### Core Fields
- `severity` - Text field (Informational, Low, Medium, High, Critical)
- `severity_id` - Numeric field (0, 1, 40, 70, 90)
- `time_dt` - Date field for timestamps
- `class_name` - Finding classification (compliance_finding, detection_finding)

### Cloud Context Fields
- `cloud.account.uid` - Cloud account identifier
- `cloud.region` - Cloud region name
- `metadata.product.vendor_name` - Cloud provider (AWS, Microsoft, Azure)

### Finding Details
- `finding_info.title` - Finding title/description
- `resource.type` - Resource type affected
- `compliance.status` - Compliance check status (PASSED/FAILED)

## Filtering and Customization

### Default Filters
The dashboard includes pre-configured filters:
- Compliance Status panel: `class_name:compliance_finding`
- High Priority panel: `severity_id:(90 OR 70 OR 40)`

### Time Range
By default, visualizations use a 30-day lookback. Adjust in the time picker at the top right of the dashboard.

### Custom Filters
Add filters using the OpenSearch Dashboards query bar:
- By severity: `severity: "Critical"`
- By cloud provider: `metadata.product.vendor_name: "AWS"`
- By region: `cloud.region: "ca-central-1"`
- By account: `cloud.account.uid: "123456789012"`

## Troubleshooting

### No Data Showing
1. Verify index pattern matches your data index
2. Check time range - findings might be outside the selected period
3. Confirm field mappings match OCSF schema

### Missing Fields
If visualizations show "No results found":
1. Check if the required fields exist in your index mapping
2. Verify data has been ingested into OpenSearch
3. Refresh index patterns in **Management** → **Index Patterns**

### Performance Issues
For large datasets:
1. Reduce time range to last 7 days
2. Add more specific filters
3. Consider index lifecycle management
4. Enable index rollover for time-series data

## Related Files

- `securityHubSummary.ndjson` - AWS Security Hub specific visualizations
- `OCSF_2.0.0_objects.ndjson` - OCSF schema mappings
- `sankey.json` - Flow visualization for network traffic

## Data Sources

This dashboard is designed to work with:
- AWS Security Hub findings (OCSF compliance_finding)
- Azure Defender/Microsoft Defender findings
- Google Security Command Center findings
- Any OCSF-compliant security data

## Support

For issues or questions:
- Review OCSF schema documentation: https://schema.ocsf.io/
- Check OpenSearch Dashboards documentation
- Validate data ingestion pipeline