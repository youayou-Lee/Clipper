# Clipper — 复现 Clipper 木马,研究应对

本项目复现 **Clipper 木马**(剪贴板劫持木马)的核心机制并开源,供公众分析其原理,
在此基础上制定与验证应对策略;仓库同时给出**示例应对策略**的实际实现。

> **免责声明**:本项目仅用于防御研究、安全教育与意识提升。
> 仓库中的"替换写回"等机制默认工作在**本机、防护者视角**(替换目标是本机固化的安全地址,
> 历史记录保留原始地址供核对)。**一切动手实践仅限本机与自有局域网内的自有测试机**
> (攻击链演练实验室,见 [Issue #38](https://github.com/youayou-Lee/Clipper/issues/38)),
> 严禁指向任何第三方设备或真实用户,那正是本项目要对抗的行为。

## Clipper 木马是什么

剪贴板劫持木马常驻受害者机器,监控剪贴板:一旦发现比特币/以太坊地址,立刻在粘贴前
把它替换成攻击者的地址。受害者视觉上无法分辨(地址同样合法、通过校验和),转账于是
打进攻击者钱包。它不需要提权、不需要联网回传,是门槛极低却极其阴险的攻击。

## 本仓库复现了什么

| 机制 | 位置 | 说明 |
|---|---|---|
| 地址检测(校验和闸门) | `clipper/detect/` | Base58Check / BIP-173/350 / EIP-55,与真实木马同源的识别能力 |
| 零宽字符清洗 | `clipper/normalize.py` | 真实样本用隐形字符规避检测,这里演示如何剥掉 |
| 剪贴板读/写 | `clipper/platforms/` | Windows(Win32 API)/ macOS / Linux 三端 |
| **替换写回**(核心机制) | `clipper/safe.py` + `cli.py` | 复现"粘贴前改写地址"的完整链路——防护视角:替换为本机固化的安全地址变体 |
| 告警与审计 | `clipper/alert.py` + `history.py` | 控制台告警 + sqlite 历史(保留原始地址) |
| webhook 通知 | `clipper/notify.py` | 检出事件外推 |
| 端到端验证 | `scripts/` | 真机剪贴板读写验证脚本、8 场景演示 |

## 示例应对策略(随仓库提供)

1. **完全匹配替换**(默认):剪贴板整体恰好是一个合法地址才替换——保原地址头 4 尾 4、
   中间换成固定安全地址中段、等长;替换物的校验和不再通过,真转账会被钱包拒绝。
2. **替换后告警 + 历史审计**:控制台明示替换发生,sqlite 保留原始地址供事后核对。
3. **粘贴时校验**:`clipper paste` 代替 Ctrl+V,输出原文并对检出地址追加提示。
4. **webhook 外推**:检出事件推送到手机/服务端(见 `--webhook`)。
   注意:payload 含剪贴板**完整原文**,请只发往可信端点(建议 HTTPS)。
5. **威胁研究驱动的检测**(进行中):见下方威胁研究一节。

## 快速开始

```bash
uv sync                                  # 或先安装 uv:pip install uv
uv run clipper watch                     # 常驻监控:检出地址→告警→替换写回(默认完全匹配模式,其余见 --help)
uv run clipper address                   # 查看本机固定的安全地址
uv run pytest tests/ -v                  # 测试
uv run python scripts/demo.py            # 8 场景端到端演示
```

剪贴板后端依赖:Windows/macOS 内置;Linux 需 `xclip`(X11)或 `wl-clipboard`(Wayland)。

## 威胁研究

方法论:**先以攻击者视角构建完整攻击链,再切防守者视角做检测点映射与对抗方案**。
跟踪:[Issue #23](https://github.com/youayou-Lee/Clipper/issues/23)。产物:

- [`docs/research/attack-chain.md`](docs/research/attack-chain.md) — 攻击链全景(分发/免杀/加载/持久化/劫持/变现,全部厂商报告溯源)
- [`docs/research/defense-mapping.md`](docs/research/defense-mapping.md) — 逐环节检测点映射、对策分级与攻防不对称分析

## 工程规范

本项目走 Issue 驱动的 GitHub Flow(见 `docs/WORKFLOW.md`):先立 Issue(可测试验收标准)
→ feat 分支 → 测试绿才 commit → PR 四要素 → CI 绿 + 代码审核 → squash merge → CHANGELOG。
