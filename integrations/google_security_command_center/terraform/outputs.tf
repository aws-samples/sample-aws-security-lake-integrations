/**
 * Terraform Outputs for Google Security Command Center Integration
 * 
 * These outputs provide essential information about the created GCP resources
 * for integration with AWS Security Lake.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# Project Information
# ============================================================================

output "project_id" {
  description = "GCP Project ID"
  value       = var.gcp_project_id
}

output "project_number" {
  description = "GCP Project Number"
  value       = data.google_project.project.number
}

output "organization_id" {
  description = "GCP Organization ID"
  value       = var.gcp_organization_id
}

# ============================================================================
# Pub/Sub Topic Outputs
# ============================================================================

output "pubsub_topic_name" {
  description = "Name of the Pub/Sub topic for SCC findings"
  value       = google_pubsub_topic.scc_findings.name
}

output "pubsub_topic_id" {
  description = "Full resource ID of the Pub/Sub topic"
  value       = google_pubsub_topic.scc_findings.id
}

output "pubsub_topic_path" {
  description = "Full path to the Pub/Sub topic"
  value       = "projects/${var.gcp_project_id}/topics/${google_pubsub_topic.scc_findings.name}"
}

# ============================================================================
# Pub/Sub Subscription Outputs
# ============================================================================

output "pubsub_subscription_name" {
  description = "Name of the Pub/Sub subscription for AWS Lambda"
  value       = google_pubsub_subscription.scc_findings_subscription.name
}

output "pubsub_subscription_id" {
  description = "Full resource ID of the Pub/Sub subscription"
  value       = google_pubsub_subscription.scc_findings_subscription.id
}

output "pubsub_subscription_path" {
  description = "Full path to the Pub/Sub subscription"
  value       = "projects/${var.gcp_project_id}/subscriptions/${google_pubsub_subscription.scc_findings_subscription.name}"
}

# ============================================================================
# Dead Letter Queue Outputs
# ============================================================================

output "pubsub_dlq_topic_name" {
  description = "Name of the dead letter queue topic (if enabled)"
  value       = var.enable_dead_letter_queue ? google_pubsub_topic.scc_findings_dlq[0].name : null
}

output "pubsub_dlq_topic_id" {
  description = "Full resource ID of the DLQ topic (if enabled)"
  value       = var.enable_dead_letter_queue ? google_pubsub_topic.scc_findings_dlq[0].id : null
}

# ============================================================================
# Service Account Outputs
# ============================================================================

output "service_account_email" {
  description = "Email address of the service account for AWS integration"
  value       = google_service_account.aws_integration.email
}

output "service_account_id" {
  description = "Unique ID of the service account"
  value       = google_service_account.aws_integration.unique_id
}

output "service_account_name" {
  description = "Name of the service account"
  value       = google_service_account.aws_integration.name
}

output "service_account_key_name" {
  description = "Name of the service account key"
  value       = google_service_account_key.aws_integration_key.name
}

output "service_account_private_key" {
  description = "Private key for the service account (base64 encoded)"
  value       = google_service_account_key.aws_integration_key.private_key
  sensitive   = true
}

output "service_account_public_key" {
  description = "Public key for the service account"
  value       = google_service_account_key.aws_integration_key.public_key
}

# ============================================================================
# Security Command Center Outputs
# ============================================================================

output "scc_notification_config_id" {
  description = "ID of the SCC notification configuration (if created)"
  value       = var.create_scc_notification ? google_scc_notification_config.scc_findings_notification[0].config_id : null
}

output "scc_notification_name" {
  description = "Full name of the SCC notification configuration (if created)"
  value       = var.create_scc_notification ? google_scc_notification_config.scc_findings_notification[0].name : null
}

output "scc_findings_filter" {
  description = "Filter applied to SCC findings"
  value       = var.scc_findings_filter
}

# ============================================================================
# Secret Manager Outputs
# ============================================================================

output "secret_manager_secret_id" {
  description = "Secret Manager secret ID (if enabled)"
  value       = var.store_key_in_secret_manager ? google_secret_manager_secret.service_account_key[0].secret_id : null
}

output "secret_manager_secret_name" {
  description = "Full name of the Secret Manager secret (if enabled)"
  value       = var.store_key_in_secret_manager ? google_secret_manager_secret.service_account_key[0].name : null
}

# ============================================================================
# Integration Configuration for AWS
# ============================================================================

output "aws_lambda_configuration" {
  description = "Configuration details needed for AWS Lambda setup"
  value = {
    gcp_project_id      = var.gcp_project_id
    subscription_id     = google_pubsub_subscription.scc_findings_subscription.name
    subscription_path   = "projects/${var.gcp_project_id}/subscriptions/${google_pubsub_subscription.scc_findings_subscription.name}"
    service_account_email = google_service_account.aws_integration.email
  }
}

output "integration_summary" {
  description = "Summary of the GCP integration setup"
  value = {
    project_id                = var.gcp_project_id
    project_number            = data.google_project.project.number
    organization_id           = var.gcp_organization_id
    pubsub_topic              = google_pubsub_topic.scc_findings.name
    pubsub_subscription       = google_pubsub_subscription.scc_findings_subscription.name
    service_account           = google_service_account.aws_integration.email
    scc_notification_enabled  = var.create_scc_notification
    dead_letter_queue_enabled = var.enable_dead_letter_queue
    environment               = var.environment
  }
}

# ============================================================================
# Instructions Output
# ============================================================================

output "next_steps" {
  description = "Next steps for completing the integration"
  value = <<-EOT
    
    ========================================
    GCP Security Command Center Integration
    ========================================
    
    1. Service Account Key Setup:
       - The service account key has been generated
       - Store the private key in AWS Secrets Manager
       - Use the 'service_account_private_key' output (marked sensitive)
       
    2. AWS Lambda Configuration:
       - GCP Project ID: ${var.gcp_project_id}
       - Subscription Path: projects/${var.gcp_project_id}/subscriptions/${google_pubsub_subscription.scc_findings_subscription.name}
       - Service Account: ${google_service_account.aws_integration.email}
       
    3. Retrieve Service Account Key:
       terraform output -raw service_account_private_key | base64 -d
       
    4. Test the Integration:
       - Ensure SCC findings are being published to Pub/Sub
       - Verify AWS Lambda can poll the subscription
       - Check CloudWatch logs for any errors
       
    5. Security Considerations:
       - Rotate service account keys regularly
       - Monitor subscription metrics in GCP Console
       - Set up alerting for failed message deliveries
    
    ========================================
  EOT
}