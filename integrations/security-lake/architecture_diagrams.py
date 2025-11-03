"""
© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
http://aws.amazon.com/agreement or other written agreement between Customer and either
Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

Security Lake Integration Framework - Architecture Diagrams

Generates architecture diagrams using Python diagrams library.
Run: python architecture_diagrams.py
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import SQS, Eventbridge
from diagrams.aws.security import SecretsManager, KMS, SecurityHub, IAM
from diagrams.aws.storage import S3
from diagrams.aws.database import Dynamodb
from diagrams.aws.analytics import Glue, ElasticsearchService
from diagrams.aws.management import Cloudwatch
from diagrams.custom import Custom

# Configure diagram attributes
graph_attr = {
    "fontsize": "12",
    "bgcolor": "white",
    "pad": "0.5"
}

# Diagram 1: Overall Modular Architecture
with Diagram(
    "Security Lake Integration Framework - Modular Architecture",
    filename="diagrams/01_modular_architecture",
    show=False,
    direction="TB",
    graph_attr=graph_attr
):
    # Core Framework
    with Cluster("Core Framework"):
        config_loader = Custom("Config Loader", "./icons/config.png") if False else Lambda("Config Loader")
        module_registry = Custom("Module Registry", "./icons/registry.png") if False else Lambda("Module Registry")
        module_loader = Custom("Module Loader", "./icons/loader.png") if False else Lambda("Module Loader")
        
        with Cluster("Core Processing"):
            event_transformer = Lambda("Event\nTransformer")
            securityhub_processor = Lambda("SecurityHub\nProcessor")
            security_lake_cr = Lambda("Security Lake\nCustom Resource")
        
        with Cluster("Shared Resources"):
            kms_key = KMS("Shared\nKMS Key")
            sqs_queue = SQS("Transformer\nQueue")
            sqs_dlq = SQS("DLQ")
    
    # Integration Modules
    with Cluster("Integration Modules"):
        with Cluster("Azure Module"):
            azure_eventhub = Lambda("Event Hub\nProcessor")
            azure_flowlog = Lambda("Flow Log\nProcessor")
            azure_checkpoint = Dynamodb("Checkpoint\nStore")
        
        with Cluster("Future Modules"):
            guardduty_module = Lambda("GuardDuty\nModule")
            gcp_module = Lambda("GCP SCC\nModule")
    
    # Destinations
    with Cluster("Destinations"):
        security_lake = S3("Security Lake\nS3 Bucket")
        security_hub = SecurityHub("AWS\nSecurity Hub")
        glue_catalog = Glue("Glue Data\nCatalog")
    
    # Visualization Layer
    with Cluster("Visualization Layer"):
        eventbridge = Eventbridge("EventBridge")
        sqs_osi = SQS("OSI\nQueue")
        osi_pipeline = ElasticsearchService("OpenSearch\nIngestion")
        opensearch = ElasticsearchService("OpenSearch\nDomain")
    
    # Flow
    config_loader >> module_registry
    module_registry >> module_loader
    module_loader >> [azure_eventhub, azure_flowlog, guardduty_module, gcp_module]
    
    azure_eventhub >> Edge(label="events") >> sqs_queue
    azure_flowlog >> Edge(label="flow logs") >> sqs_queue
    guardduty_module >> Edge(label="findings") >> sqs_queue
    gcp_module >> Edge(label="findings") >> sqs_queue
    
    sqs_queue >> event_transformer
    sqs_queue >> Edge(label="failed", style="dashed") >> sqs_dlq
    
    event_transformer >> Edge(label="OCSF") >> security_lake
    event_transformer >> Edge(label="ASFF") >> securityhub_processor
    
    securityhub_processor >> security_hub
    security_lake_cr >> [security_lake, glue_catalog]
    
    # Visualization flow
    security_lake >> Edge(label="S3 events") >> eventbridge
    eventbridge >> sqs_osi >> osi_pipeline
    osi_pipeline >> Edge(label="OCSF data") >> opensearch
    
    kms_key >> Edge(style="dotted", label="encrypts") >> [sqs_queue, sqs_dlq, azure_checkpoint]

# Diagram 2: Data Flow Architecture
with Diagram(
    "Security Lake Integration Framework - Data Flow",
    filename="diagrams/02_data_flow",
    show=False,
    direction="LR",
    graph_attr=graph_attr
):
    # External Sources
    with Cluster("External Data Sources"):
        azure_defender = Custom("Azure Defender", "./icons/azure.png") if False else Lambda("Azure\nDefender")
        azure_flowlogs = Custom("Azure Flow Logs", "./icons/azure.png") if False else Lambda("Azure\nFlow Logs")
        future_sources = Lambda("Future\nSources")
    
    # Ingestion Layer
    with Cluster("Ingestion Layer"):
        azure_eventhub_proc = Lambda("Event Hub\nProcessor")
        azure_flowlog_proc = Lambda("Flow Log\nProcessor")
        future_processors = Lambda("Future\nProcessors")
    
    # Processing Layer
    with Cluster("Processing Layer"):
        transform_queue = SQS("Transform\nQueue")
        transformer = Lambda("Event\nTransformer")
        asff_queue = SQS("ASFF\nQueue")
    
    # Output Layer
    with Cluster("Output Layer"):
        securityhub_proc = Lambda("SecurityHub\nProcessor")
        security_lake_s3 = S3("Security Lake")
        security_hub_svc = SecurityHub("SecurityHub")
    
    # Visualization Layer
    with Cluster("Visualization Layer"):
        eventbridge_vis = Eventbridge("EventBridge")
        sqs_osi_vis = SQS("OSI\nQueue")
        osi_pipeline_vis = ElasticsearchService("OpenSearch\nIngestion")
        opensearch_vis = ElasticsearchService("OpenSearch\nDashboards")
    
    # Monitoring
    monitoring = Cloudwatch("CloudWatch\nAlarms")
    
    # Flows
    azure_defender >> azure_eventhub_proc >> transform_queue
    azure_flowlogs >> azure_flowlog_proc >> transform_queue
    future_sources >> future_processors >> transform_queue
    
    transform_queue >> transformer
    transformer >> Edge(label="OCSF") >> security_lake_s3
    transformer >> Edge(label="ASFF") >> asff_queue
    asff_queue >> securityhub_proc >> security_hub_svc
    
    # Visualization flow
    security_lake_s3 >> Edge(label="S3 events") >> eventbridge_vis
    eventbridge_vis >> sqs_osi_vis >> osi_pipeline_vis
    osi_pipeline_vis >> Edge(label="dashboards") >> opensearch_vis
    
    [transform_queue, transformer, securityhub_proc] >> Edge(style="dashed") >> monitoring

# Diagram 3: Module Lifecycle
with Diagram(
    "Security Lake Integration Framework - Module Lifecycle",
    filename="diagrams/03_module_lifecycle",
    show=False,
    direction="TB",
    graph_attr=graph_attr
):
    # Configuration Phase
    with Cluster("1. Configuration Phase"):
        config_file = Custom("config.yaml", "./icons/file.png") if False else S3("config.yaml")
        config_load = Lambda("Load Config")
        legacy_detect = Lambda("Detect Legacy\nFormat")
        migrate = Lambda("Auto\nMigrate")
    
    # Validation Phase
    with Cluster("2. Validation Phase"):
        validate_core = Lambda("Validate\nCore Config")
        load_modules = Lambda("Load\nModules")
        validate_modules = Lambda("Validate Module\nConfigs")
    
    # Synthesis Phase
    with Cluster("3. Synthesis Phase"):
        create_core = Lambda("Create Core\nResources")
        init_modules = Lambda("Initialize\nModules")
        grant_perms = IAM("Grant\nPermissions")
    
    # Deployment Phase
    with Cluster("4. Deployment Phase"):
        cloudformation = Custom("CloudFormation", "./icons/cf.png") if False else S3("CloudFormation")
        deploy_stack = Lambda("Deploy\nStack")
        configure_secrets = SecretsManager("Configure\nSecrets")
    
    # Runtime Phase
    with Cluster("5. Runtime Phase"):
        module_lambdas = Lambda("Module\nLambdas")
        core_lambdas = Lambda("Core\nLambdas")
        monitoring_svc = Cloudwatch("Monitoring")
    
    # Flow
    config_file >> config_load >> legacy_detect
    legacy_detect >> Edge(label="if legacy") >> migrate >> validate_core
    legacy_detect >> Edge(label="if new") >> validate_core
    
    validate_core >> load_modules >> validate_modules
    validate_modules >> create_core >> init_modules >> grant_perms
    grant_perms >> cloudformation >> deploy_stack >> configure_secrets
    configure_secrets >> [module_lambdas, core_lambdas] >> monitoring_svc

# Diagram 4: Security Architecture
with Diagram(
    "Security Lake Integration Framework - Security Architecture",
    filename="diagrams/04_security_architecture",
    show=False,
    direction="LR",
    graph_attr=graph_attr
):
    # Identity & Access
    with Cluster("Identity & Access"):
        iam_roles = IAM("Per-Module\nIAM Roles")
        least_priv = IAM("Least\nPrivilege")
    
    # Data Protection
    with Cluster("Data Protection"):
        kms_master = KMS("Shared\nKMS Key")
        kms_module = KMS("Module-Specific\nKMS Keys")
        secrets = SecretsManager("Secrets\nManager")
    
    # Audit & Monitoring
    with Cluster("Audit & Monitoring"):
        cloudwatch_logs = Cloudwatch("CloudWatch\nLogs")
        cloudwatch_alarms = Cloudwatch("CloudWatch\nAlarms")
    
    # Module Components
    with Cluster("Module Lambda"):
        module_lambda = Lambda("Integration\nModule")
        module_role = IAM("Module\nRole")
    
    # Core Components
    with Cluster("Core Lambda"):
        core_lambda = Lambda("Event\nTransformer")
        core_role = IAM("Core\nRole")
    
    # Flows
    iam_roles >> [module_role, core_role]
    least_priv >> [module_role, core_role]
    
    module_role >> module_lambda
    core_role >> core_lambda
    
    module_lambda >> secrets
    core_lambda >> secrets
    module_lambda >> kms_master
    module_lambda >> kms_module
    core_lambda >> kms_master
    core_lambda >> kms_module
    module_lambda >> cloudwatch_logs
    core_lambda >> cloudwatch_logs
    
    cloudwatch_logs >> cloudwatch_alarms

# Diagram 5: End-to-End with Visualization
with Diagram(
    "Security Lake Integration Framework - Complete Architecture with Visualization",
    filename="diagrams/05_complete_with_visualization",
    show=False,
    direction="LR",
    graph_attr=graph_attr
):
    # External Sources
    with Cluster("Cloud Providers"):
        azure_def = Lambda("Microsoft\nDefender")
        gcp_scc = Lambda("Google\nSCC")
        aws_native = Lambda("AWS\nNative Sources")
    
    # Ingestion
    with Cluster("Ingestion Layer"):
        azure_proc = Lambda("Azure\nProcessor")
        gcp_proc = Lambda("GCP\nProcessor")
    
    # Core Processing
    with Cluster("Core Processing"):
        transform_q = SQS("Transform\nQueue")
        transformer_func = Lambda("Event\nTransformer")
    
    # Storage & Cataloging
    with Cluster("Security Lake"):
        lake_s3 = S3("Security Lake\nS3 Bucket")
        lake_glue = Glue("Glue\nCatalog")
        lake_formation = IAM("Lake\nFormation")
    
    # Visualization Pipeline
    with Cluster("Visualization Pipeline"):
        eb_notifications = Eventbridge("S3 Event\nNotifications")
        osi_queue = SQS("OSI\nQueue")
        osi_pipe = ElasticsearchService("OpenSearch\nIngestion")
    
    # Analysis Layer
    with Cluster("Analysis & Visualization"):
        opensearch_domain = ElasticsearchService("OpenSearch\nDomain")
        dashboards = Custom("Security\nDashboards", "./icons/dashboard.png") if False else ElasticsearchService("Security\nDashboards")
    
    # Other Outputs
    security_hub_out = SecurityHub("Security\nHub")
    
    # Flows
    azure_def >> azure_proc >> transform_q
    gcp_scc >> gcp_proc >> transform_q
    aws_native >> transform_q
    
    transform_q >> transformer_func
    transformer_func >> Edge(label="OCSF") >> lake_s3
    transformer_func >> Edge(label="ASFF") >> security_hub_out
    
    lake_s3 >> [lake_glue, lake_formation]
    lake_s3 >> Edge(label="S3 events") >> eb_notifications
    eb_notifications >> osi_queue >> osi_pipe
    osi_pipe >> Edge(label="indexed data") >> opensearch_domain
    opensearch_domain >> Edge(label="visualizations") >> dashboards

print("Architecture diagrams generated successfully in diagrams/ directory")
print("Generated files:")
print("  - 01_modular_architecture.png")
print("  - 02_data_flow.png")
print("  - 03_module_lifecycle.png")
print("  - 04_security_architecture.png")
print("  - 05_complete_with_visualization.png")