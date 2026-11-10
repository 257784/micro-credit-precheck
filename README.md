# 小微企业授信智能预审系统

本项目是面向小微企业授信场景的教学原型，沿用 F1/F2 业务对象，支持企业提交申请、材料检查、客户经理跟进、风控复核和人工审批。AI 用于政策解释和风险提示，不直接作授信决定。

> 仅供本机教学，使用虚构数据。系统尚未完成生产级安全、部署和数据保护；不要接入真实客户资料或暴露到不可信网络。

## 业务流程与角色

企业保存草稿并上传材料；材料检查通过后正式提交，系统按未结束申请数量自动分配客户经理。风控人员生成 AI 预审报告并逐项复核，可要求补件或提交审批；审批人员记录通过或未通过。

| 角色 | 账号角色标识 | 主要操作 |
| --- | --- | --- |
| 企业客户 | `enterprise` | 查看自己的申请，上传材料、检查并提交 |
| 客户经理 | `customer_manager` | 查看负责的申请、提出补件建议、使用授信助手 |
| 风控专员 | `risk_reviewer` | 运行风险预审、记录人工复核或正式要求补件 |
| 审批人员 | `approver` | 查看进入审批阶段的申请，记录人工审批结果 |
| 管理员 | `admin` | 管理账号、查询操作日志和助手审计 |

AI 报告可由风控选择采纳、部分采纳或不采纳。状态和权限详见 [状态流转校验图](docs/architecture/32-申请状态流转校验图.md) 与 [角色权限矩阵](docs/architecture/31-角色权限矩阵.md)。

## 技术栈和前置条件

以下步骤以 **Windows PowerShell**、仓库根目录为例。路径中的 `.venv` 和命令均在本机执行。

- Python 3.11 或更高版本，使用 uv 和 `backend/uv.lock` 管理后端依赖。
- Node.js：Vite 6 要求 Node 18、20 或 22 及以上；推荐使用 Node 20 或 22。前端使用 React、Vite 和 npm。
- MySQL 8：需要一个独立教学数据库及具备建表和读写权限的账号。
- Git 和可访问依赖下载源的网络。PyTorch 当前从 `backend/pyproject.toml` 指定的 CUDA 12.6 索引安装，首次下载较大；设备兼容性需自行确认。
- 政策检索需要本地 BGE-M3 模型和 Chroma 索引；政策问答和客户经理助手需要 DeepSeek API 配置。基础页面、规则和人工流程不要求调用 DeepSeek。

### 目录说明

| 路径 | 内容 |
| --- | --- |
| `frontend/src/` | React 页面 |
| `backend/app/api/`、`services/`、`repositories/` | 接口、业务服务和 MySQL 访问 |
| `backend/app/workflows/`、`rules/` | 材料检查、风险预审和规则 |
| `backend/app/agents/`、`tools/`、`rag/`、`llm/` | 助手、工具、知识检索和模型客户端 |
| `backend/app/db/` | ORM 表和数据库连接 |
| `docs/f3-knowledge-base/corpus/` | 虚构教学政策文档 |
| `models/` | 本地模型，不提交 Git |
| `backend/.data/` | 上传原件和 Chroma 向量库，不提交 Git |
| `scripts/`、`specs/` | 初始化与验证脚本、任务卡 |

## 一、安装依赖

打开 PowerShell，进入仓库根目录，先检查版本：

    python --version
    node --version
    npm --version
    git --version

安装 uv。下面使用 Python 模块方式调用，可以避开 Windows 上 `uv` 未加入 PATH 的问题；如果电脑有多个 Python，请确保两条命令使用同一个 Python：

    python -m pip install --user uv
    python -m uv --version

进入后端目录，按锁文件安装依赖。uv 会创建或复用 `backend/.venv`：

    cd backend
    python -m uv sync --locked
    cd ..

另开或继续使用根目录终端安装前端依赖：

    cd frontend
    npm ci
    cd ..

如果 uv 使用的 Python 版本不符合要求，可以先用 `py -0p` 查看已安装版本，再使用对应 Python 执行 `-m pip` 和 `-m uv`。不需要激活虚拟环境；后续命令直接使用 `backend/.venv/Scripts/python.exe`。

## 二、创建并配置教学数据库

1. 启动本机 MySQL，使用 MySQL 客户端或 Navicat 创建一个**全新的空数据库**，例如在 MySQL 客户端中执行：

       CREATE DATABASE credit_precheck CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

2. 准备对该数据库有建表和读写权限的本地账号。请自行设置凭据，不要将密码发送到聊天、提交 Git 或写入本文档。
3. 在仓库根目录复制示例配置，然后在本机编辑：

       Copy-Item backend/.env.example backend/.env
       notepad backend/.env

   填写 `DATABASE_URL`，格式如下；替换用户名、密码、地址和库名：

       DATABASE_URL=mysql+pymysql://用户名:密码@127.0.0.1:3306/credit_precheck?charset=utf8mb4

   密码如包含 `@`、`:`、`/`、`%` 等 URL 特殊字符，需对用户名和密码分别做 URL 编码。不要编码整个连接 URL。

4. **仅对全新空库**执行以下命令，创建当前业务表、身份表和两类审计表：

       .\backend\.venv\Scripts\python.exe scripts/init_empty_database.py

   脚本发现已有表或视图时会拒绝执行，不导入账号或样例数据。MySQL 建表可能发生隐式提交；中断后可能留下部分空表，应先检查原因。该脚本不是迁移或升级工具，不要对已有库使用。

已有项目数据库不要执行空库初始化。如果是升级已有教学库，先确认备份和表结构；现有增量脚本可创建身份表、材料检查/审批表、操作日志表及助手审计表，但**不会迁移或修改已有表结构**：

    .\backend\.venv\Scripts\python.exe scripts/init_auth_tables.py
    .\backend\.venv\Scripts\python.exe scripts/init_submission_approval_tables.py
    .\backend\.venv\Scripts\python.exe scripts/init_operation_audit.py
    .\backend\.venv\Scripts\python.exe scripts/init_assistant_audit.py

### 环境变量

| 配置 | 必需性与说明 |
| --- | --- |
| `DATABASE_URL` | 后端启动必需；MySQL 连接字符串，只写入本机 `backend/.env` |
| `APP_ENV` | 可选，健康接口环境标识；默认 `development` |
| `DEEPSEEK_API_KEY` | 政策问答、授信助手及启用外部模型节点时需要；仅写入本机后端 `.env` |
| `DEEPSEEK_MODEL` | 可选，默认 `deepseek-flash`；以服务端当前可用模型为准 |
| `DEEPSEEK_TIMEOUT_SECONDS` | 可选，默认 60 秒 |
| `CREDIT_COOKIE_SECURE` | 可选，默认关闭；HTTPS 环境可设为 `1`，本地 HTTP 不要设为 `1` |
| `CREDIT_DOCUMENT_ROOT` | 可选，上传原件目录；默认 `backend/.data/documents/` |
| `BACKEND_URL` | 前端可选配置，默认 `http://127.0.0.1:8000`；需修改时放在 `frontend/.env` |

`backend/.env`、`frontend/.env`、虚拟环境、上传材料及模型目录被 Git 忽略。不要将实际凭据放在前端代码或提交记录中。

## 三、创建账号并启动

在仓库根目录交互式创建账号，按提示输入账号、显示名称、角色和至少 12 字符的密码；密码不会显示在终端。至少创建一个企业、客户经理、风控、审批人员和管理员账号，角色名称见上表。

    .\backend\.venv\Scripts\python.exe scripts/create_local_user.py

之后可以使用管理员页面创建和管理账号。空库没有默认账号和申请；已存在的开发数据不会随 Git 克隆自动出现。

**终端 1：启动后端**，从仓库根目录执行：

    cd backend
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

**终端 2：启动前端**，从仓库根目录执行：

    cd frontend
    npm run dev -- --host 127.0.0.1 --port 5173

访问：

- 前端：<http://127.0.0.1:5173/>
- 后端健康检查：<http://127.0.0.1:8000/api/health>，预期 `status` 为 `ok`。
- 后端接口文档：<http://127.0.0.1:8000/docs>；业务接口仍需登录授权。

前端开发服务将 `/api` 代理至后端。两个终端应保持运行；按 `Ctrl+C` 可分别停止。修改后端代码后，带 `--reload` 的开发服务会尝试自动重启。

## 四、配置知识库和模型（按需）

语料在 `docs/f3-knowledge-base/corpus/`，默认配置在 [backend/app/rag/settings.py](backend/app/rag/settings.py)，BGE-M3 目录是仓库根目录的 `models/bge-m3/`，Chroma 保存在 `backend/.data/chroma/`。模型与索引不随 Git 仓库分发。

需要政策检索时，可在仓库根目录下载模型；下载需要网络，命令可重复执行：

    .\backend\.venv\Scripts\hf.exe download BAAI/bge-m3 --local-dir models/bge-m3 --max-workers 1

然后在根目录检查文件、加载模型并建立索引：

    .\backend\.venv\Scripts\python.exe scripts/check_embedding.py --check-files
    .\backend\.venv\Scripts\python.exe scripts/check_embedding.py --device cpu
    .\backend\.venv\Scripts\python.exe scripts/knowledge_base.py preview
    .\backend\.venv\Scripts\python.exe scripts/knowledge_base.py ingest --device cpu
    .\backend\.venv\Scripts\python.exe scripts/knowledge_base.py status
    .\backend\.venv\Scripts\python.exe scripts/knowledge_base.py query --product equipment --text "设备采购需要哪些材料？" --device cpu

文件检查只验证关键文件存在，模型加载和索引查询仍需单独验证。无模型或索引时，政策检索及依赖它的功能不能完整使用；不应将其当作检索无结果。

需要政策问答或授信助手的模型生成时，在 `backend/.env` 配置 DeepSeek API Key，重启后端；API 调用可能产生费用。向模型发送前会对常见手机号和 18 位身份证号做教学脱敏，但不能覆盖所有敏感内容。上传原件下载仍未脱敏。

重排是可选能力，需要另行准备 `models/bge-reranker-v2-m3/` 和 `backend/reranker.json`，并在对应查询中显式启用。配置和测试见 [本地重排序说明](docs/f3-knowledge-base/management/06-本地重排序与对比.md)。

## 五、验证

从仓库根目录运行：

    python scripts/check_project.py
    .\backend\.venv\Scripts\python.exe scripts/check_auth_integration.py
    .\backend\.venv\Scripts\python.exe scripts/check_permissions_submission.py
    .\backend\.venv\Scripts\python.exe scripts/check_state_transitions.py
    .\backend\.venv\Scripts\python.exe scripts/check_review_redaction.py

前三个专项脚本使用隔离 SQLite 和虚构数据；脱敏脚本使用模拟模型传输，不调用外部服务。项目检查覆盖 Git 空白、Python 语法和前端构建，并不等同于浏览器端到端测试或生产安全验证。

如需启用项目提交前检查，可在仓库根目录执行：

    git config --local core.hooksPath .githooks

## 常见问题

- **`uv` 不是命令**：使用安装 uv 时同一个 Python 的 `python -m uv --version` 和 `python -m uv sync --locked`；检查 Python 和 pip 是否属于同一环境。
- **后端提示数据库不可用或表缺失**：确认 MySQL 已启动、`DATABASE_URL` 指向正确库、账号权限足够，并按上文区分全新空库与已有库。不要在已有库运行空库初始化。
- **无法登录**：先确认已创建账号、输入正确角色账号及密码；本机 HTTP 不要开启 `CREDIT_COOKIE_SECURE=1`。新库没有默认账号。
- **前端无法请求后端**：检查后端 8000 端口、健康接口及前端代理配置；浏览器应访问前端地址。
- **模型文件或 `sentence_transformers` 缺失**：确认模型位于仓库根目录 `models/bge-m3/`，并使用 `backend/.venv` 的 Python 执行检查；下载中断后可重试。
- **政策问答失败**：先分别检查模型文件、Chroma 索引、DeepSeek Key 和网络；不要在截图或日志中暴露 Key。

## 已知限制与参考

- 当前只支持文本型 PDF/DOCX 解析；扫描件需要人工或 OCR。解析成功不代表材料真实、充分。
- 对话会话和登录限流使用单进程内存；重启后会话丢失，多实例部署尚未适配。
- 业务日志没有生产级防篡改、保留策略和集中备份；仅供教学。
- 人工审批是教学状态和记录，不包含放款或真实机构审批规则。
- 部分历史文档记录的是旧迁移、旧目录或已删除脚本，以当前 README 和代码为准。

详细说明：[客户使用说明](docs/handover/01-客户使用说明.md)、[运维交接手册](docs/handover/02-运维交接手册.md)、[上线风险清单](docs/handover/03-上线风险清单.md)、[关键操作日志](docs/architecture/33-关键操作日志.md)、[人工复核与脱敏方案](docs/architecture/34-人工复核与脱敏方案.md)、[知识库说明](docs/f3-knowledge-base/README.md)、[接口契约](docs/data-contract.md)、[代码规范](docs/coding-standards.md)、[数据库结构](backend/app/db/README.md)。
