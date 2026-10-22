# 小微企业授信智能预审系统 F2

本目录承接上级目录的《06-F2-MVP范围表.md》和《06-F2交接清单.md》。F2 使用虚构教学数据，目标是跑通申请列表、详情、材料、Mock AI 预审报告及人工风控复核的单笔闭环。完成复核后进入“待审批”；要求补件后进入“待企业补充材料”。正式授信审批不在本阶段范围内。

## 技术栈

| 部分 | 选择 |
| --- | --- |
| 前端 | React + Vite |
| 后端 | Python + FastAPI |
| 数据库 | MySQL（后续业务实现接入） |
| 后端依赖与环境 | uv |

## 目录

| 目录 | 用途 |
| --- | --- |
| `frontend/` | React 页面与前端资源 |
| `backend/` | FastAPI 接口及后端配置 |
| `mock_data/` | 虚构申请、材料、知识与报告样例 |
| `docs/` | F2 设计与开发文档 |
| `tests/` | 业务流程与接口测试 |

当前已提供只读的虚构申请、企业、材料和 AI 报告样例，前端可从申请列表查看详情。数据结构与存储取舍见 [核心数据对象与只读接口](docs/data-contract.md)。人工复核提交、MySQL 持久化和真实材料预览将在后续步骤实现。

代码风格、注释约定和提交前检查见 [F2 代码规范](docs/coding-standards.md)。

## 提交前自动测试

首次克隆仓库后，在 F2 根目录运行 `git config --local core.hooksPath .githooks` 启用仓库内的 hook。该配置只对本机当前仓库生效；可用 `git config --local --get core.hooksPath` 确认。

之后每次执行 `git commit`，`.githooks/pre-commit` 会调用共用的 `scripts/check_project.py`；任一步失败都会停止提交，修复后重新提交。手动运行 `python scripts/check_project.py` 即可执行相同检查。Git hook 在提交时执行；如需每次保存文件后运行测试，需要单独配置编辑器任务或文件监视器。

## Codex 写入前后检查

F2 项目的 `.codex/hooks.json` 配置了 Codex `PreToolUse` 和 `PostToolUse`。请将 **F2 目录作为 Codex 项目打开**，在 Codex 中用 `/hooks` 审查并信任项目 hook。它们与上面的 Git `pre-commit` 相互独立。

写入前，hook 检查 `apply_patch` 和常见命令行写入：如果新增内容出现密码/令牌赋值，或识别出的目标路径被 `.gitignore` 忽略，则拒绝该操作。写入代码后，Codex 也调用 `scripts/check_project.py` 运行空白检查、Python 语法检查、Python/JavaScript 单元测试及前端构建；失败结果返回给 Agent，请先修复再继续。当前的“lint”是空白与语法基础检查，项目尚未安装 Ruff 或 ESLint。

这些 hook 只覆盖 Codex 支持的工具事件及脚本能识别的写法；复杂脚本、其他程序写入和用户手工修改仍需 Git 提交前检查与人工审查。`PostToolUse` 也不能撤销已经完成的写入。

## 本地启动

首次创建后端虚拟环境（在 `backend` 目录）：`python -m venv .venv`。PowerShell 中可用 `.\.venv\Scripts\Activate.ps1` 激活；如果执行策略阻止激活，可直接运行 `.\.venv\Scripts\python.exe`。`.venv` 已被 Git 忽略。安装 uv 后运行 `python -m uv sync`，由 uv 管理这个环境及 `pyproject.toml` 中的依赖。使用 `python -m uv` 不要求将用户级 Scripts 目录加入 PATH。

前端：进入 `frontend`，将 `.env.example` 复制为 `.env`，运行 `npm install` 和 `npm run dev`，打开终端输出的本地地址。

后端：安装 uv 后进入 `backend`，将 `.env.example` 复制为 `.env`，运行 `python -m uv sync` 和 `python -m uv run --env-file .env uvicorn app.main:app --reload`。可访问 `http://127.0.0.1:8000/api/health` 检查服务。

两个服务需在不同终端启动，前端开发服务通过 `BACKEND_URL` 转发 `/api` 请求。`backend/.env` 中的 `DATABASE_URL` 目前只是后续接入 MySQL 的示例，不会建立数据库连接。

修改 `mock_data/seed.json` 后请重启后端。该文件位于 `backend` 目录外，当前 `--reload` 启动命令不保证自动监视到它。

首次安装依赖需要能够访问 Python 与 npm 包源。若当前机器无法联网，可先用已有的 Python 环境执行 `python -m uvicorn app.main:app --reload` 检查后端，但正式的后端依赖管理仍使用 uv。
