/**
 * VNet Flow Logs Module
 * 
 * This module configures Azure VNet Flow Logs using Network Watcher
 * to capture and analyze network traffic flow data at the VNet/Subnet level.
 * 
 * Features:
 * - Network Watcher Flow Logs for VNets/Subnets
 * - Storage account integration for flow log data
 * - Optional Traffic Analytics with Log Analytics
 * - Event Hub integration via diagnostic settings
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.12"
    }
  }
}

# Network Watcher Flow Log for VNets/Subnets
# Azure provider v4.x introduces proper VNet Flow Logs support
resource "azurerm_network_watcher_flow_log" "vnet_flow_log" {
  for_each = toset(var.vnet_ids)
  
  name                 = "${basename(each.value)}-flow-log"
  network_watcher_name = var.network_watcher_name
  resource_group_name  = var.network_watcher_resource_group
  
  # In provider v4.x, use target_resource_id for VNet/Subnet flow logs
  target_resource_id = each.value
  
  # Storage account for flow log data (required)
  storage_account_id = var.storage_account_id
  enabled            = true
  
  # Retention policy for flow log data in storage
  retention_policy {
    enabled = var.retention_enabled
    days    = var.retention_days
  }
  
  # Optional Traffic Analytics integration
  dynamic "traffic_analytics" {
    for_each = var.enable_traffic_analytics && var.log_analytics_workspace_id != null ? [1] : []
    content {
      enabled               = true
      workspace_id          = var.log_analytics_workspace_id
      workspace_region      = var.log_analytics_workspace_region
      workspace_resource_id = var.log_analytics_workspace_resource_id
      interval_in_minutes   = var.traffic_analytics_interval
    }
  }
  
  # Flow log format and version
  version = var.flow_log_version
  
  tags = var.tags
}

# Diagnostic setting to forward storage account logs to Event Hub
# This captures when flow log files are written to storage
resource "azurerm_monitor_diagnostic_setting" "storage_to_eventhub" {
  count = var.enable_eventhub_export ? 1 : 0
  
  name               = "flowlogs-to-eventhub"
  target_resource_id = "${var.storage_account_id}/blobServices/default"
  
  # Event Hub configuration
  eventhub_authorization_rule_id = var.eventhub_authorization_rule_id
  eventhub_name                  = var.eventhub_name
  
  # Enable storage logs for flow log files
  enabled_log {
    category = "StorageRead"
  }
  
  enabled_log {
    category = "StorageWrite"
  }
}

# Locals for extracting information from resource IDs
locals {
  # Create a map of VNet/Subnet ID to name for outputs
  vnet_info = {
    for id in var.vnet_ids : id => basename(id)
  }
}