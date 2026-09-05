"""Scan text for cryptocurrency addresses, checksum-verified."""

from dataclasses import dataclass

from ..normalize import normalize
from .bitcoin import BASE58_RE, BECH32_RE, validate_base58, validate_bech32
from .ethereum import HEX_ADDR_RE, validate_eip55

VERIFIED = "verified"
UNCHECKED = "unchecked"


@dataclass(frozen=True)
class Finding:
    chain: str  # "bitcoin" | "ethereum"
    kind: str  # P2PKH / P2SH / P2WPKH / P2WSH / P2TR / EIP55 / UNCHECKED_ETH
    address: str
    confidence: str  # VERIFIED | UNCHECKED
    start: int
    end: int

    @property
    def preview(self) -> str:
        if len(self.address) <= 16:
            return self.address
        return f"{self.address[:8]}…{self.address[-6:]}"


def scan_text(text: str) -> list:
    """Return all addresses found in *text* (normalized first).

    Runs two passes: one on the whitespace-preserving form (so word
    boundaries stay intact) and one on a whitespace-stripped form (to
    catch addresses broken across line wraps). Deduplicated by address;
    offsets of fused-pass findings refer to the fused text.
    """
    text = normalize(text)
    findings = _scan_flat(text)
    if " " in text:
        known = {f.address for f in findings}
        findings.extend(
            f for f in _scan_flat(text.replace(" ", "")) if f.address not in known
        )
    findings.sort(key=lambda f: f.start)
    return findings


def _scan_flat(text: str) -> list:
    findings = []
    for match in BASE58_RE.finditer(text):
        kind = validate_base58(match.group(0))
        if kind:
            findings.append(
                Finding("bitcoin", kind, match.group(0), VERIFIED, match.start(), match.end())
            )
    for match in BECH32_RE.finditer(text):
        kind = validate_bech32(match.group(0))
        if kind:
            findings.append(
                Finding("bitcoin", kind, match.group(0), VERIFIED, match.start(), match.end())
            )
    for match in HEX_ADDR_RE.finditer(text):
        result = validate_eip55(match.group(0))
        if result == "eip55":
            findings.append(
                Finding("ethereum", "EIP55", match.group(0), VERIFIED, match.start(), match.end())
            )
        elif result == "unchecked":
            findings.append(
                Finding(
                    "ethereum",
                    "UNCHECKED_ETH",
                    match.group(0),
                    UNCHECKED,
                    match.start(),
                    match.end(),
                )
            )
    return findings


def match_exact(text: str):
    """Return a Finding only if the whole (normalized) text is exactly one
    valid address. Anything extra — a leading word, a trailing character —
    makes this return None."""
    text = normalize(text).strip()
    if not text:
        return None

    m = BASE58_RE.fullmatch(text)
    if m:
        kind = validate_base58(m.group(0))
        if kind:
            return Finding("bitcoin", kind, m.group(0), VERIFIED, 0, len(text))

    m = BECH32_RE.fullmatch(text)
    if m:
        kind = validate_bech32(m.group(0))
        if kind:
            return Finding("bitcoin", kind, m.group(0), VERIFIED, 0, len(text))

    m = HEX_ADDR_RE.fullmatch(text)
    if m:
        result = validate_eip55(m.group(0))
        if result == "eip55":
            return Finding("ethereum", "EIP55", m.group(0), VERIFIED, 0, len(text))
        if result == "unchecked":
            return Finding("ethereum", "UNCHECKED_ETH", m.group(0), UNCHECKED, 0, len(text))
    return None


def filter_alertable(findings, include_unchecked=True):
    """Keep the findings that should trigger an alert.

    Unchecked 0x-addresses (all-lower/upper hex) are alerted by default —
    a legitimate address copied from a contract log often has no checksum
    casing, and a missed warning is worse than a rare false positive.
    Pass include_unchecked=False to silence them.
    """
    return [f for f in findings if include_unchecked or f.confidence == VERIFIED]
