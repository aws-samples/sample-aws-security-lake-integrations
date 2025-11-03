/**
 * Terraform Variables for Google Security Command Center Integration
 * 
 * These variables configure the GCP infrastructure for SCC findings
 * integration with AWS Security Lake.
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

# ============================================================================
# Required Variables
# ============================================================================

variable "gcp_project_id" {
  description = "GCP Project ID where resources will be created"
  type        = string
}

variable "gcp_organization_id" {
  description = "GCP Organization ID for Security Command Center configuration"
  type        = string
}

# ============================================================================
# Pub/Sub Configuration
# ============================================================================

variable "pubsub_topic_name" {
  description = "Name of the Pub/Sub topic for SCC findings"
  type        = string
  default     = "scc-findings-topic"
}

variable "pubsub_subscription_name" {
  description = "Name of the Pub/Sub subscription for AWS Lambda"
  type        = string
  default     = "scc-findings-aws-subscription"
}

variable "message_retention_duration" {
  description = "Message retention duration for Pub/Sub topic (e.g., '604800s' for 7 days)"
  type        = string
  default     = "604800s"
}

variable "subscription_message_retention_duration" {
  description = "Message retention duration for subscription (e.g., '604800s' for 7 days)"
  type        = string
  default     = "604800s"
}

variable "ack_deadline_seconds" {
  description = "The maximum time after a subscriber receives a message before the subscriber should acknowledge"
  type        = number
  default     = 600
}

variable "retain_acked_messages" {
  description = "Whether to retain acknowledged messages"
  type        = bool
  default     = false
}

variable "enable_message_ordering" {
  description = "Whether to enable message ordering"
  type        = bool
  default     = false
}

variable "subscription_expiration_ttl" {
  description = "TTL for subscription expiration if inactive (empty string for never expire)"
  type        = string
  default     = ""
}

variable "retry_minimum_backoff" {
  description = "Minimum backoff for retry policy"
  type        = string
  default     = "10s"
}

variable "retry_maximum_backoff" {
  description = "Maximum backoff for retry policy"
  type        = string
  default     = "600s"
}

variable "enable_dead_letter_queue" {
  description = "Whether to enable dead letter queue for undeliverable messages"
  type        = bool
  default     = true
}

variable "max_delivery_attempts" {
  description = "Maximum number of delivery attempts before sending to DLQ"
  type        = number
  default     = 5
}

variable "allowed_persistence_regions" {
  description = "List of regions where messages can be persisted (null for default)"
  type        = list(string)
  default     = null
}

# ============================================================================
# Service Account Configuration
# ============================================================================

variable "service_account_name" {
  description = "Name of the service account for AWS integration"
  type        = string
  default     = "aws-security-lake-integration"
}

variable "service_account_display_name" {
  description = "Display name for the service account"
  type        = string
  default     = "AWS Security Lake Integration Service Account"
}

# ============================================================================
# Security Command Center Configuration
# ============================================================================

variable "create_scc_notification" {
  description = "Whether to create SCC notification configuration"
  type        = bool
  default     = true
}

variable "scc_notification_config_id" {
  description = "Unique identifier for the SCC notification configuration"
  type        = string
  default     = "scc-findings-to-aws-security-lake"
}

variable "scc_findings_filter" {
  description = "Filter expression for SCC findings to publish (empty for all findings)"
  type        = string
  default     = ""
}

# ============================================================================
# API Configuration
# ============================================================================

variable "enable_scc_api" {
  description = "Whether to enable Security Command Center API"
  type        = bool
  default     = true
}

variable "enable_pubsub_api" {
  description = "Whether to enable Pub/Sub API"
  type        = bool
  default     = true
}

# ============================================================================
# Secret Manager Configuration
# ============================================================================

variable "store_key_in_secret_manager" {
  description = "Whether to store service account key in GCP Secret Manager"
  type        = bool
  default     = false
}

variable "secret_manager_secret_id" {
  description = "Secret ID for storing service account key in Secret Manager"
  type        = string
  default     = "aws-integration-service-account-key"
}

# ============================================================================
# Regional Configuration
# ============================================================================

variable "gcp_region" {
  description = "GCP region for regional resources"
  type        = string
  default     = "us-central1"
}

# ============================================================================
# Labeling
# ============================================================================

variable "labels" {
  description = "Labels to apply to all resources"
  type        = map(string)
  default = {
    environment = "production"
    managed_by  = "terraform"
    integration = "aws-security-lake"
  }
}

# ============================================================================
# Environment Configuration
# ============================================================================

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "gcp-scc-aws-securitylake"
}