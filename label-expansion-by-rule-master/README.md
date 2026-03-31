# 规则扩充

按既定规则扩充标签的异步 Python 项目。

## 项目概览

本项目根据指定规则分析链上数据，并将结果接入现有标签体系。
运行入口会根据配置中的规则名选择对应处理器，再由处理器通过统一的 Storage 封装访问 Doris、Elasticsearch、MongoDB 和标签接口。

当前仓库的默认约束如下：

- Python 版本为 3.11 及以上。
- 使用 uv 管理依赖。

## AI 协作文件

仓库已补充项目级 AI 协作说明，便于后续 Vibe Coding 任务保持一致性：

- `.trae/rulse/*.md`：应始终生效的项目规则。
- `.trae/skills/add-handler/SKILL.md`：新增或修改处理器时使用。
- `.trae/skills/storage-access/SKILL.md`：访问数据库或标签接口时使用。

这些文件面向 AI 协作，不替代本 README 的项目说明。

使用 VSCode + GitHub Copilot Chat 时，应该在配置中添加如下片段，以便能够兼容 .trae 目录：

```json
    "chat.agentFilesLocations": {
        ".trae/agents": true
    },
    "chat.agentSkillsLocations": {
        ".trae/skills": true
    },
    "chat.instructionsFilesLocations": {
        ".trae/rules": true
    }
```

## 核心结构

```text
.trae/                    # AI 规则和技能目录，以团队内使用人数最多的 Trae 编辑器标准存储
  rules/                  # 始终生效的项目规则
  skills/                 # 按需加载的技能手册
docs/
  database_knowledge_base.md  # 数据库和索引结构说明
src/
  enums/                  # 常用枚举值，如 EVM 链、所有链等
  handlers/               # 规则处理器
  storage/                # Doris、ES、Mongo、Tag API 等数据源交互封装
  utils/                  # 可复用工具函数
  config.py               # 默认配置
  main.py                 # 规则入口，根据 rule 选择处理器
```

## 运行流程

1. `src/main.py` 读取默认配置。
2. 运行时按“环境变量 CONFIG > 本地配置 > 默认配置”的优先级合并配置。
3. 从 SERVICE_CONFIG.rule 读取当前规则名。
4. 通过 rule_handler 映射选择对应的 Handler 子类。
5. 处理器执行 run 方法，并通过 self.storage 访问数据源。
6. 执行结束后统一关闭底层连接。

## 数据访问方式

业务逻辑统一通过 self.storage 访问数据源，不在 handler 中重复创建底层连接。

常见访问方式如下：

- Doris：self.storage.doris.search(data_key, chain, sql, args)
- Elasticsearch：self.storage.es.search(data_key, chain, query)
- Elasticsearch 大结果集：self.storage.es.iter_search(data_key, chain, query)
- MongoDB：self.storage.mongo.coll(client_name, data_key, chain)
- 可信币列表：self.storage.mongo.get_reliable_tokens(chain, price_gt_0=True)
- 标签接口：self.storage.tag_api.get_tag_rels(chain, addr_list)

使用数据源时应优先依赖 `src/config.py` 中的 data_map 映射，不要在业务代码中重复硬编码物理库名、表名、索引名或集合名。

## 配置说明

默认配置定义在 `src/config.py` 中，支持以下覆盖顺序（优先级从高到低）：

1. 环境变量 CONFIG，格式为 JSON 字符串。
2. 本地调试配置 `src/local_config.py`。
3. 仓库默认配置 `src/config.py`。

配置覆盖规则如下：

- 基础类型直接覆盖。
- 列表整体覆盖。
- 字典递归覆盖到最内层字段。

常用配置分组：

- CHAIN：当前运行链。
- SERVICE_CONFIG：规则运行配置，例如当前 rule。
- STORAGE_CONFIG：Doris、ES、Mongo、Tag API 及映射配置。
- THRESHOLD_CONFIG：规则的指标、阈值配置。

## 开发约定

### 代码风格

- 遵循 ruff 规则，行宽为 120。
- 优先选择直接、清晰、可维护的实现，不做过度抽象。
- 保持现有命名风格、目录结构、模块边界和公共接口稳定。

### 注释与文案

- 业务逻辑方法应补充足以说明业务约束的注释。
- 注释应解释为什么这样做，而不只是复述代码行为。
- 中文与英文、数字混排时按照「盘古之白」规范保留半角空格，应规范使用全角或半角标点符号。

### 配置新增原则

- 规则运行相关配置优先放入 SERVICE_CONFIG。
- 指标、阈值类配置优先放入 THRESHOLD_CONFIG，并按规则名分组。
- 存储相关配置放入 STORAGE_CONFIG。
- 新增配置前先检查是否已有等价配置可复用，避免重复语义。

## 新增规则的标准流程

1. 阅读现有入口和相近 handler，确认可以复用的模式。
2. 在 `src/handlers/` 下新增处理器文件，并继承 Handler。
3. 实现 run 方法和必要的辅助方法。
4. 若有跨规则复用逻辑，提取到 `src/utils/`。
5. 如需新增配置，更新 `src/config.py`。
6. 更新 `src/handlers/__init__.py`。
7. 更新 `src/main.py` 中的 rule_handler。

可参考的现有文件：

- `src/handlers/sample.py`
- `src/handlers/base.py`
- `src/main.py`

## 安装与运行

### 安装依赖

```shell
uv sync
```

如果当前环境无法使用 uv，也可以使用 pip 从内部源安装：

```shell
pip install . -i http://123.60.136.30:38080/simple --trusted-host 123.60.136.30:38080
```

### 本地调试

1. 准备本地覆盖配置。
2. 将需要调试的 rule 写入 SERVICE_CONFIG.rule。
3. 补齐对应链的数据源连接配置。
4. 运行以下命令：

```shell
uv run src/main.py
```

### 生产部署

1. 自动构建 Docker 镜像并推送。
2. 由 K8s Job 或 CronJob 调度运行。
3. 通过环境变量 CONFIG 注入运行配置。

## 相关文档

- `docs/database_knowledge_base.md`：数据库、索引和字段说明。
- `k8s/job.yaml`：一次性任务部署模板。
- `k8s/cronjob.yaml`：定时任务部署模板。

## 开发任务建议输入

如果要让 AI 或协作者更快落地新规则，建议在需求中尽量说明：

1. 规则名称。
2. 适用链或链范围。
3. 输入数据来源。
4. 核心判定条件。
5. 预期输出内容。
6. 是否需要新增配置、日志或文档。
