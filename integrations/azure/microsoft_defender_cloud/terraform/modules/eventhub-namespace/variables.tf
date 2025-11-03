/**
 * Event Hub Namespace Module Variables
 * 
 * This file defines all input variables for the Event Hub Namespace module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# REQUIRED VARIABLES
# ============================================================================

variable "namespace_name" {
  description = "Name of the Event Hub Namespace"
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{4,48}[a-zA-Z0-9]$", var.namespace_name))
    error_message = "Namespace name must be 6-50 characters, start with a letter, and contain only letters, numbers, and hyphens."
  }
}

variable "location" {
  description = "Azure region where the Event Hub Namespace will be created"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group where the Event Hub Namespace will be created"
  type        = string
}

# ============================================================================
# SKU AND CAPACITY CONFIGURATION
# ============================================================================

variable "sku" {
  description = "SKU of the Event Hub Namespace (Basic, Standard, Premium)"
  type        = string
  default     = "Standard"
  
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.sku)
    error_message = "SKU must be Basic, Standard, or Premium."
  }
}

variable "capacity" {
  description = "Specifies the Capacity / Throughput Units for the Event Hub Namespace"
  type        = number
  default     = 2
  
  validation {
    condition     = var.capacity >= 1 && var.capacity <= 20
    error_message = "Capacity must be between 1 and 20."
  }
}

# ============================================================================
# AUTO-SCALING CONFIGURATION
# ============================================================================

variable "auto_inflate_enabled" {
  description = "Is Auto Inflate enabled for the Event Hub Namespace?"
  type        = bool
  default     = true
}

variable "maximum_throughput_units" {
  description = "Specifies the maximum number of throughput units when Auto Inflate is Enabled"
  type        = number
  default     = 10
  
  validation {
    condition     = var.maximum_throughput_units >= 1 && var.maximum_throughput_units <= 20
    error_message = "Maximum throughput units must be between 1 and 20."
  }
}

# ============================================================================
# NETWORK CONFIGURATION
# ============================================================================

variable "public_network_access_enabled" {
  description = "Is public network access enabled for the Event Hub Namespace?"
  type        = bool
  default     = true
}

variable "minimum_tls_version" {
  description = "The minimum supported TLS version for the Event Hub Namespace"
  type        = string
  default     = "1.2"
  
  validation {
    condition     = contains(["1.0", "1.1", "1.2"], var.minimum_tls_version)
    error_message = "Minimum TLS version must be 1.0, 1.1, or 1.2."
  }
}

variable "network_rulesets" {
  description = "Network access rules for the Event Hub Namespace"
  type = object({
    default_action                 = string
    trusted_service_access_enabled = bool
    ip_rules                      = list(string)
    virtual_network_rules         = list(object({
      subnet_id                            = string
      ignore_missing_virtual_network_service_endpoint = bool
    }))
  })
  default = null
}

# ============================================================================
# PREMIUM SKU CONFIGURATION
# ============================================================================

variable "zone_redundant" {
  description = "Specifies if the Event Hub Namespace should be Zone Redundant (Premium SKU only)"
  type        = bool
  default     = false
}

# ============================================================================
# ACCESS CONTROL CONFIGURATION
# ============================================================================

variable "create_defender_access_rule" {
  description = "Create a dedicated authorization rule for Microsoft Defender (send-only access)"
  type        = bool
  default     = true
}

# ============================================================================
# MONITORING AND DIAGNOSTICS
# ============================================================================

variable "enable_diagnostic_logs" {
  description = "Enable diagnostic logs for the Event Hub Namespace"
  type        = bool
  default     = true
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID for diagnostic logs"
  type        = string
  default     = null
}

variable "diagnostic_log_categories" {
  description = "List of diagnostic log categories to enable"
  type        = list(string)
  default = [
    "ArchiveLogs",
    "OperationalLogs",
    "AutoScaleLogs",
    "KafkaCoordinatorLogs",
    "KafkaUserErrorLogs",
    "EventHubVNetConnectionEvent",
    "CustomerManagedKeyUserLogs"
  ]
}

# ============================================================================
# TAGGING
# ============================================================================

variable "tags" {
  description = "A mapping of tags to assign to the Event Hub Namespace"
  type        = map(string)
  default     = {}
}