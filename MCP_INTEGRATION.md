# McFit 与麦当劳 MCP 的集成

McFit 是面向麦当劳中国单餐的营养搭配 Codex Skill。由 Codex 直接调用官方 MCP，Python 负责确定性营养计算、组合搜索和本地记录，避免依靠语言模型心算或虚构价格。

## Server 与认证

- 官方服务：`https://mcp.mcd.cn`
- 协议：Streamable HTTP
- 认证：Authorization Bearer，通过启动 Codex 的进程环境变量 `MCD_MCP_TOKEN` 提供。
- 官方说明：[M-China/mcd-mcp-server](https://github.com/M-China/mcd-mcp-server)
- 配置示例：[mcp-config.example.json](mcp-config.example.json)；Codex 实际使用用户级 `~/.codex/config.toml`，见下文。

```toml
[mcp_servers.mcdonalds]
url = "https://mcp.mcd.cn"
bearer_token_env_var = "MCD_MCP_TOKEN"
enabled_tools = ["list-nutrition-foods", "order-list", "query-order"]
```

`bearer_token_env_var` 的值是环境变量名，不是 Token。仓库不包含真实凭据或个人订单。

## 实际工具与验证范围

| 工具 | 业务用途 | 当前验证状态 |
|---|---|---|
| `list-nutrition-foods` | 获取官方餐品营养，用于单餐决策支持 | 已完成真实只读调用 |
| `order-list` | 用户授权后将历史订单转为待确认摄入 | 仅离线模拟；未读取真实历史订单 |
| `query-order` | 明细不足且经用户同意后补齐订单 | 仅离线模拟；未做真实调用 |

2026-10-23，一次真实营养查询使用参数 `{}`；当时暴露的工具schema没有声明必填参数。返回 `success:true`、`code:200`、响应时间 `2026-10-23 14:32:56`，`data` 为带字段表头的160行文本，字段包括 productName、nutritionDescription、energyKj、energyKcal、protein、fat、carbohydrate、sodium、calcium。

该返回存在重复条目，没有官方食品ID、价格、过敏原或明确营养计量基准。此次证明了真实服务连接与营养查询可用，**不代表真实数据到推荐的完整端到端适配已验收**。当前规范化层接受经审核的内部桥接JSON，实际文本格式的严格解析、单位核验、稳定ID与去重仍需补齐；详见[AUDIT.md](AUDIT.md)。不将未知字段填0，也不凭名称推断过敏安全。

## 调用流程

1. Codex读取Skill，提取本餐需求；如需身体档案，先展示摘要并取得确认。
2. 检查当前工具schema，通过本地白名单策略检查后，调用官方营养工具。
3. 核对实际返回字段、单位、份量、来源时间及重复条目，将可核验数据映射至本地桥接JSON；无法确认的数据保持未知或暂停候选。
4. 执行 `normalize-foods`、`nutrition-target`、`recommend`，在Python中计算总量、筛选硬限制并排序。真实全量目录超过当前30项限制时，需要明确缩小候选范围。
5. 分开呈现可核实结果、弹性超预算备选与价格未知的营养备选；注明来源及时间。
6. 只有用户明确同意读取历史订单才调用订单工具；仅建立pending，用户确认实际食用的餐品、份额、时间和金额后才能记入统计。

流程与字段：[Skill](.agents/skills/mcfit/SKILL.md)、[本地契约](.agents/skills/mcfit/references/contracts.md)、[详细接入说明](.agents/skills/mcfit/references/mcp-integration.md)。

## 业务价值与限制

- 将官方营养信息转为可比较的单餐组合，支持增肌、减脂、维持及体态重塑的估算目标。
- 营养缺失、价格未知和过敏原不可核验会显式呈现，避免提供看似精确但无法证明的结论。
- 将账号订单与实际摄入分开，帮助用户维护本人确认的麦当劳饮食记录，而不声称涵盖全天饮食。
- 不获取定位或门店、不下单、不支付、不领券、不修改账号状态。当前响应无价格，无法承诺预算达标；历史订单金额不作为新餐报价。
- 401停止并提示检查环境；429尊重Retry-After并有限重试；超时使用标明日期的缓存或停止查询。不会把陈旧数据称为实时数据。

本项目使用Codex开发，没有使用WorkBuddy，因此不提供虚构的workbuddy.md或申请相关使用资格。项目输出仅作单餐参考，不构成专业诊疗或营养处方；已知实现缺口保留在公开审查报告中。
