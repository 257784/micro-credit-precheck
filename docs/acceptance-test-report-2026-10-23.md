# F2 核心链路验收记录（2026-10-23）

## 执行范围与环境

- 基准：`../../06-F2-MVP范围表.md`、`../specs/07-final-acceptance.md`。
- 命令：在 F2 根目录执行 `python scripts/check_project.py`，另执行 `git diff --check`。
- 数据：`mock_data/seed.json` 中 4 笔虚构申请；复核写入测试使用 `tempfile.TemporaryDirectory()` 中的独立 SQLite 文件，不修改 `backend/.data/reviews.sqlite3`。
- 方法：Python 单元与服务/路由函数测试、React 服务端渲染测试、前端生产构建。路由函数测试验证返回模型与 `HTTPException`，没有启动真实 HTTP 服务。

## 验收用例

| 编号 | 输入与操作 | 预期结果 | 实际结果 / 证据 | 结论 |
| --- | --- | --- | --- | --- |
| T01 | 读取申请列表及 `APP-DEMO-001` 详情 | 列表有 4 笔；详情、材料、报告共用申请 ID | 4 笔；关联 ID 一致；`test_read_api_keeps_application_report_and_materials_together` | 通过 |
| T02 | 打开申请详情和材料页 | 展示申请进度、材料版本和来源，空值/错误有提示 | `application_detail.test.mjs` 的详情与材料用例通过 | 通过 |
| T03 | 展示 `APP-DEMO-001` 报告 | 四类结构化摘要及材料、知识来源可见，不含最终授信决定 | `report_review.test.mjs` 与 `test_read_api_keeps_application_report_and_materials_together` 通过 | 通过 |
| T04 | 展示 `APP-DEMO-002` 证据不足报告与新材料版本 | 标明证据不足和晚于报告的材料 | `report_review.test.mjs` 与 `test_relationships_and_four_review_states` 通过 | 通过 |
| T05 | 展示 `APP-DEMO-003` 解析失败与 `APP-DEMO-004` 无报告 | 不把失败或缺失显示为无风险 | `report_review.test.mjs` 与 `test_relationships_and_four_review_states` 通过 | 通过 |
| T06 | 读取、开始或提交 `APP-UNKNOWN` | 均返回 404；其他申请不受影响 | `test_missing_application_returns_404_for_read_and_write` 通过 | 通过 |
| T07 | 客户经理开始或提交复核 | 返回 403，不能写入 | `test_api_role_boundary_and_conflict` 通过 | 通过 |
| T08 | 风控专员开始并完成 `APP-DEMO-001`，重建服务后读取 | 待风控复核 → 风控复核中 → 待审批；意见和逐项结果持久化 | `test_complete_review_persists_and_updates_only_selected_application` 通过 | 通过 |
| T09 | `APP-DEMO-003/004` 在失败或无报告时尝试完成，再要求补件 | 完成被拒绝；补件后为待企业补充材料 | `test_failed_or_missing_report_can_request_supplement_but_not_complete` 通过 | 通过 |
| T10 | 缺少关注项决定、修正说明或有效意见 | 返回 422；拒绝后不新增记录或状态事件 | `test_rejects_missing_decisions_correction_and_note`、`test_rejected_submission_does_not_append_record_or_change_status` 通过 | 通过 |
| T11 | 对已开始或已提交的申请重复操作 | 返回 409；不重复推进状态 | `test_api_role_boundary_and_conflict`、`test_failed_or_missing_report_can_request_supplement_but_not_complete` 通过 | 通过 |
| T12 | 在报告或摘要中注入最终决定，或引用其他申请材料 | 加载样例时拒绝 | `test_rejects_final_decision_in_ai_report`、`test_rejects_evidence_from_another_application`、`test_rejects_report_aspect_reference_to_another_application` 通过 | 通过 |

## 测试结果

- 基线执行：19 条 Python 测试、5 条 JavaScript 测试通过；前端构建通过。
- 补充测试：新增 3 条，覆盖同申请关联读取、未知申请 404、非法提交后的状态与记录保持。
- 最终完整检查：22 条 Python 测试、5 条 JavaScript 测试全部通过；Python 语法、工作区和暂存区空白检查、前端 Vite 构建均通过；`git diff --check` 通过。

## 问题与剩余限制

本项目实际遇到并处理的问题如下；它们与后表的范围限制分别记录。

| 编号 | 实际现象 | 处理与验证 |
| --- | --- | --- |
| I01 | 用户级安装 `uv` 后，PowerShell 提示 `uv` 不是可识别命令。 | 改用 `python -m uv` 调用已安装模块；README 已给出同步与启动命令，本轮环境核验得到 `uv 0.13.4`。 |
| I02 | 本机前端开发时默认 Vite 配置加载失败。 | 将开发与构建脚本改为 `vite --configLoader native`；本轮 Vite 启动和构建均通过。 |
| I03 | 截图脚本经 PowerShell 管道传入时，中文选择器被替换为问号，导致等待超时。 | 将脚本保存为 UTF-8 文件执行；实际页面和复核记录截图已保存在 `submission/evidence/`。 |

| 编号 | 级别 | 现象 / 影响 | 当前状态 |
| --- | --- | --- | --- |
| V01 | 验收范围限制 | 未执行真实浏览器点击和真实 HTTP 服务端到端测试；页面交互结论来自 React 渲染测试，接口结论来自路由函数与服务测试。 | 待后续浏览器验收 |
| V02 | 已知 MVP 限制 | 演示角色由 `X-Demo-Role` 标头选择，无法作为生产权限机制；真实身份认证在 F2 范围外。 | 后续阶段处理 |

本轮自动测试中未发现阻断核心链路的失败项。上述限制不计作已通过的端到端或生产安全验证。
