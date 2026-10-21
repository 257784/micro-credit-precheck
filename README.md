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

## 本地启动

首次创建后端虚拟环境（在 `backend` 目录）：`python -m venv .venv`。PowerShell 中可用 `.\.venv\Scripts\Activate.ps1` 激活；如果执行策略阻止激活，可直接运行 `.\.venv\Scripts\python.exe`。`.venv` 已被 Git 忽略。安装 uv 后运行 `python -m uv sync`，由 uv 管理这个环境及 `pyproject.toml` 中的依赖。使用 `python -m uv` 不要求将用户级 Scripts 目录加入 PATH。

前端：进入 `frontend`，将 `.env.example` 复制为 `.env`，运行 `npm install` 和 `npm run dev`，打开终端输出的本地地址。

后端：安装 uv 后进入 `backend`，将 `.env.example` 复制为 `.env`，运行 `python -m uv sync` 和 `python -m uv run --env-file .env uvicorn app.main:app --reload`。可访问 `http://127.0.0.1:8000/api/health` 检查服务。

两个服务需在不同终端启动，前端开发服务通过 `BACKEND_URL` 转发 `/api` 请求。`backend/.env` 中的 `DATABASE_URL` 目前只是后续接入 MySQL 的示例，不会建立数据库连接。

修改 `mock_data/seed.json` 后请重启后端。该文件位于 `backend` 目录外，当前 `--reload` 启动命令不保证自动监视到它。

首次安装依赖需要能够访问 Python 与 npm 包源。若当前机器无法联网，可先用已有的 Python 环境执行 `python -m uvicorn app.main:app --reload` 检查后端，但正式的后端依赖管理仍使用 uv。
