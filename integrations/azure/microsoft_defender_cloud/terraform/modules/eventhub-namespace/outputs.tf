/**
 * Event Hub Namespace Module Outputs
 * 
 * This file defines the outputs that will be returned from the Event Hub Namespace module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# EVENT HUB NAMESPACE OUTPUTS
# ============================================================================

output "namespace_id" {
  description = "The ID of the Event Hub Namespace"
  value       = azurerm_eventhub_namespace.main.id
}

output "namespace_name" {
  description = "The name of the Event Hub Namespace"
  value       = azurerm_eventhub_namespace.main.name
}

output "namespace_fqdn" {
  description = "The fully qualified domain name of the Event Hub Namespace"
  value       = local.namespace_fqdn
}

# ============================================================================
# CONNECTION STRINGS AND KEYS
# ============================================================================

output "connection_string" {
  description = "The primary connection string for the Event Hub Namespace"
  value       = local.connection_string
  sensitive   = true
}

output "primary_key" {
  description = "The primary access key for the Event Hub Namespace"
  value       = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.primary_key
  sensitive   = true
}

output "secondary_key" {
  description = "The secondary access key for the Event Hub Namespace"
  value       = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.secondary_key
  sensitive   = true
}

output "primary_connection_string" {
  description = "The primary connection string for the authorization rule"
  value       = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.primary_connection_string
  sensitive   = true
}

output "secondary_connection_string" {
  description = "The secondary connection string for the authorization rule"
  value       = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.secondary_connection_string
  sensitive   = true
}

# ============================================================================
# MICROSOFT DEFENDER ACCESS OUTPUTS
# ============================================================================

output "defender_connection_string" {
  description = "The connection string for Microsoft Defender access (send-only)"
  value       = local.defender_connection_string
  sensitive   = true
}

output "defender_primary_key" {
  description = "The primary access key for Microsoft Defender authorization rule"
  value       = var.create_defender_access_rule ? azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].primary_key : null
  sensitive   = true
}

output "defender_secondary_key" {
  description = "The secondary access key for Microsoft Defender authorization rule"
  value       = var.create_defender_access_rule ? azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].secondary_key : null
  sensitive   = true
}

# ============================================================================
# CONFIGURATION OUTPUTS
# ============================================================================

output "sku" {
  description = "The SKU of the Event Hub Namespace"
  value       = azurerm_eventhub_namespace.main.sku
}

output "capacity" {
  description = "The capacity/throughput units of the Event Hub Namespace"
  value       = azurerm_eventhub_namespace.main.capacity
}

output "auto_inflate_enabled" {
  description = "Is auto-inflate enabled for the Event Hub Namespace"
  value       = azurerm_eventhub_namespace.main.auto_inflate_enabled
}

output "maximum_throughput_units" {
  description = "The maximum throughput units when auto-inflate is enabled"
  value       = azurerm_eventhub_namespace.main.maximum_throughput_units
}

output "minimum_tls_version" {
  description = "The minimum TLS version for the Event Hub Namespace"
  value       = azurerm_eventhub_namespace.main.minimum_tls_version
}

# ============================================================================
# IDENTITY OUTPUTS
# ============================================================================

output "identity" {
  description = "The managed identity information for the Event Hub Namespace"
  value = {
    type         = azurerm_eventhub_namespace.main.identity[0].type
    principal_id = azurerm_eventhub_namespace.main.identity[0].principal_id
    tenant_id    = azurerm_eventhub_namespace.main.identity[0].tenant_id
  }
}

output "principal_id" {
  description = "The Principal ID of the System Assigned Managed Service Identity"
  value       = azurerm_eventhub_namespace.main.identity[0].principal_id
}

# ============================================================================
# NETWORK CONFIGURATION OUTPUTS
# ============================================================================

output "public_network_access_enabled" {
  description = "Is public network access enabled for the Event Hub Namespace"
  value       = azurerm_eventhub_namespace.main.public_network_access_enabled
}

output "network_rulesets_configured" {
  description = "Are network rulesets configured for the Event Hub Namespace"
  value       = var.network_rulesets != null
}

output "network_access_configuration" {
  description = "Network access configuration for the Event Hub Namespace"
  value = {
    public_network_access_enabled = azurerm_eventhub_namespace.main.public_network_access_enabled
    minimum_tls_version           = azurerm_eventhub_namespace.main.minimum_tls_version
    network_rulesets_enabled      = var.network_rulesets != null
  }
}

# ============================================================================
# DIAGNOSTIC SETTINGS OUTPUTS
# ============================================================================

output "diagnostic_setting_id" {
  description = "The ID of the diagnostic setting (if enabled)"
  value       = null  # Diagnostic settings are configured separately to avoid dependencies
}

# ============================================================================
# AUTHORIZATION RULES OUTPUTS
# ============================================================================

output "root_authorization_rule_id" {
  description = "The resource ID of the RootManageSharedAccessKey authorization rule (for diagnostic settings)"
  value       = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.id
}

output "authorization_rules" {
  description = "Information about the authorization rules"
  value = {
    root_manage_shared_access_key = {
      id     = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.id
      name   = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.name
      listen = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.listen
      send   = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.send
      manage = data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.manage
    }
    defender_send_access = var.create_defender_access_rule ? {
      id     = azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].id
      name   = azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].name
      listen = azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].listen
      send   = azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].send
      manage = azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].manage
    } : null
  }
  sensitive = true
}