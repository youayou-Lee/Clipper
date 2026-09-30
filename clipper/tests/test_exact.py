"""match_exact(完全匹配模式)的单元测试。"""

import pytest

from clipper.detect import UNCHECKED, VERIFIED, match_exact

BTC = "1BitcoinEaterAddressDontSendf59kuE"
BCH32 = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
ETH = "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"


def test_btc_base58():
    f = match_exact(BTC)
    assert f and f.chain == "bitcoin" and f.kind == "P2PKH"
    assert f.confidence == VERIFIED and f.address == BTC


def test_bech32():
    f = match_exact(BCH32)
    assert f and f.chain == "bitcoin" and f.kind == "P2WPKH"
    assert f.confidence == VERIFIED


def test_eth_eip55():
    f = match_exact(ETH)
    assert f and f.chain == "ethereum" and f.kind == "EIP55"
    assert f.confidence == VERIFIED


def test_eth_lowercase_unchecked():
    f = match_exact("0xfb6916095ca1df60bb79ce92ce3ea74c37c5d359")
    assert f and f.confidence == UNCHECKED and f.kind == "UNCHECKED_ETH"


@pytest.mark.parametrize(
    "text",
    [
        BTC + "1",  # 末尾多一个字符
        "x" + BTC,  # 开头多一个字符
        f"转账到 {BTC}",  # 夹在句中
        f"{BTC} 谢谢",  # 带尾随文本
        "0x" + "g" * 40,  # 非 hex
        "bc1 illegal !!",  # 像但不是
        "",
    ],
)
def test_rejects_non_exact(text):
    assert match_exact(text) is None


@pytest.mark.parametrize("text", [f"  {BTC} ", f"\n{ETH}\n", f"\t{BCH32}\r\n"])
def test_surrounding_whitespace_tolerated(text):
    assert match_exact(text) is not None
