# 测试方法与 Apifox 使用指南

## 是否需要自动化？

建议需要。自动化能重复验证状态、数据隔离、错误处理和脱敏等重要规则；当前项目已有可独立运行的隔离验证脚本。Apifox 适合手工观察真实 HTTP 请求，也可以编排自动化场景；浏览器人工检查适合验证按钮、布局和交互。三者解决的问题不同，不能只以页面点通代替异常测试。

本轮测试记录见 [验收测试报告](../acceptance-test-report-2026-11-10.md)。从项目根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe scripts/check_acceptance_extra.py
.\backend\.venv\Scripts\python.exe scripts/check_auth_integration.py
.\backend\.venv\Scripts\python.exe scripts/check_permissions_submission.py
.\backend\.venv\Scripts\python.exe scripts/check_state_transitions.py
.\backend\.venv\Scripts\python.exe scripts/check_review_redaction.py
.\backend\.venv\Scripts\python.exe scripts/check_credit_assistant.py
.\backend\.venv\Scripts\python.exe scripts/check_assistant_result.py
.\backend\.venv\Scripts\python.exe scripts/check_credit_assistant_workflows.py
python scripts/check_project.py
```

这些脚本使用虚构数据、隔离 SQLite 或模拟依赖；`check_project.py` 只检查空白、Python 语法和前端构建，不等于上述业务测试。

## 准备 Apifox

1. 使用独立教学测试库和虚构账号，按 [README](../../README.md) 启动后端；本机地址为 `http://127.0.0.1:8000`。**以下创建、上传、提交和复核请求会写入当前连接的数据库**，不要指向现有需要保留的数据或真实客户库。
2. 在 Apifox 新建项目，可使用「项目设置 → 导入数据 → OpenAPI/Swagger」导入 `http://127.0.0.1:8000/openapi.json`，或在本机浏览器保存该 JSON 后以文件导入。导入的是 `openapi.json`，不是 `/docs` 页面；部分服务端导入方式无法访问本机地址。参考 [Apifox OpenAPI 导入文档](https://docs.apifox.com/import-openapi-swagger)。
3. 将环境的服务地址设为 `http://127.0.0.1:8000`。下方路径均相对于此地址。使用 Apifox 客户端访问本机服务；不要手动添加不匹配的 `Origin` 请求头。
4. 使用项目内实际创建的教学账号登录。不要把凭据、Cookie、请求历史或含敏感信息的截图上传到公共仓库。

## 请求示例

### 1. 登录并保留 Cookie

`POST /api/auth/login`，Body 选择 JSON：

```json
{"username": "你的企业教学账号", "credential": "在本机填写密码"}
```

成功返回 200 和用户角色，服务器通过 `Set-Cookie` 设置 `credit_session`。在同一个 Apifox 会话和同一主机名下发送后续请求，确认 Cookie 管理器中已有对应 Cookie；不要将 Cookie 值粘贴到文档或聊天。Apifox 的 [Cookie 管理文档](https://docs.apifox.com/create-and-send-cookie) 说明了域名关联与发送方式。使用不同角色测试时，先 `POST /api/auth/logout`，再以新角色登录，避免 Cookie 被覆盖后误判身份。

### 2. 创建草稿和材料初检

企业登录后发送 `POST /api/applications`：

```json
{
  "enterprise_name": "虚构示例企业",
  "industry": "教学制造业",
  "registered_region": "教学地区",
  "product_type": "设备更新贷（教学产品）",
  "requested_amount": 100000,
  "purpose": "购置虚构教学设备",
  "is_used_equipment": false
}
```

预期 201，返回 `application_id` 和 `草稿`。保存此编号到本地测试变量或手动替换以下 `{application_id}`。

`POST /api/applications/{application_id}/materials/check`，Body 为 `{}`。无材料时应返回检查结果，其中包含缺失项；再发送 `POST /api/applications/{application_id}/resubmit`，Body 为 `{}`，预期 422，草稿不能进入风控。此请求实际运行规则并记录检查，不是只读操作。

如需上传虚构 PDF/DOCX，发送 `POST /api/applications/{application_id}/documents?category=M-C01&filename=demo.docx`，将 Body 设置为 **Binary 原始文件**并选择文件；本接口读取的是请求体原始字节，不是 `form-data`。实际完整申请需要按照对应产品清单上传其余材料；文件名和材料类别须对应。

### 3. 权限和状态异常

- 换另一个企业账号，`GET /api/applications/{application_id}`，预期 404。
- 对已经正式提交的申请再次 `POST /api/applications/{application_id}/resubmit`，Body `{}`，预期 409；不要为构造状态直接改数据库。
- 进入风控可见状态后，切换到负责该申请的客户经理，`POST /api/applications/{application_id}/risk-precheck`，Body `{}`，预期 403。若申请并不属于该经理，可能先得到 404。

### 4. 模拟知识库缺失

登录企业或其他有政策问答权限的教学账号，发送 `POST /api/policy/ask`：

```json
{"question":"请解释 CC-POL-999", "product":"equipment", "rerank":false}
```

该文号不在教学语料中，预期 HTTP 200、响应 `status` 为 `insufficient_evidence`；HTTP 200 不代表有答案。这个用例测试明确不存在的文号，不等同于所有无关问题的向量无命中。

### 5. 人工复核与日志

完整材料提交后，以风控账号调用 `POST /api/applications/{application_id}/risk-precheck`，Body `{"use_model":false}`，查看 `saved_report_id`；调用 `POST /api/applications/{application_id}/review/start`。再从 `GET /api/applications/{application_id}` 中读取最新报告的 `report_id` 和全部关注项 `item_id`。

发送 `POST /api/applications/{application_id}/review/submit`，示例中的 ID 应替换成当前报告真实返回值，`item_reviews` 必须覆盖当前全部关注项；如果没有关注项，使用空数组：

```json
{
  "review_result": "complete",
  "overall_adoption": "partial",
  "review_note": "人工复核教学意见",
  "report_id": "替换为最新报告编号",
  "item_reviews": [
    {"item_id": "替换为真实关注项编号", "decision": "partial", "correction_note": "说明修改依据"}
  ]
}
```

预期成功后为待审批。部分采纳或不采纳的逐项选择缺少说明时应被拒绝；测试时不要复用已经进入待审批的申请。退出并用管理员登录，`GET /api/operation-audit?application_id={application_id}`，检查动作、操作者、前后状态和结果，不应包含材料正文或复核意见。非管理员访问该日志接口应返回 403。

## 执行记录

每条测试保留输入、账号角色、预期、状态码和关键响应字段，必要时截图；不要保存密码、Cookie 或完整材料。Apifox 可在响应中设置断言并编排场景，重复运行前需准备新的隔离样例，避免前次状态影响结果。
