/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

/**
 * Event Grid Subscription Module Outputs
 * 
 * This file defines the outputs returned from the Event Grid subscription module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# SYSTEM TOPIC OUTPUTS
# ============================================================================

output "system_topic_id" {
  description = "The ID of the Event Grid system topic"
  value       = azurerm_eventgrid_system_topic.storage.id
}

output "system_topic_name" {
  description = "The name of the Event Grid system topic"
  value       = azurerm_eventgrid_system_topic.storage.name
}

output "system_topic_type" {
  description = "The topic type of the Event Grid system topic"
  value       = azurerm_eventgrid_system_topic.storage.topic_type
}

# ============================================================================
# SUBSCRIPTION OUTPUTS
# ============================================================================

output "subscription_id" {
  description = "The ID of the Event Grid subscription"
  value       = azurerm_eventgrid_system_topic_event_subscription.blob_events.id
}

output "subscription_name" {
  description = "The name of the Event Grid subscription"
  value       = azurerm_eventgrid_system_topic_event_subscription.blob_events.name
}

output "event_delivery_schema" {
  description = "The event delivery schema used by the subscription"
  value       = azurerm_eventgrid_system_topic_event_subscription.blob_events.event_delivery_schema
}

# ============================================================================
# CONFIGURATION OUTPUTS
# ============================================================================

output "included_event_types" {
  description = "List of event types included in the subscription"
  value       = azurerm_eventgrid_system_topic_event_subscription.blob_events.included_event_types
}

output "eventhub_endpoint_id" {
  description = "The Event Hub endpoint ID configured for this subscription"
  value       = azurerm_eventgrid_system_topic_event_subscription.blob_events.eventhub_endpoint_id
}

output "storage_account_id" {
  description = "The storage account ID being monitored"
  value       = var.storage_account_id
}

# ============================================================================
# STATUS OUTPUTS
# ============================================================================

output "configuration_summary" {
  description = "Summary of Event Grid subscription configuration"
  value = {
    system_topic_name     = azurerm_eventgrid_system_topic.storage.name
    subscription_name     = azurerm_eventgrid_system_topic_event_subscription.blob_events.name
    event_schema          = azurerm_eventgrid_system_topic_event_subscription.blob_events.event_delivery_schema
    monitored_resource    = var.storage_account_id
    endpoint_type         = "Event Hub"
    endpoint_id           = var.eventhub_id
    event_types           = ["Microsoft.Storage.BlobCreated"]
    max_delivery_attempts = var.max_delivery_attempts
    event_ttl_minutes     = var.event_time_to_live_minutes
  }
}