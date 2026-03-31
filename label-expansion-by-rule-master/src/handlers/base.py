from nb_util.logging.helper import get_logger

from storage import Storage


class Handler:
    """
    基础处理器类
    所有规则处理器的基类，提供了配置管理和存储访问等基础功能
    """

    def __init__(self, config: dict):
        """
        初始化处理器
        :param config: 配置字典
        """
        self.config = config
        self.chain = config.get("CHAIN", "")
        self.service_config = config.get("SERVICE_CONFIG", {})
        self.storage_config = config.get("STORAGE_CONFIG", {})
        self.storage = Storage(self.storage_config)
        self.logger = get_logger("Handler")

    async def close(self):
        """
        关闭处理器，释放资源
        """
        await self.storage.close()

    async def run(self, *args, **kwargs):
        """
        执行处理器逻辑
        子类必须实现此方法
        """
        raise NotImplementedError("Subclasses must implement this method")
