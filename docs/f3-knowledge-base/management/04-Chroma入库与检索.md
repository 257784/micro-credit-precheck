# Chroma 入库与检索（不参与检索）

## 基础配置

配置文件为 [backend/knowledge-base.json](../../../backend/knowledge-base.json)，其中路径均相对项目根目录解析，切换终端目录不影响文件定位。

| 项目 | 值 |
| --- | --- |
| 模型 | 本地 `models/bge-m3/`，不自动下载 |
| 维度与距离 | 1024 维、归一化、余弦距离 |
| 语料来源 | `docs/f3-knowledge-base/corpus-manifest.json` 指定的五份正文 |
| 切分 | 每条一个块，43 条；标题、表格、条后例外一起保留，无机械重叠 |
| 长度检查 | 包含文号、标题等前缀及特殊 token，最多 2048 tokens；超长报错，不截断 |
| 默认执行 | CPU、batch_size=1；可用 `--device cuda` 选择显卡半精度 |
| 持久化 | `backend/.data/chroma/` |
| 预览与活动索引 | `backend/.data/knowledge-base/chunks.json`、`active-index.json` |

2048 是本轮输入校验上限，不是强制切成 2048 tokens。当前文档以完整条款为语义边界，后续若增加长条款，应再设计切分并修改策略版本。

## 执行步骤

在项目根目录使用已有后端 Python，先检查切分结果：

```powershell
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py preview
```

预期五份文档分别为 10、9、6、10、8 条，共 43 条。预览只用标准库，不加载模型，也不写向量数据库。打开生成的 `chunks.json` 查看正文、来源和适用产品。

然后入库：

```powershell
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py ingest --device cpu
```

脚本读取完整模型文件计算指纹，再生成向量。第一次 CPU 运行可能较慢；可在显卡可用时改为 `--device cuda`。只有全部成功且数据库计数正确后，才写入活动索引记录。Chroma 显式使用 `embedding_function=None`，传入已经计算的向量，不调用它的默认 embedding 模型。

重新启动一个终端，验证持久化和检索：

```powershell
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py status
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py query --product equipment --text "没有签订设备采购合同，可以用报价单吗？" --top-k 5
.\backend\.venv\Scripts\python.exe scripts/knowledge_base.py query --product working_capital --text "经营收入资料需要覆盖几个月？" --top-k 5
```

第一题应在候选中找到 CC-POL-002 第五条或 CC-MAT-001 第四条；第二题应找到 CC-POL-001 第五条。具体命中顺序须以实际检索为准。输出保留正文、文号、版本、条号、源文件和行号，`cosine_distance` 越小表示向量越接近，不是符合政策的概率。

`--product` 必填：`equipment` 为设备更新贷，`working_capital` 为经营周转贷。共通规则都可检索；材料清单第三、四条在配置中分别限定到对应产品，防止共通文件里的专属条款串用。阶段元数据保留，本轮不启用阶段过滤，以便复核时仍能找回初检材料要求。

## 更新和失败恢复

- 相同语料、配置和模型产生相同集合名及块 ID；已完整入库的快照直接复用，不重复增加记录。
- 文本、版本、产品范围、长度配置或模型文件改变时，生成新快照。旧快照保留，不自动删除。
- 编码或写入失败时不切换活动索引。重新执行 `ingest` 可重试；配置或正文改变后，`query` 拒绝静默使用过期快照。
- 活动索引文件和 Chroma 目录应一起保留。不要并行执行多个入库命令；本轮按单人、本地顺序运行设计。
- 模型文件指纹校验会读取约 2.27 GB 权重，首次入库和每次新查询进程都可能有等待；后续服务化时可设计受控缓存。

## 验证状态与边界

本轮新增单元测试覆盖白名单路径、完整表格和例外、产品过滤、重复编号、语料变更、超长输入、无效向量、重复写入及失败不切换活动索引。存储相关单元测试使用测试替身，不等于真实 Chroma 集成测试。

2026-10-27 实际验证记录：

| 检查 | 实际结果 |
| --- | --- |
| `python scripts/knowledge_base.py preview` | 通过，五份正文生成 43 块，已保存 `chunks.json` |
| 新增知识库单元测试 | 12 条通过 |
| `python scripts/check_project.py` | 通过：34 条 Python 测试、7 条 JavaScript 测试、语法和空白检查、前端构建 |
| 后端虚拟环境执行 `ingest --device cpu` | 失败：导入 Chroma 时发生 `PermissionError`，未进入模型编码 |
| 活动索引与真实检索 | 未生成 `active-index.json`；真实持久化、重复入库和检索命中待本机验证 |

当前 Agent 会话导入已安装 Chroma 时，读取 `backend/.venv/Lib/site-packages/chromadb/__init__.py` 被系统拒绝。因此不能据单元测试宣称已经生成真实向量或完成数据库持久化；需在用户本机终端执行上述入库与查询命令并保存实际输出。

当前返回 top-k 候选，没有标定“无适用依据”的距离阈值，也没有 LLM 答复。空候选会返回空数组；有候选不意味着问题已经有充分依据。无依据、跨条款组合及拒答能力仍需后续评测。

官方接口参考：[PersistentClient](https://docs.trychroma.com/reference/python/client)、[向量与原文写入](https://docs.trychroma.com/docs/collections/add-data)、[集合配置](https://docs.trychroma.com/docs/collections/configure)。
