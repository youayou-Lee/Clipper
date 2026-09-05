"""webhook 通知链路(clipper.notify + cli 透传)的单元测试。

用本机 http.server 临时端口收真实请求,不 mock urllib 内部。
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from clipper.cli import _handle_content
from clipper.detect import scan_text
from clipper.notify import build_payload, send_webhook

BTC = "1BitcoinEaterAddressDontSendf59kuE"


class Collector(BaseHTTPRequestHandler):
    body = None
    headers = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        Collector.body = self.rfile.read(length)
        Collector.headers = dict(self.headers)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):  # 静默访问日志
        pass


@pytest.fixture
def server():
    Collector.body = None
    Collector.headers = None
    srv = HTTPServer(("127.0.0.1", 0), Collector)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/hook"
    srv.shutdown()


def test_payload_shape():
    findings = scan_text(BTC)
    payload = build_payload(findings, f"原文 {BTC}")
    assert payload["original_text"] == f"原文 {BTC}"
    assert payload["findings"] == [
        {"chain": "bitcoin", "kind": "P2PKH", "confidence": "verified", "address": BTC}
    ]
    assert payload["ts"]  # 时间戳存在


def test_send_reaches_local_server(server):
    payload = build_payload(scan_text(BTC), BTC)
    assert send_webhook(server, payload) is True
    assert Collector.body is not None
    received = json.loads(Collector.body.decode("utf-8"))
    assert received["findings"][0]["address"] == BTC
    assert Collector.headers.get("Content-Type", "").startswith("application/json")


def test_unreachable_url_returns_false():
    # 不可达端口:返回 False,绝不抛异常
    assert send_webhook("http://127.0.0.1:9/hook", {"x": 1}, timeout=0.5) is False


def test_server_500_returns_false(server):
    # 非 2xx(HTTPError):同样返回 False,不上抛
    class Fail(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(500)
            self.end_headers()

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Fail)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert send_webhook(
            f"http://127.0.0.1:{srv.server_address[1]}/hook", {"x": 1}
        ) is False
    finally:
        srv.shutdown()


class TestMainFlowUnaffectedByWebhookFailure:
    """验收标准 #2:webhook 失败不得影响告警/记录/替换写回主流程。"""

    def _backend_with(self, fixed, url):
        from clipper import safe
        from clipper.watcher import ClipboardWatcher

        class FakeBackend:
            name = "fake"

            def __init__(self):
                self.content = BTC

            def read(self):
                return self.content

            def write(self, text):
                self.content = text
                return True

        b = FakeBackend()
        w = ClipboardWatcher(
            b,
            on_content=lambda t: _handle_content(
                t, None, False, b, safe.load(path=fixed / "safe_address"),
                webhook=url,
            ),
        )
        w.poll_once()
        return b

    def test_unreachable_webhook_rewrite_still_happens(self, tmp_path):
        b = self._backend_with(tmp_path, "http://127.0.0.1:9/hook")
        assert b.content != BTC  # 主流程(替换写回)未受影响

    def test_server_500_rewrite_still_happens(self, tmp_path):
        class Fail(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                self.send_response(500)
                self.end_headers()

            def log_message(self, *args):
                pass

        srv = HTTPServer(("127.0.0.1", 0), Fail)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{srv.server_address[1]}/hook"
            b = self._backend_with(tmp_path, url)
            assert b.content != BTC
        finally:
            srv.shutdown()


def test_handle_content_without_webhook_makes_no_request(server, tmp_path):
    from clipper import safe
    from clipper.watcher import ClipboardWatcher

    fixed = safe.load(path=tmp_path / "safe_address")

    class FakeBackend:
        name = "fake"

        def __init__(self):
            self.content = BTC

        def read(self):
            return self.content

        def write(self, text):
            self.content = text
            return True

    b = FakeBackend()
    # 不传 webhook:正常完成替换写回,本地服务器零请求
    w = ClipboardWatcher(
        b, on_content=lambda t: _handle_content(t, None, False, b, fixed)
    )
    w.poll_once()
    assert b.content != BTC
    assert Collector.body is None


def test_handle_content_with_webhook_posts(server, tmp_path):
    from clipper import safe
    from clipper.watcher import ClipboardWatcher

    fixed = safe.load(path=tmp_path / "safe_address")

    class FakeBackend:
        name = "fake"

        def __init__(self):
            self.content = BTC

        def read(self):
            return self.content

        def write(self, text):
            self.content = text
            return True

    b = FakeBackend()
    w = ClipboardWatcher(
        b, on_content=lambda t: _handle_content(t, None, False, b, fixed,
                                                webhook=server)
    )
    w.poll_once()
    assert Collector.body is not None
    received = json.loads(Collector.body.decode("utf-8"))
    assert received["original_text"] == BTC
    assert received["findings"][0]["address"] == BTC
