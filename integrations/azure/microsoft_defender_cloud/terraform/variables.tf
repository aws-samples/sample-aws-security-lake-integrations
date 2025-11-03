/**
 * Microsoft Defender for Cloud - Event Hub Integration Variables
 * 
 * This file defines all configurable parameters for the Terraform deployment.
 * All variables are designed to be 100% configurable via tfvars files.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# GENERAL CONFIGURATION
# ============================================================================

variable "subscription_id" {
  description = "Azure Subscription ID where resources will be deployed"
  type        = string
  
  validation {
    condition     = can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.subscription_id))
    error_message = "Subscription ID must be a valid UUID format (e.g., 12345678-1234-1234-1234-123456789012)."
  }
}

variable "project_name" {
  description = "Name of the project (used in resource naming)"
  type        = string
  default     = "mdc-integration"
  
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "owner" {
  description = "Owner of the resources (for tagging)"
  type        = string
  default     = "SecureSight-Team"
}

variable "cost_center" {
  description = "Cost center for billing (for tagging)"
  type        = string
  default     = "Security-Operations"
}

variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# ============================================================================
# REGION AND DEPLOYMENT CONFIGURATION
# ============================================================================

variable "primary_region" {
  description = "Primary Azure region for deployment"
  type        = string
  default     = "East US"
  
  validation {
    condition = contains([
      "East US", "East US 2", "West US", "West US 2", "West US 3",
      "Central US", "North Central US", "South Central US",
      "Canada Central", "Canada East",
      "UK South", "UK West", "West Europe", "North Europe",
      "Australia East", "Australia Southeast",
      "Japan East", "Japan West", "Southeast Asia", "East Asia"
    ], var.primary_region)
    error_message = "Primary region must be a valid Azure region."
  }
}

variable "multi_region_deployment" {
  description = "Enable multi-region deployment"
  type        = bool
  default     = false
}

variable "deployment_regions" {
  description = "List of Azure regions for multi-region deployment"
  type        = list(string)
  default     = ["East US", "West US 2"]
  
  validation {
    condition     = length(var.deployment_regions) <= 5
    error_message = "Maximum of 5 regions supported for deployment."
  }
}

# ============================================================================
# RESOURCE GROUP CONFIGURATION
# ============================================================================

variable "prevent_resource_group_deletion" {
  description = "Prevent deletion of resource group if it contains resources"
  type        = bool
  default     = true
}

# ============================================================================
# EVENT HUB NAMESPACE CONFIGURATION
# ============================================================================

variable "eventhub_sku" {
  description = "Event Hub Namespace SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Standard"
  
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.eventhub_sku)
    error_message = "Event Hub SKU must be Basic, Standard, or Premium."
  }
}

variable "eventhub_capacity" {
  description = "Event Hub Namespace throughput units (1-20 for Standard, 1-10 for Premium)"
  type        = number
  default     = 2
  
  validation {
    condition     = var.eventhub_capacity >= 1 && var.eventhub_capacity <= 20
    error_message = "Event Hub capacity must be between 1 and 20."
  }
}

variable "auto_inflate_enabled" {
  description = "Enable auto-inflate for Event Hub Namespace"
  type        = bool
  default     = true
}

variable "maximum_throughput_units" {
  description = "Maximum throughput units when auto-inflate is enabled"
  type        = number
  default     = 10
  
  validation {
    condition     = var.maximum_throughput_units >= 1 && var.maximum_throughput_units <= 20
    error_message = "Maximum throughput units must be between 1 and 20."
  }
}

variable "public_network_access_enabled" {
  description = "Enable public network access to Event Hub Namespace"
  type        = bool
  default     = true
}

variable "minimum_tls_version" {
  description = "Minimum TLS version for Event Hub Namespace"
  type        = string
  default     = "1.2"
  
  validation {
    condition     = contains(["1.0", "1.1", "1.2"], var.minimum_tls_version)
    error_message = "Minimum TLS version must be 1.0, 1.1, or 1.2."
  }
}

variable "network_rulesets" {
  description = "Network access rules for Event Hub Namespace"
  type = object({
    default_action                 = string
    trusted_service_access_enabled = bool
    ip_rules                      = list(string)
    virtual_network_rules         = list(object({
      subnet_id                            = string
      ignore_missing_virtual_network_service_endpoint = bool
    }))
  })
  default = {
    default_action                 = "Allow"
    trusted_service_access_enabled = true
    ip_rules                      = []
    virtual_network_rules         = []
  }
}

# ============================================================================
# MICROSOFT DEFENDER CONTINUOUS EXPORT CONFIGURATION
# ============================================================================

variable "enable_defender_export" {
  description = "Enable Microsoft Defender for Cloud continuous export to Event Hub. When enabled, also creates RBAC role for 'Windows Azure Security Resource Provider' service principal."
  type        = bool
  default     = true
}

# ============================================================================
# EVENT HUB CONFIGURATION
# ============================================================================

variable "eventhub_name" {
  description = "Name of the Event Hub"
  type        = string
  default     = "defender-security-events"
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9-]+$", var.eventhub_name))
    error_message = "Event Hub name must contain only letters, numbers, and hyphens."
  }
}

variable "eventhub_partition_count" {
  description = "Number of partitions for the Event Hub (2-32)"
  type        = number
  default     = 4
  
  validation {
    condition     = var.eventhub_partition_count >= 2 && var.eventhub_partition_count <= 32
    error_message = "Event Hub partition count must be between 2 and 32."
  }
}

variable "eventhub_message_retention" {
  description = "Message retention in days for the Event Hub (1-7)"
  type        = number
  default     = 1
  
  validation {
    condition     = var.eventhub_message_retention >= 1 && var.eventhub_message_retention <= 7
    error_message = "Event Hub message retention must be between 1 and 7 days."
  }
}

# ============================================================================
# IAM/RBAC CONFIGURATION
# ============================================================================

variable "create_service_principal" {
  description = "Create a service principal for Microsoft Defender access"
  type        = bool
  default     = true
}

variable "service_principal_owners" {
  description = "List of object IDs to set as owners of the service principal"
  type        = list(string)
  default     = []
}

variable "defender_data_contributor_enabled" {
  description = "Enable Azure Event Hubs Data Sender role for Microsoft Defender"
  type        = bool
  default     = true
}

variable "custom_role_assignments" {
  description = "Custom role assignments for the service principal"
  type = list(object({
    role_definition_name = string
    scope               = string
  }))
  default = []
}

# ============================================================================
# MONITORING CONFIGURATION
# ============================================================================

variable "enable_monitoring" {
  description = "Enable Azure Monitor integration and alerting"
  type        = bool
  default     = true
}

variable "log_analytics_sku" {
  description = "Log Analytics Workspace SKU"
  type        = string
  default     = "PerGB2018"
  
  validation {
    condition     = contains(["Free", "PerNode", "PerGB2018", "Standalone"], var.log_analytics_sku)
    error_message = "Log Analytics SKU must be Free, PerNode, PerGB2018, or Standalone."
  }
}

variable "log_analytics_retention_days" {
  description = "Log Analytics data retention in days (30-730)"
  type        = number
  default     = 30
  
  validation {
    condition     = var.log_analytics_retention_days >= 30 && var.log_analytics_retention_days <= 730
    error_message = "Log Analytics retention must be between 30 and 730 days."
  }
}

variable "diagnostic_logs_enabled" {
  description = "Enable diagnostic logs for Event Hub"
  type        = bool
  default     = true
}

variable "metric_alerts_enabled" {
  description = "Enable metric alerts for Event Hub"
  type        = bool
  default     = true
}

variable "alert_notification_emails" {
  description = "List of email addresses for alert notifications"
  type        = list(string)
  default     = []
  
  validation {
    condition = alltrue([
      for email in var.alert_notification_emails : can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", email))
    ])
    error_message = "All email addresses must be valid."
  }
}

variable "alert_webhook_urls" {
  description = "List of webhook URLs for alert notifications"
  type        = list(string)
  default     = []
}

# Alert thresholds
variable "incoming_messages_threshold" {
  description = "Threshold for incoming messages alert (per minute)"
  type        = number
  default     = 1000
}

variable "outgoing_messages_threshold" {
  description = "Threshold for outgoing messages alert (per minute)"
  type        = number
  default     = 1000
}

variable "throttled_requests_threshold" {
  description = "Threshold for throttled requests alert (per minute)"
  type        = number
  default     = 10
}

# ============================================================================
# VNET FLOW LOGS CONFIGURATION
# ============================================================================

variable "enable_vnet_flowlogs" {
  description = "Enable VNet Flow Logs with Network Watcher"
  type        = bool
  default     = false
}

variable "use_existing_network_watcher" {
  description = "Use existing Network Watcher instead of creating a new one (Azure only allows 1 per subscription per region)"
  type        = bool
  default     = true
}

variable "existing_network_watcher_name" {
  description = "Name of existing Network Watcher to use (if use_existing_network_watcher is true). Leave null to auto-detect."
  type        = string
  default     = null
}

variable "existing_network_watcher_resource_group" {
  description = "Resource group name of existing Network Watcher (if use_existing_network_watcher is true). Defaults to 'NetworkWatcherRG'."
  type        = string
  default     = "NetworkWatcherRG"
}

variable "vnet_ids" {
  description = "List of VNet or Subnet resource IDs to configure flow logs for. Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{name} or .../subnets/{name}"
  type        = list(string)
  default     = []
}

variable "flow_logs_storage_account_name" {
  description = "Name for the storage account to store VNet flow logs (auto-generated if not provided)"
  type        = string
  default     = null
}

variable "flow_logs_storage_account_tier" {
  description = "Storage account tier for flow logs (Standard or Premium)"
  type        = string
  default     = "Standard"
  
  validation {
    condition     = contains(["Standard", "Premium"], var.flow_logs_storage_account_tier)
    error_message = "Storage account tier must be Standard or Premium."
  }
}

variable "flow_logs_storage_account_replication" {
  description = "Storage account replication type for flow logs (LRS, GRS, RAGRS, ZRS, GZRS, RAGZRS)"
  type        = string
  default     = "LRS"
  
  validation {
    condition     = contains(["LRS", "GRS", "RAGRS", "ZRS", "GZRS", "RAGZRS"], var.flow_logs_storage_account_replication)
    error_message = "Storage account replication must be one of: LRS, GRS, RAGRS, ZRS, GZRS, RAGZRS."
  }
}

variable "flow_logs_retention_enabled" {
  description = "Enable retention policy for flow logs in storage account"
  type        = bool
  default     = true
}

variable "flow_logs_retention_days" {
  description = "Number of days to retain flow logs in storage account (0 = infinite)"
  type        = number
  default     = 7
  
  validation {
    condition     = var.flow_logs_retention_days >= 0 && var.flow_logs_retention_days <= 365
    error_message = "Flow logs retention days must be between 0 and 365."
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
  description = "Enable Traffic Analytics with Log Analytics workspace for VNet Flow Logs"
  type        = bool
  default     = false
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

variable "enable_flowlogs_to_eventhub" {
  description = "Enable exporting flow logs to Event Hub via storage account diagnostic settings"
  type        = bool
  default     = true
}

# ============================================================================
# ENTRA ID DIAGNOSTICS CONFIGURATION
# ============================================================================

variable "enable_entra_id_logging" {
  description = "Enable Entra ID (Azure AD) diagnostic logging to Event Hub"
  type        = bool
  default     = false
}

variable "entra_id_log_retention_days" {
  description = "Number of days to retain Entra ID logs (0 = infinite)"
  type        = number
  default     = 7
  
  validation {
    condition     = var.entra_id_log_retention_days >= 0 && var.entra_id_log_retention_days <= 365
    error_message = "Entra ID log retention days must be between 0 and 365."
  }
}

variable "entra_id_enable_storage_retention" {
  description = "Enable storage account for long-term Entra ID log retention"
  type        = bool
  default     = false
}

variable "entra_id_storage_account_name" {
  description = "Name for Entra ID log storage account (must be globally unique, lowercase, alphanumeric only)"
  type        = string
  default     = null
}

