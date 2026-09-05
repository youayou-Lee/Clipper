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
 (本文§1)     伪装正常软件      (§2 待写)  (§2 待写)     (§2 待写)     (§2 待写)      内嵌 15,500+ 收款地址池(Check Point 案例)
```

攻击者成本结构〔推断,基于下列案例归纳〕:开发一次性投入(木马本体可复用),持续成本在
**分发与信任制造**——这正是 2023-2026 各 campaign 的演进重心。

---

## 1. 分发阶段(攻击者视角)

攻击者的核心问题不是"写一个 clipper"(门槛极低,品类存在超过十年,源自银行木马的
剪贴板替换技术),而是"**怎么把一个会被查杀的 exe 送到不知情用户手里,并让他主动运行**"。
2023-2026 的公开案例显示:分发创新已经超过 payload 创新——攻击者"更像营销者而非黑客"。

### 1.1 渠道矩阵

| # | 渠道 | 载体形态 | 目标人群 | 真实案例(出处) |
|---|------|---------|---------|----------------|
| A | **高诱惑软件捆绑**(破解软件/外挂/激活工具) | YouTube 教程视频简介→假 captcha→安装包 | 破解软件/游戏玩家 | Diamotrix 经 YouTube 破解游戏安装包分发([ANY.RUN](https://medium.com/@anyrun/diamotrix-malware-overview-39fce1fc9675));Laplas Clipper MaaS 经破解软件与 loader 分发([Hunt.io](https://hunt.io/malware-families/laplas-clipper));Powercat 假游戏外挂投 Discord/Roblox/钱包窃取([ThreatLocker](https://www.threatlocker.com/blog/powercat-malware-campaign-fake-game-cheats-deliver-infostealer-targeting-discord-roblox-and-crypto-wallets)) |
| B | **搜索/广告投毒**(malvertising + TDS) | Google Ads→仿冒站→zip(lnk→PS 多阶段) | 按语言/地域定向的泛用户 | CryptoClippy:Google Ads 竞价"WhatsApp Web"关键词(并有 SEO 投毒配合),TDS 按 VPN/UA/Accept-Language/地理位置过滤真实受害者,未过滤者跳真站养信任([Unit 42](https://unit42.paloaltonetworks.com/crypto-clipper-targets-portuguese-speakers/)) |
| C | **声誉经济**(fake reputation) | GitHub/SourceForge 仓库+互刷 star/下载、AI 配音假教程视频、VirusTotal 好评投票、付费新闻位 | 加密玩家/赌徒(找"外挂"的人) | Check Point"Ghost Network":Rust clipper 伪装 Solana sniper bot/Aviator Predictor,6 个互推 GitHub 账号、SourceForge 下载量刷到 44,485(37,460 来自不存在的 Android 版本的设备农场)、VT 好评投票污染信誉数据([Check Point](https://blog.checkpoint.com/research/from-stars-to-upvotes-the-fake-reputation-economy-behind-a-crypto-clipboard-hijackers/),[Hacker News](https://thehackernews.com/2026/06/crypto-clipper-campaign-abuses-fake.html)) |
| D | **假官方客户端** | 仿冒 Tor Browser/WhatsApp Desktop 安装包(带密码 RAR 防扫描) | 特定刚需用户(Tor 被封锁地区/日常通讯) | 假 Tor Browser clipper:15,000+ 受害者、52 国、约 $40 万损失,密码保护 RAR 规避扫描,自启动+热门图标伪装([Kaspersky](https://www.kaspersky.com/about/press-releases/new-clipper-malware-steals-us400000-in-cryptocurrencies-via-fake-tor-browser));CryptoClippy 仿 WhatsApp Web(同 B) |
| E | **社交渠道**(Discord/Telegram/游戏社区) | 劫持过期邀请链接、假 beta 试玩、社区私信 | 玩家/社区成员(高信任环境) | Check Point:过期 Discord 邀请链接被抢注重定向到多阶段投放(载荷为 AsyncRAT/Skuld,**非 clipper**——但该分发链路对 clipper 同样可复用)([Check Point Research](https://research.checkpoint.com/2025/from-trust-to-threat-hijacked-discord-invites-used-for-multi-stage-malware-delivery/));Stealka 经游戏/盗版渠道传播并劫持 Discord/Telegram 账号二次扩散、兼窃加密货币([Kaspersky](https://www.kaspersky.com/blog/windows-stealer-stealka/55058/)) |
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
  YouTube+VT+新闻位协同),攻击者复用正规品牌增长的打法,把受害者核查信誉要看的每一个
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
- **原生安装包**:NSIS/Inno 捆绑(A 案例)、脚本解释器封装(AutoIt/AHK 打包成 exe,见 §2)、合法语言运行时封装(PyInstaller/PyArmor,F 案例)、Rust/Go 静态编译(C 案例)
- **浏览器扩展包**(G 案例)

---


## 2. 免杀(攻击者视角)

免杀要解决的问题:样本从落地到常驻的整条生命线上,每个环节都有"检测者可见残留"
(→ #26 的检测点埋点,在各小节或小节组末尾标注)。公开案例显示,clipper 的免杀重心不在单一
技术,而在**组合与顺序**。

### 2.1 规避特征归纳(检测者可见残留加粗)

| # | 特征 | 公开案例证据 | 检测者可见残留 |
|---|------|-------------|---------------|
| 1 | **归档加密**:带密码 RAR/zip,杀软无法静态解包 | 假 Tor Browser 用密码保护 RAR,"明确为阻止安全方案检测"([Kaspersky](https://www.kaspersky.com/about/press-releases/new-clipper-malware-steals-us400000-in-cryptocurrencies-via-fake-tor-browser)) | **用户被要求输入密码的行为本身**(社会工程痕迹);解压后的落地文件 |
| 2 | **环境密钥化**(environment keying,ATT&CK T1480/001):解密密钥部分派生自本机特征(如 CPU ID),样本离开目标机即成死料 | CryptoClippy 的 Ricoly.ps1:XOR 密钥一半硬编码、一半取自处理器 ID([Unit 42](https://unit42.paloaltonetworks.com/crypto-clipper-targets-portuguese-speakers/));ATT&CK 收录为 Execution Guardrails([MITRE](https://attack.mitre.org/techniques/T1480/001/)) | 沙箱/分析机中"解密失败不执行"的**哑弹现象**;解密例程本身在内存中可见 |
| 3 | **多阶段分层解密**:LNK→PS1→加密 blob→PE,每层不同加密(XOR/RC4) | CryptoClippy:LNK 命令行用 ^/!!/:~ 填充混淆;ps/sc/pf 三个加密 blob;RC4 双密钥([Unit 42](https://unit42.paloaltonetworks.com/crypto-clipper-targets-portuguese-speakers/)) | PowerShell 父子进程链、**异常长的 LNK 命令行**、ScriptBlock 日志(若开启) |
| 4 | **合法解释器/运行时掩护**(LOTBins 邻域):AutoIt/AHK 打包 exe、PyInstaller+PyArmor、WScript/ActiveX | Microsoft 案例:Python 安装器 PyInstaller+PyArmor 打包,双层混淆 JS 经 WScript/ActiveXObject 执行([Microsoft](https://www.microsoft.com/en-us/security/blog/2026/06/17/crypto-clipper-uses-tor-worm-like-propagation-for-persistence-control/));AHK/AutoIt 被广泛用作 loader/打包器,MITRE 收录 T1059.010([securityscientist](https://www.securityscientist.net/blog/12-questions-and-answers-about-autohotkey-autoit-t1059-010/),[Broadcom](https://www.broadcom.com/20250305-protection-highlight-autoit-a-double-edged-sword-how-malware-exploits-automation-for-cyber-attacks)) | **合法解释器进程承载恶意脚本**的组合信号(AutoIt3.exe + 网络行为);打包器特征区段 |
| 5 | **直调系统调用,绕过用户态 hook**:syscall stub(SysWhispers2 风格)+ 反射式内存加载(D/Invoke/.NET delegate) | CryptoClippy:ps 模块做 .NET delegate 反射 PE 加载(VirtualAlloc/CreateThread),sc 模块走 SysWhispers2 风格 syscall,最终注入 svchost.exe([Unit 42](https://unit42.paloaltonetworks.com/crypto-clipper-targets-portuguese-speakers/)) | EDR 内核态仍可见的注入行为(跨进程写入+远程线程);用户态 hook 失效但 ETW/内核遥测不失效 |
| 6 | **端点防护削弱**:向 Defender 添加排除目录/进程 | Microsoft 案例:为 staging 目录和二进制添加 Defender 排除项([Microsoft](https://www.microsoft.com/en-us/security/blog/2026/06/17/crypto-clipper-uses-tor-worm-like-propagation-for-persistence-control/));排除项持久化机制([cloudbrothers](https://cloudbrothers.info/en/create-persistent-defender-av-exclusions-circumvent-defender-endpoint-detection/)) | **注册表 Exclusions 键的变更事件**(高价值告警,正常软件极少写);Defender 日志 |
| 7 | **反分析门**:检测分析环境即退出 | Microsoft 案例:WMI 查询 Win32_Process,发现任务管理器在运行即退出(伪装成"无窗口运行"的正常行为)([Microsoft](https://www.microsoft.com/en-us/security/blog/2026/06/17/crypto-clipper-uses-tor-worm-like-propagation-for-persistence-control/));沙箱/分析上下文识别归纳([Cyfirma](https://www.cyfirma.com/outofband/malware-detection-evasion-techniques/)) | WMI 查询模式;哑弹样本的可疑"什么都不做" |
| 8 | **信誉污染**:不绕检测,而是污染检测依赖的输入(VT 好评投票) | Check Point:攻击者账号在 VirusTotal 给样本投良性票+评论"looks clean"([Check Point](https://blog.checkpoint.com/research/from-stars-to-upvotes-the-fake-reputation-economy-behind-a-crypto-clipboard-hijackers/)) | **信誉系统的输入失真**(防御方难以直接检测,需交叉验证多个信誉源) |
| 9 | **Tor 隐匿 C2**:改名 tor 二进制,SOCKS5 本地代理回连 .onion | Microsoft 案例:ugate.exe(改名 Tor)→ localhost:9050 → curl POST 到 .onion 端点([Microsoft](https://www.microsoft.com/en-us/security/blog/2026/06/17/crypto-clipper-uses-tor-worm-like-propagation-for-persistence-control/)) | **本机出现 Tor 进程/SOCKS5 流量**(普通用户装 Tor 本身就罕见,强信号) |

### 2.2 攻击者的取舍〔推断,基于上述证据〕

- **脚本层 vs 原生层**:脚本(AHK/PS/JS)开发快、免杀靠"合法解释器"掩护,但留下进程链痕迹;
  原生(Rust/C 静态编译)更难分析但要自己解决 API 调用隐蔽性(SysWhispers)。头部案例两条路都走:
  脚本做 loader,原生做 payload。
- **"让样本变哑"优于"让样本变隐形"**:环境密钥化+TDS 过滤的思路是**不在分析者面前执行**,
  而不是骗过执行监控——这让传统动态沙箱系统性失效,也解释了为什么厂商只能靠"受害者侧遥测"回溯。
- **免杀的上游其实是分发**:密码 RAR、Gatekeeper 人工绕过、TDS 过滤,本质都是**把杀软的
  检查点转移给人类用户**——用户主动输入密码/点"仍要打开",检测链在人的环节断裂。

## 3. 加载运行与持久化(攻击者视角)

### 3.1 加载链(从落地到 payload 执行)

公开案例的加载链收敛为一个模式:**用户自启 → 小脚本解密 → 内存加载原生 payload**。

- CryptoClippy 全链([Unit 42](https://unit42.paloaltonetworks.com/crypto-clipper-targets-portuguese-speakers/)):
  `WhatsApp.zip → .lnk(混淆命令行)→ Ricoly.bat/ps1 → XOR 解密 ps → .NET 反射 PE loader(D/Invoke)→ 解密 sc → SysWhispers2 syscall 注入 svchost.exe`
- Microsoft 案例:`文档同名 .lnk → WScript + ActiveXObject 执行双层混淆 JS → PyInstaller/PyArmor 安装器 → worm 二进制`([Microsoft](https://www.microsoft.com/en-us/security/blog/2026/06/17/crypto-clipper-uses-tor-worm-like-propagation-for-persistence-control/))
- 常见替代形态:AutoIt/AHK 封装 exe 直接承载 dropper 逻辑([Broadcom](https://www.broadcom.com/20250305-protection-highlight-autoit-a-double-edged-sword-how-malware-exploits-automation-for-cyber-attacks));浏览器扩展无传统加载链,商店审核过审即"加载"完成([McAfee](https://www.mcafee.com/blogs/other-blogs/mcafee-labs/crypto-clipper-wallet-swapping-browser-extension-malware/))

**检测者可见残留**:进程链形态(lnk→wscript/powershell→异常子进程)、内存中的解密例程、
注入行为(即使 syscall 直调,内核遥测可见跨进程写入)。

### 3.2 持久化方式归纳

| # | 方式 | 案例 | 检测者可见残留 |
|---|------|------|---------------|
| 1 | 启动文件夹 .lnk | CryptoClippy:Startup 目录 Ricoly.lnk → bat → ps1(Unit 42) | **启动目录新文件**(常规监控点) |
| 2 | 注册表 autorun | 假 Tor Browser clipper:自启动注册+热门应用图标伪装(uTorrent)(Kaspersky) | Run 键变更事件;图标与二进制不匹配 |
| 3 | 计划任务 | Microsoft 案例:两个无限期计划任务(一个 USB 传播、一个跑 stealer)(Microsoft) | 计划任务注册事件;非标准路径的任务动作 |
| 4 | 自愈式持久化 | Check Point 案例:macOS Rust clipper 自愈设计,"手动删除后恢复"(Check Point) | 需要多监控点(单点删除无效);文件完整性监控 |
| 5 | 浏览器扩展 | Silent Swap:扩展商店分发,随浏览器常驻(McAfee) | 扩展权限申请(clipboardWrite/读取);扩展更新 |

### 3.3 生命周期

Microsoft 案例给出了最完整的生命周期画像:常驻轮询(剪贴板每 ~500ms)+ Tor C2 按需指令
(`EVAL` 任意 JScript 执行,stealer 随时可变身后门)+ USB 蠕虫横向扩散。被动等待是
clipper 的本性——**可以多年无网络活动,只在用户复制钱包地址的那一刻行动**
([Kaspersky](https://www.kaspersky.com/about/press-releases/new-clipper-malware-steals-us400000-in-cryptocurrencies-via-fake-tor-browser))。

## 4. 剪贴板劫持与变现(攻击者视角)

### 4.1 劫持实现点(三平台)

| 平台 | 实现点 | 案例/出处 |
|------|--------|----------|
| Windows | 轮询 `GetClipboardData`(数百 ms 间隔);或 `SetWinEventHook`(EVENT_OBJECT_FOCUS/VALUECHANGE)事件驱动;写入用 `SetClipboardData` | 轮询式:Microsoft 案例 500ms;事件式:CryptoClippy 的 WinEventHook + 隐藏窗口 WndProc(Unit 42) |
| macOS | NSPasteboard 轮询;Gatekeeper 人工绕过后落地,自愈持久化 | Check Point 案例(Check Point) |
| Android | 剪贴板监听(系统服务/API),伪装正常 App | Android clipper 影响([eInfochips](https://www.einfochips.com/blog/clipper-malware-what-is-it-and-how-does-it-impact-android-users/)) |

### 4.2 地址识别与替换策略(攻击者的工程细节)

- 识别:正则式前缀/长度匹配——BTC legacy(`1…`)、P2SH(`3…`)、Bech32(`bc1q…`)、
  taproot(`bc1p…`)、ETH(`0x…`+40 hex)、Tron(`T`+34)、Monero(`4/8`+95)、
  以及 BIP39 助记词(12/24 词)与 WIF/私钥(Microsoft 案例,顺带窃取)
- 替换:**按地址类型与长度匹配替换**,保留首尾字符模式(与用户视觉预期一致)——
  这正是本仓库 `safe.splice` 复现的行为(攻击者用它冒充,本仓库用它防御)
- 地址池:Check Point 案例内嵌 15,500+ 收款地址,轮换使用分摊被标记风险

### 4.3 变现链路

被动变现:受害者把转给攻击者地址的交易直接上链,资金不可逆;攻击者经钱包集群归集、
跨链/混币离场(变现链路细节超出本文范围,Merkle Science 有综述
[clipper 对加密交易的影响](https://www.merklescience.com/blog/how-clipper-malware-poses-a-threat-to-crypto-transactions))。
主动变现补充:Microsoft 案例顺带窃取助记词/私钥 + 截屏,直接掏空钱包而非等待换地址。

**检测者可见残留汇总(→ #26)**:剪贴板高频轮询行为、进程持有剪贴板句柄频率、
地址池复用(链上分析可聚类)、替换地址的首尾模式。


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
