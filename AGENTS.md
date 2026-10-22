# 项目目标

为风控专员和客户经理提供基于虚构教学数据的授信申请查看与人工预审复核流程，使单笔申请能够从“待风控复核”流转到“待审批”或“待企业补充材料”。

# 项目结构

- 前端：`frontend/src/` 是 React 页面、组件和取数代码；`frontend/package.json` 管理 Vite 命令和依赖。
- 后端：`backend/app/main.py` 是 FastAPI 入口；`backend/app/data.py` 负责数据访问与关联校验；`backend/app/models.py` 定义对象和响应结构；`backend/pyproject.toml` 与 `backend/uv.lock` 管理 Python 依赖。
- 测试：`tests/`。
- 业务规则和接口契约：每轮任务卡存放在 `specs/`，当前为 `specs/02-pre-commit-tests.md`，新任务参考 `specs/TEMPLATE.md`；上级目录 `../06-F2-MVP范围表.md`、`../06-F2交接清单.md`；接口及对象说明 `docs/data-contract.md`；代码约定 `docs/coding-standards.md`。虚构数据在 `mock_data/seed.json`。

# 开始任务前

- 阅读 `README.md`、与用户当前任务对应的 `specs/` 任务卡、相关代码和测试；涉及角色或状态时核对 F1 交接文件。
- 确认工作目录是 F2 仓库，检查 `git status`，运行现有测试并记录结果，保留用户已有改动。
- 沿“页面/接口入口 → 业务逻辑 → 数据 → 测试”找到本轮修改位置；逐页完成任务卡，验证当前页面后再做下一页。

# 修改规则

- 只修改本轮任务卡涉及的文件或模块；发现必须扩大范围时说明原因，再围绕本轮目标实施。
- 保持现有字段、接口和代码风格一致。修改字段或状态时同步维护模型、虚构样例、契约文档及相关测试。
- 区分 F1 已确认的业务约定与教学实现假设，不编造授信规则。AI 关注项不代表审批结论；证据不足、解析失败和无报告不能展示为“无风险”。
- 不读取或输出密钥，不操作未经授权的外部系统；只使用虚构教学数据，不引入真实客户或征信信息。

# 验证与交付

- 在 F2 根目录运行 `python -m unittest discover -s tests -v` 和 `git diff --check`；修改前端时在 `frontend/` 运行 `npm run build`，有 JavaScript 单元测试时再运行任务卡列出的命令。
- 检查 Diff、相关接口和页面的正常、空值与错误状态；失败时保留真实结果，不把未运行的检查写成通过。
- 交付时说明修改文件、可观察行为、测试结果与剩余风险；保持每次提交聚焦本轮任务。
