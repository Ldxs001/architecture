<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
-->

# Architecture — 架构文档仓库

> wUwproject 各技能与智能体的架构设计文档集。CC BY-SA 4.0。

## 仓库定位

本仓库独立托管 wUwproject 的技能与智能体架构设计文档。2026-08-02 自 `workbuddy-skills` 仓库的 `architecture/` 目录独立拆分而来。

**历史提交说明：** 本仓库为全新初始化，不带历史提交。所有历史记录保留于永久存档仓库：

- Gitee: https://gitee.com/wUwproject/workbuddy-skills （`architecture/` 目录）
- GitHub: https://github.com/Ldxs001/workbuddy-skills （`architecture/` 目录）

## 文档列表

| 文档 | 对应项目 | 类别 |
|------|---------|------|
| skill-standardization-architecture.md | 标准化审计引擎 | 技能 |
| skill-function-test-architecture.md | 场景测试套件 | 技能 |
| semantic-split-architecture.md | 语义拆分规划 | 技能 |
| analysis-toolkit-architecture.md | 数据分析工具箱 | 技能 |
| activity-duration-estimation-architecture.md | 活动历时估算 | 技能 |
| round-robin-allocator-architecture.md | 均匀轮转分配 | 技能 |
| latex-modular-architecture.md | LaTeX 模块化组合 | 技能 |
| novel-weaver-architecture.md | 结构化小说写作 | 技能 |
| local-rag-builder-architecture.md | 本地 RAG 搭建 | 技能 |
| orchestrator-architecture.md | 链驱动编排引擎 | 智能体 |
| rag-assistant-architecture.md | 本地知识库智能体 | 智能体 |
| structured-writer-architecture.md | 结构化写作智能体 | 智能体 |

## 目录结构

```
architecture/
├── LICENSE                    # CC BY-SA 4.0
├── README.md
└── *-architecture.md          # 各项目架构文档
```

## 维护约定

- 本仓库由 wUwproject 维护，Gitee / GitHub 双平台同步
- 架构文档随对应项目演进更新，文档名与项目名一一对应
- 采用 CC BY-SA 4.0 协议，转载须注明出处
