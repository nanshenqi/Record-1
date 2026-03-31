# 导入基础处理器类
# Handler类是所有规则处理器的基类，提供了配置管理和存储访问等基础功能
from .base import Handler
import pandas as pd  # 用于处理Excel输出
from enums.chain import EVMChain  # 导入EVM链枚举


class DepositFilterHandler(Handler):
    """
    错误充币过滤处理器
    用于过滤错误充币，包括排除钓鱼地址、冷钱包、实体错误的充币、类型错误的充币和历史未删除的充币
    """
    
    async def run(self):
        """
        执行错误充币过滤流程
        1. 获取热钱包地址列表
        2. 获取链必追定义的有价值代币列表
        3. 获取钓鱼代币货币篮子
        4. 获取所有充币地址
        5. 应用过滤规则
        6. 输出结果
        """
        self.logger.info("Running DepositFilterHandler")
        
        # 从配置中获取热钱包地址列表
        hot_wallets = self.config.get("HOT_WALLETS", {}).get(self.chain, [])
        
        # 如果配置中没有，尝试从数据库获取
        if not hot_wallets:
            hot_wallets = await self.get_hot_wallets_from_db()
        
        if not hot_wallets:
            self.logger.error("未获取到热钱包地址，无法继续执行")
            return
        
        self.logger.info(f"使用的热钱包地址: {hot_wallets}")
        
        # 1. 获取链必追定义的有价值代币列表
        self.logger.info("正在获取链必追定义的有价值代币...")
        chain_defined_valuable_tokens = await self.get_valuable_tokens()
        
        if not chain_defined_valuable_tokens:
            self.logger.warning("未获取到链必追定义的有价值代币")
        else:
            self.logger.info(f"获取到的有价值代币数量: {len(chain_defined_valuable_tokens)}")
        
        # 2. 获取钓鱼代币货币篮子
        self.logger.info("正在获取钓鱼代币货币篮子...")
        phishing_tokens = await self.get_phishing_tokens()
        
        # 3. 获取所有充币地址
        self.logger.info("正在获取所有充币地址...")
        deposit_addresses = await self.get_deposit_addresses()
        
        if not deposit_addresses:
            self.logger.warning("未获取到充币地址")
            return
        
        self.logger.info(f"获取到{len(deposit_addresses)}个充币地址")
        
        # 4. 应用过滤规则
        self.logger.info("正在应用错误充币过滤规则...")
        filter_result = await self.apply_filter_rules(
            deposit_addresses, hot_wallets, chain_defined_valuable_tokens, phishing_tokens
        )
        
        # 5. 输出结果
        self.logger.info("正在输出过滤结果...")
        await self.export_filter_result(filter_result)
    
    async def get_hot_wallets_from_db(self):
        """
        从数据库获取热钱包地址列表
        注意：当前知识库中没有定义hot_wallets表，
        此方法暂时返回空列表，需要根据实际情况修改
        :return: 热钱包地址列表
        """
        hot_wallets = []
        try:
            # 暂时返回空列表，需要根据实际情况修改
            # 后续可以从合适的表中获取热钱包地址
            self.logger.warning("当前知识库中没有定义hot_wallets表，暂时返回空列表")
        except Exception as e:
            self.logger.error(f"从数据库获取热钱包地址失败: {str(e)}")
        return hot_wallets
    
    async def get_valuable_tokens(self):
        """
        获取链必追定义的有价值代币列表
        :return: 有价值代币列表
        """
        valuable_tokens = set()  # 存储有价值代币列表
        
        try:
            # 使用EVMChain枚举获取链列表，确保使用正确的链名称
            chains = [chain.value for chain in EVMChain] + ["tron", "solana"]  # 使用solana而不是sol
            
            for chain in chains:
                # 调用get_reliable_tokens获取该链的可信代币
                reliable_tokens = await self.get_reliable_tokens(chain, price_gt_0=True)
                # 提取代币地址并格式化为"链:代币地址"的形式
                for token_address in reliable_tokens.keys():
                    token_key = f"{chain}:{token_address}"
                    valuable_tokens.add(token_key)
        except Exception as e:
            self.logger.error(f"获取有价值代币列表时出错: {str(e)}")
        
        return list(valuable_tokens)
    
    async def get_reliable_tokens(self, chain: str, price_gt_0=False):
        """
        获取可信代币（又称为价值币）列表
        :param chain: 链标识
        :param price_gt_0: 是否只要币价大于 0 的代币，默认为 False
        :returns: 可信代币字典, key 为代币地址, value 为代币信息，代币信息包含至少以下字段: decimal（精度，整数类型）, price（币价，小数类型）
        """
        reliable_tokens = {}
        
        try:
            # 1. 从chain_info数据库的reliable_token表获取该链的币种列表
            chain_info_coll = self.storage.mongo.coll("chain_info", "reliable_token", "")
            chain_info = await chain_info_coll.find_one({"_id": chain})
            
            if chain_info:
                tokens = chain_info.get("reliable_token", [])
                
                # 2. 从具体链的token_v3表中获取价格和精度等信息
                token_coll = self.storage.mongo.coll("data", "token_v3", chain)
                
                for token_address in tokens:
                    # 查询代币信息
                    token_doc = await token_coll.find_one({"_id": token_address})
                    
                    if token_doc:
                        # 价格优先取cmc_price，取不到才取price
                        price = token_doc.get("cmc_price")
                        if price is None:
                            price = token_doc.get("price")
                        
                        # 检查价格条件
                        if price_gt_0 and (price is None or price <= 0):
                            continue
                        
                        # 构建代币信息
                        token_info = {
                            "decimal": token_doc.get("decimal", 0),
                            "price": price
                        }
                        
                        reliable_tokens[token_address] = token_info
        except Exception as e:
            self.logger.error(f"获取可信代币列表时出错: {str(e)}")
        
        return reliable_tokens
    
    async def get_phishing_tokens(self):
        """
        获取钓鱼代币货币篮子（稳定币+本币）
        稳定币定义：USDT、USDC、BUSD、DAI等主流稳定币
        :return: 钓鱼代币列表
        """
        phishing_tokens = set()
        
        try:
            # 使用EVMChain枚举获取链列表，确保使用正确的链名称
            chains = [chain.value for chain in EVMChain] + ["tron", "solana"]  # 使用solana而不是sol
            
            # 定义主流稳定币地址映射，后续可以从配置或数据库中获取
            stable_coins = {
                "eth": ["0xdAC17F958D2ee523a2206206994597C13D831ec7", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"],  # USDT, USDC
                "bsc": ["0x55d398326f99059fF775485246999027B3197955", "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"],  # USDT, USDC
                "polygon": ["0xc2132D05D31c914a87C6611C10748AEb04B58e8F", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"],  # USDT, USDC
                "avalanche": ["0xdAC17F958D2ee523a2206206994597C13D831ec7", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"],  # USDT, USDC
                "arbitrum": ["0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"],  # USDT, USDC
                "optimism": ["0x94b008aA00579c1307B0EF2c499aD98a8ce58e58", "0x7F5c764cBc14f9669B88837ca1490cCa17c31607"],  # USDT, USDC
                "tron": ["TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8"],  # USDT, USDC
                "solana": ["Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"]  # USDT, USDC
            }
            
            for chain in chains:
                # 添加本币
                phishing_tokens.add(chain)
                
                # 添加稳定币
                if chain in stable_coins:
                    for stable_coin in stable_coins[chain]:
                        token_key = f"{chain}:{stable_coin}"
                        phishing_tokens.add(token_key)
        except Exception as e:
            self.logger.error(f"获取钓鱼代币货币篮子时出错: {str(e)}")
        
        return list(phishing_tokens)
    
    async def get_deposit_addresses(self):
        """
        获取所有充币地址
        从标签接口获取具有充币标签的地址
        :return: 充币地址列表
        """
        deposit_addresses = []
        try:
            # 使用EVMChain枚举获取链列表，确保使用正确的链名称
            chains = [chain.value for chain in EVMChain] + ["tron", "solana"]  # 使用solana而不是sol
            
            for chain in chains:
                try:
                    # 从标签接口获取具有充币标签的地址
                    # 注意：这里需要根据实际的标签接口API进行修改
                    # 暂时使用一个模拟的实现
                    # 实际使用时，应该调用self.storage.tag_api的相应方法
                    # 例如：addresses = await self.storage.tag_api.get_addresses_by_tag('deposit', chain)
                    
                    # 模拟返回空列表，需要根据实际情况修改
                    self.logger.info(f"从标签接口获取{chain}链的充币地址")
                    # 这里应该添加实际的标签接口调用
                except Exception as e:
                    self.logger.warning(f"从标签接口获取{chain}链的充币地址时出错: {str(e)}")
        except Exception as e:
            self.logger.error(f"获取充币地址失败: {str(e)}")
        return deposit_addresses
    
    async def apply_filter_rules(self, deposit_addresses, hot_wallets, chain_defined_valuable_tokens, phishing_tokens):
        """
        应用错误充币过滤规则
        :param deposit_addresses: 充币地址列表
        :param hot_wallets: 热钱包地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :param phishing_tokens: 钓鱼代币货币篮子
        :return: 过滤结果
        """
        # 初始化过滤结果
        filter_result = {
            "phishing_addresses": [],  # 历史误标为充币的钓鱼地址
            "cold_wallets": [],  # 历史误标为充币的冷钱包
            "entity_error_deposits": [],  # 实体错误的充币
            "type_error_deposits": [],  # 类型错误的充币
            "unremoved_deposits": [],  # 历史未删除的充币
            "valid_deposits": []  # 有效的充币
        }
        
        for addr_info in deposit_addresses:
            address = addr_info.get('address')
            chain = addr_info.get('chain')
            
            # 规则1：排除历史误标为充币的钓鱼地址
            if await self.is_phishing_address(address, chain, hot_wallets, phishing_tokens):
                filter_result["phishing_addresses"].append(addr_info)
                continue
            
            # 规则2：筛历史误标为充币的冷钱包
            if await self.is_cold_wallet(address, chain, chain_defined_valuable_tokens):
                filter_result["cold_wallets"].append(addr_info)
                continue
            
            # 规则3：筛实体错误的充币
            if await self.has_entity_error(address, chain, hot_wallets):
                filter_result["entity_error_deposits"].append(addr_info)
                continue
            
            # 规则4：筛类型错误的充币
            if await self.has_type_error(address, chain):
                filter_result["type_error_deposits"].append(addr_info)
                continue
            
            # 规则5：筛历史未删除的充币
            if await self.is_unremoved_deposit(address, chain, hot_wallets):
                filter_result["unremoved_deposits"].append(addr_info)
                continue
            
            # 所有规则都通过，认为是有效的充币
            filter_result["valid_deposits"].append(addr_info)
        
        return filter_result
    
    async def is_phishing_address(self, address, chain, hot_wallets, phishing_tokens):
        """
        规则1：排除历史误标为充币的钓鱼地址
        该地址跟所有热钱包的出向交易的总交易金额/总交易笔数折算为U，价值小于1.5U。（该条件仅针对钓鱼代币货币篮子）
        :param address: 地址
        :param chain: 链
        :param hot_wallets: 热钱包地址列表
        :param phishing_tokens: 钓鱼代币货币篮子
        :return: 是否是钓鱼地址
        """
        try:
            # 获取该地址的交易统计信息
            stats = await self.get_address_stats(chain, [address])
            
            if address in stats:
                tx_count = stats[address].get('tx_count', 0)
                total_amount = stats[address].get('total_amount', 0)
                
                # 获取该地址的所有交易，检查是否使用了钓鱼代币
                transactions = await self.get_transactions(chain, from_address=address, limit=1000)
                is_phishing_token = False
                
                for tx in transactions:
                    token_address = tx.get('token_address')
                    if token_address:
                        token_key = f"{chain}:{token_address}"
                        if token_key in phishing_tokens:
                            is_phishing_token = True
                            break
                    else:
                        # 本币
                        if chain in phishing_tokens:
                            is_phishing_token = True
                            break
                
                if is_phishing_token and tx_count > 0 and (total_amount / tx_count) < 1.5:
                    return True
        except Exception as e:
            self.logger.warning(f"检查{address}是否是钓鱼地址时出错: {str(e)}")
        
        return False
    
    async def is_cold_wallet(self, address, chain, chain_defined_valuable_tokens):
        """
        规则2：筛历史误标为充币的冷钱包
        余额总价值（本币和来源热钱包的有价值代币）大于十万U。
        :param address: 地址
        :param chain: 链
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :return: 是否是冷钱包
        """
        try:
            # 获取地址余额
            total_balance_value = await self.get_address_balance_value(address, chain, chain_defined_valuable_tokens)
            
            # 余额总价值大于十万U
            if total_balance_value > 100000:
                return True
        except Exception as e:
            self.logger.warning(f"检查{address}是否是冷钱包时出错: {str(e)}")
        
        return False
    
    async def has_entity_error(self, address, chain, hot_wallets):
        """
        规则3：筛实体错误的充币
        去除0对手后，存在出向对手不是同一实体的热钱包。
        :param address: 地址
        :param chain: 链
        :param hot_wallets: 热钱包地址列表
        :return: 是否存在实体错误
        """
        try:
            # 获取该地址的转出交易
            transactions = await self.get_transactions(chain, from_address=address, limit=1000)
            
            # 去除0对手（金额为0的交易）
            non_zero_transactions = [tx for tx in transactions if tx.get('amount', 0) > 0]
            
            # 检查是否存在出向对手不是同一实体的热钱包
            # 这里需要根据实际情况检查对手是否是同一实体的热钱包
            # 暂时假设所有热钱包都是同一实体的
            
            # 检查是否存在出向对手不是热钱包的情况
            has_non_hot_wallet_opponent = False
            for tx in non_zero_transactions:
                to_address = tx.get('to_address')
                if to_address not in hot_wallets:
                    has_non_hot_wallet_opponent = True
                    break
            
            if has_non_hot_wallet_opponent:
                return True
        except Exception as e:
            self.logger.warning(f"检查{address}是否存在实体错误时出错: {str(e)}")
        
        return False
    
    async def has_type_error(self, address, chain):
        """
        规则4：筛类型错误的充币
        去除0对手后，存在出向对手具有非中心化交易所下的标签（例如支付机构、金融托管等等）。
        :param address: 地址
        :param chain: 链
        :return: 是否存在类型错误
        """
        try:
            # 获取该地址的转出交易
            transactions = await self.get_transactions(chain, from_address=address, limit=1000)
            
            # 去除0对手（金额为0的交易）
            non_zero_transactions = [tx for tx in transactions if tx.get('amount', 0) > 0]
            
            # 检查是否存在出向对手具有非中心化交易所下的标签
            for tx in non_zero_transactions:
                to_address = tx.get('to_address')
                if await self.has_non_cex_tag(to_address, chain):
                    return True
        except Exception as e:
            self.logger.warning(f"检查{address}是否存在类型错误时出错: {str(e)}")
        
        return False
    
    async def is_unremoved_deposit(self, address, chain, hot_wallets):
        """
        规则5：筛历史未删除的充币
        去除0交易对手后，转出对手中没有热钱包。
        :param address: 地址
        :param chain: 链
        :param hot_wallets: 热钱包地址列表
        :return: 是否是历史未删除的充币
        """
        try:
            # 获取该地址的转出交易
            transactions = await self.get_transactions(chain, from_address=address, limit=1000)
            
            # 去除0对手（金额为0的交易）
            non_zero_transactions = [tx for tx in transactions if tx.get('amount', 0) > 0]
            
            # 检查转出对手中是否没有热钱包
            has_hot_wallet_opponent = False
            for tx in non_zero_transactions:
                to_address = tx.get('to_address')
                if to_address in hot_wallets:
                    has_hot_wallet_opponent = True
                    break
            
            if not has_hot_wallet_opponent:
                return True
        except Exception as e:
            self.logger.warning(f"检查{address}是否是历史未删除的充币时出错: {str(e)}")
        
        return False
    
    async def get_address_stats(self, chain, addresses):
        """
        获取地址的交易统计信息（交易额和交易量）
        :param chain: 链
        :param addresses: 地址列表
        :return: 地址统计信息字典，key为地址，value为统计信息
        """
        stats = {}
        try:
            # 计算昨天的日期（格式：YYYY-MM-DD）
            import datetime
            yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            
            # 构建Doris查询，使用地址统计表，只统计金额大于0的交易
            query = f"""
            SELECT 
                target_addr as address,      -- 地址
                COUNT(*) as tx_count,  -- 交易笔数（只统计金额大于0的交易）
                SUM(value) as total_amount,   -- 交易额总和（只统计金额大于0的交易）
                MIN(value) as min_amount,   -- 最小交易额（只统计金额大于0的交易）
                MAX(value) as max_amount    -- 最大交易额（只统计金额大于0的交易）
            WHERE 
                target_addr IN ({','.join([f'"{addr}"' for addr in addresses])})  -- 地址在指定列表中
                AND period = '{yesterday}'         -- 只查询昨天的数据
                AND value > 0                      -- 只统计金额大于0的交易
            GROUP BY 
                target_addr  -- 按地址分组
            """
            
            # 执行Doris查询，使用addr_stats data_key
            query_response = await self.storage.doris.search("addr_stats", chain, query, {})
            
            # 处理查询结果
            if query_response:
                for row in query_response:
                    address = row.get('address')
                    stats[address] = {
                        'tx_count': row.get('tx_count', 0),
                        'total_amount': row.get('total_amount', 0),
                        'min_amount': row.get('min_amount', 0),
                        'max_amount': row.get('max_amount', 0)
                    }
        except Exception as e:
            self.logger.warning(f"查询{chain}地址统计时出错: {str(e)}")
        return stats
    
    async def get_transactions(self, chain, from_address=None, to_addresses=None, limit=10000):
        """
        获取交易记录
        :param chain: 链
        :param from_address: 发送地址
        :param to_addresses: 接收地址列表
        :param limit: 限制数量
        :return: 交易记录列表
        """
        response = []
        try:
            # 计算昨天的日期（格式：YYYY-MM-DD）
            import datetime
            yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Build Doris query, using daily transaction pairs table
            if from_address:
                query = f"""
                SELECT 
                    target_addr as from_address,  -- 交易发送地址，重命名为from_address
                    peer_addr as to_address,      -- 与target_addr成对的地址，重命名为to_address
                    target_token as token_address, -- 代币地址
                    value as amount,              -- 交易额
                    '' as tx_hash,                -- Daily transaction pairs table doesn't have tx_hash field, using empty string
                    latest_tx_time as block_time   -- 最近交易时间戳
                WHERE 
                    target_addr = '{from_address}'     -- 交易发送地址为指定地址
                    AND direction = 1                 -- 交易方向为1（转出）
                    AND period = '{yesterday}'         -- 只查询昨天的数据
                LIMIT {limit}
                """
            elif to_addresses:
                query = f"""
                SELECT 
                    target_addr as from_address,  -- 交易发送地址，重命名为from_address
                    peer_addr as to_address,      -- 与target_addr成对的地址，重命名为to_address
                    target_token as token_address, -- 代币地址
                    value as amount,              -- 交易额
                    '' as tx_hash,                -- Daily transaction pairs table doesn't have tx_hash field, using empty string
                    latest_tx_time as block_time   -- 最近交易时间戳
                WHERE 
                    peer_addr IN ({','.join([f'"{addr}"' for addr in to_addresses])})  -- 与target_addr成对的地址在指定列表中
                    AND direction = 2                 -- 交易方向为2（转入）
                    AND period = '{yesterday}'         -- 只查询昨天的数据
                LIMIT {limit}
                """
            else:
                return response
            
            # 执行Doris查询，使用daily_pair data_key
            query_response = await self.storage.doris.search("daily_pair", chain, query, {})
            
            # 处理查询结果
            if query_response:
                response.extend(query_response)
        except Exception as e:
            self.logger.warning(f"查询{chain}交易记录时出错: {str(e)}")
        return response
    
    async def get_address_balance_value(self, address, chain, chain_defined_valuable_tokens):
        """
        获取地址余额总价值
        :param address: 地址
        :param chain: 链
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :return: 余额总价值（U）
        """
        total_value = 0
        try:
            # 这里需要根据实际情况从数据库获取地址余额
            # 暂时返回0，需要根据实际情况修改
            self.logger.warning("当前知识库中没有定义address_balances表，暂时返回0")
        except Exception as e:
            self.logger.error(f"获取{address}余额时出错: {str(e)}")
        return total_value
    
    async def has_non_cex_tag(self, address, chain):
        """
        检查地址是否具有非中心化交易所下的标签
        :param address: 地址
        :param chain: 链
        :return: 是否具有非中心化交易所下的标签
        """
        try:
            # 使用self.storage.tag_api查询地址的标签
            tags = await self.storage.tag_api.get_tag_rels(address, chain)
            # 检查是否有非中心化交易所下的标签（例如支付机构、金融托管等等）
            non_cex_tags = ['payment_institution', 'financial_custody']  # 示例标签类型
            return any(tag.get('type') in non_cex_tags for tag in tags)
        except Exception as e:
            self.logger.warning(f"检查{address}是否具有非中心化交易所下的标签时出错: {str(e)}")
            return False
    
    async def export_filter_result(self, filter_result):
        """
        输出过滤结果
        :param filter_result: 过滤结果
        """
        # 生成时间戳
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 输出历史误标为充币的钓鱼地址
        if filter_result.get('phishing_addresses'):
            await self.export_to_excel(filter_result['phishing_addresses'], f'钓鱼地址_{timestamp}.xlsx')
        
        # 输出历史误标为充币的冷钱包
        if filter_result.get('cold_wallets'):
            await self.export_to_excel(filter_result['cold_wallets'], f'冷钱包_{timestamp}.xlsx')
        
        # 输出实体错误的充币
        if filter_result.get('entity_error_deposits'):
            await self.export_to_excel(filter_result['entity_error_deposits'], f'实体错误充币_{timestamp}.xlsx')
        
        # 输出类型错误的充币
        if filter_result.get('type_error_deposits'):
            await self.export_to_excel(filter_result['type_error_deposits'], f'类型错误充币_{timestamp}.xlsx')
        
        # 输出历史未删除的充币
        if filter_result.get('unremoved_deposits'):
            await self.export_to_excel(filter_result['unremoved_deposits'], f'历史未删除充币_{timestamp}.xlsx')
        
        # 输出有效的充币
        if filter_result.get('valid_deposits'):
            await self.export_to_excel(filter_result['valid_deposits'], f'有效充币_{timestamp}.xlsx')
    
    async def export_to_excel(self, addresses, filename):
        """
        将地址信息输出到Excel表格
        :param addresses: 地址信息列表
        :param filename: 输出文件名
        """
        if not addresses:
            self.logger.warning("没有需要输出的地址")
            return
        
        try:
            # 准备输出数据
            output_data = []
            for addr_info in addresses:
                chain = addr_info.get('chain', '')
                address = addr_info.get('address', '')
                # 实体暂时使用地址本身，后续可以根据需要修改
                entity = address
                
                output_data.append({
                    '链': chain,
                    '实体': entity,
                    '地址': address
                })
            
            # 创建DataFrame
            df = pd.DataFrame(output_data)
            
            # 输出到Excel文件
            df.to_excel(filename, index=False)
            
            self.logger.info(f"已将{len(addresses)}个地址输出到Excel文件: {filename}")
            
        except Exception as e:
            self.logger.error(f"输出Excel文件时出错: {str(e)}")
