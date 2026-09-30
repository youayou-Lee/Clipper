"""_handle_content 链路(exact/contains 模式、写回失败、防循环)的组件测试。"""

import pytest

from clipper.cli import _handle_content
from clipper.watcher import ClipboardWatcher

BTC = "1BitcoinEaterAddressDontSendf59kuE"
ETH = "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"


class FakeBackend:
    name = "fake"

    def __init__(self, content=""):
        self.content = content
        self.write_ok = True
        self.written = []

    def available(self):
        return True

    def read(self):
        return self.content

    def write(self, text):
        if not self.write_ok:
            return False
        self.written.append(text)
        self.content = text
        return True


@pytest.fixture
def fixed(tmp_path):
    from clipper import safe

    return safe.load(path=tmp_path / "safe_address")


def run(text, fixed, backend, contains=False, skip_unchecked=False):
    return _handle_content(text, None, skip_unchecked, backend, fixed, contains=contains)


class TestExactMode:
    def test_pure_address_rewritten(self, fixed):
        b = FakeBackend(BTC)
        run(BTC, fixed, b)
        assert len(b.written) == 1
        out = b.written[0]
        assert len(out) == len(BTC)
        assert out != BTC
        assert out[:4] == BTC[:4] and out[-4:] == BTC[-4:]

    def test_text_with_context_untouched(self, fixed):
        text = f"转账到 {BTC} 谢谢"
        b = FakeBackend(text)
        run(text, fixed, b)
        assert b.written == []  # 只告警,不改写

    def test_trailing_char_untouched(self, fixed):
        text = BTC + "1"
        b = FakeBackend(text)
        run(text, fixed, b)
        assert b.written == []

    def test_no_addresses_no_write(self, fixed):
        b = FakeBackend("明天十点开会")
        assert run("明天十点开会", fixed, b) is None
        assert b.written == []


class TestContainsMode:
    def test_address_in_sentence_replaced_in_place(self, fixed):
        text = f"BTC: {BTC}\nETH: {ETH}"
        b = FakeBackend(text)
        run(text, fixed, b, contains=True)
        assert len(b.written) == 1
        out = b.written[0]
        assert BTC not in out and ETH not in out
        assert out.startswith("BTC: ") and "\nETH: " in out

    def test_unchecked_skipped(self, fixed):
        text = "0xfb6916095ca1df60bb79ce92ce3ea74c37c5d359"
        b = FakeBackend(text)
        run(text, fixed, b, contains=True, skip_unchecked=True)
        assert b.written == []  # 未校验地址被跳过,不替换


class TestFailurePaths:
    def test_write_failure_returns_none_no_exception(self, fixed):
        b = FakeBackend(BTC)
        b.write_ok = False
        assert run(BTC, fixed, b) is None

    def test_no_backend_still_alerts_without_write(self, fixed):
        # backend=None(如 scan 路径):不写回、不抛异常
        assert _handle_content(BTC, None, False, None, fixed) is None

    def test_no_safe_address_no_write(self):
        b = FakeBackend(BTC)
        _handle_content(BTC, None, False, b, None)
        assert b.written == []


class TestNoAlertLoop:
    def test_rewritten_content_is_new_baseline(self, fixed):
        b = FakeBackend(BTC)
        watcher = ClipboardWatcher(
            b, on_content=lambda t: run(t, fixed, b)
        )
        assert watcher.poll_once() is True
        first = b.content
        assert first != BTC  # 已被改写
        assert watcher.poll_once() is False  # 改写不再触发新一轮
        assert b.content == first  # 内容稳定,不会追加
