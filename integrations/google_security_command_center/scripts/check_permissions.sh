#!/bin/bash

# Check Lambda Role Permissions for Security Lake
# This script verifies if the Lambda has all required permissions

set -e

echo "=========================================="
echo "Security Lake Lambda Permissions Checker"
echo "=========================================="
echo ""

STACK_NAME="gcp-scc-cloudtrail-integration-dev"
REGION=${AWS_REGION:-$(aws configure get region)}

# Get the Lambda role name
echo "Finding Lambda role..."
ROLE_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name "$STACK_NAME" \
  --logical-resource-id SecurityLakeCustomResourceRole296A15BD \
  --query 'StackResources[0].PhysicalResourceId' \
  --output text 2>/dev/null)

if [ -z "$ROLE_NAME" ] || [ "$ROLE_NAME" == "None" ]; then
  echo "❌ Cannot find SecurityLakeCustomResourceRole296A15BD in stack"
  echo "Has the stack been deployed?"
  exit 1
fi

echo "✓ Found role: $ROLE_NAME"
echo ""

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo "Role ARN: $ROLE_ARN"
echo ""

# Check inline policies
echo "Checking inline policies..."
POLICIES=$(aws iam list-role-policies --role-name "$ROLE_NAME" --query 'PolicyNames' --output text)
echo "Inline policies: $POLICIES"
echo ""

if [[ "$POLICIES" == *"SecurityLakePolicy"* ]]; then
  echo "Getting SecurityLakePolicy document..."
  POLICY_DOC=$(aws iam get-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name SecurityLakePolicy \
    --query 'PolicyDocument' \
    --output json)
  
  echo "Checking for required permissions..."
  echo ""
  
  # Check specific permissions
  check_permission() {
    local perm=$1
    if echo "$POLICY_DOC" | grep -q "$perm"; then
      echo "  ✓ $perm"
      return 0
    else
      echo "  ❌ MISSING: $perm"
      return 1
    fi
  }
  
  MISSING=0
  
  echo "Security Lake permissions:"
  check_permission "securitylake:CreateCustomLogSource" || MISSING=1
  check_permission "securitylake:GetDataLakeSources" || MISSING=1
  check_permission "securitylake:ListLogSources" || MISSING=1
  
  echo ""
  echo "Lake Formation permissions:"
  check_permission "lakeformation:RegisterResource" || MISSING=1
  check_permission "lakeformation:GrantPermissions" || MISSING=1
  check_permission "lakeformation:PutDataLakeSettings" || MISSING=1
  
  echo ""
  echo "IAM permissions:"
  check_permission "iam:PassRole" || MISSING=1
  check_permission "iam:CreateRole" || MISSING=1
  check_permission "iam:GetRole" || MISSING=1
  
  echo ""
  if [ $MISSING -eq 0 ]; then
    echo "✓ All checked permissions are present"
  else
    echo "❌ Some permissions are missing!"
  fi
fi

echo ""
echo "Checking Lake Formation Data Lake Settings..."
LF_ADMINS=$(aws lakeformation get-data-lake-settings \
  --query 'DataLakeSettings.DataLakeAdmins[*].DataLakePrincipalIdentifier' \
  --output text 2>/dev/null || echo "")

if [ -z "$LF_ADMINS" ]; then
  echo "❌ Cannot get Lake Formation admins (permission issue?)"
else
  echo "Lake Formation Admins:"
  echo "$LF_ADMINS"
  
  if echo "$LF_ADMINS" | grep -q "$ROLE_ARN"; then
    echo "✓ Lambda role IS a Lake Formation administrator"
  else
    echo "❌ Lambda role is NOT a Lake Formation administrator"
    echo ""
    echo "⚠️  CRITICAL: The role must be a Lake Formation administrator!"
    echo ""
    echo "To fix this, run:"
    echo "aws lakeformation put-data-lake-settings --data-lake-settings '{\"DataLakeAdmins\":[{\"DataLakePrincipalIdentifier\":\"$ROLE_ARN\"}]}'"
  fi
fi

echo ""
echo "Checking Security Lake status..."
SL_STATUS=$(aws securitylake get-data-lake-sources --region "$REGION" 2>&1 || true)

if echo "$SL_STATUS" | grep -q "ResourceNotFoundException\|NotFound"; then
  echo "❌ Security Lake is NOT configured in region $REGION"
  echo ""
  echo "You must set up Security Lake first:"
  echo "1. Go to AWS Console → Security Lake"
  echo "2. Click 'Get Started'"
  echo "3. Follow the setup wizard"
elif echo "$SL_STATUS" | grep -q "AccessDenied"; then
  echo "❌ Access Denied to Security Lake"
  echo "The IAM user/role running this script cannot access Security Lake"
else
  echo "✓ Security Lake is configured"
fi

echo ""
echo "=========================================="
echo "Diagnosis Summary"
echo "=========================================="
echo ""

echo "Common causes of AccessDeniedException:"
echo ""
echo "1. Lake Formation Administrator Not Set"
echo "   - The Lambda role MUST be a Lake Formation administrator"
echo "   - This is set via Lake Formation Data Lake Settings"
echo "   - CDK sets this but it may take a few minutes to propagate"
echo ""
echo "2. Security Lake Not Fully Initialized"
echo "   - Security Lake must be enabled AND fully configured"
echo "   - Check AWS Console → Security Lake → Settings"
echo ""
echo "3. IAM Permissions Not Yet Applied"
echo "   - After cdk deploy, IAM changes can take 10-60 seconds"
echo "   - Try waiting 60 seconds and deploying again"
echo ""
echo "4. Service-Linked Role Missing"
echo "   - Security Lake needs a service-linked role"
echo "   - Usually created automatically"
echo "   - Check: aws iam get-role --role-name AWSServiceRoleForSecurityLake"
echo ""
echo "5. Resource-Based Policies"
echo "   - S3 bucket policy may be blocking access"
echo "   - Check bucket: aws s3api get-bucket-policy --bucket <bucket-name>"
echo ""

echo "Recommended Actions:"
echo ""
echo "1. Wait 60 seconds for IAM to propagate, then:"
echo "   cd integrations/google_security_command_center/cdk"
echo "   cdk deploy"
echo ""
echo "2. If still failing, manually set Lake Formation admin:"
echo "   aws lakeformation put-data-lake-settings \\"
echo "     --data-lake-settings '{\"DataLakeAdmins\":[{\"DataLakePrincipalIdentifier\":\"$ROLE_ARN\"}]}'"
echo ""
echo "3. Verify Security Lake is fully set up in AWS Console"
echo ""
echo "4. Check CloudFormation stack for Lake Formation settings:"
echo "   aws cloudformation describe-stack-resources \\"
echo "     --stack-name $STACK_NAME \\"
echo "     --logical-resource-id SecurityLakeDataLakeSettings"