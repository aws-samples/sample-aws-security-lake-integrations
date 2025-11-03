/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Azure App Registration Module
 * 
 * This module creates an Azure AD application registration with service principal
 * and client secret for AWS integration to access Azure storage accounts.
 * 
 * Features:
 * - Azure AD Application with configurable display name
 * - Service Principal for authentication
 * - Client Secret with configurable expiration
 * - Storage Blob Data Reader role assignment
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

terraform {
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.12"
    }
  }
}

# Get current Azure AD context
data "azuread_client_config" "current" {}

# Azure AD Application for AWS integration
resource "azuread_application" "main" {
  display_name = var.application_name
  owners       = concat([data.azuread_client_config.current.object_id], var.additional_owners)
  
  tags = var.application_tags
}

# Service Principal for the application
resource "azuread_service_principal" "main" {
  client_id                    = azuread_application.main.client_id
  app_role_assignment_required = var.app_role_assignment_required
  owners                       = concat([data.azuread_client_config.current.object_id], var.additional_owners)
  
  tags = var.application_tags
}

# Client Secret for the application
resource "azuread_application_password" "main" {
  application_id    = azuread_application.main.id
  display_name      = var.secret_display_name
  end_date_relative = var.secret_expiration_hours
}

# Assign Storage Blob Data Reader role to the service principal for each storage account
resource "azurerm_role_assignment" "storage_reader" {
  for_each = toset(var.storage_account_ids)
  
  scope                = each.value
  role_definition_name = var.role_definition_name
  principal_id         = azuread_service_principal.main.object_id
  
  depends_on = [azuread_service_principal.main]
}

# Local values
locals {
  storage_account_count = length(var.storage_account_ids)
}