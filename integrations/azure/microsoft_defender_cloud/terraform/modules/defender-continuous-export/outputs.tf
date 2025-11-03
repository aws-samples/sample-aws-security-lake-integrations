/**
 * Microsoft Defender Continuous Export Module Outputs
 * 
 * This file defines the outputs that will be returned from the module.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# CONTINUOUS EXPORT OUTPUTS
# ============================================================================

output "automation_id" {
  description = "The ID of the Security Center automation"
  value       = azurerm_security_center_automation.defender_export.id
}

output "automation_name" {
  description = "The name of the Security Center automation"
  value       = azurerm_security_center_automation.defender_export.name
}

output "automation_location" {
  description = "The location of the Security Center automation"
  value       = azurerm_security_center_automation.defender_export.location
}

output "subscription_scope" {
  description = "The subscription scope where the automation is applied"
  value       = data.azurerm_subscription.current.id
}

output "configuration" {
  description = "Configuration details of the continuous export"
  value = {
    name          = azurerm_security_center_automation.defender_export.name
    location      = azurerm_security_center_automation.defender_export.location
    subscription  = data.azurerm_subscription.current.id
    eventhub_id   = var.eventhub_id
    data_sources  = ["Alerts", "Assessments", "SecureScores", "RegulatoryComplianceAssessment"]
  }
}