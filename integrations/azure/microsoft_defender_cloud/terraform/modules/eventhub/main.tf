/**
 * Event Hub Module
 * 
 * This module creates an Azure Event Hub within an existing Event Hub Namespace
 * for receiving Microsoft Defender for Cloud continuous export data.
 * 
 * Features:
 * - Configurable partition count and message retention
 * - Authorization rules for granular access control
 * - Consumer groups for multiple data consumers
 * - Optional capture configuration (disabled for stream-through)
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
  }
}

# Event Hub
resource "azurerm_eventhub" "main" {
  name                = var.eventhub_name
  namespace_name      = var.namespace_name
  resource_group_name = var.resource_group_name
  
  # Partition configuration
  partition_count = var.partition_count
  
  # Message retention configuration (1-7 days for Standard, 1-90 days for Premium)
  message_retention = var.message_retention
  
  # Status (Active, Disabled, SendDisabled)
  status = var.status
  
  # Capture configuration (disabled by default for stream-through architecture)
  dynamic "capture_description" {
    for_each = var.capture_enabled ? [1] : []
    content {
      enabled  = var.capture_enabled
      encoding = var.capture_encoding
      
      # Time window for capture (60-900 seconds)
      interval_in_seconds = var.capture_interval_seconds
      
      # Size window for capture (10485760-524288000 bytes)
      size_limit_in_bytes = var.capture_size_limit_bytes
      
      # Skip empty archives
      skip_empty_archives = var.capture_skip_empty_archives
      
      destination {
        name                = "EventHubArchive.AzureBlockBlob"
        archive_name_format = var.capture_name_format
        blob_container_name = var.capture_container_name
        storage_account_id  = var.capture_storage_account_id
      }
    }
  }
}

# Note: Basic tier Event Hub only supports the default "$Default" consumer group
# Additional consumer groups require Standard or Premium tier
# The $Default consumer group is automatically created and available for use

# Placeholder for consumer groups (only created if Event Hub is Standard/Premium tier)
resource "azurerm_eventhub_consumer_group" "external_consumers" {
  for_each = var.eventhub_tier != "Basic" ? toset(var.consumer_groups) : []
  
  name                = each.value
  namespace_name      = var.namespace_name
  eventhub_name       = azurerm_eventhub.main.name
  resource_group_name = var.resource_group_name
  user_metadata       = "Consumer group for ${each.value}"
  
  depends_on = [azurerm_eventhub.main]
}

# Authorization Rules for Event Hub (more granular than namespace-level)
resource "azurerm_eventhub_authorization_rule" "listen_only" {
  count               = var.create_listen_only_rule ? 1 : 0
  name                = "ListenOnlyAccess"
  namespace_name      = var.namespace_name
  eventhub_name       = azurerm_eventhub.main.name
  resource_group_name = var.resource_group_name
  
  listen = true
  send   = false
  manage = false
  
  depends_on = [azurerm_eventhub.main]
}

resource "azurerm_eventhub_authorization_rule" "send_only" {
  count               = var.create_send_only_rule ? 1 : 0
  name                = "SendOnlyAccess"
  namespace_name      = var.namespace_name
  eventhub_name       = azurerm_eventhub.main.name
  resource_group_name = var.resource_group_name
  
  listen = false
  send   = true
  manage = false
  
  depends_on = [azurerm_eventhub.main]
}

resource "azurerm_eventhub_authorization_rule" "full_access" {
  count               = var.create_full_access_rule ? 1 : 0
  name                = "FullAccess"
  namespace_name      = var.namespace_name
  eventhub_name       = azurerm_eventhub.main.name
  resource_group_name = var.resource_group_name
  
  listen = true
  send   = true
  manage = true
  
  depends_on = [azurerm_eventhub.main]
}

# ============================================================================
# MICROSOFT DEFENDER FOR CLOUD RBAC INTEGRATION
# ============================================================================

# Data source to get the "Windows Azure Security Resource Provider" service principal
# This is the built-in service principal used by Microsoft Defender for Cloud
# Only created when enable_defender_rbac is true
data "azuread_service_principal" "defender_resource_provider" {
  count = var.enable_defender_rbac ? 1 : 0
  
  display_name = "Windows Azure Security Resource Provider"
}

# Role assignment: Azure Event Hubs Data Sender for Microsoft Defender
# This allows Microsoft Defender for Cloud to send events to the Event Hub using RBAC
# Only created when enable_defender_rbac is true
resource "azurerm_role_assignment" "defender_eventhub_sender" {
  count = var.enable_defender_rbac ? 1 : 0
  
  scope                = azurerm_eventhub.main.id
  role_definition_name = "Azure Event Hubs Data Sender"
  principal_id         = data.azuread_service_principal.defender_resource_provider[0].object_id
  
  depends_on = [azurerm_eventhub.main]
}

# Locals for computed values
locals {
  # Generate Event Hub-specific connection strings
  listen_connection_string = var.create_listen_only_rule ? azurerm_eventhub_authorization_rule.listen_only[0].primary_connection_string : null
  send_connection_string   = var.create_send_only_rule ? azurerm_eventhub_authorization_rule.send_only[0].primary_connection_string : null
  full_connection_string   = var.create_full_access_rule ? azurerm_eventhub_authorization_rule.full_access[0].primary_connection_string : null
  
  # Partition IDs (0-based indexing)
  partition_ids = [for i in range(var.partition_count) : tostring(i)]
  
  # Consumer group names (including default $Default)
  all_consumer_groups = concat(["$Default"], var.consumer_groups)
}