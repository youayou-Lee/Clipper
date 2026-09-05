"""Command line interface."""

import argparse
import json
import sys

from . import __version__
from .alert import alert, safe_console
from .detect import filter_alertable, match_exact, scan_text
from .history import recent, record
from .watcher import ClipboardWatcher
from . import safe

_BACKEND_HINT = (
    "[clipper] 没有可用的剪贴板后端。\n"
    "  X11:     sudo apt install xclip\n"
    "  Wayland: sudo apt install wl-clipboard"
)


def _get_backend():
    from .platforms import get_backend

    backend = get_backend()
    if backend is None:
        sys.exit(_BACKEND_HINT)
    return backend


_WARNING = "请注意检查该地址！！！"


def _handle_content(text, db_path, skip_unchecked, backend=None, safe_address=None,
                    contains=False, webhook=None):
    findings = scan_text(text)
    alertable = filter_alertable(findings, include_unchecked=not skip_unchecked)
    if not alertable:
        return None
    alert(alertable)
    record(alertable, db_path)
    if webhook:
        from .notify import build_payload, send_webhook
        from urllib.parse import urlsplit

        if not send_webhook(webhook, build_payload(alertable, text)):
            # 只显示 scheme+host,避免用户 URL 里带的 token 进日志
            host = urlsplit(webhook).netloc
            print(f"[clipper] webhook 通知失败: {host}", file=sys.stderr, flush=True)
    if backend is None or not safe_address:
        return None
    if contains:
        targets = [f.address for f in alertable]
    else:
        # 完全匹配模式(默认):剪贴板整体必须是恰好一个合法地址才替换,
        # 地址前后多一个字符都不动,避免把正常文本里的地址改坏。
        exact = match_exact(text)
        targets = [exact.address] if exact else []
    if not targets:
        return None
    marked = text
    for addr in targets:
        marked = marked.replace(addr, safe.splice(addr, safe_address))
    if backend.write(marked):
        print(
            f"[clipper] 地址已替换为固定地址变体并写回剪贴板(基准: {safe_address})",
            flush=True,
        )
        return marked
    print("[clipper] 剪贴板写入失败,无法替换地址", file=sys.stderr, flush=True)
    return None


def main(argv=None):
    safe_console()  # 必须先于任何输出:粘贴/--json 会回显剪贴板里的任意字符
    parser = argparse.ArgumentParser(
        prog="clipper",
        description="剪贴板守护:检测比特币/以太坊地址(校验和验证),粘贴前告警。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_watch = sub.add_parser("watch", help="常驻监控剪贴板")
    p_watch.add_argument("--interval", type=float, default=0.8, help="轮询间隔(秒)")
    p_watch.add_argument("--db", help="历史 sqlite 路径(默认按平台数据目录)")
    p_watch.add_argument(
        "--skip-unchecked", action="store_true", help="不对未校验的 0x 地址告警"
    )
    p_watch.add_argument(
        "--contains",
        action="store_true",
        help="包含模式:文本中任何位置检出地址都替换(默认仅剪贴板整体为一个地址时替换)",
    )
    p_watch.add_argument(
        "--webhook", help="检出地址时向该 URL POST JSON 通知(3s 超时,失败仅警告)"
    )

    p_scan = sub.add_parser("scan", help="扫描当前剪贴板或指定文本")
    p_scan.add_argument("--text", help="扫描指定文本而不是当前剪贴板")
    p_scan.add_argument("--json", action="store_true", help="以 JSON 输出结果")

    p_paste = sub.add_parser(
        "paste", help="代替 Ctrl+V:原样输出剪贴板原文,检出地址时在其后追加提示"
    )
    p_paste.add_argument("--db", help="历史 sqlite 路径(默认按平台数据目录)")
    p_paste.add_argument(
        "--skip-unchecked", action="store_true", help="不对未校验的 0x 地址提示"
    )

    p_addr = sub.add_parser(
        "address", help="查看/生成固定安全地址(检出地址时替换成它)"
    )
    p_addr.add_argument(
        "--regenerate", action="store_true", help="丢弃旧地址,重新随机生成并固化"
    )

    p_hist = sub.add_parser("history", help="查看最近检出的地址")
    p_hist.add_argument("--limit", type=int, default=20)
    p_hist.add_argument("--db")

    args = parser.parse_args(argv)

    if args.command == "watch":
        backend = _get_backend()
        safe_address = safe.load()
        watcher = ClipboardWatcher(
            backend,
            interval=args.interval,
            on_content=lambda text: _handle_content(
                text, args.db, args.skip_unchecked, backend, safe_address,
                contains=args.contains, webhook=args.webhook,
            ),
        )
        watcher.run()
    elif args.command == "address":
        addr = safe.load(force=args.regenerate)
        print(f"固定安全地址: {addr}")
        print(f"(存于 {safe.default_config_path()},重新生成: clipper address --regenerate)")
    elif args.command == "scan":
        text = args.text if args.text is not None else _get_backend().read()
        if not text:
            print("[clipper] 剪贴板为空或不可读")
            return
        findings = scan_text(text)
        if args.json:
            print(
                json.dumps(
                    [
                        {
                            "chain": f.chain,
                            "kind": f.kind,
                            "confidence": f.confidence,
                            "address": f.address,
                            "preview": f.preview,
                        }
                        for f in findings
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif findings:
            alert(findings)
        else:
            print("[clipper] 未发现加密货币地址")
    elif args.command == "paste":
        text = _get_backend().read()
        if not text:
            print("[clipper] 剪贴板为空或不可读")
            return
        print(text)
        alertable = filter_alertable(
            scan_text(text), include_unchecked=not args.skip_unchecked
        )
        if alertable:
            print("请注意检查该地址！！！", flush=True)
            record(alertable, args.db)
    elif args.command == "history":
        rows = recent(args.limit, args.db)
        if not rows:
            print("[clipper] 历史为空")
            return
        print(f"{'时间':<21}{'链':<10}{'类型':<14}{'置信':<10}地址")
        for ts, chain, kind, confidence, address in rows:
            print(f"{ts:<21}{chain:<10}{kind:<14}{confidence:<10}{address}")


if __name__ == "__main__":
    main()
