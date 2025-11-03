/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Entra ID Diagnostics Module Variables
 * 
 * This file defines all input variables for the Entra ID diagnostic settings module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# GENERAL CONFIGURATION
# ============================================================================

variable "resource_group_name" {
  description = "Name of the resource group for the storage account"
  type        = string
}

variable "location" {
  description = "Azure region for the storage account"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# ============================================================================
# DIAGNOSTIC SETTINGS CONFIGURATION
# ============================================================================

variable "diagnostic_setting_name" {
  description = "Name of the Entra ID diagnostic setting"
  type        = string
  default     = "entra-id-to-eventhub"
}

variable "eventhub_authorization_rule_id" {
  description = "Resource ID of the Event Hub Namespace authorization rule"
  type        = string
}

variable "eventhub_name" {
  description = "Name of the Event Hub to send logs to"
  type        = string
}

variable "log_retention_days" {
  description = "Number of days to retain logs (0 = infinite)"
  type        = number
  default     = 7
  
  validation {
    condition     = var.log_retention_days >= 0 && var.log_retention_days <= 365
    error_message = "Log retention days must be between 0 and 365."
  }
}

# ============================================================================
# STORAGE ACCOUNT CONFIGURATION
# ============================================================================

variable "enable_storage_retention" {
  description = "Enable storage account for long-term log retention"
  type        = bool
  default     = false
}

variable "storage_account_name" {
  description = "Name of the storage account for log retention (must be globally unique)"
  type        = string
  default     = ""
}

variable "storage_account_tier" {
  description = "Storage account tier (Standard or Premium)"
  type        = string
  default     = "Standard"
  
  validation {
    condition     = contains(["Standard", "Premium"], var.storage_account_tier)
    error_message = "Storage account tier must be Standard or Premium."
  }
}

variable "storage_account_replication" {
  description = "Storage account replication type (LRS, GRS, RAGRS, ZRS, GZRS, RAGZRS)"
  type        = string
  default     = "LRS"
  
  validation {
    condition     = contains(["LRS", "GRS", "RAGRS", "ZRS", "GZRS", "RAGZRS"], var.storage_account_replication)
    error_message = "Storage account replication must be one of: LRS, GRS, RAGRS, ZRS, GZRS, RAGZRS."
  }
}

variable "blob_retention_days" {
  description = "Number of days to retain deleted blobs"
  type        = number
  default     = 7
  
  validation {
    condition     = var.blob_retention_days >= 1 && var.blob_retention_days <= 365
    error_message = "Blob retention days must be between 1 and 365."
  }
}

variable "container_retention_days" {
  description = "Number of days to retain deleted containers"
  type        = number
  default     = 7
  
  validation {
    condition     = var.container_retention_days >= 1 && var.container_retention_days <= 365
    error_message = "Container retention days must be between 1 and 365."
  }
}