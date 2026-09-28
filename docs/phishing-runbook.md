# Web3 授权钓鱼复现 Runbook(TrapLab 案例二,Issue #59)

> ⚠ 仅限**自有内网实验室**演练:Anvil 测试链 + 公开测试私钥,零真实资产。
> 受害者页面 100% 拟真、不含任何演示字样;安全边界由本文件与 `/admin` 横幅承载。

角色:受害者 = Anvil 测试账户 #0(导入 MetaMask);攻击者 = 账户 #1(见 config)。

## 1. 起链、部署假币、配置

```bash
anvil --chain-id 31337 --port 8546 &
export PATH="$HOME/.foundry/bin:$PATH"
cd scripts/contracts
forge create PhishingToken --broadcast \
  --private-key 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d \
  --rpc-url http://127.0.0.1:8546
# 记下 Deployed to: 0x… 
cp config.example.yaml config.yaml    # 已 gitignore;把 token.address 改成上面的地址
```

想演示"精确授权有上限"的对比,把 `site.claim_mode` 改成 `exact`。

## 2. 启动钓鱼实验室

```bash
uv run python scripts/phish_server.py --config scripts/config.yaml
```

两个入口:
- **受害者**:`http://<内网IP或localhost>:8088/` —— 逼真假空投站
- **攻击者**:`http://localhost:8088/admin?key=traplab` —— 收割台(口令见 config)

## 3. 受害者侧(MetaMask)

1. MetaMask 导入测试私钥 `0xac09…ff80`,网络指到钓鱼站添加的 `NovaChain Mainnet`(即本机 Anvil);
2. 打开钓鱼站 → 连接钱包 → 点「立即领取」→ MetaMask 确认(Approve);
   或点「免 Gas 领取」→ MetaMask 签名(EIP-712,无交易);
3. 页面显示"核销成功,10 分钟内到账"——然后什么都不会发生,这就是攻击得手后的受害者体验。

## 4. 攻击者侧(收割台)

打开 `/admin`:
- 实时事件流出现"受害者连接钱包 / 已签署授权";
- 待收割清单出现新条目 → 点「收割」;
- 状态变"已收割",事件流打印受害者与攻击者余额变化;MetaMask 里核对代币余额归零。

## 5. 收尾

Ctrl-C 停 phish_server;`kill %1` 停 anvil;`pgrep -x anvil` 确认无残留。
permit 的 nonce 固定 0,同一受害者只能演示一次 permit,重演请重启 anvil 或换测试账户。
