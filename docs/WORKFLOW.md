# 工程开发规范:流程、计划、测试

> 本项目(单人 + AI 协作)的实际工作规范,参照 coding-agent 的 `docs/WORKFLOW.md` 制定。
> 原则:**main 随时可发布,每个变更有据可查,一切以测试数据为准**。
> 配套设施:CI(pytest,PR 强制)、分支保护(required check)、Issue 模板、Milestone。

## 0. 计划表三层:在哪、怎么看

| 层 | 载体 | 位置 |
|---|---|---|
| 北极星(月级以上) | 项目定位:剪贴板地址守护的可用工具 | README + 版本收口时对照更新 |
| 版本切分 | Roadmap(本文件 §6)+ GitHub Milestone | 见 §6 |
| 任务级 | Issue(挂 Milestone) | GitHub Issues |

**看进度**:

```bash
gh api repos/youayou-Lee/Clipper/milestones --jq '.[] | "\(.title): \(.open_issues) open / \(.closed_issues) closed, due \(.due_on)"'
gh issue list --milestone "v0.2" --state all
```

## 1. 一个功能的生命周期:七步,每步合格标准

### Step 1 立项 —— 写 Issue
- [ ] "要解决的问题"讲清场景(痛点,不是"实现 X")
- [ ] 验收标准 ≥3 条,每条**可测试**(不写"更好用",写"`clipper scan --json` 输出包含字段 X")
- [ ] 挂 Milestone;预计 >3 天 → 拆成子 Issue

### Step 2 设计 —— 先方案后代码
- [ ] Issue 下补设计评论:模块划分、接缝(改哪些文件)、测试计划
- [ ] 能用一段话讲清"数据怎么从剪贴板流到告警/替换";讲不清 → 回去重想
- [ ] 关键决策列 A/B 备选 + 取舍理由

### Step 3 开发 —— 分支 + 小步提交
- [ ] `git switch main && git pull --ff-only` 后切 `feat/xxx` / `fix/xxx` / `docs/xxx`;一分支一 Issue
- [ ] **测试红不 commit 不 push**;一个 commit 一件事;message `type: 动机`(feat/fix/docs/refactor/test/chore)
- [ ] 混了就 `git rebase -i` 拆

### Step 4 自测 —— 三层(详见 §3)
- [ ] L1 pytest 全绿(与 CI 同套)
- [ ] 涉及剪贴板读/写行为 → 本机端到端验证(Linux:xclip 实测),输出留痕贴进 PR
- [ ] 平台相关改动 → 说明未覆盖平台的风险

### Step 5 PR
- [ ] 描述四要素:动机(`Refs #N`)/ 改动(逐模块一句话)/ 验证(数据)/ 风险与回滚
- [ ] CI 绿(分支保护强制,不许绕);merge 前自己通读一遍 diff

### Step 6 合并收尾
- [ ] 只用 squash:`gh pr merge --squash --delete-branch`
- [ ] CHANGELOG 当天有条目;`Closes #N` 仅限"本 PR 完全解决该 Issue",前置/关联一律 `Refs #N`
- [ ] 核对 Milestone 进度

### Step 7 版本收口 —— 复盘
- [ ] Milestone 全关 → `git tag v0.x.0 && git push --tags`
- [ ] 对照 README"路线图"逐项更新勾选
- [ ] CHANGELOG 版本总结:做了什么、验证数据、下一版本为什么是它

## 2. 计划怎么分

```
北极星(可信的剪贴板地址守护)
  → Milestone(版本,2-4 周量级):v0.1 → v0.2 → v0.3
    → Issue(1-3 天原子任务,一 Issue = 一 PR)
```

**拆 Issue 规则**:
- 一 Issue = 一 PR,预计 1-3 天;估超 → 继续拆
- 每版本先打通最小可验收路径,再补边界加固
- 依赖关系写进 Issue 正文("依赖 #N");父 Issue 用 tasklist 跟踪子 Issue
- Milestone 建立时机:上一版本收口时建下一个

## 3. 三层测试体系

| 层 | 测什么 | 怎么跑 | 何时跑 | 合格标准 |
|---|---|---|---|---|
| **L1 单元** | 纯逻辑:检测/校验和(base58、bech32、EIP-55)、normalize、safe.splice、match_exact | pytest,`tests/test_*.py` | 每次 commit 前 + CI 强制 | 全绿;每公开函数有正常例+边界例 |
| **L2 组件** | 剪贴板读→扫→替换→写回链路(fake backend) | scripted 场景,零外部依赖 | 改动 watch/_handle_content 的 PR | 覆盖:检出替换 / 不检出不动 / 写回失败 / 完全匹配拒绝多余字符;改写后不循环告警 |
| **L3 端到端** | 真实剪贴板(本机 xclip/wl-copy) | `scripts/demo.py` 8 场景 + 手工验证 | 涉及剪贴板行为的 PR | demo 全 PASS;实际粘贴内容符合预期,输出贴 PR |

**三条纪律(铁律)**:
1. 测试红 → 不 push 不 merge
2. 修 bug 先写复现测试再修;修复后测试永久留在回归集
3. "应该没问题"不作数,测试与实测数据说话

## 4. 一票否决速查表

| 环节 | 一票否决项 |
|---|---|
| Issue | 无可测试验收标准 → 不开工 |
| 设计 | 讲不清数据流动 → 重想 |
| 开发 | 测试红 commit → 打回 |
| PR | CI 不绿 / 描述缺要素 → 不 merge |
| 收尾 | CHANGELOG 缺条目 / Issue 关错 → 补完算完 |
| 版本收口 | 路线图未更新 → 不打 tag |

## 5. 常用命令

```bash
# 分支与提交
git switch main && git pull --ff-only
git switch -c feat/xxx

# Issue / PR
gh issue create -t "标题" -l enhancement -m "v0.2" -b "正文"
gh pr create --fill-first          # 标题取首个 commit,正文补四要素
gh pr checks                       # CI 状态
gh pr merge --squash --delete-branch

# 测试
.venv/bin/pytest tests/ -v   # L1+L2
.venv/bin/python scripts/demo.py                    # L3 端到端(本机)

# 版本收口
git tag v0.x.0 && git push --tags
```

## 6. Roadmap

| 版本 | 内容 | 状态 |
|---|---|---|
| v0.1 | 检测(校验和闸门)+ watch/scan/paste/history + 完全匹配替换写回 | ✅ 已发布 |
| 流程脚手架 | WORKFLOW/CI/Issue 模板/CHANGELOG/Milestone | 🚧 本分支 |
| **v0.2** | 替换链路单元测试;平台端到端;webhook 告警 | 收口 v0.1 时建 |
| v0.3 | 写入者进程归因;浏览器扩展联动调研 | v0.2 收口时建 |

> 本文件随流程演进更新;改本文件也走 PR(docs/ 前缀)。
