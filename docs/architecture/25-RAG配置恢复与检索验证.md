# RAG Python配置恢复与检索验证

## 变更与边界

- `app/rag/settings.py`提供模型、语料、持久化路径、2048 token上限、批次与条款产品范围；`app/agents/product_catalog.py`提供两个产品的别名及政策范围引用。这些值根据现存文档、知识块和活动索引重建，无法证明与已删除的原JSON逐字相同。
- `load_config()`默认读取Python配置，并保留显式传入JSON路径的兼容能力；政策问答、风险Workflow、客户经理助手和评测脚本不再依赖旧知识库或产品目录JSON。政策条款仍来自虚构Markdown语料，密钥仍由环境变量管理。
- 产品目录引用经43个政策块校验文号、条款、版本及适用产品；引用用途只说明产品范围，不证明客户符合授信准入。两个Agent的RAG连接使用相同的政策检索服务。
- 原重排配置`backend/reranker.json`仍缺失。本轮只恢复纯向量检索；开启重排不能作为已恢复功能。

## 旧索引只读核对

`python scripts/check_rag_recovery.py`在本环境完成：现有语料生成43块；新配置计算的语料签名与活动索引一致；完整读取本地BGE-M3文件得到的模型指纹一致；只读查询Chroma SQLite元数据发现目标集合存在、维度1024、complete标记和集合签名一致、记录数43一致。

该检查没有写入或删除旧集合。SQLite元数据核对**不能替代通过Chroma API打开集合及运行实际向量查询**：当前执行环境加载NumPy/Chroma时DLL或依赖文件被系统拒绝访问。因此只能说旧索引元数据及指纹匹配、具有复用条件，不能说本轮真实检索已验证复用成功。

## 五题历史检索证据

2026-10-27 14:45:41（UTC）的既有开发集报告与当前语料签名一致。下表是该历史运行最大K=20的一次检索结果的前8条，并非本轮重新查询或直接K=8查询。历史输出包含完整候选与距离；表中命中仅指预先标注条款在候选里，不保证答案正确或证据充分。

| 题目 | 产品 | 标注依据 | 历史前8条结果 |
| --- | --- | --- | --- |
| Q01 经营周转贷能用于证券投资吗 | 经营周转 | CC-POL-001 第二条 | 命中 |
| Q02 2026年10月申请需哪几个月收入资料 | 经营周转 | CC-POL-001 第五条 | 命中 |
| Q05 尚无合同是否必然缺必交材料 | 经营周转 | CC-MAT-001 第三条 | 命中 |
| Q06 设备贷未签合同能否用报价单 | 设备更新 | CC-POL-002 第五条、CC-MAT-001 第四条 | 两条均命中 |
| Q14 请求不存在的CC-POL-999或其他机构政策 | 设备更新 | 无适用依据 | 检索仍返回8条候选；候选不等于可回答，须生成层识别无依据 |

五题的完整历史候选摘要和核对结果见`25-rag-restoration-evidence.json`。原始历史记录保存在被忽略的`backend/.data/knowledge-base/top-k-evaluation/report.json`，F4交接应单独保存。

## 当前验证

- 用户于2026-10-30 04:14:03 UTC在本机执行`verify_policy_live.py`，实际结果保存在`25-policy-live-results.json`。Q06返回answered，模型字段为deepseek-flash，耗时18.45秒，引用CC-POL-002第五、九条和CC-MAT-001第四条；回答保留报价单、未签约说明、必要字段及人工核对条件，没有作授信决定。Q13返回answered，耗时7.18秒，引用CC-POL-002第六、九条，没有编造额度、利率或自有资金比例，missing_information说明需补充适用制度。Q14返回insufficient_evidence、model=null、无引用，属于不存在文号的代码前置拦截，不是模型拒答验证。
- Q13来源第九条写的是“最终额度”未规定，不应直接等同于证明全部可能制度均未设置“最高额度”；此次回答没有给出最高额度数值，并明确要求补充具体制度，人工复核结论为符合保守回答预期。自动校验只检查状态及引用存在，不证明语义蕴含或所有政策均已穷尽。
- 实际响应为单轮`/api/policy/ask`；并未验证前端多轮SSE政策Agent或客户经理助手通过真实模型调用search_policy。模型字段表明有模型生成路径，响应未提供token用量和费用，不能推算成本或总体正确率。
- 用户在本机执行 `scripts/check_rag_recovery.py --live` 成功：实际通过Chroma查询Q01、Q02、Q05、Q06、Q14，每题直接返回Top-8。前4题的全部标注依据均被召回；Q14无标注依据但仍返回8个候选，不能据此认定已实现拒答。结果见同目录`25-rag-restoration-evidence.json` 的 `live` 字段。旧索引的模型、语料和集合元数据检查通过，已实际复用；未重新入库。
- 此次结果来自用户本机，执行进程和模型加载在用户环境中完成；本Agent环境仍无法导入相关DLL。上面五题为小规模定向用例，标签仍需人工核对，不能据此宣称整体准确率或召回率为100%。
- 16题开发标签核对通过；上表5题从中选取，含1道无依据题。
- 使用历史候选和假模型验证了`PolicyQA`生成引用、客户经理助手`search_policy`返回来源及审计链路；这是受控接线验证，不等于真实模型或实时检索通过。
- 本Agent执行环境中的 `.\backend\.venv\Scripts\python.exe scripts/check_rag_recovery.py --live`曾返回ImportError，status显示NumPy `_multiarray_umath` DLL拒绝访问；随后用户本机执行成功。两次结果不冲突，环境不同。
- 根目录`python scripts/check_project.py`通过；`python scripts/check_credit_assistant.py`及`python scripts/evaluate_credit_agent_risks.py`通过。政策不可用测试现为主动模拟检索异常，不再假设旧JSON缺失。
- 本Agent环境的真实DeepSeek连接曾失败；用户本机随后完成上述单轮真实调用。前端多轮、客户经理助手真实工具调用及未使用不存在文号的无依据模型拒答仍待验证。

## 本机后续验证

2026-10-30问答复验：Agent执行环境的DeepSeek连通检查返回`network_error`；当时本机8000端口无运行服务，HTTP测试的三题返回`URLError`。直接调用单轮政策服务时，不存在文号`CC-POL-999`得到`insufficient_evidence`，这是代码前置拦截，未调用模型；普通问题得到`retrieval_error`。随后用户本机成功运行，结果以“当前验证”为准。

新增 `scripts/verify_policy_live.py`，对本机8000端口测试Q06、Q13和Q14，保存HTTP响应和待人工核对的原文引用；Q06/Q13可能调用DeepSeek产生费用，Q14是前置规则拒答。输出的基础断言通过不代表回答语义和政策例外已人工确认。每次运行会覆盖本轮结果文件，保留旧记录时请先复制。

在项目根目录、用户自己的PowerShell中运行：

```powershell
.\backend\.venv\Scripts\python.exe scripts/check_rag_recovery.py --live
```

成功时将当前5题的直接Top-8结果写入`25-rag-restoration-evidence.json`；请人工核查Q14不能因有候选就给出政策结论。若失败，请提供错误类型和日志，不提供API Key或数据库密码。该命令不执行入库或删除索引；真实LLM问答需另行在页面测试，可能产生费用。

`check_rag_recovery.py`仅输出安全错误类型；若要查看本地依赖的详细诊断，可运行 `.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py status`，此命令不要求读取模型服务密钥。
