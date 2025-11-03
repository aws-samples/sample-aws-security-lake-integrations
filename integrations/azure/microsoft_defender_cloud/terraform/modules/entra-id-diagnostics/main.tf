/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Entra ID Diagnostics Module
 * 
 * This module configures Azure Entra ID (Azure Active Directory) diagnostic settings
 * to stream audit logs and sign-in logs to an Event Hub for security monitoring and compliance.
 * 
 * Features:
 * - Diagnostic settings for Entra ID default directory
 * - All log categories enabled (AuditLogs, SignInLogs, etc.)
 * - Integration with existing Event Hub infrastructure
 * - Optional storage account for long-term log retention
 * - RBAC permissions for Event Hub data sender role
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.12"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }
}

# Get current Azure AD tenant information
data "azuread_client_config" "current" {}

# Storage Account for Entra ID Diagnostic Logs (optional long-term retention)
# Only created if enable_storage_retention is true
resource "azurerm_storage_account" "entra_logs" {
  count = var.enable_storage_retention ? 1 : 0
  
  name                     = var.storage_account_name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = var.storage_account_tier
  account_replication_type = var.storage_account_replication
  
  # Security settings
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  
  # Network rules - allow Azure services
  network_rules {
    default_action             = "Allow"
    bypass                     = ["AzureServices"]
  }
  
  # Blob properties with versioning and soft delete
  blob_properties {
    versioning_enabled = true
    
    delete_retention_policy {
      days = var.blob_retention_days
    }
    
    container_delete_retention_policy {
      days = var.container_retention_days
    }
  }
  
  tags = var.tags
}

# Azure Monitor Diagnostic Setting for Entra ID
# Sends all Entra ID logs to Event Hub and optionally to Storage Account
resource "azurerm_monitor_aad_diagnostic_setting" "entra_id" {
  name                           = var.diagnostic_setting_name
  eventhub_authorization_rule_id = var.eventhub_authorization_rule_id
  eventhub_name                  = var.eventhub_name
  storage_account_id             = var.enable_storage_retention ? azurerm_storage_account.entra_logs[0].id : null
  
  # Enable all Entra ID log categories
  # Note: retention_policy blocks are required by the provider but must be disabled
  # Azure doesn't support retention for Entra ID diagnostic settings
  # Retention is managed at the storage account level if enabled
  
  # AuditLogs: Directory changes, user management, group changes, etc.
  enabled_log {
    category = "AuditLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # SignInLogs: Interactive user sign-ins
  enabled_log {
    category = "SignInLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # NonInteractiveUserSignInLogs: Service principal and managed identity sign-ins
  enabled_log {
    category = "NonInteractiveUserSignInLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # ServicePrincipalSignInLogs: Application sign-ins
  enabled_log {
    category = "ServicePrincipalSignInLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # ManagedIdentitySignInLogs: Azure managed identity sign-ins
  enabled_log {
    category = "ManagedIdentitySignInLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # ProvisioningLogs: Provisioning service logs
  enabled_log {
    category = "ProvisioningLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # ADFSSignInLogs: ADFS sign-in logs (if applicable)
  enabled_log {
    category = "ADFSSignInLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # RiskyUsers: Identity Protection risky users
  enabled_log {
    category = "RiskyUsers"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # UserRiskEvents: Identity Protection user risk events
  enabled_log {
    category = "UserRiskEvents"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # NetworkAccessTrafficLogs: Network access traffic logs
  enabled_log {
    category = "NetworkAccessTrafficLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # RiskyServicePrincipals: Risky service principals
  enabled_log {
    category = "RiskyServicePrincipals"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # ServicePrincipalRiskEvents: Service principal risk events
  enabled_log {
    category = "ServicePrincipalRiskEvents"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # EnrichedOffice365AuditLogs: Office 365 audit logs with enriched data
  enabled_log {
    category = "EnrichedOffice365AuditLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # MicrosoftGraphActivityLogs: Microsoft Graph API activity
  enabled_log {
    category = "MicrosoftGraphActivityLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # RemoteNetworkHealthLogs: Remote network health logs
  enabled_log {
    category = "RemoteNetworkHealthLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # NetworkAccessConnectionEvents: Network access connection events
  enabled_log {
    category = "NetworkAccessConnectionEvents"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # MicrosoftServicePrincipalSignInLogs: Microsoft service principal sign-ins
  enabled_log {
    category = "MicrosoftServicePrincipalSignInLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # AzureADGraphActivityLogs: Azure AD Graph API activity
  enabled_log {
    category = "AzureADGraphActivityLogs"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  # NetworkAccessGenerativeAIInsights: Generative AI network access insights
  enabled_log {
    category = "NetworkAccessGenerativeAIInsights"
    retention_policy {
      enabled = false
      days    = 0
    }
  }
  
  depends_on = [
    azurerm_storage_account.entra_logs
  ]
}

# Locals for computed values
locals {
  tenant_id           = data.azuread_client_config.current.tenant_id
  storage_account_url = var.enable_storage_retention ? azurerm_storage_account.entra_logs[0].primary_blob_endpoint : null
  
  # All enabled log categories for reference
  enabled_log_categories = [
    "AuditLogs",
    "SignInLogs",
    "NonInteractiveUserSignInLogs",
    "ServicePrincipalSignInLogs",
    "ManagedIdentitySignInLogs",
    "ProvisioningLogs",
    "ADFSSignInLogs",
    "RiskyUsers",
    "UserRiskEvents",
    "NetworkAccessTrafficLogs",
    "RiskyServicePrincipals",
    "ServicePrincipalRiskEvents",
    "EnrichedOffice365AuditLogs",
    "MicrosoftGraphActivityLogs",
    "RemoteNetworkHealthLogs",
    "NetworkAccessConnectionEvents",
    "MicrosoftServicePrincipalSignInLogs",
    "AzureADGraphActivityLogs",
    "NetworkAccessGenerativeAIInsights"
  ]
}