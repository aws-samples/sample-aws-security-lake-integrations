#!/bin/bash

# Diagnostic and Fix Script for Security Lake Integration
# This script will identify and help fix Security Lake custom resource errors

set -e

echo "=========================================="
echo "Security Lake Integration Diagnostic Tool"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get region
REGION=${AWS_REGION:-$(aws configure get region)}
echo "Region: $REGION"
echo ""

# Step 1: Get CloudWatch Logs
echo -e "${YELLOW}Step 1: Checking Lambda Logs for Errors${NC}"
echo "----------------------------------------"

LOG_GROUP="/aws/lambda/gcp-scc-cloudtrail-integr-SecurityLakeCustomResour-B5QfI6wBGeVF"

echo "Fetching recent error logs..."
LOGS=$(aws logs filter-log-events \
  --log-group-name "$LOG_GROUP" \
  --filter-pattern "ERROR" \
  --start-time "$(($(date +%s) - 3600))000" \
  --query 'events[*].message' \
  --output text 2>&1 || echo "Cannot access logs")

if [[ "$LOGS" == *"Cannot access logs"* ]] || [[ -z "$LOGS" ]]; then
  echo -e "${RED}❌ Cannot access Lambda logs${NC}"
  echo "Log group might not exist yet or no errors logged"
else
  echo -e "${GREEN}✓ Found error logs:${NC}"
  echo "$LOGS"
fi
echo ""

# Get full recent logs
echo "Fetching all recent logs (last 5 minutes)..."
aws logs tail "$LOG_GROUP" --since 5m 2>/dev/null | tail -50 || echo "Cannot tail logs"
echo ""

# Step 2: Check Security Lake Status
echo -e "${YELLOW}Step 2: Checking Security Lake Setup${NC}"
echo "----------------------------------------"

SECURITY_LAKE_STATUS=$(aws securitylake get-data-lake-sources --region "$REGION" 2>&1)

if [[ "$SECURITY_LAKE_STATUS" == *"AccessDeniedException"* ]]; then
  echo -e "${RED}❌ AccessDenied: No permission to access Security Lake${NC}"
  echo "Required permission: securitylake:GetDataLakeSources"
elif [[ "$SECURITY_LAKE_STATUS" == *"ResourceNotFoundException"* ]] || [[ "$SECURITY_LAKE_STATUS" == *"NotFound"* ]]; then
  echo -e "${RED}❌ Security Lake is NOT set up in region $REGION${NC}"
  echo ""
  echo -e "${YELLOW}FIX: You need to set up AWS Security Lake first:${NC}"
  echo "1. Go to AWS Console → Security Lake"
  echo "2. Click 'Get Started' or 'Create Data Lake'"
  echo "3. Follow the setup wizard"
  echo "4. Note the S3 bucket name created"
  echo "5. Update config.yaml with the bucket name"
  echo "6. Re-run: cdk deploy"
  exit 1
else
  echo -e "${GREEN}✓ Security Lake is configured${NC}"
  echo "$SECURITY_LAKE_STATUS"
fi
echo ""

# Step 3: Check S3 Bucket
echo -e "${YELLOW}Step 3: Checking Security Lake S3 Bucket${NC}"
echo "----------------------------------------"

# Try to find Security Lake buckets
echo "Looking for Security Lake buckets..."
S3_BUCKETS=$(aws s3 ls 2>/dev/null | grep aws-security-data-lake || echo "")

if [[ -z "$S3_BUCKETS" ]]; then
  echo -e "${RED}❌ No Security Lake buckets found${NC}"
  echo "Expected bucket name format: aws-security-data-lake-{region}-{hash}"
else
  echo -e "${GREEN}✓ Found Security Lake buckets:${NC}"
  echo "$S3_BUCKETS"
  
  # Extract bucket name
  BUCKET_NAME=$(echo "$S3_BUCKETS" | head -1 | awk '{print $3}')
  echo ""
  echo -e "${GREEN}Detected bucket: $BUCKET_NAME${NC}"
  
  # Check config.yaml
  CONFIG_FILE="../cdk/config.yaml"
  if [[ -f "$CONFIG_FILE" ]]; then
    CONFIG_BUCKET=$(grep -A 5 "securityLake:" "$CONFIG_FILE" | grep "s3Bucket:" | awk '{print $2}' | tr -d "'\"")
    echo "Config file bucket: $CONFIG_BUCKET"
    
    if [[ "$CONFIG_BUCKET" != "$BUCKET_NAME" ]]; then
      echo -e "${RED}❌ Bucket mismatch!${NC}"
      echo ""
      echo -e "${YELLOW}FIX: Update config.yaml:${NC}"
      echo "  s3Bucket: '$BUCKET_NAME'"
    else
      echo -e "${GREEN}✓ Bucket name matches config${NC}"
    fi
  fi
fi
echo ""

# Step 4: Check IAM Service Role
echo -e "${YELLOW}Step 4: Checking Service Role${NC}"
echo "----------------------------------------"

SERVICE_ROLE="SecurityLakeGlueCrawler"
ROLE_CHECK=$(aws iam get-role --role-name "$SERVICE_ROLE" 2>&1)

if [[ "$ROLE_CHECK" == *"NoSuchEntity"* ]]; then
  echo -e "${RED}❌ Service role '$SERVICE_ROLE' does not exist${NC}"
  echo ""
  echo -e "${YELLOW}FIX: The role will be created automatically by Security Lake.${NC}"
  echo "OR you can change config.yaml to use a different existing role."
else
  echo -e "${GREEN}✓ Service role exists: $SERVICE_ROLE${NC}"
fi
echo ""

# Step 5: Check Lambda IAM Permissions
echo -e "${YELLOW}Step 5: Checking Lambda IAM Permissions${NC}"
echo "----------------------------------------"

STACK_NAME="gcp-scc-cloudtrail-integration-dev"
ROLE_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name "$STACK_NAME" \
  --logical-resource-id SecurityLakeCustomResourceRole \
  --query 'StackResources[0].PhysicalResourceId' \
  --output text 2>/dev/null || echo "")

if [[ -z "$ROLE_NAME" ]] || [[ "$ROLE_NAME" == "None" ]]; then
  echo -e "${YELLOW}⚠ Lambda role not found (stack may not be fully deployed)${NC}"
else
  echo "Lambda Role: $ROLE_NAME"
  
  # Check for SecurityLake permissions
  POLICIES=$(aws iam list-role-policies --role-name "$ROLE_NAME" --query 'PolicyNames' --output text 2>/dev/null || echo "")
  echo "Inline Policies: $POLICIES"
  
  if [[ "$POLICIES" == *"SecurityLakePolicy"* ]]; then
    POLICY=$(aws iam get-role-policy --role-name "$ROLE_NAME" --policy-name SecurityLakePolicy --query 'PolicyDocument' 2>/dev/null)
    
    if [[ "$POLICY" == *"securitylake:CreateCustomLogSource"* ]]; then
      echo -e "${GREEN}✓ Has CreateCustomLogSource permission${NC}"
    else
      echo -e "${RED}❌ Missing CreateCustomLogSource permission${NC}"
    fi
  fi
fi
echo ""

# Step 6: Test Security Lake API
echo -e "${YELLOW}Step 6: Testing Security Lake API Access${NC}"
echo "----------------------------------------"

echo "Attempting to list existing log sources..."
LIST_SOURCES=$(aws securitylake list-log-sources --region "$REGION" 2>&1)

if [[ "$LIST_SOURCES" == *"AccessDenied"* ]]; then
  echo -e "${RED}❌ Access Denied to list log sources${NC}"
  echo "The Lambda role needs securitylake:ListLogSources permission"
elif [[ "$LIST_SOURCES" == *"error"* ]]; then
  echo -e "${RED}❌ Error accessing Security Lake:${NC}"
  echo "$LIST_SOURCES"
else
  echo -e "${GREEN}✓ Can access Security Lake${NC}"
  echo "Existing sources:"
  echo "$LIST_SOURCES" | jq '.' 2>/dev/null || echo "$LIST_SOURCES"
fi
echo ""

# Step 7: Summary and Recommendations
echo -e "${YELLOW}=========================================="
echo "Summary and Recommended Actions"
echo "==========================================${NC}"
echo ""

# Check if we found critical issues
ISSUES_FOUND=0

if [[ "$SECURITY_LAKE_STATUS" == *"NotFound"* ]] || [[ "$SECURITY_LAKE_STATUS" == *"ResourceNotFoundException"* ]]; then
  echo -e "${RED}⚠ CRITICAL: Security Lake not set up${NC}"
  echo "   Action: Set up Security Lake in AWS Console first"
  ISSUES_FOUND=1
fi

if [[ -n "$S3_BUCKETS" ]] && [[ -f "../cdk/config.yaml" ]]; then
  CONFIG_BUCKET=$(grep -A 5 "securityLake:" "../cdk/config.yaml" | grep "s3Bucket:" | awk '{print $2}' | tr -d "'\"")
  DETECTED_BUCKET=$(echo "$S3_BUCKETS" | head -1 | awk '{print $3}')
  
  if [[ "$CONFIG_BUCKET" != "$DETECTED_BUCKET" ]]; then
    echo -e "${RED}⚠ Bucket name mismatch in config.yaml${NC}"
    echo "   Current: $CONFIG_BUCKET"
    echo "   Should be: $DETECTED_BUCKET"
    echo "   Action: Update config.yaml and redeploy"
    ISSUES_FOUND=1
  fi
fi

if [[ "$ROLE_CHECK" == *"NoSuchEntity"* ]]; then
  echo -e "${YELLOW}⚠ Service role missing${NC}"
  echo "   Action: Let Security Lake create it, or create manually"
  ISSUES_FOUND=1
fi

if [[ $ISSUES_FOUND -eq 0 ]]; then
  echo -e "${GREEN}No obvious configuration issues found.${NC}"
  echo ""
  echo "The error might be:"
  echo "1. Transient API issue - try deploying again"
  echo "2. Race condition - Security Lake resources still initializing"
  echo "3. Event class names invalid - check config.yaml eventClasses"
  echo ""
  echo "Try: cdk destroy && cdk deploy"
else
  echo ""
  echo "Fix the issues above and run: cdk deploy"
fi

echo ""
echo "=========================================="
echo "For more details, check:"
echo "  - CloudWatch Logs: $LOG_GROUP"
echo "  - CloudFormation Stack: $STACK_NAME"
echo "=========================================="