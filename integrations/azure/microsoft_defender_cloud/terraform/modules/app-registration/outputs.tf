/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Azure App Registration Module Outputs
 * 
 * This file defines the outputs returned from the Azure App Registration module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# APPLICATION OUTPUTS
# ============================================================================

output "application_id" {
  description = "The Application (Client) ID of the Azure AD application"
  value       = azuread_application.main.client_id
}

output "application_object_id" {
  description = "The Object ID of the Azure AD application"
  value       = azuread_application.main.object_id
}

output "application_name" {
  description = "The display name of the Azure AD application"
  value       = azuread_application.main.display_name
}

# ============================================================================
# SERVICE PRINCIPAL OUTPUTS
# ============================================================================

output "service_principal_id" {
  description = "The Object ID of the service principal"
  value       = azuread_service_principal.main.object_id
}

output "service_principal_application_id" {
  description = "The Application (Client) ID associated with the service principal"
  value       = azuread_service_principal.main.client_id
}

# ============================================================================
# CLIENT SECRET OUTPUTS
# ============================================================================

output "client_secret" {
  description = "The client secret value - SAVE THIS IMMEDIATELY as it cannot be retrieved later"
  value       = azuread_application_password.main.value
  sensitive   = true
}

output "client_secret_id" {
  description = "The key ID of the client secret"
  value       = azuread_application_password.main.key_id
  sensitive   = true
}

output "client_secret_expiration" {
  description = "The expiration date of the client secret"
  value       = azuread_application_password.main.end_date
}

# ============================================================================
# ROLE ASSIGNMENT OUTPUTS
# ============================================================================

output "role_assignments" {
  description = "Information about the role assignments created"
  value = {
    for id, assignment in azurerm_role_assignment.storage_reader : id => {
      id                   = assignment.id
      scope                = assignment.scope
      role_definition_name = assignment.role_definition_name
      principal_id         = assignment.principal_id
    }
  }
}

output "storage_account_count" {
  description = "Number of storage accounts the service principal has access to"
  value       = local.storage_account_count
}

# ============================================================================
# AUTHENTICATION OUTPUTS
# ============================================================================

output "authentication" {
  description = "Complete authentication details for AWS Lambda integration"
  value = {
    client_id     = azuread_application.main.client_id
    client_secret = azuread_application_password.main.value
  }
  sensitive = true
}