/**
 * Microsoft Defender for Cloud - Event Hub Integration
 *
 * This Terraform configuration creates Azure infrastructure to receive
 * continuous export data from Microsoft Defender for Cloud via Event Hubs.
 * Events are processed by AWS Lambda functions for integration with CloudTrail.
 *
 * Architecture Components:
 * - Resource Group
 * - Event Hub Namespace with auto-scaling
 * - Event Hub for security data streams
 * - IAM/RBAC configuration for Microsoft Defender access
 * - Azure Monitor with email/webhook alerting
 *
 * Author: SecureSight Team
 * Version: 1.0.0
 */

terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }
}

# Configure the Azure Provider
provider "azurerm" {
  subscription_id = var.subscription_id
  
  features {
    resource_group {
      prevent_deletion_if_contains_resources = var.prevent_resource_group_deletion
    }
  }
}

# Configure the Azure Active Directory Provider
provider "azuread" {}

# Data sources for current context
data "azurerm_client_config" "current" {}
data "azuread_client_config" "current" {}

# Local values for resource naming and tagging
locals {
  # Generate a short hash from subscription ID for global uniqueness (6 chars to keep names short)
  subscription_hash = substr(sha256(data.azurerm_client_config.current.subscription_id), 0, 6)
  
  # Naming convention: {project}-{hash}-{component}-{region}
  # Note: We use hash instead of environment to keep names within Azure's 50-character limit
  resource_prefix = "${var.project_name}-${local.subscription_hash}"
  
  # Convert region names to valid Azure resource naming format
  # Replace spaces with hyphens and convert to lowercase
  region_abbreviations = {
    "East US"           = "eastus"
    "East US 2"         = "eastus2"
    "West US"           = "westus"
    "West US 2"         = "westus2"
    "West US 3"         = "westus3"
    "Central US"        = "centralus"
    "North Central US"  = "northcentralus"
    "South Central US"  = "southcentralus"
    "Canada Central"    = "canadacentral"
    "Canada East"       = "canadaeast"
    "UK South"          = "uksouth"
    "UK West"           = "ukwest"
    "West Europe"       = "westeurope"
    "North Europe"      = "northeurope"
    "Australia East"    = "australiaeast"
    "Australia Southeast" = "australiasoutheast"
    "Japan East"        = "japaneast"
    "Japan West"        = "japanwest"
    "Southeast Asia"    = "southeastasia"
    "East Asia"         = "eastasia"
  }
  
  # Common tags applied to all resources
  common_tags = merge(var.additional_tags, {
    Project               = var.project_name
    Environment          = var.environment
    Owner               = var.owner
    CostCenter          = var.cost_center
    ManagedBy           = "Terraform"
    Purpose             = "Microsoft Defender for Cloud Integration"
    DeploymentTimestamp = timestamp()
    TerraformVersion    = "~> 1.0"
  })
  
  # Resource naming (hash already included in resource_prefix)
  resource_group_name    = "${local.resource_prefix}-${var.environment}-rg"
  eventhub_namespace     = "${local.resource_prefix}-ehns"
  eventhub_name         = var.eventhub_name
  
  # Multi-region support
  deployment_regions = var.multi_region_deployment ? var.deployment_regions : [var.primary_region]
}

# Resource Group
resource "azurerm_resource_group" "main" {
  for_each = toset(local.deployment_regions)
  
  name     = "${local.resource_group_name}-${local.region_abbreviations[each.key]}"
  location = each.key
  tags     = local.common_tags

  # Note: For production, uncomment the lifecycle block to prevent accidental deletion
  # lifecycle {
  #   prevent_destroy = true
  # }
}

# Event Hub Namespace Module
module "eventhub_namespace" {
  source = "./modules/eventhub-namespace"
  
  for_each = toset(local.deployment_regions)
  
  resource_group_name = azurerm_resource_group.main[each.key].name
  location           = each.key
  namespace_name     = "${local.eventhub_namespace}-${local.region_abbreviations[each.key]}"
  
  # Auto-scaling configuration
  sku                         = var.eventhub_sku
  capacity                    = var.eventhub_capacity
  auto_inflate_enabled        = var.auto_inflate_enabled
  maximum_throughput_units    = var.maximum_throughput_units
  
  # Network configuration
  public_network_access_enabled = var.public_network_access_enabled
  network_rulesets             = var.network_rulesets
  
  # Security configuration
  minimum_tls_version = var.minimum_tls_version
  
  # Monitoring configuration
  enable_diagnostic_logs      = var.diagnostic_logs_enabled
  log_analytics_workspace_id  = null
  
  tags = local.common_tags
}

# Event Hub Module
module "eventhub" {
  source = "./modules/eventhub"
  
  for_each = toset(local.deployment_regions)
  
  resource_group_name  = azurerm_resource_group.main[each.key].name
  namespace_name       = module.eventhub_namespace[each.key].namespace_name
  eventhub_name       = local.eventhub_name
  
  # Event Hub configuration
  partition_count   = var.eventhub_partition_count
  message_retention = var.eventhub_message_retention
  eventhub_tier    = var.eventhub_sku  # Pass the SKU tier to determine consumer group support
  
  # Capture configuration (disabled for stream-through architecture)
  capture_enabled = false
  
  # Microsoft Defender RBAC configuration
  enable_defender_rbac = var.enable_defender_export
  
  tags = local.common_tags
  
  depends_on = [module.eventhub_namespace]
}

# ============================================================================
# MICROSOFT DEFENDER CONTINUOUS EXPORT CONFIGURATION
# ============================================================================

# Microsoft Defender Continuous Export Module
# Only created when enable_defender_export is true
module "defender_export" {
  source = "./modules/defender-continuous-export"
  
  for_each = var.enable_defender_export ? toset(local.deployment_regions) : []
  
  automation_name            = "ExportToHub"
  location                   = each.key
  resource_group_name        = azurerm_resource_group.main[each.key].name
  eventhub_id                = module.eventhub[each.key].eventhub_id
  eventhub_connection_string = module.eventhub[each.key].send_connection_string
  
  tags = local.common_tags
  
  depends_on = [module.eventhub]
}

# ============================================================================
# VNET FLOW LOGS CONFIGURATION
# ============================================================================

# Storage Account for VNet Flow Logs
# Created when VNet Flow Logs are enabled
resource "azurerm_storage_account" "flow_logs" {
  for_each = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? toset(local.deployment_regions) : []
  
  # Storage account names must be globally unique, lowercase, alphanumeric only (3-24 chars)
  name                     = var.flow_logs_storage_account_name != null ? var.flow_logs_storage_account_name : "${lower(replace(local.resource_prefix, "-", ""))}fl${local.subscription_hash}"
  resource_group_name      = azurerm_resource_group.main[each.key].name
  location                 = each.key
  account_tier             = var.flow_logs_storage_account_tier
  account_replication_type = var.flow_logs_storage_account_replication
  
  # Security settings
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  
  # Network rules - allow Azure services
  network_rules {
    default_action             = "Allow"
    bypass                     = ["AzureServices"]
  }
  
  tags = local.common_tags
}

# Data source to get existing Network Watcher (if using existing one)
# Azure automatically creates a Network Watcher in "NetworkWatcherRG" when first needed
data "azurerm_network_watcher" "existing" {
  for_each = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 && var.use_existing_network_watcher ? toset(local.deployment_regions) : []
  
  name                = coalesce(var.existing_network_watcher_name, "NetworkWatcher_${each.key}")
  resource_group_name = var.existing_network_watcher_resource_group
}

# Network Watcher for VNet Flow Logs
# Only creates Network Watcher if use_existing_network_watcher is false
# Note: Azure only allows 1 Network Watcher per subscription per region
resource "azurerm_network_watcher" "main" {
  for_each = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 && !var.use_existing_network_watcher ? toset(local.deployment_regions) : []
  
  name                = "NetworkWatcher-${local.region_abbreviations[each.key]}"
  location            = each.key
  resource_group_name = azurerm_resource_group.main[each.key].name
  
  tags = local.common_tags
}

# Local to determine which Network Watcher to use
# Only create these locals when VNet flow logs are enabled
locals {
  network_watcher_info = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? {
    for region in local.deployment_regions :
    region => {
      name = var.use_existing_network_watcher ? data.azurerm_network_watcher.existing[region].name : azurerm_network_watcher.main[region].name
      resource_group = var.use_existing_network_watcher ? data.azurerm_network_watcher.existing[region].resource_group_name : azurerm_network_watcher.main[region].resource_group_name
    }
  } : {}
}

# IAM/RBAC: Network Watcher Service - Storage Account Access
# Grants Network Watcher permission to write flow logs to storage
resource "azurerm_role_assignment" "network_watcher_storage" {
  for_each = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? toset(local.deployment_regions) : []
  
  scope                = azurerm_storage_account.flow_logs[each.key].id
  role_definition_name = "Storage Account Contributor"
  
  # Grant the current service principal (running Terraform) access
  # This allows Terraform to manage flow logs
  principal_id         = data.azurerm_client_config.current.object_id
  
  depends_on = [
    azurerm_network_watcher.main,
    data.azurerm_network_watcher.existing
  ]
}

# VNet Flow Logs Module
# Azure provider v4.x supports VNet flow logs via target_resource_id
module "vnet_flow_logs" {
  source = "./modules/vnet-flow-logs"
  
  for_each = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? toset(local.deployment_regions) : []
  
  vnet_ids                       = var.vnet_ids
  network_watcher_name           = local.network_watcher_info[each.key].name
  network_watcher_resource_group = local.network_watcher_info[each.key].resource_group
  storage_account_id             = azurerm_storage_account.flow_logs[each.key].id
  eventhub_name                  = module.eventhub[each.key].eventhub_name
  eventhub_authorization_rule_id = module.eventhub_namespace[each.key].root_authorization_rule_id
  enable_eventhub_export         = var.enable_flowlogs_to_eventhub
  retention_enabled              = var.flow_logs_retention_enabled
  retention_days                 = var.flow_logs_retention_days
  flow_log_version               = var.flow_log_version
  enable_traffic_analytics       = var.enable_traffic_analytics
  traffic_analytics_interval     = var.traffic_analytics_interval
  tags                           = local.common_tags
  
  depends_on = [
    azurerm_storage_account.flow_logs,
    azurerm_role_assignment.network_watcher_storage,
    azurerm_network_watcher.main,
    data.azurerm_network_watcher.existing,
    module.eventhub,
    module.eventhub_namespace
  ]
}

# Event Grid Subscription Module
# Monitors blob creation events in the flow logs storage account
# and forwards them to the Event Hub using Cloud Event Schema v1.0
module "eventgrid_subscription" {
  source = "./modules/eventgrid-subscription"
  
  for_each = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 && var.enable_flowlogs_to_eventhub ? toset(local.deployment_regions) : []
  
  resource_group_name = azurerm_resource_group.main[each.key].name
  location            = each.key
  storage_account_id  = azurerm_storage_account.flow_logs[each.key].id
  eventhub_id         = module.eventhub[each.key].eventhub_id
  
  # Custom naming to match project conventions
  system_topic_name = "${local.resource_prefix}-flowlogs-events-${local.region_abbreviations[each.key]}"
  subscription_name = "flowlogs-to-eventhub"
  
  # Enable advanced filtering for flow log containers
  enable_advanced_filtering = true
  blob_type_filters = [
    "/blobServices/default/containers/insights-logs-"
  ]
  
  tags = local.common_tags
  
  depends_on = [
    azurerm_storage_account.flow_logs,
    module.eventhub
  ]
}

# ============================================================================
# AZURE APP REGISTRATION FOR AWS FLOW LOG INGESTION
# ============================================================================

# Azure App Registration Module for AWS Lambda to access flow logs
module "flowlog_app_registration" {
  source = "./modules/app-registration"
  
  count = var.enable_vnet_flowlogs && length(var.vnet_ids) > 0 ? 1 : 0
  
  application_name = "AWS Flow Log Ingestion"
  
  # Collect all storage account IDs from all regions
  storage_account_ids = [
    for region, sa in azurerm_storage_account.flow_logs : sa.id
  ]
  
  # Tags for the application
  application_tags = [
    "Purpose:AWS-Integration",
    "Service:Flow-Logs",
    "Environment:${var.environment}"
  ]
  
  # Secret configuration
  secret_display_name      = "AWS Flow Log Ingestion"
  secret_expiration_hours  = "43800h"  # 5 years
  
  # Role assignment
  role_definition_name = "Storage Blob Data Reader"
  
  depends_on = [azurerm_storage_account.flow_logs]
}

# ============================================================================
# ENTRA ID DIAGNOSTICS CONFIGURATION
# ============================================================================

# Entra ID Diagnostics Module
# Configures diagnostic settings to send all Entra ID logs to Event Hub
# Only created when enable_entra_id_logging is true
module "entra_id_diagnostics" {
  source = "./modules/entra-id-diagnostics"
  
  for_each = var.enable_entra_id_logging ? toset(local.deployment_regions) : []
  
  resource_group_name            = azurerm_resource_group.main[each.key].name
  location                       = each.key
  eventhub_authorization_rule_id = module.eventhub_namespace[each.key].root_authorization_rule_id
  eventhub_name                  = module.eventhub[each.key].eventhub_name
  
  # Log retention configuration
  diagnostic_setting_name = "entra-id-to-eventhub"
  log_retention_days      = var.entra_id_log_retention_days
  
  # Optional storage account for long-term retention
  enable_storage_retention    = var.entra_id_enable_storage_retention
  storage_account_name        = var.entra_id_storage_account_name != null ? var.entra_id_storage_account_name : "${lower(replace(local.resource_prefix, "-", ""))}entra${local.subscription_hash}"
  storage_account_tier        = "Standard"
  storage_account_replication = "LRS"
  blob_retention_days         = 30
  container_retention_days    = 30
  
  tags = local.common_tags
  
  depends_on = [
    module.eventhub,
    module.eventhub_namespace
  ]
}

# ============================================================================
# AWS LAMBDA INTEGRATION
# ============================================================================
# Note: AWS Lambda functions are deployed via CDK in the companion AWS stack.
# AWS Lambda polls this Event Hub to retrieve Microsoft Defender events.
