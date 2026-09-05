"""端到端演示:把一组真实世界的剪贴板场景送进检测器。

不需要剪贴板后端,直接扫描文本;每个场景带预期结果并自动判定 PASS/FAIL,
因此也可以当作冒烟测试用:

    .venv/bin/python scripts/demo.py

演示中出现的地址全部来自 BIP-173 / EIP-55 官方测试向量等公开资料。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipper.detect import UNCHECKED, VERIFIED, scan_text

BC1_P2WPKH = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
P2PKH_EATER = "1BitcoinEaterAddressDontSendf59kuE"
P2SH = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"

_CONF = {VERIFIED: "校验和已验证", UNCHECKED: "未校验"}


def scenario(title, clipboard, expect, context="", note=""):
    return {
        "title": title,
        "clipboard": clipboard,   # 送进扫描器的内容
        "context": context,       # 仅展示,不扫描
        "expect": expect,         # {"count": n[, "confidence": ..., "kind": ...]}
        "note": note,
    }


SCENARIOS = [
    scenario(
        "普通聊天消息",
        "明早十点开会,记得把上季度的报表带一下",
        {"count": 0},
        note="日常内容不应触发任何告警",
    ),
    scenario(
        "从交易所复制的合法 SegWit 地址",
        f"收款地址:{BC1_P2WPKH} 请查收",
        {"count": 1, "confidence": VERIFIED, "kind": "P2WPKH"},
        note="bech32 校验和验证通过,弹提示提醒核对首尾",
    ),
    scenario(
        "【模拟攻击】剪贴板地址已被替换",
        P2SH,
        {"count": 1, "confidence": VERIFIED, "kind": "P2SH"},
        context=f"用户复制的是 {P2PKH_EATER},木马在粘贴前把它换成了下面的地址",
        note="告警的地址不是用户以为的那个 —— 这就是 clipper 攻击现场",
    ),
    scenario(
        "零宽字符注入(混淆规避手法)",
        BC1_P2WPKH[:6] + chr(0x200B) + BC1_P2WPKH[6:],
        {"count": 1, "confidence": VERIFIED},
        note="清洗层剥离隐形字符后应照常检出",
    ),
    scenario(
        "PDF / 邮件里被换行截断的地址",
        P2SH[:20] + "\n" + P2SH[20:],
        {"count": 1, "confidence": VERIFIED},
        note="第二遍去空白扫描应把断行接回来",
    ),
    scenario(
        "纯小写 ETH 地址(无大小写校验信息)",
        "0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed",
        {"count": 1, "confidence": UNCHECKED},
        note="默认仍告警并标注【未校验】;--skip-unchecked 可关闭",
    ),
    scenario(
        "噪音:交易哈希 + git commit SHA",
        "txid 0x" + "ab" * 32 + " commit 5f3a7b1c9d2e4f6a8b0c1d3e5f7a9b1c3d5e7f9a",
        {"count": 0},
        note="64 位哈希和无 0x 前缀的 40 位串都不是地址,不应打扰",
    ),
    scenario(
        "手打错一个字符的地址(校验和不通过)",
        BC1_P2WPKH[:-1] + ("5" if BC1_P2WPKH[-1] != "5" else "6"),
        {"count": 0},
        note="不告警 ≠ 可放心转:打错的地址校验和同样不通过,转账前必须人工核对",
    ),
]


def display(clipboard):
    text = clipboard.replace(chr(0x200B), "<ZWSP>").replace("\n", "⏎")
    return text if len(text) <= 64 else text[:61] + "…"


def check(findings, expect):
    if len(findings) != expect.get("count", 0):
        return False
    if findings and expect.get("confidence"):
        if findings[0].confidence != expect["confidence"]:
            return False
    if findings and expect.get("kind"):
        if findings[0].kind != expect["kind"]:
            return False
    return True


def main():
    width = 72
    print("=" * width)
    print(f"Clipper 端到端场景演示(共 {len(SCENARIOS)} 个场景)")
    print("=" * width)

    passed = 0
    for i, s in enumerate(SCENARIOS, 1):
        findings = scan_text(s["clipboard"])
        ok = check(findings, s["expect"])
        passed += ok

        print(f"\n[{i}] {s['title']}")
        if s["context"]:
            print(f"    背景: {s['context']}")
        print(f"    剪贴板: {display(s['clipboard'])}")
        if findings:
            for f in findings:
                print(f"    → {f.chain:<8} {f.kind:<13} [{_CONF[f.confidence]}] {f.preview}")
        else:
            print("    → (未检出)")
        want = s["expect"]
        expect_str = f"预期 {want.get('count', 0)} 条"
        if want.get("confidence"):
            expect_str += f" / {_CONF[want['confidence']]}"
        if want.get("kind"):
            expect_str += f" / {want['kind']}"
        print(f"    {'✓ PASS' if ok else '✗ FAIL'} ({expect_str})")
        if s["note"]:
            print(f"    ※ {s['note']}")

    print("\n" + "=" * width)
    print(f"结果: {passed}/{len(SCENARIOS)} 通过")
    print("=" * width)
    return 0 if passed == len(SCENARIOS) else 1


if __name__ == "__main__":
    sys.exit(main())
