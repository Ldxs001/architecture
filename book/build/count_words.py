# -*- coding: utf-8 -*-
"""严格字数多口径统计"""
import io, re, sys
sys.stdout.reconfigure(encoding='utf-8')
t = io.open(r'C:\Users\sm001\WorkBuddy\architecture\book\build\output\架构解析全书.md', encoding='utf-8').read()

# 1. 原始字符数
total = len(t)

# 2. 去空白
no_ws = len(re.sub(r'\s', '', t))

# 3. 纯汉字（CJK 统一表意文字）
cjk = len(re.findall(r'[\u4e00-\u9fff]', t))

# 4. 汉字 + 中文标点（全角标点）
cjk_punct = len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2014\u2018\u2019\u201c\u201d\u2026]', t))

# 5. 去 markdown 语法符号后的可见字符
no_md = re.sub(r'[#*|\-`>\[\]()]', '', t)
no_md_ws = len(re.sub(r'\s', '', no_md))

# 6. 出版折算口径：汉字数 + 英文单词数 + 连续数字串数（中文出版常见折算）
text_no_md = re.sub(r'[#*|\-`>\[\]()]', '', t)
cjk_cnt = len(re.findall(r'[\u4e00-\u9fff]', text_no_md))
en_words = len(re.findall(r'[A-Za-z]+', text_no_md))
num_groups = len(re.findall(r'\d[\d.,]*(?![\d])', text_no_md))
# 纯字母串（如 p(x)、KB）中的英文按单词计，但公式符号也计入会虚高
pub_est = cjk_cnt + en_words + num_groups

print(f'① 全书.md 总字符(含空白/md语法): {total:,}')
print(f'② 去除所有空白: {no_ws:,}')
print(f'③ 纯汉字数(CJK): {cjk:,}')
print(f'④ 汉字+中文标点: {cjk_punct:,}')
print(f'⑤ 去md语法符号+空白: {no_md_ws:,}')
print(f'⑥ 出版折算(汉字+英文词+数字串): {pub_est:,}  (汉字 {cjk_cnt:,} + 英文词 {en_words:,} + 数字串 {num_groups:,})')
