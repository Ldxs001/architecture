<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
Licensed under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0).
See https://creativecommons.org/licenses/by-sa/4.0/ for details.
-->

# 我思故我写 · 架构解析——七套核心系统的工程实现

![书封](cover.png)

> **Cogito, Scribo.** 我思，故我写。
>
> 母书《我思故我写》的姊妹卷：母书回答"为什么"，本册回答"怎么做"——七套核心系统的架构设计工程实现。

> **协议：本书整体采用 CC BY-SA 4.0**（署名-相同方式共享 4.0 国际）。详情见 `frontmatter/00_版权页.md`。

## 获取本册

| 方式 | 入口 |
|------|------|
| **在线阅读整本册子** | GitHub Pages：<https://ldxs001.github.io/architecture/> |
| **下载 PDF / HTML / EPUB** | 发行版 **arch-v1.0.0**（[Gitee](https://gitee.com/wUwproject/architecture/releases/tag/arch-v1.0.0) / [GitHub](https://github.com/Ldxs001/architecture/releases/tag/arch-v1.0.0)，含 PDF 打印版） |
| **册子源码（Markdown）** | 本目录 `book/`（frontmatter：版权页 / 导读 / 附录 A / 附录 B） |
| **构建管线** | `build/`（`python build.py` 一键构建，复用母书管线） |

## 本册的结构

| 部分 | 目录 | 内容 |
|------|------|------|
| 版权页 | `frontmatter/00_版权页.md` | 版本、协议、署名 |
| 导读 | `frontmatter/00_导读.md` | 七套系统的阅读路径 |
| 正文七篇 | 仓库根目录 `*-architecture.md` | skill-standardization / semantic-split / activity-duration-estimation / rag-assistant / structured-writer（成熟 5 篇）+ orchestrator / silprespec-orchestrator（实验性 2 篇） |
| 附录 A | `frontmatter/附录A_统一术语表.md` | 统一术语表 |
| 附录 B | `frontmatter/附录B_运行速查.md` | 运行速查 |

全册约 3.9 万字（arch-v1.0.0）。

## 目录结构

```
book/
├── README.md               # 本册门面（本文件）
├── cover.png               # 书封（1200×630）
├── cover.svg               # 书封矢量版
├── cover_wechat.png        # 微信宣传图（900×383）
├── frontmatter/            # 版权页 / 导读 / 附录 A 术语表 / 附录 B 运行速查
└── build/                  # 构建管线（assemble/md2html/make_pdf/count_words/gen_covers）
```

## 同系列

- 母书《我思故我写》：<https://gitee.com/wUwproject/Cogito_Scribit>（GitHub 同名仓库）
- 姊妹卷《排版解析》：<https://gitee.com/wUwproject/Cogito_Scribit/blob/main/typesetting/book/README.md>
- 源仓库双平台同步，内容一致，任选其一：
  - Gitee：<https://gitee.com/wUwproject/architecture>
  - GitHub：<https://github.com/Ldxs001/architecture>
