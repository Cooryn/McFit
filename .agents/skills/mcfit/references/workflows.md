# 可执行对话流程

入口、字段见contracts.md。所有Python调用用输入文件或stdin；临时文件放MCFIT_DATA_DIR或私有目录，用完清除。confirmed和history_consent等字段只能反映真实用户确认，不能由助手默认填true。

## 建档/更新

“我21岁，男，175cm，60kg，想增肌到65kg，每周练4次。”→parse-profile，获得年龄/身高/当前和目标体重/训练习惯/目标。询问尚缺的公式参数与日常活动，每次一个；不因“男”自动选参数。体脂可空。无单位不猜；目标体脂不当当前体脂。

复述换算摘要及默认均衡/弹性预算，用户确认后save-profile。本地随机UUID不使用手机号。今后“现在60kg了”“默认预算改28元”：get-profile→parse-profile(existing)→确认更新。无需体重趋势表。

## 普通、带条件和训练推荐

“推荐一顿麦当劳午餐”：get-profile→parse-request→RecommendationRequest继承档案默认值。核对MCP并取得营养/明确缓存时间→normalize-foods→recommend。没有档案时只补最低必需字段。

“预算25元，高蛋白，不要牛肉”：预算本次覆盖，高蛋白本地解析默认30g**软偏好**，用户可改；牛肉为硬排除。未知成分不放行。无可靠参考价格时只能展示独立营养备选，不能说25元内。

“刚练完胸”：post；“两小时后跑步”：pre；“今天休息”：rest。Codex可理解更丰富表达，将结构化场景传入，不追加运动消耗。解析器不是通用中文理解模型，遇到否定、复杂过敏描述和新单位须由Codex核对。

“第二套去掉含糖饮料，650 kcal以内”：取第二套及原request，识别要去掉的ID，replacement-request保留其他餐品数量；parse-request(previous)追加饮料排除和maximum_kcal。没有可行替换时解释，不放宽其他限制。

“再来两套便宜的”：用more-request保留原约束并排除所有前次ID/食品集合，recommendation_count=2，strategy=price；无价格降级，不能虚称便宜。自然语言数词支持一/两/二/三/四/五及阿拉伯数，其他情况Codex映射。

## 订单导入与手动补录

“从历史订单整理最近吃过的”：先说明需要只读账号订单并取得授权，然后mcp-policy与order-list。补详情需进一步同意query-order。消除联系方式/地址等无关字段，优先官方food_id匹配，别名需审核，模糊结果只能unknown。

prepare-order-import只创建pending；展示食品/规格/订购数量/匹配可靠性，问本人实际吃的份额、具体时间和归属金额。分食可.5份，饮料未喝可0；金额单独确认，不默认按份数分摊。confirmed=true后confirm-consumption写快照。

“昨天午饭吃一份…和中薯”：Codex按当前Asia/Shanghai日期解析昨天，请确认具体时间或午饭约定时间，人工匹配规格，source=manual、随机来源UUID，同样pending→确认。未匹配营养保持null，允许保存真实吃过但营养未知的记录，不生成虚假可靠汇总。

取消/退款订单不自动视为吃过；确实食用需手动记录并确认实际金额。改份额/时间用replace=true；未食用或误记用retract-consumption。重复导入不覆盖已确认记录。

## 统计、导出、删除

“本月花多少、多少蛋白质”：report month、上海本地anchor；只说已记录麦当劳已知小计与未知条目/覆盖比例，不能表示全天总摄入或完整月支出。

export可JSON或CSV，提醒其含个人数据，写用户指定私有路径；delete确认后删除该UUID的个人表和消费记录，clear-cache清食品缓存。删除不保证清除用户自行生成的导出文件或系统备份，需另行管理。
