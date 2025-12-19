# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Dockerfile for OpenSearch Workspace Creator Lambda Function
# Uses AWS Lambda Python 3.13 ARM64 base image for optimal performance

FROM public.ecr.aws/lambda/python:3.13-arm64

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy helper modules
COPY helpers/ helpers/

# Copy the Lambda handler
COPY app.py .

# Set the Lambda handler
CMD ["app.handler"]
