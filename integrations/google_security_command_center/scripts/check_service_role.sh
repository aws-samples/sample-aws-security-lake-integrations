#!/bin/bash

# Check Security Lake Service Role and S3 Bucket
set -e

echo "============================================"
echo "Security Lake Service Role & S3 Diagnostics"
echo "============================================"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# From config.yaml
SERVICE_ROLE="SecurityLakeGlueCrawler"
REGION="ca-central-1"

echo "1. Checking Service Role: $SERVICE_ROLE"
echo "----------------------------------------"

ROLE_CHECK=$(aws iam get-role --role-name "$SERVICE_ROLE" 2>&1 || true)

if echo "$ROLE_CHECK" | grep -q "NoSuchEntity"; then
  echo -e "${RED}❌ Service role '$SERVICE_ROLE' does NOT exist${NC}"
  echo ""
  echo "This role is required by Security Lake for Glue Crawler operations."
  echo ""
  echo "SOLUTION: Create the role or update config.yaml to use an existing role."
  echo ""
  echo "To check what roles exist:"
  echo "aws iam list-roles --query 'Roles[?contains(RoleName, \`SecurityLake\`) || contains(RoleName, \`Glue\`)].RoleName'"
  echo ""
  exit 1
else
  echo -e "${GREEN}✓ Service role exists${NC}"
  ROLE_ARN=$(echo "$ROLE_CHECK" | jq -r '.Role.Arn' 2>/dev/null || echo "Could not parse")
  echo "Role ARN: $ROLE_ARN"
  
  # Check role policies
  echo ""
  echo "Checking role policies..."
  MANAGED_POLICIES=$(aws iam list-attached-role-policies --role-name "$SERVICE_ROLE" --query 'AttachedPolicies[*].PolicyName' --output text 2>/dev/null || echo "")
  INLINE_POLICIES=$(aws iam list-role-policies --role-name "$SERVICE_ROLE" --query 'PolicyNames' --output text 2>/dev/null || echo "")
  
  if [ -n "$MANAGED_POLICIES" ]; then
    echo "Managed policies: $MANAGED_POLICIES"
  fi
  if [ -n "$INLINE_POLICIES" ]; then
    echo "Inline policies: $INLINE_POLICIES"
  fi
  
  # Check if role has Glue permissions
  if echo "$MANAGED_POLICIES" | grep -q "Glue" || echo "$INLINE_POLICIES" | grep -q "glue"; then
    echo -e "${GREEN}✓ Role has Glue-related policies${NC}"
  else
    echo -e "${YELLOW}⚠️  Role may be missing Glue permissions${NC}"
  fi
fi

echo ""
echo "2. Checking Security Lake S3 Bucket"
echo "----------------------------------------"

# Try to find Security Lake bucket
BUCKETS=$(aws s3 ls | grep "aws-security-data-lake-$REGION" | awk '{print $3}' || echo "")

if [ -z "$BUCKETS" ]; then
  echo -e "${RED}❌ No Security Lake buckets found in region $REGION${NC}"
  echo ""
  echo "SOLUTION: Verify Security Lake is set up in region $REGION"
else
  echo -e "${GREEN}✓ Found Security Lake bucket(s):${NC}"
  echo "$BUCKETS"
  
  # Check first bucket's policy
  BUCKET=$(echo "$BUCKETS" | head -1)
  echo ""
  echo "Checking bucket policy for: $BUCKET"
  
  BUCKET_POLICY=$(aws s3api get-bucket-policy --bucket "$BUCKET" 2>&1 || true)
  
  if echo "$BUCKET_POLICY" | grep -q "NoSuchBucketPolicy"; then
    echo -e "${YELLOW}⚠️  No bucket policy set${NC}"
  elif echo "$BUCKET_POLICY" | grep -q "AccessDenied"; then
    echo -e "${YELLOW}⚠️  Cannot read bucket policy (insufficient permissions)${NC}"
  else
    echo "Bucket policy exists"
    
    # Check if Lambda role has access
    LAMBDA_ROLE_ARN=$(aws cloudformation describe-stack-resources \
      --stack-name gcp-scc-cloudtrail-integration-dev \
      --logical-resource-id SecurityLakeCustomResourceRole296A15BD \
      --query 'StackResources[0].PhysicalResourceId' \
      --output text 2>/dev/null || echo "")
    
    if [ -n "$LAMBDA_ROLE_ARN" ]; then
      LAMBDA_ROLE_ARN="arn:aws:iam::061849379246:role/$LAMBDA_ROLE_ARN"
      if echo "$BUCKET_POLICY" | grep -q "$LAMBDA_ROLE_ARN"; then
        echo -e "${GREEN}✓ Lambda role is in bucket policy${NC}"
      else
        echo -e "${YELLOW}⚠️  Lambda role NOT found in bucket policy${NC}"
        echo "This might cause permission issues"
      fi
    fi
  fi
fi

echo ""
echo "3. Testing Security Lake API Access"
echo "----------------------------------------"

echo "Attempting to list custom log sources..."
CUSTOM_SOURCES=$(aws securitylake list-log-sources \
  --regions "$REGION" \
  --query 'logSources[?sourceType==`CUSTOM`]' \
  --output json 2>&1 || true)

if echo "$CUSTOM_SOURCES" | grep -q "AccessDenied"; then
  echo -e "${RED}❌ Access Denied to list Security Lake sources${NC}"
  echo "You don't have permission to list Security Lake sources"
elif echo "$CUSTOM_SOURCES" | grep -q "error"; then
  echo -e "${YELLOW}⚠️  Error accessing Security Lake:${NC}"
  echo "$CUSTOM_SOURCES"
else
  echo -e "${GREEN}✓ Can access Security Lake API${NC}"
  
  # Check for existing custom sources
  if echo "$CUSTOM_SOURCES" | jq -e '.[] | select(.sourceName | contains("gcpSccIntegration"))' > /dev/null 2>&1; then
    echo ""
    echo -e "${GREEN}✓ Found existing gcpSccIntegration source${NC}"
    echo ""
    echo "The source already exists! This might be causing the deployment issue."
    echo ""
    echo "SOLUTION: Delete the existing source first:"
    echo "aws securitylake delete-custom-log-source --source-name gcpSccIntegration"
    echo ""
    echo "Then redeploy:"
    echo "cdk deploy"
  else
    echo "No existing gcpSccIntegration source found"
  fi
fi

echo ""
echo "4. Checking for Service-Linked Role"
echo "----------------------------------------"

SLR_CHECK=$(aws iam get-role --role-name AWSServiceRoleForSecurityLake 2>&1 || true)

if echo "$SLR_CHECK" | grep -q "NoSuchEntity"; then
  echo -e "${YELLOW}⚠️  Service-linked role for Security Lake doesn't exist${NC}"
  echo ""
  echo "This is usually created automatically by Security Lake."
  echo "To create manually:"
  echo "aws iam create-service-linked-role --aws-service-name securitylake.amazonaws.com"
else
  echo -e "${GREEN}✓ Service-linked role exists${NC}"
fi

echo ""
echo "============================================"
echo "RECOMMENDATIONS"
echo "============================================"
echo ""

if [ -z "$BUCKETS" ]; then
  echo -e "${RED}CRITICAL: Set up Security Lake in region $REGION first${NC}"
elif echo "$ROLE_CHECK" | grep -q "NoSuchEntity"; then
  echo -e "${RED}CRITICAL: Create service role '$SERVICE_ROLE' or update config.yaml${NC}"
else
  echo "All prerequisites appear to be in place."
  echo ""
  echo "If deployment still fails with AccessDenied:"
  echo ""
  echo "1. Check if custom source already exists (see above)"
  echo "2. Verify S3 bucket policy allows Lambda role access"
  echo "3. Try deploying after deleting any existing sources"
  echo "4. Check CloudWatch Logs for detailed error messages"
  echo ""
  echo "To delete existing source:"
  echo "  aws securitylake delete-custom-log-source --source-name gcpSccIntegration --region $REGION"
  echo ""
  echo "To check Lambda logs:"
  echo "  aws logs tail /aws/lambda/gcp-scc-cloudtrail-integr-SecurityLakeCustomResour-* --follow"
fi

echo ""