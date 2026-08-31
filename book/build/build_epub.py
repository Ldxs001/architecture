# -*- coding: utf-8 -*-
"""
《我思故我写》零依赖 EPUB3 生成器
EPUB3 本质 = ZIP 包 + XHTML 内容 + OPF 元数据 + TOC。
用标准库 zipfile 手写，无需 ebooklib/pandoc。
用法: python build_epub.py [全书.md] [输出.epub]
"""
import sys, io, os, zipfile, uuid
from md2html import md_to_html

BOOK_TITLE = "我思故我写——一本 AI 写成的书：AI 时代的方法论、边界与人类自洽"
BOOK_AUTHOR = "wUwproject"
BOOK_ID = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "cogito-liber-v1"))

EPUB_NS = {
    'container': 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"',
    'opf': 'xmlns="http://www.idpf.org/2007/opf" version="3.0"',
    'xhtml': 'xmlns="http://www.w3.org/1999/xhtml"',
}

def split_sections(md_text):
    """按一级标题（# ）切分章节——每篇/组件一章（跳过代码块内的 # 注释行）"""
    lines = md_text.split('\n')
    sections = []
    cur_title, cur_body = None, []
    in_code = False
    for line in lines:
        stripped = line.strip()
        # 代码块开关：``` 切换状态（围栏长度 3+）
        if stripped.startswith('```'):
            in_code = not in_code
        if not in_code and line.startswith('# '):
            if cur_title:
                sections.append({'id': f'chap{len(sections)+1:03d}', 'title': cur_title, 'body': '\n'.join(cur_body)})
            cur_title = line[2:].strip()
            cur_body = [line]
        else:
            if cur_body is not None:
                cur_body.append(line)
    if cur_title:
        sections.append({'id': f'chap{len(sections)+1:03d}', 'title': cur_title, 'body': '\n'.join(cur_body)})
    if not sections:  # 兜底：无一级标题时按原逻辑
        raw = md_text.split('\n\n---\n\n')
        for i, part in enumerate(raw):
            title = '未命名'
            for line in part.split('\n'):
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
            sections.append({'id': f'chap{i+1:03d}', 'title': title, 'body': part})
    return sections

def make_xhtml(section):
    body = md_to_html(section['body'])
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html {EPUB_NS['xhtml']} lang="zh-CN" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/">
<head>
<meta charset="utf-8"/>
<title>{section['title']}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
{body}
</body>
</html>'''

def make_opf(sections):
    manifest = '\n'.join(
        f'    <item id="{s["id"]}" href="{s["id"]}.xhtml" media-type="application/xhtml+xml"/>'
        for s in sections)
    manifest += '\n    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
    manifest += '\n    <item id="css" href="style.css" media-type="text/css"/>'
    spine = '\n'.join(f'    <itemref idref="{s["id"]}"/>' for s in sections)
    nav_points = '\n'.join(
        f'      <navPoint id="nav{s["id"]}" playOrder="{i+1}"><navLabel><text>{s["title"]}</text></navLabel><content src="{s["id"]}.xhtml"/></navPoint>'
        for i, s in enumerate(sections))
    return f'''<?xml version="1.0" encoding="utf-8"?>
<package {EPUB_NS['opf']} unique-identifier="BookId">
  <metadata {EPUB_NS['opf']}>
    <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">{BOOK_TITLE}</dc:title>
    <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">{BOOK_AUTHOR}</dc:creator>
    <dc:identifier xmlns:dc="http://purl.org/dc/elements/1.1/" id="BookId">{BOOK_ID}</dc:identifier>
    <dc:language xmlns:dc="http://purl.org/dc/elements/1.1/">zh-CN</dc:language>
    <dc:rights xmlns:dc="http://purl.org/dc/elements/1.1/">CC BY-SA 4.0</dc:rights>
    <meta property="dcterms:modified">2026-08-12T00:00:00Z</meta>
  </metadata>
  <manifest>
{manifest}
  </manifest>
  <spine toc="ncx">
{spine}
  </spine>
</package>'''

def make_ncx(sections):
    points = '\n'.join(
        f'    <navPoint id="nav{s["id"]}" playOrder="{i+1}"><navLabel><text>{s["title"]}</text></navLabel><content src="{s["id"]}.xhtml"/></navPoint>'
        for i, s in enumerate(sections))
    return f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="{BOOK_ID}"/><meta name="dtb:depth" content="1"/></head>
  <docTitle><text>{BOOK_TITLE}</text></docTitle>
  <navMap>
{points}
  </navMap>
</ncx>'''

def make_container():
    return '''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''

EPUB_CSS = """
body { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.8; }
h1 { font-size: 1.6em; margin-top: 1.5em; }
h2 { font-size: 1.3em; }
blockquote { border-left: 3px solid #999; margin: .8em 0; padding: .3em 1em; color: #666; }
table { border-collapse: collapse; width: 100%; margin: .8em 0; }
th, td { border: 1px solid #bbb; padding: .3em .5em; word-break: keep-all; vertical-align: top; }
table.ref-table { table-layout: fixed; }
table.ref-table th:nth-child(1), table.ref-table td:nth-child(1) { width: 8%; }
table.ref-table th:nth-child(2), table.ref-table td:nth-child(2) { width: 47%; }
table.ref-table th:nth-child(3), table.ref-table td:nth-child(3) { width: 45%; }
table.ref-table th, table.ref-table td { overflow-wrap: anywhere; }
table td .ref-piece, table th .ref-piece { display: block; white-space: normal;
  word-break: keep-all; overflow-wrap: break-word; line-height: 1.7; }
pre { background: #f5f5f5; padding: .6em; overflow-x: auto; font-size: .85em; }
code { font-size: .9em; }
.math { font-family: "Times New Roman", Georgia, serif;
        font-style: italic; white-space: nowrap; }
.math sup, .math sub { font-style: normal; font-size: .72em; }
.math-block { text-align: center; margin: .8em 0; padding: .6em .9em;
              background: #f4f6fa; border: 1px solid #ccc; border-radius: 8px; }
.math-block .math { font-size: 1.1em; white-space: normal; }
hr { border: none; border-top: 1px solid #ccc; margin: 1.5em 0; }
.flow { margin: .8em 0; padding: .7em .9em;
        background: #f4f6fa; border: 1px solid #ccc; border-radius: 8px; }
.flow-phase { font-weight: bold; color: #2a6fd6; margin: .5em 0 .2em; }
.flow-step { background: #f0f4fa; border: 1px solid #ccc; border-radius: 4px;
             padding: .25em .6em; margin: .2em 0; line-height: 1.5; }
.flow-step.lv1 { background: rgba(160,166,172,.10); }
.flow-step.lv2 { background: rgba(122,148,178,.10); }
.flow-step.lv3 { background: rgba(126,158,138,.10); }
.flow-step.lv4 { background: rgba(158,138,116,.10); }
.flow-step.lv5 { background: rgba(158,150,168,.10); }
.flow-edge { color: #555; padding: .15em 0 .15em 1.5em; font-size: .95em; }
.flow-note { color: #777; font-size: .88em; padding: .15em 0; text-align: center; }
.flow-chain { display: flex; align-items: stretch; justify-content: center;
              flex-wrap: wrap; gap: .4em; margin: .8em 0;
              padding: .7em .9em; background: #f4f6fa; border: 1px solid #ccc; border-radius: 8px; }
.flow-chain-title { align-self: center; font-weight: bold; color: #2a6fd6;
                    font-size: 1.05em; margin-right: .4em;
                    padding: .3em .6em; background: #e8f0fb; border-radius: 6px; }
.flow-cnode { display: flex; flex-direction: column; justify-content: center;
              min-width: 5.5em; text-align: center; }
.flow-cnode .flow-step { margin: 0; }
.flow-cnode .flow-note { margin-top: .2em; }
.flow-carr { align-self: center; color: #2a6fd6; font-weight: bold; font-size: 1.15em; }
.flow-layers { margin: .8em 0; padding: .6em .8em;
               background: #f4f6fa; border: 1px solid #ccc; border-radius: 8px; }
.flow-layer { border: 1px solid #ccc; border-radius: 6px; margin: .5em 0;
              padding: .4em .6em; background: #fafbfd; }
.flow-layer.lv1 { background: rgba(160,166,172,.10); }
.flow-layer.lv2 { background: rgba(122,148,178,.10); }
.flow-layer.lv3 { background: rgba(126,158,138,.10); }
.flow-layer.lv4 { background: rgba(158,138,116,.10); }
.flow-layer.lv5 { background: rgba(158,150,168,.10); }
.flow-layer-name { font-weight: bold; color: #2a6fd6; margin-bottom: .2em; }
.flow-layer-item { line-height: 1.6; }
.flow-layer-key { color: #555; font-weight: bold; margin-right: .3em; }
.flow-tree { margin: .8em 0; padding: .6em .8em;
             background: #f4f6fa; border: 1px solid #ccc; border-radius: 8px;
             font-family: Consolas, "Courier New", monospace;
             font-size: .9em; line-height: 1.7; }
.flow-tnode { padding: .05em 0; white-space: nowrap; }
.flow-tmark { color: #888; margin-right: .35em; }
.flow-tnode.dir .flow-ttext { font-weight: bold; }
.flow-step.ellipsis-step { color: #999; }
.flow-treegroup { border: 1px solid #ccc; border-radius: 8px;
                  margin: .25em 0; padding: .35em .7em;
                  font-family: Consolas, "Courier New", monospace;
                  font-size: .9em; line-height: 1.7; }
.flow-treegroup.lv1 { background: rgba(160,166,172,.10); }
.flow-treegroup.lv2 { background: rgba(122,148,178,.10); }
.flow-treegroup.lv3 { background: rgba(126,158,138,.10); }
.flow-treegroup.lv4 { background: rgba(158,138,116,.10); }
.flow-treegroup.lv5 { background: rgba(158,150,168,.10); }
.flow-tree-row { padding: .08em 0; white-space: pre; }
.flow-tree-row.lv1 { background: rgba(160,166,172,.07); }
.flow-tree-row.lv2 { background: rgba(122,148,178,.07); }
.flow-tree-row.lv3 { background: rgba(126,158,138,.07); }
.flow-tree-row.lv4 { background: rgba(158,138,116,.07); }
.flow-tree-row.lv5 { background: rgba(158,150,168,.07); }
.flow-tnode.lv1 { background: rgba(160,166,172,.07); }
.flow-tnode.lv2 { background: rgba(122,148,178,.07); }
.flow-tnode.lv3 { background: rgba(126,158,138,.07); }
.flow-tnode.lv4 { background: rgba(158,138,116,.07); }
.flow-tnode.lv5 { background: rgba(158,150,168,.07); }
.flow-tree-row .flow-tmark { color: #888; }
.flow-cols { display: flex; gap: 1.2em; margin: .8em 0;
             padding: .7em .9em; background: #f4f6fa; border: 1px solid #ccc; border-radius: 8px; }
.flow-col { flex: 1; min-width: 0; }
.flow-col .flow-step { margin: .3em 0; }
.flow-col .flow-edge { padding-left: 0; text-align: center; color: #777; }
.flow-inline-arrow { color: #2a6fd6; font-weight: bold; margin: 0 .25em; }
.flow-arrow { color: #2a6fd6; text-align: center; line-height: 1.3; font-weight: bold;
              padding: .1em 0; }
.flow-edge .edge-fall { color: #2a6fd6; font-weight: bold; }
"""

def build_epub(md_path, out_path):
    with io.open(md_path, encoding='utf-8') as f:
        md_text = f.read()
    sections = split_sections(md_text)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', make_container())
        z.writestr('OEBPS/content.opf', make_opf(sections))
        z.writestr('OEBPS/toc.ncx', make_ncx(sections))
        z.writestr('OEBPS/style.css', EPUB_CSS)
        for s in sections:
            z.writestr(f'OEBPS/{s["id"]}.xhtml', make_xhtml(s))
    print(f'EPUB 已生成: {out_path}（{len(sections)} 章）')

if __name__ == '__main__':
    import os
    md = sys.argv[1] if len(sys.argv) > 1 else 'output/全书.md'
    out = sys.argv[2] if len(sys.argv) > 2 else 'output/book.epub'
    build_epub(md, out)
