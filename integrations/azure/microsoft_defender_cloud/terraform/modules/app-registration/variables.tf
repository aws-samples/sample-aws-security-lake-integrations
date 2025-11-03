/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Azure App Registration Module Variables
 * 
 * This file defines input variables for the Azure App Registration module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# REQUIRED VARIABLES
# ============================================================================

variable "application_name" {
  description = "Display name for the Azure AD application"
  type        = string
}

variable "storage_account_ids" {
  description = "List of storage account resource IDs to grant access to"
  type        = list(string)
}

# ============================================================================
# OPTIONAL VARIABLES - APPLICATION CONFIGURATION
# ============================================================================

variable "application_tags" {
  description = "Tags to apply to the Azure AD application and service principal"
  type        = list(string)
  default     = []
}

variable "additional_owners" {
  description = "Additional object IDs to set as owners of the application (current user is always added)"
  type        = list(string)
  default     = []
}

variable "app_role_assignment_required" {
  description = "Whether app role assignment is required for users/groups to access this app"
  type        = bool
  default     = false
}

# ============================================================================
# OPTIONAL VARIABLES - CLIENT SECRET CONFIGURATION
# ============================================================================

variable "secret_display_name" {
  description = "Display name for the client secret"
  type        = string
  default     = "AWS Integration Secret"
}

variable "secret_expiration_hours" {
  description = "Client secret expiration in hours (e.g., '43800h' for 5 years)"
  type        = string
  default     = "43800h"  # 5 years
  
  validation {
    condition     = can(regex("^[0-9]+h$", var.secret_expiration_hours))
    error_message = "Secret expiration must be in hours format (e.g., '8760h' for 1 year, '43800h' for 5 years)."
  }
}

# ============================================================================
# OPTIONAL VARIABLES - ROLE ASSIGNMENT
# ============================================================================

variable "role_definition_name" {
  description = "Azure RBAC role to assign to the service principal on storage accounts"
  type        = string
  default     = "Storage Blob Data Reader"
  
  validation {
    condition = contains([
      "Storage Blob Data Reader",
      "Storage Blob Data Contributor",
      "Storage Account Contributor",
      "Reader"
    ], var.role_definition_name)
    error_message = "Role must be one of: Storage Blob Data Reader, Storage Blob Data Contributor, Storage Account Contributor, Reader."
  }
}