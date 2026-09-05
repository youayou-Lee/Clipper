"""Ethereum address detection with EIP-55 checksum validation.

Plain hex has no checksum, so an all-lowercase or all-uppercase address
cannot be verified — those are reported with 'unchecked' confidence.
The lookaround in the regex rejects longer hex blobs (e.g. 32-byte
transaction hashes) and bare 40-hex strings without a 0x prefix (git
commit SHAs).
"""

import re

from Crypto.Hash import keccak

# 0x + 40 hex digits, not embedded in a longer hex run.
HEX_ADDR_RE = re.compile(r"(?<![0-9a-fA-F])0[xX][0-9a-fA-F]{40}(?![0-9a-fA-F])")

VERIFIED = "eip55"
UNCHECKED = "unchecked"


def _keccak256(data: bytes) -> bytes:
    return keccak.new(digest_bits=256, data=data).digest()


def validate_eip55(candidate: str):
    """Return 'eip55' (checksum verified), 'unchecked', or None (invalid)."""
    body = candidate[2:]
    if body == body.lower() or body == body.upper():
        return UNCHECKED  # no case information -> checksum cannot be verified
    digest_hex = _keccak256(body.lower().encode("ascii")).hex()
    for i, ch in enumerate(body):
        if ch.isalpha() and ((int(digest_hex[i], 16) >= 8) != ch.isupper()):
            return None
    return VERIFIED
