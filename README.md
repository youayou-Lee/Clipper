# Clipper — 剪贴板守护

一个跨平台的剪贴板安全工具:**在粘贴之前**检测剪贴板中的比特币/以太坊地址并告警,
用来对抗剪贴板劫持类攻击(clipper 木马会把你复制的收款地址替换成攻击者的地址)。



## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

剪贴板后端依赖(按你的显示协议二选一):

```bash
sudo apt install xclip          # X11
sudo apt install wl-clipboard   # Wayland
```

## 使用

```bash
clipper watch            # 常驻监控:检出地址时告警,并把"原文+提示"写回剪贴板
clipper paste            # 代替 Ctrl+V:原样输出剪贴板原文,检出地址时追加提示
clipper scan             # 立即扫描当前剪贴板
clipper scan --text "..."# 扫描任意文本(调试用)
clipper scan --json      # JSON 输出
clipper history          # 查看最近检出的地址
```

**核心防护形态**是 `clipper watch` 常驻后台:一旦检出加密货币地址,除了控制台告警,
还会把剪贴板里的地址原位替换成一个固定地址的变体并写回剪贴板——
替换规则是保留原地址前 4 位和后 4 位不变,中间换成固定地址的中段,总长度不变
(固定地址由 `clipper address` 首次随机生成并固化)。替换后的地址保留了原地址的
头尾形态、且长度与原文一致,排版不会跳变;但它不再是通过校验和的有效地址,
也不会与固定地址本身混淆。改写只发生一次,不会循环触发告警;历史记录里保存的仍是原始地址。

替换默认工作在**完全匹配模式**:剪贴板内容(去除首尾空白后)必须整体恰好是一个
合法地址才会替换——地址后面多粘一个字符、或夹在句子里的地址都只告警、不动内容,
避免改坏正常文本。加 `--contains` 切换到包含模式:文本中任何位置检出地址都原位替换。

`watch` 常用参数:`--interval 0.5`(轮询秒数)、`--skip-unchecked`(不告警未校验地址)、`--db PATH`。
`paste` 也支持 `--skip-unchecked`、`--db PATH`。

## 检测原理:两层,校验和是唯一闸门

1. **候选提取**(宽松正则):Base58(`1`/`3` 开头)、Bech32(`bc1`/`tb1`)、EVM(`0x`+40 位十六进制)。
2. **真实验证**:
   - BTC Base58 → Base58Check 双 SHA256 校验和
   - BTC Bech32 → BIP-173/350 多项式校验和 + 见证版本/长度规则(v0: 20/32 字节;v1: 32 字节)
   - ETH → EIP-55 大小写校验和(keccak256)

只有通过校验和的地址才告警,误报率接近零。
`0x` 前缀 40 位十六进制天然排除了 git commit SHA(无 `0x` 前缀)和交易哈希(64 位)。

**EIP-55 无法校验的情况**:纯小写/纯大写地址没有大小写校验信息。默认仍告警
(标为"未校验"——漏报比偶发打扰更糟),用 `--skip-unchecked` 可关闭。

## 内容清洗

扫描前会剥离零宽字符(ZWSP/ZWNJ/ZWJ/Word Joiner/BOM/软连字符)和全部空白,
既修复从聊天工具/PDF 复制出来的换行地址,也防御隐形字符混淆。

## 平台支持

| 平台 | 后端 | 说明 |
|---|---|---|
| Linux | `wl-paste`(Wayland)/ `xclip`、`xsel`(X11) | 本机开发环境 |
| Windows | ctypes 调用 Win32 剪贴板 API | 无第三方依赖 |
| macOS | `pbpaste` | 系统自带 |

告警:仅控制台输出(所有平台一致,无弹窗依赖)。

## 历史

检出的地址写入本地 sqlite(默认 `~/.local/share/clipper/history.db`,权限 0600)。
地址本身不是机密(公钥),但历史能帮你事后核对"我当时要转给谁"。

## 路线图

- [ ] Windows/macOS 端到端测试
- [ ] 写入者进程归因(X11 可查 selection owner → PID;Wayland 受限;Windows 可查 clipboard owner)
- [ ] 浏览器扩展联动:粘贴进网页输入框时二次确认
- [ ] 托盘 GUI、webhook 告警

## 测试

```bash
.venv/bin/pytest tests/ -v   # 测试(pytest,兼容 unittest 风格)
.venv/bin/python scripts/demo.py                    # 8 个真实场景的端到端演示(自检)
```

测试向量来自 BIP-173 与 EIP-55 官方规范。
