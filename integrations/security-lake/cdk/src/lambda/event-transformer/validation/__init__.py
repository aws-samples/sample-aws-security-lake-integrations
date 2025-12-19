# (c) 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
# This AWS Content is provided subject to the terms of the AWS Customer Agreement available at
# http://aws.amazon.com/agreement or other written agreement between Customer and either
# Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

"""Template validation package for event-transformer templates."""

from .errors import (
    ValidationError,
    ValidationResult,
    AggregatedValidationResult,
    ValidationPhase,
    ValidationSeverity,
)

__all__ = [
    "ValidationError",
    "ValidationResult",
    "AggregatedValidationResult",
    "ValidationPhase",
    "ValidationSeverity",
]