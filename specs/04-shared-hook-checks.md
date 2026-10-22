# 任务：统一 Git 与 Codex hook 的检查入口

## 来源与目标

- 需求来源：用户指出 `.codex` 与 `.githooks` 重复维护测试命令，希望抽出共用脚本。
- 目标用户：F2 项目开发者和使用 Codex 的成员。
- 要解决的问题：两处检查清单容易出现遗漏或不一致。
- 完成后的可观察结果：两个 hook 都调用 `scripts/check_project.py`，手工也能运行同一命令。

## 当前行为

- 触发步骤：Codex 修改代码或执行 `git commit`。
- 实际结果：Codex 的 `policy.py` 和 Git 的 `pre-commit` 分别维护 Python 测试、JavaScript 测试与前端构建命令。
- 相关文件/接口：`.codex/hooks/policy.py`、`.githooks/pre-commit`、`tests/`、`frontend/package.json`。
- 未确认信息：后续是否引入 Ruff/ESLint；本轮使用已存在且验证通过的检查。

## 期望行为

- 正常输入 → 两种触发方式均运行同一组空白、语法、单元测试和前端构建检查。
- 信息不足 → 所需命令未安装时报告失败，开发者补齐环境。
- 错误/冲突 → 任一检查失败时共用脚本返回非零状态；Git 阻止提交，Codex 将失败反馈给 Agent 修复。
- 人工确认点 → 开发者仍审查测试输出；Codex 项目 hook 的信任由用户在 `/hooks` 中确认。

## 本轮范围

- 允许修改：`scripts/check_project.py`、`.githooks/pre-commit`、`.codex/hooks/policy.py`、相关测试、`README.md`、`AGENTS.md` 和本任务卡。
- 暂不实现：新增 lint 工具、变更业务逻辑、扩大 hook 的工具覆盖范围。
- 必须保持：Git 提交前失败拦截、Codex 写入前规则和修改后失败反馈。

## 验收

- 用例1：运行 `python scripts/check_project.py`、`git hook run pre-commit`，两者执行相同检查且通过。
- 用例2：Codex PostToolUse 模拟检查脚本返回失败，收到 `block` 和修复提示。
- 测试命令：`python -m unittest discover -s tests -v`、`python scripts/check_project.py`、`git hook run pre-commit`、`git diff --check`。
- 交付证据：代码 Diff、两个 hook 的调用输出、失败反馈测试及未通过项。
