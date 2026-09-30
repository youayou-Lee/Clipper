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


class Always500(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(500)
        self.end_headers()

    def log_message(self, *args):
        pass


def _start(handler):
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def server():
    Collector.body = None
    Collector.headers = None
    srv = _start(Collector)
    yield f"http://127.0.0.1:{srv.server_address[1]}/hook"
    srv.shutdown()


@pytest.fixture
def fail_server():
    srv = _start(Always500)
    yield f"http://127.0.0.1:{srv.server_address[1]}/hook"
    srv.shutdown()


class FakeBackend:
    name = "fake"

    def __init__(self):
        self.content = BTC

    def read(self):
        return self.content

    def write(self, text):
        self.content = text
        return True


@pytest.fixture
def fixed(tmp_path):
    from clipper import safe

    return safe.load(path=tmp_path / "safe_address")


def _watch_once(backend, fixed, webhook=None):
    from clipper.watcher import ClipboardWatcher

    w = ClipboardWatcher(
        backend,
        on_content=lambda t: _handle_content(
            t, None, False, backend, fixed, webhook=webhook
        ),
    )
    w.poll_once()


def test_payload_shape():
    findings = scan_text(BTC)
    payload = build_payload(findings, f"原文 {BTC}")
    assert payload["original_text"] == f"原文 {BTC}"
    assert payload["findings"] == [
        {"chain": "bitcoin", "kind": "P2PKH", "confidence": "verified", "address": BTC}
    ]
    ts = payload["ts"]
    assert ts  # 时间戳存在
    # 带时区偏移 + 微秒精度(0.8s 轮询间隔下同秒事件也能区分先后)
    assert ("+" in ts[10:] or "-" in ts[10:] or "Z" in ts)
    assert "." in ts


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


def test_server_500_returns_false(fail_server):
    # 非 2xx(HTTPError):同样返回 False,不上抛
    assert send_webhook(fail_server, {"x": 1}) is False


class TestMainFlowUnaffectedByWebhookFailure:
    """验收标准 #2:webhook 失败不得影响告警/记录/替换写回主流程。"""

    def test_unreachable_webhook_rewrite_still_happens(self, fixed):
        b = FakeBackend()
        _watch_once(b, fixed, webhook="http://127.0.0.1:9/hook")
        assert b.content != BTC  # 主流程(替换写回)未受影响

    def test_server_500_rewrite_still_happens(self, fixed, fail_server):
        b = FakeBackend()
        _watch_once(b, fixed, webhook=fail_server)
        assert b.content != BTC


def test_handle_content_without_webhook_makes_no_request(server, fixed):
    b = FakeBackend()
    # 不传 webhook:正常完成替换写回,本地服务器零请求
    _watch_once(b, fixed)
    assert b.content != BTC
    assert Collector.body is None


def test_handle_content_with_webhook_posts(server, fixed):
    b = FakeBackend()
    _watch_once(b, fixed, webhook=server)
    assert Collector.body is not None
    received = json.loads(Collector.body.decode("utf-8"))
    assert received["original_text"] == BTC
    assert received["findings"][0]["address"] == BTC
