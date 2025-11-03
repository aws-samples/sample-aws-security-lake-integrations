/**
 * Microsoft Defender for Cloud - Event Hub Integration Outputs
 * 
 * This file defines the outputs that will be returned after successful deployment.
 * These outputs provide important information for configuring Microsoft Defender
 * and connecting external systems.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# RESOURCE GROUP OUTPUTS
# ============================================================================

output "resource_groups" {
  description = "Resource group information for each deployed region"
  value = {
    for region, rg in azurerm_resource_group.main : region => {
      name     = rg.name
      location = rg.location
      id       = rg.id
    }
  }
}

# ============================================================================
# EVENT HUB NAMESPACE OUTPUTS
# ============================================================================

output "eventhub_namespaces" {
  description = "Event Hub Namespace information for each deployed region"
  value = {
    for region, ns in module.eventhub_namespace : region => {
      name                    = ns.namespace_name
      id                     = ns.namespace_id
      connection_string      = ns.connection_string
      primary_key           = ns.primary_key
      secondary_key         = ns.secondary_key
      sku                   = ns.sku
      capacity              = ns.capacity
      auto_inflate_enabled  = ns.auto_inflate_enabled
      maximum_throughput_units = ns.maximum_throughput_units
    }
  }
  sensitive = true
}

output "eventhub_namespace_connection_strings" {
  description = "Event Hub Namespace connection strings (sensitive)"
  value = {
    for region, ns in module.eventhub_namespace : region => ns.connection_string
  }
  sensitive = true
}

# ============================================================================
# EVENT HUB OUTPUTS
# ============================================================================

output "eventhubs" {
  description = "Event Hub information for each deployed region"
  value = {
    for region, eh in module.eventhub : region => {
      name              = eh.eventhub_name
      id               = eh.eventhub_id
      partition_count  = eh.partition_count
      message_retention = eh.message_retention
      partition_ids    = eh.partition_ids
    }
  }
}

output "eventhub_connection_strings" {
  description = "Event Hub connection strings for Microsoft Defender configuration"
  value = {
    for region, eh in module.eventhub : region => eh.connection_string
  }
  sensitive = true
}

# ============================================================================
# IAM/RBAC OUTPUTS
# ============================================================================


# ============================================================================
# MICROSOFT DEFENDER CONTINUOUS EXPORT OUTPUTS
# ============================================================================

output "defender_continuous_export" {
  description = "Microsoft Defender continuous export configuration (only populated when enable_defender_export is true)"
  value = var.enable_defender_export ? {
    for region, export in module.defender_export : region => {
      id            = export.automation_id
      name          = export.automation_name
      location      = export.automation_location
      subscription  = export.subscription_scope
      configuration = export.configuration
    }
  } : {}
}

# ============================================================================
# AWS LAMBDA INTEGRATION OUTPUTS
# ============================================================================

output "aws_lambda_configuration" {
  description = "Configuration information needed for AWS Lambda Event Hub integration"
  value = {
    for region in local.deployment_regions : region => {
      # Event Hub connection details for AWS Lambda
      event_hub_namespace_name = module.eventhub_namespace[region].namespace_name
      event_hub_name          = local.eventhub_name
      event_hub_connection_string = module.eventhub_namespace[region].connection_string
      consumer_group          = "$Default"  # Basic tier only supports $Default
      
      # Azure subscription and tenant info
      subscription_id = data.azurerm_client_config.current.subscription_id
      tenant_id      = data.azurerm_client_config.current.tenant_id
      
      # Resource identifiers
      resource_group_name = azurerm_resource_group.main[region].name
      
      # No service principal needed - using AWS Lambda native authentication
      authentication_method = "aws_lambda_native"
    }
  }
  sensitive = true
}

# ============================================================================
# MICROSOFT DEFENDER CONFIGURATION OUTPUTS
# ============================================================================

output "microsoft_defender_configuration" {
  description = "Configuration information for Microsoft Defender for Cloud Continuous Export"
  value = {
    for region in local.deployment_regions : region => {
      # Event Hub configuration for Continuous Export
      event_hub_namespace    = module.eventhub_namespace[region].namespace_name
      event_hub_name        = local.eventhub_name
      connection_string     = module.eventhub_namespace[region].connection_string
      
      # Resource identifiers
      resource_group_name   = azurerm_resource_group.main[region].name
      subscription_id       = data.azurerm_client_config.current.subscription_id
      tenant_id            = data.azurerm_client_config.current.tenant_id
      
      # AWS Lambda integration method
      integration_method    = "aws_lambda_native"
    }
  }
  sensitive = true
}

# ============================================================================
# VNET FLOW LOGS OUTPUTS
# ============================================================================

output "vnet_flow_logs_storage_accounts" {
  description = "Storage account information for VNet Flow Logs (only populated when enable_vnet_flowlogs is true)"
  value = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? {
    for region, sa in azurerm_storage_account.flow_logs : region => {
      name                = sa.name
      id                  = sa.id
      location            = sa.location
      primary_endpoint    = sa.primary_blob_endpoint
      account_tier        = sa.account_tier
      replication_type    = sa.account_replication_type
    }
  } : {}
}


output "vnet_flow_logs_summary" {
  description = "Summary of VNet Flow Logs configuration"
  value = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? {
    enabled                = true
    vnet_count             = length(var.vnet_ids)
    retention_days         = var.flow_logs_retention_days
    flow_log_version       = var.flow_log_version
    traffic_analytics      = var.enable_traffic_analytics
    eventhub_export        = var.enable_flowlogs_to_eventhub
    deployed_regions       = local.deployment_regions
    message                = "VNet Flow Logs are enabled and configured"
  } : {
    enabled          = false
    vnet_count       = 0
    retention_days   = 0
    flow_log_version = 0
    traffic_analytics = false
    eventhub_export  = false
    deployed_regions = []
    message          = "VNet Flow Logs are not enabled. Set enable_vnet_flowlogs = true and provide vnet_ids to enable."
  }
}

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================

output "deployment_summary" {
  description = "Summary of deployed resources and configuration"
  value = {
    project_name          = var.project_name
    environment          = var.environment
    deployment_timestamp = timestamp()
    deployed_regions     = local.deployment_regions
    
    resources_deployed = {
      resource_groups            = length(local.deployment_regions)
      eventhub_namespaces        = length(local.deployment_regions)
      eventhubs                  = length(local.deployment_regions)
      defender_continuous_export = var.enable_defender_export ? length(local.deployment_regions) : 0
      vnet_flow_logs_enabled     = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0
      vnet_flow_logs_count       = var.enable_vnet_flowlogs ? length(var.vnet_ids) : 0
      flow_logs_storage_accounts = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? length(local.deployment_regions) : 0
    }
    
    configuration = {
      multi_region_deployment = var.multi_region_deployment
      auto_scaling_enabled    = var.auto_inflate_enabled
      defender_export_enabled = var.enable_defender_export
    }
  }
}

# ============================================================================
# AWS CDK INTEGRATION CONFIGURATION
# ============================================================================

output "cdk_deployment_command" {
  description = "CDK deployment command for AWS Lambda integration"
  value = {
    for region in local.deployment_regions : region =>
      "cd ../cdk && npm run deploy"
  }
  sensitive = false
}

# ============================================================================
# NEXT STEPS INFORMATION
# ============================================================================

output "next_steps" {
  description = "Next steps for completing the Microsoft Defender integration"
  value = {
    microsoft_defender_setup = [
      "1. Navigate to Microsoft Defender for Cloud in the Azure portal",
      "2. Go to Environment Settings > Continuous Export",
      "3. Configure continuous export with the following settings:",
      "   - Export target: Event Hub",
      "   - Event Hub Namespace: Use the namespace from outputs",
      "   - Event Hub Name: Use the Event Hub name from outputs",
      "   - Connection String: Use the connection string from outputs (if not using Managed Identity)",
      "4. Select the data types to export (Security alerts, Recommendations, etc.)",
      "5. Configure the export frequency and scope",
      "6. Test the integration by generating security alerts or recommendations"
    ]
    
    external_system_integration = [
      "1. The Microsoft Defender continuous export 'ExportToHub' is automatically configured",
      "2. Security data is now streaming to the Event Hub",
      "3. Configure AWS Lambda (via CDK stack) to consume from the Event Hub",
      "4. Use the connection strings and configuration from the outputs",
      "5. Test end-to-end data flow from Microsoft Defender to AWS"
    ]
  }
}
# ============================================================================
# EVENT GRID SUBSCRIPTION OUTPUTS
# ============================================================================

output "eventgrid_subscription" {
  description = "Event Grid subscription configuration for flow logs storage monitoring"
  value = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 && var.enable_flowlogs_to_eventhub ? {
    for region, sub in module.eventgrid_subscription : region => {
      system_topic_id       = sub.system_topic_id
      system_topic_name     = sub.system_topic_name
      subscription_id       = sub.subscription_id
      subscription_name     = sub.subscription_name
      event_delivery_schema = sub.event_delivery_schema
      included_event_types  = sub.included_event_types
      configuration_summary = sub.configuration_summary
    }
  } : {}
}
# ============================================================================
# ENTRA ID DIAGNOSTICS OUTPUTS
# ============================================================================

output "entra_id_diagnostic_setting_ids" {
  description = "Resource IDs of the Entra ID diagnostic settings by region"
  value = var.enable_entra_id_logging ? {
    for region, config in module.entra_id_diagnostics : region => config.diagnostic_setting_id
  } : {}
}

output "entra_id_diagnostic_setting_names" {
  description = "Names of the Entra ID diagnostic settings by region"
  value = var.enable_entra_id_logging ? {
    for region, config in module.entra_id_diagnostics : region => config.diagnostic_setting_name
  } : {}
}

output "entra_id_storage_account_ids" {
  description = "Resource IDs of storage accounts for Entra ID log retention (if enabled)"
  value = var.enable_entra_id_logging && var.entra_id_enable_storage_retention ? {
    for region, config in module.entra_id_diagnostics : region => config.storage_account_id
  } : {}
}

output "entra_id_enabled_log_categories" {
  description = "List of all enabled Entra ID log categories"
  value = var.enable_entra_id_logging ? [
    for region, config in module.entra_id_diagnostics : config.enabled_log_categories
  ][0] : []
}

output "entra_id_tenant_id" {
  description = "Azure AD tenant ID being monitored"
  value = var.enable_entra_id_logging ? [
    for region, config in module.entra_id_diagnostics : config.tenant_id
  ][0] : null
}

# ============================================================================
# AZURE APP REGISTRATION OUTPUTS (FLOW LOG INGESTION)
# ============================================================================

output "flowlog_ingestion_app_registration" {
  description = "Azure App Registration credentials for AWS Flow Log Ingestion"
  value = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? {
    application_id     = module.flowlog_app_registration[0].application_id
    application_name   = module.flowlog_app_registration[0].application_name
    tenant_id          = data.azurerm_client_config.current.tenant_id
    client_secret      = module.flowlog_app_registration[0].client_secret
    client_secret_id   = module.flowlog_app_registration[0].client_secret_id
    expiration_date    = module.flowlog_app_registration[0].client_secret_expiration
    role_assignment    = "Storage Blob Data Reader"
    
    # Storage accounts this app has access to
    storage_accounts = {
      for region, sa in azurerm_storage_account.flow_logs : region => {
        name               = sa.name
        id                 = sa.id
        primary_endpoint   = sa.primary_blob_endpoint
      }
    }
    
    # Authentication details for AWS Lambda
    authentication = {
      client_id       = module.flowlog_app_registration[0].application_id
      client_secret   = module.flowlog_app_registration[0].client_secret
      tenant_id     = data.azurerm_client_config.current.tenant_id
      subscription_id = data.azurerm_client_config.current.subscription_id
    }
  } : null
  sensitive = true
}

output "flowlog_ingestion_credentials_summary" {
  description = "Summary of flow log ingestion credentials (non-sensitive)"
  value = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? {
    application_name      = module.flowlog_app_registration[0].application_name
    application_id        = module.flowlog_app_registration[0].application_id
    tenant_id             = data.azurerm_client_config.current.tenant_id
    subscription_id       = data.azurerm_client_config.current.subscription_id
    role_assigned         = "Storage Blob Data Reader"
    expiration_years      = 5
    expiration_date       = module.flowlog_app_registration[0].client_secret_expiration
    storage_account_count = module.flowlog_app_registration[0].storage_account_count
    message            = "IMPORTANT: Save the client_secret from 'flowlog_ingestion_app_registration' output - it will not be shown again!"
  } : null
}
