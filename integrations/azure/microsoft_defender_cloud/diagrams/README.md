# Architecture Diagrams - Microsoft Defender CloudTrail Integration

This directory contains visual architecture diagrams for the Microsoft Defender for Cloud CloudTrail integration solution. These diagrams provide a comprehensive view of the cross-cloud integration architecture, data flow, and component relationships.

## Diagram Overview

### 1. Overall Architecture (`01_overall_architecture.png`)

**Purpose**: Provides a complete high-level view of the cross-cloud integration architecture.

**Components Shown**:
- **Azure Cloud**: Microsoft Defender for Cloud and Azure Event Hub infrastructure
- **Cross-Cloud Integration**: Connection points between Azure and AWS
- **AWS Cloud**: Complete AWS infrastructure including Lambda functions, queues, and CloudTrail
- **Monitoring**: CloudWatch monitoring and alerting components

**Use Case**: Understanding the complete solution architecture for stakeholders, architects, and operations teams.

### 2. Data Flow (`02_data_flow.png`)

**Purpose**: Illustrates the step-by-step data processing pipeline from Microsoft Defender events to CloudTrail storage.

**Flow Stages**:
1. Microsoft Defender continuous export to Azure Event Hub
2. AWS Lambda credential retrieval and Event Hub polling
3. Event processing and state management in DynamoDB
4. Message queuing through SQS
5. Event transformation to CloudTrail format
6. CloudTrail Channel delivery to Event Data Store

**Use Case**: Understanding data processing workflow, troubleshooting data flow issues, and optimizing processing performance.

### 3. AWS Components (`03_aws_components.png`)

**Purpose**: Detailed view of AWS infrastructure components and their relationships.

**Components Detailed**:
- **Infrastructure Layer**: KMS keys and Secrets Manager
- **Data Storage**: DynamoDB CheckpointStore and SQS queues
- **Processing Layer**: Event Hub Processor and Event Transformer Lambda functions
- **CloudTrail Layer**: CloudTrail Channel and Event Data Store
- **Monitoring Layer**: CloudWatch logs, alarms, and metrics

**Use Case**: AWS infrastructure planning, resource configuration, and operational monitoring setup.

### 4. Azure Components (`04_azure_components.png`)

**Purpose**: Detailed view of Azure infrastructure components required for the integration.

**Components Detailed**:
- **Microsoft Security Services**: Microsoft Defender for Cloud
- **Azure Event Hub Infrastructure**: Resource Group, Event Hub Namespace, and Event Hub
- **Integration Configuration**: Continuous export setup and connection string management

**Use Case**: Azure infrastructure planning, Event Hub configuration, and Microsoft Defender setup.

### 5. Integration Flow (`05_integration_flow.png`)

**Purpose**: Sequential view of the integration process showing step-by-step component interactions.

**Process Steps**:
1. Azure Event Hub polling by AWS Lambda
2. Checkpoint state updates in DynamoDB
3. Event queuing in SQS
4. SQS trigger for transformation Lambda
5. CloudTrail format conversion and delivery

**Use Case**: Understanding operational flow, debugging integration issues, and monitoring processing stages.

## Diagram Generation

### Prerequisites

```bash
pip install diagrams
```

### Regenerating Diagrams

```bash
# From the integration root directory
cd integrations/azure/microsoft_defender_cloud

# Run the diagram generation script
python architecture_diagrams.py
```

### Customizing Diagrams

The diagrams are generated from [`architecture_diagrams.py`](../architecture_diagrams.py). To customize:

1. Edit the Python script to modify components, layouts, or styling
2. Run the generation script to create updated diagrams
3. Commit both the script changes and generated PNG files

## Using the Diagrams

### Documentation Integration

These diagrams are referenced in:
- **Solution README**: Overall architecture context
- **Component READMEs**: Specific component relationships
- **Deployment Guides**: Visual deployment workflow
- **Configuration Documentation**: Infrastructure context for configuration decisions

### Presentation and Communication

- **Stakeholder Reviews**: Use overall architecture diagram for executive briefings
- **Technical Reviews**: Use component diagrams for detailed technical discussions
- **Troubleshooting**: Use data flow diagram for operational issue resolution
- **Training**: Use integration flow diagram for team training and onboarding

### Maintenance

- **Regular Updates**: Regenerate diagrams when architecture changes
- **Version Control**: Keep diagrams in sync with code and documentation updates
- **Quality Assurance**: Verify diagrams accurately represent actual implementation

## Diagram Specifications

**Format**: PNG (Portable Network Graphics)
**Resolution**: High resolution suitable for presentations and documentation
**Style**: Clean, professional styling with consistent color coding
**Labels**: Clear, descriptive component names and relationship labels
**Layout**: Logical flow from left to right or top to bottom based on data processing sequence

## Integration with Documentation

These visual diagrams complement the written documentation:

- **[Solution README](../README.md)**: References overall architecture diagram
- **[CDK Documentation](../cdk/README.md)**: References AWS components diagram
- **[Terraform Documentation](../terraform/README.md)**: References Azure components diagram
- **[Configuration Guide](../cdk/CONFIGURATION.md)**: Uses diagrams to explain infrastructure context

The combination of visual architecture diagrams and comprehensive written documentation provides complete understanding of the Microsoft Defender CloudTrail integration solution.