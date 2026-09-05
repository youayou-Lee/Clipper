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
