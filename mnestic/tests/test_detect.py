"""mnestic.detect 单元测试:BIP-39 词表匹配与校验和验证。"""

import pytest

from mnestic.detect.detector import MnemonicHit, find_mnemonics, validate_checksum

# BIP-39 官方测试向量:entropy 全零的 12 词助记词(校验和自洽)
VALID_12 = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
# 同上把末词换成 abandon:词表全命中但校验和不自洽
INVALID_CHECKSUM_12 = " ".join(["abandon"] * 12)
# BIP-39 校验和自洽的 24 词向量(256 位全一熵,由官方算法程序化生成)
VALID_24 = "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo vote"


class TestValidateChecksum:
    def test_official_vector_12_words_valid(self):
        assert validate_checksum(VALID_12) is True

    def test_official_vector_24_words_valid(self):
        assert validate_checksum(VALID_24) is True

    def test_all_wordlist_words_invalid_checksum(self):
        assert validate_checksum(INVALID_CHECKSUM_12) is False

    def test_word_not_in_wordlist(self):
        bad = VALID_12.replace("about", "notaword")
        assert validate_checksum(bad) is False

    @pytest.mark.parametrize("count", [11, 13, 0, 23, 25])
    def test_invalid_lengths_rejected(self, count):
        assert validate_checksum(" ".join(["abandon"] * count)) is False

    def test_case_and_whitespace_noise_tolerated(self):
        noisy = "  Abandon   ABANDON abandon\nabandon\tabandon abandon abandon abandon abandon abandon ABANDON About "
        assert validate_checksum(" ".join(noisy.split()).lower()) is True


class TestFindMnemonics:
    def test_finds_valid_12_in_plain_text(self):
        hits = find_mnemonics(f"my seed: {VALID_12} keep it safe")
        target = [h for h in hits if h.phrase == VALID_12]
        assert len(target) == 1 and target[0].checksum_valid is True

    def test_finds_24_word_hit(self):
        hits = find_mnemonics(VALID_24)
        target = [h for h in hits if h.phrase == VALID_24]
        assert len(target) == 1 and target[0].word_count == 24

    def test_detects_even_with_invalid_checksum(self):
        hits = find_mnemonics(INVALID_CHECKSUM_12)
        assert [h for h in hits if h.checksum_valid is False]

    def test_punctuation_and_newline_noise(self):
        text = f"Seed:\n{VALID_12}.\n(Note: write it down!)"
        assert any(h.phrase == VALID_12 for h in find_mnemonics(text))

    def test_non_wordlist_word_breaks_run(self):
        text = VALID_12.replace("about", "zzzzz")
        assert find_mnemonics(text) == []

    def test_plain_text_without_mnemonics(self):
        assert find_mnemonics("the quick brown fox jumps over the lazy dog") == []
        assert find_mnemonics("") == []

    def test_dedup_same_phrase(self):
        hits = find_mnemonics(f"{VALID_12} ... again: {VALID_12}")
        assert [h.phrase for h in hits].count(VALID_12) == 1

    def test_long_wordlist_run_yields_both_12_and_24_windows(self):
        # 24 个 abandon:既是"24 词窗口"也是"12 词窗口",至少各出一个命中
        text = " ".join(["abandon"] * 24)
        hits = find_mnemonics(text)
        counts = {h.word_count for h in hits}
        assert 12 in counts and 24 in counts

    def test_masked_keeps_first_last_word(self):
        hit = MnemonicHit(phrase=VALID_12, word_count=12, checksum_valid=True)
        masked = hit.masked()
        assert masked.startswith("abandon ")
        assert masked.endswith(" about")
        assert "abandon " * 3 not in masked


class TestWordlist:
    def test_wordlist_loaded_exactly_2048(self):
        from mnestic.detect.detector import _WORDLIST

        assert len(_WORDLIST) == 2048
        assert _WORDLIST[0] == "abandon"
        assert _WORDLIST[-1] == "zoo"
