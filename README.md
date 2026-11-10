# 小微企业授信智能预审系统

面向小微企业授信场景的教学原型：企业在线提交申请与材料，客户经理认领跟进，风控专员运行 AI 预审 Workflow 并逐项人工复核，最终进入「待审批」或「待企业补充材料」。

> 本项目只使用虚构教学数据。AI 仅输出待人工核验的线索，不生成授信结论，也不执行审批或放款。系统未做生产级安全加固，请勿接入真实客户数据或暴露到不可信网络。

## 业务闭环

```
待企业补充材料 →（初检通过后重新提交）→ 待风控复核 →（开始复核）→ 风控复核中
                                                                      ├→（完成复核）→ 待审批
                                                                      └→（要求补件）→ 待企业补充材料
```

| 角色 | 登录标识 | 可访问范围 |
| --- | --- | --- |
| 企业客户 | `enterprise` | 自己的申请；上传材料；初检后重新提交 |
| 客户经理 | `customer_manager` | 系统自动分配的申请；只读审批进度；政策问答与授信助手 |
| 风控专员 | `risk_reviewer` | 待风控复核、风控复核中、待审批，以及已有复核记录的待企业补充材料申请；运行风险预审、提交复核 |
| 审批人员 | `approver` | 查看进入审批阶段的申请、材料和复核记录；记录人工审批结果 |
| 管理员 | `admin` | 创建和管理账号、查看助手工具审计 |

审批决定由审批人员手动记录，AI 不作审批决定。

## 功能一览

| 模块 | 使用角色 | 说明 |
| --- | --- | --- |
| 登录 / 退出 | 全部 | 账号密码登录，服务端 Cookie 会话，8 小时过期 |
| 企业申请 | 企业 | 填写虚构企业、产品、金额与用途，提交后进入待企业补充材料 |
| 材料上传与补件 | 企业 | 上传 PDF/DOCX（单文件 10MB 内），自动解析正文；仅「待企业补充材料」状态可上传 |
| 材料初检并重新提交 | 企业 | 规则初检无缺失、异常或未确认项时提交至待风控复核；证据充分性仍需人工判断 |
| 自动分配 | 系统 | 正式提交后按未结束申请数自动分配启用的客户经理 |
| 工作台 / 看板 | 风控、客户经理 | 按权限过滤的申请列表与状态汇总，不给风险评级 |
| 申请详情 | 风控、客户经理 | 企业、材料、历次报告、进度与复核记录 |
| AI 预审与报告 | 风控、客户经理 | 风控运行后保存报告；客户经理只读 |
| 人工复核 | 风控 | 逐项确认或修正关注项，完成复核或要求补件 |
| 政策问答 | 企业、客户经理、风控、审批 | 多轮 SSE 对话，回答附条款引文 |
| 授信助手 | 客户经理 | 只读工具编排，返回结构化分析结果，不修改业务状态 |
| 账号管理 / 审计 | 管理员 | 创建、停用账号、调整角色，查询助手工具审计 |

页面入口（URL 参数）：`?view=dashboard`（看板）、`?view=policy`（政策问答）、`?view=assistant`（授信助手）、`?view=claims`（待认领），以及 `?application=APP-FICT-001&view=detail|materials|report|review|assistant`。

## 技术栈

| 部分 | 选择 |
| --- | --- |
| 前端 | React 19 + Vite 6 |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy |
| 业务数据 | MySQL（启动时校验连接与表是否存在） |
| 向量检索 | Chroma 本地持久化 + 本地 BGE-M3 |
| 可选重排 | 本地 bge-reranker-v2-m3 |
| 模型服务 | DeepSeek（政策问答、风险预审可选节点、授信助手工具选择） |
| 后端依赖管理 | uv（`backend/pyproject.toml` 与 `uv.lock`） |

## 目录结构

| 目录 | 用途 |
| --- | --- |
| `frontend/src/` | React 页面、组件、取数与样式 |
| `backend/app/api/` | 路由与请求级权限校验 |
| `backend/app/services/` | 共享业务入口（预审、复核、报告、提交、文档） |
| `backend/app/workflows/` | 材料完整性与风险预审 Workflow |
| `backend/app/rules/` | 材料清单、数值核对、工作流定义 |
| `backend/app/repositories/` | MySQL 数据访问与事务 |
| `backend/app/schemas/` | Pydantic 契约 |
| `backend/app/rag/` | 语料、Chroma 向量、检索与重排 |
| `backend/app/agents/` | 政策问答、授信助手、会话记忆 |
| `backend/app/tools/` | 只读工具注册与执行、审计前置 |
| `backend/app/db/` | 连接、ORM 模型、表结构说明 |
| `backend/app/llm/` | DeepSeek 同步/流式客户端与 JSON 校验 |
| `fixtures/fictional_applications/` | 10 笔虚构申请与配套 DOCX 样例 |
| `docs/f3-knowledge-base/` | 五份教学政策正文及知识库管理说明 |
| `evals/runners/` | 检索、重排、问答效果评测 |
| `scripts/` | 初始化、校验、评测与兼容 CLI |
| `specs/` | 各轮业务任务卡与验收要求 |

## 本地启动

### 前置条件

- MySQL 8 已运行，`backend/.env` 中的 `DATABASE_URL` 指向教学库（不要指向生产库）。
- 业务表已存在。仓库当前**不包含**业务表建表/迁移脚本，新环境请沿用既有教学库，或依据 [数据库说明](backend/app/db/README.md) 中的表结构准备。
- 前端 `frontend/.env` 中的 `BACKEND_URL` 指向后端地址（默认 `http://127.0.0.1:8000`）。
- 需要 DeepSeek 能力时，在 `backend/.env` 配置 `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL` 与超时；密钥不要写入前端或仓库。

### 启动步骤

```powershell
# 1. 创建缺失的身份表（幂等，不改动业务数据）
.\backend\.venv\Scripts\python.exe scripts/init_auth_tables.py

# 创建材料检查与审批记录表（幂等）
.\backend\.venv\Scripts\python.exe scripts/init_submission_approval_tables.py

# 创建关键操作日志表（幂等）
.\backend\.venv\Scripts\python.exe scripts/init_operation_audit.py

# 2. 交互式创建教学账号，可为 enterprise / customer_manager / risk_reviewer / approver / admin
.\backend\.venv\Scripts\python.exe scripts/create_local_user.py
# 使用客户经理助手前，再创建审计表：
.\backend\.venv\Scripts\python.exe scripts/init_assistant_audit.py

# 3. 启动后端（在 backend 目录）
cd backend
.\.venv\Scripts\python.exe -m uv run --env-file .env uvicorn app.main:app --reload

# 4. 启动前端（另开终端）
cd frontend
npm install
npm run dev
```

后端健康检查：`http://127.0.0.1:8000/api/health`。前端开发服务通过 Vite 代理转发 `/api`，直接打开终端输出的本地地址即可登录。

首次创建虚拟环境：在 `backend` 目录执行 `python -m venv .venv`，再执行 `.\.venv\Scripts\python.exe -m pip install uv`，最后用 `python -m uv sync` 安装依赖。`.venv`、`node_modules`、`backend/.data` 与 `models/` 均被 Git 忽略。

如需为所有已有账号重设密码，在项目根目录运行 `.\backend\.venv\Scripts\python.exe scripts/reset_all_user_passwords.py`，根据提示在本机终端为每个账号输入并确认新密码。所有输入完成后才在一个事务中更新密码并撤销旧登录会话，账号 ID、角色、启停状态及申请归属不变。

## 账号与权限

- 密码使用 scrypt 加盐哈希存储，登录令牌只保存 SHA-256 摘要；Cookie 为 HttpOnly、SameSite=Strict，HTTPS 部署需设置 `CREDIT_COOKIE_SECURE=1`。
- 同一 IP + 账号 5 分钟内失败 5 次会被限流；该计数保存在单进程内存，重启即清空，也不适用于多进程部署。
- 每个业务接口都在服务端重新校验角色与申请归属，不信任请求头或前端声明的身份：
  - 企业：按 `application_owners` 表判断归属；
  - 客户经理：按申请中的 `account_manager_id` 判断；
  - 风控：按申请状态与是否存在复核记录判断。
- 有未结束申请的客户经理不能直接停用或更换角色；已有申请归属的企业账号不能直接更换角色。
- 不存在的申请与无权限申请统一返回 404，避免泄露编号是否存在。

## AI 能力与边界

**材料完整性 Workflow**：按输入校验、材料版本快照、类型匹配、可选名称模型、可读性、必交与组合判断、字段检查、汇总执行；输出缺失、异常、待确认项与节点轨迹，不修改申请状态。

**风险预审 Workflow**：读取同一申请与材料快照，先跑完整性规则，再按教学政策与可比较的材料事实形成线索，输出 `risk_items`、证据、`missing_info`、待人工复核项与节点轨迹。模型节点默认关闭，需显式启用；检索或模型失败时保留真实状态并标为降级，不伪装成「无风险」。

**政策问答 Agent**：企业客户、客户经理、风控和审批人员可用。默认 BGE-M3 + Chroma 召回 8 条、选 6 条上下文，可选重排；多轮 SSE 会话绑定登录用户，回答限定在五份教学政策内，并附条款引文。

**客户经理授信助手**：仅客户经理可用。模型只能选择只读工具（查申请、列材料、读取已有材料检查结果、政策检索），不能运行两条 Workflow；执行前先写审计，审计失败即拒绝。

企业先保存草稿、上传材料并执行检查；正式提交时服务端重新检查并核对材料版本。检查结果保存时间、材料版本及声明，材料或声明变化后标为过期。系统按启用客户经理的未结束申请数分配；无人可分配时保留待分配，在客户经理登录时重试。客户经理的补件建议不改变状态，正式退回由风控复核执行。

企业提交申请时可声明与产品有关的条件；材料检查和风险预审自动复用该申请已保存的声明。文档中带明确字段标签的内容可以作为候选，并附材料版本、位置和原文；候选与声明冲突或信息未知时需要确认，不能直接推定材料齐全。旧申请没有这些声明时仍按未知处理。企业补件成功后提交的明确声明会保存到申请。

授信助手只读取企业已保存的检查结果；没有检查结果或结果已过期时提示企业重新检查，不根据对话答案重新运行 Workflow。材料候选与已保存声明冲突时应由人工核实，必要时更新申请资料。

共同边界：

- 只读运行，不修改申请状态、报告或复核记录（风控主动运行风险预审并保存报告除外）。
- 引用校验只能保证「引文存在于该材料位置」，不代表语义正确；证据不足、解析失败、无报告都不能展示为无风险。
- 会话保存在单进程内存，30 分钟过期，重启丢失。

## 知识库与模型（可选）

语料为 `docs/f3-knowledge-base/corpus/` 下五份教学文档，按完整条款切分为 43 个知识块；参数在 [rag/settings.py](backend/app/rag/settings.py)，向量库在 `backend/.data/chroma/`。本地 BGE-M3 位于 `models/bge-m3/`（不提交 Git）。

```powershell
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py preview
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py ingest --device cpu
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py status
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py query --product equipment --text "没有签订设备采购合同，可以用报价单吗？"
```

- 首次入库前可用 `scripts/check_embedding.py --check-files` 检查模型文件，再用 `--device cpu` 验证向量输出。
- 重排为可选项：需本地创建 `backend/reranker.json` 并准备 `models/bge-reranker-v2-m3/`，仓库不包含该配置文件；未配置时不要使用 `--rerank`。
- Top-K、重排对比与政策问答评测分别见 [Top-K 测试](docs/f3-knowledge-base/management/05-Top-K测试说明.md)、[本地重排序](docs/f3-knowledge-base/management/06-本地重排序与对比.md)、[DeepSeek 政策问答](docs/f3-knowledge-base/management/07-DeepSeek政策问答.md)。评测脚本可能调用付费模型。

## 数据与存储

- **MySQL**：`enterprises`、`applications`、`materials`、`reports`、`status_events`、`review_actions`、`knowledge_items`，以及身份表 `users`、`login_sessions`、`application_owners` 和审计表 `assistant_tool_audit`。表关系见 [数据库说明](backend/app/db/README.md)。
- **原件**：上传文件保存在 `backend/.data/documents/`，数据库只存元数据与解析结果；同名最新版本内容相同不新增版本。
- **向量**：Chroma 独立保存，与业务表无外键关系。
- **当前教学数据**：`APP-FICT-001` ~ `APP-FICT-010` 共 10 笔虚构申请、57 条上传材料记录，初始状态均为待风控复核；账号需按上文自行创建。可用 `scripts/create_fictional_applications.py` 重建（不覆盖已有申请），用 `scripts/verify_fictional_applications.py` 只读验证两条 Workflow。
- **历史遗留**：`backend/.data/reviews.sqlite3` 与 `backend/.data/*backups/` 是旧版 SQLite 复核记录与迁移备份，运行时已不再读取，保留仅供参考。

## 校验与检查

提交前在仓库根目录运行：

```powershell
python scripts/check_project.py
```

该脚本依次执行 Git 空白检查、Python 语法编译（`backend/app`、`scripts`、`evals`、`.codex/hooks`）与前端生产构建；任一步失败即中止。仓库自带 Git hook：首次克隆后执行 `git config --local core.hooksPath .githooks` 启用，之后每次 `git commit` 自动运行同一脚本。

专项验证脚本：

| 脚本 | 用途 | 依赖 |
| --- | --- | --- |
| `check_auth_foundation.py` | 登录、申请归属、对话隔离 | 内存 SQLite，不连开发库 |
| `check_auth_integration.py` | 多用户业务路由边界 | 内存 SQLite + 可写临时目录 |
| `check_credit_assistant_workflows.py` | 助手工具与越权分支 | 内存 SQLite + 假模型 |
| `check_credit_assistant_mysql.py` | 助手真实 MySQL 隔离 | 需临时建库权限 |
| `verify_fictional_applications.py` | 10 笔样例的双 Workflow 回归 | 读取真实教学库，不调用模型 |
| `check_embedding.py` | 本地 BGE-M3 文件与向量输出 | 本地模型目录 |
| `evaluate_*.py` | 检索、重排、问答效果评测 | 部分会调用 DeepSeek |

当前**没有自动化单元测试目录**，上述脚本是手工回归工具；未运行的检查不应写成通过。

## 已知边界

- 正式授信审批、放款与审批结论录入未实现。
- 登录限流与两类对话会话均在单进程内存中，不支持多实例部署。
- 业务表无随仓库发布的建表/迁移脚本，`schema_migrations` 当前为空。
- `docs/` 下部分历史报告（第 20 轮 MySQL 迁移、第 25 轮 RAG 恢复）保留当时的命令与结论，其中部分脚本已删除，以本 README 为准。
- 材料解析只支持文字型 PDF/DOCX；扫描件需人工或 OCR，正文可解析不代表材料真实或充分。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| [归档说明](docs/README.md) | 文档目录与范围 |
| [核心数据对象与接口](docs/data-contract.md) | 接口契约、对象关系与状态说明 |
| [后端架构](docs/architecture/README.md) | 分层职责与历史重构记录 |
| [数据库说明](backend/app/db/README.md) | 表结构、索引与存储取舍 |
| [代码规范](docs/coding-standards.md) | 注释、提交与检查约定 |
| [知识库说明](docs/f3-knowledge-base/README.md) | 五份教学文件与语料边界 |
| [材料完整性 Workflow](docs/f3-knowledge-base/management/09-材料完整性Workflow.md) | 检查节点与失败分支 |
| [AI 风险预审 Workflow](docs/f3-knowledge-base/management/10-AI风险预审Workflow.md) | 风险线索、证据与降级状态 |
| [多轮政策对话](docs/f3-knowledge-base/management/08-多轮政策对话与流式验收.md) | SSE 事件与引用契约 |
| [授信助手验证](docs/architecture/23-客户经理授信助手验证.md) | 工具、审计与隔离验证记录 |
| [F3 PBL 报告](docs/delivery/) | 项目总结与验证结论 |
| [任务卡](specs/TEMPLATE.md) | 新业务任务的编写模板 |

本目录承接上级目录的《06-F2-MVP范围表.md》与《06-F2交接清单.md》；角色与状态约定以其为准。
