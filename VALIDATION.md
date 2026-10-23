# 实际验证记录

日期：2026-10-23；Windows、Python 3.12、pytest 9.1.1。

最终执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp private/pytest-run-2
# 51 passed in 1.49s

.\.venv\Scripts\python.exe -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .agents/skills/mcfit
# Skill is valid!

.\.venv\Scripts\python.exe .agents/skills/mcfit/scripts/cli.py --help
.\.venv\Scripts\python.exe .agents/skills/mcfit/scripts/cli.py smoke --input tests/fixtures/synthetic.json
```

Skill校验器路径随安装位置变化；`-X utf8`避免Windows默认GBK读取中文Skill失败。CLI在参数解析前设置UTF-8，使中文帮助正常输出。

初次运行42通过、6个setup错误，原因为沙箱系统临时目录不可写。改用项目专用`--basetemp private/...`后48通过；追加负数输入、后续方案食品集合去重及数据范围隔离回归后51通过。没有跳过失败用例。初始系统Python别名不可执行，改用已安装的应用Python建立虚拟环境；ensurepip失败后通过该Python的pip为项目虚拟环境安装pytest和PyYAML。

## 需求到测试映射

| 验收项 | 验证位置 |
|---|---|
| 自然语言草稿、最低缺项、单位、确认门槛、改档 | test_nutrition / test_storage |
| 四类目标、能量近似守恒、训练场景、不重复运动消耗 | test_nutrition |
| 热量/蛋白硬软区分、无解不放宽 | test_nutrition / test_optimizer |
| 三种排序与预期顺序 | test_optimizer::test_sorting |
| 默认三套、多样性、数量、替换、新方案去重 | test_optimizer |
| 牛肉/薯条/糖饮排除、过敏原和交叉接触 | test_optimizer |
| 未知不是0、kJ和每100g、矛盾数据、重复ID | test_normalize / test_optimizer |
| 严格预算价格未知/过期、超额拒绝、弹性额外备选 | test_optimizer |
| 无价格降级、门店价格不复用、合成真实不混用 | test_optimizer |
| 订单只pending、重复导入/确认、部分食用、退款取消 | test_storage |
| 修改/撤回、已知小计和缺失覆盖率、日周月/时区 | test_storage |
| 401/缺Token/429/超时、白名单与授权模拟日志 | test_orders_and_workflows |
| 导出JSON/CSV、删除级联、隐私字段不持久化 | test_storage / test_orders_and_workflows |
| 三条中文输入到推荐、CLI子进程、错误不泄露正文 | test_orders_and_workflows |
| 手动补录→确认→导出→删除 | test_orders_and_workflows::test_manual_workflow_export_and_delete |

所有餐品、价格、档案为显式`synthetic:true`的合成测试数据。测试中的长期价格有效期只为避免测试随日期漂移，不可照搬到真实数据。

## 已核验与未核验

已核验：本地算法、SQLite事务及记录流程、CLI、文档链接、正式Skill元数据；新Skill已被Codex技能列表发现。官方文档明确了工具用途和接入方式。

后续真实验证：2026-10-23已完成一次`list-nutrition-foods({})`只读调用，返回success=true、code=200和160行营养文本。详情见[MCP_INTEGRATION.md](MCP_INTEGRATION.md)。这更新了开发初期服务不可用的状态。

仍未核验：实际营养计量基准、分页/完整覆盖、真实文本到推荐的端到端规范化、实际价格可用性，以及真实历史订单。未查询真实账号订单、未执行任何账号写操作。现有离线测试通过不代表[AUDIT.md](AUDIT.md)列出的缺口已修复。

限制：复杂自然语言由Codex核对结构化输入；当前订单单一摄入时间，跨时间拆分需人工补记；候选超过30项要求缩小范围；参考价不是结算承诺。完整使用与边界见README。
