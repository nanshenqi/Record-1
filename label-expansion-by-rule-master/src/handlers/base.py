from typing import Any

from nb_util.logging.helper import get_logger

from src.storage import Storage


class Handler:
    """规则处理器基类。

    当前仓库在不同规则之间共享同一套存储层封装（Doris / ES / Mongo / Tag API），
    因此基类仅负责保存公共上下文，避免在每个 handler 内重复拼装依赖。
    """

    def __init__(self, chain: str, storage: Storage, config: dict[str, Any]):
        self.chain = chain
        self.storage = storage
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

    async def run(self):
        raise NotImplementedError
