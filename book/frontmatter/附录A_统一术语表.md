<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
-->

# 附录 A：统一术语表

> 本表收拢七篇架构文档共用的概念。**承自母书的术语定义与母书附录 A 一字不差**（不另造定义）；架构册特有的工程术语单列，并注明使用范围。

## 一、承自母书的术语（定义见母书附录 A）

| 术语 | 一句话口径 | 母书出处 | 本册使用篇 |
|------|-----------|---------|-----------|
| 技能（Skill） | 带元数据声明、可被标准校验的工具包 | 母书第 I 部 | 全部 |
| 智能体（Agent） | 由链驱动架构编排的 LLM 执行系统 | 母书第 II 部 | 架构 04/05/07 |
| 链驱动执行（Chain-Driven） | 链是主体，LLM 只做两头，中间确定性执行 | 母书 05 | 架构 06 |
| 有限决策范式（Limited Decision） | LLM 只填空，不决策——决策权归链、架构与人 | 母书 08 | 全部 |
| 前置规范（Pre-emptive Specification） | 前置规范 > 后置验证——错误空间封堵在生成时刻 | 母书 08a | 架构 07 主线 |
| 空（Slot）/ 槽位 | LLM 填空的槽位，内容轴不可收束到点 | 母书 08b | 架构 04/05/07 |
| 槽位减法（Slot Subtraction） | 槽位是减法不是加法——子集接受语义损失换幻觉收敛 | 母书 08c | 架构 05/07 |
| 穷举（Enumeration） | 用枚举保证稳定；穷举是统计本质的定价 | 母书 09 | 架构 04/05/07 |
| 推动点位（Driver Point） | 配置推动把偏差钉在可指认的位置上 | 母书 09b | 架构 05 |

## 二、架构册特有术语

| 术语 | 定义 | 使用篇 |
|------|------|--------|
| 可执行原子（Executable Atom） | 技能拆解出的可执行单元（CLI/脚本/子步骤）——有主脚本入口的技能才可被编排 | 架构 06 |
| 可执行过滤（Executable Filter） | 纯提示词 skill（无主脚本入口）不进入 Pipeline 池——编排对象必须是真执行的 | 架构 06 |
| 组合（Combo） | silprespec-orchestrator 的前置规范单元：`生成（LLM）→ 后处理（PY）→ 校验（PY）→ 观测（PY）` 四段骨架，当前原子库下穷举 14 种 | 架构 07 |
| combo_registry | 14 种组合的声明注册表（`COMBOS: list[ComboSpec]`），PY 查表驱动，不存在第 15 种 | 架构 07 |
| PY 门禁 | Python 确定性校验/后处理层的统称——"达标"与否的裁判是代码，不是模型自评 | 架构 04/05/07 |
| exec_recipe | 组合的执行配方：generate / postprocess / validate / retry / observe 五元声明 | 架构 07（源承 silprespec-emulator） |
| ProgressMap（进度地图） | 贯穿编排全程的进度对象——子任务分解到执行汇总的每一步状态 | 架构 07 |
| KB 签名（KB Signature） | rag-assistant 的知识库关键词签名（四分法采样 + jieba 候选 + BCE 排序）——路由的精排依据 | 架构 04 |
| top-N 多 KB 路由 | route_query 收集所有过阈值 KB 按分降序取前 N 个并查（v2.3.0），`router.top_n` / `classify_threshold` | 架构 04 |
| vendor 自包含 | 第三方库嵌入 `vendor/` 目录（bs4/pypdfium2/markdownify…），零外部 pip 安装也可运行 | 架构 04 |
| 配置统一源（Config Unification） | 散落各文件的常量收拢为单一模块（如 structured-writer 的 `novel/nover_config.py`）——推动点位唯一化 | 架构 05 |
| 三智能体注册（Tool Registry） | silprespec-orchestrator 的 `tool_registry.py`：ToolSpec/FieldSpec/ExampleSpec 声明可调用的智能体及其输入槽位 | 架构 07 |
| 填空域（Fill Domain） | 一个 LLM 在一次协作中负责填充的边界——编排器/检索/写作各域不重叠不冲突 | 架构 05/06/07 |
