# TrapLab — 安全案例实验室

> 本仓库曾名 Clipper;现定位为**安全案例实验室**:每个案例独立成线,按需扩展新方向。
> 各案例的完整说明见各自 README:
>
> - **案例一:剪贴板守护**(Clipper 木马复现与应对)— [`clipper/README.md`](clipper/README.md)
> - **案例二:Web3 授权钓鱼实验室**(Approve / Permit 复现)— [`scripts/README.md`](scripts/README.md),详细 Runbook 见 [`docs/phishing-runbook.md`](docs/phishing-runbook.md)

> **免责声明**:本项目仅用于防御研究、安全教育与意识提升。
> 所有动手实践仅限**本机、自有测试机与自有内网实验室**,
> 严禁指向任何第三方设备或真实用户,那正是本项目要对抗的行为。

## 案例一:剪贴板守护(`clipper/`)

复现 **Clipper 木马**(剪贴板劫持木马)的核心机制:监控剪贴板,检出比特币/以太坊地址
(Base58Check / BIP-173 / EIP-55 校验和闸门)后,在粘贴前把地址替换为本机固化的安全地址变体
(保头 4 尾 4、等长),并告警 + sqlite 审计(保留原始地址)。支持 Windows / macOS / Linux 三端。

示例应对策略:完全匹配替换(默认)、替换后告警 + 审计、`clipper paste` 粘贴时校验、
webhook 外推、威胁研究驱动的检测(进行中)。快速开始与机制明细见 [`clipper/README.md`](clipper/README.md)。

## 案例二:Web3 授权钓鱼实验室(`scripts/`)

在自有内网实验室复现 Approve / EIP-2612 Permit 授权钓鱼的完整攻击链:
受害者侧 100% 拟真假空投站(Approve 交易 / 免 Gas Permit 签名两条路),
攻击者侧 `/admin` 收割台(实时事件流、待收割清单、一键收割)。
默认目标为 Anvil 本地测试链(零真实资产),引擎与目标解耦,
`scripts/targets/` 已实测产出 Anvil / Polygon USDC / BSC USDT 等目标档案。
运行步骤见 [`scripts/README.md`](scripts/README.md)。

## 威胁研究

方法论:**先以攻击者视角构建完整攻击链,再切防守者视角做检测点映射与对抗方案**。
跟踪:[Issue #23](https://github.com/youayou-Lee/TrapLab/issues/23)。产物:

- [`docs/research/attack-chain.md`](docs/research/attack-chain.md) — 攻击链全景(分发/免杀/加载/持久化/劫持/变现,全部厂商报告溯源)
- [`docs/research/defense-mapping.md`](docs/research/defense-mapping.md) — 逐环节检测点映射、对策分级与攻防不对称分析

## 工程规范

本项目走 Issue 驱动的 GitHub Flow(见 `docs/WORKFLOW.md` 与 `AGENTS.md`):先立 Issue(可测试验收标准)
→ feat 分支 → 测试绿才 commit → PR 四要素 → CI 绿 + 代码审核 → squash merge → CHANGELOG。
