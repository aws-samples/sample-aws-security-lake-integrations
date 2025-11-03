/**
 * Google Security Command Center - GCP Infrastructure
 * 
 * This Terraform configuration creates GCP resources for Security Command Center
 * integration with AWS Security Lake:
 * - Pub/Sub topic for SCC findings
 * - Pub/Sub subscription for AWS Lambda polling
 * - Service account for AWS authentication
 * - IAM bindings for secure access
 * 
 * Author: SecureSight Team
 * Version: 1.0.0
 */

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Create Pub/Sub topic for Security Command Center findings
resource "google_pubsub_topic" "scc_findings" {
  name    = var.pubsub_topic_name
  project = var.gcp_project_id

  labels = merge(
    var.labels,
    {
      purpose = "security-findings"
      source  = "google-scc"
    }
  )

  message_retention_duration = var.message_retention_duration

  # Enable message ordering if required
  dynamic "message_storage_policy" {
    for_each = var.allowed_persistence_regions != null ? [1] : []
    content {
      allowed_persistence_regions = var.allowed_persistence_regions
    }
  }
}

# Create Pub/Sub subscription for AWS Lambda to poll
resource "google_pubsub_subscription" "scc_findings_subscription" {
  name    = var.pubsub_subscription_name
  topic   = google_pubsub_topic.scc_findings.name
  project = var.gcp_project_id

  labels = merge(
    var.labels,
    {
      consumer = "aws-lambda"
      purpose  = "security-lake-integration"
    }
  )

  # Message retention duration
  message_retention_duration = var.subscription_message_retention_duration

  # Acknowledgement deadline
  ack_deadline_seconds = var.ack_deadline_seconds

  # Retain acknowledged messages
  retain_acked_messages = var.retain_acked_messages

  # Enable message ordering
  enable_message_ordering = var.enable_message_ordering

  # Expiration policy - subscription expires if inactive
  expiration_policy {
    ttl = var.subscription_expiration_ttl
  }

  # Retry policy
  retry_policy {
    minimum_backoff = var.retry_minimum_backoff
    maximum_backoff = var.retry_maximum_backoff
  }

  # Dead letter policy (optional)
  dynamic "dead_letter_policy" {
    for_each = var.enable_dead_letter_queue ? [1] : []
    content {
      dead_letter_topic     = google_pubsub_topic.scc_findings_dlq[0].id
      max_delivery_attempts = var.max_delivery_attempts
    }
  }
}

# Create dead letter queue topic (optional)
resource "google_pubsub_topic" "scc_findings_dlq" {
  count   = var.enable_dead_letter_queue ? 1 : 0
  name    = "${var.pubsub_topic_name}-dlq"
  project = var.gcp_project_id

  labels = merge(
    var.labels,
    {
      purpose = "dead-letter-queue"
      source  = "google-scc"
    }
  )
}

# Create service account for AWS authentication
resource "google_service_account" "aws_integration" {
  account_id   = var.service_account_name
  display_name = var.service_account_display_name
  description  = "Service account for AWS Security Lake integration with GCP Security Command Center"
  project      = var.gcp_project_id
}

# Grant Pub/Sub Subscriber role to service account
resource "google_pubsub_subscription_iam_member" "subscriber" {
  subscription = google_pubsub_subscription.scc_findings_subscription.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.aws_integration.email}"
  project      = var.gcp_project_id
}

# Grant Pub/Sub Viewer role to service account (for subscription management)
resource "google_pubsub_subscription_iam_member" "viewer" {
  subscription = google_pubsub_subscription.scc_findings_subscription.name
  role         = "roles/pubsub.viewer"
  member       = "serviceAccount:${google_service_account.aws_integration.email}"
  project      = var.gcp_project_id
}

# Create service account key for AWS Lambda authentication
resource "google_service_account_key" "aws_integration_key" {
  service_account_id = google_service_account.aws_integration.name
  public_key_type    = "TYPE_X509_PEM_FILE"
}

# Configure Security Command Center notification to publish to Pub/Sub topic
resource "google_scc_notification_config" "scc_findings_notification" {
  count        = var.create_scc_notification ? 1 : 0
  config_id    = var.scc_notification_config_id
  organization = var.gcp_organization_id
  description  = "Send Security Command Center findings to Pub/Sub for AWS Security Lake"
  pubsub_topic = google_pubsub_topic.scc_findings.id

  streaming_config {
    filter = var.scc_findings_filter
  }
}

# Grant Security Command Center permission to publish to topic
resource "google_pubsub_topic_iam_member" "scc_publisher" {
  count   = var.create_scc_notification ? 1 : 0
  topic   = google_pubsub_topic.scc_findings.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-scc-notification.iam.gserviceaccount.com"
  project = var.gcp_project_id
}

# Data source to get project number
data "google_project" "project" {
  project_id = var.gcp_project_id
}

# Optional: Enable Security Command Center API
resource "google_project_service" "scc_api" {
  count   = var.enable_scc_api ? 1 : 0
  project = var.gcp_project_id
  service = "securitycenter.googleapis.com"

  disable_on_destroy = false
}

# Optional: Enable Pub/Sub API
resource "google_project_service" "pubsub_api" {
  count   = var.enable_pubsub_api ? 1 : 0
  project = var.gcp_project_id
  service = "pubsub.googleapis.com"

  disable_on_destroy = false
}

# Store service account key in Google Secret Manager (optional)
resource "google_secret_manager_secret" "service_account_key" {
  count     = var.store_key_in_secret_manager ? 1 : 0
  secret_id = var.secret_manager_secret_id
  project   = var.gcp_project_id

  labels = merge(
    var.labels,
    {
      purpose = "aws-integration"
      type    = "service-account-key"
    }
  )

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "service_account_key_version" {
  count       = var.store_key_in_secret_manager ? 1 : 0
  secret      = google_secret_manager_secret.service_account_key[0].id
  secret_data = base64decode(google_service_account_key.aws_integration_key.private_key)
}