# 任务：Codex 写入保护与修改后检查

## 来源与目标

- 需求来源：用户要求配置 Pre-Command 与 Post-Command Hook。
- 目标用户：使用 Codex 开发 F2 的项目成员。
- 要解决的问题：写入敏感赋值或忽略文件，以及改动代码后忘记运行检查。
- 完成后的可观察结果：Codex 写入前拒绝可识别的违规操作，代码修改后运行检查并把失败反馈给 Agent。

## 当前行为

- 触发步骤：让 Codex 通过 `apply_patch` 或命令行修改代码。
- 实际结果：F2 只有 Git `pre-commit` hook，Codex 工具调用前后没有项目 hook。
- 相关文件/接口：`.githooks/pre-commit`、`.gitignore`、`tests/`、`frontend/package.json`、Codex 项目 `.codex/hooks.json`。
- 未确认信息：其他编辑器或外部程序的写入不经过 Codex 工具事件。

## 期望行为

- 正常输入 → 修改受版本管理的代码后，完成基础 lint、语法、单元测试和前端构建。
- 信息不足 → 无法识别为写操作的命令不触发写入检查；需要人工审查复杂命令。
- 错误/冲突 → 检测到敏感赋值或已识别的忽略目标时拒绝写入；修改后检查失败时反馈给 Agent 修复。
- 人工确认点 → 用户在 Codex `/hooks` 中审查并信任项目 hook；项目成员仍要审查代码与测试结果。

## 本轮范围

- 允许修改：`.codex/hooks.json`、`.codex/hooks/policy.py`、`tests/test_codex_hooks.py`、`README.md`、`AGENTS.md`、本任务卡。
- 暂不实现：Ruff/ESLint 依赖安装、对任意脚本写入的完整拦截、外部编辑器或 CI 策略。
- 必须保持：现有 Git `pre-commit` 和业务接口不变；不读取或输出密钥值。

## 验收

- 用例1：模拟 `apply_patch` 添加敏感赋值或忽略文件，PreToolUse 返回 deny，且反馈中不含敏感值。
- 用例2：模拟代码修改后的检查失败，PostToolUse 返回 block 和修复提示；正常检查全部通过。
- 测试命令：`python -m unittest discover -s tests -v`、`node --test tests/application_filters.test.mjs`、`npm --prefix frontend run build`、`git diff --check`。
- 交付证据：hook 配置与脚本 Diff、测试输出、信任状态和未覆盖的写入路径。
