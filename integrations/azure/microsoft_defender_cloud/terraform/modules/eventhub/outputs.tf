/**
 * Event Hub Module Outputs
 * 
 * This file defines the outputs that will be returned from the Event Hub module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# EVENT HUB OUTPUTS
# ============================================================================

output "eventhub_id" {
  description = "The ID of the Event Hub"
  value       = azurerm_eventhub.main.id
}

output "eventhub_name" {
  description = "The name of the Event Hub"
  value       = azurerm_eventhub.main.name
}

output "partition_count" {
  description = "The number of partitions in the Event Hub"
  value       = azurerm_eventhub.main.partition_count
}

output "message_retention" {
  description = "The message retention period in days"
  value       = azurerm_eventhub.main.message_retention
}

output "status" {
  description = "The status of the Event Hub"
  value       = azurerm_eventhub.main.status
}

output "partition_ids" {
  description = "List of partition IDs for the Event Hub"
  value       = local.partition_ids
}

# ============================================================================
# CONSUMER GROUPS OUTPUTS
# ============================================================================

output "consumer_groups" {
  description = "Information about created consumer groups"
  value = {
    for name, group in azurerm_eventhub_consumer_group.external_consumers : name => {
      id            = group.id
      name          = group.name
      user_metadata = group.user_metadata
    }
  }
}

output "all_consumer_groups" {
  description = "List of all consumer groups (including default)"
  value       = local.all_consumer_groups
}

# ============================================================================
# AUTHORIZATION RULES OUTPUTS
# ============================================================================

output "listen_only_rule" {
  description = "Information about the listen-only authorization rule"
  value = var.create_listen_only_rule ? {
    id                            = azurerm_eventhub_authorization_rule.listen_only[0].id
    name                          = azurerm_eventhub_authorization_rule.listen_only[0].name
    primary_key                   = azurerm_eventhub_authorization_rule.listen_only[0].primary_key
    secondary_key                 = azurerm_eventhub_authorization_rule.listen_only[0].secondary_key
    primary_connection_string     = azurerm_eventhub_authorization_rule.listen_only[0].primary_connection_string
    secondary_connection_string   = azurerm_eventhub_authorization_rule.listen_only[0].secondary_connection_string
  } : null
  sensitive = true
}

output "send_only_rule" {
  description = "Information about the send-only authorization rule"
  value = var.create_send_only_rule ? {
    id                            = azurerm_eventhub_authorization_rule.send_only[0].id
    name                          = azurerm_eventhub_authorization_rule.send_only[0].name
    primary_key                   = azurerm_eventhub_authorization_rule.send_only[0].primary_key
    secondary_key                 = azurerm_eventhub_authorization_rule.send_only[0].secondary_key
    primary_connection_string     = azurerm_eventhub_authorization_rule.send_only[0].primary_connection_string
    secondary_connection_string   = azurerm_eventhub_authorization_rule.send_only[0].secondary_connection_string
  } : null
  sensitive = true
}

output "full_access_rule" {
  description = "Information about the full access authorization rule"
  value = var.create_full_access_rule ? {
    id                            = azurerm_eventhub_authorization_rule.full_access[0].id
    name                          = azurerm_eventhub_authorization_rule.full_access[0].name
    primary_key                   = azurerm_eventhub_authorization_rule.full_access[0].primary_key
    secondary_key                 = azurerm_eventhub_authorization_rule.full_access[0].secondary_key
    primary_connection_string     = azurerm_eventhub_authorization_rule.full_access[0].primary_connection_string
    secondary_connection_string   = azurerm_eventhub_authorization_rule.full_access[0].secondary_connection_string
  } : null
  sensitive = true
}

# ============================================================================
# CONNECTION STRINGS OUTPUTS
# ============================================================================

output "connection_string" {
  description = "Connection string for the most appropriate authorization rule"
  value = coalesce(
    local.send_connection_string,
    local.full_connection_string,
    local.listen_connection_string
  )
  sensitive = true
}

output "listen_connection_string" {
  description = "Connection string for listen-only access"
  value       = local.listen_connection_string
  sensitive   = true
}

output "send_connection_string" {
  description = "Connection string for send-only access (recommended for Microsoft Defender)"
  value       = local.send_connection_string
  sensitive   = true
}

output "full_connection_string" {
  description = "Connection string for full access"
  value       = local.full_connection_string
  sensitive   = true
}

# ============================================================================
# CAPTURE CONFIGURATION OUTPUTS
# ============================================================================

output "capture_enabled" {
  description = "Whether Event Hub Capture is enabled"
  value       = var.capture_enabled
}

output "capture_configuration" {
  description = "Event Hub Capture configuration (if enabled)"
  value = var.capture_enabled ? {
    enabled                 = var.capture_enabled
    encoding               = var.capture_encoding
    interval_in_seconds    = var.capture_interval_seconds
    size_limit_in_bytes    = var.capture_size_limit_bytes
    skip_empty_archives    = var.capture_skip_empty_archives
    archive_name_format    = var.capture_name_format
    container_name         = var.capture_container_name
    storage_account_id     = var.capture_storage_account_id
  } : null
}

# ============================================================================
# MICROSOFT DEFENDER CONFIGURATION OUTPUTS
# ============================================================================

output "defender_rbac_role_assignment" {
  description = "Information about the Microsoft Defender RBAC role assignment (null if disabled)"
  value = var.enable_defender_rbac ? {
    role_assignment_id   = azurerm_role_assignment.defender_eventhub_sender[0].id
    role_definition_name = azurerm_role_assignment.defender_eventhub_sender[0].role_definition_name
    principal_id         = azurerm_role_assignment.defender_eventhub_sender[0].principal_id
    scope                = azurerm_role_assignment.defender_eventhub_sender[0].scope
    service_principal    = "Windows Azure Security Resource Provider"
  } : null
}

output "microsoft_defender_config" {
  description = "Configuration information specifically for Microsoft Defender for Cloud"
  value = {
    # Recommended configuration settings
    eventhub_name               = azurerm_eventhub.main.name
    partition_count            = azurerm_eventhub.main.partition_count
    
    # Recommended connection string (send-only)
    recommended_connection_string = local.send_connection_string
    
    # Consumer group for Microsoft Defender (uses default)
    consumer_group             = "$Default"
    
    # RBAC authentication status
    rbac_enabled = var.enable_defender_rbac
    rbac_role    = var.enable_defender_rbac ? "Azure Event Hubs Data Sender" : null
    
    # Export configuration guidance
    export_configuration = {
      data_types = [
        "Security recommendations",
        "Security alerts",
        "Secure score",
        "Regulatory compliance"
      ]
      frequency = "Streaming"
      format    = "JSON"
    }
  }
  sensitive = true
}