# 本地JSON契约v1

完整类型在scripts/models.py；这不是尚未验证的官方MCP schema。所有输入顶层JSON对象，模型未知字段拒绝。

## 档案和推荐

- parse-profile `{text,existing?}` 返回draft/missing/next_question，不写入。save-profile `{profile,confirmed:true}`。更新先get-profile `{user_id}`，合并完整档案并保留UUID，摘要确认后保存。
- 必需Profile：age_years,height_cm,weight_kg,sex_for_equation（plus5/minus161）,goal_type（gain_muscle/lose_fat/maintain/recomposition）,activity_level（sedentary/light/moderate/active）。safety_flags记录需要暂停指导的风险，resistance_training需明确证据。其余可选见模型。
- parse-request `{text,previous?}`；nutrition-target `{profile或user_id,request?,meal_shares?}`；recommend `{profile或user_id,request?,foods:[规范食品]}`；smoke同recommend另加text，用于中文到求解离线验证。
- request：meal_type breakfast/lunch/dinner/snack/unspecified；strategy nutrition/price/balanced；workout_context pre/post/rest/unknown。energy_target_kcal/protein_target_g/fat_target_g/carbs_target_g软目标；maximum_kcal硬上限；minimum_protein_g默认软，protein_minimum_hard=true才为硬。未传预算/策略/餐次继承档案；显式budget_cny=null取消本次预算。
- excluded_foods追加档案排除；allergens不能放宽。清除长期偏好需确认更新档案。recommendation_count 1–10默认3；exclude_signatures排除以前方案ID。replacement-request `{previous_request,candidate,remove_ids}` 保留其余食品数量，然后parse-request叠加新限制再求解。

normalize-foods示例（**完全合成**）：
```json
{"bridge_version":1,"mapping_reviewed":true,"synthetic":true,"foods":[{"food_id":"synthetic-example","name":"合成测试餐品","source":"synthetic-fixture","observed_at":"2026-10-23T12:00:00+08:00","basis":"per_100g","serving_mass_g":200,"energy_unit":"kJ","energy":836.8,"protein_g":20,"fat_g":8,"carbs_g":12,"price_status":"unavailable","price_cny":null}]}
```
真实source=list-nutrition-foods且synthetic=false。basis per_serving或per_100g，后者需要serving_mass_g；ml没有质量不猜密度。energy标准化成kcal_per_serving，营养按份量缩放，单份价格不缩放。单位、转换和来源保留，未知null。套餐必须先人工确认并拆成不重叠单品。

allergens_verified包含成分和交叉接触核查，allergens/cross_contact为列表，ingredients_known/tags需要来源。uncertain匹配不用于可靠汇总。

verified/reference价格必填price_cny,price_scope,price_source,price_observed_at,price_valid_until,includes_discounts,includes_delivery；推荐只用china_reference当前有效价格。不知道有效期时保持unavailable，不随意延长。不可用金额必须null。

## 订单及记录

新增方案用 `more-request {previous_request,candidates,count:2}`，自动同时填 exclude_signatures 和 exclude_compositions（食品ID列表的列表），避免同样餐品换数量伪装新方案；再解析本次价格/营养偏好并求解。

prepare-order-import `{user_id,history_consent:true,detail_consent?:true,order,foods,aliases?}`，order示例（合成）：
```json
{"source":"order-list","source_key":"SYNTHETIC-ORDER-1","ordered_at":"2026-10-23T12:00:00+08:00","status":"completed","items":[{"line_id":"1","food_id":"synthetic-example","name":"合成测试餐品","quantity":1}]}
```
source可query-order/manual。手动source_key用稳定随机UUID，不需账号读取许可；状态paid/completed/manual可确认，cancelled/refunded不能直接确认。每行唯一line_id，单品，数量正值。paid_unit_price_cny需price_source，但不会自动变成摄入金额。编号优先，其次人工审核别名 `{名称|规格:food_id}`，未匹配营养未知。

pending `{user_id}` 查询。confirm-consumption `{user_id,pending_id,confirmed:true,consumed_at,selections:[{line_id,consumed_quantity,amount_cny?}],replace?:false}`。食用数量可.5等小数，不超过订单数量。金额单独确认，不按吃掉份额自动分摊。每个来源键一个摄入时间，selections支持不同餐品分食；同订单跨时间分次需手动不同UUID补记并避免重复。

重复导入返回原ID，重复确认报错。replace=true整体替换快照；retract-consumption `{user_id,pending_id,confirmed:true}` 撤回并保留去重墓碑。取消/退款但实际吃过须手动补录并核对金额。

report `{user_id,period:"day或week或month",anchor:"YYYY-MM-DD"}` 北京时间，周一/自然月。每指标known_subtotal/unknown_items/known_items/coverage_ratio，无条目coverage=null，已知小计0不等于完整0。

export `{user_id}` 支持--format csv，含敏感数据，仅写私有目录。delete `{user_id,confirmed:true}` 级联删除资料/设置/记录并VACUUM，不删除用户已导出的文件或系统备份。cache-put `{key,foods}`、cache-get `{key,ttl_seconds?}`、clear-cache `{}`。
