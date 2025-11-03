#!/usr/bin/env python3
"""
Microsoft Defender for Cloud - CloudTrail Integration Architecture Diagrams

This script generates architecture diagrams for the complete cross-cloud integration
using the Python diagrams library. Run this script to generate PNG diagrams.

Requirements:
    pip install diagrams

Usage:
    python architecture_diagrams.py
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.azure.security import SecurityCenter
from diagrams.azure.analytics import EventHubs
from diagrams.azure.general import Resourcegroups
from diagrams.aws.compute import Lambda
from diagrams.aws.database import DynamodbTable
from diagrams.aws.integration import SQS
from diagrams.aws.management import Cloudtrail, Cloudwatch
from diagrams.aws.security import SecretsManager, KMS
from diagrams.aws.general import General


def create_overall_architecture():
    """Create overall cross-cloud architecture diagram"""
    
    with Diagram("Microsoft Defender CloudTrail Integration - Overall Architecture", 
                 filename="diagrams/01_overall_architecture", 
                 direction="TB",
                 show=False):
        
        # Azure Cloud Components
        with Cluster("Azure Cloud (Canada Central)"):
            mdc = SecurityCenter("Microsoft Defender\nfor Cloud")
            event_hub = EventHubs("Azure Event Hub\n(Continuous Export)")
            
            mdc >> Edge(label="Security Events") >> event_hub
        
        # Cross-Cloud Integration
        cross_cloud = General("Cross-Cloud\nIntegration")
        event_hub >> Edge(label="Poll Events\n(Every 5 min)") >> cross_cloud
        
        # AWS Cloud Components
        with Cluster("AWS Cloud (ca-central-1)"):
            
            # Event Processing Layer
            with Cluster("Event Processing"):
                secrets = SecretsManager("Azure Credentials\n(Secrets Manager)")
                processor = Lambda("Event Hub\nProcessor")
                checkpoint_db = DynamodbTable("DynamoDB\nCheckpointStore")
                
                secrets >> processor
                processor >> checkpoint_db
            
            # Message Queue Layer  
            with Cluster("Message Processing"):
                sqs = SQS("SQS Queue")
                dlq = SQS("Dead Letter\nQueue")
                transformer = Lambda("Event\nTransformer")
                
                processor >> Edge(label="Azure Events") >> sqs
                sqs >> transformer
                transformer >> Edge(label="Failed Events") >> dlq
            
            # CloudTrail Layer
            with Cluster("CloudTrail Integration"):
                channel = General("CloudTrail\nChannel")
                event_store = Cloudtrail("CloudTrail\nEvent Data Store")
                
                transformer >> Edge(label="CloudTrail Events") >> channel
                channel >> event_store
            
            # Monitoring Layer
            with Cluster("Monitoring"):
                kms = KMS("KMS Key\n(Encryption)")
                logs = Cloudwatch("CloudWatch\nLogs & Alarms")
                
                [processor, transformer] >> logs
                [checkpoint_db, sqs, dlq] >> Edge(style="dashed") >> kms
        
        cross_cloud >> processor


def create_data_flow_diagram():
    """Create detailed data flow diagram"""
    
    with Diagram("Microsoft Defender CloudTrail Integration - Data Flow",
                 filename="diagrams/02_data_flow",
                 direction="LR", 
                 show=False):
        
        # Source
        mdc = SecurityCenter("Microsoft Defender")
        
        # Azure Layer
        with Cluster("Azure Event Hub"):
            event_hub = EventHubs("defender-events")
            connection = General("Connection String")
        
        # AWS Processing Layer
        with Cluster("AWS Event Processing"):
            secrets = SecretsManager("Secrets Manager")
            processor = Lambda("Event Hub\nProcessor\n(Scheduled)")
            checkpoint = DynamodbTable("CheckpointStore")
            
            sqs_queue = SQS("Event Queue") 
            transformer = Lambda("Event Transformer\n(SQS Trigger)")
            dlq = SQS("Dead Letter Queue")
        
        # CloudTrail Layer
        with Cluster("CloudTrail Lake"):
            channel = General("CloudTrail Channel")
            data_store = Cloudtrail("Event Data Store")
        
        # Monitoring
        monitoring = Cloudwatch("CloudWatch")
        
        # Data Flow
        mdc >> Edge(label="1. Continuous Export") >> event_hub
        connection >> secrets
        secrets >> Edge(label="2. Retrieve Creds") >> processor
        event_hub >> Edge(label="3. Poll Events") >> processor
        processor >> Edge(label="4. Update State") >> checkpoint
        processor >> Edge(label="5. Forward Events") >> sqs_queue
        sqs_queue >> Edge(label="6. Process Batch") >> transformer
        transformer >> Edge(label="7. Failed Messages") >> dlq
        transformer >> Edge(label="8. CloudTrail Format") >> channel
        channel >> Edge(label="9. External Events") >> data_store
        
        [processor, transformer] >> Edge(label="Logs", style="dashed") >> monitoring


def create_aws_components_diagram():
    """Create AWS components detail diagram"""
    
    with Diagram("AWS Components - Microsoft Defender CloudTrail Integration",
                 filename="diagrams/03_aws_components", 
                 direction="TB",
                 show=False):
        
        # Infrastructure Layer
        with Cluster("Infrastructure & Security"):
            kms = KMS("Shared KMS Key")
            secrets = SecretsManager("Azure Credentials")
            
        # Data Storage Layer
        with Cluster("Data Storage"):
            checkpoint_table = DynamodbTable("CheckpointStore\n(Composite Key)")
            sqs_main = SQS("Main Queue\n(4-day retention)")
            sqs_dlq = SQS("Dead Letter Queue\n(14-day retention)")
        
        # Processing Layer
        with Cluster("Event Processing"):
            event_processor = Lambda("Event Hub Processor\n- Python 3.11\n- 512MB RAM\n- 5min timeout\n- Reserved: 1")
            transformer = Lambda("Event Transformer\n- Python 3.11\n- 512MB RAM\n- 1min timeout\n- Reserved: 10")
        
        # CloudTrail Layer
        with Cluster("CloudTrail Lake"):
            channel = General("External Event Channel")
            event_data_store = Cloudtrail("Event Data Store\n(90-day retention)")
        
        # Monitoring Layer
        with Cluster("Monitoring & Alerting"):
            cloudwatch = Cloudwatch("CloudWatch\n- Logs\n- Alarms\n- Metrics")
        
        # Connections
        secrets >> event_processor
        event_processor >> checkpoint_table
        event_processor >> sqs_main
        sqs_main >> transformer
        transformer >> sqs_dlq
        transformer >> channel
        channel >> event_data_store
        
        [event_processor, transformer] >> cloudwatch
        kms >> Edge(style="dashed", label="Encrypts") >> [checkpoint_table, sqs_main, sqs_dlq]


def create_azure_components_diagram():
    """Create Azure components detail diagram"""
    
    with Diagram("Azure Components - Microsoft Defender CloudTrail Integration",
                 filename="diagrams/04_azure_components",
                 direction="TB", 
                 show=False):
        
        # Microsoft Services
        with Cluster("Microsoft Security Services"):
            defender = SecurityCenter("Microsoft Defender\nfor Cloud")
            
        # Azure Infrastructure
        with Cluster("Azure Event Hub Infrastructure"):
            resource_group = Resourcegroups("Resource Group")
            event_hub_namespace = EventHubs("Event Hub Namespace\n(Standard SKU)")
            event_hub = EventHubs("Event Hub\n- 4 Partitions\n- 1-day retention\n- Auto-scaling")
        
        # Configuration
        with Cluster("Integration Configuration"):
            continuous_export = General("Continuous Export\nConfiguration")
            connection_string = General("Connection String\n(Shared Access Key)")
        
        # Data Flow
        defender >> Edge(label="Security Events") >> continuous_export
        continuous_export >> event_hub
        event_hub >> event_hub_namespace
        event_hub_namespace >> resource_group
        
        # Integration Points
        connection_string >> Edge(label="Stored in\nAWS Secrets Manager", style="dashed") >> General("AWS Integration")


def create_integration_flow_diagram():
    """Create integration flow sequence diagram"""
    
    with Diagram("Integration Flow - Step by Step Process",
                 filename="diagrams/05_integration_flow",
                 direction="LR",
                 show=False):
        
        # Components
        azure_hub = EventHubs("Azure\nEvent Hub")
        aws_processor = Lambda("Event Hub\nProcessor")
        checkpoint_store = DynamodbTable("Checkpoint\nStore")  
        sqs = SQS("SQS\nQueue")
        transformer = Lambda("Event\nTransformer")
        cloudtrail = Cloudtrail("CloudTrail\nData Store")
        
        # Flow
        azure_hub >> Edge(label="1. Poll Events") >> aws_processor
        aws_processor >> Edge(label="2. Update Checkpoint") >> checkpoint_store
        aws_processor >> Edge(label="3. Queue Events") >> sqs
        sqs >> Edge(label="4. Trigger Processing") >> transformer
        transformer >> Edge(label="5. Transform & Send") >> cloudtrail


if __name__ == "__main__":
    print("Generating Microsoft Defender CloudTrail Integration architecture diagrams...")
    
    # Create diagrams directory
    import os
    os.makedirs("diagrams", exist_ok=True)
    
    # Generate all diagrams
    create_overall_architecture()
    print("✓ Generated overall architecture diagram")
    
    create_data_flow_diagram() 
    print("✓ Generated data flow diagram")
    
    create_aws_components_diagram()
    print("✓ Generated AWS components diagram")
    
    create_azure_components_diagram()
    print("✓ Generated Azure components diagram")
    
    create_integration_flow_diagram()
    print("✓ Generated integration flow diagram")
    
    print("\nAll diagrams generated in ./diagrams/ directory")
    print("Files created:")
    print("  - 01_overall_architecture.png")
    print("  - 02_data_flow.png") 
    print("  - 03_aws_components.png")
    print("  - 04_azure_components.png")
    print("  - 05_integration_flow.png")