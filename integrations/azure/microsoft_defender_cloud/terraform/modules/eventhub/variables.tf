/**
 * Event Hub Module Variables
 * 
 * This file defines all input variables for the Event Hub module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# REQUIRED VARIABLES
# ============================================================================

variable "eventhub_name" {
  description = "Name of the Event Hub"
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-]{0,48}[a-zA-Z0-9]$", var.eventhub_name))
    error_message = "Event Hub name must be 1-50 characters, start with a letter, and contain only letters, numbers, and hyphens."
  }
}

variable "namespace_name" {
  description = "Name of the Event Hub Namespace"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "eventhub_tier" {
  description = "Event Hub Namespace SKU tier (Basic, Standard, Premium)"
  type        = string
  default     = "Basic"
}

# ============================================================================
# EVENT HUB CONFIGURATION
# ============================================================================

variable "partition_count" {
  description = "Number of partitions for the Event Hub (2-32)"
  type        = number
  default     = 4
  
  validation {
    condition     = var.partition_count >= 2 && var.partition_count <= 32
    error_message = "Partition count must be between 2 and 32."
  }
}

variable "message_retention" {
  description = "Message retention period in days (1-7 for Standard, 1-90 for Premium)"
  type        = number
  default     = 1
  
  validation {
    condition     = var.message_retention >= 1 && var.message_retention <= 90
    error_message = "Message retention must be between 1 and 90 days."
  }
}

variable "status" {
  description = "Status of the Event Hub (Active, Disabled, SendDisabled)"
  type        = string
  default     = "Active"
  
  validation {
    condition     = contains(["Active", "Disabled", "SendDisabled"], var.status)
    error_message = "Status must be Active, Disabled, or SendDisabled."
  }
}

# ============================================================================
# CAPTURE CONFIGURATION (DISABLED BY DEFAULT FOR STREAM-THROUGH)
# ============================================================================

variable "capture_enabled" {
  description = "Enable Event Hub Capture feature"
  type        = bool
  default     = false
}

variable "capture_encoding" {
  description = "Encoding format for captured data (Avro, AvroDeflate)"
  type        = string
  default     = "Avro"
  
  validation {
    condition     = contains(["Avro", "AvroDeflate"], var.capture_encoding)
    error_message = "Capture encoding must be Avro or AvroDeflate."
  }
}

variable "capture_interval_seconds" {
  description = "Time window for capture in seconds (60-900)"
  type        = number
  default     = 300
  
  validation {
    condition     = var.capture_interval_seconds >= 60 && var.capture_interval_seconds <= 900
    error_message = "Capture interval must be between 60 and 900 seconds."
  }
}

variable "capture_size_limit_bytes" {
  description = "Size window for capture in bytes (10485760-524288000)"
  type        = number
  default     = 314572800
  
  validation {
    condition     = var.capture_size_limit_bytes >= 10485760 && var.capture_size_limit_bytes <= 524288000
    error_message = "Capture size limit must be between 10485760 and 524288000 bytes."
  }
}

variable "capture_skip_empty_archives" {
  description = "Skip creating empty archive files"
  type        = bool
  default     = true
}

variable "capture_name_format" {
  description = "Archive name format for captured data"
  type        = string
  default     = "{Namespace}/{EventHub}/{PartitionId}/{Year}/{Month}/{Day}/{Hour}/{Minute}/{Second}"
}

variable "capture_container_name" {
  description = "Storage container name for captured data"
  type        = string
  default     = null
}

variable "capture_storage_account_id" {
  description = "Storage account ID for captured data"
  type        = string
  default     = null
}

# ============================================================================
# CONSUMER GROUPS CONFIGURATION
# ============================================================================

variable "consumer_groups" {
  description = "List of consumer group names to create (in addition to $Default)"
  type        = list(string)
  default     = ["external-systems", "analytics", "monitoring"]
  
  validation {
    condition = alltrue([
      for group in var.consumer_groups : can(regex("^[a-zA-Z][a-zA-Z0-9-_]{0,49}$", group))
    ])
    error_message = "Consumer group names must be 1-50 characters, start with a letter, and contain only letters, numbers, hyphens, and underscores."
  }
}

# ============================================================================
# AUTHORIZATION RULES CONFIGURATION
# ============================================================================

variable "create_listen_only_rule" {
  description = "Create an authorization rule with listen-only permissions"
  type        = bool
  default     = true
}

variable "create_send_only_rule" {
  description = "Create an authorization rule with send-only permissions"
  type        = bool
  default     = true
}

variable "create_full_access_rule" {
  description = "Create an authorization rule with full access permissions"
  type        = bool
  default     = false
}

# ============================================================================
# MICROSOFT DEFENDER RBAC CONFIGURATION
# ============================================================================

variable "enable_defender_rbac" {
  description = "Enable RBAC role assignment for Microsoft Defender service principal"
  type        = bool
  default     = true
}

# ============================================================================
# TAGGING
# ============================================================================

variable "tags" {
  description = "A mapping of tags to assign to the Event Hub"
  type        = map(string)
  default     = {}
}