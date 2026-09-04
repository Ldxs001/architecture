# -*- coding: utf-8 -*-
"""
《我思故我写 · 架构解析》书稿拼接脚本
将导读 + 8 篇架构文档拼接为单一书稿 Markdown。
用法: python assemble.py [输出路径]
零依赖（标准库）。入书规范参考 Cogito_Scribit STRUCTURE_GUIDE。

入书清洗（STRUCTURE_GUIDE 去留规则的管线级硬约束，arch-v1.0.1）：
- 剥 SPDX 头（strip_spdx）
- 剥章头「摘要 + 更新行/生成时间」blockquote（成书无摘要/日期戳）
- 剥篇尾「*最后更新：…*」脚注（成书无版本戳）
- 剥章尾「本文档基于 …综合分析整理」生成戳记 blockquote（与最后更新脚注同类写作痕迹，strip_compilation_note）
- 剥正文分隔线 `---`/`***`（代码块外独立行；成书层级由 ## 承担，排版册同款规则，strip_horizontal_rules）
- 章题统一为母书族系格式 `NN｜标题`（母书为 `第 X 部 · NN｜标题`，姊妹卷无部；去章题版本后缀）
"""
import sys, io, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 书的结构（顺序即书的顺序；按主书第 I 部工程线排序，实验性编排器两篇之后为演进收束篇）
# 元组第三项 = 成书章题（None = 保留源 H1，用于版权页/导读/附录）
STRUCTURE = [
    ("frontmatter/00_版权页.md", "版权页", None),
    ("frontmatter/00_导读.md", "导读", None),
    ("skill-standardization-architecture.md", "架构 01 · skill-standardization", "01｜skill-standardization 架构与规范体系文档"),
    ("semantic-split-architecture.md", "架构 02 · semantic-split", "02｜semantic-split 架构与规范体系文档"),
    ("activity-duration-estimation-architecture.md", "架构 03 · activity-duration-estimation", "03｜activity-duration-estimation 架构与规范体系文档"),
    ("rag-assistant-architecture.md", "架构 04 · rag-assistant", "04｜RAG Assistant 架构文档"),
    ("structured-writer-architecture.md", "架构 05 · structured-writer", "05｜Structured Writer 架构文档"),
    ("orchestrator-architecture.md", "架构 06 · orchestrator（实验性）", "06｜Orchestrator 架构文档"),
    ("silprespec-orchestrator-architecture.md", "架构 07 · silprespec-orchestrator（实验性）", "07｜silprespec-orchestrator 架构文档"),
    ("技能编排器到agent编排器——编排对象迁移与圈的z轴.md", "架构 08 · 演进收束篇", "08｜技能编排器到 agent 编排器——编排对象迁移与“圈”的 z 轴"),
    ("99_结语.md", "结语", None),
    ("appendix/统一术语表.md", "附录 A 统一术语表", "附录 A 统一术语表"),
    ("appendix/运行速查.md", "附录 B 运行速查", "附录 B 运行速查"),
]

def strip_spdx(text):
    """剥离 SPDX 头（HTML 注释块），保留正文"""
    return re.sub(r'<!--.*?-->', '', text, flags=re.S).lstrip('\n')

# 写作痕迹判据：篇尾版本戳 / 章头日期戳行
_FOOTNOTE_RE = re.compile(r'^\*最后更新：.*\*\s*$', re.M)
_STAMP_RE = re.compile(r'^\s*>\s*(更新：|生成时间：)', re.M)

def strip_writing_traces(body):
    """剥离写作痕迹：章头「摘要+更新行/生成时间」blockquote 与篇尾「最后更新」脚注。
    判据锚定：仅当章 H1 后紧跟的 blockquote 含日期戳行（更新：/生成时间：）才整块剥离——
    导读/附录的开篇 blockquote 无日期戳行，不受影响。"""
    lines = body.split('\n')
    h1_idx = next((i for i, l in enumerate(lines) if l.startswith('# ')), None)
    if h1_idx is not None:
        j = h1_idx + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].lstrip().startswith('>'):
            k = j
            while k < len(lines) and (lines[k].lstrip().startswith('>') or not lines[k].strip()):
                k += 1
            if _STAMP_RE.search('\n'.join(lines[j:k])):
                # 连带剥掉紧随的分隔线（摘要的 ---，非正文内容）
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines) and lines[k].strip() == '---':
                    k += 1
                rest = lines[k:]
                while rest and not rest[0].strip():
                    rest.pop(0)
                lines = lines[:h1_idx + 1] + [''] + rest
    lines = [l for l in lines if not _FOOTNOTE_RE.match(l)]
    return '\n'.join(lines)

def strip_compilation_note(body):
    """剥章尾「本文档基于 …综合分析整理」生成戳记 blockquote。
    与篇尾「*最后更新：…*」脚注同类——文档生成时刻的元信息戳记，非架构内容。
    判据锚定：blockquote 首行以 `> 本文档基于` 起始，连带跳过其连续 `>` 续行。"""
    lines, out, skipping = body.split('\n'), [], False
    for l in lines:
        ls = l.strip()
        if skipping:
            if ls.startswith('>'):
                continue
            skipping = False
        if ls.startswith('> 本文档基于'):
            skipping = True
            continue
        out.append(l)
    return '\n'.join(out)

def strip_horizontal_rules(body):
    """剥正文分隔线（代码块外独立 `---`/`***`/`___` 行）。
    成书章节层级由 `## N` 标题承担，横线为视觉冗余（排版册 STRUCTURE_GUIDE 同款规则）。
    代码块围栏内的横线属文本内容，保留。"""
    lines, out, in_code = body.split('\n'), [], False
    for l in lines:
        if l.strip().startswith('```'):
            in_code = not in_code
            out.append(l)
            continue
        if not in_code and l.strip() in ('---', '***', '___'):
            continue
        out.append(l)
    return '\n'.join(out)

def retitle(body, title):
    """章题对齐：替换首个 H1 为成书章题"""
    lines = body.split('\n')
    for i, l in enumerate(lines):
        if l.startswith('# '):
            lines[i] = f'# {title}'
            break
    return '\n'.join(lines)

def assemble():
    parts = []
    for rel, _label, title in STRUCTURE:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            # 架构篇在仓库根目录（book/ 上一级）
            path = os.path.join(ROOT, '..', rel)
        with io.open(path, encoding='utf-8') as f:
            text = f.read()
        body = strip_horizontal_rules(strip_compilation_note(strip_writing_traces(strip_spdx(text)))).strip()
        if title:
            body = retitle(body, title)
        parts.append(body)
    # 章间不注入 '---'：h1 已强制每章新页（break-before: page）
    return '\n\n'.join(parts)

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'output', '架构解析全书.md')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    book = assemble()
    with io.open(out, 'w', encoding='utf-8') as f:
        f.write(book)
    print(f'书稿已拼接: {out}（{len(book):,} 字符，{len(STRUCTURE)} 个部分）')

if __name__ == '__main__':
    main()
