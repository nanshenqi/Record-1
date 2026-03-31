from enum import StrEnum, auto


# EVM 链
class EVMChain(StrEnum):
    arbitrum = auto()
    avalanche = auto()
    base = auto()
    bsc = auto()
    conflux = auto()
    eth = auto()
    hsk = auto()
    iotex = auto()
    klaytn = auto()
    optimism = auto()
    polygon = auto()
    zksync = auto()


# UTXO 模型链
class UTXOChain(StrEnum):
    btc = auto()
    doge = auto()
    ltc = auto()


# 存在主账户子账户模型的链
class OwnerChain(StrEnum):
    solana = auto()
    ton = auto()


# 其它链
class OtherChain(StrEnum):
    aptos = auto()
    xrp = auto()


# 所有链，包含 EVM + Tron + UTXO + Owner + Other
class Chain(StrEnum):
    arbitrum = auto()
    avalanche = auto()
    base = auto()
    bsc = auto()
    conflux = auto()
    eth = auto()
    hsk = auto()
    iotex = auto()
    klaytn = auto()
    optimism = auto()
    polygon = auto()
    zksync = auto()

    tron = auto()

    btc = auto()
    doge = auto()
    ltc = auto()

    solana = auto()
    ton = auto()

    aptos = auto()
    xrp = auto()


# 链必追相关链
# NOTE: 需明确应在什么场景下使用链必追相关链。标签服务于公司所有产品，而非仅限于链必追。
class LbzChain(StrEnum):
    # EVM 链
    arbitrum = auto()
    avalanche = auto()
    base = auto()
    bsc = auto()
    eth = auto()
    optimism = auto()
    polygon = auto()
    zksync = auto()

    # 其它链
    tron = auto()
    solana = auto()
