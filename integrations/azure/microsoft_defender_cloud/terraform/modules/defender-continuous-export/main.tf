/**
 * Microsoft Defender Continuous Export Module
 * 
 * This module configures Microsoft Defender for Cloud continuous export
 * to send security data to an Event Hub.
 * 
 * Features:
 * - Automatic continuous export configuration
 * - Exports security alerts, assessments, scores, and compliance data
 * - Subscription-level scope
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

# Data source to get the current subscription
data "azurerm_subscription" "current" {}

# Microsoft Defender Continuous Export to Event Hub
resource "azurerm_security_center_automation" "defender_export" {
  name                = "exportToEventHub"
  location            = var.location
  resource_group_name = var.resource_group_name
  
  # Scopes: Apply to the entire subscription
  scopes = [data.azurerm_subscription.current.id]
  
  # Action: Export to Event Hub
  action {
    type              = "eventhub"
    resource_id       = var.eventhub_id
    connection_string = var.eventhub_connection_string
  }
  
  # Source: Export security alerts
  source {
    event_source = "Alerts"
    rule_set {
      rule {
        property_path  = "properties.metadata.severity"
        operator       = "Equals"
        expected_value = "High"
        property_type  = "String"
      }
      rule {
        property_path  = "properties.metadata.severity"
        operator       = "Equals"
        expected_value = "Medium"
        property_type  = "String"
      }
      rule {
        property_path  = "properties.metadata.severity"
        operator       = "Equals"
        expected_value = "Low"
        property_type  = "String"
      }
    }
  }
  
  # Source: Export security assessments (recommendations)
  source {
    event_source = "Assessments"
    rule_set {
      rule {
        property_path  = "type"
        operator       = "Contains"
        expected_value = "Microsoft.Security/assessments"
        property_type  = "String"
      }
    }
  }
  
  # Source: Export secure score
  source {
    event_source = "SecureScores"
  }
  
  # Source: Export regulatory compliance
  source {
    event_source = "RegulatoryComplianceAssessment"
  }
  
  tags = var.tags
}