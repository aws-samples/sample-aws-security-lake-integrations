/**
 * VNet Flow Logs Module Variables
 * 
 * This file defines all input variables for the VNet flow logs module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# REQUIRED VARIABLES
# ============================================================================

variable "vnet_ids" {
  description = "List of VNet or Subnet resource IDs to configure flow logs for. Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{name} or .../subnets/{name}"
  type        = list(string)
  
  validation {
    condition     = length(var.vnet_ids) > 0
    error_message = "At least one VNet or Subnet resource ID must be provided."
  }
}

variable "network_watcher_name" {
  description = "Name of the Network Watcher (e.g., NetworkWatcher_canadacentral)"
  type        = string
}

variable "network_watcher_resource_group" {
  description = "Resource group containing the Network Watcher (e.g., NetworkWatcherRG)"
  type        = string
}

variable "storage_account_id" {
  description = "Resource ID of the storage account for flow log data"
  type        = string
}

# ============================================================================
# EVENT HUB CONFIGURATION
# ============================================================================

variable "eventhub_name" {
  description = "Name of the Event Hub to send flow logs to"
  type        = string
}

variable "eventhub_authorization_rule_id" {
  description = "Resource ID of the Event Hub authorization rule"
  type        = string
}

variable "enable_eventhub_export" {
  description = "Enable exporting flow logs to Event Hub via storage account diagnostic settings"
  type        = bool
  default     = true
}

# ============================================================================
# OPTIONAL VARIABLES
# ============================================================================

variable "retention_enabled" {
  description = "Enable retention policy for flow logs in storage account"
  type        = bool
  default     = true
}

variable "retention_days" {
  description = "Number of days to retain flow logs in storage account (0 = infinite)"
  type        = number
  default     = 7
  
  validation {
    condition     = var.retention_days >= 0 && var.retention_days <= 365
    error_message = "Retention days must be between 0 and 365."
  }
}

variable "flow_log_version" {
  description = "Flow log format version (1 or 2)"
  type        = number
  default     = 2
  
  validation {
    condition     = contains([1, 2], var.flow_log_version)
    error_message = "Flow log version must be 1 or 2."
  }
}

variable "enable_traffic_analytics" {
  description = "Enable Traffic Analytics with Log Analytics workspace"
  type        = bool
  default     = false
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace GUID for Traffic Analytics"
  type        = string
  default     = null
}

variable "log_analytics_workspace_region" {
  description = "Log Analytics workspace region for Traffic Analytics"
  type        = string
  default     = null
}

variable "log_analytics_workspace_resource_id" {
  description = "Log Analytics workspace resource ID for Traffic Analytics"
  type        = string
  default     = null
}

variable "traffic_analytics_interval" {
  description = "Traffic Analytics processing interval in minutes (10 or 60)"
  type        = number
  default     = 60
  
  validation {
    condition     = contains([10, 60], var.traffic_analytics_interval)
    error_message = "Traffic Analytics interval must be 10 or 60 minutes."
  }
}

variable "tags" {
  description = "A mapping of tags to assign to the flow log resources"
  type        = map(string)
  default     = {}
}