#!/bin/bash

# Fix Security Lake S3 Bucket Policy to include Lambda Role
set -e

echo "============================================"
echo "Security Lake S3 Bucket Policy Fix"
echo "============================================"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
STACK_NAME="gcp-scc-cloudtrail-integration-dev"
REGION="ca-central-1"
ACCOUNT_ID="061849379246"

# Get Lambda role name
echo "1. Getting Lambda role from CloudFormation stack..."
LAMBDA_ROLE_NAME=$(aws cloudformation describe-stack-resources \
  --stack-name "$STACK_NAME" \
  --logical-resource-id SecurityLakeCustomResourceRole296A15BD \
  --query 'StackResources[0].PhysicalResourceId' \
  --output text)

if [ -z "$LAMBDA_ROLE_NAME" ] || [ "$LAMBDA_ROLE_NAME" == "None" ]; then
  echo -e "${RED}❌ Cannot find Lambda role in stack${NC}"
  exit 1
fi

LAMBDA_ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$LAMBDA_ROLE_NAME"
echo -e "${GREEN}✓ Lambda role: $LAMBDA_ROLE_ARN${NC}"
echo ""

# Get Security Lake bucket
echo "2. Finding Security Lake S3 bucket..."
BUCKET=$(aws s3 ls | grep "aws-security-data-lake-$REGION" | awk '{print $3}' | head -1)

if [ -z "$BUCKET" ]; then
  echo -e "${RED}❌ Cannot find Security Lake bucket${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Found bucket: $BUCKET${NC}"
echo ""

# Get current bucket policy
echo "3. Retrieving current bucket policy..."
CURRENT_POLICY=$(aws s3api get-bucket-policy --bucket "$BUCKET" --query 'Policy' --output text 2>/dev/null || echo "{}")

if [ "$CURRENT_POLICY" == "{}" ]; then
  echo -e "${YELLOW}⚠️  No existing bucket policy${NC}"
  echo "Creating new policy..."
  
  # Create new policy with Lambda role
  NEW_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecurityLakeCustomResourceAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "$LAMBDA_ROLE_ARN"
      },
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::$BUCKET",
        "arn:aws:s3:::$BUCKET/*"
      ]
    }
  ]
}
EOF
)
else
  echo -e "${GREEN}✓ Current policy retrieved${NC}"
  
  # Check if Lambda role already in policy
  if echo "$CURRENT_POLICY" | grep -q "$LAMBDA_ROLE_ARN"; then
    echo -e "${GREEN}✓ Lambda role already in bucket policy!${NC}"
    echo ""
    echo "The bucket policy is correct. The issue might be elsewhere."
    echo "Check CloudWatch Logs for detailed error:"
    echo ""
    echo "aws logs tail /aws/lambda/gcp-scc-cloudtrail-integr-SecurityLakeCustomResour-* --follow"
    exit 0
  fi
  
  echo -e "${YELLOW}Adding Lambda role to existing policy...${NC}"
  
  # Parse and add Lambda role to existing policy
  NEW_POLICY=$(echo "$CURRENT_POLICY" | jq --arg role "$LAMBDA_ROLE_ARN" '
    .Statement += [{
      "Sid": "SecurityLakeCustomResourceAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": $role
      },
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        ("arn:aws:s3:::" + "'$BUCKET'"),
        ("arn:aws:s3:::" + "'$BUCKET'" + "/*")
      ]
    }]
  ')
fi

echo ""
echo "4. Applying updated bucket policy..."
echo "$NEW_POLICY" | jq '.'
echo ""

read -p "Apply this policy to $BUCKET? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
  aws s3api put-bucket-policy --bucket "$BUCKET" --policy "$NEW_POLICY"
  
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Bucket policy updated successfully!${NC}"
    echo ""
    echo "The Lambda role now has access to the Security Lake S3 bucket."
    echo ""
    echo "Next steps:"
    echo "1. Wait 10-15 seconds for policy to propagate"
    echo "2. Redeploy the stack:"
    echo "   cd ../cdk"
    echo "   cdk deploy"
  else
    echo -e "${RED}❌ Failed to update bucket policy${NC}"
    echo ""
    echo "You may need additional permissions or the bucket might be protected."
    echo "Try updating the policy through AWS Console instead."
  fi
else
  echo "Policy update cancelled"
fi

echo ""
echo "============================================"