# Quishing 扫码钓鱼与 WalletConnect 恶意配对调研:机制、案例与案例四复现方向

> 状态:调研(对应 [Issue #85](https://github.com/youayou-Lee/TrapLab/issues/85))。
> 定位:评估"案例四:扫码钓鱼 + 恶意配对"的立项依据。
> **免责声明**:本文仅基于公开威胁情报与公开协议文档做防御性分析,不含任何可武器化的
> 实现细节;任何实验性复现仅限本机与自有测试环境(Anvil 模拟链 + 公开测试私钥),
> 不接触官方 Relay 上的真实会话,不接触任何真实钱包/真实资产。

## 1. 是什么,为什么值得单独立案

**Quishing**(QR + phishing):用二维码承载恶意链接/URI 的钓鱼。二维码把真实目的地址
藏进了图像,人眼无法像核对短信链接那样检查,线下传单、停车场假罚单、邮件 PDF、
群聊图片都是载体。

**WalletConnect 恶意配对**:WalletConnect 是"手机钱包 ↔ 桌面/网页 dApp"的标准连接
协议。它的配对 URI 本身不含任何秘密、只代表"建立一个加密会话的邀请",于是产生一个
反直觉的社会工程事实——

> 受害者以为"扫一下 = 我主动连接某个 dApp,主动权在我",
> 实际是"我的钱包加入了**攻击者**建立的会话,攻击者从此获得持续向这个钱包
> 发起签名请求的合法通道"。

与现有三条案例线的关系:

| 案例线 | 偷什么 | 入口 |
|---|---|---|
| 案例一 clipper | 这一次转账(地址替换) | PC 剪贴板 |
| 案例二 phishlab | 被授权的代币(approve/permit) | 点链接进假 dApp 前端 |
| 案例三 mnestic | 整个钱包(助记词) | 恶意 App 相册 OCR 扫描 |
| **案例四(本调研)** | **被授权的代币(同案例二)** | **扫一个二维码** |

注意案例四的"收尾"与案例二完全同构(setApprovalForAll / permit / drainer 扫款),
**新意全在入口**:从"点链接"换成"扫码 + 恶意配对"。这意味着 phishlab 的授权钓鱼
后端可以大量复用,案例四是一个增量很小、但补齐攻击面拼图重要一格的案例。

## 2. WalletConnect v2 配对协议拆解

以下为公开协议行为([WalletConnect 官方文档](https://docs.walletconnect.com)、
[ND Labs 安全指南](https://ndlabs.dev/is-walletconnect-safe))。

### 2.1 正常流程:三个角色 + 一个中继

WalletConnect 解决"手机钱包 ↔ 网页 dApp"的通信:中间架一个**中继服务器(Relay)**
当"邮局",所有消息经它转发但内容端到端加密,Relay 看不懂也改不了。

```
dApp(发起方)                          钱包(响应方)
   │ 1. 生成配对 URI                      │
   │    wc:<topic>@2?relay-protocol=irn   │
   │        &symKey=<对称密钥>            │
   │ 2. URI 画成二维码                    │
   │        └──────受害者扫码──────┘      │
   │ 3. 双方经 Relay 交换握手消息(对称密钥 │
   │    已随 URI 预共享,握手由之派生出    │
   │    会话 topic 与密钥)                │
   │ 4. 钱包按 namespaces 同意会话        │
   │    (如允许哪些链/哪些方法)           │
   │ 5. 会话建立:dApp 可持续发请求,       │
   │    每条请求钱包弹窗让用户确认         │
```

关键点:

- **`wc:` URI 的三个成分**:`topic`(配对的门牌号)、`symKey`(该配对的对称密钥)、
  relay 参数。它**不含私钥、不代表任何授权**,只是一张"会诊单"。
- **扫码 = 钱包主动加入别人建的配对**。谁生成 URI/二维码,谁就是 dApp 端;
  谁扫码,谁就是钱包端。协议对"dApp 是否可信"零校验。
- **会话建立后是持久的**:dApp 可反复发签名请求,直到用户在钱包里手动断开会话。
  这就是"连一次,钓 N 次"的通道。

### 2.2 恶意配对:同一协议,方向反转

攻击者不需要攻破任何加密——他直接**当 dApp 端**:

```
攻击者                                      受害者
  │ 1. 用官方 SDK 写一个假 dApp 客户端        │
  │    (几十行代码),生成配对 URI            │
  │ 2. 套上诱惑外壳:"扫二维码领空投"          │
  │    "NFT 白名单铸造""钱包安全验证"         │
  │ 3. ──────────二维码发出去──────────▶      │ 扫码,钱包弹"连接?"
  │    元数据(dApp 名/图标)是自报的,        │ 显示 "Uniswap" → 确认
  │    可写成任何知名应用                     │
  │ 4. ◀── 经 Relay 发签名请求 ─────────      │
  │    setApprovalForAll / permit /          │ 弹窗显示一串 hex 或
  │    EIP-712 授权签名                      │ 合约地址 → 手一抖确认
  │ 5. 授权生效 → drainer 合约扫款,          │ (此后不再需要任何签名)
  │    DaaS 套件连这步都是打包好的            │
```

三个加重因素:

1. **移动端钱包内置扫码器往往不展示完整 URI**,只展示自报的 dApp 名称/图标 +
   一个"连接"按钮,用户在钱包 App 内信任度最高、信息最少。
2. **签名弹窗的内容与操作初衷天然脱节**:用户扫码是为了"领空投",弹窗让他签的
   是一串看不出含义的 hex,行为与预期断裂正是社工成功率最高的时刻。
3. **硬件钱包也防不住**:签名的是"真"交易,私钥从未离开钱包——这不是钱包被黑,
   而是用户被诱导交出授权。

### 2.3 中继(Relay)在攻击中的角色

Relay 完全合规且不知情:它只是转发端到端加密消息。攻击者使用的是官方基础设施,
**协议层抓不到任何异常**。因此防御必须落在钱包端展示、签名内容审查与用户教育上,
而不是"封 Relay"之类的协议层幻想。

## 3. 真实案例

### 3.1 加密会议线下二维码空投传单(模式性案例)

线下传单/贴纸印二维码,声称"独家加密空投/免费钱包",扫码进入连接钱包的钓鱼流程,
确认授权即被 drainer 清空。此类投放在行业会议(参会者"人人有钱包、人人想薅羊毛")
与停车场(假缴费二维码)集中出现,是安全厂商综述里反复描述的经典场景。
**说明**:网传"2025 Miami 大会空投传单"未见单一权威原始报道,此处按
Group-IB / Check Point 综述中记载的模式性案例收录,不作为独立事件引用。
来源:[Group-IB 综述 §3.4](https://www.group-ib.com/resources/knowledge-hub/crypto-wallet-drainers/)、
[Check Point §3.3](https://research.checkpoint.com/2024/wallet-scam-a-case-study-in-crypto-drainer-tactics/)。

### 3.2 "WalletConnect & Web3Inbox Airdrop" drainer(2024,PCrisk)

直接冒用 WalletConnect 官方品牌,假借"Web3Inbox 空投"诱导用户连接钱包并签署
恶意交易,本质是 crypto drainer。意义:连**协议品牌本身**都被拿来做信任背书。
来源:[PCrisk 判定页](https://www.pcrisk.com/removal-guides/28877-walletconnect-and-web3inbox-airdrop-scam)。

### 3.3 Check Point:drainer 战术拆解(2024)

Check Point Research 对一起 wallet drainer 的完整解剖:假冒 Web3 连接工具获取
信任 → 诱导连接 → 恶意签名 → 合约扫款,并指出 drainer 已形成"变现即服务"的
成熟分工。来源:[CPR 报告](https://research.checkpoint.com/2024/wallet-scam-a-case-study-in-crypto-drainer-tactics/)。

### 3.4 Drainer-as-a-Service(Group-IB 综述)

Group-IB 归纳的 DaaS 生态:现成钓鱼套件自带逼真假 dApp 站点、钱包连接流程
(含 WalletConnect 扫码配对)、多链支持与抽成分账。**攻击门槛被压到"买套件 +
想诱饵话术"**,这正是"攻击过程极简"的产业背景。
来源:[Group-IB 知识库](https://www.group-ib.com/resources/knowledge-hub/crypto-wallet-drainers/)。

### 3.5 WalletConnect 官方仓库的滥用报告(GitHub Issue #5400)

社区直报:假 dApp 与受害者钱包配对后请求恶意签名/交易。官方立场是协议本身安全
(端到端加密、无私钥暴露),损失源于钓鱼、恶意授权与**假会话**。
来源:[walletconnect-monorepo #5400](https://github.com/WalletConnect/walletconnect-monorepo/issues/5400)、
[ND Labs: Is WalletConnect Safe?](https://ndlabs.dev/is-walletconnect-safe)。

## 4. 本机复现可行性(案例四的实现路径评估)

目标:不依赖官方 Relay、不碰真实资产,在本机走通"生成恶意配对二维码 → burner
钱包扫码入会 → 恶意授权签名 → drainer 扫款"全链路。

### 4.1 复用点(与 phishlab 对照)

| 案例四需要 | phishlab 已有 | 复用方式 |
|---|---|---|
| 恶意授权签名收尾(setApprovalForAll/permit) | `phishlab/phish_server.py` 假前端已产出两类授权;`drain.py` 两条收割路径(approve→transferFrom / permit→上链→transferFrom) | **直接复用收割端**,案例四只换"请求从哪来" |
| EVM 测试环境 | `phishlab/contracts/`(Foundry + PhishingToken)+ Anvil 惯例 | 原样复用 |
| 目标代币配置 | `phishlab/targets/` 档案机制 | 原样复用 |
| 会话层 | —— | **新增**:本地模拟 WalletConnect 配对/会话(见 4.2) |
| 二维码入口 | —— | **新增**:配对 URI → 二维码渲染(终端/网页) |

### 4.2 会话层的两条候选路径

- **路径 A(推荐,工作量小)**:**协议模拟**。不实现完整 WalletConnect 握手,
  本机起一个"会话代理"服务,行为上等价于"配对成功后的 dApp 端":生成
  `wc:` 格式的 URI 画成二维码;burner 钱包侧不做真扫码,由一个**模拟钱包客户端**
  (本地 Python 进程)解析二维码、建立会话、接收并"确认"签名请求。真实攻击中
  钱包弹窗给用户看的那一步,在这里变成模拟钱包打印请求内容 + 人工确认,
  教学/复现价值等价,且完全离线。
- **路径 B(更真实,成本高)**:自建兼容 Relay(开源实现/本地转发) + 真手机钱包
  扫码。能真实验证"钱包 App 元数据展示"这一防御盲区,但依赖外部钱包 App 的
  行为,不可测试性差,且与"仅自有测试环境"边界要反复核对。
- **建议**:案例四主体走路径 A;路径 B 作为可选附录做一次人工验证,只记录观察
  (如某钱包扫码后展示/不展示 URI),不进自动化测试。

### 4.3 端到端验收链(草案)

1. 攻击者端生成配对二维码(带自报元数据 "Uniswap")。
2. 模拟钱包扫码 → 打印"连接请求:Uniswap,允许 eth-mainnet × [personal_sign,
   eth_sendTransaction]" → 确认,会话建立。
3. 攻击者经会话发 `permit` 授权请求(EIP-712 报文与案例二同构)→ 模拟钱包展示
   spender/deadline → 确认。
4. `drain.py` permit 路径收割 → 断言 burner 余额归零。
5. 防御模块(见 §5)介入后,同一链路在步骤 2/3 被告警/拒绝。

## 5. 防御视角

按攻击链逐环节的可落地检测/防御点:

| # | 环节 | 防御点 | 可测试性(实验室) |
|---|---|---|---|
| 1 | 扫码入会 | 扫码前 URI 预览;钱包对 `wc:` URI 展示完整 topic/来源 | 高:规则引擎对 URI 打分(非官方 relay 参数、自报元数据与已知品牌相似度) |
| 2 | 会话建立 | "已连接 dApp"会话管理:定期清理、断开即失效 | 高:会话表状态机,断开后请求必被拒 |
| 3 | 签名请求 | **三大死亡信号**:`setApprovalForAll`、陌生 spender、`permit`(EIP-712 含 spender+deadline 而无金额上限) | 高:签名请求分类器,规则可单测 |
| 4 | 事后 | Revoke.cash / Etherscan token approval checker 定期自查 | 中:链上 allowance 查询需新增代码,但可参考 drain.py 已有的链上交互模式 |
| 5 | 教育 | "扫码 = 加入别人的会话"的方向性认知 | 低 |

其中 **#3 签名请求分类器**最适合作为案例四的防御落点:与案例二已有的 permit
nonce/过期校验工作一脉相承,规则可写成纯函数单测,且天然产出"告警 vs 放行"的
演示对比——同一攻击链,装上守卫后在步骤 3 被拦下,教学闭环完整。

## 6. 结论与立项建议

- **建议立项案例四**,形态:模块 `quishlab/`(或并入 `phishlab/` 作子案例,视
  复用程度在立项 Issue 讨论;初步判断独立模块 + 依赖 phishlab 合约/drain 更清晰)。
- 复现走 §4.2 路径 A(协议模拟,完全离线),真实手机扫码只做人工附录验证。
- 防御落点选 §5 #3(签名请求分类器),与案例二形成"同一收割、两种入口、
  一个守卫"的叙事。
- 边界重申:仅 Anvil 模拟链 + 公开测试私钥;不实现真实 Relay 中间人,不优化
  诱饵话术的真实投放效果。

## 参考来源

- [ND Labs: Is WalletConnect Safe? v2 Security Guide](https://ndlabs.dev/is-walletconnect-safe)
- [Check Point Research: Wallet Scam — A Case Study in Crypto Drainer Tactics](https://research.checkpoint.com/2024/wallet-scam-a-case-study-in-crypto-drainer-tactics/)
- [Group-IB: Crypto Wallet Drainers](https://www.group-ib.com/resources/knowledge-hub/crypto-wallet-drainers/)
- [PCrisk: WalletConnect & Web3Inbox Airdrop Scam](https://www.pcrisk.com/removal-guides/28877-walletconnect-and-web3inbox-airdrop-scam)
- [walletconnect-monorepo Issue #5400: phishing abuse report](https://github.com/WalletConnect/walletconnect-monorepo/issues/5400)
- [Tangem: Scam Detection for WalletConnect dApps](https://tangem.com/en/blog/post/scam-detection-dapps/)
- [WalletConnect 官方文档](https://docs.walletconnect.com)
