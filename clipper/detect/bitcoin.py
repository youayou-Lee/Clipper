"""Bitcoin address detection: candidate extraction + real checksum validation.

The regexes are deliberately loose — they only surface *candidates*.
The Base58Check / Bech32 checksum is the real gatekeeper, which is what
keeps the false-positive rate near zero.
"""

import re

from .base58 import b58check_decode
from .bech32 import decode_segwit_address

# Base58 legacy: '1' (P2PKH) or '3' (P2SH), 26-35 chars total.
BASE58_RE = re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")

# SegWit bech32: bc/tb + '1' + data part, up to the BIP-173 limit of 90 chars.
BECH32_RE = re.compile(r"\b(?:bc|tb)1[a-z0-9]{8,87}\b", re.IGNORECASE)

_KINDS = {0x00: "P2PKH", 0x05: "P2SH"}
_BECH32_KINDS = {(0, 20): "P2WPKH", (0, 32): "P2WSH", (1, 32): "P2TR"}


def validate_base58(candidate: str):
    """Return the address kind ('P2PKH'/'P2SH') or None if invalid."""
    payload = b58check_decode(candidate)
    if payload is None or len(payload) != 21:
        return None
    return _KINDS.get(payload[0])


def validate_bech32(candidate: str):
    """Return the address kind ('P2WPKH'/'P2WSH'/'P2TR') or None if invalid.

    Witness versions 2-16 have no standard script yet, so they are not
    reported.
    """
    decoded = decode_segwit_address(candidate)
    if decoded is None:
        return None
    version, program = decoded
    return _BECH32_KINDS.get((version, len(program)))
