# © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""
CloudTrail Lake Integration Types
Dataclasses for CloudTrail API payloads
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class CloudTrailAuditEvent:
    """
    Structure for CloudTrail put_audit_events API call
    
    This dataclass represents the payload format required by the CloudTrail
    put_audit_events API for ingesting external events into CloudTrail Lake.
    """
    eventData: str  # JSON string of the complete CloudTrail event
    id: str  # Original event ID from the source event
    eventDataChecksum: Optional[str] = None  # Optional checksum for data integrity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API call"""
        result = {
            'eventData': self.eventData,
            'id': self.id
        }
        if self.eventDataChecksum:
            result['eventDataChecksum'] = self.eventDataChecksum
        return result