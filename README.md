# McFit

## 项目介绍

McFit 是面向麦当劳中国单餐的 Codex Skill，帮助用户结合营养目标、餐品偏好和可核实的参考预算选择一餐。

- 支持增肌、减脂、维持体重和体态重塑四类目标，以 Python 确定性计算估算单餐需求。
- 提供营养优先、价格优先和均衡推荐三种策略，支持餐品排除、方案替换和新增候选。
- 使用麦当劳官方 MCP 查询营养；价格无法核实时明确标注，不承诺满足预算。
- 经用户确认后保存本地档案和实际摄入记录，支持日、周、月统计与数据导出。

项目目前为开发预览版：已完成真实 MCP 营养查询，本地计算和记录流程可离线运行，真实数据到推荐的完整适配仍在完善。仅供个人学习与单餐参考，非麦当劳官方产品，不提供下单、支付或全天饮食计划。

## 安装方法

需要 Python 3.11+、Git 和支持项目级 Skill 的 Codex。核心脚本只依赖 Python 标准库。

克隆项目并创建虚拟环境：

```bash
git clone https://github.com/Cooryn/McFit.git
cd McFit
python -m venv .venv
```

Windows PowerShell 检查命令入口：

```powershell
.\.venv\Scripts\python.exe .agents/skills/mcfit/scripts/cli.py --help
```

Linux/macOS 使用：

```bash
.venv/bin/python .agents/skills/mcfit/scripts/cli.py --help
```

在 Codex 中打开项目目录，加载 `.agents/skills/mcfit/SKILL.md`；若技能未显示，请新建会话。

使用真实营养查询前，到 [麦当劳 MCP 开放平台](https://open.mcd.cn/mcp) 获取 Token，并在启动 Codex 的进程环境中设置 `MCD_MCP_TOKEN`。将以下配置添加到用户级 `~/.codex/config.toml`：

```toml
[mcp_servers.mcdonalds]
url = "https://mcp.mcd.cn"
bearer_token_env_var = "MCD_MCP_TOKEN"
enabled_tools = ["list-nutrition-foods", "order-list", "query-order"]
```

`bearer_token_env_var` 填写环境变量名，真实 Token 不写入仓库。配置后重新启动 Codex，详细步骤见 [MCP 接入说明](.agents/skills/mcfit/references/mcp-integration.md)。用户资料默认保存在系统用户数据目录，也可通过 `MCFIT_DATA_DIR` 指定私有目录。

## 使用示例

在 Codex 对话中调用：

```text
$mcfit 帮我建立档案：我25岁，175cm，65kg，想增肌，日常久坐，每周力量训练3次。

$mcfit 推荐一顿麦当劳午餐，热量不超过650 kcal，蛋白质至少30g。

$mcfit 预算25元，不要薯条；价格无法核实时请明确说明。

$mcfit 第二套替换饮料，保留其他限制。

$mcfit 再给我两套不同的方案。

$mcfit 统计这个月我已确认记录的麦当劳蛋白质和已知金额。
```

首次建档会补齐必要信息、请用户选择公式参数，并在确认后保存。读取历史订单需要明确授权；只有本人确认实际食用的内容才计入摄入记录。统计仅覆盖已记录的麦当劳餐品。

无需连接 MCP，也可运行合成数据演示：

```powershell
.\.venv\Scripts\python.exe .agents/skills/mcfit/scripts/cli.py smoke --input tests/fixtures/synthetic.json
```

演示中的档案、餐品和价格均为合成测试数据，不代表真实麦当劳信息。Linux/macOS 将 Python 路径替换为 `.venv/bin/python`。

## 目标用户

- 希望结合热量、蛋白质等目标选择麦当劳单餐的一般健康成年人。
- 有明确餐品偏好，希望比较不同组合及可核实参考预算的用户。
- 希望维护本人已确认的麦当劳饮食记录、查看已知营养和金额统计的用户。
- 希望学习 Codex Skill、只读 MCP 编排与确定性营养计算的开发者。

营养结果是估算，不构成医疗诊断或专业营养处方。未成年人、妊娠或哺乳期、存在饮食障碍风险或需要疾病治疗饮食的用户，不适用常规自动营养指导；过敏原信息不足时不能保证餐品安全。
