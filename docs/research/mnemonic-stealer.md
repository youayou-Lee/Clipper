# 助记词木马调研:机制、案例与各平台实现难点

> 状态:调研(对应 [Issue #80](https://github.com/youayou-Lee/TrapLab/issues/80))。
> 定位:评估"案例三:助记词泄露防护"的立项依据。
> **免责声明**:本文仅基于公开威胁情报做防御性分析,不含任何可武器化的实现细节;
> 任何实验性复现仅限本机与自有测试环境。

## 1. 是什么,为什么危害量级最大

助记词(BIP-39 恢复短语,12/24 个单词)是确定性钱包的**根凭据**:拿到它即可在任何设备
导入钱包,控制全部派生地址的历史资产与未来充值——无需接触受害者设备上的私钥文件、
无需签名交互、交易不可逆。相比之下:

- **剪贴板木马(案例一复现的 clipper)**偷的是"这一次转账",替换一次地址得一次资金;
- **Approve/Permit 钓鱼(案例二)**偷的是"被授权的那部分代币",可被 revoke;
- **助记词木马**偷的是"整个钱包",一击致命且无法撤销。

因此助记词木马与 clipper 常打包出现:同一恶意程序既做地址替换(剪肉)也做助记词窃取
(断根),如 Efimer 与 Microsoft 报告的 Crypto Clipper。

## 2. 四大窃取手段

| # | 手段 | 原理 | 关键依赖 |
|---|------|------|----------|
| 1 | **相册 OCR 扫描** | 大量用户把助记词截图存相册。木马对图片做本地 OCR(或整相册回传服务端识别),命中 BIP-39 词表特征后窃取 | 相册读取权限;本地 OCR 库(如 Google ML Kit)或服务端识别 |
| 2 | **输入/剪贴板嗅探** | 键盘记录捕获用户输入的单词序列,按 BIP-39 的 2048 词表匹配;或监控剪贴板中粘贴的助记词 | PC:全局钩子;Android:无障碍服务;iOS:基本不可行 |
| 3 | **钓鱼诱导输入** | 假"钱包验证/客服/空投"页面直接骗用户输入助记词。技术含量最低,占比最高 | 社工,无需漏洞 |
| 4 | **文件/内存/扩展窃取** | infostealer 扫描钱包数据库、keystore 文件、浏览器扩展(MetaMask 等)的本地存储 | 落盘执行权限;PC 为主 |

其中手段 1 是移动端主流(SparkCat/SparkKitty/SpyAgent 均为此路线),手段 2/4 是 PC 主流,
手段 3 跨全平台且始终有效。

## 3. 真实案例

### 3.1 SparkCat(2025.02,卡巴斯基)——首个上架 App Store 的 OCR 窃密木马

- **传播**:恶意框架/SDK 捆绑进看起来正经的应用(外卖、AI 聊天等),同时进入
  Google Play 与 App Store;2026.04 出现新变种再次过审上架(SC World)。
- **技术**:集成 **Google ML Kit OCR** 本地扫描相册,识别含助记词的截图后回传
  攻击者服务器(报告中的 C2 域如 `secure-dp[.]com`)。
- **意义**:证明"正经应用 + 合理权限(相册)+ 官方 OCR 库"即可通过两家商店审核,
  iOS 沙盒对**权限内**的行为无能为力。
- 来源:[Securelist: SparkCat crypto stealer in Google Play and App Store](https://securelist.com/sparkcat-stealer-in-app-store-and-google-play/115385/)
  (2024 年末发现,2025.02 发布);2026.04 有新变种再次过审上架两家商店的报道见
  [SC World](https://www.scworld.com)。

### 3.2 SparkKitty(2025.06,卡巴斯基)——SparkCat 的"整相册回传"进化版

- **传播**:木马化的约会/博彩/生活方式类应用,渠道含第三方网站、App Store、
  Google Play,iOS 侧还有企业分发/侧载载荷。
- **技术**:不再本地逐图 OCR,而是**整相册上传**,在服务端筛助记词/密码/证件照/
  二维码截图——本地行为更"安静",检测难度更高。
- **地域**:主要东南亚(新加坡、印尼等),跨平台。
- 来源:[Securelist 技术报告](https://securelist.com/sparkkitty-ios-android-malware/116793/)、
  [PolySwarm 分析](https://blog.polyswarm.io/sparkkitty-trojan-targets-mobile-users-with-cross-platform-espionage)。

### 3.3 Efimer(2024.10–2025.07,卡巴斯基)——PC 端"剪肉 + 断根"二合一

- **传播**:钓鱼邮件群发 + 被黑 WordPress 站/种子站投递,伪装成"法律文书"等诱饵文件;
  逾 5,000 名个人与企业用户中招。
- **技术**:本体为 ClipBanker 家族,clipper(替换剪贴板中的钱包地址)+ **持续检测剪贴板
  中的助记词,命中即存为 SEED 文件回传**;同时截取屏幕;C2 走 Tor(curl + socks5)。
  另有分支版本扫描浏览器扩展目录与钱包应用目录,直接回传钱包数据。
- 来源:[Securelist: Efimer](https://securelist.com/efimer-trojan/117148/)、
  [卡巴斯基新闻稿](https://www.kaspersky.com/about/press-releases/kaspersky-uncovers-efimer-trojan-targeting-organizations-through-phishing-emails)。

### 3.4 Crypto Clipper(2026.02–,Microsoft)——Tor C2 + USB 蠕虫式传播

- **传播**:含恶意 LNK 快捷方式的感染 U 盘,蠕虫式横向扩散;2026.02 起活跃。
- **技术**:剪贴板地址替换 + 钱包数据窃取 + 内置 **Tor 代理做 SOCKS C2** 隐藏基础设施,
  脚本化组件提供可远程执行的后门——持久化与控制力超出单纯"偷一票"。
- 来源:[Microsoft Security Blog](https://www.microsoft.com/en-us/security/blog/2026/06/17/crypto-clipper-uses-tor-worm-like-propagation-for-persistence-and-control/)(2026.06.17)。

### 3.5 补充参照

- **SpyAgent**(McAfee,2024.09):Android 木马用 OCR 筛设备上的截图,回传含恢复短语的
  图片内容——相册 OCR 路线的先例(早于 SparkCat 披露),经短信链接传播,主攻韩国市场。
- **ComboJack**(Unit 42,2018)/ **首个上架 Google Play 的 clipper**(ESET,2019):
  剪贴板替换路线的早期节点,与本仓库案例一直接相关。

## 4. 手段 × 平台实现难点对照

图例:✅ 相对容易实现 / ⚠️ 有明显障碍但可绕 / ❌ 平台层面基本封死

| 手段 | PC(Windows/macOS/Linux) | Android | iOS |
|------|--------------------------|---------|-----|
| **相册 OCR 扫描** | ⚠️ 桌面端少有"相册"概念,需扫描用户目录图片,噪声大 | ✅ `READ_MEDIA_IMAGES` 权限即可;ML Kit 本地 OCR;Android 13 起按媒体类型授权、14 支持"部分相册访问"反而降低用户警觉 | ✅ `PHPhotoLibrary` 授权后同路径可行;SparkCat/SparkKitty 实证可过审;`PHPicker` 无需完整授权是更隐蔽的口子 |
| **输入嗅探(键盘记录)** | ✅ Windows 全局钩子成熟;macOS 需辅助功能/输入监控授权;Linux X11 容易、Wayland 受限 | ⚠️ 无键盘钩子 API,需**无障碍服务**逐字读取屏幕——Google 对无障碍滥用审核趋严,且用户需在设置中显式授敏 | ❌ 沙盒内无任何全局输入监听途径;自定义键盘需用户主动切换且无网络权限,基本不可行 |
| **剪贴板监控** | ✅ Windows `AddClipboardFormatListener`、macOS `NSPasteboard` 轮询、Linux 均可行(案例一已复现) | ⚠️ Android 10 起**仅默认输入法或获得焦点**的 App 可读剪贴板,后台监听被封;绕法是申请无障碍服务或诱导前台 | ⚠️ 仅前台 App 可读;iOS 14 起读取必弹横幅提示;iOS 16 起需粘贴确认,后台监听不可行 |
| **文件/钱包数据窃取** | ✅ infostealer 成熟路线:扫描 AppData/浏览器扩展 Local Storage/keystore 文件 | ⚠️ 沙盒隔离各 App 数据,拿不到其他钱包 App 的私钥文件;能拿的只有共享存储里的截图/下载 | ❌ 沙盒完全隔离,跨 App 读数据不可行;iCloud 整盘备份类攻击属另一维度 |
| **钓鱼诱导输入** | ✅ 始终有效 | ✅ 始终有效(叠加无障碍覆盖窗更逼真) | ✅ 始终有效;WebView 钓鱼页是 iOS 上最现实的助记词窃取路径 |

**平台难点小结**:

- **PC**:技术上几乎无障碍(钩子、剪贴板、文件扫描全通),难点在**免杀与持久化**
  (杀软/EDR 对比、Tor C2 流量特征)——这正是 Crypto Clipper 用 Tor + USB 蠕虫解决的。
- **Android**:文件窃取被沙盒挡住,主流路线收敛为**相册 + OCR**(SparkCat 路线);
  键盘/剪贴板路线必须先过"无障碍服务"这道用户显式授权 + 商店审核的关卡。
- **iOS**:最封闭——无键盘记录、无后台剪贴板、无跨 App 读取;**唯一成规模的真实攻击面
  就是相册权限 + 社工钓鱼**。SparkCat 系列证明:只要攻击藏在"合理权限内的行为",
  App Store 审核拦不住;防御重心因此从"平台隔离"退到"用户行为"(不截图助记词)。

## 5. 防御视角与案例三复现方向建议

**可落地的检测/防御点**:

1. **助记词数字化检测(用户侧自检)**:扫描本机/相册中的图片,检出疑似 BIP-39
   助记词的截图并告警——把 SparkCat 的 OCR 能力反转成防御工具,直接消除手段 1 的目标面。
2. **剪贴板助记词识别告警(与案例一协同)**:`clipper` 的检出闸门已能识别地址;
   扩展为识别剪贴板中的 12/24 词 BIP-39 序列并告警"你正在复制/粘贴助记词,极可能是钓鱼",
   直接对冲手段 2/3 的最后一步(Efimer 正是从剪贴板偷助记词的)。
3. **粘贴地址核对(已有)**:案例一的等长替换 + 头尾提示已覆盖,属 clipper 对抗范畴。
4. **权限最小化教育**:不截图助记词、手写/刻钢板离线保存;审查 App 相册权限;
   iOS 上对"粘贴确认"弹窗保持警觉。

**复现方向建议(推荐 1 + 2 合并为案例三)**:

- **最贴合实验室定位**:复用案例一的 watch/_handle_content 链路与检出闸门,新增
  "BIP-39 助记词序列检出 → 强告警 + 审计",以及一个扫描本地图片目录的 `clipper scan`
  子命令(OCR 可用 tesseract,Pillow 出图);这是纯防御工具,与红线(仅本机)完全一致,
  且与真实威胁(SparkCat/Efimer)逐点对应。
- **不推荐**:攻击侧复现 OCR 窃取/无障碍监听——武器化程度高、跨平台成本大,
  且攻击链的认知价值已被本文档与上述防御工具覆盖。

## 6. 结论

助记词木马 = "clipper 的变现升级 + infostealer 的目标升级",移动端以**相册 OCR** 为主流
(iOS 因沙盒几乎只剩这条路 + 钓鱼),PC 端以**嗅探 + 文件窃取**为主流。iOS 的强沙盒把
防御责任推给了用户行为(不数字化保存助记词),因此防御工具的价值在于:**在用户犯错之前
把已经数字化的助记词找出来**。建议以"剪贴板助记词告警 + 本地图片扫描自检"立项案例三,
另开实现 Issue 承载。
