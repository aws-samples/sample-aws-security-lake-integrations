"""
GCP Pub/Sub Poller Lambda Function

This Lambda function polls GCP Security Command Center findings from Pub/Sub
subscriptions and forwards them to SQS for further processing.

Key Features:
- Authenticates to GCP using service account credentials from AWS Secrets Manager
- Polls Pub/Sub subscription for new findings
- Maintains processing state using DynamoDB cursors
- Forwards findings to SQS for transformation
- Handles errors and implements retry logic

Author: SecureSight Team
Version: 1.0.0
"""

__version__ = '1.0.0'