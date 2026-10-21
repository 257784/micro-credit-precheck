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

当前仅建立工程骨架。业务接口、MySQL 表结构、Mock 样例及页面将在后续步骤实现。

## 本地启动

前端：进入 `frontend`，运行 `npm install` 和 `npm run dev`。

后端：安装 uv 后进入 `backend`，运行 `uv sync` 和 `uv run uvicorn app.main:app --reload`。可访问 `/health` 检查服务。
