from .base import Handler
from enums.chain import LbzChain
from datetime import datetime, timedelta


class PaymentInstitutionAnalysisHandler(Handler):
    """
    支付机构和金融托管分析处理器
    识别标准充币地址和非标准充币地址，并检测未知平台地址
    """

    async def run(self):
        """
        执行支付机构和金融托管分析
        """
        self.logger.info("开始执行支付机构和金融托管分析")

        # 获取平台地址列表
        platform_addresses = await self.get_platform_addresses()
        if not platform_addresses:
            self.logger.warning("未获取到平台地址，分析终止")
            return

        # 构建平台地址列表（用于排除自身）
        platform_addresses_list = []
        for chain, addresses in platform_addresses.items():
            platform_addresses_list.extend(addresses)

        # 获取链必追定义的有价值代币
        chain_defined_valuable_tokens = await self.get_chain_defined_valuable_tokens()
        if not chain_defined_valuable_tokens:
            self.logger.warning("未获取到有价值代币，分析终止")
            return

        # 获取钓鱼代币货币篮子
        phishing_tokens = await self.get_phishing_tokens()

        # 查询无标签入向对手，排除钓鱼地址
        untagged_addresses = await self.get_untagged_inbound_addresses(
            platform_addresses, chain_defined_valuable_tokens, phishing_tokens
        )

        # 筛选充币地址
        deposit_addresses = await self.screen_deposit_addresses(
            untagged_addresses.get('valid_addresses', []), platform_addresses_list, chain_defined_valuable_tokens
        )

        # 记录钓鱼地址
        await self.record_phishing_addresses(untagged_addresses.get('phishing_addresses', []))

        # 输出标准充币地址
        await self.output_standard_deposits(deposit_addresses.get('standard_deposits', []))

        # 检测未知平台地址
        await self.detect_unknown_platform_addresses(
            deposit_addresses.get('non_standard_deposits', []), platform_addresses_list, chain_defined_valuable_tokens
        )

        self.logger.info("支付机构和金融托管分析执行完成")

    async def get_platform_addresses(self):
        """
        获取平台地址列表
        首先从配置中获取 PLATFORM_ADDRESSES
        如果配置中没有，从MongoDB的 data.platform_addresses.{chain} 表获取
        :return: 平台地址列表，格式为 {chain: [address1, address2, ...]}
        """
        platform_addresses = {}

        try:
            # 首先从配置中获取
            config_platform_addresses = self.config.get("PLATFORM_ADDRESSES", {})
            if config_platform_addresses:
                platform_addresses = config_platform_addresses
            else:
                # 从MongoDB获取
                # 使用LbzChain枚举获取链列表，确保使用正确的链名称
                chains = [chain.value for chain in LbzChain]

                for chain in chains:
                    try:
                        # 使用self.storage.mongo.coll获取集合
                        coll = self.storage.mongo.coll("data", "platform_addresses", chain)
                        # 查询所有平台地址
                        platform_addresses_list = await coll.find({}).to_list(None)
                        # 提取地址列表
                        addresses = [item.get("address") for item in platform_addresses_list if item.get("address")]
                        if addresses:
                            platform_addresses[chain] = addresses
                    except Exception as e:
                        self.logger.warning(f"从MongoDB获取{chain}平台地址失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"从数据库获取平台地址失败: {str(e)}")

        return platform_addresses

    async def get_chain_defined_valuable_tokens(self):
        """
        获取链必追定义的有价值代币
        从MongoDB的 chain_info.reliable_token 表获取
        :return: 有价值代币列表，格式为 ["chain:token_address", ...]
        """
        chain_defined_valuable_tokens = []

        try:
            chains = [chain.value for chain in LbzChain]

            for chain in chains:
                reliable_tokens = await self.storage.mongo.get_reliable_tokens(chain, price_gt_0=True)
                for token_address in reliable_tokens.keys():
                    token_key = f"{chain}:{token_address}"
                    chain_defined_valuable_tokens.append(token_key)
        except Exception as e:
            self.logger.error(f"获取有价值代币失败: {str(e)}")

        return chain_defined_valuable_tokens

    async def get_phishing_tokens(self):
        """
        获取钓鱼代币货币篮子
        从配置中获取钓鱼代币篮子
        :return: 钓鱼代币列表
        """
        phishing_tokens = set()

        try:
            # 从配置中获取钓鱼代币篮子
            phishing_tokens_config = self.config.get("PHISHING_TOKENS", [])
            if phishing_tokens_config:
                phishing_tokens.update(phishing_tokens_config)
        except Exception as e:
            self.logger.error(f"获取钓鱼代币货币篮子时出错: {str(e)}")

        return list(phishing_tokens)

    async def get_address_stats(self, chain, addresses, chain_defined_valuable_tokens=None):
        """
        获取地址的交易统计信息（交易额和交易量）
        :param chain: 链
        :param addresses: 地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币，可选
        :return: 地址统计信息字典，key为地址，value为统计信息
        """
        stats = {}
        try:
            # 如果没有传入有价值代币列表，则获取
            if chain_defined_valuable_tokens is None:
                chain_defined_valuable_tokens = await self.get_chain_defined_valuable_tokens()
            # 提取当前链的有价值代币地址
            valuable_token_addresses = []
            for token_key in chain_defined_valuable_tokens:
                if token_key.startswith(f"{chain}:"):
                    token_address = token_key.split(':')[1]
                    valuable_token_addresses.append(token_address)
            
            if not addresses:
                return stats

            # 通过 data_key 获取映射后的真实表名，避免硬编码物理表
            _, table = self.storage.doris.get_db_table("full_pair", chain)
            address_list_sql = ','.join([f'"{addr}"' for addr in addresses])

            # 构建代币过滤条件，避免出现 IN () 语法错误
            if valuable_token_addresses:
                token_list_sql = ','.join([f'"{token}"' for token in valuable_token_addresses])
                token_filter_sql = f"(target_token IN ({token_list_sql}) OR target_token IS NULL)"
            else:
                token_filter_sql = "target_token IS NULL"

            # 构建Doris查询，统计有价值代币的入向交易金额和去除0交易的出向交易笔数
            query = f"""
            SELECT 
                target_addr as address,
                -- 出向交易笔数（去除0交易）
                SUM(CASE WHEN direction = 1 AND value > 0 THEN 1 ELSE 0 END) as out_tx_count,
                -- 有价值代币的入向交易金额
                SUM(CASE WHEN direction = 2 AND value > 0 AND {token_filter_sql} THEN value ELSE 0 END) as valuable_in_amount
            FROM 
                {table}
            WHERE 
                target_addr IN ({address_list_sql})  -- 地址在指定列表中
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
                        'out_tx_count': row.get('out_tx_count', 0),
                        'valuable_in_amount': row.get('valuable_in_amount', 0)
                    }
        except Exception as e:
            self.logger.warning(f"查询{chain}地址统计时出错: {str(e)}")
        return stats

    async def get_opponents(self, chain, from_address=None, to_addresses=None, limit=10000):
        """
        获取交易对手
        :param chain: 链
        :param from_address: 发送地址
        :param to_addresses: 接收地址列表
        :param limit: 限制数量
        :return: 交易对手列表
        """
        response = []
        try:
            # 计算昨天的日期（格式：YYYY-MM-DD）
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            # 通过 data_key 获取映射后的真实表名
            _, table = self.storage.doris.get_db_table("daily_pair", chain)

            # 构建Doris查询，使用日交易对表
            if from_address:
                query = f"""
                SELECT 
                    target_addr as from_address,  -- 交易发送地址，重命名为from_address
                    peer_addr as to_address,      -- 与target_addr成对的地址，重命名为to_address
                    target_token as token_address, -- 代币地址
                    value as amount,              -- 交易额
                    latest_tx_time as block_time   -- 最近交易时间戳
                FROM 
                    {table}     -- 日交易对表，使用data_key映射
                WHERE 
                    target_addr = '{from_address}'     -- 交易发送地址为指定地址
                    AND direction = 1                 -- 交易方向为1（转出）
                    AND period = '{yesterday}'         -- 只查询昨天的数据
                LIMIT {limit}
                """
            elif to_addresses:
                query = f"""
                SELECT 
                    peer_addr as from_address,    -- 交易发送地址，重命名为from_address
                    target_addr as to_address,    -- 交易接收地址，重命名为to_address
                    target_token as token_address, -- 代币地址
                    value as amount,              -- 交易额
                    latest_tx_time as block_time   -- 最近交易时间戳
                FROM 
                    {table}     -- 日交易对表，使用data_key映射
                WHERE 
                    target_addr IN ({','.join([f'"{addr}"' for addr in to_addresses])})  -- 统计目标地址在指定列表中
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
            self.logger.warning(f"查询{chain}交易对手时出错: {str(e)}")
        return response

    async def check_address_has_tag(self, address, chain):
        """
        检查地址是否有标签
        使用标签库API查询
        :param address: 地址
        :param chain: 链
        :return: True表示有标签，False表示无标签
        """
        try:
            # 使用标签库API查询地址是否有标签
            tag_rels = await self.storage.tag_api.get_tag_rels(chain, addr_list=[address])
            # 检查返回的标签列表是否为空
            return len(tag_rels) > 0
        except Exception as e:
            self.logger.warning(f"查询地址标签时出错: {str(e)}")
            return False

    async def get_untagged_inbound_addresses(self, platform_addresses, chain_defined_valuable_tokens, phishing_tokens):
        """
        查询无标签入向对手，排除钓鱼地址
        :param platform_addresses: 平台地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :param phishing_tokens: 钓鱼代币货币篮子
        :return: {valid_addresses: [], phishing_addresses: []}
        """
        valid_addresses = {}  # 有效地址
        phishing_addresses = {}  # 钓鱼地址

        # 构建平台地址列表（用于排除自身）
        platform_addresses_list = []
        for chain, addresses in platform_addresses.items():
            platform_addresses_list.extend(addresses)

        # 使用LbzChain枚举获取链列表，确保使用正确的链名称
        chains = [chain.value for chain in LbzChain]

        for chain in chains:
            try:
                # 获取平台地址的入向交易
                addresses = platform_addresses.get(chain, [])
                if not addresses:
                    continue

                response = await self.get_opponents(chain, to_addresses=addresses, limit=10000)

                if response:
                    # 遍历查询结果
                    for row in response:
                        from_address = row.get('from_address')
                        token_address = row.get('token_address')

                        # 检查发送方地址是否存在且不在平台地址列表中
                        if from_address and from_address not in platform_addresses_list:
                            # 从标签库API查询地址是否有标签
                            has_tag = await self.check_address_has_tag(from_address, chain)
                            # 如果无标签
                            if not has_tag:
                                # 构建代币键
                                token_key = None
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

                                # 检查是否是钓鱼代币
                                is_phishing_token = False
                                if token_key:
                                    if token_key in phishing_tokens:
                                        is_phishing_token = True
                                else:
                                    if chain in phishing_tokens:
                                        is_phishing_token = True

                                # 根据是否是钓鱼代币，分别处理
                                if is_phishing_token:
                                    # 对于钓鱼代币，只记录地址，后续使用统计信息
                                    if address_key not in phishing_addresses:
                                        phishing_addresses[address_key] = {
                                            'address': from_address,
                                            'chain': chain,
                                            'token': token
                                        }
                                else:
                                    # 对于非钓鱼代币，只记录地址，后续使用统计信息
                                    if address_key not in valid_addresses:
                                        valid_addresses[address_key] = {
                                            'address': from_address,
                                            'chain': chain,
                                            'token': token
                                        }
            except Exception as e:
                self.logger.warning(f"查询{chain}交易记录时出错: {str(e)}")

        # 收集所有需要查询统计信息的地址
        all_addresses = list(phishing_addresses.keys()) + list(valid_addresses.keys())

        if all_addresses:
            # 使用LbzChain枚举获取链列表
            chains = [chain.value for chain in LbzChain]

            for chain in chains:
                try:
                    # 筛选出该链的地址
                    chain_addresses = [addr.split(':')[1] if ':' in addr else addr for addr in all_addresses if addr.startswith(f"{chain}:")]

                    if chain_addresses:
                        # 获取这些地址的交易统计信息
                        address_stats = await self.get_address_stats(chain, chain_addresses, chain_defined_valuable_tokens)

                        # 遍历统计信息，更新地址数据
                        for address, stats in address_stats.items():
                            address_key = f"{chain}:{address}"
                            tx_count = stats.get('out_tx_count', 0)
                            total_amount = stats.get('valuable_in_amount', 0)

                            # 检查该地址是钓鱼地址还是有效地址
                            if address_key in phishing_addresses:
                                # 对于钓鱼代币，需要交易额/交易笔数大于1.5U，交易笔数需要排除0U交易
                                if tx_count > 0 and (total_amount / tx_count) > 1.5:
                                    phishing_addresses[address_key].update({
                                        'tx_count': tx_count,
                                        'total_amount': total_amount,
                                        'min_amount': 0,
                                        'max_amount': 0
                                    })
                                else:
                                    # 不符合条件，从钓鱼地址中移除
                                    del phishing_addresses[address_key]
                            elif address_key in valid_addresses:
                                # 对于非钓鱼代币，只需要无标签
                                valid_addresses[address_key].update({
                                    'tx_count': tx_count,
                                    'total_amount': total_amount,
                                    'min_amount': 0,
                                    'max_amount': 0
                                })
                except Exception as e:
                    self.logger.warning(f"查询{chain}地址统计时出错: {str(e)}")

        # 过滤掉不符合条件的钓鱼地址
        filtered_phishing_addresses = []
        for addr_info in phishing_addresses.values():
            tx_count = addr_info.get('tx_count', 0)
            total_amount = addr_info.get('total_amount', 0)
            if tx_count > 0 and (total_amount / tx_count) > 1.5:
                filtered_phishing_addresses.append(addr_info)

        return {
            'valid_addresses': list(valid_addresses.values()),
            'phishing_addresses': filtered_phishing_addresses
        }

    async def record_phishing_addresses(self, phishing_addresses):
        """
        记录钓鱼地址
        :param phishing_addresses: 钓鱼地址列表
        """
        if not phishing_addresses:
            return

        try:
            # 暂时只记录日志，后续会根据配置添加到合适的表中
            # 如需新建MongoDB库/表，应先添加到config.py中
            self.logger.info(f"记录{len(phishing_addresses)}个钓鱼地址")
            for address in phishing_addresses:
                self.logger.info(f"钓鱼地址: 链={address.get('chain')}, 地址={address.get('address')}, 代币={address.get('token')}, 交易笔数={address.get('tx_count')}, 总金额={address.get('total_amount')}")

        except Exception as e:
            self.logger.error(f"记录钓鱼地址时出错: {str(e)}")

    async def screen_deposit_addresses(self, valid_addresses, platform_addresses_list, chain_defined_valuable_tokens):
        """
        筛选充币地址
        :param valid_addresses: 有效地址列表
        :param platform_addresses_list: 平台地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :return: {standard_deposits: [], non_standard_deposits: []}
        """
        standard_deposits = []  # 标准充币地址
        non_standard_deposits = []  # 非标准充币地址

        for address_info in valid_addresses:
            address = address_info.get('address')
            chain = address_info.get('chain')

            try:
                # 获取地址的出向交易
                response = await self.get_opponents(chain, from_address=address, limit=10000)

                has_platform_opponent = False  # 是否有平台地址对手
                has_non_platform_opponent = False  # 是否有非平台地址对手

                if response:
                    for row in response:
                        to_address = row.get('to_address')
                        token_address = row.get('token_address')
                        amount = row.get('amount', 0)

                        # 检查交易金额是否大于0
                        if amount <= 0:
                            continue

                        # 构建代币键
                        if token_address:
                            token_key = f"{chain}:{token_address}"
                            # 检查代币是否在链必追定义的有价值代币列表中
                            if token_key not in chain_defined_valuable_tokens:
                                continue
                        else:
                            # 本币默认在有价值代币列表中
                            pass

                        # 检查出向对手是否是平台地址
                        if to_address in platform_addresses_list:
                            has_platform_opponent = True
                        else:
                            has_non_platform_opponent = True

                # 分类充币地址
                if has_platform_opponent and not has_non_platform_opponent:
                    # 标准充币地址：出向对手全是本实体平台地址
                    standard_deposits.append(address_info)
                elif has_platform_opponent and has_non_platform_opponent:
                    # 非标准充币地址：出向对手既存在本实体平台地址，又存在无标签地址或其他实体地址
                    non_standard_deposits.append(address_info)

            except Exception as e:
                self.logger.warning(f"筛选{chain}充币地址时出错: {str(e)}")

        return {
            'standard_deposits': standard_deposits,
            'non_standard_deposits': non_standard_deposits
        }

    async def output_standard_deposits(self, standard_deposits):
        """
        输出标准充币地址
        :param standard_deposits: 标准充币地址列表
        """
        if not standard_deposits:
            self.logger.info("未检测出标准充币地址")
            return

        try:
            # 暂时只记录日志，后续会根据配置输出为CSV文件
            self.logger.info(f"检测出{len(standard_deposits)}个标准充币地址")
            for deposit in standard_deposits:
                self.logger.info(f"标准充币地址: 链={deposit.get('chain')}, 地址={deposit.get('address')}, 代币={deposit.get('token')}, 交易笔数={deposit.get('tx_count')}, 总金额={deposit.get('total_amount')}")

        except Exception as e:
            self.logger.error(f"输出标准充币地址时出错: {str(e)}")

    async def detect_unknown_platform_addresses(self, non_standard_deposits, platform_addresses_list, chain_defined_valuable_tokens):
        """
        检测并推送同实体未知平台地址
        :param non_standard_deposits: 非标准充币地址列表
        :param platform_addresses_list: 平台地址列表
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        """
        unknown_platform_addresses = []

        for deposit in non_standard_deposits:
            address = deposit.get('address')
            chain = deposit.get('chain')

            try:
                # 获取地址的出向交易
                response = await self.get_opponents(chain, from_address=address, limit=10000)

                # 过滤掉0交易对手
                non_zero_opponents = []
                if response:
                    for row in response:
                        to_address = row.get('to_address')
                        token_address = row.get('token_address')
                        amount = row.get('amount', 0)

                        # 检查交易金额是否大于0
                        if amount <= 0:
                            continue

                        # 构建代币键
                        if token_address:
                            token_key = f"{chain}:{token_address}"
                            # 检查代币是否在链必追定义的有价值代币列表中
                            if token_key not in chain_defined_valuable_tokens:
                                continue
                        else:
                            # 本币默认在有价值代币列表中
                            pass

                        non_zero_opponents.append(to_address)

                # 去重
                unique_opponents = list(set(non_zero_opponents))

                # 检查出向交易对手是否小于15个
                if len(unique_opponents) < 15:
                    # 获取它们的本币和有价值代币的出向对手中无热钱包标签的对手非合约地址A
                    for opponent in unique_opponents:
                        # 检查对手是否在平台地址列表中
                        if opponent in platform_addresses_list:
                            continue

                        # 检查对手是否是合约地址
                        is_contract = await self.is_contract_address(opponent, chain)
                        if is_contract:
                            continue

                        # 查询A的总交易笔数
                        tx_count = await self.get_address_tx_count(opponent, chain)

                        # 检查去除0交易对手后交易对手是否大于100
                        if tx_count > 100:
                            # 查询A的入向对手
                            inbound_opponents = await self.get_inbound_opponents(opponent, chain, chain_defined_valuable_tokens)

                            # 检查入向对手中的随机1千个地址中有大于等于3个的本实体充币标签地址
                            deposit_tag_count = 0
                            for inbound_opponent in inbound_opponents[:1000]:  # 只取前1000个
                                has_deposit_tag = await self.has_deposit_tag(inbound_opponent, chain)
                                if has_deposit_tag:
                                    deposit_tag_count += 1
                                    if deposit_tag_count >= 3:
                                        break

                            if deposit_tag_count >= 3:
                                # 判定A是个未知平台地址
                                unknown_platform_addresses.append({
                                    'address': opponent,
                                    'chain': chain,
                                    'source_address': address
                                })
            except Exception as e:
                self.logger.error(f"检测{address}的未知平台地址时出错: {str(e)}")

        # 推送未知平台地址
        await self.push_unknown_platform_addresses(unknown_platform_addresses)

    async def is_contract_address(self, address, chain):
        """
        检查地址是否是合约地址
        使用MongoDB合约表查询
        :param address: 地址
        :param chain: 链
        :return: True表示是合约地址，False表示不是
        """
        try:
            # 使用MongoDB合约表查询
            coll = self.storage.mongo.coll("data", "contract", chain)
            # 查询地址是否在合约表中
            contract = await coll.find_one({"_id": address})
            # 如果找到记录，说明是合约地址
            return contract is not None
        except Exception as e:
            self.logger.warning(f"查询地址是否是合约地址时出错: {str(e)}")
            return False

    async def get_address_tx_count(self, address, chain):
        """
        获取地址的交易笔数
        :param address: 地址
        :param chain: 链
        :return: 交易笔数
        """
        try:
            # 计算昨天的日期（格式：YYYY-MM-DD）
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            # 通过 data_key 获取映射后的真实表名
            _, table = self.storage.doris.get_db_table("daily_pair", chain)

            # 构建Doris查询，使用日交易对表
            query = f"""
            SELECT 
                COUNT(*) as tx_count  -- 交易笔数
            FROM 
                {table}     -- 日交易对表，使用data_key映射
            WHERE 
                target_addr = '{address}'  -- 地址是发送方
                AND period = '{yesterday}'         -- 只查询昨天的数据
                AND value > 0                      -- 只统计金额大于0的交易
            """

            # 执行Doris查询，使用daily_pair data_key
            query_response = await self.storage.doris.search("daily_pair", chain, query, {})

            # 处理查询结果
            if query_response:
                return query_response[0].get('tx_count', 0)
            return 0
        except Exception as e:
            self.logger.warning(f"查询{chain}地址交易笔数时出错: {str(e)}")
            return 0

    async def get_inbound_opponents(self, address, chain, chain_defined_valuable_tokens):
        """
        获取地址的入向对手
        :param address: 地址
        :param chain: 链
        :param chain_defined_valuable_tokens: 链必追定义的有价值代币列表
        :return: 入向对手列表
        """
        inbound_opponents = []

        try:
            # 计算昨天的日期（格式：YYYY-MM-DD）
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            # 通过 data_key 获取映射后的真实表名
            _, table = self.storage.doris.get_db_table("daily_pair", chain)

            # 构建Doris查询，使用日交易对表
            query = f"""
            SELECT 
                peer_addr as from_address    -- 交易发送地址，重命名为from_address
            FROM 
                {table}     -- 日交易对表，使用data_key映射
            WHERE 
                target_addr = '{address}'   -- 统计目标地址为指定地址
                AND direction = 2                 -- 交易方向为2（转入）
                AND period = '{yesterday}'         -- 只查询昨天的数据
                AND value > 0                      -- 只统计金额大于0的交易
            """

            # 执行Doris查询，使用daily_pair data_key
            query_response = await self.storage.doris.search("daily_pair", chain, query, {})

            # 处理查询结果
            if query_response:
                for row in query_response:
                    from_address = row.get('from_address')
                    if from_address:
                        inbound_opponents.append(from_address)
        except Exception as e:
            self.logger.warning(f"查询{chain}地址入向对手时出错: {str(e)}")

        return inbound_opponents

    async def has_deposit_tag(self, address, chain):
        """
        检查地址是否有充币标签
        使用标签库API查询
        :param address: 地址
        :param chain: 链
        :return: True表示有充币标签，False表示没有
        """
        try:
            # 使用标签库API查询地址是否有充币标签
            tag_rels = await self.storage.tag_api.get_tag_rels(chain, addr_list=[address])
            # 检查返回的标签列表中是否有类型为'deposit'的标签
            for tag_rel in tag_rels:
                if tag_rel.get('type') == 'deposit':
                    return True
            return False
        except Exception as e:
            self.logger.warning(f"查询地址是否有充币标签时出错: {str(e)}")
            return False

    async def push_unknown_platform_addresses(self, unknown_platform_addresses):
        """
        推送未知平台地址
        :param unknown_platform_addresses: 未知平台地址列表
        """
        if not unknown_platform_addresses:
            self.logger.info("未检测出未知平台地址")
            return

        try:
            # 暂时只记录日志，后续会根据配置添加到合适的表中
            # 如需新建MongoDB库/表，应先添加到config.py中
            self.logger.info(f"需要推送{len(unknown_platform_addresses)}个未知平台地址")
            for address in unknown_platform_addresses:
                self.logger.info(f"未知平台地址: 链={address.get('chain')}, 地址={address.get('address')}, 来源地址={address.get('source_address')}")

        except Exception as e:
            self.logger.error(f"推送未知平台地址时出错: {str(e)}")
