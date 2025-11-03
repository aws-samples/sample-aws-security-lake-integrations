/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

# Entra ID Diagnostics Module

This Terraform module configures Azure Entra ID (Azure Active Directory) diagnostic settings to stream audit and sign-in logs to an Event Hub for centralized security monitoring and compliance.

## Features

- **Comprehensive Log Collection**: Enables all 15 Entra ID log categories including:
  - AuditLogs: Directory changes and administrative actions
  - SignInLogs: Interactive user authentication events
  - NonInteractiveUserSignInLogs: Service account sign-ins
  - ServicePrincipalSignInLogs: Application authentication
  - ManagedIdentitySignInLogs: Azure managed identity activity
  - ProvisioningLogs: User and group provisioning events
  - ADFSSignInLogs: Active Directory Federation Services events
  - RiskyUsers and UserRiskEvents: Identity Protection alerts
  - NetworkAccessTrafficLogs: Network access patterns
  - RiskyServicePrincipals and ServicePrincipalRiskEvents: App security events
  - EnrichedOffice365AuditLogs: Office 365 audit data
  - MicrosoftGraphActivityLogs: Graph API usage
  - RemoteNetworkHealthLogs: Remote network diagnostics

- **Event Hub Integration**: Real-time log streaming to existing Event Hub infrastructure

- **Optional Storage Retention**: Long-term log storage with configurable retention policies

- **Automatic Configuration**: Applies to the default Azure AD tenant with no manual setup required

## Prerequisites

- Existing Event Hub Namespace and Event Hub
- Azure AD tenant with appropriate permissions
- Terraform >= 1.0
- Azure Provider >= 4.12
- Azure AD Provider >= 3.0

## Usage

```hcl
module "entra_id_diagnostics" {
  source = "./modules/entra-id-diagnostics"
  
  # Required parameters
  resource_group_name            = azurerm_resource_group.main.name
  location                       = azurerm_resource_group.main.location
  eventhub_authorization_rule_id = module.eventhub_namespace.root_authorization_rule_id
  eventhub_name                  = module.eventhub.eventhub_name
  
  # Optional parameters
  diagnostic_setting_name = "entra-id-to-eventhub"
  log_retention_days     = 7
  
  # Optional storage account for long-term retention
  enable_storage_retention   = false
  storage_account_name       = "entraidlogs${random_string.suffix.result}"
  storage_account_tier       = "Standard"
  storage_account_replication = "LRS"
  blob_retention_days        = 30
  container_retention_days   = 30
  
  tags = local.common_tags
}
```

## Required Permissions

The service principal or user running Terraform must have:

- `Microsoft.Insights/diagnosticSettings/write` on the Azure AD tenant
- `Contributor` or `Owner` role on the resource group (if creating storage account)
- `Azure Event Hubs Data Sender` role on the Event Hub (granted automatically by parent module)

## Log Categories

| Category | Description | Use Case |
|----------|-------------|----------|
| AuditLogs | Directory changes, user/group management | Compliance, change tracking |
| SignInLogs | Interactive user sign-ins | Security monitoring, access patterns |
| NonInteractiveUserSignInLogs | Service principal sign-ins | Application authentication tracking |
| ServicePrincipalSignInLogs | App registrations sign-ins | App security monitoring |
| ManagedIdentitySignInLogs | Azure managed identity activity | Service authentication tracking |
| ProvisioningLogs | User/group provisioning | Identity lifecycle management |
| ADFSSignInLogs | ADFS authentication events | Hybrid identity monitoring |
| RiskyUsers | Identity Protection risky users | Security threat detection |
| UserRiskEvents | User risk detections | Anomaly detection |
| NetworkAccessTrafficLogs | Network access patterns | Network security analysis |
| RiskyServicePrincipals | Risky app identities | App threat detection |
| ServicePrincipalRiskEvents | App risk detections | App security monitoring |
| EnrichedOffice365AuditLogs | Office 365 audit data | M365 compliance |
| MicrosoftGraphActivityLogs | Graph API activity | API usage tracking |
| RemoteNetworkHealthLogs | Remote network health | Network diagnostics |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| resource_group_name | Resource group name | string | n/a | yes |
| location | Azure region | string | n/a | yes |
| eventhub_authorization_rule_id | Event Hub Namespace authorization rule ID | string | n/a | yes |
| eventhub_name | Event Hub name | string | n/a | yes |
| diagnostic_setting_name | Diagnostic setting name | string | "entra-id-to-eventhub" | no |
| log_retention_days | Log retention days | number | 7 | no |
| enable_storage_retention | Enable storage account | bool | false | no |
| storage_account_name | Storage account name | string | "" | no |
| storage_account_tier | Storage tier | string | "Standard" | no |
| storage_account_replication | Replication type | string | "LRS" | no |
| blob_retention_days | Blob retention days | number | 7 | no |
| container_retention_days | Container retention days | number | 7 | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| diagnostic_setting_id | Resource ID of the diagnostic setting |
| diagnostic_setting_name | Name of the diagnostic setting |
| storage_account_id | Storage account resource ID (if enabled) |
| storage_account_name | Storage account name (if enabled) |
| storage_account_primary_blob_endpoint | Storage blob endpoint (if enabled) |
| tenant_id | Azure AD tenant ID |
| enabled_log_categories | List of enabled log categories |
| eventhub_name | Event Hub name receiving logs |

## Important Notes

1. **Tenant-Wide Configuration**: This module configures diagnostics for the entire Azure AD tenant using the default directory. It cannot be scoped to specific users or applications.

2. **Storage Account Naming**: Storage account names must be globally unique, lowercase, and alphanumeric only (3-24 characters). If not provided, you must generate a unique name.

3. **Cost Considerations**: Entra ID diagnostic logging can generate significant data volume. Consider:
   - Event Hub ingress costs
   - Storage costs (if enabled)
   - Log retention period

4. **Retention Policy**: The `log_retention_days` parameter applies to all log categories. Set to 0 for infinite retention (not recommended for cost reasons).

5. **Permissions**: Azure AD diagnostic settings require elevated permissions. Ensure the deployment identity has appropriate access.

## Example: Complete Configuration with Storage

```hcl
resource "random_string" "storage_suffix" {
  length  = 6
  special = false
  upper   = false
}

module "entra_id_diagnostics" {
  source = "./modules/entra-id-diagnostics"
  
  resource_group_name            = azurerm_resource_group.main.name
  location                       = "East US"
  eventhub_authorization_rule_id = module.eventhub_namespace.root_authorization_rule_id
  eventhub_name                  = "entra-id-logs"
  
  # Enable storage for long-term retention
  enable_storage_retention    = true
  storage_account_name        = "entraidlogs${random_string.storage_suffix.result}"
  storage_account_tier        = "Standard"
  storage_account_replication = "GRS"  # Geo-redundant for compliance
  blob_retention_days         = 90
  container_retention_days    = 90
  
  # Retention in Event Hub
  log_retention_days = 7
  
  tags = {
    Environment = "Production"
    Purpose     = "Security Monitoring"
    Compliance  = "Required"
  }
}
```

## Integration with Parent Stack

This module is designed to integrate seamlessly with the parent Microsoft Defender for Cloud terraform deployment:

```hcl
# In main.tf
module "entra_id_diagnostics" {
  source = "./modules/entra-id-diagnostics"
  
  for_each = var.enable_entra_id_logging ? toset(local.deployment_regions) : []
  
  resource_group_name            = azurerm_resource_group.main[each.key].name
  location                       = each.key
  eventhub_authorization_rule_id = module.eventhub_namespace[each.key].root_authorization_rule_id
  eventhub_name                  = module.eventhub[each.key].eventhub_name
  
  tags = local.common_tags
}
```

## Troubleshooting

### Issue: Permission Denied

**Symptom**: Error creating diagnostic settings

**Solution**: Ensure the deployment identity has `Microsoft.Insights/diagnosticSettings/write` permission on the tenant

### Issue: Storage Account Name Already Exists

**Symptom**: Storage account creation fails with name conflict

**Solution**: Provide a unique `storage_account_name` or use a random suffix generator

### Issue: Event Hub Connection Failure

**Symptom**: Logs not appearing in Event Hub

**Solution**: 
- Verify Event Hub authorization rule has Send permission
- Check Event Hub namespace firewall rules allow Azure services
- Confirm diagnostic setting is active in Azure portal

## Additional Resources

- [Azure Monitor Diagnostic Settings](https://docs.microsoft.com/azure/azure-monitor/essentials/diagnostic-settings)
- [Entra ID Audit Logs](https://docs.microsoft.com/azure/active-directory/reports-monitoring/concept-audit-logs)
- [Event Hubs Overview](https://docs.microsoft.com/azure/event-hubs/event-hubs-about)

## Version History

- **1.0.0**: Initial release with all 15 Entra ID log categories