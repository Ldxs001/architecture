<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
-->

# 《架构解析》入书排版规范（STRUCTURE GUIDE）

> 本文档固定《我思故我写 · 架构解析——七套核心系统的工程实现》成书的全部标准：单篇规范、入书清洗、配套同步、字数统计、版本号与构建/发布管线。
> 分工：本文档管"架构文档定稿后怎么变成书"（book/ 目录的成书全过程）；架构文档自身的写法（系统概览 → 模块划分 → 核心机制 → 边界）与"文档同步代码"纪律，见各篇开头声明与导读。
> 基准范本：arch-v1.0.0 成册 + arch-v1.0.1 清洗管线化补全（2026-09-02 固化）+ arch-v1.1.0 演进收束篇（架构 08）入书（2026-09-03）+ arch-v1.1.1 文意修订（z 轴正解立规 + 三组术语词汇对照，不增篇/章，2026-09-03） + arch-v1.1.2 印刷字体事故根因修复（不增篇/章，2026-09-03）。
> 标准一旦固定不再变动——改规范 = 改本文档 + 改 assemble/build 脚本 + 全量 rebuild。

---

## 一、单篇规范（仓库顶层 `*-architecture.md`）

仓库顶层架构文档 14 篇（技能 9 + 智能体 4 + 架构论述 1），其中 **8 篇入书**（成熟 5 + 实验性 2 + 演进收束 1，见导读），其余 6 篇保持仓库文档形态（入书判据见第三章）。单篇结构要素：

| 元素 | 形态 |
|---|---|
| SPDX 头 | HTML 注释块（CC-BY-SA-4.0，Copyright 2026 wUwproject） |
| H1 | `# {工具名} 架构与规范体系文档`（部分篇为 `# {工具名} 架构文档`；入书后重命名为 `NN｜标题`，无部） |
| 章头摘要 | H1 后 blockquote，首行"完整解读 vX.X.X 版的架构设计…"，内含 `更新：日期（版本 → 版本，变更摘要）` 日期戳行 |
| 正文 | 随系统而异：系统概览 → 模块划分 → 核心机制 → 边界 / 版本历史表自含（版本号跟随对应工具真实版本） |
| 章尾戳记 | 两类并存：`*最后更新：YYYY-MM-DD (vX.X.X)*` 脚注，或 `> 本文档基于 vX.X.X 的 SKILL.md + references/*.md + 核心脚本综合分析整理。` blockquote |

---

## 二、转化规则（该去除的去除，该保留的保留）

入书清洗全部由 `book/build/assemble.py` 管线执行（源文保留，成书统一；不手工改单篇）：

| 单篇元素 | 成书处理 | 实现（assemble.py） |
|---|---|---|
| SPDX 头 | **剥** | `strip_spdx`（HTML 注释块） |
| H1 标题 | **重命名** `NN｜标题`（母书为 `第 X 部 · NN｜标题`，姊妹卷无部；去章题版本后缀） | `retitle` |
| 章头摘要 blockquote（含 `更新：`/`生成时间：` 日期戳行） | **整块剥**（判据锚定：仅当 H1 后紧跟的 blockquote 含日期戳行才剥——导读/附录开篇 blockquote 无日期戳，不受影响） | `strip_writing_traces` + `_STAMP_RE` |
| 章尾 `*最后更新：…*` 脚注 | **剥** | `_FOOTNOTE_RE` |
| 章尾「本文档基于 …综合分析整理」blockquote | **剥**（与最后更新脚注同类生成戳记；01/02/03 篇独有，arch-v1.0.1 补） | `strip_compilation_note` |
| 正文分隔线 `---`/`***`（代码块外独立行） | **剥**（成书层级由 `## N` 承担，横线为视觉冗余；代码块内 ASCII 图中的 `---` 属文本内容保留） | `strip_horizontal_rules`（arch-v1.0.1 补） |
| 正文（表格/代码块/说明 blockquote/版本历史表） | **全部保留** | — |
| 章间连接 | **不注入 `---`**（H1 已强制每章新页 break-before: page） | `assemble()` |

---

## 三、配套同步清单（入书/发版后必做，缺一不可）

**入书判据**：新架构文档是否收入册子——成熟/实验性两档（对应导读"实验性说明"）；未入书文档（如 skill-function-test、analysis-toolkit、round-robin-allocator、latex-modular、novel-weaver、local-rag-builder）保持仓库文档，随项目演进更新，不因未入书而降级维护。

| 文件 | 动作 |
|---|---|
| `book/build/assemble.py` | STRUCTURE 列表注册新篇（`("顶层文档.md", "架构 NN · 工具名", "NN｜标题")`），顺序按正文排布 |
| `book/frontmatter/00_版权页.md` | 规模/章数行、版本历史追加一条（版本号 + 变更 + **全书 N 章**，章数必改） |
| `book/frontmatter/00_导读.md` | 映射表加行（架构篇/系统版本/对应母书篇目/落地原则）；"七系统关系总览"若涉及分层结构同步 |
| `book/frontmatter/附录A_统一术语表.md` | 术语若有新增/变更同步 |
| `book/frontmatter/附录B_运行速查.md` | 运行方式若有变更同步 |
| 根目录 `README.md` | 姊妹卷段版本/字数；文档列表行（**全部 14 篇都列**，含未入书） |
| `book/README.md` | 获取表 release tag、规模行、正文八篇/附录说明 |
| **`index.html`（在线阅读落地页）** | PDF 下载链接 release tag、底部版本/日期（**历史上最易漏**，arch-v1.0.1 教训：内容已入库而 index 停在 arch-v1.0.0，见第七章） |
| `book/build/make_pdf.py` | 封面版本字（`center('arch-vX.Y.Z · YYYY 年 M 月', …)`） |
| 全书重建 | `cd book && python build/build.py`（assemble → 全书.md + book.html + book.epub，输出"（12 章）"须与版权页一致）→ `python build/make_pdf.py`（封面 + 打印版 PDF）→ `python build/count_words.py` 取字数 |

---

## 四、字数统计规范（全量维护点）

字数口径统一为 `book/build/count_words.py` ⑥出版折算（汉字 + 英文词 + 数字串）。**章节数/正文变化时，以下位置全部同步，缺一即 FAIL：**

| # | 位置 | 内容 |
|---|---|---|
| 1 | `count_words.py` | 统计脚本（自动，无硬编码） |
| 2 | `book/frontmatter/00_版权页.md` | `约 X.X 万字（出版折算口径）…12 章` |
| 3 | 根目录 `README.md` | `（arch-vX.Y.Z，约 X.X 万字…）` |
| 4 | `book/README.md` | `全册约 X.X 万字（arch-vX.Y.Z）` |
| 5 | `index.html` | 结构卡片/底部版本（本册落地页精简版，当前不含字数表述，若加须同步） |

当前值：约 4.4 万字（出版折算 44,947），12 章（版权页 + 导读 + 架构 01-08 + 附录 A/B）。

---

## 五、版本号规范（全量维护点）

**版本规则**：新增入书篇/附录结构变化/章节数变化 → 次版本 +1（arch-v1.0.2 → arch-v1.1.0：新增演进收束篇架构 08，正文 7→8 篇、11→12 章）；纯清洗修正、文档/规范文档新增 → 修订号 +1（arch-v1.0.1 → arch-v1.0.2）。**章数变化与版本号变化必须同时发生。**

| # | 位置 | 内容 | 更新时机 |
|---|---|---|---|
| 1 | `book/frontmatter/00_版权页.md` | 版本行 + 版本历史追加条目 | 任何实质变更 |
| 2 | 根目录 `README.md` | 姊妹卷段 `arch-vX.Y.Z` | 同上 |
| 3 | `book/README.md` | 获取表 release tag + 规模行 | 同上 |
| 4 | **`index.html`** | PDF 下载链接 `arch-vX.Y.Z/book_arch-vX.Y.Z.pdf` + 底部版本日期 | 同上（**最易漏**） |
| 5 | `book/build/make_pdf.py` | PDF 封面版本字 | 同上 |
| 6 | GitHub/Gitee Release | tag `arch-vX.Y.Z` + 附件 | 发布时 |

**三端一致校验**：版权页版本号 == 根 README tag == book/README 获取表 == index.html PDF 链接 == PDF 封面版本字，任一不一致即 FAIL。Release 发行：GitHub/Gitee 双平台 Release（tag `arch-vX.Y.Z`，附件命名 `book_arch-vX.Y.Z.{pdf,html,epub}`）；PDF 附件随内容更新同步替换（Gitee 同名上传为新增，需先删旧）。

---

## 六、构建与发布管线

```text
顶层文档 ×8 + frontmatter ×4
        │ python build/build.py
        ▼
assemble.py（清洗 + 章题重命名 + 拼接）
        → output/架构解析全书.md
        → md2html → output/book.html
        → build_epub → output/book.epub（12 章）
        │ python build/make_pdf.py（playwright 渲染）
        ▼
封面 PNG（300dpi 2480×3508）+ book_print.pdf（封面 + 正文，页码奇右偶左 + 目录点线/书签）
        │ python build/count_words.py
        ▼
⑥ 出版折算字数（全量维护点，见第四章）
```

- `output/` 三件进仓（GitHub Pages 在线阅读依赖 book.html）；`book_print.pdf`/封面 PNG/字体不进仓（.gitignore），由 Release 附件承载
- 发布：commit → tag `arch-vX.Y.Z` → Gitee/GitHub 双远端 push → 双平台 Release + `book_arch-vX.Y.Z.{pdf,html,epub}` 附件

---

## 七、历史教训（防止复发）

1. **清洗规则要全量覆盖 + 产物实证扫描**（arch-v1.0.1）：清洗管线化首版只剥了章头摘要与"最后更新"脚注，漏了章尾「本文档基于 …综合分析整理」生成戳记（01/02/03 篇独有）与正文分隔线 `---`（68 处）——成书七篇尾部样式不一。修复后须对产物做逐篇尾部/残留模式实证扫描（`本文档基于`/`最后更新`/`更新：`/正文 `---` 全零），不能只信改动声明。
2. **门面版本同步滞后**（arch-v1.0.1）：内容与版权页已推进到 arch-v1.0.1，但根 README/book README/index.html/PDF 封面仍停 arch-v1.0.0——发版前必须 grep 全仓版本串逐处对齐，index.html 是历史上最易漏的位置。
3. **生成戳记会把过期版本暴露给读者**：01/02/03 篇编制说明内版本（如 activity-duration-estimation v1.11.0）已与导读映射表（v1.11.7）脱节——这类文档生成时刻的元信息必须入书剥离，正文版本以导读/各篇版本历史为准。
