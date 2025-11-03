/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Event Grid Subscription Module Variables
 * 
 * This file defines input variables for the Event Grid subscription module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# REQUIRED VARIABLES
# ============================================================================

variable "resource_group_name" {
  description = "Name of the resource group where Event Grid resources will be created"
  type        = string
}

variable "location" {
  description = "Azure region where the Event Grid system topic will be created"
  type        = string
}

variable "storage_account_id" {
  description = "Resource ID of the storage account to monitor for blob events"
  type        = string
}

variable "eventhub_id" {
  description = "Resource ID of the Event Hub endpoint to send events to"
  type        = string
}

# ============================================================================
# OPTIONAL VARIABLES - NAMING
# ============================================================================

variable "system_topic_name" {
  description = "Name for the Event Grid system topic"
  type        = string
  default     = "flowlogs-storage-events"
}

variable "subscription_name" {
  description = "Name for the Event Grid subscription"
  type        = string
  default     = "blob-created-to-eventhub"
}

# ============================================================================
# OPTIONAL VARIABLES - FILTERING
# ============================================================================

variable "enable_advanced_filtering" {
  description = "Enable advanced filtering on event properties"
  type        = bool
  default     = false
}

variable "blob_type_filters" {
  description = "List of blob path prefixes to filter (e.g., ['/blobServices/default/containers/insights-logs-'])"
  type        = list(string)
  default     = []
}

variable "enable_subject_filtering" {
  description = "Enable subject-based filtering"
  type        = bool
  default     = false
}

variable "subject_begins_with" {
  description = "Subject filter - begins with pattern"
  type        = string
  default     = ""
}

variable "subject_ends_with" {
  description = "Subject filter - ends with pattern"
  type        = string
  default     = ""
}

variable "subject_case_sensitive" {
  description = "Whether subject filtering is case sensitive"
  type        = bool
  default     = false
}

# ============================================================================
# OPTIONAL VARIABLES - RETRY AND DELIVERY
# ============================================================================

variable "max_delivery_attempts" {
  description = "Maximum number of delivery attempts for failed events"
  type        = number
  default     = 30
  
  validation {
    condition     = var.max_delivery_attempts >= 1 && var.max_delivery_attempts <= 30
    error_message = "Max delivery attempts must be between 1 and 30."
  }
}

variable "event_time_to_live_minutes" {
  description = "Event time-to-live in minutes (1440 = 24 hours)"
  type        = number
  default     = 1440
  
  validation {
    condition     = var.event_time_to_live_minutes >= 1 && var.event_time_to_live_minutes <= 1440
    error_message = "Event TTL must be between 1 and 1440 minutes."
  }
}

# ============================================================================
# OPTIONAL VARIABLES - DEAD LETTER
# ============================================================================

variable "dead_letter_storage_account_id" {
  description = "Storage account ID for dead letter destination (null to disable)"
  type        = string
  default     = null
}

variable "dead_letter_container_name" {
  description = "Container name for dead letter events"
  type        = string
  default     = "eventgrid-deadletter"
}

# ============================================================================
# OPTIONAL VARIABLES - TAGS
# ============================================================================

variable "tags" {
  description = "Tags to apply to Event Grid resources"
  type        = map(string)
  default     = {}
}