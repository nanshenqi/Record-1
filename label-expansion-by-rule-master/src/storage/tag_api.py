import asyncio

from aiohttp import ClientSession
from nb_util.logging.helper import get_logger


class TagAPI:
    def __init__(self, config: dict):
        self.url = config.get("url")
        self.headers = {"Content-Type": "application/json", "token": config.get("token")}
        self.session = ClientSession(self.url)
        self.logger = get_logger("TagAPI")

    async def close(self):
        await self.session.close()

    async def get_tag_rels(self, chain: str, addr_list: list[str]):
        router = "/api/v1/tag/get_tag_rels"
        result = []
        try:
            step = 100
            for i in range(0, len(addr_list), step):
                batch_addr = addr_list[i : i + step]
                body = {
                    "chain": chain,
                    "addresses": batch_addr,
                    "page_size": 1000,  # 万一一个地址对应几条标签，因此这里设置比 step 大，避免分页时遗漏数据
                    "page_num": 1,
                }
                async with self.session.post(router, headers=self.headers, json=body, ssl=False) as resp:
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
        for i in range(0, len(bodies), self._batch):
            batch = bodies[i : i + self._batch]
            try:
                tasks = [asyncio.create_task(self.add_tag_rel(body)) for body in batch]
                await asyncio.gather(*tasks)
            except Exception as e:
                self.logger.error(f"批量添加标签时发生错误：{e}")
