# Clipper 攻击链研究

> 方法论(见 Issue #23):**先攻击、后防御**。本文档 Phase 1 以攻击者视角构建完整攻击链
> (分发 → 免杀 → 加载运行 → 持久化 → 劫持变现),Phase 2 的检测点映射见
> `defense-mapping.md`(由 Issue #26 产出,未完成)。
> 红线:产物为文档,不含可运行恶意代码,不针对真实目标;所有论断带出处,推断处标注〔推断〕。

## 0. 攻击链全景(骨架)

```
[分发] ──→ [落地/初始执行] ──→ [免杀] ──→ [加载] ──→ [持久化] ──→ [剪贴板劫持] ──→ [变现]
  │              │                │           │             │              │              │
 渠道×载体     用户自启          信任伪造    多阶段解密     自启动机制      监控+正则匹配    收款地址轮换
 (本文§1)     伪装正常软件      (§2 待写)  (§2 待写)     (§2 待写)     (§2 待写)      15k+ 地址池
```

攻击者成本结构〔推断,基于下列案例归纳〕:开发一次性投入(木马本体可复用),持续成本在
**分发与信任制造**——这正是 2024-2026 各campaign 的演进重心。

---

## 1. 分发阶段(攻击者视角)

攻击者的核心问题不是"写一个 clipper"(门槛极低,品类存在超过十年,源自银行木马的
剪贴板替换技术),而是"**怎么把一个会被查杀的 exe 送到不知情用户手里,并让他主动运行**"。
2024-2026 的公开案例显示:分发创新已经超过 payload 创新——攻击者"更像营销者而非黑客"。

### 1.1 渠道矩阵

| # | 渠道 | 载体形态 | 目标人群 | 真实案例(出处) |
|---|------|---------|---------|----------------|
| A | **高诱惑软件捆绑**(破解软件/外挂/激活工具) | YouTube 教程视频简介→假 captcha→安装包 | 破解软件/游戏玩家 | Diamotrix 经 YouTube 破解游戏安装包分发([ANY.RUN](https://medium.com/@anyrun/diamotrix-malware-overview-39fce1fc9675));Laplas Clipper MaaS 经破解软件与 loader 分发([Hunt.io](https://hunt.io/malware-families/laplas-clipper));Powercat 假游戏外挂投 Discord/Roblox/钱包窃取([ThreatLocker](https://www.threatlocker.com/blog/powercat-malware-campaign-fake-game-cheats-deliver-infostealer-targeting-discord-roblox-and-crypto-wallets)) |
| B | **搜索/广告投毒**(malvertising + TDS) | Google Ads→仿冒站→zip(lnk→PS 多阶段) | 按语言/地域定向的泛用户 | CryptoClippy:Google Ads 竞价"WhatsApp Web"关键词,TDS 按 VPN/UA/Accept-Language/地理位置过滤真实受害者,未过滤者跳真站养信任([Unit 42](https://unit42.paloaltonetworks.com/crypto-clipper-targets-portuguese-speakers/)) |
| C | **声誉经济**(fake reputation) | GitHub/SourceForge 仓库+互刷 star/下载、AI 配音假教程视频、VirusTotal 好评投票、付费新闻位 | 加密玩家/赌徒(找"外挂"的人) | Check Point"Ghost Network":Rust clipper 伪装 Solana sniper bot/Aviator Predictor,6 个互推 GitHub 账号、SourceForge 下载量刷到 44,485(37,460 来自不存在的 Android 版本的设备农场)、VT 好评投票污染信誉数据([Check Point](https://blog.checkpoint.com/research/from-stars-to-upvotes-the-fake-reputation-economy-behind-a-crypto-clipboard-hijackers/),[Hacker News](https://thehackernews.com/2026/06/crypto-clipper-campaign-abuses-fake.html)) |
| D | **假官方客户端** | 仿冒 Tor Browser/WhatsApp Desktop 安装包(带密码 RAR 防扫描) | 特定刚需用户(Tor 被封锁地区/日常通讯) | 假 Tor Browser clipper:15,000+ 受害者、52 国、约 $40 万损失,密码保护 RAR 规避扫描,自启动+热门图标伪装([Kaspersky](https://www.kaspersky.com/about/press-releases/new-clipper-malware-steals-us400000-in-cryptocurrencies-via-fake-tor-browser));CryptoClippy 仿 WhatsApp Web(同 B) |
| E | **社交渠道**(Discord/Telegram/游戏社区) | 劫持过期邀请链接、假 beta 试玩、社区私信 | 玩家/社区成员(高信任环境) | Check Point:过期 Discord 邀请链接被抢注重定向到多阶段投放([Check Point Research](https://research.checkpoint.com/2025/from-trust-to-threat-hijacked-discord-invites-used-for-multi-stage-malware-delivery/));Stealka 经游戏/盗版渠道传播并劫持 Discord/Telegram 账号二次扩散([Kaspersky](https://www.kaspersky.com/blog/windows-stealer-stealka/55058/)) |
| F | **移动介质蠕虫** | USB 上的 .lnk(藏原文件、同名快捷方式指向 payload) | 物理接触目标(离线场景/内网) | Microsoft 2026-06 报告:clipper 藏文档同名 LNK,插入 USB 即经计划任务蠕虫传播,C2 走 Tor([Microsoft](https://www.microsoft.com/en-us/security/blog/2026/06/17/crypto-clipper-uses-tor-worm-like-propagation-for-persistence-control/)) |
| G | **浏览器扩展** | 商店/侧载扩展,页面内替换钱包地址 | DeFi/交易所网页操作者 | McAfee"Silent Swap"扩展 ([McAfee](https://www.mcafee.com/blogs/other-blogs/mcafee-labs/crypto-clipper-wallet-swapping-browser-extension-malware/)) |

### 1.2 攻击者的取舍分析〔推断,基于上述报告事实〕

| 维度 | A 捆绑 | B 广告投毒 | C 声誉经济 | D 假客户端 | E 社交 | F USB | G 扩展 |
|---|---|---|---|---|---|---|---|
| 到达规模 | 大 | 大(需买量成本) | 中 | 中(需刚需) | 小(信任高) | 极小 | 大(若进商店) |
| 单位成本 | 低 | 高(广告费) | 中(养号/刷量) | 中 | 极低 | 低 | 中 |
| 暴露/被封风险 | 中 | 高(广告平台封号) | 中(平台风控升级) | 中 | 低 | 低(无平台) | 高(商店审核) |
| 目标精度 | 中(圈定人群) | 可定向(如 TDS 语言过滤) | 高(找捷径人群) | 高(刚需人群) | 高(熟人信任) | 精确(物理接近) | 高(钱包用户) |

- **趋势**:头部 campaign 正从"单渠道散投"转向"**多渠道声誉网络**"(C 案例:GitHub+SourceForge+
  YouTube+VT+新闻位协同),攻击者复用正规品牌增长的打法,把受害者 checking 信誉要看的每一个
  平台都布置了假信号。
- **信任制造 > 规避检测**:C 案例里样本本身 VT 检出率低,攻击者还专门投票刷好评——
  不仅绕过检测,还污染检测依赖的输入。B 案例的 TDS 把"非受害者"引去真站,让安全 researcher
  和沙箱都只看到正常页面。
- **平台套利**:Windows 收紧后转 macOS(要求用户手动绕过 Gatekeeper——Check Point 原话:
  "That step is the attack")或浏览器扩展/移动端,防御覆盖面差异即攻击面。

### 1.3 与下一环节的交接形态(→ 免杀/加载,#25 续写)

各渠道最终交付给"加载环节"的形态收敛为:
- **带社会工程外壳的归档**:密码保护 RAR/zip(躲静态扫描,D 案例)、需要用户手动绕过 OS 保护(macOS Gatekeeper,C 案例)
- **快捷方式/文档伪装**:.lnk(带混淆参数的命令行,F/B 案例)
- **脚本 dropper**:PowerShell/bat(多阶段解密,B 案例的 Ricoly 链)
- **原生安装包**:NSIS/Inno 捆绑(A 案例)、签名或盗签二进制〔待 #25 归纳〕
- **浏览器扩展包**(G 案例)

---

## 2. 免杀与加载运行(待写,Issue #25)

## 3. 持久化与生命周期(待写,Issue #25)

## 4. 剪贴板劫持与变现(待写,Issue #25)

## 5. 防守者视角:检测点映射与对抗(待写,Issue #26 → defense-mapping.md)

---

## 参考来源

- Unit 42 (Palo Alto Networks), CryptoClippy: https://unit42.paloaltonetworks.com/crypto-clipper-targets-portuguese-speakers/
- Microsoft Threat Intelligence, Crypto clipper with Tor & worm-like propagation (2026-06-17): https://www.microsoft.com/en-us/security/blog/2026/06/17/crypto-clipper-uses-tor-worm-like-propagation-for-persistence-control/
- Check Point Research, The Fake Reputation Economy Behind a Crypto Clipboard Hijacker: https://blog.checkpoint.com/research/from-stars-to-upvotes-the-fake-reputation-economy-behind-a-crypto-clipboard-hijackers/
- The Hacker News 对该报告的报道(2026-06): https://thehackernews.com/2026/06/crypto-clipper-campaign-abuses-fake.html
- Kaspersky, Fake Tor Browser clipper($400k/15k 受害者): https://www.kaspersky.com/about/press-releases/new-clipper-malware-steals-us400000-in-cryptocurrencies-via-fake-tor-browser
- McAfee Labs, Silent Swap browser extension clipper: https://www.mcafee.com/blogs/other-blogs/mcafee-labs/crypto-clipper-wallet-swapping-browser-extension-malware/
- Hunt.io, Laplas Clipper (MaaS): https://hunt.io/malware-families/laplas-clipper
- ANY.RUN, Diamotrix overview: https://medium.com/@anyrun/diamotrix-malware-overview-39fce1fc9675
- ThreatLocker, Powercat fake game cheats: https://www.threatlocker.com/blog/powercat-malware-campaign-fake-game-cheats-deliver-infostealer-targeting-discord-roblox-and-crypto-wallets
- Check Point Research, Hijacked Discord invites (2025): https://research.checkpoint.com/2025/from-trust-to-threat-hijacked-discord-invites-used-for-multi-stage-malware-delivery/
- Kaspersky, Stealka stealer: https://www.kaspersky.com/blog/windows-stealer-stealka/55058/
