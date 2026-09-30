"""L2 组件测试:C2 模拟器(回环 fail-closed、回传闭环、入库)。"""

import json
import sqlite3
import urllib.error
import urllib.request

import pytest

from mnestic.c2 import exfiltrate, record_exfil, start_c2

SAMPLE = [
    {"image": "/tmp/a.png", "phrase": "abandon abandon about", "word_count": 3, "checksum_valid": False},
    {"image": "/tmp/b.png", "phrase": "zoo zoo vote", "word_count": 3, "checksum_valid": False},
]


@pytest.fixture
def c2_server(tmp_path):
    db = tmp_path / "c2.db"
    server = start_c2(port=0, db_path=db)  # port=0:由内核分配空闲端口
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/exfil", db
    server.shutdown()
    server.server_close()


class TestStartC2:
    def test_rejects_non_loopback_bind(self, tmp_path):
        with pytest.raises(RuntimeError, match="非回环"):
            start_c2(port=0, db_path=tmp_path / "c2.db", host="0.0.0.0")

    def test_rejects_lan_address(self, tmp_path):
        with pytest.raises(RuntimeError, match="非回环"):
            start_c2(port=0, db_path=tmp_path / "c2.db", host="192.168.1.10")


class TestExfilRoundtrip:
    def test_exfiltrate_to_local_c2(self, c2_server):
        url, db = c2_server
        result = exfiltrate(url, SAMPLE)
        assert result == {"ok": True, "count": 2}

        conn = sqlite3.connect(db)
        try:
            rows = conn.execute("SELECT image, phrase, word_count, checksum_valid FROM exfil").fetchall()
        finally:
            conn.close()
        assert len(rows) == 2
        assert rows[0][0] == "/tmp/a.png"

    def test_exfiltrate_empty_findings(self, c2_server):
        url, _ = c2_server
        assert exfiltrate(url, []) == {"ok": True, "count": 0}

    def test_malformed_payload_rejected(self, c2_server):
        url, _ = c2_server
        req = urllib.request.Request(
            url, data=b"not json", headers={"Content-Type": "application/json"}, method="POST"
        )
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(req, timeout=5)
        assert excinfo.value.code == 400

    def test_unknown_path_404(self, c2_server):
        url, _ = c2_server
        bad = url.replace("/exfil", "/other")
        req = urllib.request.Request(bad, data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(req, timeout=5)
        assert excinfo.value.code == 404


class TestRecordExfil:
    def test_normalizes_missing_fields(self, tmp_path):
        db = tmp_path / "c2.db"
        count = record_exfil([{"phrase": "only phrase"}], db)
        assert count == 1
        conn = sqlite3.connect(db)
        try:
            row = conn.execute("SELECT image, word_count, checksum_valid FROM exfil").fetchone()
        finally:
            conn.close()
        assert row == ("", 0, 0)
