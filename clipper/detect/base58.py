"""Base58 / Base58Check codec (Bitcoin style).

Pure Python; no external dependencies.
"""

import hashlib

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {c: i for i, c in enumerate(ALPHABET)}


def b58decode(text: str):
    """Decode a Base58 string, or return None if it is not valid Base58."""
    if not text:
        return None
    num = 0
    for ch in text:
        idx = _INDEX.get(ch)
        if idx is None:
            return None
        num = num * 58 + idx
    # Leading '1' characters encode leading zero bytes.
    n_zeros = len(text) - len(text.lstrip("1"))
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    return b"\x00" * n_zeros + body


def b58check_decode(text: str):
    """Decode Base58Check, returning the version-prefixed payload or None.

    Payload = version_byte + data; last 4 bytes are the first 4 bytes of
    the double-SHA256 checksum.
    """
    raw = b58decode(text)
    if raw is None or len(raw) < 5:
        return None
    payload, checksum = raw[:-4], raw[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected:
        return None
    return payload
