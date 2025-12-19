# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Helper modules for OpenSearch Workspace Creator Lambda.

This package contains:
- opensearch_client: OpenSearch Serverless client for workspace API operations
"""

from helpers.opensearch_client import OpenSearchClient, WorkspaceResult

__all__ = ["OpenSearchClient", "WorkspaceResult"]
