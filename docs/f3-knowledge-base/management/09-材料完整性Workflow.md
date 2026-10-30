# 材料完整性Workflow

材料页的检查按钮读取本申请的服务端材料，按 CC-MAT-001 1.0 虚构教学清单执行。旧材料中的“可读取”和静态摘录不会被当作全文解析；已提交、不可读取、缺项和待核实分别展示。结果只在本次页面运行中使用，不修改申请状态或旧报告。

入口 `POST /api/applications/{application_id}/materials/check`，请求允许 `use_model` 和人工演示条件 `conditions`，不接收材料列表。未知申请404，条件输入无效422；正常运行返回节点轨迹和 `missing_items`、`abnormal_items`、`pending_items`。配置失败返回503。`dependency_degraded` 表示名称模型失败，规则结果仍可查看。

模型默认关闭。开启时只判断未归类名称可能属于哪些类别，输出候选和来自输入的文字，须人工确认。模型不能决定必交/豁免；不可用或输出非法时降级。启用可能调用DeepSeek并产生费用。

在项目根目录使用已有Python运行三个独立虚构fixture：

```powershell
python scripts/check_materials.py --fixture mock_data/material_workflow/normal.json
python scripts/check_materials.py --fixture mock_data/material_workflow/empty.json
python scripts/check_materials.py --fixture mock_data/material_workflow/failed_and_missing.json
```

normal展示声明材料和Mock字段；empty展示空材料与必交缺项；failed_and_missing展示已提交但解析失败，以及已检查字段为空。输出含规则出处、版本、材料快照、节点轨迹和人工核对建议。使用 `--output` 可在项目内保存结果；`--use-model` 会尝试实际调用模型。

这不是PDF/DOCX解析器。声明后缀只做格式提示，文件真伪、具体内容、证据充分性与最终授信仍由人工核验。原F2样例并非按新清单准备，可能产生缺项和待核实结果。

实际执行记录保存在 [normal.json](workflow-evidence/normal.json)、[empty.json](workflow-evidence/empty.json)、[failed_and_missing.json](workflow-evidence/failed_and_missing.json)。正常样例无确定缺项和异常，但仍有1项人工充分性核验；空材料样例有5项必交缺项、1项空列表异常及1项条件待确认；解析失败样例有3项缺项、2项异常。以上均是规则和Mock数据结果，未执行真实模型或文件解析。
