# 小微企业授信智能预审系统 F2

## 企业申请与演示角色

界面参考 F1 原型提供侧边导航：企业客户填写并提交教学申请；风控专员查看工作台、申请与报告并执行现有人工复核；客户经理查看申请、报告和只读审批进度，不能提交复核或审批决定。企业申请使用虚构信息，提交时将企业、申请和进度事件写入 MySQL，初始状态为“待企业补充材料”；材料上传与重新提交申请尚未在企业页面实现，客户经理暂为待分配。审批页面仅查看进度，不提供审批通过。

角色切换与请求头只用于教学演示，可以伪造；现有其他业务读取接口尚未统一授权，也没有企业归属和分派过滤，不能用于真实身份、数据隔离或生产权限控制。上线前必须建立服务端认证、接口授权、数据归属及审计。

RAG更新：知识库参数和教学产品目录现由`backend/app/rag/settings.py`与`backend/app/agents/product_catalog.py`提供，不再需要原`knowledge-base.json`或`policy-products.json`。旧索引签名及指纹匹配，当前Agent环境的DLL限制和实时检索复验方式见[RAG恢复报告](docs/architecture/25-RAG配置恢复与检索验证.md)。

## 客户经理授信助手（教学原型）

助手最终返回版本化结构化JSON并在页面分区展示；材料原文标注为不可信内容。后端依据同申请文件记录核对材料编号、版本、位置及原文，不可核验项降级为待核对；政策检索来源与规则引用分开。最终结果不构成授信决定。

主页点击“客户经理授信助手”，或在申请详情点击“使用助手分析本申请”。服务端固定教学主体，仅允许访问APP-FICT-001至010；前端演示角色切换不构成身份认证。助手只调用查询与预审工具，不执行审批或状态修改。

审计表首次安装在项目根目录执行 `.\backend\.venv\Scripts\python.exe scripts/init_assistant_audit.py`；可重复执行，不清空业务表。工具执行前必须写审计，失败时拒绝执行。演示管理员只能由服务器进程环境 `CREDIT_DEMO_ADMIN=1` 开启，然后可通过 `GET /api/credit-assistant/audit` 按actor、application_id、run_id、since筛选，默认客户经理无法查看。该开关对整个演示服务生效，**不是生产身份认证**。

助手工具选择使用DeepSeek非流式请求，页面流式显示进度，最终仅展示由工具结果整理的内容。政策检索缺失配置时明确不可用。会话保存在单进程内存，30分钟过期，重启丢失；终止操作后已经开始的只读工具可能继续结束。

隔离验证：`python scripts/check_credit_assistant.py`；`python scripts/check_credit_assistant_workflows.py`。真实MySQL隔离验证为 `python scripts/check_credit_assistant_mysql.py`，需要项目虚拟环境和临时建库权限。每项结果及环境限制见[助手验证报告](docs/architecture/23-客户经理授信助手验证.md)。

2026-10-29清理：按用户要求，MySQL业务表已清空、旧迁移脚本及自动测试目录已删除。保留表结构及清理前备份；启动后申请列表为空。下文涉及已删除的迁移、测试和材料样例命令属于历史记录。当前`scripts/check_project.py`只执行Git空白、Python语法和前端构建检查，不再运行单元测试。

当前存储已在第20轮统一为MySQL：企业、申请、材料记录、解析结果、报告和复核动作均通过Repository读写数据库，原件和Chroma保持独立存储。下文F2阶段简介中的SQLite属于历史实现。迁移记录与当前环境限制见[数据库迁移报告](docs/architecture/database-migration-report.md)。

本目录承接上级目录的《06-F2-MVP范围表.md》和《06-F2交接清单.md》。F2 使用虚构教学数据，目标是跑通申请列表、详情、材料、Mock AI 预审报告及人工风控复核的单笔闭环。完成复核后进入“待审批”；要求补件后进入“待企业补充材料”。正式授信审批不在本阶段范围内。

## 技术栈

| 部分 | 选择 |
| --- | --- |
| 前端 | React + Vite |
| 后端 | Python + FastAPI |
| 数据库 | MySQL（统一业务数据）；Chroma（政策向量） |
| 后端依赖与环境 | uv |

## 目录

后端已按API、Service、Repository、Workflow、RAG和Agent拆包；app顶层旧模块已删除，旧CLI命令仍可使用。目录职责见 [后端架构说明](docs/architecture/README.md)，数据库文件、表关系和索引见 [数据库结构说明](backend/app/db/README.md)。

| 目录 | 用途 |
| --- | --- |
| `frontend/` | React 页面与前端资源 |
| `backend/` | FastAPI 接口及后端配置 |
| `mock_data/` | 虚构申请、材料、知识与报告样例 |
| `docs/` | F2 设计与开发文档 |
| `tests/` | 业务流程与接口测试 |

当前已提供虚构申请、企业、材料和 AI 报告样例。前端可从“风险看板”或申请列表进入详情，再查看材料清单、AI 预审报告和人工复核；`?view=dashboard` 可直接打开看板，`?application=APP-DEMO-001&view=materials`、`view=report` 或 `view=review` 可直接打开指定申请页面。看板只汇总申请状态及最新报告处理状态，不给出风险评级或授信决定。报告以结构化字段展示材料完整性、待核验提示、政策/教学规则匹配和预审建议，并保留材料及知识来源；它不生成最终授信决定。风控专员演示身份可以开始复核、逐项确认或修正关注项、填写意见，完成复核或要求补件；客户经理演示身份只读。复核记录保存在本地 SQLite，重启后可回看。数据结构与存储取舍见 [核心数据对象与复核接口](docs/data-contract.md)。生产身份认证、MySQL 和真实材料预览将在后续步骤实现。

代码风格、注释约定和提交前检查见 [F2 代码规范](docs/coding-standards.md)。

## 提交前自动测试

首次克隆仓库后，在 F2 根目录运行 `git config --local core.hooksPath .githooks` 启用仓库内的 hook。该配置只对本机当前仓库生效；可用 `git config --local --get core.hooksPath` 确认。

之后每次执行 `git commit`，`.githooks/pre-commit` 会调用共用的 `scripts/check_project.py`；任一步失败都会停止提交，修复后重新提交。手动运行 `python scripts/check_project.py` 即可执行相同检查。Git hook 在提交时执行；如需每次保存文件后运行测试，需要单独配置编辑器任务或文件监视器。

## Codex 写入前后检查

F2 项目的 `.codex/hooks.json` 配置了 Codex `PreToolUse` 和 `PostToolUse`。请将 **F2 目录作为 Codex 项目打开**，在 Codex 中用 `/hooks` 审查并信任项目 hook。它们与上面的 Git `pre-commit` 相互独立。

写入前，hook 检查 `apply_patch` 和常见命令行写入：如果新增内容出现密码/令牌赋值，或识别出的目标路径被 `.gitignore` 忽略，则拒绝该操作。写入代码后，Codex 也调用 `scripts/check_project.py` 运行空白检查、Python 语法检查、Python/JavaScript 单元测试及前端构建；失败结果返回给 Agent，请先修复再继续。当前的“lint”是空白与语法基础检查，项目尚未安装 Ruff 或 ESLint。

这些 hook 只覆盖 Codex 支持的工具事件及脚本能识别的写法；复杂脚本、其他程序写入和用户手工修改仍需 Git 提交前检查与人工审查。`PostToolUse` 也不能撤销已经完成的写入。

## 本地启动

真实文件材料位于 `mock_data/document_cases/`。选择APP-DOC-NORMAL、APP-DOC-CONTENT或APP-DOC-AMOUNT，在材料页上传原件。测试命令、结果和环境限制见 [真实文件双Workflow测试报告](docs/f3-knowledge-base/management/11-真实文件双Workflow验收.md)。

首次创建后端虚拟环境（在 `backend` 目录）：`python -m venv .venv`。PowerShell 中可用 `.\.venv\Scripts\Activate.ps1` 激活；如果执行策略阻止激活，可直接运行 `.\.venv\Scripts\python.exe`。`.venv` 已被 Git 忽略。安装 uv 后运行 `python -m uv sync`，由 uv 管理这个环境及 `pyproject.toml` 中的依赖。使用 `python -m uv` 不要求将用户级 Scripts 目录加入 PATH。

前端：进入 `frontend`，将 `.env.example` 复制为 `.env`，运行 `npm install` 和 `npm run dev`，打开终端输出的本地地址。

后端：安装 uv 后进入 `backend`，将 `.env.example` 复制为 `.env`，运行 `python -m uv sync` 和 `python -m uv run --env-file .env uvicorn app.main:app --reload`。可访问 `http://127.0.0.1:8000/api/health` 检查服务。

两个服务需在不同终端启动，前端开发服务通过 `BACKEND_URL` 转发 `/api` 请求。后端现通过backend/.env的DATABASE_URL连接MySQL；缺配置或尚未迁移时启动失败。先按[数据库说明](backend/app/db/README.md)预检和迁移，再启动后端。切换演示角色不代表真实身份认证。

迁移后修改mock_data/seed.json不会改变线上业务数据；运行时不再读取旧JSON/SQLite。保留旧源和迁移备份，后续数据修改通过Repository或版本迁移完成。

首次安装依赖需要能够访问 Python 与 npm 包源。若当前机器无法联网，可先用已有的 Python 环境执行 `python -m uvicorn app.main:app --reload` 检查后端，但正式的后端依赖管理仍使用 uv。

## 本地 embedding 检查

BGE-M3 文件位于项目根目录 `models/bge-m3/`，该目录不提交 Git。依赖使用 `backend/.venv`；全局或 Anaconda 的 Python 不一定安装了相同依赖。在项目根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe scripts/check_embedding.py --check-files
.\backend\.venv\Scripts\python.exe scripts/check_embedding.py --device cpu
```

第一条只检查关键文件存在且非空，不验证下载哈希；第二条从本地加载模型并检查向量输出。文件未齐全时会列出缺项，不自动下载。CPU 检查通过且 PyTorch 能识别显卡后，可将参数改为 `--device cuda`。脚本路径是根目录的 `scripts/check_embedding.py`，模型目录不依赖终端当前路径。

## 本地 Chroma 知识库

向量存储使用 Chroma 本地持久化模式，无需 Docker 或独立服务。配置在 `backend/knowledge-base.json`，数据库在 `backend/.data/chroma/`。操作说明及实际验证范围见 [Chroma 入库与检索](docs/f3-knowledge-base/management/04-Chroma入库与检索.md)。从项目根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py preview
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py ingest --device cpu
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py status
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py query --product equipment --text "没有签订设备采购合同，可以用报价单吗？"
```

只读取 corpus 白名单的五份教学文档，按完整条款形成 43 个块；使用本地 BGE-M3 的 1024 维归一化向量和余弦距离。重复入库复用同一快照，正文或模型改变后生成新快照，成功后切换。检索结果仅为教学候选条款，不是授信决定。

## Top-K 小规模测试

执行 `.\backend\.venv\Scripts\python.exe scripts/evaluate_retrieval.py --device cpu`，对 16 道开发题比较 K=1、3、5、8、10、15、20 的召回、全依据覆盖和上下文大小，结果保存到 `backend/.data/knowledge-base/top-k-evaluation/`。仅检查标签可加 `--validate-only`。实际测得符合预设目标后再决定 K，不自动修改默认值。指标及限制见 [Top-K 测试说明](docs/f3-knowledge-base/management/05-Top-K测试说明.md)。

## 本地 Reranker

默认向量召回数现为 8。重排配置独立放在 `backend/reranker.json`，使用已下载的 `models/bge-reranker-v2-m3/`，无需重新入库：

```powershell
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py query --product equipment --text "没有采购合同，可以用报价单吗？" --rerank --context-k 5
.\backend\.venv\Scripts\python.exe scripts/evaluate_reranker.py --device cpu --reranker-device cpu
```

第一条对 8 条候选重排并选取前 5 条；`reranking` 同时保留原序和完整重排结果。缺模型或评分失败时，明确返回 `fallback` 并使用原排名。第二条逐题对比原序和重排的 Top-3/5，报告在 `backend/.data/knowledge-base/reranker-evaluation/`；仅校验可加 `--validate-only`。字段含义、失败状态与实际验证记录见 [本地重排序与对比](docs/f3-knowledge-base/management/06-本地重排序与对比.md)。

## DeepSeek 政策问答

AI 预审报告页提供只读风险预审入口，默认规则检查，可选择启用 DeepSeek；详见 [风险预审说明](docs/f3-knowledge-base/management/10-AI风险预审Workflow.md)。

材料页现提供“材料完整性教学检查”，默认纯规则，可选名称模型辅助；输出缺项、解析异常、待确认和节点轨迹，不改变申请状态。项目根目录可执行 `python scripts/check_materials.py --fixture mock_data/material_workflow/empty.json` 或将文件名改为 `normal.json`、`failed_and_missing.json`。详见 [材料完整性Workflow](docs/f3-knowledge-base/management/09-材料完整性Workflow.md)。

当前页面已升级为多轮对话，不再要求先选择产品：描述用途，助手识别范围或自然语言追问，再逐条展示核对引文的回答。旧单轮API及下述单轮评测仍兼容。先在 `backend` 执行 `python -m uv sync` 同步新增直接依赖，再用原环境命令启动；临时会话在后端重启或空闲30分钟后失效。多轮入口、停止/恢复和真实API验收见 [多轮政策对话与流式验收](docs/f3-knowledge-base/management/08-多轮政策对话与流式验收.md)。

在本机 `backend/.env` 中填写 `DEEPSEEK_API_KEY`，参考 `.env.example` 的 `DEEPSEEK_MODEL` 和超时设置；不要覆盖已有环境配置或放入前端。后端通过 `python -m uv run --env-file .env uvicorn app.main:app --reload` 加载环境并启动后，前端点击“政策问答”（`?view=policy`）。默认纯向量召回8条、上下文6条，重排序可选，回答附原文和文号/条号；不能执行审批。

先单题验证，再从项目根目录运行 `python -m uv run --project backend --env-file backend/.env python scripts/evaluate_policy_qa.py --run --limit 16`，会调用 DeepSeek，可能产生费用。输出位于 `backend/.data/knowledge-base/policy-qa-evaluation/`；人工核对正确性、条件和引用。完整步骤及失败处理见 [DeepSeek 政策问答](docs/f3-knowledge-base/management/07-DeepSeek政策问答.md)。
