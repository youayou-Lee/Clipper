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
- **#4 ✅ Windows 部分(2026-09-05,PR #17 → 67bb916)**:`scripts/e2e_platform.py` 跨平台剪贴板 e2e 脚本(--self-test/--read/--write,零第三方依赖);Windows 真机(you-win)实测——往返 PASS(含中文 token)、写方向用户桌面确认、读方向逐字符一致;关键技术结论:ssh 会话剪贴板隔离,须用计划任务投射交互会话;修 PS5.1 stdin 码页乱码(写方向 base64 载荷,reviewer Important)+ 新增 8 项单测(总 73)。macOS 延后,有设备再拆子 Issue;reviewer 两个非阻塞 nit 记 Issue #18
- **#10 ✅(2026-09-06,PR #19)**:webhook payload ts 带时区偏移+微秒精度;test_webhook 去重(Fail 服务/FakeBackend 抽 fixture)
- **#15 ✅(2026-09-06,PR #21)**:pre-push 钩子打磨——`uv run --locked` 快速失败;区分"测试红"与"uv/环境失败"两种拒绝语义(以 pytest 输出特征判定);.venv 回退注释明确仅 POSIX(Windows 走 uv);三种路径本地实测
- **#19 ✅(2026-09-06,PR #22)**:e2e 脚本移除死代码 parser.error(required 互斥组已兜底);_ps() 缺失时友好报错而非裸 TypeError(+2 单测,总 75)
- **#27 ✅(2026-09-06,PR #28)**:README 重写——定位改为"复现 Clipper 木马核心机制并开源供分析+制定应对策略",含免责声明、复现范围表、5 条示例应对策略、威胁研究一节(#23);reviewer 提醒补回 webhook 隐私警告
- **研究体系建立(2026-09-06)**:父 Issue #23 + 三个子 Issue(#24 分发/#25 免杀/#26 加载运行),防御视角红线,产物收 docs/research/
- **#24 ✅(2026-09-06,PR #30)**:docs/research/attack-chain.md——攻击链全景骨架 + 「分发」章节:7 类渠道矩阵(A 捆绑/B 广告投毒+TDS/C 声誉经济/D 假客户端/E 社交/F USB 蠕虫/G 浏览器扩展),全部厂商一手报告溯源;攻击者取舍分析(规模/成本/暴露/精度);5 种交接形态(→#25 免杀/加载)。方法论按用户要求修订为"先攻击者构建链路,后防守者映射"(#23/#24/#25/#26 全部改写);#26 改为依赖 #24/#25

---

## v0.2(2026-09-06 收口)— 定位确立 + 攻击链研究启动

**版本主题**:从"纯防御工具"确立为"复现 Clipper 木马机制供分析 + 攻击链研究 + 对抗策略"。

**完成**(5/5 Issue,Milestone v0.2 清零):
- #2 替换链路单元测试(PR #6,+37 用例)与 pytest 迁移
- #13 统一 uv 工具链(PR #14,uv.lock/CI/钩子/文档)
- #3 webhook 告警(PR #9)——首次完整走通审核阶段
- #4 Windows 真机 e2e(PR #17,ssh/计划任务/编码修复);macOS 延后
- #24 攻击链「分发」章节(PR #30,7 渠道全部溯源)+ #23-26 方法论确立为"先攻击后防御"

**基础设施**:仓库转公开+分支保护(required check+strict)、pre-push 测试闸门(钩子打磨 #15/#19/#10)、审核阶段(requesting-code-review skill)、README 重写(#27/#28)。

**数据**:75 用例全绿;CI ~10s;本版 PR 全部经 reviewer 子代理审核(两次 REQUEST_CHANGES 均修复后复核通过:钩子 Critical 放行洞、e2e 编码 Important)。

**下一版(v0.3)方向**:#25 免杀/加载运行章节 → #26 防守映射 → 对抗策略落地为本项目 Issue;攻击链研究成为仓库的一等公民内容。
