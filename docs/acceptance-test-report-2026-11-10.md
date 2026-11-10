# 授信预审系统验收测试记录

测试日期：2026-11-10。范围为当前工作区代码。测试采用虚构材料、临时 SQLite、FastAPI TestClient 和模拟模型／检索器；不修改开发数据库，不调用真实 DeepSeek。以下“通过”限于所述输入和断言，不代表生产验收。

## 验收用例

| 编号 | 场景与操作 | 预期 / 本次实际 | 结果与证据 |
|---|---|---|---|
| T01 | 企业创建草稿，上传 APP-FICT-001 六份正文 DOCX，初检后提交 | 返回 201、上传成功，提交后为待风控复核 | 通过；`check_auth_integration.py` |
| T02 | 企业没有材料即提交 | 422，不能进入风控复核 | 通过；`check_auth_integration.py` |
| T03 | 上传损坏 DOCX 再提交 | 解析标记失败，提交返回 422；重新上传可读文件后继续 | 通过；`check_auth_integration.py` |
| T04 | 已正式提交后再次提交 | 409，状态不重复推进 | 通过；`check_auth_integration.py` |
| T05 | 第二家企业读取第一家企业材料 | 404，不暴露跨企业申请 | 通过；`check_auth_integration.py` |
| T06 | 客户经理运行风险预审 | 403，只有风控可运行 | 通过；`check_auth_integration.py`、`check_permissions_submission.py` |
| T07 | 伪造仓储预期状态，试图从待审批直接完成风控复核；对审批终态再次操作 | 拒绝跳转，状态和记录不改变 | 通过；`check_state_transitions.py` |
| T08 | AI 返回缺少引用字段的结构化回答 | 生成结果为 `generation_error` / `invalid_answer`，不返回该解释 | 通过；`check_acceptance_extra.py::test_missing_ai_field_rejected`，使用假模型 |
| T09 | 检索器返回空结果且模型未配置 | `insufficient_evidence`，不调用模型；修复前为 `configuration_error` | 通过（修复后）；`check_acceptance_extra.py::test_no_hit_without_model_configuration`，模拟空结果 |
| T10 | 常见手机号和 18 位身份证出现在申请或解析文本中 | 相关页面 API 部分掩码；模型请求不含原号码；日志不含材料和意见 | 通过；`check_auth_integration.py`、`check_review_redaction.py`，模型传输为模拟 |
| T11 | 风控总体部分采纳，逐项处理报告并提交 | 保存处理结果、报告 ID，状态进入待审批；旧报告被拒绝 | 通过；`check_auth_integration.py`、`check_review_redaction.py` |
| T12 | 部分采纳或不采纳但未填写逐项说明 | 复核服务拒绝，不执行保存 | 通过；`check_review_redaction.py` |
| T13 | 最新检查后材料版本变化 | 旧检查记录标记过期 | 通过；`check_permissions_submission.py`，使用隔离数据模拟版本变化 |
| T14 | 模拟报告保存故障和风险 Workflow 降级 | 保存故障返回 503；降级报告标记 failed，不当作无风险 | 通过；`check_auth_integration.py`，使用故障注入 |
| T15 | 日志插入失败及无权限查询审计 | 业务状态回滚；非管理员查询 403 | 通过；`check_state_transitions.py`、`check_auth_integration.py` |
| T16 | 知识检索器抛出故障 | `retrieval_error`，不伪装成无命中 | 通过；`check_acceptance_extra.py::test_retrieval_failure_is_not_empty_result`，模拟故障 |
| T17 | 询问知识库不存在的文件文号 | `insufficient_evidence`，不调用模型 | 通过；`check_acceptance_extra.py::test_unknown_document_refused` |
| T18 | 合规用户下载虚构原件 | 返回上传的原始字节；原件未脱敏 | 行为确认；`check_auth_integration.py`，风险见 P03 |

以上 18 条均有本次执行的断言。T18 的“行为确认”不等于安全通过；T09 的空结果来自模拟检索器，并未证明向量检索对所有无关问题都能自动判断无命中。逐项复核三种选择及历史兼容由 `check_review_redaction.py` 的服务层测试覆盖；T11 的实际 API 总体选择为部分采纳。

## 问题清单

| 编号 | 实际发现与复现 | 处理 | 结果或原因 |
|---|---|---|---|
| P01 | 模拟检索空结果、模型未配置：修复前返回 `configuration_error`，掩盖无依据事实 | **已修复** | 将模型客户端初始化移至非空检索结果之后；T09 回归通过。此修复针对单轮 `PolicyQA`，不代表所有 Agent 流程均已验证。 |
| P02 | `redact_text('手机号 138 0013 8000', 'model')` 原样返回；带空格号码未被现有规则识别 | **延期** | 现有规则只覆盖连续格式；需后续处理分隔符、误匹配与 OCR 变体，并做更大样本验证。在此之前不能使用真实客户数据。测试通过表示如实确认当前边界，不表示该风险已解决。 |
| P03 | 有权用户下载材料时返回原始 DOCX 字节，文件内容不会因页面掩码而改变 | **教学环境暂接受风险** | 保留原件供有权人员核验，T18 确认当前行为；仅适用于虚构数据和本机受控环境。真实业务需要重新设计原件访问、审计和脱敏，不等于已获得生产使用批准。 |

## 验收结论与限制

**教学范围有条件通过**：18 项指定场景的预期行为或已知边界已按上表核验，P01 已修复；P02、P03 尚未达到真实敏感数据的安全要求。测试中没有真实模型调用、浏览器人工验收、外部服务故障演练或 MySQL 并发压力测试，不能据此宣称生产就绪。

测试过程运行：`scripts/check_acceptance_extra.py`（5 项）、`check_auth_integration.py`、`check_permissions_submission.py`、`check_state_transitions.py`、`check_review_redaction.py`、`check_credit_assistant.py`（13 项）、`check_assistant_result.py`（10 项）、`check_credit_assistant_workflows.py`（4 组），以及 `python scripts/check_project.py`；上述进程均返回 0。详细操作和 Apifox 示例见 [测试方法与 Apifox 指南](architecture/35-测试方法与Apifox.md)。
