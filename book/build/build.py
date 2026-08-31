# -*- coding: utf-8 -*-
"""
《我思故我写 · 架构解析》构建脚本
assemble → md2html → epub
用法: python build.py
"""
import os, sys, io, subprocess

BUILD = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BUILD)
sys.path.insert(0, BUILD)

def main():
    # 1) assemble
    from assemble import assemble, STRUCTURE
    book = assemble()
    out_md = os.path.join(BUILD, 'output')
    os.makedirs(out_md, exist_ok=True)
    md_path = os.path.join(out_md, '架构解析全书.md')
    with io.open(md_path, 'w', encoding='utf-8') as f:
        f.write(book)
    print(f'[1/3] 拼接: {md_path}（{len(book):,} 字符，{len(STRUCTURE)} 个部分）')

    # 2) md2html
    from md2html import convert
    html = convert(book, title='我思故我写 · 架构解析——七套核心系统的工程实现')
    html_path = os.path.join(out_md, 'book.html')
    with io.open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[2/3] HTML 预览: {html_path}')

    # 3) EPUB
    try:
        from build_epub import build_epub
        epub_path = os.path.join(out_md, 'book.epub')
        build_epub(md_path, epub_path)
        print(f'[3/3] EPUB 已生成: {epub_path}')
    except Exception as e:
        print(f'[3/3] EPUB 跳过: {e}')

    print('构建完成。输出目录:', out_md)

if __name__ == '__main__':
    main()
