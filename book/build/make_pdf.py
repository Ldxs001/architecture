# -*- coding: utf-8 -*-
"""《我思故我写 · 架构解析》打印版 PDF 全流程生成脚本。

流程：
1. PIL 渲染封面 PNG（思源黑体 OTF 直接画入图片，150dpi A4）
2. book/build/output/book.html → 打印版 HTML（去 dark / 思源黑体
   @font-face / 打印 CSS）→ Playwright 渲染正文 PDF（@page 精确 18mm 边距）
3. PyMuPDF 合并：封面页 + 正文页

产物：book_print.pdf（封面独立 PDF 页 + 正文 Type3 思源黑体矢量字形，
零字体嵌入、零分发争议；封面与正文物理分离，不会互相污染）
用法：cd book/build/PDF && python make_pdf.py
前置：pip install playwright pillow pymupdf
      python -m playwright install chromium
      本目录须有 SourceHanSansSC-Regular/Medium/Bold.otf（封面 + @font-face）
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(BASE, 'output', 'book.html'))
TMP_HTML = os.path.join(BASE, 'book_print.tmp.html')
BODY_PDF = os.path.join(BASE, 'book_print.body.pdf')
OUT = os.path.join(BASE, 'book_print.pdf')

FONT_BODY = '"SourceHanPrint", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif'
FONT_MONO = '"DejaVu Sans Mono", "SourceHanPrint", Consolas, monospace'

FONT_FACE = """@font-face {
  font-family: "SourceHanPrint";
  src: url("SourceHanSansSC-Regular.otf") format("opentype");
  font-weight: normal;
}
@font-face {
  font-family: "SourceHanPrint";
  src: url("SourceHanSansSC-Medium.otf") format("opentype");
  font-weight: 500;
}
@font-face {
  font-family: "SourceHanPrint";
  src: url("SourceHanSansSC-Bold.otf") format("opentype");
  font-weight: bold;
}"""

PRINT_CSS = """@page {
  size: A4;
  margin: 18mm 16mm;
}
@media print {
  /* 打印去掉 body padding/margin，边距由 @page 控制 */
  body { padding: 0 !important; max-width: none; margin: 0 !important; }
  /* 代码块长行强制换行：pre 默认 white-space:pre 不换行，打印无滚动条，
     超宽行会被直接裁掉（raw 输出/长行文本必现）——pre-wrap 保留原换行
     并允许软换行，overflow-wrap:anywhere 兜底超长词/URL */
  pre { white-space: pre-wrap; overflow-wrap: anywhere; }
  /* 书籍标准分页：版权页/序言/阅读指南/每篇/结语/附录各自独立起页 */
  h1 { break-before: page; }
  /* 小节标题不落页末：标题与后续内容同页 */
  h2, h3, h4 { break-after: avoid; }
  /* 段落防孤立行（页首/页底最少 2 行；3 太严，触发整段推页造成大空白） */
  p { orphans: 2; widows: 2; }
  /* 列表项多为单行：widows 2 会让单行 bullet（1 行 < 2）永远被推下页留白 */
  li { orphans: 1; widows: 1; }
  /* 分隔线/修饰符不独占一页（break-before 去掉：hr 前禁断页与 h2 后禁断页
     形成"保护链"，Chrome 会把 hr+h2 尾部整块推下页，留下半页空白） */
  hr, .flow-arrow { break-inside: avoid; break-after: avoid; }
  /* 纵向结构（pre 代码块 / flow 流程图 / flow-tree / table 表格）允许在
     内容单元间拆页：行内不拆（见下）、表格跨页重复表头（thead），
     避免"整块搬下页"留白；横向并排/层叠结构与引用块保持不拆 */
  table { break-inside: auto; }
  blockquote, .flow-cols, .flow-layers { break-inside: avoid; }
  .flow-step, .flow-layer, tr { break-inside: avoid; }
  /* 超长元素（单页装不下）：就地分页。
     JS 在渲染前检测 offsetHeight > 单页可用高度，动态加 print-overflow。
     避免"先整体搬下一页、下一页仍装不下再分页"导致第一页留大空白。 */
  thead { display: table-header-group; }
  table.print-overflow, blockquote.print-overflow { break-inside: auto; }
}"""


def make_cover_png():
    """PIL 渲染 A4 封面图（300dpi 印刷标准，2480×3508）
    到 BASE/cover.png（PNG 无损——渐变数据是平滑插值，PNG 预测滤波
    压缩率极高，实测 0.17MB 比 JPEG q88 还小，且文字无振铃、
    渐变无 DCT 块伪影）。
    配色与原 cover.svg 一致（深蓝渐变 #12224A→#081630 + 金色标 #C9A45C），
    文字用思源黑体 OTF 直接画入图片（图片内文字，非字体分发）。
    注意：封面是位图，打印分辨率 = 像素 ÷ 8.27 英寸——300ppi 为印刷
    行业标准；600ppi 在 A4 阅读距离无感知增益。"""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 2480, 3508  # A4 @300dpi
    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    top = (18, 34, 74)   # #12224A
    bot = (8, 22, 48)    # #081630
    for y in range(H):
        t = y / (H - 1)
        draw.line([(0, y), (W, y)],
                  fill=tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    reg = os.path.join(BASE, 'SourceHanSansSC-Regular.otf')
    bold = os.path.join(BASE, 'SourceHanSansSC-Bold.otf')
    medium = os.path.join(BASE, 'SourceHanSansSC-Medium.otf')
    f_kicker = ImageFont.truetype(medium, 88)
    f_title = ImageFont.truetype(bold, 238)
    f_sub = ImageFont.truetype(reg, 109)
    f_sub2 = ImageFont.truetype(reg, 75)
    f_meta = ImageFont.truetype(reg, 59)
    f_ver = ImageFont.truetype(reg, 53)
    f_note = ImageFont.truetype(reg, 41)
    GOLD = (201, 164, 92)
    LIGHT = (232, 237, 248)
    SUB = (216, 223, 236)
    SUB2 = (150, 165, 195)
    META = (150, 165, 195)
    VER = (124, 139, 176)
    NOTE = (143, 160, 191)

    def center(text, font, y, fill):
        w = draw.textlength(text, font=font)
        draw.text(((W - w) / 2, y), text, font=font, fill=fill)

    center('COGITO · SCRIBO', f_kicker, 519, GOLD)
    center('架构解析', f_title, 759, LIGHT)
    center('我思故我写 · 姊妹卷', f_sub, 1181, SUB)
    center('七套核心系统的工程实现', f_sub2, 1381, SUB2)
    draw.line([(W / 2 - 360, 1600), (W / 2 + 360, 1600)], fill=(201, 164, 92, 140), width=6)
    center('wUwproject · CC BY-SA 4.0 · 免费公开', f_meta, 2659, META)
    center('arch-v1.1.0 · 2026 年 9 月', f_ver, 2841, VER)
    note = '本书文字（含书名、标题、正文、图表标注）使用思源黑体（Source Han Sans SC）渲染，字体采用 SIL OFL 1.1 开源许可。'
    nw = draw.textlength(note, font=f_note)
    draw.text(((W - nw) / 2, 3241), note, font=f_note, fill=NOTE)
    out = os.path.join(BASE, 'cover.png')
    img.save(out, 'PNG', optimize=True)
    print('封面 PNG 已生成（300dpi 2480×3508 无损）:', out)


def build_print_html():
    with io.open(SRC, encoding='utf-8') as f:
        t = f.read()
    # 1) 去掉 dark 媒体查询（打印强制 light）
    t = re.sub(r'@media \(prefers-color-scheme: dark\) \{.*?\n\}', '', t, flags=re.S)
    # 2) 字体栈干净替换（从原始 book.html 出发，避免叠加）
    t = t.replace('"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif', FONT_BODY)
    t = t.replace('Consolas, "Courier New", monospace', FONT_MONO)
    t = t.replace('"PingFang SC", "Microsoft YaHei"', FONT_BODY)  # 兜底形态
    # 3) 注入 @font-face + 打印 CSS
    t = t.replace('</style>', FONT_FACE + '\n' + PRINT_CSS + '\n</style>', 1)
    with io.open(TMP_HTML, 'w', encoding='utf-8', newline='\n') as f:
        f.write(t)
    print('打印版 HTML 已生成:', TMP_HTML)
    print('dark 块残留:', '@media (prefers-color-scheme: dark)' in t,
          '| YaHei 残留(回退链内):', 'Microsoft YaHei' in t,
          '| @page CSS:', '@page {' in t)


def render_pdf():
    html_url = 'file:///' + TMP_HTML.replace('\\', '/')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # A4 @96dpi = 794x1123px；视口与 @page 打印布局一致，保证表格测量准确
        page = browser.new_page(viewport={'width': 794, 'height': 1123})
        page.goto(html_url, wait_until='networkidle')
        page.evaluate('document.fonts.ready.then(() => true)')
        page.wait_for_timeout(2000)
        fonts = page.evaluate('''() => {
            const used = [];
            for (const f of document.fonts) {
                if (f.status === 'loaded') used.push(f.family + ':' + f.weight);
            }
            return used.slice(0, 10);
        }''')
        print('已加载字体:', fonts)
        # 超长元素标记：offsetHeight > 单页可用高度（A4 1123px - 上下 18mm 边距 68px×2）
        # → 加 print-overflow（break-inside:auto，就地分页），避免整体搬页留大空白
        overflow_tables = page.evaluate('''() => {
            const usable = 1123 - 2 * 68;
            const marked = [];
            document.querySelectorAll('table, blockquote').forEach(t => {
                if (t.offsetHeight > usable) {
                    t.classList.add('print-overflow');
                    marked.push(t.tagName + ':' + t.rows?.length + '行');
                }
            });
            return marked;
        }''')
        print('超长元素标记:', overflow_tables if overflow_tables else '无')
        page.pdf(path=BODY_PDF, prefer_css_page_size=True,
                 print_background=True)
        browser.close()
    # 合并：封面页（PIL PNG → A4 页）置于正文前
    import fitz
    cover_png = os.path.join(BASE, 'cover.png')
    body = fitz.open(BODY_PDF)
    cover = fitz.open()
    page = cover.new_page(width=595, height=842)  # A4 pt
    page.insert_image(fitz.Rect(0, 0, 595, 842), filename=cover_png)
    cover.insert_pdf(body)
    # deflate=True：PyMuPDF 嵌入 PNG 时存未压缩像素（~25MB），
    # Flate 重压后 ~3.9MB（垂直渐变行间重复，压缩率极高）
    cover.save(OUT, garbage=3, deflate=True)
    n = cover.page_count
    cover.close()
    body.close()
    # 后处理：先定位正文起始页（版权页 h1），页码从版权页 = 1 起
    # （封面/目录无页码，书籍规范）；目录页加链接 + 点线 + PDF 书签
    h1_page = find_h1_page(OUT)
    add_page_numbers(OUT, h1_page)
    add_toc_dots(OUT, h1_page)
    os.remove(BODY_PDF)
    print(f'PDF 已生成（封面 + 正文 {n-1} 页 = 共 {n} 页，含页码/目录点线/书签）:', OUT)
    os.remove(TMP_HTML)  # 中间产物不留（可随时再生成）
    print('临时 HTML 已清理:', TMP_HTML)


def find_h1_page(path):
    """定位正文起始页：首个大字号（>15pt）"版权页"标题行。
    标题可能被拆成单字 span，须按行合并判断。"""
    import fitz
    doc = fitz.open(path)
    total = doc.page_count
    h1_page = None
    for pi in range(1, total):
        d = doc[pi].get_text('dict')
        found = False
        for b in d['blocks']:
            if 'lines' not in b:
                continue
            for line in b['lines']:
                ltext = ''.join(sp['text'] for sp in line['spans']).strip()
                max_size = max((sp['size'] for sp in line['spans']), default=0)
                if ltext == '版权页' and max_size > 15:
                    h1_page = pi
                    found = True
                    break
            if found:
                break
        if h1_page:
            break
    doc.close()
    return h1_page


def add_page_numbers(path, h1_page):
    """在 PDF 底部 margin 区插入页码：奇页右下 / 偶页左下（外侧）。
    封面 + 目录无页码；版权页 = 页码 1，之后递增。
    页码奇偶 = 物理页奇偶（封面+目录共 8 页为偶，偏移一致）。"""
    import fitz
    doc = fitz.open(path)
    total = doc.page_count
    font = fitz.Font('helv')
    for i in range(h1_page, total):
        page = doc[i]
        n = i - h1_page + 1  # 版权页 = 1
        w, h = page.rect.width, page.rect.height  # 595 x 842
        text = str(n)
        tw = font.text_length(text, fontsize=9)
        y = h - 24  # 底部 margin 区（18mm≈51pt 内）
        if n % 2 == 1:
            x = w - 40 - tw  # 奇页（右页）右下角，靠外
        else:
            x = 40           # 偶页（左页）左下角，靠外
        page.insert_text((x, y), text, fontname='helv', fontsize=9,
                         color=(0.45, 0.45, 0.45))
    doc.save(path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    print(f'页码已插入（{total-1} 页，奇右偶左）')


def add_toc_dots(path, h1_page):
    """目录点线引导 + 页码 + 链接 + PDF 书签。
    Chromium 不支持 CSS target-counter() 且打印不生成内部链接/书签，
    全部由 PyMuPDF 后处理：
    1. 提取目录行（标题 + y）→ 在正文按"大字号标题行"匹配各标题所在页
    2. 目录行尾部画虚线 + 页码（页码 = 目标页 - h1_page + 1，版权页 = 1）
    3. 目录行加内部链接（点击跳转目标页）
    4. 生成 PDF 书签大纲（l1 = 部/篇/附录，l2 = 小节；按缩进 x 判断层级）"""
    import fitz
    doc = fitz.open(path)
    total = doc.page_count
    if h1_page is None:
        doc.close()
        print('目录点线：未找到正文起始页，跳过')
        return
    # 1) 提取目录行（目录页 = 1..h1_page-1）
    rows = []  # (page_idx, y_center, x0, x1, text)
    for pi in range(1, h1_page):
        d = doc[pi].get_text('dict')
        for b in d['blocks']:
            if 'lines' not in b:
                continue
            for line in b['lines']:
                s = ''.join(sp['text'] for sp in line['spans']).strip()
                if s:
                    y = (line['bbox'][1] + line['bbox'][3]) / 2
                    x0 = line['bbox'][0]
                    x1 = line['bbox'][2]
                    rows.append((pi, y, x0, x1, s))
    # 2) 正文标题匹配（大字号标题行 + 顺序锚定）
    gray = (0.6, 0.6, 0.6)
    font = fitz.Font('helv')
    drawn = 0
    bookmarks = []  # (level, title, page_1based)
    last_target = h1_page - 1
    for pi, y, x0, x1, text in rows:
        key = text.replace(' ', '').replace('\u3000', '')[:14]
        if not key:
            continue
        target = None
        for pj in range(max(h1_page, last_target), total):
            d = doc[pj].get_text('dict')
            hit = False
            for b in d['blocks']:
                if 'lines' not in b:
                    continue
                for line in b['lines']:
                    ltext = ''.join(sp['text'] for sp in line['spans'])
                    max_size = max((sp['size'] for sp in line['spans']), default=0)
                    if max_size >= 12 and ltext.replace(' ', '').replace('\u3000', '').startswith(key):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                target = pj
                break
        if target is None:
            continue
        last_target = target
        page = doc[pi]
        # 虚线：标题右端 → 页码左
        dx1 = min(x1 + 6, 400)
        page.draw_line((dx1, y), (532, y), color=gray, width=0.7,
                       dashes='[3 3] 0')
        # 页码右对齐；版权页 = 1
        num = str(target - h1_page + 1)
        tw = font.text_length(num, fontsize=8.5)
        px = 548 - tw
        page.insert_text((px, y + 3), num, fontname='helv',
                         fontsize=8.5, color=(0.45, 0.45, 0.45))
        # 目录行链接（点击跳转目标页顶部）
        link_rect = fitz.Rect(x0 - 2, y - 8, 556, y + 8)
        page.insert_link({'kind': fitz.LINK_GOTO, 'from': link_rect,
                          'page': target, 'to': fitz.Point(0, 0)})
        # 书签：l1 = x0 < 65（部/篇/附录），l2 = 缩进小节
        level = 1 if x0 < 65 else 2
        bookmarks.append([level, text, target + 1])
        drawn += 1
    # 3) 写 PDF 书签大纲
    if bookmarks:
        doc.set_toc(bookmarks)
    doc.save(path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    print(f'目录点线/链接/书签已生成（{drawn} 条）')


if __name__ == '__main__':
    make_cover_png()
    build_print_html()
    render_pdf()
