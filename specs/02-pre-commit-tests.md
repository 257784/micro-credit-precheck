# 任务：提交前自动运行测试

## 来源与目标

- 需求来源：用户希望每次改完代码后自动执行测试。
- 目标用户：F2 项目开发者。
- 要解决的问题：修改代码后容易遗漏手工运行 Python、JavaScript 测试和前端构建。
- 完成后的可观察结果：执行 `git commit` 时自动运行现有检查，任一检查失败则停止提交。

## 当前行为

- 触发步骤：修改并暂存代码，然后执行 `git commit`。
- 实际结果：仓库没有启用自定义 Git hook，提交前不会自动执行项目测试。
- 相关文件/接口：`AGENTS.md`、`README.md`、`tests/`、`frontend/package.json`、`.gitattributes`、Git 的本地 `core.hooksPath` 配置。
- 未确认信息：用户是否还希望每次保存文件时运行测试；本轮按 Git 提交前自动检查实现。

## 期望行为

- 正常输入 → 提交前依次检查暂存区空白、Python 测试、JavaScript 测试及前端构建，通过后继续提交。
- 信息不足 → 本机未安装或未将 Python、Node.js、npm 放入 PATH 时，命令失败并停止提交，由开发者补齐环境。
- 错误/冲突 → 任一检查失败时输出原始错误并阻止本次提交；修复后重新运行 `git commit`。
- 人工确认点 → 开发者决定何时暂存和提交代码；每次保存文件的即时测试另行配置文件监视器。

## 本轮范围

- 允许修改：`.githooks/pre-commit`、`.gitattributes`、`README.md`、`AGENTS.md`、本任务卡以及本地 Git `core.hooksPath`。
- 暂不实现：编辑器每次保存时的自动测试、CI 远端流水线、新业务测试或依赖迁移。
- 必须保持：现有业务对象、接口和测试命令不变；hook 文件可被 Git 执行且跨平台换行一致。

## 验收

- 用例1：运行 `.githooks/pre-commit`，全部现有测试和构建通过；提交时 Git 实际调用该 hook。
- 用例2：暂存内容有空白错误或任一测试失败时，hook 返回非零状态，Git 中断提交。
- 测试命令：`sh .githooks/pre-commit`、`git diff --check`、`git config --local --get core.hooksPath`。
- 交付证据：代码 Diff、测试输出、Git hook 路径和文件模式，以及未通过项及原因。
