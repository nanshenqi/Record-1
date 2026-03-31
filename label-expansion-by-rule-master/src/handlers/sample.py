from .base import Handler


class SampleHandler(Handler):
    async def run(self):
        self.logger.info("Running SampleHandler")
        address = "0xc727eb69ccf89d5911042f21be25a193d67e2c23"
        token = "0xdac17f958d2ee523a2206206994597c13d831ec7"

        # 查询 doris 数据
        _, table = self.storage.doris.get_db_table("balance", self.chain)
        sql = f"SELECT balance FROM {table} WHERE address = %s AND token = %s"
        args = [address, token]
        doris_res = await self.storage.doris.search("balance", self.chain, sql, args)
        self.logger.info(f"Doris query result: {doris_res}")

        # 查询 es 数据
        sized_query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"to": address}},
                        {"term": {"send_token": token}},
                    ]
                }
            },
            "size": 3,
        }
        es_res = await self.storage.es.search("transfer", self.chain, sized_query)
        self.logger.info(f"ES search result: {es_res}")

        # 查询 es 数据（使用 iter_search 迭代器查询）
        range_query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"to": address}},
                        {"term": {"send_token": token}},
                        {"range": {"block_time": {"gte": 1773186410, "lt": 1773186450}}},
                    ]
                }
            }
        }
        async for doc in self.storage.es.iter_search("transfer", self.chain, range_query):
            self.logger.info(f"ES iter_search result: {doc}")

        # 查询 mongo 数据
        coll = self.storage.mongo.coll("data", "token", self.chain)
        mongo_res = await coll.find_one(
            {"_id": token},
            {"_id": True, "name": True, "symbol": True, "decimal": True, "price": True, "cmc_price": True},
        )
        self.logger.info(f"Mongo query result: {mongo_res}")

        # 从 Mongo 查询可信币（价值币）
        reliable_tokens = await self.storage.mongo.get_reliable_tokens(self.chain, price_gt_0=True)
        reliable_samples = {k: v for i, (k, v) in enumerate(reliable_tokens.items()) if i < 3}  # 取前 3 个打印作为示例
        self.logger.info(f"Mongo reliable tokens: {reliable_samples}")

        # 查询标签接口
        tag_res = await self.storage.tag_api.get_tag_rels(self.chain, addr_list=[address])
        self.logger.info(f"Tag API query result: {tag_res}")
