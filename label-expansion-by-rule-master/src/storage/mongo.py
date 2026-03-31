# 导入 MongoDB 异步助手模块，用于操作 MongoDB 数据库
from nb_conn.mongodb.async_helper import MongodbHelper
# 导入日志助手模块，用于创建和管理日志
from nb_util.logging.helper import get_logger


class MongoStorage:
    """
    MongoDB 存储类
    用于管理 MongoDB 连接和数据访问
    """
    
    def __init__(self, config: dict):
        """
        初始化 MongoStorage 实例
        :param config: 配置字典，包含 MongoDB 客户端和数据映射配置
        """
        # 存储配置信息
        self.config = config
        # 存储 MongoDB 客户端连接
        self._clients = {}
        # 存储数据映射配置
        self._mapping = {}
        
        # 遍历配置，初始化每个 MongoDB 客户端
        for k, v in config.items():
            # 创建并存储 MongoDB 客户端连接
            self._clients[k] = MongodbHelper(v["client"])
            # 存储数据映射配置
            self._mapping[k] = v["data_map"]

        # 创建日志记录器
        self.logger = get_logger("MongoStorage")

    async def close(self):
        """
        关闭所有 MongoDB 客户端连接
        """
        # 遍历所有客户端，关闭连接
        for client in self._clients.values():
            client.close()

    def client(self, client_name: str):
        """
        获取 MongoDB 客户端连接
        :param client_name: MongoDB 客户端名称（比如要访问数据 Mongo 则为 data，标签 Mongo 则为 tag，具体请参考配置）
        :returns: nb_conn.mongodb.async_helper.MongodbHelper
        """
        # 从客户端字典中获取指定名称的客户端
        if client := self._clients.get(client_name):
            return client

        # 如果客户端不存在，抛出异常
        raise ValueError(f"Invalid mongo client name: {client_name}")

    def coll(
        self,
        client_name: str,
        data_key: str,
        chain: str | None = None,
    ):
        """
        获取 MongoDB 的集合用于查询
        :param client_name: MongoDB 客户端名称（比如要访问数据 Mongo 则为 data，标签 Mongo 则为 tag，具体请参考配置）
        :param data_key: 数据标识（比如查询代币则为 token，合约则为 contract，具体请参考配置）
        :param chain: 链标识符，可选（部分数据没有分链存储，如可信币）
        :returns: motor.motor_asyncio.AsyncIOMotorCollection
        """
        # 获取指定名称的 MongoDB 客户端
        client = self.client(client_name)
        
        # 从数据映射中获取指定数据标识的配置
        if mapping := self._mapping[client_name].get(data_key):
            # 如果指定了链，且该链在映射中有配置
            if chain in mapping:
                # 获取数据库名和集合名
                db = mapping[chain]["db"]
                collection = mapping[chain]["collection"]
                # 返回对应的集合
                return client.collection(collection, db)
            # 如果映射中包含通配符配置
            elif "*" in mapping:
                # 获取通配符配置的数据库名和集合名
                db = mapping["*"]["db"]
                collection = mapping["*"]["collection"]
                # 返回对应的集合
                return client.collection(collection, db)

        # 如果无法找到对应的集合，抛出异常
        raise ValueError(f"Invalid mongo collection, client: {client_name}, data_name: {data_key}, chain: {chain}")

    async def get_reliable_tokens(self, chain: str, price_gt_0=False):
        """
        获取可信代币（又称为价值币）列表
        :param chain: 链标识符
        :param price_gt_0: 是否只要币价大于 0 的代币，默认为 False
        :returns: 可信代币字典，key 为代币地址，value 为代币信息，代币信息包含至少以下字段：decimal（精度，整数类型），price（币价，小数类型）
        """
        # 获取可靠代币集合
        reliable_coll = self.coll("data", "reliable_token")
        # 获取代币信息集合
        token_coll = self.coll("data", "token", chain)

        # 存储代币地址的集合
        tokens = set()
        
        # 遍历可靠代币集合，获取指定链的代币地址
        async for item in reliable_coll.find({"chain": chain}, {"token": True, "_id": False}):
            tokens.add(item["token"])

        # 存储结果的字典
        result = {}
        
        # 遍历代币信息集合，获取代币的精度和价格信息
        async for item in token_coll.find(
            {"_id": {"$in": list(tokens)}},
            {"_id": True, "decimal": True, "price": True, "cmc_price": True},
        ):
            # 优先使用 cmc_price，其次使用 price，都没有则使用 0
            price = item.get("cmc_price", 0) or item.get("price", 0) or 0
            
            # 如果只需要价格大于 0 的代币，且当前代币价格小于等于 0，则跳过
            if price_gt_0 and price <= 0:
                continue

            # 将代币信息添加到结果字典中
            result[item["_id"]] = {
                "decimal": item.get("decimal") or 18,  # 精度，默认为 18
                "price": price,  # 代币价格
            }
        
        # 返回可信代币字典
        return result
