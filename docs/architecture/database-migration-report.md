# 第20轮：统一业务数据库迁移记录

日期：2026-10-29。使用本机.env配置的真实MySQL，未输出凭据，未修改旧JSON、旧SQLite及上传原件。迁移清单见database-migration-result.json，真实MySQL测试摘要见mysql-test-result.json。

## 结果

| 对象 | 迁移数量 |
| --- | ---: |
| 企业 | 4 |
| 申请 | 7 |
| 材料（旧材料与上传记录） | 23 |
| 报告 | 3 |
| 初始状态事件 | 8 |
| 复核动作 | 6 |
| 教学知识版本 | 1 |

所有迁移字段与源快照逐项一致，7笔申请的当前状态与迁移前一致。APP-DEMO-001/002保持待审批，003保持待企业补充材料，其余保持待风控复核。此次没有材料版本冲突。第二次apply返回already_migrated，没有重复写入或覆盖新数据。

首次备份：backend/.data/migration-backups/20261029T111946621213Z。重复验证也生成独立备份，路径记录在JSON清单。SQLite使用backup API生成一致快照；上传原件保留原位置。切换后必须重启旧后端进程，避免旧进程继续写旧SQLite。

## 代码与行为

- db/models.py定义实际8张表、外键和索引；db/session.py管理连接与启动验证；db/migration.py显式事务迁移，失败回滚业务记录。
- repositories/sql_business.py和sql_documents.py统一业务存储；api/dependencies.py装配，main.py在生命周期检查连接，数据库运行错误返回503且不暴露内部连接信息。
- 材料适配器使用统一版本；风险规则在调用时取得统一存储入口，避免缓存旧测试存储。CLI风险检查也读取数据库。
- DocumentStore直接指向SQLDocumentStore，取消按参数切换SQLite。旧SQLite连接、DDL及读写实现已移至app/legacy_sqlite，构造必须显式提供临时路径，仅供旧格式隔离测试。Service不再导入旧ReviewStore。验证脚本verify_document_workflows也改走统一SQL Repository。
- 申请详情与上传接口保持原契约；两个Workflow和工具读取相同MySQL业务来源。Chroma与原件文件无需搬入关系库。
- 普通测试通过scripts/run_unit_tests.py注入隔离临时数据库；真实MySQL测试通过scripts/verify_mysql_storage.py创建随机独立数据库并清理，仅操作自身创建的测试库。

## 验证

- 迁移前基线：131条Python测试、15条JS测试及前端构建通过。
- 真实MySQL存储：9条测试通过，覆盖读取/重连状态、重复迁移保留新动作、来源变化拒绝、外键、版本唯一约束、迁移失败全量回滚、上传幂等/解析失败、重复复核、并发只成功一次。
- 真实MySQL HTTP双Workflow：正常、正文不符合、金额不一致3组真实文件用例通过。模型关闭，不产生API费用；此项验证持久化接入和规则链路，不代表重新评测模型正确率。
- 实际迁移库只读HTTP验证：health、企业、申请列表、APP-DEMO-002详情和APP-DOC-NORMAL材料接口均返回200；应用生命周期连接验证通过。
- 目录收尾后完整检查：141条Python用例中140条通过、1条MySQL专属并发用例跳过；15条JavaScript测试和前端构建通过。该并发用例已在真实MySQL专项执行通过。接口联调使用ASGI HTTP客户端，不等同于浏览器或真实TCP端口验证。
- 收尾实测：连接dialect为mysql，运行时为ApplicationRepository、ReviewRepository、SQLDocumentStore，读取7笔申请。新增架构测试禁止业务层引用legacy_sqlite；真实MySQL的9条存储用例和3组双Workflow用例重新通过。

## 环境问题与剩余限制

1. 当前Agent执行环境加载backend/.venv中的orjson DLL被系统拒绝，导致该解释器无法导入FastAPI。迁移本身在项目虚拟环境成功；HTTP/真实MySQL测试使用已能运行项目检查的全局Python，并从现有虚拟环境加载PyMySQL。实际执行命令如下，未修改或绕过DLL加载策略：

```powershell
python -c "import fastapi, sys, runpy; sys.path.append('backend/.venv/Lib/site-packages'); runpy.run_path('scripts/verify_mysql_storage.py', run_name='__main__')"
```

2. python-dotenv显式加入pyproject，但uv lock在线更新被网络权限错误10013阻止，离线缓存也不完整。未宣称uv.lock已同步；用户终端具备网络后应在backend执行`python -m uv lock`和`python -m uv sync`。已有环境中依赖可用。
3. 本次保留连接中现有账号，未创建或替换专用低权限账号。生产账号授权、真实用户认证、数据库服务部署加固不在本轮。
4. MySQL DDL自动提交，失败可能留下空表；业务导入有事务。上传进程被强制终止可能留下孤立文件，普通事务失败已清理新文件。后续表变更必须用版本迁移，不能依赖create_all升级。
5. 旧数据保留不等于自动双写回滚。若切换后已有新数据，不能直接切回旧源，否则新动作会丢失；应先备份MySQL并核对差异。
