/**
 * Event Hub Namespace Module
 * 
 * This module creates an Azure Event Hub Namespace with auto-scaling capabilities
 * for receiving Microsoft Defender for Cloud continuous export data.
 * 
 * Features:
 * - Auto-scaling with configurable throughput units
 * - Network access controls
 * - Security configurations (TLS, encryption)
 * - Monitoring and diagnostic settings
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

# Event Hub Namespace
resource "azurerm_eventhub_namespace" "main" {
  name                = var.namespace_name
  location            = var.location
  resource_group_name = var.resource_group_name
  
  # SKU and capacity configuration
  sku      = var.sku
  capacity = var.capacity
  
  # Auto-scaling configuration
  auto_inflate_enabled     = var.auto_inflate_enabled
  maximum_throughput_units = var.auto_inflate_enabled ? var.maximum_throughput_units : null
  
  # Network configuration
  public_network_access_enabled = var.public_network_access_enabled
  minimum_tls_version           = var.minimum_tls_version
  
  # Network rulesets (configured inline)
  dynamic "network_rulesets" {
    for_each = var.network_rulesets != null ? [var.network_rulesets] : []
    content {
      default_action                 = network_rulesets.value.default_action
      trusted_service_access_enabled = network_rulesets.value.trusted_service_access_enabled
      
      dynamic "ip_rule" {
        for_each = network_rulesets.value.ip_rules
        content {
          ip_mask = ip_rule.value
        }
      }
      
      dynamic "virtual_network_rule" {
        for_each = network_rulesets.value.virtual_network_rules
        content {
          subnet_id                            = virtual_network_rule.value.subnet_id
          ignore_missing_virtual_network_service_endpoint = virtual_network_rule.value.ignore_missing_virtual_network_service_endpoint
        }
      }
    }
  }
  
  # Note: Zone redundancy is configured at the region level for Premium SKUs
  
  # Identity configuration (system-assigned managed identity)
  identity {
    type = "SystemAssigned"
  }
  
  tags = var.tags
  
  # Note: For production, uncomment the lifecycle block to prevent accidental deletion
  # lifecycle {
  #   prevent_destroy = true
  # }
}

# Note: Network rules for Event Hub namespaces are configured via the namespace resource
# The azurerm_eventhub_namespace_network_rulesets resource is not supported in this provider version
# Network access controls should be configured using the network_rulesets block in the namespace resource
# For advanced network isolation, consider using Private Endpoints instead

# Note: RootManageSharedAccessKey is automatically created by Azure
# We reference the auto-created one instead of creating our own
data "azurerm_eventhub_namespace_authorization_rule" "root_manage_shared_access_key" {
  name                = "RootManageSharedAccessKey"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = var.resource_group_name
  
  depends_on = [azurerm_eventhub_namespace.main]
}

# Additional authorization rule for Microsoft Defender (send-only)
resource "azurerm_eventhub_namespace_authorization_rule" "defender_send_access" {
  count               = var.create_defender_access_rule ? 1 : 0
  name                = "DefenderSendAccess"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = var.resource_group_name
  
  listen = false
  send   = true
  manage = false
  
  depends_on = [azurerm_eventhub_namespace.main]
}

# Note: Diagnostic Settings are configured separately to avoid circular dependencies
# They can be added after initial deployment or managed separately
# Uncomment and configure the following resource if Log Analytics workspace is available:

# resource "azurerm_monitor_diagnostic_setting" "namespace" {
#   name               = "${azurerm_eventhub_namespace.main.name}-diagnostics"
#   target_resource_id = azurerm_eventhub_namespace.main.id
#   log_analytics_workspace_id = var.log_analytics_workspace_id
#
#   dynamic "enabled_log" {
#     for_each = var.diagnostic_log_categories
#     content {
#       category = enabled_log.value
#     }
#   }
#
#   metric {
#     category = "AllMetrics"
#     enabled  = true
#   }
# }

# Locals for computed values
locals {
  # Connection string components
  namespace_fqdn = "${azurerm_eventhub_namespace.main.name}.servicebus.windows.net"
  
  # Generate connection string using auto-created authorization rule
  connection_string = "Endpoint=sb://${local.namespace_fqdn}/;SharedAccessKeyName=${data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.name};SharedAccessKey=${data.azurerm_eventhub_namespace_authorization_rule.root_manage_shared_access_key.primary_key}"
  
  # Defender-specific connection string (if enabled)
  defender_connection_string = var.create_defender_access_rule ? "Endpoint=sb://${local.namespace_fqdn}/;SharedAccessKeyName=${azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].name};SharedAccessKey=${azurerm_eventhub_namespace_authorization_rule.defender_send_access[0].primary_key}" : null
}