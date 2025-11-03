/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Entra ID Diagnostics Module Outputs
 * 
 * This file defines the outputs from the Entra ID diagnostic settings module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

output "diagnostic_setting_id" {
  description = "Resource ID of the Entra ID diagnostic setting"
  value       = azurerm_monitor_aad_diagnostic_setting.entra_id.id
}

output "diagnostic_setting_name" {
  description = "Name of the Entra ID diagnostic setting"
  value       = azurerm_monitor_aad_diagnostic_setting.entra_id.name
}

output "storage_account_id" {
  description = "Resource ID of the storage account for log retention (if enabled)"
  value       = var.enable_storage_retention ? azurerm_storage_account.entra_logs[0].id : null
}

output "storage_account_name" {
  description = "Name of the storage account for log retention (if enabled)"
  value       = var.enable_storage_retention ? azurerm_storage_account.entra_logs[0].name : null
}

output "storage_account_primary_blob_endpoint" {
  description = "Primary blob endpoint of the storage account (if enabled)"
  value       = var.enable_storage_retention ? azurerm_storage_account.entra_logs[0].primary_blob_endpoint : null
}

output "tenant_id" {
  description = "Azure AD tenant ID being monitored"
  value       = local.tenant_id
}

output "enabled_log_categories" {
  description = "List of all enabled log categories"
  value       = local.enabled_log_categories
}

output "eventhub_name" {
  description = "Name of the Event Hub receiving the logs"
  value       = var.eventhub_name
}