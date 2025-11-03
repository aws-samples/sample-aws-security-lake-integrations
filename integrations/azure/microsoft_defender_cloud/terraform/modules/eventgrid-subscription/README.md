/**
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
 * http://aws.amazon.com/agreement or other written agreement between Customer and either
 * Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 */

# Event Grid Subscription Module

This Terraform module creates an Azure Event Grid subscription that monitors storage account blob events and forwards them to an Event Hub endpoint.

## Features

- **Event Grid System Topic**: Creates a system topic for storage account events
- **Cloud Event Schema v1.0**: Uses the modern Cloud Event Schema format
- **Blob Created Events**: Filters to capture only blob creation events
- **Event Hub Integration**: Forwards events directly to an Event Hub
- **Retry Policy**: Configurable retry and dead letter handling
- **Advanced Filtering**: Optional subject and property-based filtering

## Architecture

```
Storage Account (Flow Logs)
  └─> Event Grid System Topic
       └─> Event Grid Subscription (Cloud Event Schema v1.0)
            └─> Event Hub (endpoint)
```

## Usage

### Basic Usage

```hcl
module "eventgrid_subscription" {
  source = "./modules/eventgrid-subscription"
  
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  storage_account_id  = azurerm_storage_account.flow_logs.id
  eventhub_id         = module.eventhub.eventhub_id
  
  tags = local.common_tags
}
```

### Advanced Usage with Filtering

```hcl
module "eventgrid_subscription" {
  source = "./modules/eventgrid-subscription"
  
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  storage_account_id  = azurerm_storage_account.flow_logs.id
  eventhub_id         = module.eventhub.eventhub_id
  
  # Custom naming
  system_topic_name  = "flowlogs-events"
  subscription_name  = "flowlogs-to-hub"
  
  # Enable advanced filtering for specific blob paths
  enable_advanced_filtering = true
  blob_type_filters = [
    "/blobServices/default/containers/insights-logs-networksecuritygroupflowevent/"
  ]
  
  # Subject filtering
  enable_subject_filtering = true
  subject_begins_with     = "/blobServices/default/containers/"
  subject_ends_with       = ".json"
  
  # Dead letter configuration
  dead_letter_storage_account_id = azurerm_storage_account.deadletter.id
  dead_letter_container_name     = "eventgrid-failed-events"
  
  # Retry configuration
  max_delivery_attempts      = 10
  event_time_to_live_minutes = 720  # 12 hours
  
  tags = local.common_tags
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| resource_group_name | Name of the resource group | `string` | n/a | yes |
| location | Azure region | `string` | n/a | yes |
| storage_account_id | Storage account resource ID to monitor | `string` | n/a | yes |
| eventhub_id | Event Hub resource ID for endpoint | `string` | n/a | yes |
| system_topic_name | Name for the Event Grid system topic | `string` | `"flowlogs-storage-events"` | no |
| subscription_name | Name for the Event Grid subscription | `string` | `"blob-created-to-eventhub"` | no |
| enable_advanced_filtering | Enable advanced property filtering | `bool` | `false` | no |
| blob_type_filters | List of blob path prefixes to filter | `list(string)` | `[]` | no |
| enable_subject_filtering | Enable subject-based filtering | `bool` | `false` | no |
| subject_begins_with | Subject filter - begins with pattern | `string` | `""` | no |
| subject_ends_with | Subject filter - ends with pattern | `string` | `""` | no |
| subject_case_sensitive | Subject filtering case sensitivity | `bool` | `false` | no |
| max_delivery_attempts | Maximum delivery attempts | `number` | `30` | no |
| event_time_to_live_minutes | Event TTL in minutes | `number` | `1440` | no |
| dead_letter_storage_account_id | Dead letter storage account ID | `string` | `null` | no |
| dead_letter_container_name | Dead letter container name | `string` | `"eventgrid-deadletter"` | no |
| tags | Tags to apply to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| system_topic_id | Event Grid system topic ID |
| system_topic_name | Event Grid system topic name |
| subscription_id | Event Grid subscription ID |
| subscription_name | Event Grid subscription name |
| event_delivery_schema | Event delivery schema (CloudEventSchemaV1_0) |
| included_event_types | List of monitored event types |
| eventhub_endpoint_id | Event Hub endpoint ID |
| configuration_summary | Complete configuration summary |

## Event Schema

Events are delivered using **Cloud Event Schema v1.0**:

```json
{
  "specversion": "1.0",
  "type": "Microsoft.Storage.BlobCreated",
  "source": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Storage/storageAccounts/{account}",
  "id": "event-id",
  "time": "2025-10-20T14:30:00Z",
  "subject": "/blobServices/default/containers/{container}/blobs/{blob}",
  "dataschema": "https://...",
  "datacontenttype": "application/json",
  "data": {
    "api": "PutBlob",
    "clientRequestId": "...",
    "requestId": "...",
    "eTag": "...",
    "contentType": "application/json",
    "contentLength": 1234,
    "blobType": "BlockBlob",
    "url": "https://...",
    "sequencer": "...",
    "storageDiagnostics": {...}
  }
}
```

## Event Types

The subscription is configured to monitor:

- **Microsoft.Storage.BlobCreated**: Triggered when a new blob is created in the storage account

This is ideal for monitoring flow log files as they are written to storage.

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.0 |
| azurerm | ~> 4.12 |

## Notes

- Event Grid system topics are free; you only pay for event delivery
- Cloud Event Schema v1.0 is recommended for modern event-driven architectures
- Dead letter configuration requires a separate storage account and container
- Maximum delivery attempts range: 1-30
- Event TTL range: 1-1440 minutes (24 hours max)

## Author

SecureSight Team

## Version

1.0.0