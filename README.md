# McFit

可执行的麦当劳中国单餐营养 Codex Skill：中文建档/改参、四类目标估算、三种排序、硬约束配餐、替换/新增方案、只读MCP编排、SQLite待确认及已确认摄入、日周月统计和导出删除。仅个人学习、非商业用途，不是官方产品。

目标用户：希望依据官方营养信息选择麦当劳单餐、比较可核实的参考预算，或记录本人已确认摄入的一般健康成年人。特殊健康状况不适用自动营养指导。

当前为开发预览版：51项离线测试通过，已完成一次真实营养MCP查询；真实数据解析、跨工具订单去重等仍有已知缺口，见[AUDIT.md](AUDIT.md)，尚非全部需求验收通过的版本。

## 使用示例

在安装并连接麦当劳MCP后，可在Codex中输入：

```text
$mcfit 推荐一顿麦当劳午餐，热量不超过650 kcal，蛋白质至少30g。
$mcfit 预算25元，不要薯条；如果价格无法核实，请明确说明。
$mcfit 第二套替换饮料，保留其他限制。
$mcfit 统计这个月我已确认记录的麦当劳蛋白质和已知金额。
```

首次建档会先提取必要参数、核对单位并请求确认。历史订单不会自动读取；订单也不会自动计入摄入。没有真实MCP时，可运行下方合成数据演示，不代表真实餐品或价格。

## 安装与运行

Python 3.11+。核心代码只用标准库；pytest、PyYAML仅用于测试及Skill校验。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe .agents/skills/mcfit/scripts/cli.py --help
.\.venv\Scripts\python.exe -m pytest -q --basetemp private/pytest-local
.\.venv\Scripts\python.exe .agents/skills/mcfit/scripts/cli.py smoke --input tests/fixtures/synthetic.json
```

Linux/macOS将`.venv\Scripts\python.exe`替换为`.venv/bin/python`。`--basetemp`仅指向专用测试目录，pytest会清理它，不要指向个人数据目录。

在本项目启动Codex即可发现`.agents/skills/mcfit/SKILL.md`，用`$mcfit 推荐一顿麦当劳午餐`。本次开发中该Skill已进入应用技能列表。若刚复制到其他项目未发现，请重新开启会话。

每条CLI命令支持`--input <UTF-8 JSON文件>`，省略为stdin。数据库目录由`--data-dir`、`MCFIT_DATA_DIR`、系统用户目录依次决定。Windows默认`%LOCALAPPDATA%/McFit`；Linux默认`$XDG_DATA_HOME/mcfit`或`~/.local/share/mcfit`。不要把真实身体/订单数据写到项目。测试只用synthetic:true的合成资料。

## 入口与说明

- [正式Skill](.agents/skills/mcfit/SKILL.md)：工具选择及对话路由。
- [本地JSON契约](.agents/skills/mcfit/references/contracts.md)：所有命令参数和数据模型。
- [工作流](.agents/skills/mcfit/references/workflows.md)：建档、推荐、替换、待确认、记录和统计。
- [营养假设](.agents/skills/mcfit/references/nutrition-method.md)：公式来源、可配置常量、权重和安全范围。
- [MCP配置](.agents/skills/mcfit/references/mcp-integration.md)：用户级TOML、Windows/Ubuntu环境变量、只读白名单、缓存和错误降级。

核心命令：parse-profile、save-profile、get-profile、parse-request、nutrition-target、normalize-foods、recommend、replacement-request、more-request、prepare-order-import、pending、confirm-consumption、retract-consumption、report、export（JSON/CSV）、delete、cache-put/get/clear-cache、mcp-policy/error。档案更新保存完整合并结果；记录修改用replace:true。

## 数据与接口边界

2026-10-23已核对[Codex Skill规范](https://developers.openai.com/codex/skills)、[MCP配置规范](https://developers.openai.com/codex/mcp)和[麦当劳官方仓库](https://github.com/M-China/mcd-mcp-server)。开发初期服务不可用；随后已通过 `list-nutrition-foods({})` 完成真实只读营养查询，返回160行文本。**尚未完成真实数据规范化到推荐的端到端验收，未查询真实历史订单。** 详细工具、实际格式和业务价值见[MCP_INTEGRATION.md](MCP_INTEGRATION.md)。

真实接入需用户在启动Codex的进程环境提供MCD_MCP_TOKEN；代码不读取或保存Token。Python负责确定性本地计算，Codex直接调用已注册工具。订单读取须明确同意。菜单/计价依赖门店，因此不调用、不定位，价格默认未知；历史实付不能复用作新餐报价。

价格未知方案与合规结果分开；严格预算不放宽。营养未知不当零；未审核匹配不用于可靠汇总。过敏原/交叉接触无法核实即排除。未成年人、妊娠哺乳、疾病治疗饮食、饮食障碍风险不使用常规自动指导；极端限制拒绝。自然语言规则覆盖常见表达，复杂语义由Codex核对后输入结构化JSON，不能把规则解析器当通用理解模型。

不实现其他品牌、全天食谱、门店/库存/地址管理、购买支付、账号修改、长期体重趋势或后台监控。单个订单目前一个摄入时间；不同条目/分食份额可拆选，同订单跨时间分次需人工补记并去重。候选超过30项要求缩小范围。SQLite为本地明文，依赖操作系统账户权限；删除不包括用户导出副本和系统备份。

## 文件树

```text
.agents/skills/mcfit/
  SKILL.md
  references/{contracts,mcp-integration,nutrition-method,workflows,output-examples}.md
  scripts/
    cli.py models.py language.py nutrition.py normalize.py optimizer.py
    mcp_policy.py orders.py storage.py reporting.py
tests/
  fixtures/synthetic.json
  conftest.py test_nutrition.py test_normalize.py test_optimizer.py
  test_storage.py test_orders_and_workflows.py
pyproject.toml
.gitignore
README.md
VALIDATION.md
AUDIT.md
MCP_INTEGRATION.md
mcp-config.example.json
CONTEST_DECLARATION.md
```

开发临时目录private、测试数据库、.venv、缓存均被忽略。不要提交个人导出、用户config.toml或.env。详细执行结果与验收映射见[VALIDATION.md](VALIDATION.md)。

## 活动提交材料

按[官方活动规则](https://github.com/M-China/mcd-developer-innovation-challenge/blob/main/activityGuidelines.md)提供README、官方原样参赛声明、MCP集成说明和脱敏JSON示例。JSON中的 `${MCD_MCP_TOKEN}` 仅为环境变量占位符，是否自动展开取决于宿主；Codex应使用上文链接中的TOML配置，不能直接把JSON当成Codex配置文件。

仓库公开发布与提交报名Issue是两个步骤。请阅读官方规则及[参赛声明](CONTEST_DECLARATION.md)，并按实际资格提交报名；代码测试通过或仓库公开不代表活动方已接受报名。不提供WorkBuddy使用记录，因为本项目由Codex辅助开发。
