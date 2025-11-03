/**
 * Microsoft Defender Continuous Export Module Variables
 * 
 * This file defines all input variables for the Defender continuous export module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# REQUIRED VARIABLES
# ============================================================================

variable "automation_name" {
  description = "Name of the Security Center automation (continuous export configuration)"
  type        = string
}

variable "location" {
  description = "Azure region for the automation resource"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "eventhub_id" {
  description = "Resource ID of the Event Hub to export data to"
  type        = string
}

variable "eventhub_connection_string" {
  description = "Connection string for the Event Hub (with send permissions)"
  type        = string
  sensitive   = true
}

# ============================================================================
# OPTIONAL VARIABLES
# ============================================================================

variable "tags" {
  description = "A mapping of tags to assign to the automation resource"
  type        = map(string)
  default     = {}
}