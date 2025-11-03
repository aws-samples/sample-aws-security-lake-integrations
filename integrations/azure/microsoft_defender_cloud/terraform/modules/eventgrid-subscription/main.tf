/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Event Grid Subscription Module
 * 
 * This module creates an Azure Event Grid subscription to monitor storage account
 * blob events and forward them to an Event Hub endpoint.
 * 
 * Features:
 * - Storage account blob event monitoring
 * - Cloud Event Schema v1.0 format
 * - Filtered to "Blob Created" events
 * - Event Hub endpoint integration
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

# Event Grid System Topic for Storage Account
# This creates a system topic to capture storage account events
resource "azurerm_eventgrid_system_topic" "storage" {
  name                   = var.system_topic_name
  resource_group_name    = var.resource_group_name
  location               = var.location
  source_arm_resource_id = var.storage_account_id
  topic_type             = "Microsoft.Storage.StorageAccounts"
  
  tags = var.tags
}

# Event Grid Subscription
# Subscribes to blob created events and forwards to Event Hub
resource "azurerm_eventgrid_system_topic_event_subscription" "blob_events" {
  name                = var.subscription_name
  system_topic        = azurerm_eventgrid_system_topic.storage.name
  resource_group_name = var.resource_group_name
  
  # Event Hub endpoint configuration
  eventhub_endpoint_id = var.eventhub_id
  
  # Use Cloud Event Schema v1.0
  event_delivery_schema = "CloudEventSchemaV1_0"
  
  # Filter to Blob Created events only
  included_event_types = [
    "Microsoft.Storage.BlobCreated"
  ]
  
  # Advanced filtering (optional)
  dynamic "advanced_filter" {
    for_each = var.enable_advanced_filtering ? [1] : []
    content {
      # Filter by blob type if specified
      dynamic "string_begins_with" {
        for_each = length(var.blob_type_filters) > 0 ? [1] : []
        content {
          key    = "subject"
          values = var.blob_type_filters
        }
      }
    }
  }
  
  # Retry policy for failed deliveries
  retry_policy {
    max_delivery_attempts = var.max_delivery_attempts
    event_time_to_live    = var.event_time_to_live_minutes
  }
  
  # Dead letter configuration (optional)
  dynamic "dead_letter_identity" {
    for_each = var.dead_letter_storage_account_id != null ? [1] : []
    content {
      type = "SystemAssigned"
    }
  }
  
  dynamic "storage_blob_dead_letter_destination" {
    for_each = var.dead_letter_storage_account_id != null ? [1] : []
    content {
      storage_account_id          = var.dead_letter_storage_account_id
      storage_blob_container_name = var.dead_letter_container_name
    }
  }
  
  # Subject filtering (optional)
  dynamic "subject_filter" {
    for_each = var.enable_subject_filtering ? [1] : []
    content {
      subject_begins_with = var.subject_begins_with
      subject_ends_with   = var.subject_ends_with
      case_sensitive      = var.subject_case_sensitive
    }
  }
  
  depends_on = [azurerm_eventgrid_system_topic.storage]
}

# Locals for outputs
locals {
  subscription_full_id = azurerm_eventgrid_system_topic_event_subscription.blob_events.id
}