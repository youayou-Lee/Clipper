"""GBK 控制台下告警不得崩溃(Windows 真机发现,Issue: GBK UnicodeEncodeError)。"""

import io
import sys

from clipper.alert import alert
from clipper.detect import scan_text

BTC = "1BitcoinEaterAddressDontSendf59kuE"


def test_alert_survives_gbk_stdout(monkeypatch):
    findings = scan_text(f"原文 {BTC}")
    gbk = io.TextIOWrapper(io.BytesIO(), encoding="gbk", errors="strict")
    monkeypatch.setattr(sys, "stdout", gbk)
    alert(findings)  # 修复前:UnicodeEncodeError;修复后:输出(⚠ 被替换),不抛
    gbk.flush()
    out = gbk.buffer.getvalue().decode("gbk")
    assert BTC in out  # 地址可读(replace 而非整段丢失)
    assert "加密货币地址" in out
    assert "⚠" not in out  # 非 GBK 符号被替换为 ?,而不是让整条告警丢失


def test_stderr_reconfigured(monkeypatch):
    import contextlib

    gbk_err = io.TextIOWrapper(io.BytesIO(), encoding="gbk", errors="strict")
    monkeypatch.setattr(sys, "stderr", gbk_err)
    with contextlib.suppress(Exception):
        sys.stderr.write("\u26a0 test\n")
    sys.stderr.flush()  # 修复后 replace 生效,不抛
