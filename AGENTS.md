# Clipper 工程规范(对 AI 协作者与人类同等生效)

完整版见 `docs/WORKFLOW.md`,本文件是每次开工前的速查约束。

## 流程铁律(Issue 驱动的 GitHub Flow)

1. **先 Issue 后代码**:用户提出新功能/想法/改进时,**第一动作是 `gh issue create`**,
   而不是直接写代码。Issue 必须含:场景痛点 + ≥3 条可测试的验收标准 + 挂 Milestone;
   预估 >3 天必须拆子 Issue。
2. **一分支一 Issue**:从 main 切 `feat/xxx` / `fix/xxx` / `docs/xxx`;先
   `git switch main && git pull --ff-only`。
3. **测试红不 commit 不 push**:commit/push 前必跑(钩子会拦截 push):
   ```bash
   .venv/bin/pytest tests/ -v
   ```
4. **修 bug 先写复现测试**(红)再修,修完该测试永久留在回归集。
5. **PR 描述四要素**:动机(关联 Issue 用 `Refs #N`,不用 `Closes`)/ 改动(逐模块一句话)/
   验证(测试与实测数据)/ 风险与回滚。CI 绿才许 merge。
6. **只用 squash merge**:`gh pr merge --squash --delete-branch`。
7. **合并当天更新 `docs/CHANGELOG.md`**,并核对 Milestone 进度。

## 测试

- L1 单元:`tests/`,pytest 风格(存量 unittest 用例由 pytest 兼容运行)
- L2 组件:fake clipboard backend 走 watch/_handle_content 链路
- L3 端到端:`.venv/bin/python scripts/demo.py`(8 场景)+ 本机 xclip 实测

## 项目速览

剪贴板加密货币地址守护:检出(Base58Check/BIP-173/EIP-55 校验和闸门)→ 控制台告警 →
写回剪贴板(默认完全匹配模式:整段恰好一个合法地址才替换;替换 = 保原地址头 4 尾 4、
中间换成固定安全地址中段、等长)。固定地址在 `~/.local/share/clipper/safe_address`
(`clipper address --regenerate` 重新生成)。

## 分支保护替代(私有免费仓库无 branch protection)

`core.hooksPath=scripts/hooks`:pre-push 跑全量测试,红则拒绝 push——不要绕过(--no-verify 禁用)。
