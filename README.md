<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
-->

# Architecture — 架构文档仓库

> wUwproject 各技能与智能体的架构设计文档集。CC BY-SA 4.0。

## 系列三部曲

| 母书 | 姊妹卷 · 排版 | 姊妹卷 · 架构（本仓库） |
|------|--------------|----------------------|
| <a href="https://gitee.com/wUwproject/Cogito_Scribit/blob/main/book/README.md"><img src="assets/mother-cover.png" width="330" alt="《我思故我写》"></a> | <a href="https://gitee.com/wUwproject/Cogito_Scribit/blob/main/typesetting/book/README.md"><img src="assets/typ-cover.png" width="330" alt="《排版解析》"></a> | <a href="book/README.md"><img src="book/cover.png" width="330" alt="《架构解析》"></a> |
| **我思故我写**——一本 AI 写成的书 | **排版解析**——五层排版如何把一篇文章变成一本书 | **架构解析**——七套核心系统的工程实现 |
| 回答"为什么" | 回答"怎么排" | 回答"怎么做" |

## 仓库定位

本仓库独立托管 wUwproject 的技能与智能体架构设计文档。2026-08-02 自 `workbuddy-skills` 仓库的 `architecture/` 目录独立拆分而来。

**历史提交说明：** 本仓库为全新初始化，不带历史提交。所有历史记录保留于永久存档仓库：

- Gitee: https://gitee.com/wUwproject/workbuddy-skills （`architecture/` 目录）
- GitHub: https://github.com/Ldxs001/workbuddy-skills （`architecture/` 目录）

## 架构解析（姊妹卷）

本仓库 8 篇核心文档已汇编为册子《**我思故我写 · 架构解析——七套核心系统的工程实现**》（arch-v1.1.2，约 4.4 万字，CC BY-SA 4.0）——母书《我思故我写》的姊妹卷：母书回答"为什么"，本册回答"怎么做"。

收录篇目：skill-standardization / semantic-split / activity-duration-estimation / rag-assistant / structured-writer（成熟 5 篇）+ orchestrator / silprespec-orchestrator（实验性 2 篇，编排器两代）+ 演进收束篇《技能编排器到 agent 编排器——编排对象迁移与"圈"的 z 轴》（架构 08，以编排器两代为标本的论述篇，非系统）。

**册子的在线阅读、下载（PDF / HTML / EPUB）、入书规范（`STRUCTURE_GUIDE.md`）与构建入口统一见 [`book/README.md`](book/README.md)，发行说明见 [`成册说明_架构解析.md`](成册说明_架构解析.md)。**

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
| silprespec-orchestrator-architecture.md | 前置规范编排器 | 智能体 |
| 技能编排器到agent编排器——编排对象迁移与圈的z轴.md | 演进收束篇（编排对象迁移论述，架构 08） | 架构论述 |
| rag-assistant-architecture.md | 本地知识库智能体 | 智能体 |
| structured-writer-architecture.md | 结构化写作智能体 | 智能体 |

## 目录结构

```
architecture/
├── LICENSE                    # CC BY-SA 4.0
├── README.md
├── STRUCTURE_GUIDE.md         # 《架构解析》入书排版规范（清洗/同步/字数/版本/构建）
├── 成册说明_架构解析.md        # 册子发行说明（收录/结构/核对同步/获取）
├── index.html                 # 架构解析册在线阅读落地页（GitHub Pages）
├── *-architecture.md          # 各项目架构文档
├── assets/                    # 跨仓库展示用封面
└── book/                      # 架构解析册（门面/版权页/导读/附录/封面/构建管线，详见 book/README.md）
```

## 维护约定

- 本仓库由 wUwproject 维护，Gitee / GitHub 双平台同步
- 架构文档随对应项目演进更新，文档名与项目名一一对应
- 采用 CC BY-SA 4.0 协议，转载须注明出处
