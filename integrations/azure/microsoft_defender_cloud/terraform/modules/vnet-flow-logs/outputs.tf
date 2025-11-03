/**
 * VNet Flow Logs Module Outputs
 * 
 * This file defines the outputs that will be returned from the VNet flow logs module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# VNET FLOW LOGS OUTPUTS
# ============================================================================

output "configured_vnets" {
  description = "Information about VNets/Subnets with flow logs configured"
  value = {
    for id in var.vnet_ids : id => {
      id   = id
      name = local.vnet_info[id]
    }
  }
}

output "flow_log_resources" {
  description = "Information about created Network Watcher flow log resources"
  value = {
    for id, flow_log in azurerm_network_watcher_flow_log.vnet_flow_log : id => {
      id                  = flow_log.id
      name                = flow_log.name
      target_resource_id  = flow_log.target_resource_id
      storage_account_id  = flow_log.storage_account_id
      enabled             = flow_log.enabled
    }
  }
}

output "flow_logs_count" {
  description = "Number of VNets/Subnets configured with flow logs"
  value       = length(var.vnet_ids)
}

output "storage_account_destination" {
  description = "Storage account used for flow log data"
  value       = var.storage_account_id
}

output "eventhub_destination" {
  description = "Event Hub destination for flow logs"
  value = var.enable_eventhub_export ? {
    eventhub_name                  = var.eventhub_name
    eventhub_authorization_rule_id = var.eventhub_authorization_rule_id
  } : null
  sensitive = true
}

output "traffic_analytics_enabled" {
  description = "Whether Traffic Analytics is enabled"
  value       = var.enable_traffic_analytics
}