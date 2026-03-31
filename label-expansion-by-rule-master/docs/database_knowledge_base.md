# 数据库知识库

## 目录

- [数据库知识库](#数据库知识库)
  - [目录](#目录)
  - [ES (Elasticsearch)](#es-elasticsearch)
    - [交易行为说明](#交易行为说明)
    - [索引别名](#索引别名)
    - [EVM 链](#evm-链)
      - [本币交易](#本币交易)
      - [内部交易](#内部交易)
      - [代币转账](#代币转账)
      - [兑币](#兑币)
      - [跨链](#跨链)
    - [Tron 链交易行为](#tron-链交易行为)
      - [本币交易](#本币交易-1)
      - [其他交易类型](#其他交易类型)
    - [其他链](#其他链)
    - [地址表](#地址表)
    - [Telegram 舆情](#telegram-舆情)
      - [TG 公群表](#tg-公群表)
      - [TG 用户表](#tg-用户表)
      - [TG 群 - 用户关系表](#tg-群---用户关系表)
      - [TG 消息表](#tg-消息表)
    - [开源情报](#开源情报)
      - [开源情报 News](#开源情报-news)
  - [Doris](#doris)
    - [日交易对](#日交易对)
    - [全量交易对](#全量交易对)
    - [地址统计](#地址统计)
  - [MongoDB](#mongodb)
    - [代币信息](#代币信息)
      - [token\_v3](#token_v3)
    - [合约信息](#合约信息)
      - [contract\_base](#contract_base)
    - [非单一链相关信息](#非单一链相关信息)
      - [cmc\_tokens\_all](#cmc_tokens_all)
      - [reliable\_coin](#reliable_coin)
      - [reliable\_token](#reliable_token)
  - [Nebula](#nebula)
    - [交易行为统计图](#交易行为统计图)


## ES (Elasticsearch)

**版本：** 7.17.22

### 交易行为说明

交易行为表中即有行为数据也有明细数据，通过标记字段（`is_dest`, `is_direct`）区分：

- **行为数据**：即抽象（穿透）了兑币跨链行为的资金流转关系的交易数据。
- **明细数据**：即原始的资金转移关系的交易数据。

### 索引别名

| 索引类型 | 索引别名 |
| --- | --- |
| 本币交易 | `{chain}_tx_behavior` |
| 内部交易 | `{chain}_inner_tx_behavior` |
| 代币转账 | `{chain}_transfer_behavior` |
| 兑币 | `{chain}_swap_behavior` |
| 跨链 | `{chain}_cross_behavior` |


### EVM 链

**支持的链：** eth, bsc, polygon, avalanche, arbitrum, optimism, base, klaytn, iotex, conflux

#### 本币交易

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| tx_hash | str | 交易 hash | |
| block_number | int | 区块号 | |
| block_time | int | 区块时间 | |
| tx_trigger | str | 取原始交易的 from 地址 | |
| tx_call_contract | str | 取原始交易的 to 地址，to 是合约的情况，非合约为 null | |
| from | str | from 地址 | |
| to | str | to 地址 | |
| send_value | int | 发送金额 | |
| send_token | str | 发送代币 | 忽略，无意义，本币交易默认 null |
| receive_value | int | 接收金额 | 和 send_value 相同 |
| receive_token | str | 接收代币 | 忽略，无意义，本币交易默认 null |
| trigger_type | str | 触发类型 | normal: 普通转账，transfer: 代币转账，custom: 触发合约 |
| tx_type | str | 交易类型 | tx: 本币交易，inner_tx: 内部交易，transfer: 代币交易，swap: 兑币交易，cross: 跨链；固定值：tx |
| tx_index | int | 交易在块中的 index | |
| index | int | 当前数据在交易中的 index | 本币交易 index 和 tx_index 相同 |
| contract_address | str | 创建的合约地址 | 部署合约交易特有 |
| is_direct | bool | 标记是否原始数据 | |
| is_dest | bool | 标记是否行为结果数据 | |
| type | str | 原始交易的 type | |
| fee | int | 交易费用 | |
| gas | int | 交易 gas | |
| gas_price | int | 交易 gas 价格 | |
| gas_used | int | 交易 gas 使用量 | |
| create_at | int | 数据入库时间 | |

#### 内部交易

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| tx_hash | str | 交易 hash | |
| block_number | int | 区块号 | |
| block_time | int | 区块时间 | |
| tx_trigger | str | 取原始交易的 from 地址 | |
| tx_call_contract | str | 取原始交易的 to 地址，to 是合约的情况，非合约为 null | |
| from | str | from 地址 | |
| to | str | to 地址 | |
| send_value | int | 发送金额 | |
| send_token | str | 发送代币 | 忽略，无意义，本币交易默认 null |
| receive_value | int | 接收金额 | 和 send_value 相同 |
| receive_token | str | 接收代币 | 忽略，无意义，本币交易默认 null |
| trigger_type | str | 触发类型 | normal: 普通转账，transfer: 代币转账，custom: 触发合约 |
| tx_type | str | 交易类型 | 固定值：inner_tx |
| tx_index | int | 交易在块中的 index | |
| index | int | 内部交易在交易中的 index | |
| is_direct | bool | 标记是否原始数据 | |
| is_dest | bool | 标记是否行为结果数据 | |
| type | str | 内部交易的 type | |
| gas | int | 交易 gas | |
| gas_price | int | 交易 gas 价格 | |
| gas_used | int | 交易 gas 使用量 | |
| create_at | int | 数据入库时间 | |

#### 代币转账

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| tx_hash | str | 交易 hash | |
| block_number | int | 区块号 | |
| block_time | int | 区块时间 | |
| tx_trigger | str | 取原始交易的 from 地址 | |
| tx_call_contract | str | 取原始交易的 to 地址，to 是合约的情况，非合约为 null | |
| from | str | from 地址 | |
| to | str | to 地址 | |
| send_value | int | 发送金额 | |
| send_token | str | 发送代币 | |
| receive_value | int | 接收金额 | 和 send_value 相同 |
| receive_token | str | 接收代币 | 和 send_token 相同 |
| trigger_type | str | 触发类型 | normal: 普通转账，transfer: 代币转账，custom: 触发合约 |
| tx_type | str | 交易类型 | 固定值：transfer |
| tx_index | int | 交易在块中的 index | |
| index | int | transfer 在交易中的 index | |
| is_direct | bool | 标记是否原始数据 | |
| is_dest | bool | 标记是否行为结果数据 | |
| create_at | int | 数据入库时间 | |

#### 兑币

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| tx_hash | str | 交易 hash | |
| block_number | int | 区块号 | |
| block_time | int | 区块时间 | |
| tx_trigger | str | 取原始交易的 from 地址 | |
| tx_call_contract | str | 取原始交易的 to 地址，to 是合约的情况，非合约为 null | |
| from | str | from 地址 | 兑币出钱地址 |
| to | str | to 地址 | 兑币收钱地址 |
| send_value | int | 发送金额 | |
| send_token | str | 发送代币 | 空字符串""表示本币 |
| receive_value | int | 接收金额 | |
| receive_token | str | 接收代币 | 空字符串""表示本币 |
| trigger_type | str | 触发类型 | 固定值：custom |
| tx_type | str | 交易类型 | 固定值：swap |
| tx_index | int | 交易在块中的 index | |
| index | int | swap 在交易中的 index | |
| is_direct | bool | 标记是否原始数据 | 固定值：false |
| is_dest | bool | 标记是否行为结果数据 | 固定值：true |
| lp_address | list | LP 合约地址列表 | |
| create_at | int | 数据入库时间 | |

#### 跨链

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| tx_hash | str | 交易 hash | |
| block_number | int | 区块号 | |
| block_time | int | 区块时间 | |
| tx_trigger | str | 取原始交易的 from 地址 | |
| tx_call_contract | str | 取原始交易的 to 地址，to 是合约的情况，非合约为 null | |
| from | str | from 地址 | 跨链未配对情况下可能为空 |
| to | str | to 地址 | 跨链未配对情况下可能为空 |
| send_value | int | 发送金额 | |
| send_token | str | 发送代币 | 空字符串""表示本币，null 表示未知（跨链未配对情况） |
| receive_value | int | 接收金额 | 跨链未配对情况下可能为空 |
| receive_token | str | 接收代币 | 空字符串""表示本币，null 表示未知（跨链未配对情况） |
| trigger_type | str | 触发类型 | 固定值：custom |
| tx_type | str | 交易类型 | 固定值：cross |
| tx_index | int | 交易在块中的 index | |
| index | int | cross 在交易中的 index | |
| is_direct | bool | 标记是否原始数据 | 固定值：false |
| is_dest | bool | 标记是否行为结果数据 | 固定值：true |
| cross_send_chain_id | str | 发送链 ID | 未配对情况下可能为 null |
| cross_receive_chain_id | str | 接收链 ID | 未配对情况下可能为 null |
| cross_opposite_block_time | int | 接收链区块时间 | 未配对情况下为 null |
| cross_opposite_tx_hash | str | 跨链对端交易哈希 | 未配对情况下为 null |
| cross_contract | str | 跨链合约 | |
| cross_protocol | str | 跨链协议 | |
| cross_associated | str | 跨链配对关联字段 | 数据内部使用 |
| paired_at | int | 跨链配对时间 | 未配对情况下为 null |
| create_at | int | 数据入库时间 | |

### Tron 链交易行为

#### 本币交易

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| tx_hash | str | 交易 hash | |
| block_number | int | 区块号 | |
| block_time | int | 区块时间 | |
| tx_trigger | str | 取原始交易的 from 地址 | |
| tx_call_contract | str | 取原始交易的 to 地址，to 是合约的情况，非合约为 null | |
| from | str | from 地址 | |
| to | str | to 地址 | |
| send_value | int | 发送金额 | |
| send_token | str | 发送代币 | 有值代币 TRC10 代币的 id 或名称 |
| receive_value | int | 接收金额 | 和 send_value 相同 |
| receive_token | str | 接收代币 | 同 send_token |
| trigger_type | str | 触发类型 | normal: 普通转账，transfer: 代币转账，custom: 触发合约 |
| tx_type | str | 交易类型 | 固定值：tx |
| tx_index | int | 交易在块中的 index | |
| index | int | 当前数据在交易中的 index | 本币交易 index 和 tx_index 相同 |
| contract_address | str | 创建的合约地址 | 部署合约交易特有 |
| is_direct | bool | 标记是否原始数据 | |
| is_dest | bool | 标记是否行为结果数据 | |
| type | str | 原始交易的 type | |
| fee | int | 交易费用 | |
| memo | str | 交易备注 | |
| cost | dict | 交易开销 | cost.net_usage: 消耗的带宽数量 cost.net_fee: 因带宽而燃烧的 TRX 数量 cost.energy_usage_total: 消耗的能量总量 cost.energy_fee: 因能量而燃烧的 TRX 数量 cost.energy_penalty_total: 因调用少数热门合约而需要支付的额外能量数量 cost.origin_energy_usage: 消耗的合约部署者的能量数量 |
| detail | dict | 不同交易特异性字段 | |
| create_at | int | 数据入库时间 | |

#### 其他交易类型

- **内部交易**：同 EVM 链内部交易
- **代币转账**：同 EVM 链代币转账
- **兑币**：同 EVM 链兑币
- **跨链**：同 EVM 链跨链


### 其他链

其他链（Zksync、Aleo、XRP、Aptos、Stacks、Solana、Ton、Neo、Omni、BTC、LTC）的交易行为表结构与 EVM 链类似，具体字段请参考原文档。


### 地址表

**索引名：** `{chain}_address`

用于地址模糊搜索，前缀 + 后缀精确搜索。

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| address | str | 完整地址 | text |
| addr_prefix | str | 前缀查询，限制最长 8 位 | keyword |
| addr_suffix_reverse | str | 后缀查询，字符串倒叙，限制最长 8 位 | keyword |

### Telegram 舆情

#### TG 公群表

**索引别名：** `poi_tg_group`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| group_id | long | 群 id |
| group_name | keyword | 群名，针对 keyword 可使用 wildcard 模糊搜索 |
| group_invite_url | keyword | 公群链接，针对 keyword 可使用 wildcard 模糊搜索 |
| group_status | integer | 群状态 |
| guarantee_platform | keyword | 担保平台 |
| business_type | keyword | 业务类型 |
| latest_chat_time | date | 最近聊天时间 |
| group_chat_type | keyword | 群聊天类型：0: 未知，1: 群组，2: 频道，3: 超级群组 |
| valid | bool | |
| create_time | date | 创建时间（毫秒） |
| update_time | date | 更新时间（毫秒） |

#### TG 用户表

**索引别名：** `poi_tg_user`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_id | long | 用户 id |
| name | keyword | 名称（last_name + first_name） |
| username | keyword | 用户名，针对 keyword 可使用 wildcard 模糊搜索 |
| phone | keyword | 手机号，针对 keyword 可使用 wildcard 模糊搜索 |
| first_name | keyword | |
| last_name | keyword | |
| status | integer | 状态 |
| create_time | date | 创建时间（毫秒） |
| update_time | date | 更新时间（毫秒） |

#### TG 群 - 用户关系表

**索引别名：** `poi_tg_group_user`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_id | long | 用户 id |
| group_id | long | 群 id |
| create_time | date | 创建时间（毫秒） |
| update_time | date | 更新时间（毫秒） |

#### TG 消息表

**索引别名：** `poi_tg_message`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| group_id | long | 群 id |
| sender_id | long | 用户 id |
| sender_username | keyword | 用户信息冗余字段 |
| sender_phone | keyword | 用户信息冗余字段 |
| sender_last_name | keyword | 用户信息冗余字段 |
| sender_first_name | keyword | 用户信息冗余字段 |
| message_id | integer | 消息 id |
| message_type | integer | 消息类型：1: 文本，2: 图片，3: 图文结合 |
| message_txt | text | 消息体（文本消息体） |
| message_image | binary | 消息体（图片消息体 base64） |
| message_image_path | keyword | 图片 obs 路径 |
| message_ocr | text | 消息体 OCR 识别出文本 |
| send_time | date | 消息发送时间 |
| flag | integer | 数据处理标识：-1: OCR 识别失败，0: OCR 未识别，1: OCR 识别成功，2: OCR 未识别出文字，4: 没有图片或无效图片 |
| create_time | date | 创建时间（毫秒） |
| update_time | date | 更新时间（毫秒） |

### 开源情报

#### 开源情报 News

**索引别名：** `poi_news_message`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| news_id | keyword | 舆情 id |
| url | keyword | 舆情内容 url |
| source | keyword | 来源 |
| author | keyword | 作者 |
| title | text | 标题 |
| content | text | 内容 |
| pub_time | date | 舆情发布时间（毫秒） |
| create_time | date | 创建时间（毫秒） |
| update_time | date | 更新时间（毫秒） |


## Doris

### 日交易对

| 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target_addr | varchar | 256 | 0 | Y | N | | 统计主体地址 |
| peer_type | tinyint | 4 | 0 | N | N | | 交易对类型，是行为数据的 is_direct 和 is_dest 两个字段的抽象；仅明细：1，仅行为：2，即是明细也是行为：3 |
| type | varchar | 16 | 0 | Y | N | | 交易类型，本币：tx，内部：inner_tx，ERC20 代币：transfer，兑币：swap，跨链（配对）：cross，跨链（未配对）：unpaired_cross |
| direction | tinyint | 4 | 0 | N | N | | 交易方向。1: 转出/兑出/跨出；2: 转入/兑入/跨入 |
| target_token | varchar | 256 | 0 | Y | N | | 代币地址 |
| period | datetime | 19 | 0 | Y | N | | 统计周期起始时间 |
| peer_addr | varchar | 256 | 0 | Y | N | | 与 target_addr 在指定形成方向上成对的地址 |
| peer_token | varchar | 2048 | 0 | Y | N | | 本次交易与 peer_addr 匹配的代币地址，普通代币转账时为空字符，只有兑币/跨链才有值 |
| peer_chain | varchar | 64 | 0 | Y | N | | peer_addr 所在链，只有跨链才有值 |
| contract | varchar | 2048 | 0 | Y | N | | 兑币使用的 LP / 跨链使用的 Cross contract |
| first_tx_time | bigint | 20 | 0 | Y | N | | 首次交易时间 |
| latest_tx_time | bigint | 20 | 0 | Y | N | | 最近交易时间戳 |
| tx_count | bigint | 20 | 0 | Y | N | | 交易量 |
| value | decimal | 39 | 0 | Y | N | | 交易额 |
| peer_value | decimal | 39 | 0 | Y | N | | 兑币/跨链关联 peer token 的交易额 |
| value_min | decimal | 39 | 0 | Y | N | | 最小交易额 |
| value_max | decimal | 39 | 0 | Y | N | | 最大交易额 |
| fee | decimal | 39 | 0 | Y | N | | 交易手续费 |
| peer | bitmap | | | 0 | N | N | 涉及的交易对手 |
| hashes | bitmap | | | 0 | N | N | 涉及的交易 hash |
| types | bitmap | | | 0 | N | N | 交易类型整形 BITMAP，用于计算涉及哪些交易类型 |
| periods | bitmap | | | 0 | N | N | 涉及的交易日期（安天） |
| update_time | datetime | 19 | 0 | Y | N | 记录的最后更新时间 |

### 全量交易对

| 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target_addr | varchar | 256 | 0 | Y | N | | 统计主体地址 |
| target_token | varchar | 256 | 0 | Y | N | | 代币地址 |
| direction | tinyint | 4 | 0 | N | N | | 交易方向。1: 转出/兑出/跨出；2: 转入/兑入/跨入 |
| peer_type | tinyint | 4 | 0 | N | N | | 交易对类型，是行为数据的 is_direct 和 is_dest 两个字段的抽象；仅明细：1，仅行为：2，即是明细也是行为：3 |
| type | varchar | 16 | 0 | Y | N | | 交易类型，本币：tx，内部：inner_tx，ERC20 代币：transfer，兑币：swap，跨链（配对）：cross，跨链（未配对）：unpaired_cross |
| peer_addr | varchar | 256 | 0 | Y | N | | 与 target_addr 在指定形成方向上成对的地址 |
| peer_token | varchar | 2048 | 0 | Y | N | | 本次交易与 peer_addr 匹配的代币地址，普通代币转账时为空字符串，只有兑币/跨链才有值 |
| peer_chain | varchar | 64 | 0 | Y | N | | peer_addr 所在链，只有跨链才有值 |
| contract | varchar | 2048 | 0 | Y | N | | 兑币使用的 LP / 跨链使用的 Cross contract |
| first_tx_time | bigint | 20 | 0 | Y | N | | 首次交易时间戳 |
| latest_tx_time | bigint | 20 | 0 | Y | N | | 最近交易时间戳 |
| tx_count | bigint | 20 | 0 | Y | N | | 交易量 |
| value | decimal | 39 | 0 | Y | N | | 交易额 |
| peer_value | decimal | 39 | 0 | Y | N | | 兑币/跨链关联 peer token 的交易额 |
| value_min | decimal | 39 | 0 | Y | N | | 最小交易额 |
| value_max | decimal | 39 | 0 | Y | N | | 最大交易额 |
| fee | decimal | 39 | 0 | Y | N | | 交易手续费 |
| hashes | bitmap | | | 0 | N | N | 涉及的交易 hash |
| types | bitmap | | | 0 | N | N | 交易类型整形 BITMAP，用于计算涉及哪些交易类型 |
| periods | bitmap | | | 0 | N | N | 涉及的交易日期（安天） |
| update_time | datetime | 19 | 0 | Y | N | | 记录的最后更新 |

### 地址统计

| 名称 | 数据类型 | 长度 | 小数位 | 允许空值 | 主键 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target_addr | varchar | 2048 | 0 | Y | N | | 统计主体地址 |
| peer_type | tinyint | 4 | 0 | N | N | | 交易对类型 |
| type | varchar | 16 | 0 | Y | N | | 交易类型 |
| direction | tinyint | 4 | 0 | N | N | | 交易方向 |
| target_token | varchar | 2048 | 0 | Y | N | | 代币地址 |
| peer_chain | varchar | 64 | 0 | Y | N | | peer_addr 所在链，只有跨链才有值 |
| first_tx_time | bigint | 20 | 0 | Y | N | | 首次交易时间戳 |
| latest_tx_time | bigint | 20 | 0 | Y | N | | 最近交易时间戳 |
| tx_count | bigint | 20 | 0 | Y | N | | 交易量 |
| value | decimal | 39 | 0 | Y | N | | 交易额 |
| value_min | decimal | 39 | 0 | Y | N | | 最小交易额 |
| value_max | decimal | 39 | 0 | Y | N | | 最大交易额 |
| fee | decimal | 39 | 0 | Y | N | | 交易手续费 |
| peer | bitmap | 0 | N | N | | 涉及的交易对手 | |
| peer_hll | hll | 0 | N | N | | 涉及的交易对手（HLL） | |
| hashes | bitmap | 0 | N | N | | 涉及的交易 hash | |
| types | bitmap | 0 | N | N | | 交易类型整形 BITMAP | |
| periods | bitmap | 0 | N | N | | 涉及的交易日期（按天） | |
| update_time | datetime | 19 | 0 | Y | N | | 记录的最后更新时间 |

## MongoDB

### 代币信息

#### token_v3

**数据库：** {chain}

存放代币信息（主要维护精度和币价信息）。

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| _id | str | 代币地址 | |
| name | str | 代币名称 | |
| symbol | str | 代币简称 | |
| decimal | int | 代币精度 | |
| price | float | 代币币价（计算或手动设置） | 业务上仅当没有 cmc_price 时采用该字段 |
| cmc_price | float | 代币币价（cmc 定时更新） | 业务上优先于 price 字段 |
| cmc_id | str | 代币在 cmc 上的 id | |
| total_supply | str | 总供应量（经过精度换算） | |
| website | str | 代币官网 | |
| logo | str | 代币 logo 地址 | |
| logo_base64 | str | 代币的 logo base64 编码 | |
| create_time | int | 数据创建时间戳 | |
| update_time | int | 数据更新时间戳 | |
| price_update_time | int | 币价更新时间戳 | |
| version | int | 数据版本，每次更新递增 1 | |


### 合约信息

#### contract_base

**数据库：** {chain}

存放链上合约的基本信息。

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| _id | str | 合约地址 | |
| abi | list | 合约的接口 | list 的每一项均为一个字典 |
| create_at | int | 合约创建的时间戳 | |
| create_block | int | 合约创建的区块号 | |
| create_hash | str | 合约创建的交易哈希 | |
| create_time | int | 数据首次入库的时间戳 | |
| creator | str | 合约的创建者地址 | |
| decimals | int | 代币精度 | 代币合约才有值 |
| destroy_block | int | 合约销毁的区块号 | |
| destroy_hash | str | 合约销毁的交易哈希 | |
| destroy_time | int | 合约销毁的时间戳 | |
| destroy_type | str | 合约销毁的类型 | |
| destroyed | bool | 合约是否销毁 | |
| erc-1155 | bool | 合约是否符合 erc1155 协议 | |
| erc-20 | bool | 合约是否符合 erc20 协议 | |
| erc-721 | bool | 合约是否符合 erc721 协议 | |
| logo | str | 项目 logo 的 url | |
| name | str | 代币的名称 | 代币合约才有值 |
| name_prefix | str | 代币的名称的缩写 | 即 name 的最多前 30 位 |
| symbol | str | 代币的符号 | 代币合约才有值 |
| symbol_prefix | str | 代币的符号的缩写 | 即 symbol 的最多前 20 位 |
| update_time | int | 文档最近更新的时间戳 | |
| version | int | 文档的版本号 | 每次更新加 1 |
| logic_address | str | 代理合约地址 | |
| is_token | bool | 合约是否为代币 | |
| trigger | str | 创建合约的交易的发起者 | |


### 非单一链相关信息

#### cmc_tokens_all

**数据库：** chain_info

cmc 获取到的币种列表，一个币种在多个链的有多条数据。

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| _id | ObjectId | | |
| chain | str | 链 | |
| cmc_id | str | CMC 上对应的币种 ID | |
| token | str | 代币地址 | |
| logo | str | 代币图标 | |
| name | str | 代币名称 | |
| symbol | str | 代币标识 | |
| create_time | int | 数据首次入库的时间戳 | |
| update_time | int | 文档最近更新的时间戳 | |
| date_time | datetime | 文档最近更新的日期时间 | |
| version | int | 文档的版本号，每次更新加 1 | |

#### reliable_coin

**数据库：** chain_info

根据日成交量、周成交量、月成交量阈值过滤出的「可信币」及其价格，每天将清空重入。

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| _id | int | CMC ID | |
| cmc_rank | int | CMC 上的币种排名 | |
| name | str | 代币名称 | |
| symbol | str | 代币标识 | |
| total_supply | float | 供应量 | |
| price | float | 币价 | |
| volume24h | float | 日成交量 | |
| volume7d | float | 周成交量 | |
| volume30d | float | 月成交量 | |
| date_time | datetime | 数据更新日期时间 | |
| create_time | int | 数据首次入库的时间戳 | |

#### reliable_token

**数据库：** chain_info

可信代币列表

| 字段 | 类型 | 释义 | 备注 |
| --- | --- | --- | --- |
| _id | ObjectId | | |
| cmc_id | str | CMC ID | |
| chain | str | 链 | |
| token | str | 代币地址 | |
| name | str | 代币名称 | |
| symbol | str | 代币标识 | |
| logo | str | 代币图标 | |
| is_coin | bool | 是否本币 | 包含各链平台币、包装本币，以及 USDT/USDC |
| date_time | datetime | 数据更新日期时间 | |
| create_time | int | 数据首次入库的时间戳 | |
| update_time | int | 文档最近更新的时间戳 | |
| version | int | 文档的版本号，每次更新加 1 | |


## Nebula

### 交易行为统计图

（此处可添加交易行为统计图的相关信息）
