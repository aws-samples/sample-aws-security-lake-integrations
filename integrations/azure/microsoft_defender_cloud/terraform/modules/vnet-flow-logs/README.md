# NSG Flow Logs Module

**DEPRECATION NOTICE**: NSG Flow Logs will be retired on **September 30, 2027**. After June 30, 2025, you will no longer be able to create NEW NSG flow logs. Microsoft recommends migrating to **VNet Flow Logs** instead, which address the limitations of NSG flow logs. For more information, see the [official Azure announcement](https://azure.microsoft.com/updates/network-watcher-nsg-flow-logs-retirement/).

This module configures Azure Network Security Group (NSG) diagnostic settings to export flow logs directly to Event Hub for centralized log collection and analysis.

**Recommendation**: Consider using VNet Flow Logs (not included in this module) for new deployments.

## Features

- **NSG Lookup by Name**: Automatically looks up NSGs in a specified resource group
- **Direct Event Hub Export**: Sends flow logs directly to Event Hub without requiring storage accounts
- **NetworkSecurityGroupFlowEvent Category**: Captures network flow data for security analysis
- **Multiple NSGs Support**: Configure multiple NSGs in a single module call
- **Standalone Module**: Can be used independently or integrated with main stack

## Usage

### Basic Usage

```hcl
module "nsg_flow_logs" {
  source = "./modules/nsg-flow-logs"
  
  nsg_names                      = ["my-nsg-1", "my-nsg-2"]
  resource_group_name            = "my-resource-group"
  eventhub_name                  = "defender-security-events"
  eventhub_authorization_rule_id = "/subscriptions/.../authorizationRules/RootManageSharedAccessKey"
}
```

### Integration with Main Stack

```hcl
# In main.tf
module "nsg_flow_logs" {
  source = "./modules/nsg-flow-logs"
  
  for_each = var.enable_nsg_flow_logs ? toset(local.deployment_regions) : []
  
  nsg_names                      = var.nsg_names
  resource_group_name            = azurerm_resource_group.main[each.key].name
  eventhub_name                  = module.eventhub[each.key].eventhub_name
  eventhub_authorization_rule_id = module.eventhub_namespace[each.key].root_authorization_rule_id
  
  depends_on = [module.eventhub_namespace]
}
```

## Requirements

### Azure Subscription Prerequisites

**IMPORTANT**: This module uses NSG diagnostic settings to export flow logs, which requires specific Azure subscription capabilities.

**Known Limitation**: The `NetworkSecurityGroupFlowEvent` category via diagnostic settings may not be available in all Azure subscription types. You may encounter this error:
```
Category 'NetworkSecurityGroupFlowEvent' requires feature 'AllowNsgFlowLogging' in 'Registered' state
```

If you receive this error, the feature is not available for your subscription type. In this case:
1. Keep `enable_nsg_flowlogs = false` in your configuration
2. Use traditional NSG Flow Logs with storage accounts instead (not included in this module)
3. Contact Azure support to verify if your subscription supports NSG diagnostic settings for flow logs

**Alternative Approaches**:
1. **VNet Flow Logs (Recommended)**: Use Azure VNet Flow Logs instead of NSG Flow Logs - the modern replacement
2. **Traditional NSG Flow Logs**: Use Azure Network Watcher with storage accounts (different approach, also being deprecated)

**Migration Path**: If you're currently using this module, plan to migrate to VNet Flow Logs before June 30, 2025.

### Other Prerequisites
- Network Security Groups must exist (can be in any resource group or subscription)
- Event Hub and Event Hub Namespace must be deployed
- Appropriate permissions to configure diagnostic settings on NSGs

### Required Providers
- `azurerm` >= 3.0

## Inputs

| Name | Description | Type | Required |
|------|-------------|------|----------|
| `nsg_names` | List of NSG names to configure | `list(string)` | Yes |
| `resource_group_name` | Resource group containing the NSGs | `string` | Yes |
| `eventhub_name` | Event Hub name for log destination | `string` | Yes |
| `eventhub_authorization_rule_id` | Authorization rule resource ID | `string` | Yes |

## Outputs

| Name | Description |
|------|-------------|
| `configured_nsgs` | Information about NSGs with flow logs |
| `diagnostic_settings` | Created diagnostic settings details |
| `flow_logs_count` | Number of NSGs configured |
| `eventhub_destination` | Event Hub destination information |

## Flow Log Data

The module captures **NetworkSecurityGroupFlowEvent** logs, which include:
- Source and destination IPs
- Source and destination ports
- Protocol (TCP, UDP, ICMP)
- Traffic direction (Inbound/Outbound)
- Traffic decision (Allow/Deny)
- Flow state
- Packet and byte counts
- Timestamps

## Notes

- Flow logs are sent directly to Event Hub in real-time
- No storage account is required for this configuration
- Diagnostic settings are named `{nsg_name}-flow-logs`
- The module uses the namespace-level authorization rule for authentication

## Example: Complete Integration

```hcl
# Variables
variable "enable_nsg_flow_logs" {
  description = "Enable NSG flow logs export to Event Hub"
  type        = bool
  default     = false
}

variable "nsg_names" {
  description = "List of NSG names to monitor"
  type        = list(string)
  default     = []
}

# Module usage
module "nsg_flow_logs" {
  source = "./modules/nsg-flow-logs"
  
  count = var.enable_nsg_flow_logs ? 1 : 0
  
  nsg_names                      = var.nsg_names
  resource_group_name            = azurerm_resource_group.main.name
  eventhub_name                  = module.eventhub.eventhub_name
  eventhub_authorization_rule_id = module.eventhub_namespace.root_authorization_rule_id
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| NSG not found | Verify NSG name and resource group are correct |
| Permission denied | Ensure sufficient permissions for diagnostic settings |
| Event Hub connection fails | Verify authorization rule ID is correct |
| No flow logs appearing | Check NSG has active traffic and rules configured |