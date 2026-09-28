# Approve/Permit 授权钓鱼复现 Runbook(Issue #56)

> ⚠ 仅供本地安全教育演示:全程在本机 Anvil 模拟链上进行,使用 Anvil 公开测试
> 私钥,**零真实资产**。禁止将任何脚本/页面指向真实环境。

你将扮演受害者,亲眼看到:点一次"领取空投",钱包里的代币如何被搬空——
甚至**一笔交易都不用发**(permit 场景)。

前提:已装 [Foundry](https://book.getfoundry.sh)(`anvil`/`cast`/`forge`),Chrome + MetaMask 扩展。
`~/.foundry/bin` 不在 PATH 时自行补全。

| 角色 | 来源 |
|---|---|
| 受害者 | Anvil 测试账户 #0(`0xf39F…2266`,私钥 `0xac09…ff80`,导入 MetaMask) |
| 攻击者 | Anvil 测试账户 #1(`0x7099…79C8`,脚本默认私钥,无需安装任何东西) |

## 1. 起链、部署代币、给受害者发币

```bash
anvil --chain-id 31337 --port 8546 &          # 记下 PID,收尾时 kill
cd scripts/contracts
forge create PhishingToken --broadcast \
  --private-key 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d \
  --rpc-url http://127.0.0.1:8546
# 记下 "Deployed to: 0x…" 即代币地址 TOKEN
TOKEN=<代币地址>
cast send $TOKEN "transfer(address,uint256)" \
  0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 1000000000000000000000 \
  --private-key 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d \
  --rpc-url http://127.0.0.1:8546
# 给受害者 1000 AIRDROP(模拟"之前领过的空投",让钱包里有肉)
```

## 2. 打开钓鱼页

```bash
cd scripts && python3 -m http.server 8080
# Chrome 打开 http://127.0.0.1:8080/phishing_demo.html
```

MetaMask 配置:导入账户 → 粘贴测试私钥
`0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80`;
添加网络 Anvil Local(RPC `http://127.0.0.1:8546`,链 ID `31337`)。
页面首次点击按钮会要求你粘贴 TOKEN 地址(存 localStorage,之后免填)。

## 3. 场景一:无限 approve(主场景)

1. 点绿色按钮「连接钱包,领取空投」。
2. MetaMask 弹出确认——注意:界面上写的是 **Approve(允许spender动用你的 AIRDROP)**
   和一个天文字,而页面语境是"领取"。真实受害者就是在这里被骗的。
3. 确认。页面会打出一条收割命令,复制到终端执行:

```bash
uv run python scripts/drain.py --tx <页面给的哈希> --token $TOKEN
```

预期输出:受害者 `1000e18 → 0`,攻击者等额增加。

## 4. 场景二:permit(受害者零交易)

点「gasless 领取(免 gas 签名)」→ MetaMask 弹出**签名请求**(不是交易)→
确认后复制页面给的收割命令执行。注意终端输出会说明:受害者没有发过任何
交易,只签过一个名——链上除收割交易外没有任何受害者痕迹。

## 5. 对比场景:精确授权

先重发点币(§1 的 transfer 1000),再点「需签名两次的版本」(approve 1000)。
收割后受害者余额只减 1000,攻击者**拿不到额度之外的一分钱**——这就是
"无限授权"与"精确授权"的差别,也是签名哨兵(见
`docs/research/defense-mapping.md` §7)死守前者的原因。

## 6. 收尾

`kill <anvil PID>`、Ctrl-C http.server;`pgrep -x anvil` 确认无残留。
