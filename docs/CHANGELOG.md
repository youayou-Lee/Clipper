# 迭代日志 — Clipper

> 每个迭代周期一条:目标、改动、证据(测试/实测)、发现的问题、下一步。
> 原则:**真实优先于好看**——失败照记,未验证的不写"已完成"。

## v0.1.0(2026-09-05)— 起点:检测 + 告警 + 完全匹配替换写回

**目标**:剪贴板地址守护的最小可用闭环——检出、告警、防误粘。

**架构落地**:

| 部件 | 文件 | 职责 |
|---|---|---|
| 候选提取与校验 | `clipper/detect/` | 宽松正则提取 + 校验和闸门(Base58Check / BIP-173/350 / EIP-55) |
| 内容清洗 | `clipper/normalize.py` | 剥零宽字符与空白,防隐形字符混淆、修复断行地址 |
| 剪贴板后端 | `clipper/platforms/` | Linux(wl-paste/xclip/xsel)、Windows(ctypes)、macOS(pbpaste);read + write |
| 告警 | `clipper/alert.py` | 纯控制台,无弹窗 |
| 固定安全地址 | `clipper/safe.py` | 首次随机生成 bech32 地址并固化;`splice()` 保头 4 尾 4、等长替换 |
| 监控与替换 | `clipper/watcher.py` + `cli.py` | watch 轮询;检出→告警→记历史→替换写回(默认完全匹配模式) |

**证据**:
- L1 单元测试 20 项全绿(测试向量来自 BIP-173 与 EIP-55 官方规范)
- L3 端到端:`scripts/demo.py` 8 场景全 PASS;本机 xclip 实测——纯地址/首尾空白 → 替换,末尾多一字符/夹在句中 → 只告警不改写,替换后不循环触发

**已知问题**(→ v0.2):
- 替换链路(splice / match_exact / _handle_content)尚无单元测试,仅手工验证
- Windows/macOS 的 read/write 无端到端验证
- 告警只有控制台,无 webhook 等远程通知渠道

## v0.2 进展(#2 ✅ 2026-09-05,PR #6 → d096fd2)

- **替换链路单元测试落地**:+37 用例(总 57,pytest 兼容运行存量 20)——splice 等长/头尾保留/循环取用/退化路径,match_exact 三地址类型+7 种非精确拒绝,_handle_content exact/contains/写回失败/防循环,safe.load 固化与 0600
- **pytest 迁移**:pyproject dev extra,CI 命令改 `pytest -v`(job 更名 tests),pre-push 钩子与文档同步
- **仓库转公开**,分支保护生效(required check `tests` + strict + enforce_admins),此前由本地 pre-push 钩子兜底
**流程补强(2026-09-05)**:引入 obra/superpowers 的 requesting-code-review / receiving-code-review skill,merge 前新增审核阶段(reviewer 子代理只看 diff 与需求;Critical 立即修 / Important merge 前修 / Minor 记 Issue),写入 AGENTS.md 与 WORKFLOW Step 5。
- v0.2 剩余:#3 webhook 告警、#4 Windows/macOS 端到端
- **#3 ✅(2026-09-05,PR #9 → 230178d)**:`clipper watch --webhook URL` 检出地址时 POST JSON({ts, findings[], original_text}),urllib 标准库零依赖,3s 超时、任何失败仅 stderr 警告且不影响替换写回(有专门测试钉住);不传参零网络请求。首次完整走通"审核阶段":reviewer 子代理 2 Important(失败路径无测试)修复 + 3 Minor 采纳(ts 带时区/失败信息不泄漏 URL token/README 数据暴露警告),复核 APPROVE 后 merge;剩余 Minor 记 Issue #10。65 用例全绿
- **#13 ✅(2026-09-05,PR #14 → 021e26b)**:统一 uv 工具链——uv.lock 入库,CI 改 setup-uv + `uv run pytest`,pre-push 钩子优先 uv(回退 .venv),文档命令统一 `uv sync`/`uv run`;冗余 dev extra 已删(reviewer Minor 采纳),钩子打磨记 Issue #15。65 用例全绿,CI 9s。另:#12 收口 .gitignore(.local/ 本机设备信息不入库),you-win(Windows 测试机)SSH 免密打通,Issue #4 范围收窄为 Windows(macOS 延后)
