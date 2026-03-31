---
name: storage-access
description: '访问 Doris、Elasticsearch、MongoDB 或标签接口时使用。适用于选择 data_key、复用 self.storage 封装、编写查询等任务。'
---

# 数据访问技能手册

## 何时使用

- 需要为 handler 补充数据库或标签接口访问逻辑。
- 需要判断某个查询应走 Doris、ES、Mongo 还是 Tag API。
- 需要新增映射配置并保持与现有 Storage 封装一致。
- 需要排查查询代码是否误用了底层客户端或物理表名。

## 存储访问总原则

- 在 handler 中统一通过 self.storage 访问数据源。
- 优先使用 data_key 和 chain 选择资源，不要直接拼接物理实例信息。
- 新增映射时先复用现有分组名称和配置结构，避免重复配置。

## 访问策略

### Doris

- 适用于查询地址相关的数据，包含地址余额、地址统计、地址交易对手（每日或全局）等数据。
- 优先调用 self.storage.doris.search(data_key, chain, sql, args)。
- 必要时调用 get_db_table 获取映射后的 db 和 table。
- 查询返回值是字典列表，字段名来自列名或别名。

### Elasticsearch

- 适用于查询交易明细或行为数据。
- self.storage.es.search 适用于结果量可控的查询。
- self.storage.es.iter_search 适用于导出或大结果集遍历。
- 返回结果已经是 _source 列表，不需要再从 hits.hits 中手动取值。

### MongoDB

- 适用于查询代币（包含币价）、合约、LP 等静态或半静态数据。
- 使用 self.storage.mongo.coll(client_name, data_key, chain) 获取集合。
- data_key 必须来自 `src/config.py` 的 STORAGE_CONFIG.*.data_map，例如 token、contract、lp、reliable_token。
- 通用能力优先复用，如可信币获取使用 self.storage.mongo.get_reliable_tokens。

### Tag API

- 查询标签关系优先使用 self.storage.tag_api.get_tag_rels。
- 写入标签可使用 add_tag_rel 或 batch_add_tag_rel。
- 批量查询时优先沿用现有接口封装，不要在 handler 中重复分批逻辑。

## 相关文件

- `src/handlers/sample.py` 规则处理器调用存储样例
- `src/storage/__init__.py`
- `src/storage/doris.py`
- `src/storage/es.py`
- `src/storage/mongo.py`
- `src/storage/tag_api.py`
- `src/config.py` 中对应的 STORAGE_CONFIG.*.data_map
- `docs/database_knowledge_base.md` 数据库知识库，包含数据分布和结构说明

## 查询设计建议

1. 确定需要查询的数据源
2. 确定数据源是否已有 data_key 映射。
3. 确定输出是否适合复用现有 storage 方法。
4. 如果现有 data_key 不足，应先从数据库知识库中确认，再修改 `src/config.py` 中的 STORAGE_CONFIG.*.data_map。
5. 如果单一数据源的查询逻辑跨多个 handler 复用，优先抽取到对应的 `src/storage/*.py`。
6. 如果跨数据源的组合逻辑跨多个 handler 复用，抽取到 `src/utils/`。
7. 保持查询参数、别名和返回结构清晰，方便后续规则复用。

## 常见错误

- 在 handler 中直接实例化 AsyncDoris、AsyncEs 或 MongodbHelper 等。
- 调用异步查询方法或异步迭代器时忘记 await 或 async for。
- 直接把物理索引名、表名写死在多个 handler 中。
- 把 ES 返回值当成原始 hits 结构使用。
- 把 Doris 返回值当成二维数组使用。
- 编造数据库知识库中未曾说明的 data_map。

## 完成标准

- 查询代码可以通过 self.storage 落到正确的数据源。
- 物理资源选择来自映射配置，而不是散落在业务代码里的硬编码。
- 返回结构处理与现有 storage 封装保持一致。
- 如需新增映射，已在 `src/config.py` 中补齐并注明用途。
