"""Detection tests. Published vectors from BIP-173 and EIP-55 where available."""

import unittest

from clipper.detect import UNCHECKED, VERIFIED, filter_alertable, scan_text
from clipper.detect.bech32 import encode_segwit_address

P2PKH = "1BitcoinEaterAddressDontSendf59kuE"
P2SH = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
P2WPKH = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
P2WSH = "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3"
EIP55 = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"


class BitcoinTests(unittest.TestCase):
    def test_p2pkh(self):
        findings = scan_text(f"pls send to {P2PKH} thx")
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0].chain, findings[0].kind), ("bitcoin", "P2PKH"))
        self.assertEqual(findings[0].confidence, VERIFIED)

    def test_p2sh(self):
        self.assertEqual(scan_text(P2SH)[0].kind, "P2SH")

    def test_p2wpkh(self):
        self.assertEqual(scan_text(P2WPKH)[0].kind, "P2WPKH")

    def test_p2wsh(self):
        self.assertEqual(scan_text(P2WSH)[0].kind, "P2WSH")

    def test_taproot_roundtrip(self):
        addr = encode_segwit_address("bc", 1, bytes(range(32)))
        self.assertTrue(addr.startswith("bc1p"))
        self.assertEqual(scan_text(addr)[0].kind, "P2TR")

    def test_uppercase_bech32(self):
        self.assertEqual(scan_text(P2WPKH.upper())[0].kind, "P2WPKH")

    def test_tampered_base58_rejected(self):
        bad = P2PKH[:-1] + ("D" if P2PKH[-1] != "D" else "E")
        self.assertEqual(scan_text(bad), [])

    def test_tampered_bech32_rejected(self):
        bad = P2WPKH[:-1] + ("5" if P2WPKH[-1] != "5" else "6")
        self.assertEqual(scan_text(bad), [])

    def test_mixed_case_bech32_rejected(self):
        self.assertEqual(scan_text("Bc1q" + P2WPKH[4:]), [])


class EthereumTests(unittest.TestCase):
    def test_eip55_verified(self):
        findings = scan_text(f"pay {EIP55} now")
        self.assertEqual((findings[0].chain, findings[0].kind), ("ethereum", "EIP55"))
        self.assertEqual(findings[0].confidence, VERIFIED)

    def test_eip55_vectors(self):
        # The four examples published in EIP-55.
        for addr in (
            "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
            "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
            "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
            "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
        ):
            self.assertEqual(scan_text(addr)[0].confidence, VERIFIED, addr)

    def test_lowercase_unchecked(self):
        findings = scan_text(EIP55.lower())
        self.assertEqual(findings[0].confidence, UNCHECKED)
        # Default: still alert (missed warnings are worse than rare noise)…
        self.assertEqual(len(filter_alertable(findings)), 1)
        # …but --skip-unchecked silences them.
        self.assertEqual(filter_alertable(findings, include_unchecked=False), [])

    def test_wrong_checksum_rejected(self):
        bad = "0x5Aaeb6053F3E94C9b9A09f33669435E7Ef1BeAed"  # one case flipped
        self.assertEqual(scan_text(bad), [])

    def test_tx_hash_not_an_address(self):
        self.assertEqual(scan_text("0x" + "ab" * 32), [])

    def test_bare_git_sha_ignored(self):
        self.assertEqual(scan_text("commit 5f3a7b1c9d2e4f6a8b0c1d3e5f7a9b1c3d5e7f9a"), [])


class NormalizationTests(unittest.TestCase):
    def test_zero_width_characters(self):
        injected = P2WPKH[:6] + chr(0x200B) + P2WPKH[6:]
        self.assertEqual(scan_text(injected)[0].kind, "P2WPKH")

    def test_line_wrapped_address(self):
        self.assertEqual(scan_text(P2SH[:20] + "\n" + P2SH[20:])[0].kind, "P2SH")

    def test_plain_text_no_findings(self):
        self.assertEqual(scan_text("hello world, nothing here 12345"), [])


if __name__ == "__main__":
    unittest.main()
