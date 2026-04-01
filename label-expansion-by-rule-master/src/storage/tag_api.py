import asyncio

from aiohttp import ClientSession
from nb_util.logging.helper import get_logger


class TagAPI:
    def __init__(self, config: dict):
        self.url = config.get("url")
        self.headers = {"Content-Type": "application/json", "token": config.get("token")}
        self.session = ClientSession(self.url)
        self._batch = int(config.get("batch", 50) or 50)
        self.logger = get_logger("TagAPI")

    async def close(self):
        await self.session.close()

    async def get_tag_rels(
        self,
        chain: str,
        addr_list: list[str] | None = None,
        a_id: str | None = None,
        v_id: str | None = None,
    ):
        """
        获取标签关系。
        如果指定了地址列表，则将分批全部获取后返回。
        如果未指定地址列表，则最多获取 1000 条。
        :param chain: 链名称
        :param addr_list: 地址列表
        :param a_id: 标签属性 ID，用于通过标签类型过滤
        :param v_id: 标签属性值 ID，用于通过标签类型过滤
        """

        router = "/api/v1/tag/get_tag_rels"
        result = []
        try:
            body = {
                "chain": chain,
                "addresses": [],
                "page_size": 1000,  # 万一一个地址对应几条标签，因此这里设置比 step 大，避免分页时遗漏数据
                "page_num": 1,
            }
            if a_id:
                body["a_id"] = a_id
            if v_id:
                body["v_id"] = v_id

            if not addr_list:
                async with self.session.post(router, headers=self.headers, json=body, ssl=False) as resp:
                    json_resp = await resp.json(content_type=None)
                    result = json_resp.get("data", {}).get("tags", [])
                return result

            step = 100
            for i in range(0, len(addr_list), step):
                batch_addr = addr_list[i : i + step]
                async with self.session.post(
                    router, headers=self.headers, json=dict(body, **{"addresses": batch_addr}), ssl=False
                ) as resp:
                    json_resp = await resp.json(content_type=None)
                    batch_tags = json_resp.get("data", {}).get("tags", [])
                    result.extend(batch_tags)

        except Exception as e:
            self.logger.exception(f"获取标签失败：{str(e)}")

        return result

    async def add_tag_rel(self, body):
        router = "/api/v1/tag/add_tag_rel"
        async with self.session.post(router, headers=self.headers, json=body, ssl=False) as resp:
            if 200 <= resp.status < 300:
                json_resp = await resp.json(content_type=None)
                if json_resp.get("code") not in [0, 105]:
                    self.logger.error(f"标签添加失败：{json_resp.get('msg', '未知错误')}")
                return json_resp
            else:
                self.logger.error(f"服务未正确响应，状态码 {resp.status}")
                return None

    async def batch_add_tag_rel(self, bodies: list[dict]):
        if not bodies:
            return

        for i in range(0, len(bodies), self._batch):
            batch = bodies[i : i + self._batch]
            try:
                tasks = [asyncio.create_task(self.add_tag_rel(body)) for body in batch]
                await asyncio.gather(*tasks)
            except Exception as e:
                self.logger.error(f"批量添加标签时发生错误：{e}")
