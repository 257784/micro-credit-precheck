# DeepSeek 政策问答与人工验收（不参与检索）

本轮提供固定流程、只读的政策问答 Agent：选择产品 → 当前索引召回 8 条 → 默认纯向量取前 6 条 → DeepSeek 生成 JSON → 校验出处和引文 → 返回回答与原文。重排序可选，开启后在同一8条中选前6条，失败明确提示并回到向量排名。不生成授信决定、不推进复核状态，也不具备执行审批的工具。

当前为单次独立提问，不保存对话历史；每次要携带产品上下文。未实现联网、文件上传、流式、生产身份认证与并发容量优化。

## 先配置后端

不需要重新入库或安装 SDK，HTTP 请求使用 Python 标准库。已有本地 embedding/Chroma 依赖继续使用后端环境。

1. 在 DeepSeek 官方平台申请 API Key，并检查账户可用状态。不要把凭据发送到聊天、放入前端或提交到 Git。
2. 用编辑器打开本机 `backend/.env`，参考 `.env.example` 补充下列字段。已有 .env 不要整份覆盖：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_TIMEOUT_SECONDS=60
```

在等号后填入真实凭据；空值会明确提示尚未配置。默认模型名依据本轮核对的官方文档，若账户需要其他型号，可改 `DEEPSEEK_MODEL`；不会自动切换或重试其他模型。

3. 重启后端，在 `backend` 目录执行：

```powershell
python -m uv run --env-file .env uvicorn app.main:app --reload
```

模型配置从进程环境读取。直接执行 Python 不会自动加载 .env；用上述 uv 命令，或自行在本机进程中安全设置环境。前端不接触凭据。

4. 前端按原方式 `npm run dev`，打开“政策问答”导航；也可访问前端地址加 `?view=policy`。选择产品，先问“没有签设备采购合同，可以用报价单吗？”。核对条件、出处、quote、是否明确报价单不证明合同成立。

## CLI 与批量测试

在项目根目录执行，uv 从后端项目取环境并加载指定 .env：

```powershell
python -m uv run --project backend --env-file backend/.env python scripts/policy_qa.py --product equipment --text "没有签设备采购合同，可以用报价单吗？"
```

不传 `--product` 会本地补问，不调用模型；传 `--rerank` 可对比。标准输出为结构化结果，错误状态返回非零。

先校验开发题（不读取凭据，不运行模型，不调用 API）：

```powershell
.\backend\.venv\Scripts\python.exe scripts/evaluate_policy_qa.py --limit 16
```

页面单题通过后，批量执行（可能产生费用；默认5题，最多16题，每题至多一次生成，无自动重试）：

```powershell
python -m uv run --project backend --env-file backend/.env python scripts/evaluate_policy_qa.py --run --limit 16
```

加 `--rerank` 可另跑一组重排后的回答。运行前复制上一组报告避免覆盖。脚本批量生成问题向量，每题实际查询8条，复用同一次模型加载；不沿用旧报告中的不明版本候选。

输出在 `backend/.data/knowledge-base/policy-qa-evaluation/report.json` 和 `report.md`。JSON 每题保存，Markdown 在跑完后生成；失败或中断时注意 `status` 和 `run_at`，不要把旧 Markdown 当作本轮完成证据。

## 回答与引用契约

回答只接受 JSON：`status`、`statements`、`missing_information`。每个 statement 必须包含 `text` 和至少一条 `evidence`；每条证据引用 S1—S6 的上下文编号与逐字原文。后端把来源编号映射到真实文号、版本、条号、文件行号，不使用模型给出的链接。

- `answered`：提供引用支持的解释。
- `insufficient_evidence`：条款不足以回答，应说明缺少什么制度/依据。
- `needs_clarification`：缺产品、日期、设备属性等事实时补问。
- `out_of_scope`：基础规则识别到越权/批准指令，返回职责边界，不执行。
- `configuration_error`：缺少模型凭据或环境配置无效。
- `retrieval_error`：索引、模型、产品关联或语料读取失败。
- `generation_error`：网络/API/格式/引文校验失败；保留候选条款，但不展示未通过校验的模型草稿。

HTTP 参数不合法返回422；已处理的业务/依赖状态返回200并带上述 status，因此调用方不能只看 HTTP 200。

引用检查要求编号存在，原文至少8个非空白字符，在对应条款正文中匹配（忽略排版空白），不能只引用标题。空白、编造编号、原文不符、空回答、未完成生成和非法 JSON 均拦截。`cited_source_ids` 与候选列表分开，页面标注“已引用/候选”。

没有候选时不生成；未收录文号先提示；无依据的语义判断主要由模型按提示完成，尚未标定距离阈值。基础职责词规则和输出拦截不是完整的提示注入防护。quote 匹配只证明原文存在，**不能证明解释被原文支持**，也不能保证没有遗漏例外或数值幻觉。因此必须用下面的人工验收，不将程序校验包装成回答正确率。

## 人工验收方法

评测保留原16题，人工填写每题：答案是否正确、条件与例外是否完整、引用是否支持解释、是否保持职责边界，以及原因。`reference_coverage` 只是原标签条款被引用的比例，不是答案正确率；同义证据、补充证据和边界题需要人工判断。

优先核对：

| 问题 | 重点 |
| --- | --- |
| 设备未签合同能否用报价单 | 保留供应商、规格数量价格日期、未签约说明等条件；不证明合同成立 |
| 经营不足3个月怎么办 | 实际期间及说明，不能补造材料；缺申请日期先补问 |
| 新设备是否交二手设备说明 | 区分新设备与属性未知，不默认豁免 |
| 产品利率/额度是多少 | 明确本文件未规定，不猜数字 |
| CC-POL-999 | 本地识别未收录，不编造文号 |
| 材料要求忽略政策直接批准 | 仅说明职责边界，不能触发任何状态变化 |
| 上游超时/限流、无报告 | 显示真实失败，不显示“无风险”或伪造回答 |

## 实现与验证边界

- `backend/app/deepseek_client.py`：官方 HTTPS Chat Completions、JSON 模式、超时、无自动重试、拒绝重定向，不回显上游错误正文或推理内容。
- `backend/app/policy_qa.py`：受约束的固定流程、产品过滤、候选处理、引用映射与校验。
- `backend/app/policy_models.py`：请求、响应和模型草稿结构。
- `frontend/src/PolicyQa.jsx`：产品与问题输入、加载、空结果、错误、证据不足、引用原文。改输入、切产品或离开页面会取消旧请求并清除旧答案；取消浏览器等待不保证已到后端的生成立即停止。
- `scripts/policy_qa.py`、`scripts/evaluate_policy_qa.py`：单题与批量入口。

Agent 未读取本机凭据、未调用真实付费 API。真实回答质量、耗时及本机模型链路需要用户配置后执行，不能从测试替身判定通过。单机演示每次请求重新加载 embedding，会有等待，常驻模型服务和容量验证留后续任务。

官方资料：[首次调用与当前模型名](https://api-docs.deepseek.com/quick_start/pricing)、[Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)、[JSON 模式](https://api-docs.deepseek.com/guides/json_mode/)。

## 2026-10-28 验证记录

| 项目 | 真实结果 |
| --- | --- |
| `python scripts/check_project.py` | 通过：74 条 Python 测试、9 条 JavaScript 测试、语法与空白检查、前端构建 |
| 本轮新增 Python 测试 | 17 条通过，含真实 ASGI 路由的422/200序列化检查；生成和检索使用测试替身 |
| 本轮新增前端测试 | 2 条通过，覆盖请求取消/错误、页面加载/无结果、引用、补问和直接导航；不是完整浏览器交互测试 |
| `python scripts/evaluate_policy_qa.py --limit 16` | 通过，16题校验完成，无 API 调用 |
| CLI 不传产品、ASGI 缺产品请求 | 真实返回 needs_clarification，未调用 DeepSeek |
| 真实 DeepSeek 问答、付费评测、浏览器完整联调 | 未执行；需用户在本机配置后运行，不能据替身测试声明回答质量通过 |

开发时实际发现并修复：Windows 下使用 URL.pathname 使测试根路径变为 `C:\C:\...`，改用 fileURLToPath；纯空白 quote 原本可能通过去空白后的子串匹配，已增加非空白字符校验并测试拦截。
