# 导入基础处理器类
# Handler类是所有规则处理器的基类，提供了配置管理和存储访问等基础功能
from .base import Handler
import pandas as pd  # 用于处理Excel输出


class HotWalletAnalysisHandler(Handler):
    """
    热钱包分析处理器
    用于分析热钱包的交易情况，筛选无标签入向对手地址，并进行进一步处理
    """
    
    async def run(self):
        """
        执行热钱包分析流程
        1. 获取热钱包地址列表
        2. 获取热钱包交易过的本币和有价值代币
        3. 查询交易记录并筛选无标签入向对手地址
        4. 对筛选后地址进行进一步处理
        5. 记录被排除的钓鱼地址
        6. 过滤充币，检查转出对手
        7. 识别余额价值大于十万U的冷钱包
        """
        self.logger.info("Running HotWalletAnalysisHandler")
        
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
        chain_defined_valuable_tokens = await self.get_valuable_tokens_from_mongo()
        
        if not chain_defined_valuable_tokens:
            self.logger.warning("未获取到链必追定义的有价值代币")
        else:
            self.logger.info(f"获取到的有价值代币数量: {len(chain_defined_valuable_tokens)}")
        
        # 2. 查询交易记录并筛选无标签入向对手地址
        self.logger.info("正在查询交易记录并筛选无标签入向对手地址...")
        untagged_addresses = await self.get_untagged_inbound_addresses(
            hot_wallets, chain_defined_valuable_tokens
        )
        
        if not untagged_addresses:
            self.logger.warning("未筛选出无标签入向对手地址")
        else:
            self.logger.info(f"筛选出{len(untagged_addresses)}个无标签入向对手地址")
        
        # 3. 对筛选后地址进行进一步处理
        self.logger.info("正在对筛选后地址进行进一步处理...")
        # 从MongoDB获取链必追定义的有价值代币列表
        chain_defined_valuable_tokens = await self.get_valuable_tokens_from_mongo()
        
        processing_result = await self.process_untagged_addresses(
            untagged_addresses, hot_wallets, chain_defined_valuable_tokens
        )
        
        self.logger.info("处理结果:")
        self.logger.info(f"符合条件地址数量: {len(processing_result['符合条件_addresses'])}")
        self.logger.info(f"不符合条件地址数量: {len(processing_result['不符合条件_addresses'])}")
        
        # 4. 记录被排除的钓鱼地址（不符合条件的地址）
        await self.record_phishing_addresses(processing_result['不符合条件_addresses'])
        
        # 5. 过滤充币，检查转出对手是否全是本实体的热钱包
        valid_deposits = await self.filter_deposits(processing_result['符合条件_addresses'], hot_wallets, chain_defined_valuable_tokens)
        
        # 6. 识别余额价值大于十万U的冷钱包
        cold_wallets = await self.identify_cold_wallets(processing_result['不符合条件_addresses'], chain_defined_valuable_tokens)
        
        # 7. 输出结果
        await self.export_to_excel(processing_result['不符合条件_addresses'])
        if valid_deposits:
            await self.export_deposits_to_excel(valid_deposits)
        if cold_wallets:
            await self.export_cold_wallets_to_excel(cold_wallets)
    
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
    
    async def get_untagged_inbound_addresses(self, hot_wallets, chain_defined_valuable_tokens):
        """
        查询交易记录并筛选无标签入向对手地址
        :param hot_wallets: 热钱包地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :return: 无标签入向对手地址列表（包含交易笔数统计）
        """
        untagged_addresses = {}  # 使用字典存储，key为地址，value为地址信息
        
        # 从配置中获取链列表
        chains = self.config.get("CHAINS", ["eth", "bsc", "polygon", "avax", "arbitrum", "optimism"])
        
        for chain in chains:
            # 处理本币交易和代币转账，使用Doris查询
            try:
                # 构建Doris查询，获取热钱包的入向交易
                query = f"""
                SELECT 
                    `from` as from_address,  -- 发送地址，重命名为from_address
                    `to` as to_address,      -- 接收地址，重命名为to_address
                    send_token as token_address,  -- 发送代币，重命名为token_address
                    send_value as amount,    -- 发送金额，重命名为amount
                    tx_hash,                -- 交易哈希
                    block_time              -- 区块时间
                    -- 注意：Doris表中没有tags字段，后续会通过标签库API获取地址标签
                FROM 
                    {chain}_tx_behavior     -- 本币交易表，根据知识库使用正确的表名
                WHERE 
                    `to` IN ({','.join([f'"{wallet}"' for wallet in hot_wallets])})  -- 接收地址在热钱包列表中
                    AND is_dest = true      -- 只获取行为结果数据
                LIMIT 10000
                """
                
                # 同时查询代币转账，使用{chain}_transfer_behavior表
                transfer_query = f"""
                SELECT 
                    `from` as from_address,  -- 发送地址，重命名为from_address
                    `to` as to_address,      -- 接收地址，重命名为to_address
                    send_token as token_address,  -- 发送代币，重命名为token_address
                    send_value as amount,    -- 发送金额，重命名为amount
                    tx_hash,                -- 交易哈希
                    block_time              -- 区块时间
                    -- 注意：Doris表中没有tags字段，后续会通过标签库API获取地址标签
                FROM 
                    {chain}_transfer_behavior  -- 代币转账表，根据知识库使用正确的表名
                WHERE 
                    `to` IN ({','.join([f'"{wallet}"' for wallet in hot_wallets])})  -- 接收地址在热钱包列表中
                    AND is_dest = true      -- 只获取行为结果数据
                LIMIT 10000
                """
                
                # 执行Doris查询
                tx_response = await self.storage.doris.execute(query)
                transfer_response = await self.storage.doris.execute(transfer_query)
                
                # 合并结果
                response = []
                if tx_response:
                    response.extend(tx_response)
                if transfer_response:
                    response.extend(transfer_response)
                
                if response:
                    # 遍历查询结果
                    for row in response:
                        from_address = row.get('from_address')
                        to_address = row.get('to_address')
                        token_address = row.get('token_address')
                        amount = row.get('amount', 0)
                        tx_hash = row.get('tx_hash')
                        block_time = row.get('block_time')
                        # 注意：Doris表中没有tags字段，后续会通过标签库API获取地址标签
                        # tags = row.get('tags')
                        
                        # 检查发送方地址是否存在且不在热钱包列表中
                        if from_address and from_address not in hot_wallets:
                            # 从标签库API查询地址是否有标签
                            has_tag = await self.check_address_has_tag(from_address, chain)
                            # 如果无标签
                            if not has_tag:
                                # 构建代币键
                                if token_address:
                                    token_key = f"{chain}:{token_address}"
                                    # 检查代币是否在链必追定义的有价值代币列表中
                                    if token_key not in chain_defined_valuable_tokens:
                                        continue
                                    token = token_address
                                else:
                                    # 本币
                                    token = chain
                                    # 本币默认在有价值代币列表中
                                    
                                address_key = f"{chain}:{from_address}"
                                if address_key not in untagged_addresses:
                                    untagged_addresses[address_key] = {
                                        'address': from_address,
                                        'chain': chain,
                                        'token': token,
                                        'amount': amount,
                                        'tx_count': 1,  # 初始交易笔数为1
                                        'total_amount': amount,  # 初始总金额
                                        'tx_hash': tx_hash,
                                        'block_time': block_time
                                    }
                                else:
                                    # 如果已存在，累加交易笔数和总金额
                                    untagged_addresses[address_key]['tx_count'] += 1
                                    untagged_addresses[address_key]['total_amount'] += amount
            except Exception as e:
                self.logger.warning(f"查询{chain}交易记录时出错: {str(e)}")
        
        return list(untagged_addresses.values())
    
    async def check_address_has_tag(self, address, chain):
        """
        从标签库API查询地址是否有标签
        :param address: 地址
        :param chain: 链
        :return: 是否有标签的布尔值
        """
        try:
            # 这里需要根据实际的标签库API接口进行修改
            # 暂时返回False，后续会实现真实的API调用
            # 示例：
            # response = await self.tag_api.get_address_tags(address, chain)
            # return bool(response.get('tags', []))
            return False
        except Exception as e:
            self.logger.error(f"查询地址标签失败: {str(e)}")
            # 出错时默认返回False，避免影响流程
            return False
    
    async def get_valuable_tokens_from_mongo(self):
        """
        从MongoDB获取链必追定义的有价值代币列表
        1. 从chain_info.common获取指定链的币种列表
        2. 从具体链的token_v3表中获取价格和精度等信息
        3. 价格优先取cmc_price，取不到才取price
        :return: 有价值代币列表
        """
        valuable_tokens = set()  # 存储有价值代币列表
        
        try:
            # 从配置中获取链列表
            chains = self.config.get("CHAINS", ["eth", "bsc", "polygon", "avax", "arbitrum", "optimism"])
            
            for chain in chains:
                # 1. 从data.chain_info.common获取该链的币种列表
                chain_info_coll = self.storage.mongo.coll("data", "chain_info", "common")
                chain_info = await chain_info_coll.find_one({"_id": chain})
                
                if chain_info:
                    reliable_tokens = chain_info.get("reliable_token", [])
                    
                    # 2. 从具体链的token_v3表中获取价格和精度等信息
                    token_coll = self.storage.mongo.coll("data", "token_v3", chain)
                    
                    for token_address in reliable_tokens:
                        # 查询代币信息
                        token_doc = await token_coll.find_one({"_id": token_address})
                        
                        if token_doc:
                            # 3. 价格优先取cmc_price，取不到才取price
                            price = token_doc.get("cmc_price")
                            if price is None:
                                price = token_doc.get("price")
                            
                            # 检查价格是否大于0
                            if price and price > 0:
                                # 构建代币键，格式为"链:代币地址"
                                token_key = f"{chain}:{token_address}"
                                valuable_tokens.add(token_key)
        except Exception as e:
            self.logger.error(f"从MongoDB获取有价值代币列表时出错: {str(e)}")
        
        return list(valuable_tokens)
    
    async def process_untagged_addresses(self, untagged_addresses, hot_wallets, chain_defined_valuable_tokens):
        """
        对筛选后地址进行进一步处理
        :param untagged_addresses: 无标签地址列表（包含交易笔数和总金额）
        :param hot_wallets: 热钱包地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :return: 处理结果
        """
        符合条件_addresses = []  # 符合条件的地址列表
        不符合条件_addresses = []  # 不符合条件的地址列表
        
        # 处理无标签地址
        for addr_info in untagged_addresses:
            address = addr_info.get('address')  # 地址
            chain = addr_info.get('chain')  # 链名
            token = addr_info.get('token')  # 代币
            tx_count = addr_info.get('tx_count', 0)  # 交易笔数
            total_amount = addr_info.get('total_amount', 0)  # 总金额
            
            # 检查代币是否在链必追定义的有价值代币列表中
            token_key = f"{chain}:{token}"
            if token_key in chain_defined_valuable_tokens:
                # 检查交易额/交易笔数是否大于1.5U
                if tx_count > 0 and (total_amount / tx_count) > 1.5:
                    符合条件_addresses.append(addr_info)
                else:
                    不符合条件_addresses.append(addr_info)
            else:
                不符合条件_addresses.append(addr_info)
        
        return {
            '符合条件_addresses': 符合条件_addresses,
            '不符合条件_addresses': 不符合条件_addresses
        }
    
    async def export_to_excel(self, addresses):
        """
        将不符合条件的地址输出到Excel表格
        :param addresses: 地址信息列表
        """
        if not addresses:
            self.logger.warning("没有需要输出的地址")
            return
        
        try:
            # 准备输出数据，格式为：链、实体、地址
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
            
            # 生成输出文件名，包含时间戳
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'不符合条件地址_{timestamp}.xlsx'
            
            # 输出到Excel文件
            df.to_excel(filename, index=False)
            
            self.logger.info(f"已将{len(addresses)}个不符合条件的地址输出到Excel文件: {filename}")
            
        except Exception as e:
            self.logger.error(f"输出Excel文件时出错: {str(e)}")
    
    async def record_phishing_addresses(self, phishing_addresses):
        """
        记录被排除的钓鱼地址
        注意：当前知识库中没有定义phishing_addresses表，
        此方法暂时只记录日志，需要根据实际情况修改
        :param phishing_addresses: 钓鱼地址列表
        """
        if not phishing_addresses:
            self.logger.warning("没有需要记录的钓鱼地址")
            return
        
        try:
            # 暂时只记录日志，需要根据实际情况修改
            # 后续可以记录到合适的表中
            self.logger.info(f"需要记录{len(phishing_addresses)}个钓鱼地址，但当前知识库中没有定义phishing_addresses表")
            
        except Exception as e:
            self.logger.error(f"记录钓鱼地址时出错: {str(e)}")
    
    async def filter_deposits(self, addresses, hot_wallets, chain_defined_valuable_tokens):
        """
        过滤充币，检查转出对手是否全是本实体的热钱包
        :param addresses: 符合条件的地址列表
        :param hot_wallets: 热钱包地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :return: 符合条件的充币列表
        """
        valid_deposits = []
        
        for addr_info in addresses:
            address = addr_info.get('address')
            chain = addr_info.get('chain')
            
            # 检查该地址的所有转出交易
            is_valid = True
            
            try:
                # 构建Doris查询，获取该地址的转出交易
                query = f"""
                SELECT 
                    `from` as from_address,  -- 发送地址，重命名为from_address
                    `to` as to_address,      -- 接收地址，重命名为to_address
                    send_token as token_address,  -- 发送代币，重命名为token_address
                    send_value as amount     -- 发送金额，重命名为amount
                FROM 
                    {chain}_tx_behavior     -- 本币交易表，根据知识库使用正确的表名
                WHERE 
                    `from` = '{address}'     -- 发送地址为当前地址
                    AND is_dest = true       -- 只获取行为结果数据
                LIMIT 1000
                """
                
                # 同时查询代币转账
                transfer_query = f"""
                SELECT 
                    `from` as from_address,  -- 发送地址，重命名为from_address
                    `to` as to_address,      -- 接收地址，重命名为to_address
                    send_token as token_address,  -- 发送代币，重命名为token_address
                    send_value as amount     -- 发送金额，重命名为amount
                FROM 
                    {chain}_transfer_behavior  -- 代币转账表，根据知识库使用正确的表名
                WHERE 
                    `from` = '{address}'     -- 发送地址为当前地址
                    AND is_dest = true       -- 只获取行为结果数据
                LIMIT 1000
                """
                
                # 执行Doris查询
                tx_response = await self.storage.doris.execute(query)
                transfer_response = await self.storage.doris.execute(transfer_query)
                
                # 合并结果
                response = []
                if tx_response:
                    response.extend(tx_response)
                if transfer_response:
                    response.extend(transfer_response)
                
                if response:
                    for row in response:
                        to_address = row.get('to_address')
                        token_address = row.get('token_address')
                        
                        # 检查代币是否在链必追定义的有价值代币列表中
                        if token_address:
                            token_key = f"{chain}:{token_address}"
                            if token_key in chain_defined_valuable_tokens:
                                # 检查转出对手是否在热钱包列表中
                                if to_address not in hot_wallets:
                                    is_valid = False
                                    break
                        else:
                            # 本币，默认在有价值代币列表中
                            if to_address not in hot_wallets:
                                is_valid = False
                                break
                
                if is_valid:
                    valid_deposits.append(addr_info)
                    
            except Exception as e:
                self.logger.warning(f"检查{address}的转出交易时出错: {str(e)}")
        
        self.logger.info(f"筛选出{len(valid_deposits)}个符合条件的充币")
        return valid_deposits
    
    async def identify_cold_wallets(self, addresses, chain_defined_valuable_tokens):
        """
        识别余额价值大于十万U的冷钱包
        注意：当前知识库中没有定义address_balances和tokens表，
        此方法暂时只记录日志，需要根据实际情况修改
        :param addresses: 不符合条件的地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :return: 冷钱包列表
        """
        cold_wallets = []
        MIN_COLD_WALLET_BALANCE = 100000  # 十万U
        
        try:
            # 暂时只记录日志，需要根据实际情况修改
            # 后续可以从合适的表中获取余额信息
            self.logger.info(f"需要识别冷钱包，但当前知识库中没有定义address_balances和tokens表")
            
        except Exception as e:
            self.logger.error(f"识别冷钱包时出错: {str(e)}")
        
        self.logger.info(f"识别出{len(cold_wallets)}个冷钱包")
        return cold_wallets
    
    async def export_deposits_to_excel(self, deposits):
        """
        将符合条件的充币输出到Excel表格
        :param deposits: 符合条件的充币列表
        """
        if not deposits:
            self.logger.warning("没有需要输出的充币")
            return
        
        try:
            # 准备输出数据，格式为：链、实体、地址
            output_data = []
            for deposit in deposits:
                chain = deposit.get('chain', '')
                address = deposit.get('address', '')
                # 实体暂时使用地址本身，后续可以根据需要修改
                entity = address
                
                output_data.append({
                    '链': chain,
                    '实体': entity,
                    '地址': address
                })
            
            # 创建DataFrame
            df = pd.DataFrame(output_data)
            
            # 生成输出文件名，包含时间戳
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'符合条件充币_{timestamp}.xlsx'
            
            # 输出到Excel文件
            df.to_excel(filename, index=False)
            
            self.logger.info(f"已将{len(deposits)}个符合条件的充币输出到Excel文件: {filename}")
            
        except Exception as e:
            self.logger.error(f"输出充币Excel文件时出错: {str(e)}")
    
    async def export_cold_wallets_to_excel(self, cold_wallets):
        """
        将冷钱包输出到Excel表格
        :param cold_wallets: 冷钱包列表
        """
        if not cold_wallets:
            self.logger.warning("没有需要输出的冷钱包")
            return
        
        try:
            # 准备输出数据，格式为：链、实体、地址、余额价值
            output_data = []
            for wallet in cold_wallets:
                chain = wallet.get('chain', '')
                address = wallet.get('address', '')
                total_balance_value = wallet.get('total_balance_value', 0)
                # 实体暂时使用地址本身，后续可以根据需要修改
                entity = address
                
                output_data.append({
                    '链': chain,
                    '实体': entity,
                    '地址': address,
                    '余额价值(U)': total_balance_value
                })
            
            # 创建DataFrame
            df = pd.DataFrame(output_data)
            
            # 生成输出文件名，包含时间戳
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'冷钱包_{timestamp}.xlsx'
            
            # 输出到Excel文件
            df.to_excel(filename, index=False)
            
            self.logger.info(f"已将{len(cold_wallets)}个冷钱包输出到Excel文件: {filename}")
            
        except Exception as e:
            self.logger.error(f"输出冷钱包Excel文件时出错: {str(e)}")
