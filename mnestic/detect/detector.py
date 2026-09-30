"""BIP-39 助记词检出:词表匹配 + 校验和验证。

复现 SparkCat 类木马的核心识别能力:从任意文本(OCR 输出、剪贴板内容等)中
找出 BIP-39 英文助记词序列,并验证其校验和是否自洽。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib import resources

_WORDLIST_FILE = "wordlist_en.txt"

# BIP-39 合法的助记词长度(词数)
VALID_LENGTHS = (12, 15, 18, 21, 24)


def load_wordlist() -> tuple[list[str], frozenset[str]]:
    """加载 BIP-39 英文词表(官方 2048 词,随包分发)。"""
    text = resources.files("mnestic.detect").joinpath(_WORDLIST_FILE).read_text("utf-8")
    words = [w.strip() for w in text.splitlines() if w.strip()]
    if len(words) != 2048:
        raise RuntimeError(f"BIP-39 词表异常:期望 2048 词,实际 {len(words)}")
    return words, frozenset(words)


_WORDLIST, _WORDSET = load_wordlist()
_WORD_TO_INDEX = {w: i for i, w in enumerate(_WORDLIST)}


@dataclass(frozen=True)
class MnemonicHit:
    """一条检出结果:phrase 为原始词序列,checksum_valid 表示校验和自洽。"""

    phrase: str
    word_count: int
    checksum_valid: bool

    def masked(self) -> str:
        """脱敏显示:保首尾词,中间以 * 代替(与 clipper 保头尾思路一致)。"""
        words = self.phrase.split()
        if len(words) <= 2:
            return "*" * len(self.phrase)
        return " ".join([words[0], *["*" * len(w) for w in words[1:-1]], words[-1]])


def validate_checksum(phrase: str) -> bool:
    """验证助记词的 BIP-39 校验和是否自洽(不校验 passphrase)。"""
    words = phrase.lower().split()
    if len(words) not in VALID_LENGTHS:
        return False
    try:
        indices = [_WORD_TO_INDEX[w] for w in words]
    except (KeyError, ValueError):
        return False
    bits = "".join(f"{i:011b}" for i in indices)
    checksum_len = (len(words) * 11) // 33
    entropy_len = len(words) * 11 - checksum_len
    entropy = int(bits[:entropy_len], 2).to_bytes(entropy_len // 8, "big")
    digest = hashlib.sha256(entropy).digest()
    expected = bin(int.from_bytes(digest, "big"))[2:].zfill(256)[:checksum_len]
    return bits[entropy_len:] == expected


def find_mnemonics(text: str) -> list[MnemonicHit]:
    """在文本中找出 12/24 词(及全部合法长度)的 BIP-39 助记词序列。

    匹配规则:连续的纯字母 token 全部命中词表,窗口长度为合法词数;
    同一段文本内的重复命中去重。噪声(大小写、标点、换行)不影响检出,
    但词序中断(夹入一个非词表词)会截断候选——与真实 OCR 场景一致。
    """
    tokens = re.findall(r"[a-z]+", text.lower())
    hits: dict[str, MnemonicHit] = {}
    run: list[str] = []

    def flush_run(run_words: list[str]) -> None:
        for size in sorted(VALID_LENGTHS, reverse=True):
            for start in range(0, len(run_words) - size + 1):
                window = run_words[start : start + size]
                phrase = " ".join(window)
                if phrase not in hits:
                    hits[phrase] = MnemonicHit(
                        phrase=phrase,
                        word_count=size,
                        checksum_valid=validate_checksum(phrase),
                    )

    for token in tokens:
        if token in _WORDSET:
            run.append(token)
        else:
            flush_run(run)
            run = []
    flush_run(run)

    return list(hits.values())
