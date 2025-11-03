# OpenSearch IAM Identity Center Authentication Setup

This guide provides step-by-step instructions for configuring AWS IAM Identity Center authentication for OpenSearch domains.

## Table of Contents

- [Prerequisites](#prerequisites)
- [IAM Identity Center Configuration](#iam-identity-center-configuration)
- [SAML Authentication Setup](#saml-authentication-setup)
- [Group and Role Configuration](#group-and-role-configuration)
- [OpenSearch Access Policies](#opensearch-access-policies)
- [OCSF Schema Deployment](#ocsf-schema-deployment)

## Prerequisites

- AWS IAM Identity Center enabled in your AWS account
- OpenSearch domain deployed and accessible
- Administrative access to both IAM Identity Center and OpenSearch
- AWS CLI configured with appropriate permissions

## IAM Identity Center Configuration

### Step 1: Create Admin User

1. Navigate to **IAM Identity Center** in the AWS Console
2. Create an admin user with a secure password
3. Note the user's email and username for configuration

### Step 2: Enable API Access

Configure OpenSearch domain for IAM Identity Center authentication:

1. Navigate to your OpenSearch domain in the AWS Console
2. Go to **Domain configuration** → **Security Configuration** → **Edit**
3. In the **IAM Identity Center Authentication** section:
   - Select **Enable API access authenticated with IAM Identity Center**
   - Configure the following keys:

**Subject Key Options:**
- **UserId** (default): Use IAM Identity Center user ID as principal
- **UserName**: Use username as principal (recommended for readability)
- **Email**: Use email address as principal

**Roles Key Options:**
- **GroupId** (default): Use IAM Identity Center group ID as backend role
- **GroupName**: Use group name as backend role (recommended for readability)

### Step 3: Update Domain Configuration

```bash
# Update OpenSearch domain with IAM Identity Center configuration
aws opensearch update-domain-config \
    --domain-name <OpenSearch-Cluster-Name> \
    --identity-center-options '{
        "EnabledAPIAccess": true,
        "IdentityCenterInstanceARN": "<Identity-Center-ARN>",
        "SubjectKey": "UserName",
        "RolesKey": "GroupName"
    }'
```

**Configuration Parameters:**
- `EnabledAPIAccess`: Set to `true` to enable API access
- `IdentityCenterInstanceARN`: Your IAM Identity Center instance ARN
- `SubjectKey`: Principal identifier (UserName recommended)
- `RolesKey`: Backend role mapping (GroupName recommended)

## SAML Authentication Setup

### Step 1: Create SAML Application

1. Navigate to **IAM Identity Center** → **Applications**
2. Choose **Add application** → **I have an application I want to set up**
3. Select **SAML 2.0** application type
4. Configure SAML settings:
   - **Application ACS URL**: Use the IdP-initiated SSO URL from OpenSearch
   - **Application SAML audience**: Use the Service Provider Entity ID from OpenSearch

### Step 2: Download and Upload Metadata

1. **From IAM Identity Center**: Download the SAML metadata XML
2. **In OpenSearch**: Upload the metadata XML under Security Configuration

### Step 3: Configure Attribute Mappings

1. In IAM Identity Center application settings, choose **Actions** → **Edit attribute mappings**
2. Configure the following mappings:
   - **Subject**: `${user:email}` → **emailAddress** format
   - **Role**: `${user:groups}` → **unspecified** format

## Group and Role Configuration

### Step 1: Create OpenSearch Admin Group

1. Navigate to **IAM Identity Center** → **Groups**
2. Create a new group named `OS_Admin`
3. Assign your admin user to this group
4. Copy the **Group ID** for use in OpenSearch configuration

### Step 2: Configure OpenSearch Backend Role

1. Access the **OpenSearch Dashboards**
2. Navigate to **Security** → **Edit**
3. Add the IAM Identity Center Group ID to the **SAML master backend role**
   - This grants all members of the `OS_Admin` group administrative access to OpenSearch

### Step 3: Map Backend Role to Permissions

1. In OpenSearch Dashboards, navigate to:
   - **Management** → **Security** → **Roles** → **all_access**
2. Select **Mapped Users**
3. Add **Backend role**: Include the IAM role used by your OpenSearch Ingestion pipeline

## OpenSearch Access Policies

Configure OpenSearch domain access policies to allow pipeline ingestion:

```bash
# Update OpenSearch access policies
aws opensearch update-domain-config \
    --domain-name <opensearch-domain-name> \
    --access-policies '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": "arn:aws:iam::<account-id>:role/service-role/<pipeline-iam-role>"
                },
                "Action": "es:*",
                "Resource": "arn:aws:es:<region>:<account-id>:domain/<domain-name>/*"
            }
        ]
    }'
```

**Replace placeholders:**
- `<opensearch-domain-name>`: Your OpenSearch domain name
- `<account-id>`: Your AWS account ID
- `<pipeline-iam-role>`: IAM role name for OpenSearch Ingestion pipeline
- `<region>`: AWS region (e.g., ca-central-1)
- `<domain-name>`: OpenSearch domain name in ARN format



aws opensearch update-domain-config \
  --domain-name aes-siem \
  --access-policies '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "AWS": "arn:aws:iam::061849379246:role/service-role/OpenSearchIngestion-s3-85f7c9"
        },
        "Action": "es:*",
        "Resource": "arn:aws:es:ca-central-1:061849379246:domain/aes-siem/*"
      }
    ]
  }'


## Deploy schema and components
Git clone https://github.com/aws-samples/ocsf-for-opensearch.git

cd ocsf-for-opensearch/schemas
zip -r index_templates.zip ./index_templates
zip -r ./component_templates.zip ./component_templates
upload to a deployment bucket
aws s3 cp ./index_templates.zip s3://fedlcc-securityhub-s3-deploymentbucket-n3feglhgokye/index_templates.zip
aws s3 cp ./component_templates.zip s3://fedlcc-securityhub-s3-deploymentbucket-n3feglhgokye/component_templates.zip

cd ..
Edit ./scripts/os_init.py
```
## Initialise variables
OSEndpoint = 'https://search-aes-siem-6kyxwfcgu2stlwbjx5ebzgqahy.ca-central-1.es.amazonaws.com'
bucket_name = 'fedlcc-securityhub-s3-deploymentbucket-n3feglhgokye'
component_templates = 'component_templates.zip'
index_templates = 'index_templates.zip'
url = urlparse(OSEndpoint)
region = 'ca-central-1'
```
pip install opensearch-py
python ./scripts/os_init.py