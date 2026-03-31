# 目录说明

本目录用于沉淀可跨编辑器、跨 IDE 复用的 AI 协作约束。

## 结构约定

- rules：始终生效的项目级规则，所有任务都应遵守的约束。
- skills：按需加载的任务手册，特定工作流的步骤、检查项和最佳实践等。

## 当前拆分

- `rules/project.instructions.md`：项目全局规则。
- `skills/add-handler/SKILL.md`：新增或修改规则处理器（handlers）时使用。
- `skills/storage-access/SKILL.md`：访问 Doris、ES、MongoDB 或标签接口时使用。

## 维护原则

- rules 确保是项目全局范围的必要约束，尽量保持单文件，保持简洁有力。
- skills 只写任务流程和专项注意事项，不重复抄写全局规则。
- 若某条规则适用于所有任务，放到 rules；若只在特定任务下才需要，放到对应 skill。
