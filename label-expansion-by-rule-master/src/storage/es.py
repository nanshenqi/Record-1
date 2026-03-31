from nb_conn.es.async_helper import AsyncEs
from nb_util.logging.helper import get_logger


class EsStorage:
    def __init__(self, config: dict, chain_instance_mapping: dict):
        self.config = config
        self._clients = {}
        self._data_map: dict = self.config.get("data_map")
        self._chain_instance_mapping = chain_instance_mapping
        for k, v in self.config.items():
            if k.startswith("client"):
                self._clients[k] = AsyncEs(**v)

        self.logger = get_logger("EsStorage")

    async def close(self):
        for client in self._clients.values():
            await client.close()

    def get_index(self, data_key: str, chain: str) -> str:
        """
        获取指定数据键和链对应的 Elasticsearch 索引名称
        :param data_key: 数据键
        :param chain: 链标识符
        :returns: Elasticsearch 索引名称
        """

        if index := self._data_map.get(data_key, {}).get(chain):
            return index
        raise ValueError(f"ES index not found for data_key: {data_key}, chain: {chain}")

    async def search(
        self,
        data_key: str,
        chain: str,
        query: dict,
        timeout: str = "60s",
        request_timeout: int = 60,
    ) -> list[dict]:
        """
        指定请求体查询 Elasticsearch 索引中的数据
        ES 普通查询限制最大返回 10000 条数据，适用于查询条件较精确，查询结果数可控的场景
        该普通查询的优势是更轻量，对 ES 服务端的压力较小
        :param data_key: 数据键，用于获取对应的 ES 索引名称
        :param chain: 链标识符（不同链可能对应不同的 ES 实例，需要指定链用以获取对应的 ES 实例连接）
        :param query: 查询条件
        :param timeout: 查询超时时间，默认 "60s"
        :param request_timeout: 请求超时时间，默认 60 秒
        :returns: 查询结果
        """

        client_name = self._chain_instance_mapping.get(chain)
        client: AsyncEs = self._clients.get(client_name)
        if not client:
            raise ValueError(f"ES client not found, chain: {chain}, client: {client_name}")

        index = self.get_index(data_key=data_key, chain=chain)
        docs = await client.search_index_docs(index=index, body=query, timeout=timeout, request_timeout=request_timeout)
        return [doc["_source"] for doc in docs.get("hits", {}).get("hits", [])]

    async def iter_search(
        self,
        data_key: str,
        chain: str,
        query: dict,
        size: int = 2000,
        keep_alive: str = "1m",
    ):
        """
        指定请求体，通过迭代器分页查询 Elasticsearch 索引中的数据
        通过类似轻量级视图的机制配合分页，保证大量数据查询时的搜索结果一致性，通常用于全量查询或导出场景
        该迭代器查询的优势是可以查询超过 10000 条的数据，但对 ES 服务端的压力相对较大
        :param data_key: 数据键，用于获取对应的 ES 索引名称
        :param chain: 链标识符（不同链可能对应不同的 ES 实例，需要指定链用以获取对应的 ES 实例连接）
        :param query: 查询条件
        :param size: 每次批量查询的文档数量，默认 2000
        :param keep_alive: 游标保持时间，默认 "1m"
        :returns: 查询结果
        """

        client_name = self._chain_instance_mapping.get(chain)
        client: AsyncEs = self._clients.get(client_name)
        if not client:
            raise ValueError(f"ES client not found, chain: {chain}, client: {client_name}")

        index = self.get_index(data_key=data_key, chain=chain)
        async for hit in client.iter_search(index=index, query=query, size=size, keep_alive=keep_alive):
            yield hit.get("_source", {})
