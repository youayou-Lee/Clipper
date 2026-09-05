"""Address detection package."""

from .scanner import (
    UNCHECKED,
    VERIFIED,
    Finding,
    filter_alertable,
    match_exact,
    scan_text,
)

__all__ = [
    "Finding",
    "scan_text",
    "match_exact",
    "filter_alertable",
    "VERIFIED",
    "UNCHECKED",
]
