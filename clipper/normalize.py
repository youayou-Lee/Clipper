"""Clipboard text normalization.

Addresses copied out of messengers, PDFs or terminals often pick up
zero-width characters that break candidate extraction — and invisible
characters are also a typosquatting trick. Strip them before scanning.

Whitespace is collapsed to single spaces (not removed) so that word
boundaries stay intact; the scanner additionally runs a whitespace-
stripped pass to catch addresses wrapped across lines.
"""

import re
import unicodedata

# Zero-width and invisible formatting characters, by codepoint:
# 200B zero width space, 200C ZWNJ, 200D ZWJ, 2060 word joiner,
# FEFF zero width no-break space (BOM), 00AD soft hyphen.
_INVISIBLE = frozenset(map(chr, (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD)))

_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Remove invisible characters; collapse whitespace to single spaces."""
    out = []
    for ch in text:
        if ch in _INVISIBLE:
            continue
        if unicodedata.category(ch) == "Zs":  # any Unicode space (incl. NBSP)
            out.append(" ")
        else:
            out.append(ch)
    return _WS_RE.sub(" ", "".join(out))
