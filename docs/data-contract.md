# F2 核心数据对象与复核接口

客户经理助手第26轮：`POST /api/credit-assistant/conversations/{cid}/messages/stream`在进度事件之后发送`result`事件，包含`result`对象：schema_version、run_id、application_id、status、summary、facts、material_issues、risk_items、policy_sources、missing_info、need_human_review及limitations。字段由`backend/app/schemas/assistant.py`定义并拒绝额外字段。证据需属于同一申请，且材料ID、版本、位置及引文通过服务端记录核验；未通过的线索移除并提示补充信息。规则政策引用和本轮检索来源分别展示；本次结果不修改申请或复核。`answer`事件仅为兼容摘要，`done.status=partial`表示依赖未完成，不能解读为完整成功。

第20轮存储更新：企业、申请、材料元数据/解析结果、报告和复核动作统一由MySQL提供，连接来自backend/.env的DATABASE_URL。原文件仍存backend/.data/documents；Chroma独立维护向量。JSON/SQLite已退出运行时，修改seed不影响已迁移库。接口字段和路径保持兼容，详见[实际表结构](../backend/app/db/README.md)。下文关于JSON/SQLite的描述仅保留为F2阶段历史取舍，不代表当前存储。

## 实际教学文件接口

`POST /api/applications/{id}/documents?category=M-C01&filename=申请表.docx` 接收原始文件字节，限制10MB，允许PDF/DOCX。`GET`同路径列出记录，`GET /api/applications/{id}/documents/{document_id}` 下载本申请原件。未知申请/文件404，格式及输入错误422，过大413；不可解析文件保存failed记录而不伪造成功。

本地 `backend/.data/documents/` 保存原件及SQLite元数据，包含id、application_id、category、version、sha256、parsed（status/sections/fields/parser_version）。同类别最新版相同内容不新增版本；恢复历史内容会建立新版本。实际解析来源为parsed，旧教学来源仍为parsed_mock，扫描件无文本需人工/OCR。

两个Workflow读取同一申请实际上传解析记录；规则风险线索附材料版本和段落位置。上传不自动更新申请审批状态或历史复核记录。仅支持当前明确字段模板，正文可解析不等于真实性或充分性已确认。

## F3 材料完整性教学Workflow

`POST /api/applications/{application_id}/materials/check` 从服务器读取该申请材料；请求可含 `use_model` 和带 `manual_demo` 来源及位置的三值条件。输出包含配置版本、输入快照、checklist、missing_items、abnormal_items、pending_items、name_hints、node_trace和warnings。模型建议仅供人工确认，不自动消除缺项或修改状态。原始材料仅有静态摘录时内容待核实。详情见 [Workflow说明](f3-knowledge-base/management/09-材料完整性Workflow.md)。

## F3 政策问答

当前页面改用多轮协议：`POST /api/policy/conversations` 创建会话，`GET /{id}`恢复、`DELETE /{id}`幂等结束；`POST /{id}/messages/stream` 接收 question、request_id、可选retry_of，返回SSE。以上路径共用 `/api/policy/conversations` 前缀。请求不接受product或客户端历史；产品由用户语境和目录识别，不能把元数据过滤表达式交给模型自由生成。

流事件为meta、status、scope、sources、statement、clarification、warning、done、error，各data带conversation_id、request_id、message_id、递增seq；注释心跳不计序号。只有done表示完整回答通过校验并提交，error或无done的EOF均撤回正式正文。引用锚点按消息隔离；直接读取目录范围条款时cosine_distance为null，不冒充向量距离。完整会话和异常契约见 [多轮说明](f3-knowledge-base/management/08-多轮政策对话与流式验收.md)。

下述旧单轮接口保持兼容：

`POST /api/policy/ask` 请求为 `{"question":"未签设备采购合同可用报价单吗？","product":"equipment","rerank":false}`。product 为 `equipment`、`working_capital` 或 null；null 先补问。问题去空白后非空，最长2000字符，拒绝未知字段。与申请复核写入接口独立，不修改任何申请状态。

响应包含 `status`、`answer`、`statements`（每项含 text 及 source_id/quote 证据）、`sources`（条款来源及全文）、`cited_source_ids`、`missing_information`、`warnings`、`model`、`prompt_version`、`retrieval_k=8`、`context_k=6`、`elapsed_seconds`、`error_code` 和教学边界 notice。来源编号 S1—S6 只在本次请求有效。候选来源不代表被引用或已经支持回答。

status 为 `answered`、`insufficient_evidence`、`needs_clarification`、`out_of_scope`、`configuration_error`、`retrieval_error` 或 `generation_error`。已处理状态 HTTP 200；请求校验错误 HTTP 422。API/引用错误保留来源，不返回未通过校验的模型草稿。不会返回凭据、上游原始错误或推理过程。完整约定与人工验收见 [政策问答说明](f3-knowledge-base/management/07-DeepSeek政策问答.md)。

## 当前存储选择

企业、申请、材料和 Mock 报告使用 [seed.json](../mock_data/seed.json) 作为只读数据源，FastAPI 启动时用 Pydantic 校验字段和对象引用。人工复核动作保存在本地 SQLite 文件 `backend/.data/reviews.sqlite3`，该目录被 Git 忽略。读取申请时，接口将种子数据与动作记录按申请 ID 合并，返回最新状态、进度及复核记录。

固定教学样例保留 JSON，便于核对对象关系。复核需要重启后回看和防止重复提交，所以使用 Python 标准库 SQLite，以事务检查状态并写入动作。无需先安装 MySQL；生产级多用户并发、账号权限及数据库迁移留待后续，届时可替换存储层并保持接口契约。

当前不提供真实文件预览或生产级权限。修改种子样例后需要重启后端；若用 `--reload` 启动，应检查服务是否已重新读取数据。本地复核记录会保留，测试其他状态时请使用尚未复核的申请。

## 对象和关系

| 对象 | 主键 | 关系 |
| --- | --- | --- |
| 企业客户 | `enterprise_id` | 一家企业可对应多笔申请 |
| 授信申请 | `application_id` | 通过 `enterprise_id` 归属企业；一笔申请对应一个产品需求 |
| 进度事件 | `event_id` | 通过 `application_id` 归属申请，记录事件名称和发生时间 |
| 申请材料 | `material_id` | 通过 `application_id` 归属申请，`version_no` 区分补交版本 |
| AI 预审报告 | `report_id` | 通过 `application_id` 归属申请；多次运行可保留多份报告 |
| 报告摘要维度 | 所属 `report_id` | 材料完整性、风险提示、政策/教学规则匹配、预审建议；通过材料、关注项和知识 ID 追溯来源 |
| 预审知识条目 | `knowledge_id` + `version` | 报告关注项的 `knowledge_ref` 引用 |
| 人工复核记录 | `review_id` | 通过 `application_id` 归属申请，保留报告 ID、风控演示身份、时间、结果、意见和逐项处理 |

报告关注项中的 `evidence[].material_id` 必须指向同一申请下的材料。进度事件也必须指向现有申请，并按发生时间返回。数据加载时检查这些关系、重复 ID 和知识版本；不合格数据会阻止后端启动。

`Report` 增加四类结构化字段：`material_completeness`、`risk_prompts[]`、`policy_match`、`precheck_advice`。每个摘要维度包含 `status`、`summary`、`material_ids[]`、`item_ids[]` 和 `knowledge_refs[]`。状态只能为 `needs_review`（待人工核验）、`insufficient_evidence`（证据不足）或 `not_evaluated`（未形成判断）。引用必须属于当前申请和当前报告，知识编号、版本与要求文字必须匹配种子条目；未知引用会阻止启动。失败报告没有风险提示，并将无法分析的维度标为 `not_evaluated`。

这些字段是虚构教学预审线索，不构成正式政策认定或信用风险定性。报告模型禁止额外的 `final_decision` 等字段；完成复核只会把申请推进到“待审批”，最终授信决定不由 AI 报告产生。

## 接口

| 接口 | 响应 |
| --- | --- |
| `GET /api/enterprises` | 企业客户数组 |
| `GET /api/applications` | 申请数组，附企业名称和最新报告状态 |
| `GET /api/applications/{application_id}` | 申请、所属企业、`status_history`、材料、报告和 `reviews`；不存在时返回 404 |
| `POST /api/applications/{application_id}/review/start` | 风控演示身份从“待风控复核”进入“风控复核中”，返回更新后的申请详情 |
| `POST /api/applications/{application_id}/review/submit` | 风控演示身份提交逐项处理和意见，返回更新后的申请详情 |

写接口使用请求头 `X-Demo-Role: risk_reviewer`；`customer_manager` 或缺少该头返回 403。这个头可由客户端自行设置，仅用于教学角色差异，不是生产认证。演示风控人员 ID 固定为 `RISK-DEMO-001`。状态不符或重复提交返回 409；内容不完整返回 422；申请不存在返回 404。

提交体示例：

```json
{
  "review_result": "complete",
  "review_note": "已核对教学样例，建议进入后续审批。",
  "item_reviews": [
    {"item_id": "FINDING-DEMO-001", "decision": "confirmed", "correction_note": null}
  ]
}
```

`review_result` 为 `complete` 或 `request_supplement`；每个当前报告关注项须选择 `confirmed` 或 `corrected`，修正时须填写 `correction_note`。无报告或报告失败不能直接完成复核，可写明原因要求补件。结果分别转入“待审批”和“待企业补充材料”，不产生正式授信审批结论。

前端从申请列表选择一笔申请，再读取详情。`failed` 表示处理失败，`insufficient_evidence` 表示证据不足，空 `reports` 表示暂无报告；这些情况均不能展示为“无风险”。材料清单复用详情接口，只展示当前申请的材料。`preview_url` 目前为 `null`，不提供真实文件；可选的 `sample_location` 与 `sample_excerpt` 成对提供虚构教学静态摘录。页面明确标注摘录不是原件，报告证据需由人工依据正式材料核对。补交版本使用相同申请、材料类型与递增的 `version_no`；同一申请、材料类型和版本组合不得重复。

`status_history` 中每条事件包含 `event_id`、`application_id`、`event_label` 和带时区的 `occurred_at`。种子事件是教学样例；开始复核及提交结果会从 SQLite 动作生成后续进度事件，页面只显示实际返回的事件。`reviews` 仅包含已提交的复核记录，不将“开始复核”当成完成记录。

## 虚构样例

| 申请 | 情况 |
| --- | --- |
| `APP-DEMO-001` | 有材料页码、原文片段和教学知识版本的关注项 |
| `APP-DEMO-002` | 第 1 版被报告引用且证据不足，第 2 版为补交样例；尚无覆盖第 2 版的新报告 |
| `APP-DEMO-003` | 材料解析失败，报告给出错误及下一步 |
| `APP-DEMO-004` | 同一家企业的另一笔申请，暂无报告 |

所有名称、金额、材料文字和知识条目均为教学虚构数据，不代表真实客户、授信规则或风险结论。
# 企业教学申请提交（本轮）

`POST /api/applications` 接收 `enterprise_name`、`industry`、`registered_region`、`product_type`、`requested_amount`（正整数，单位元）和 `purpose`，需演示请求头 `X-Demo-Role: enterprise`。成功返回 201 和新申请，服务端生成申请与企业编号，将企业、申请及提交事件在同一事务中保存；初始状态为“待企业补充材料”，客户经理待分配。输入不合法返回 422，演示角色不符返回 403。既有申请的 `purpose` 可为空。

该角色标头可伪造，不能用于真实认证或数据隔离。企业端材料上传、补件后重新提交和人员分配尚未实现，不能把此提交视为完整进件或预审通过。
