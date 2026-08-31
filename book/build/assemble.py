# -*- coding: utf-8 -*-
"""
《我思故我写 · 架构解析》书稿拼接脚本
将导读 + 7 篇架构文档拼接为单一书稿 Markdown。
用法: python assemble.py [输出路径]
零依赖（标准库）。入书规范参考 Cogito_Scribit STRUCTURE_GUIDE。
"""
import sys, io, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 书的结构（顺序即书的顺序；按主书第 I 部工程线排序，实验性两篇收尾）
STRUCTURE = [
    ("frontmatter/00_版权页.md", "版权页"),
    ("frontmatter/00_导读.md", "导读"),
    ("skill-standardization-architecture.md", "架构 01 · skill-standardization"),
    ("semantic-split-architecture.md", "架构 02 · semantic-split"),
    ("activity-duration-estimation-architecture.md", "架构 03 · activity-duration-estimation"),
    ("rag-assistant-architecture.md", "架构 04 · rag-assistant"),
    ("structured-writer-architecture.md", "架构 05 · structured-writer"),
    ("orchestrator-architecture.md", "架构 06 · orchestrator（实验性）"),
    ("silprespec-orchestrator-architecture.md", "架构 07 · silprespec-orchestrator（实验性）"),
    ("frontmatter/附录A_统一术语表.md", "附录 A 统一术语表"),
    ("frontmatter/附录B_运行速查.md", "附录 B 运行速查"),
]

def strip_spdx(text):
    """剥离 SPDX 头（HTML 注释块），保留正文"""
    return re.sub(r'<!--.*?-->', '', text, flags=re.S).lstrip('\n')

def assemble():
    parts = []
    for rel, _label in STRUCTURE:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            # 架构篇在仓库根目录（book/ 上一级）
            path = os.path.join(ROOT, '..', rel)
        with io.open(path, encoding='utf-8') as f:
            text = f.read()
        body = strip_spdx(text).strip()
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
