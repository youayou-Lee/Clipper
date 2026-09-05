"""Bech32 / Bech32m codec (BIP-173 / BIP-350), as used by SegWit addresses.

Pure Python reference-style implementation; no external dependencies.
"""

_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_INDEX = {c: i for i, c in enumerate(_CHARSET)}
_BECH32M_CONST = 0x2BC830A3

# Address human-readable parts: mainnet and testnet/signet.
_HRPS = ("bc", "tb")


def _polymod(values):
    gen = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            if (top >> i) & 1:
                chk ^= gen[i]
    return chk


def _hrp_expand(hrp):
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _convert_bits(data, from_bits, to_bits, pad=True):
    """Regroup a bit stream, MSB first (5-bit <-> 8-bit for SegWit)."""
    acc = bits = 0
    ret = []
    maxv = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        if value < 0 or value >> from_bits:
            return None
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        return None
    return ret


def decode_segwit_address(address):
    """Decode a bc1/tb1 address into (witness_version, program) or None.

    Enforces BIP-173/BIP-350 rules: single case, valid charset, checksum
    constant per witness version, and standard program lengths
    (v0: 20 or 32 bytes; v1: 32 bytes).
    """
    addr = address.strip()
    if addr.lower() != addr and addr.upper() != addr:
        return None  # mixed case is invalid
    addr = addr.lower()
    pos = addr.rfind("1")  # '1' is not in the charset, so this is the separator
    if pos < 1 or pos + 7 > len(addr):  # need >= 6 checksum + 1 version char
        return None
    hrp = addr[:pos]
    if hrp not in _HRPS:
        return None
    data = []
    for ch in addr[pos + 1 :]:
        idx = _INDEX.get(ch)
        if idx is None:
            return None
        data.append(idx)
    if not data or data[0] > 16:
        return None
    version = data[0]
    # The last 6 values are the checksum: strip them before regrouping the
    # witness program, and verify them against the full data below.
    program = _convert_bits(data[1:-6], 5, 8, pad=False)
    if program is None or not 2 <= len(program) <= 40:
        return None
    if version == 0 and len(program) not in (20, 32):
        return None
    if version == 1 and len(program) != 32:
        return None
    const = _polymod(_hrp_expand(hrp) + data)
    if const != (1 if version == 0 else _BECH32M_CONST):
        return None
    return version, bytes(program)


def encode_segwit_address(hrp, version, program):
    """Encode (hrp, witness_version, program) into a Bech32 address."""
    data = [version] + _convert_bits(program, 8, 5)
    const = 1 if version == 0 else _BECH32M_CONST
    polymod = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ const
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_CHARSET[d] for d in data + checksum)
