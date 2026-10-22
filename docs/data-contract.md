# F2 核心数据对象与只读接口

## 当前存储选择

本步使用 [seed.json](../mock_data/seed.json) 作为只读数据源，FastAPI 启动时用 Pydantic 校验字段和对象引用，再通过 `/api` 接口提供给 React 页面。

选择 JSON 是因为本步要验证对象关系、页面取数和异常样例，且数据完全固定。它不需要先安装、初始化和迁移 MySQL，也不会让接口与页面直接依赖文件格式。SQLite 对本步的固定样例仍需建表和迁移，收益有限。MySQL 保留为后续人工复核记录、状态更新和多用户操作所需的持久化方案；届时替换数据访问层，保持接口响应结构。

当前 JSON 不提供并发写入、持久化复核、文件预览或数据库约束。修改样例后需要重启后端；若用 `--reload` 启动，应检查服务是否已重新读取数据。

## 对象和关系

| 对象 | 主键 | 关系 |
| --- | --- | --- |
| 企业客户 | `enterprise_id` | 一家企业可对应多笔申请 |
| 授信申请 | `application_id` | 通过 `enterprise_id` 归属企业；一笔申请对应一个产品需求 |
| 进度事件 | `event_id` | 通过 `application_id` 归属申请，记录事件名称和发生时间 |
| 申请材料 | `material_id` | 通过 `application_id` 归属申请，`version_no` 区分补交版本 |
| AI 预审报告 | `report_id` | 通过 `application_id` 归属申请；多次运行可保留多份报告 |
| 预审知识条目 | `knowledge_id` + `version` | 报告关注项的 `knowledge_ref` 引用 |

报告关注项中的 `evidence[].material_id` 必须指向同一申请下的材料。进度事件也必须指向现有申请，并按发生时间返回。数据加载时检查这些关系、重复 ID 和知识版本；不合格数据会阻止后端启动。

## 只读接口

| 接口 | 响应 |
| --- | --- |
| `GET /api/enterprises` | 企业客户数组 |
| `GET /api/applications` | 申请数组，附企业名称和最新报告状态 |
| `GET /api/applications/{application_id}` | 申请、所属企业、`status_history` 进度事件数组、材料数组和报告数组；不存在时返回 404 |

前端从申请列表选择一笔申请，再读取详情。`failed` 表示处理失败，`insufficient_evidence` 表示证据不足，空 `reports` 表示暂无报告；这些情况均不能展示为“无风险”。`preview_url` 目前为 `null`，页面明确提示尚无样例文件预览。

`status_history` 中每条事件包含 `event_id`、`application_id`、`event_label` 和带时区的 `occurred_at`。当前两条事件仅用于教学页面验证，不是生产审计记录；页面只显示实际返回的事件，不推断未记录的状态。

## 虚构样例

| 申请 | 情况 |
| --- | --- |
| `APP-DEMO-001` | 有材料页码、原文片段和教学知识版本的关注项 |
| `APP-DEMO-002` | 材料无法核对申请表数值，标记证据不足 |
| `APP-DEMO-003` | 材料解析失败，报告给出错误及下一步 |
| `APP-DEMO-004` | 同一家企业的另一笔申请，暂无报告 |

所有名称、金额、材料文字和知识条目均为教学虚构数据，不代表真实客户、授信规则或风险结论。
