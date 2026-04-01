from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

from .base import Handler


@dataclass
class UserAddressExpansionResult:
    """规则执行结果。

    - standard_users: 标准用户地址（出向对手仅命中本实体平台地址）。
    - non_standard_users: 非标准用户地址（既有平台地址也有无标签地址）。
    - phishing_addresses: 在步骤 2 中识别并剔除的钓鱼地址。
    - unknown_platform_addresses: 在步骤 4 中识别到的同实体未知平台地址。
    """

    standard_users: list[dict]
    non_standard_users: list[str]
    phishing_addresses: list[str]
    unknown_platform_addresses: list[str]


class UserAddressExpansionHandler(Handler):
    """用户地址扩充规则（EVM/TRON）。

    规则来源于业务定义，共 4 个阶段：

    1. 通过平台地址归集行为得到疑似用户地址。
    2. 用「入向交易额 / 出向笔数 > 1.5 U」过滤钓鱼地址并按月归档。
    3. 将疑似用户地址拆分为标准用户地址与非标准用户地址。
    4. 在非标准用户地址中识别同实体未知平台地址。

    设计说明：
    - 该 handler 只依赖 self.storage，不直接访问底层连接。
    - 查询条件尽量写成可配置阈值，避免硬编码。
    - 对标签接口返回字段做了兼容解析（label/tag/entity_name 等），降低字段漂移风险。
    """

    async def run(self) -> UserAddressExpansionResult:
        cfg = self.config.get("SERVICE_CONFIG", {}).get("user_address_expansion", {})
        thresholds = self.config.get("THRESHOLD_CONFIG", {}).get("user_address_expansion", {})

        platform_addresses = await self._get_platform_addresses(cfg)
        if not platform_addresses:
            raise ValueError("平台地址为空：请配置 platform_addresses 或 platform_tag_a_id/platform_tag_v_id")

        # 有价值代币：来自可靠代币篮子（price > 0）。
        reliable_tokens = await self.storage.mongo.get_reliable_tokens(self.chain, price_gt_0=True)
        token_price_map = {token.lower(): meta["price"] for token, meta in reliable_tokens.items()}

        suspects = await self._collect_suspects(platform_addresses, set(token_price_map.keys()))
        self.logger.info(f"步骤 1 完成，疑似用户地址数量: {len(suspects)}")

        filtered_suspects, phishing_addresses = await self._exclude_phishing_addresses(
            suspects=suspects,
            platform_addresses=platform_addresses,
            token_price_map=token_price_map,
            amount_per_out_threshold_usd=float(thresholds.get("amount_per_out_threshold_usd", 1.5)),
        )
        self.logger.info(
            f"步骤 2 完成，过滤后疑似用户地址数量: {len(filtered_suspects)}，剔除钓鱼地址数量: {len(phishing_addresses)}"
        )

        standard_users, non_standard_users = await self._classify_users(filtered_suspects, platform_addresses)
        self.logger.info(
            f"步骤 3 完成，标准用户地址数量: {len(standard_users)}，非标准用户地址数量: {len(non_standard_users)}"
        )

        unknown_platform_addresses = await self._discover_unknown_platform_addresses(
            non_standard_users=non_standard_users,
            platform_addresses=platform_addresses,
            token_price_map=token_price_map,
            max_user_counterparties=int(thresholds.get("max_user_counterparties", 20)),
            min_platform_counterparties=int(thresholds.get("min_platform_counterparties", 200)),
            sample_size=int(thresholds.get("sample_size", 10000)),
            min_entity_user_hits=int(thresholds.get("min_entity_user_hits", 3)),
        )
        self.logger.info(f"步骤 4 完成，识别到未知平台地址数量: {len(unknown_platform_addresses)}")

        return UserAddressExpansionResult(
            standard_users=standard_users,
            non_standard_users=sorted(non_standard_users),
            phishing_addresses=sorted(phishing_addresses),
            unknown_platform_addresses=sorted(unknown_platform_addresses),
        )


    async def _get_platform_addresses(self, cfg: dict) -> set[str]:
        """获取平台地址。

        优先级：
        1) 直接使用 SERVICE_CONFIG.user_address_expansion.platform_addresses。
        2) 若未配置地址，则通过标签接口按 a_id/v_id 拉取平台地址。
        """
        direct_addresses = {addr.lower() for addr in cfg.get("platform_addresses", []) if addr}
        if direct_addresses:
            return direct_addresses

        a_id = cfg.get("platform_tag_a_id")
        v_id = cfg.get("platform_tag_v_id")
        if not (a_id or v_id):
            return set()

        tags = await self.storage.tag_api.get_tag_rels(self.chain, addr_list=None, a_id=a_id, v_id=v_id)
        addresses = {(row.get("address") or "").lower() for row in tags}
        return {addr for addr in addresses if addr}

    async def _collect_suspects(self, platform_addresses: set[str], reliable_tokens: set[str]) -> set[str]:
        """步骤 1：通过平台地址入向对手获取疑似用户地址。"""
        should = [{"terms": {"to": list(platform_addresses)}}]
        if reliable_tokens:
            should.append({"terms": {"send_token": list(reliable_tokens)}})

        query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"is_dest": True}},
                        {"term": {"tx_type": "transfer"}},
                    ],
                    "must": should,
                }
            }
        }

        suspects: set[str] = set()
        async for item in self.storage.es.iter_search("transfer", self.chain, query):
            from_addr = (item.get("from") or "").lower()
            if from_addr and from_addr not in platform_addresses:
                suspects.add(from_addr)
        return suspects

    async def _exclude_phishing_addresses(
        self,
        suspects: set[str],
        platform_addresses: set[str],
        token_price_map: dict[str, float],
        amount_per_out_threshold_usd: float,
    ) -> tuple[set[str], set[str]]:
        """步骤 2：过滤钓鱼地址。

        判定口径（按需求实现）：
        - 仅统计有价值代币交易。
        - 忽略 0 U 价值交易。
        - 目标地址的「入向交易额 / 出向交易笔数」超过阈值（默认 1.5 U）视为钓鱼。
        - 仅针对无标签地址生效（避免误删已知实体地址）。
        """
        if not suspects:
            return set(), set()

        tag_map = await self._get_label_map(list(suspects))
        filtered = set()
        phishing_addresses = set()

        for addr in suspects:
            # 已有标签（不含未知/空标签）默认不按钓鱼过滤。
            if self._is_labeled(tag_map.get(addr, [])):
                filtered.add(addr)
                continue

            stats = await self._get_address_value_stats(addr, token_price_map)
            out_count = stats["out_count"]
            in_value_usd = stats["in_value_usd"]
            ratio = in_value_usd / out_count if out_count > 0 else 0

            if ratio > amount_per_out_threshold_usd:
                phishing_addresses.add(addr)
            else:
                filtered.add(addr)

        return filtered, phishing_addresses

    async def _classify_users(
        self,
        filtered_suspects: set[str],
        platform_addresses: set[str],
    ) -> tuple[list[dict], set[str]]:
        """步骤 3：划分标准用户地址与非标准用户地址。"""
        standard_users: list[dict] = []
        non_standard_users: set[str] = set()

        for addr in filtered_suspects:
            outbound_counterparties = await self._get_outbound_counterparties(addr)
            if not outbound_counterparties:
                continue

            outbound_counterparties = {item for item in outbound_counterparties if item}
            if outbound_counterparties and outbound_counterparties.issubset(platform_addresses):
                addr_type = await self._address_output_type(addr)
                standard_users.append({"address": addr, "output_type": addr_type})
            elif outbound_counterparties & platform_addresses:
                non_standard_users.add(addr)

        return standard_users, non_standard_users

    async def _discover_unknown_platform_addresses(
        self,
        non_standard_users: set[str],
        platform_addresses: set[str],
        token_price_map: dict[str, float],
        max_user_counterparties: int,
        min_platform_counterparties: int,
        sample_size: int,
        min_entity_user_hits: int,
    ) -> set[str]:
        """步骤 4：识别同实体未知平台地址。"""
        candidates: set[str] = set()

        for user in non_standard_users:
            outbound = await self._get_outbound_counterparties(user)
            outbound = {cp for cp in outbound if cp and cp != "0x0000000000000000000000000000000000000000"}
            if len(outbound) >= max_user_counterparties:
                continue

            unlabeled_non_contract = await self._get_unlabeled_non_contract_counterparties(
                source=user,
                token_price_map=token_price_map,
                exclude=platform_addresses,
            )
            candidates.update(unlabeled_non_contract)

        result = set()
        for candidate in candidates:
            all_counterparties = await self._get_all_counterparties(candidate, remove_zero_value=True)
            if len(all_counterparties) <= min_platform_counterparties:
                continue

            inbound = await self._get_inbound_counterparties(candidate, remove_zero_value=True)
            if not inbound:
                continue

            sample = random.sample(inbound, min(sample_size, len(inbound)))
            label_map = await self._get_label_map(sample)
            entity_user_hits = sum(1 for addr in sample if self._contains_entity_user_tag(label_map.get(addr, [])))

            if entity_user_hits >= min_entity_user_hits:
                result.add(candidate)

        return result

    async def _get_outbound_counterparties(self, address: str) -> set[str]:
        query = {
            "query": {"bool": {"filter": [{"term": {"from": address}}, {"term": {"is_dest": True}}]}},
            "_source": ["to"],
        }
        counterparties = set()
        async for item in self.storage.es.iter_search("transfer", self.chain, query):
            to_addr = (item.get("to") or "").lower()
            if to_addr:
                counterparties.add(to_addr)
        return counterparties

    async def _get_address_value_stats(self, address: str, token_price_map: dict[str, float]) -> dict[str, float]:
        """统计地址的入向价值和出向笔数，忽略 0 U 价值交易。"""
        query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"is_dest": True}},
                        {
                            "bool": {
                                "should": [
                                    {"term": {"from": address}},
                                    {"term": {"to": address}},
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    ]
                }
            },
            "_source": ["from", "to", "send_token", "send_value"],
        }

        in_value_usd = 0.0
        out_count = 0
        async for item in self.storage.es.iter_search("transfer", self.chain, query):
            token = (item.get("send_token") or "").lower()
            price = token_price_map.get(token, 0)
            value = float(item.get("send_value") or 0)
            usd_value = value * price
            if usd_value <= 0:
                continue

            from_addr = (item.get("from") or "").lower()
            to_addr = (item.get("to") or "").lower()
            if to_addr == address:
                in_value_usd += usd_value
            if from_addr == address:
                out_count += 1

        return {"in_value_usd": in_value_usd, "out_count": out_count}

    async def _get_unlabeled_non_contract_counterparties(
        self,
        source: str,
        token_price_map: dict[str, float],
        exclude: set[str],
    ) -> set[str]:
        """获取 source 出向中无平台标签、无标签、非合约的对手地址 A。"""
        query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"from": source}},
                        {"term": {"is_dest": True}},
                    ]
                }
            },
            "_source": ["to", "send_token", "send_value"],
        }

        raw_targets = []
        async for item in self.storage.es.iter_search("transfer", self.chain, query):
            token = (item.get("send_token") or "").lower()
            usd = float(item.get("send_value") or 0) * token_price_map.get(token, 0)
            if usd <= 0:
                continue
            to_addr = (item.get("to") or "").lower()
            if to_addr and to_addr not in exclude:
                raw_targets.append(to_addr)

        if not raw_targets:
            return set()

        tag_map = await self._get_label_map(list(set(raw_targets)))
        contract_map = await self._get_contract_map(list(set(raw_targets)))

        return {
            addr
            for addr in raw_targets
            if not self._is_labeled(tag_map.get(addr, [])) and not contract_map.get(addr, False)
        }

    async def _get_all_counterparties(self, address: str, remove_zero_value: bool) -> set[str]:
        return await self._get_direction_counterparties(address, remove_zero_value=remove_zero_value, direction="both")

    async def _get_inbound_counterparties(self, address: str, remove_zero_value: bool) -> list[str]:
        pairs = await self._get_direction_counterparties(address, remove_zero_value=remove_zero_value, direction="in")
        return sorted(pairs)

    async def _get_direction_counterparties(self, address: str, remove_zero_value: bool, direction: str) -> set[str]:
        query = {
            "query": {
                "bool": {
                    "filter": [{"term": {"is_dest": True}}],
                    "must": [],
                }
            },
            "_source": ["from", "to", "send_value"],
        }

        if direction == "in":
            query["query"]["bool"]["must"].append({"term": {"to": address}})
        elif direction == "out":
            query["query"]["bool"]["must"].append({"term": {"from": address}})
        else:
            query["query"]["bool"]["must"].append(
                {
                    "bool": {
                        "should": [{"term": {"to": address}}, {"term": {"from": address}}],
                        "minimum_should_match": 1,
                    }
                }
            )

        counterparties = set()
        async for item in self.storage.es.iter_search("transfer", self.chain, query):
            if remove_zero_value and float(item.get("send_value") or 0) <= 0:
                continue

            from_addr = (item.get("from") or "").lower()
            to_addr = (item.get("to") or "").lower()
            if to_addr == address and from_addr:
                counterparties.add(from_addr)
            if from_addr == address and to_addr:
                counterparties.add(to_addr)

        return counterparties

    async def _get_label_map(self, addresses: list[str]) -> dict[str, list[dict]]:
        if not addresses:
            return {}

        raw = await self.storage.tag_api.get_tag_rels(self.chain, addresses)
        label_map: dict[str, list[dict]] = defaultdict(list)
        for row in raw:
            addr = (row.get("address") or "").lower()
            if addr:
                label_map[addr].append(row)
        return label_map

    async def _get_contract_map(self, addresses: list[str]) -> dict[str, bool]:
        if not addresses:
            return {}
        coll = self.storage.mongo.coll("data", "contract", self.chain)
        result = {addr: False for addr in addresses}
        async for row in coll.find({"_id": {"$in": addresses}}, {"_id": True}):
            result[row["_id"].lower()] = True
        return result

    async def _address_output_type(self, address: str) -> str:
        """EVM 地址按需求区分：合约地址标记为 single-love，其余为 evm。"""
        if self.chain == "tron":
            return "tron"

        contract_map = await self._get_contract_map([address])
        return "single-love" if contract_map.get(address, False) else "evm"

    @staticmethod
    def _is_labeled(tag_rows: list[dict]) -> bool:
        for row in tag_rows:
            if row.get("label") or row.get("tag") or row.get("entity_name"):
                return True
        return False

    @staticmethod
    def _contains_entity_user_tag(tag_rows: list[dict]) -> bool:
        for row in tag_rows:
            text = "|".join(str(v) for v in row.values()).lower()
            if "user" in text and ("entity" in text or "exchange" in text or "本实体" in text):
                return True
        return False