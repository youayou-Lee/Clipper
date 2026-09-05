"""User-facing alerts: console line only (no desktop popups)."""

import datetime
import sys

from .detect import UNCHECKED, VERIFIED


def _safe_console():
    """GBK 等窄码页控制台遇 ⚠ 等字符会抛 UnicodeEncodeError(Windows 真机实测),
    把错误策略降级为 replace:输出不中断,个别符号显示为 ?。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass


def alert(findings) -> None:
    _safe_console()
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"\n⚠  [{ts}] 剪贴板中发现 {len(findings)} 个加密货币地址:", flush=True)
    for f in findings:
        if f.confidence == VERIFIED:
            conf = "校验和已验证"
        elif f.confidence == UNCHECKED:
            conf = "无大小写信息,未校验"
        else:
            conf = f.confidence
        print(f"   {f.chain:<8} {f.kind:<13} [{conf}] {f.address} 请注意检查该地址！！！")
    print("   ⚠ 粘贴前请与来源逐字符核对首尾 8 位字符。", flush=True)
