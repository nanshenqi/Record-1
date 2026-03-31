from nb_conn.doris.async_helper import AsyncDoris
from nb_util.logging.helper import get_logger


class DorisStorage:
    def __init__(self, config: dict, chain_instance_mapping: dict):
        self.config = config
        self._clients = {}
        self._data_map: dict = self.config.get("data_map")
        self._chain_instance_mapping = chain_instance_mapping
        for k, v in self.config.items():
            if k.startswith("client"):
                self._clients.setdefault(k, {})
                for db in self.config.get("dbs", []):
                    self._clients[k][db] = AsyncDoris(dict(v, **{"db": db}))

        self.logger = get_logger("DorisStorage")

    async def close(self):
        for client in self._clients.values():
            for db_client in client.values():
                await db_client.close()

    def get_db_table(self, data_key: str, chain: str) -> tuple[str, str]:
        if db_info := self._data_map.get(data_key, {}).get(chain):
            return db_info["db"], db_info["table"]
        raise ValueError(f"Doris db/table not found for data_key: {data_key}, chain: {chain}")

    async def search(
        self,
        data_key: str,
        chain: str,
        sql: str,
        args: list | tuple | None = None,
    ) -> list[dict]:
        """
        指定 SQL 查询 Doris 数据库
        :param data_key: 数据键，用于获取对应的 Doris DB 名称
        :param chain: 链标识符（不同链可能对应不同的 Doris 实例，需要指定链用以获取对应的 Doris 实例连接）
        :param sql: SQL 查询语句，可以包含占位符（如 %s）以接受参数，可以使用 {{table}} 占位符来动态替换表名
        （如 "SELECT * FROM {{table}} WHERE id = %s"）
        :param args: SQL 查询参数，可选
        :returns: 查询结果列表，每个元素为一个字典，键为列名或 SQL 中指定的别名
        """
        client_name = self._chain_instance_mapping.get(chain)
        db, table = self.get_db_table(data_key=data_key, chain=chain)
        client: AsyncDoris = self._clients.get(client_name, {}).get(db)
        if not client:
            raise ValueError(f"Doris client not found, chain: {chain}, client: {client_name}, db: {db}")
        sql = sql.replace("{{table}}", table)
        return await client.execute(sql, args, fetch_all=True)
