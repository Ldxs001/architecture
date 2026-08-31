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

## 架构解析（姊妹卷）

本仓库 7 篇核心架构文档已汇编为册子《**我思故我写 · 架构解析——七套核心系统的工程实现**》（arch-v1.0.0，CC BY-SA 4.0）——母书《我思故我写》的姊妹卷：母书回答"为什么"，本册回答"怎么做"。

| 项 | 入口 |
|----|------|
| 在线阅读整本册子（GitHub Pages） | <https://ldxs001.github.io/architecture/> |
| 下载 PDF / HTML / EPUB | 发行版 **arch-v1.0.0**（[GitHub](https://github.com/Ldxs001/architecture/releases/tag/arch-v1.0.0) / Gitee 同 tag，含 PDF 打印版） |
| 册子源码（版权页/导读/术语表/运行速查 + 封面） | [`book/`](book/) |
| 构建管线（MD → HTML/EPUB/PDF，复用母书管线） | `book/build/`（`python build.py` 一键构建） |

收录篇目：skill-standardization / semantic-split / activity-duration-estimation / rag-assistant / structured-writer（成熟 5 篇）+ orchestrator / silprespec-orchestrator（实验性 2 篇）。

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
├── index.html                 # 架构解析册在线阅读落地页（GitHub Pages）
├── *-architecture.md          # 各项目架构文档
└── book/                      # 架构解析册（版权页/导读/附录/封面/构建管线）
```

## 维护约定

- 本仓库由 wUwproject 维护，Gitee / GitHub 双平台同步
- 架构文档随对应项目演进更新，文档名与项目名一一对应
- 采用 CC BY-SA 4.0 协议，转载须注明出处
