# 导入异步 IO 模块，用于处理异步操作
import asyncio

# 导入配置加载模块，用于加载和合并配置
from nb_frame.star.config import LoadConfig

# 导入默认配置
from config import config

# 导入所有处理器类
from handlers import *  # noqa

# 规则处理器映射字典
# 键为规则名称，值为对应的处理器类
rule_handler = {
    "sample": SampleHandler,  # 示例规则处理器
    "hot_wallet_analysis": HotWalletAnalysisHandler,  # 热钱包分析规则处理器
    "payment_institution_analysis": PaymentInstitutionAnalysisHandler,  # 支付机构和金融托管分析规则处理器
    "deposit_filter": DepositFilterHandler,  # 错误充币过滤规则处理器
}


async def main():
    """
    主函数
    1. 加载配置
    2. 获取服务配置和规则类型
    3. 根据规则类型选择对应的处理器
    4. 执行处理器的 run 方法
    5. 无论执行结果如何，都关闭处理器
    """
    # 加载配置，优先级：环境变量 > 本地配置 > 默认配置
    merged_config = LoadConfig.load_config(config)

    # 获取服务配置
    service_config = merged_config.get("SERVICE_CONFIG")
    # 获取要执行的规则类型
    rule = service_config.get("rule")
    # 根据规则类型获取对应的处理器类
    handler_cls = rule_handler.get(rule)
    # 创建处理器实例
    handler = handler_cls(merged_config)

    try:
        # 执行处理器的 run 方法
        await handler.run()
    finally:
        # 关闭处理器，释放资源
        await handler.close()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
