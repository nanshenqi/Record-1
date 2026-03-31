from .doris import DorisStorage
from .es import EsStorage
from .mongo import MongoStorage
from .tag_api import TagAPI


class Storage:
    def __init__(self, config: dict):
        # Doris 和 ES 都有两个数据库实例，不同的链的数据分布在不同的实例上
        chain_inst_map = config.get("chain_instance_mapping")

        doris_conf = config.get("doris", {})
        self.doris = DorisStorage(doris_conf, chain_inst_map)

        es_conf = config.get("es", {})
        self.es = EsStorage(es_conf, chain_inst_map)

        mongo_conf = config.get("mongodb", {})
        self.mongo = MongoStorage(mongo_conf)

        tag_api_conf = config.get("tag_api", {})
        self.tag_api = TagAPI(tag_api_conf)

    async def close(self):
        await self.doris.close()
        await self.es.close()
        await self.mongo.close()
        await self.tag_api.close()
