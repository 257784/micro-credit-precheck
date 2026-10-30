# 后端架构与重构验收

第20轮更新：API、Workflow和工具的业务存储已切换MySQL；db/models.py是实际ORM，db/session.py管理连接，repositories/sql_business.py和sql_documents.py执行查询与事务。旧JSON/SQLite仅用于迁移和隔离测试。详细表关系、迁移与命令见[数据库说明](../../backend/app/db/README.md)，以下保留第18、19轮历史记录。

后续清理已完成：app顶层旧兼容模块已删除，所有仓库内Python引用已改为新包路径。下文旧兼容描述仅是第18轮的迁移记录，当前以本段为准。新增`app/db/`集中SQLite连接与实际DDL，见 [数据库结构说明](../../backend/app/db/README.md)。没有迁移或删除本机数据。

本轮采用模块化单体：一个FastAPI应用、一个后端环境，按职责拆包。没有更换数据库、模型、提示词或业务政策。

## 当前目录与职责

| 路径 | 职责 |
| --- | --- |
| `backend/app/main.py` | 创建FastAPI、注册路由，兼容原有函数导入 |
| `backend/app/api/` | 申请、文件、预审、复核和对话路由；dependencies装配实例 |
| `backend/app/schemas/` | 原有Pydantic数据和请求响应结构，不是ORM模型 |
| `backend/app/services/` | 共享预审入口、文件业务入口、复核服务、单轮政策问答 |
| `backend/app/repositories/` | 种子数据访问、上传原件记录和SQLite复核记录；保留原事务及幂等行为 |
| `backend/app/documents/parsers.py` | PDF/DOCX正文和字段提取；可单独测试 |
| `backend/app/workflows/` | 材料/风险流程、输入适配和名称辅助 |
| `backend/app/rules/` | 清单配置校验、数值核对、实际文件字段规则 |
| `backend/app/llm/` | DeepSeek同步/流式客户端、流式JSON解析 |
| `backend/app/rag/` | 语料、向量存储、检索和重排 |
| `backend/app/agents/` | 多轮政策助手、记忆、政策范围识别 |
| `backend/app/tools/` | 明确输入契约的只读工具注册表 |
| `backend/app/core/config.py` | 稳定的项目、数据和配置路径 |
| `backend/app/observability/` | 安全运行元数据日志，复用现有Workflow节点轨迹 |
| `evals/runners/` | 检索、重排、问答和真实模型效果评测 |
| `tests/`、`frontend/tests/` | 默认不调用付费服务的自动回归 |
| `scripts/` | 开发、数据生成、联调及兼容CLI入口 |

依赖方向：API或Agent工具 → Service → Workflow/规则 → Repository、LLM、RAG。解析能力不依赖HTTP；日志和测试横跨各层。路由把错误映射成原有HTTP状态与detail，未引入破坏兼容的错误包装。

## Agent如何复用能力

```python
from app.tools.registry import ReadOnlyTools

# application_service由应用装配层注入；须限定调用者可访问的申请。
tools = ReadOnlyTools(application_service)
result = tools.invoke("check_materials", {"application_id": "APP-DEMO-003"})
```

注册能力只有check_materials和run_risk_precheck，禁止任意URL、SQL和审批动作。默认不启用模型，显式options.use_model才触发模型流程。注册表不替代身份认证，后续接入Agent时仍须提供经过授权的申请服务。

当前政策对话Agent的工具选择行为保持原样；本轮提供共享工具入口，并未擅自为它增加调用预审或修改状态的自主行为。以后独立部署Agent时，可在工具适配器中换成HTTP客户端，业务实现仍由Service承接。

## 兼容与迁移约束

- app顶层旧模块现在是兼容转发文件；真正实现位于新包。`module-map.json`列出一一对应关系。没有两份并行维护的业务代码。
- 新代码使用新包路径；旧脚本与测试导入仍可运行。测试替换服务时使用`app.api.dependencies.reviews`，不再替换main的只读导出别名。
- 评测旧命令继续有效，如`python scripts/evaluate_retrieval.py --validate-only`，实现位于evals/runners。
- 配置暂保留backend/workflows、knowledge-base.json、reranker.json等已使用路径；语料与golden数据不迁移，以保持已有引用稳定。
- 当前持久化是SQLite/JSON，不为满足目录名制造空ORM模型。数据库连接与事务仍在Repository中，Service协调原有业务动作；不借目录整理改写事务策略。
- tests仍保留原测试发现布局，避免移动后漏跑；统一检查已新增evals的语法检查。
- 不读取、移动或修改.env、模型目录和现有本机数据库。路径专门有回归断言。

## 验收结果

基线122条Python、15条JavaScript及构建通过。重构后127条Python、15条JavaScript及构建通过；新增5项架构检查：

1. OpenAPI与重构前快照完全一致（含URL、方法、参数及响应schema）。
2. 旧模块和新包导入指向同一实现对象。
3. 服务、规则、流程、存储和工具不依赖FastAPI路由。
4. 只读工具可运行真实材料规则，未知审批工具被拒绝。
5. 种子、数据库和语料路径保持不变。

三组真实文件HTTP联调结果不变：NORMAL缺项0/异常0、风险completed；CONTENT缺项0/异常5、风险insufficient_evidence；AMOUNT缺项0/异常0，保留金额差异线索。16题检索标签和重排配置校验通过，真实模型CLI帮助入口正常。本轮没有再次付费调用模型，也未声称重新测量模型效果。

运行：`python scripts/check_project.py`；`python scripts/verify_document_workflows.py`。接口基线为`openapi-before.json`。

现有PDF字体映射警告、上轮uv依赖锁未更新及DOCX版式验证限制并未通过此次目录重构解决，继续参考上轮测试报告。
