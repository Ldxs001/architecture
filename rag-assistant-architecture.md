<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
Licensed under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0).
See https://creativecommons.org/licenses/by-sa/4.0/ for details.
-->

# RAG Assistant 架构文档

> 独立 RAG 智能体 — LLM 驱动的组合式语义检索与多库路由。
> 作者：wUwproject | 许可证：Apache 2.0
> 更新：2026-09-04（对照代码 v2.4.1 全文复核）— 决策循环两阶段重写 + evidence 原文锚定 + 查询类型场景层（§1.4 可配置的前置分类）+ Ranker 后插件点位解析（§3.10）+ 会话管理补录

---

## 一、系统概览

RAG Assistant 是一个**本地知识库问答智能体**，基于 local-rag-builder 技能构建，核心理念是从传统单轮问答升级为 **LLM 驱动的组合式检索** + **用户画像自适应交互**：

```
用户输入
  → [LLM 决策层·两阶段]
       阶段 1 模式判定（单次调用）：chat（显式 <<ACTION type="chat">>）→ 直接回答
       阶段 2 动作校验循环（≤5 次，禁止逃逸动作模式，耗尽禁止自由回答）
       └─ 知识库查询 → entities/attrs/rel 三槽位分词 + evidence 原文锚定
           （槽位填写按查询类型场景规则：内置 4 类 + 用户自定义，见 §1.4）
           → [组合展开器] 三层切片（entity 单独 / entity×attr / rel 语义两两配对）
           → [多切片检索] 每片独立走完整 RAG 流程
              1. 路由（route_query → 嵌入模型 × KB签名/关键词）
              2. 检索（retrieve_documents → ChromaDB 相似度 + HNSW 自动修复）
              3. (可选) 重排序（reranker：model / rule / hybrid 三模式）
              4. (可选) NLI 三向分类（entailment / neutral / contradiction）
              5. 构建上下文（build_context，含 NLI 标签渲染 + SM3 去重）
           → [SM3 国密去重合并] 按内容哈希去重 + 源文档头部块回填
           → [插件注入·Ranker 后点位] input_return 插件注入上下文（检索管道含 rerank 完成后、综合回答前，见 §3.10）
           → [LLM 综合回答] 基于完整上下文 + 用户画像 + 3插槽 prompt 生成回答
           → [插件副作用] input_output 插件执行（如日志记录）
           → [引用门禁] 校验 LLM 回答中的 [n] 引用是否在资料段落范围内
```

### 1.1 核心设计原则

| 原则 | 说明 |
|------|------|
| **LLM 分词 > 规则分词** | 实体/属性由 LLM 基于语义标注，不依赖关键词规则 |
| **穷举 > 猜测** | 三层切片全查一遍（entity 单独 / entity×attr / rel 语义切片），不预判哪组最优。rel 时多实体两两配对，单实体 attrs 两两配对 |
| **有限枚举 > 无界穷举** | 三槽位骨架限定归类，查询类型场景约束取值——穷举收敛为三元分类下专属场景内的有限枚举（§1.4） |
| **原文锚定 > 自由发挥** | evidence 强制每个 entity/attr 提供原文出处，三源校验 + NLI 语义二次判断，拒绝 LLM 编造检索词 |
| **去重 > 冗余** | SM3 国密哈希按内容去重，避免重复上下文浪费 token |
| **自修正 > 静默丢弃** | 两阶段决策：模式判定单次调用 → 动作校验循环最多 5 次，解析错误/校验拒绝反馈重试，禁止逃逸动作模式，耗尽后禁止 LLM 自由回答 |
| **技能完整走 > 绕路** | 每片独立走 route_query → retrieve_documents → reranker → NLI → build_context 全流程，不改造技能内部逻辑 |
| **配置持久化 > 运行时内存** | 所有配置（LLM / 路由 / 重排序 / NLI / 切片 / prompt 插槽 / 查询类型）写入 `rag_config.json`，刷新页面不丢 |
| **历史隔离 > 上下文污染** | 第一轮 LLM 决策仅传压缩摘要 + 上一轮问答原文（供 evidence 三源引用），完整历史不进决策，摘要概念禁止用作当前 entities/attrs |
| **用户画像自适应 > 固定 prompt** | 基于 OCEAN 五维人格 + 语言风格分析的画像系统，自动调整 LLM 交互风格 |
| **旁路扩展 > 主体侵入** | 扩展点只增不改、失败透传；主体（路由/检索/精排）变更必须架构级，不接受补丁式侵入（§3.10） |

### 1.2 路由开关行为

三开关体系：

| 开关 | 控制 | 开 | 关 |
|------|------|----|----|
| `kb.enabled` | 多知识库主开关 | 允许入库/出库路由工作 | 全部路由失效，全进 default |
| `kb.auto_classify` | 入库路由 | 嵌入模型余弦相似度匹配文档 × 各 KB 关键词，路由到最佳 KB | 纯关键词匹配，无匹配进 default |
| `router.enabled` | 出库路由 | 嵌入模型 × KB 签名关键词做余弦相似度（精排开时），或嵌入模型 × 规则关键词（精排关时）。精排关时不写 KB 签名 | 纯关键词匹配，不写 KB 签名 |

路由方法枚举：

| 路由方法 | 触发条件 |
|---------|---------|
| `hardcoded` | 命中硬编码关键词规则 |
| `embedding_signature` | 精排开：嵌入模型 × KB 签名关键词做余弦相似度。v1.7.0b1 支持多向量路由：有分象限签名列表时各做一次 cosine 取最高分，优于单字符串路由 |
| `embedding_keyword` | 精排关：嵌入模型 × 规则关键词（top-30）做余弦相似度 |
| `default` | 无匹配，路由到 default |
| `direct` | 用户直接指定了知识库 |
| `broadcast` | 语义回退失败后全量广播所有 KB 检索 |

**top-N 多 KB 路由（v2.3.0）**：`route_query()` 从 top-1（只取最高分 KB）改为 top-N——收集所有过阈值 KB，按分数降序取前 N 个，激活 `retrieve_context` 预留的多 KB 并查循环。跨域问题（如"量子物理与音乐的关系"）不再漏召回次相关 KB。三层防护：UI 限 1-10 → 代码夹 `[1,10]` → 运行时限实际过阈值 KB 数。配置项 `router.top_n`（默认 1 保持兼容）与 `router.classify_threshold`（主路由 KB 分数下限，默认 0.3）；外部 API `POST /api/kb/query` 支持 `top_n` 参数单次临时指定。

### 1.3 KB 签名生成流程（v1.7.0b1）

```
入库 → 文档 chunks
  → 四分法采样（N<200 全量 / 200≤N<500 全域随机 / N≥500 四分+每份随机）
  → 4 象限各自独立计算 BCE 语义质心
  → 每象限取距质心最近的 20 个 chunk
  → 各象限独立 jieba 候选词提取 + 停用词过滤（含 PDF 分页残留词）
  → 各象限独立 BCE 比对原始关键词排序
  → 四段拼接：Q1[:20] + Q2[:20] + Q3[:20] + Q4[:20] → 上限 80 词
  → 签名同时保存为合并字符串 + 4 个分象限子字符串（多向量路由用）
  → 反哺：(30 - count(originals)) // 4 每象限配额
```

v1.7.0b1 核心改进：
- 四分法从"采样 4 份合 1 质心"改为"4 份各自算质心、各取 20 近邻"
- 签名上限从 12 词扩至 80 词（不强求，取实际值）
- 签名同时保存多段子签名（`signatures` 列表），路由时逐个 cosine 取最高分
- 反哺从全局排序改为四象限均分：`(30 - originals) // 4`
- 停用词扩展 8 个 PDF 分页残留词：接上、转下页、上一页、下一页、上页、下页、翻页、第几页

### 1.4 可配置的前置分类 — 三元分类下的专属场景有限枚举

前置分类解决一个问题：任意自然语言问题的检索空间是**无定义穷举**，必须收敛为有限枚举，切片数与检索成本才可预估。收敛分两级，两级正交：

```
无定义穷举（任意自然语言问题）
  ↓ 第一级【归类】：三槽位骨架（系统锁定，不可配）
     所有查询动作固定为 entities（主体）/ attrs（目的）/ rel（行为）
     三槽位 + type / kb / evidence 参数，LLM 只按语义规则填槽（§5.3）
  = 归类内穷举 —— 穷举有了维度，但每个槽位内仍可无界取值
  ↓ 第二级【场景】：查询类型（预制 + 用户自定义，可配）
     每个场景 = 三槽位取值约束模板（label + example + rules），
     规定该类问题 entities 填什么、attrs 填几个/什么域、rel 是否固定
  = 用户场景内穷举 —— 场景内槽位取值模式有限
  ↓ 组合展开器（三层切片）
  = 有限枚举 —— 切片数场景内可预估、可预算
```

**第一级：归类。** 三槽位骨架就是限定了分类——无论问题多自由，LLM 输出都被固定到 entities/attrs/rel 三维。骨架由系统锁定（动作格式 + 校验器 + 展开器三方联动），变更属协议级/架构级改动。

**第二级：场景。** 三元分类下每一类槽位仍可无界取值，因此需要场景约束值域。场景不是启发式技巧，而是**用户问题的类型归属**：问题本身是二元对立的，就命中 opposition 场景，按其规则填槽。归类与场景的关系：**几个固定参数（三槽位）就是归类，用户配置（场景增删与取值规则）就是场景**——用户最清楚自己领域内的问题形态，场景内穷举因此收敛为有限枚举。

内置场景（`BUILTIN_QUERY_TYPES`，agent.py）：

| key | label | example | entities 规则 | attrs 规则 | rel 规则 |
|-----|-------|---------|--------------|-----------|----------|
| `fact` | 事实查询 | "茅台的价格是多少？" | 主体/名词，能被替换为"关于XX"的 XX | 目的/属性维度，禁比较意图词与疑问词 | 留空（不触发两两配对） |
| `compare` | 实体对比 | "茅台和五粮液酿造工艺异同" | 被对比的多个实体，逗号分隔 | 对比维度，"比它们的什么方面" | `"对比"` |
| `opposition` | 二元对立 | "AI是顺着倾向回答还是独立思考" | 只填主体，不把对立面放进来 | 两个对立面的表述，逗号分隔 | `"对比"` |
| `analysis` | 多维度分析 | "新能源汽车的市场规模、政策环境和消费者态度" | 分析主体，只填 1 个 | 分析维度并列列举 | 留空（两主体对比应改用 compare） |

自定义机制（`query_types`，rag_config.json）：

| 环节 | 说明 |
|------|------|
| 存储 | `rag_config.json` 的 `query_types` 字典；**同 key 覆盖内置，新增 key 即新增场景** |
| Web 管理 | 配置页查询类型区 CRUD（`/api/config/query_types`），内置类型不可删除，自定义类型可增删改 |
| 场景结构 | `{key: {label, example, rules: {entities, attrs, rel}, built_in}}`，rules 三键对应三槽位填写规则 |
| 注入链路 | `_get_all_query_types()` 合并内置+自定义 → `_build_type_reference()` 渲染进第一轮决策 system prompt 的「查询类型参考」节——**LLM 不需要声明类型，只需参照最匹配场景的规则填槽** |

设计边界：

- 场景只约束"怎么填槽"，**不改变执行管线**——组合展开器对全部场景一视同仁地做三层切片
- 场景增删 = 配置级变更，随时可做；三槽位骨架变更 = 架构级变更，需动作格式/校验器/展开器联动
- 场景化收益以 opposition 为例：无场景约束时 LLM 倾向把对立面塞进 entities 导致展开爆炸；场景规则将其收敛为"主体 1 + 对立面 2（attrs）+ rel 固定"，切片数确定
- 实时类需求当前走 `type="search"` 独立动作通道；如需"实时查询"场景化（场景内混合 rag/search 通道），属用户自定义场景的演进方向

---

## 二、三层架构

| 层 | 组件 | 职责 |
|---|------|------|
| **表现层** | `web_ui.py` (port 8765) / RAG 配置页 subprocess (port 8766) / CLI (stdin) | Web 界面、LLM 配置面板、聊天界面、模型管理、知识库配置、CLI 交互 |
| **业务层** | `agent.py` / `rag_wrapper.py` / `engine/rag_core.py` / `engine/router.py` / `engine/reranker.py` | 决策循环、组合查询、路由/检索/重排序/NLI、记忆管理、用户画像 |
| **基础设施** | `llm_client.py` / `engine/config.py` / `engine/utils.py` / `data/` / `vendor/` | LLM 通信、配置管理、数据持久化、内嵌第三方依赖 |

### 2.1 完整文件结构

```
rag-assistant/
├── main.py                          # ★ 入口（4 种模式：web / cli / batch / jsonl）
├── setup.bat                        # Windows 一键启动 + 进程管理
├── requirements.txt                 # 依赖清单
├── CHANGELOG.md                     # 版本更新日志
├── PROTOCOL.md                      # 外部接入协议规范（HTTP/CLI/文件交互）
├── llms.txt                         # AI 可读的项目自描述文档（llmstxt.org）
├── blueprint_rag.json               # PyPI 发布蓝图
├── README.md                        # 项目说明
├── LICENSE                          # Apache 2.0
├── server.pid                       # 运行时 PID（setup.bat 管理进程）
├── _test_router_score.py            # 路由评分测试脚本
├── .gitignore
│
├── rag_assistant/                   # ★ 智能体核心层
│   ├── __init__.py                  # 版本号: 0.9.5
│   ├── agent.py                     # Agent 决策循环（~620 行）
│   ├── web_ui.py                    # Web 界面（port 8765，~1300 行）
│   ├── llm_client.py                # LLM 统一客户端
│   ├── rag_wrapper.py               # RAG 封装桥接层
│   ├── search.py                    # 联网搜索
│   ├── memory.py                    # 四层记忆 + 用户画像系统
│   ├── _fix_rag.py                  # 破损数据修复工具
│   │
│   └── engine/                      # ★ local-rag-builder 技能核心（独立副本）
│       ├── __init__.py
│       ├── rag_core.py              # RAG 核心：检索/嵌入/导入
│       ├── router.py                # 两级路由：关键词 + 嵌入 × KB 签名
│       ├── reranker.py              # 三模式重排序 + FallbackRouter
│       ├── nli_classifier.py        # NLI 三向分类器
│       ├── knowledge_base_manager.py# 知识库 CRUD + 自动分类 + SM3 去重 + ChromaDB 容灾
│       ├── config.py                # 配置加载/保存/自动修正模型路径
│       ├── embedding_model_manager.py# 5 源并行模型下载管理
│       ├── prompt_manager.py        # 3 插槽 + 预设管理 + 用户画像扩展点
│       ├── text_splitter.py         # 5 策略 + 5 守卫插件架构
│       ├── rag_skill.py             # 技能接口
│       ├── rag_standalone.py        # 独立模式
│       ├── rag_web_ui.py            # RAG 配置页（完整前端）
│       ├── rag_setup_orchestrator.py# 安装编排
│       ├── rag_env_setup.py         # 环境检测
│       └── utils.py                 # 工具函数 + 数据目录管理
│
├── vendor/                          # ★ 内嵌第三方库（零 pip 也可在受限环境中运行）
│   ├── bs4/                         # BeautifulSoup4
│   ├── pypdfium2/                   # PDF 解析（Google PDFium 引擎，v2.4.0 替换 pypdf）
│   ├── pypdfium2_raw/               # PDFium 预编译二进制（含 pdfium.dll）
│   ├── pypdfium2_cfg/               # pypdfium2 配置
│   ├── markdownify/                 # HTML → Markdown
│   └── soupsieve/                   # CSS 选择器（bs4 依赖）
│
└── data/                            # 运行时数据
    ├── config/rag_config.json       # 引擎全量配置（含 llm 子字典、prompt_slots 等）
    ├── kb/
    │   ├── kb_index.json            # 知识库索引
    │   ├── kb_signatures.json       # KB 签名关键词
    │   ├── auto_classify_rules.json # 自动分类规则
    │   └── {name}/                  # 各知识库（13 个，ChromaDB SQLite + HNSW）
    ├── models/
    │   └── model_index.json         # 模型索引
    ├── config/rag_config.json       # LLM 与检索配置
    ├── memory/
    │   ├── compressed_{id}.txt      # LLM 压缩摘要
    │   ├── kb_gaps.json             # 知识缺口（最多 200 条）
    │   └── user_habits.json         # 用户习惯 + OCEAN 人格画像
    ├── sessions/{id}.txt            # 短期对话
    ├── prompts/
    │   ├── custom_presets.json      # 用户自定义 prompt 预设
    │   └── custom_prompt_template.txt
    ├── import_manifest.json         # 待入库文件清单
    ├── imports/                     # 浏览器上传临时目录（入库后自动清理）
    └── cache/                       # 模型下载临时缓存
```

---

## 三、组件详解

### 3.1 决策循环 — `agent.py`

核心是 `chat()` → `_decide_with_retry()` 的**两阶段决策 + 动作校验循环**。

**两阶段设计**：

```
阶段 1（模式判定）：单次 LLM 调用，不进循环
  ├─ 显式 <<ACTION type="chat">>（或旧版无动作标记）→ chat 模式，直接返回
  └─ 解析出 query/search/import 或格式错误 → 进入阶段 2
阶段 2（动作校验循环 _action_validation_loop）：max_retries=5
  ├─ LLM 一旦进入动作模式，必须在重试中保持动作模式
  │   ——不允许通过"不输出 <<ACTION>>"逃逸校验，逃逸按修正提醒强制回正
  ├─ 解析错误 / 校验拒绝 → 以【修正提醒】反馈给 LLM 重试
  └─ 5 次耗尽 → 禁止 LLM 自由回答（防止捏造引用），返回固定提示"请重新表述你的问题"
```

**第一轮决策消息构建**（`_build_first_pass_messages`，不传完整历史对话）：

1. system prompt（动作格式 + 查询类型参考场景规则，见 §1.4）
2. 上一轮问题/回答原文（`_get_previous_turns()`，供追问时 entities/attrs/evidence 三源引用）
3. 压缩摘要（标注"其中的概念/关键词不得用于当前问题的 entities/attrs"，防历史泄漏）
4. 用户画像提示（prompt_manager.build_persona_context()）
5. 当前消息

#### _parse_action — 状态机解析器

从 LLM 输出中提取 `<<ACTION type="..." ...>>` 指令，使用**状态机逐字符扫描**（而非正则表达式）：

1. **Windows 路径兼容**：`C:\Users\...` 中的反斜杠不被当作转义前缀，`\U` 不被解释为 Unicode 序列
2. **文件名含引号**：仅 `\"` 和 `\\` 视为转义，其他 `\X` 保持字面量
3. **格式错误捕获**：`<action>`、`<<action>>` 等非标准写法返回错误原因进入修正循环，不静默丢弃

返回格式：
- `(None, None)` — 无动作标记（chat 模式）
- `(None, "原因")` — 有 `<<ACTION` 但格式错误
- `({...}, None)` — 解析成功

#### _validate_action — 动作校验

type 必须是 `query / search / import / chat`；chat 无需额外校验，其余逐类校验：

| 类型 | 校验项 |
|------|--------|
| `query` | entities/attrs 必填且各为**单概念**（禁 `/`、`\|`、`、`、`·` 拼接分隔符）；**evidence 必填**（见下）；kb 若填必须为用户原话提及的名称 |
| `import` | **关键词门禁**：用户没说导入/入库等，直接拒绝 import 指令；path 非 MANIFEST 时必须存在（支持逗号分隔多路径）；kb 必须用户原话提及**且真实存在**（查 list_kbs） |
| `search` | query 必填 |

**evidence 原文锚定校验**：

- 格式：JSON 字典，key 与 entities/attrs 中的写法**精确一致**（LLM 多塞的额外 key 自动忽略），value 必须是**原文单个连续子串**（禁拼接分隔符，尾部省略号自动清洗）
- 三源校验：value 须在**当前消息 / 上一轮问题 / 上一轮回答**之一中存在
- 语义二次判断：硬编码校验不通过且 `nli.output_enabled` 开启时，走 NLI `verify(key, value)`（key/value 互含子串自动通过，否则模型判断），降低错误拒绝率
- 拒绝信息附带 key 所在源的**字符级切片定位参考**（前后 30/80 字符），引导 LLM 对照原文修正

#### 组合查询 — 三层切片展开

当 LLM 输出 `type="query"` 时触发。展开器做三层切片（示例为 opposition 场景填槽）：

```python
# LLM 输出示例
<<ACTION type="query" entities="AI" attrs="迎合,独立思考" rel="对比"
          evidence='{"AI":"AI","迎合":"顺着倾向回答","独立思考":"独立思考"}'>>

# 三层切片：
slices = [
    "AI",                          # 第一层：entity 单独（实体宽泛检索）
    "AI 迎合",                      # 第二层：entity × attr（事实块检索）
    "AI 独立思考",
    "AI 迎合 独立思考 对比",          # 第三层：rel 语义切片（单实体 → attrs 两两配对 + rel）
]
# rel 语义层的两种形态：
#   多实体（≥2）：itertools.combinations 两两配对 → "e1 e2 rel" / "e1 e2 attr rel"
#   单实体：attrs 两两配对 → "e a1 a2 rel"
# 过滤：比较意图词（异同/区别/对比…）与疑问词（为什么/怎么/如何…）从 attrs 剔除，不自动设 rel
```

切片展开后各片独立走 `rag.query(slice, include_header=True)` 完整流程，结果按 SM3 内容哈希去重合并；同时回取各命中文档的**源文档头部块**（`headers`），以【文档: 源文件】形式拼在语义检索结果之前，补足头部上下文。

**get_embeddings() 缓存优化**（v0.8.5）：组合查询共享同一个嵌入模型实例，避免每片重复加载（18 次 → 1 次）。

### 3.2 LLM 客户端 — `llm_client.py`

支持双后端，统一返回 `{text, reasoning, raw}`。支持流式响应：

| 后端 | 协议 | 接口 | 模型参数 | 默认端口 |
|------|------|------|---------|---------|
| LM Studio | HTTP (OpenAI 兼容) | `/v1/chat/completions` | `max_tokens` / `temperature` | 1234 |
| Ollama | HTTP (Ollama API) | `/api/chat` | `num_predict` / `temperature` | 11434 |

**模型发现**：调用 `/v1/models`（LM Studio）或 `/api/tags`（Ollama）列出可用模型。

**健康检查**：`check_health()` 通过简化 API 调用测试后端连通性。

### 3.3 Web 界面 — `web_ui.py`

基于 Python `http.server` 的单文件 Web 界面（~1300 行），无外部框架依赖。端口自动分配（`_find_ports()` 查找 2 个可用端口）。

**前端**：内嵌单页 HTML + JS，使用 marked CDN（cdn.jsdelivr.net/npm/marked/marked.min.js）渲染 Markdown。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` 或 `/index.html` | GET | 主页面（配置 Tab + 对话 Tab） |
| `/api/config` | GET | 获取完整配置 |
| `/api/kbs` | GET | 知识库列表 |
| `/api/llm/models?backend=xxx` | GET | 扫描模型列表 |
| `/api/llm/test` | GET | 测试 LLM 连接 |
| `/api/config/llm` | GET/POST | 获取/更新 LLM 配置（backend/model/timeout/maxtokens） |
| `/api/config/search` | GET/POST | 联网搜索配置 |
| `/api/config/memory` | GET/POST | 记忆参数配置 |
| `/api/config/query_types` | GET/POST | 查询类型场景 CRUD（内置类型不可删除，自定义同 key 覆盖，见 §1.4） |
| `/api/chat` | GET/POST | Agent 决策循环聊天 |
| `/api/chat/history` | GET | 聊天历史持久化（v0.8.4） |
| `/api/agent/query` | GET/POST | 直接 RAG 查询（绕过 Agent 决策） |
| `/api/agent/import` | POST | 导入文档（3 种模式：path/text/content） |
| `/api/agent/upload-files` | POST | 浏览器上传文件到服务器临时目录 |
| `/api/agent/gaps` | GET | 知识缺口列表 |
| `/api/memory/reset` | GET | 重置对话 |
| `/api/memory/compress` | GET/POST | 压缩上下文 |
| `/api/memory/clear-context` | GET/POST | 清除上下文 |
| `/api/memory/inject` | POST | 注入系统通知 |
| `/api/session/new` `/api/session/list` | GET/POST | 会话新建 / 列表（含归档会话与首条消息预览） |
| `/api/session/switch` `/api/session/archive` | GET/POST | 会话切换 / 归档（压缩摘要同步归档） |
| `/api/session/restore` `/api/session/delete` | GET/POST | 会话恢复 / 永久删除 |
| `/api/search/toggle` | POST | 联网搜索开关 |
| `/api/availability-status` | GET | 模型下载探测状态（v0.9.0） |
| `/api/plugins` | GET | 插件列表（v2.1.0） |
| `/api/plugins/toggle` | POST | 启用/禁用插件（v2.1.0） |
| `/api/plugins/config` | POST | 打开插件配置界面（v2.1.0） |
| `/api/plugins/refresh` | POST | 重新扫描插件目录（v2.1.0） |
| `/api/plugins/generate` | POST | AI 插件生成器（v2.1.0） |

**关键交互细节**：
- `loadModels()` 在页面加载后 500ms 触发，填充模型下拉框
- 配置保存后立即同步到 `self.agent.llm.*` 运行时实例
- `llm_max_tokens` 和 `llm_timeout` 持久化到 `rag_config.json`
- 路由/reranker/NLI toggle 无已下载模型时灰化 + 红色提示文字
- 网络探测结果实时增量更新 🟢/🔴

**文件上传流程**：点击文件选择按钮 → 文件以 base64 二进制上传到服务器 `data/imports/` 目录并记录到 `import_manifest.json`，同时聊天框出现系统通知。用户输入"入库"后 LLM 发出 `path="MANIFEST"` 指令，系统读取清单逐个走完整导入管线。

**PDF 导入**（v2.4.0 引擎迁移 pypdf → pypdfium2，三层 OCR 判断）：
- 多页 PDF 合并全部页内容后切分（`"\n\n".join(d.page_content for d in docs)`）
- PDF 引擎：pypdfium2（Google PDFium），从根源消除 pypdf 的 ToUnicode CMap 形似字缺陷（`Iethods`→`Methods` 类）
- 三层 OCR 判断（v2.4.0 重构，替代旧版两层判断）：
  1. **二进制类型判断**：读 PDF 二进制检测 `/Font` 与 `/Image`——无 `/Font` 直接 OCR（无文本层）；有 `/Image` 且无文本页占比 > 50% 直接 OCR（混合版扫描件）
  2. **信号 2 乱码检测**（逐页）：英文词间距丢失（`alpha > 0.5 且 max_run > 30`）
  3. **信号 4 乱码检测**（逐页）：中文常用字覆盖率 < 50%（`_COMMON_CJK` ~200 高频字表）
  - 乱码页占比 > 10% → 整篇 OCR；乱码 chunk 不剔除，让检索自然降权
- 英文正常 PDF 不走 OCR

### 3.4 RAG 封装层 — `rag_wrapper.py`

将 local-rag-builder 的技能接口包装为 Agent 可调用的形式：

```python
rag.query(question, kb_name=None, include_header=False, ...)
  → retrieve_context(question, kb_name, ...)
    → route_query(question)                 # 路由：两级（关键词 + 嵌入 × KB签名）
      → retrieve_documents(question, kb)    # 检索：取 top-K chunk（HNSW 自动修复）
        → reranker.rerank(docs)             # 可选：精排（model/rule/hybrid）
      → nli_classifier.classify(docs)       # 可选：NLI 三向标注
      → build_context(docs)                 # 构建上下文（含 NLI 标签）
  → return {context, docs, kb, headers, has_context}
```

### 3.5 搜索模块 — `search.py`

| 引擎 | 方式 | API Key |
|------|------|---------|
| DuckDuckGo | `requests.get(html.duckduckgo.com/html/)` | 无需 Key |
| Tavily | `POST api.tavily.com/search` | 需配置 Key |
| urllib fallback | 纯 HTML 解析回退 | 无需 Key |

通过 `web_search_enabled` + `web_search_api_key` + `web_search_engine` 配置。

### 3.6 引用门禁 — `agent.py`

v0.8.0 新增：LLM 回答后校验引用编号。`_second_pass()` 中的引用校验逻辑：
- 系统提示强制要求每个具体事实/数字后面标注来源段落编号 `[n]`
- LLM 回答后提取所有 `[n]` 引用，检查编号是否在资料段落范围内
- 不存在的段落编号 → 告警追加到回答尾部
- 无引用 → 记录日志（不作为错误）
- 插件注入内容走**来源标记引用**：上下文含【联网搜索】等插件标记时，追加引用规则——引用插件信息标注 `[插件名称]`，引用知识库信息继续用 `[n]` 段落编号

### 3.7 KB 暂停写入

v0.8.0 新增：配置页自动分类规则表格每行增加暂停/恢复按钮。

| 场景 | 行为 |
|------|------|
| 自动路由入库 | `auto_classify()` 从 rules 中过滤掉 `kb_paused` 列表中的 KB，文件自动路由到次高分的非暂停 KB |
| 用户指定入库 | `add_documents_to_kb()` 拒绝写入，提示"已暂停，请恢复或选其他 KB" |
| 查询/检索 | 完全不受影响 |
| 恢复暂停 | 再次点击按钮，KB 恢复为可写入 |

### 3.8 重排序 — `engine/reranker.py`

三模式重排序 + FallbackRouter（v0.7.0 从 router.py 迁入）：

| 组件 | 职责 |
|------|------|
| `ModelReranker` | transformer cross-encoder 打分排序 |
| `RuleReranker` | 规则引擎（score_weight / recency / source_weight / boost_keywords） |
| `HybridReranker` | 模型打分 + 规则微调 |
| `FallbackRouter` | 语义回退路由（cross-encoder 对 query × KB 签名打分）+ KB 签名生成阶段的文档片段打分 |

重排序不再参与路由决策（v0.5.0 解耦）。路由改用嵌入模型余弦相似度。

### 3.9 NLI 三向分类器 — `engine/nli_classifier.py`

v0.9.0 新增，cross-encoder 3-class 模型（contradiction / neutral / entailment）。

| 模型 | 语言 |
|------|------|
| `cross-encoder/nli-deberta-v3-base` | 英文（SOTA） |
| `MoritzLaurer/mDeBERTa-v3-base-xnli` | 多语言 XNLI |
| `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` | 多语言（双源训练） |
| `BAAI/bge-reranker-v2-minicpm-layerwise` | 多任务 |
| `cross-encoder/nli-MiniLM2-L6-H768` | 英文（轻量） |
| `cross-encoder/nli-roberta-base` | 英文 |

标签输出格式：`[NLI: entailment, 92%]`
在 reranker 之后（reranker 开时）或向量召回之后（reranker 关时）运行。

除管道内三向分类外，NLI 分类器还通过 `verify(key, value)` 方法承担 **evidence 语义二次判断**（agent 动作校验共享 `get_nli_classifier()` 单例，见 §3.1）：硬编码原文校验不通过时判断 key 与 value 的语义一致性，降低错误拒绝率。

---

### 3.10 Ranker 后插件点位 — before_response 旁路扩展（已实现）

定位：`input_return` 类型插件的执行时机，位于**完整检索管道（含 reranker）之后、LLM 综合回答之前**。相对 ranker 而言，这是一个"检索已定、精排已定"之后的旁路注入点——锦上添花，不影响主体功能完整性。

**管道位置（agent.py `chat()`，实测代码锚点 L320-344）**：

```
用户查询 → [组合展开器] 多切片
  → 每片独立: route → retrieve → rerank → NLI → build_context   （主体引擎管道）
  → [SM3 去重合并] 多片结果按内容哈希去重
  → [插件点位·input_return]  ← Ranker 后点位（run_before_response）
  │     插件读取 question / rag_context / thinking 等裁剪输入
  │     产出补充内容（如联网搜索结果）
  → [合并] 注入内容以分隔线 + "## 插件补充信息" 附加到 context（不改写主体管道产出）
  → [LLM 综合回答] _second_pass（3 插槽 prompt，含插件来源引用规则）
  → [插件点位·input_output] 回答后副作用（run_after_response）
```

**与 ranker 的相对位置**：主体引擎管道内部（route → retrieve → rerank → NLI → build_context）**没有任何插件点位，也不应该有**——管道内每一步都是主体功能，扩展点开在管道内部等于允许外部代码介入主体执行路径。插件点位开在整条管道**完成后**：插件只能消费管道的最终产出（rag_context），不能触达路由/检索/精排的任何中间环节。

**稳定性契约（代码事实）**：

| 契约 | 代码证据 |
|------|---------|
| 失败透传 | `run_before_response` 整体 try/except，异常仅 warning 日志，主流程照走（agent.py L325-336）；单插件失败由 `PluginManager._safe_execute` 隔离，不影响其他插件 |
| 只消费不改源 | 插件输入按 `input_fields` 从 6 字段池裁剪；注入内容**附加**到 context 尾部（`existing + "\n\n---\n\n## 插件补充信息\n\n" + injected`），不修改、不覆盖主体管道产出（agent.py L338-344） |
| 五道防线 | 信息隔离 / 文件沙箱 / 超时熔断（per-plugin timeout）/ 输出校验 / SM3 签名校验（`_verify_signature`），与 §6.6 同一套 |
| type 硬约束 | 插件 type 枚举硬校验，仅允许 `input_return` / `input_output`（manager.py L152-153），非注册点位的执行路径不存在 |
| 主体变更 = 架构级 | 插件点位只增不改；主体（路由/检索/精排）要改必须是架构级变更，不允许补丁式侵入 |

**设计理据 — 为什么点位在 ranker 之后**：

- 检索与精排完成后，任何增强（外部检索补召回、行情查询、结果补充）都是锦上添花：不影响前面任何环节的正确性，也不因自身失败拖垮主体
- 在一个运行系统中，部分需求扩张导致的例如召回率等参数不理想时，正确动作是**旁路补足**（web_search 联网搜索插件就是这一原则的活实例：知识库覆盖不到的实时内容，由插件在管道完成后注入），而不是为指标回头改主体——哪怕保持低召回的稳定性，也不能引发系统崩坏级的不稳定
- 系统越大越难发现"蚁穴"和"蝴蝶翅膀"在哪里——这不是简单的试错问题，不是积累经验的问题，这是人类和 AI 共同存在的**注意力机制**的局限。用点位隔离代替试错，是稳定运行的重要前提

---

## 四、记忆系统 — `memory.py`

四层记忆 + 用户画像系统，统一管理短期对话、压缩摘要、知识缺口和用户习惯性格画像。

### 4.1 短期记忆

| 方法 | 功能 | 存储 |
|------|------|------|
| `append_short_term(session_id, role, content)` | 追加一条对话记录（超 2000 字符截断） | `data/sessions/{session_id}.txt` |
| `get_short_term(session_id)` | 读取完整对话历史 | 返回 `str` |
| `clear_short_term(session_id)` | 清空对话历史 | 删除文件 |
| `pop_oldest_lines(session_id, n)` | 弹出最旧的 N 行（默认 40） | 返回被移除的文本 |
| `short_term_line_count(session_id)` | 当前行数 | 返回 `int` |
| `needs_compression(session_id)` | 行数 > 100 触发压缩开关 | 返回 `bool` |

### 4.2 长时记忆（压缩摘要）

| 方法 | 功能 | 存储 |
|------|------|------|
| `store_compressed(session_id, summary)` | 追加一条压缩摘要 | `data/memory/compressed_{session_id}.txt` |
| `get_compressed(session_id, limit=3)` | 返回最近 N 条摘要 | 返回 `str`（多摘要拼接） |

**压缩触发**（`_compress_if_needed()`）：当 `short_term_line_count() > 100`（约 50 轮对话）时触发：
1. `pop_oldest_lines()` 取出最旧 40 行对话
2. 调 LLM 压缩为摘要（结构化指令要求保留核心需求、已得结论、追问方向、最近 3 条原文，200 字以内）
3. `store_compressed()` 存入长时记忆

### 4.3 知识缺口记录

记录检索不到答案的查询，分析知识库覆盖盲区。保留最近 200 条，相同 query 自动累加计数。

```json
{
  "query": "三个代表与老子无为而治的相同点",
  "kb": "政经文哲",
  "count": 3,
  "first_seen": "2026-07-08T04:20:13",
  "last_seen": "2026-07-08T04:25:27"
}
```

### 4.4 用户习惯与性格画像（v0.6.0）

**三层分析体系**：

| 层级 | 方法 | 输出 |
|------|------|------|
| **规则级语言分析** | `_classify_sentence(msg)` | 句式（statement/question/imperative/rhetorical）+ 语气（neutral/critical/curious/sarcastic/terse/enthusiastic）+ 深度（shallow/medium/deep） |
| **OCEAN 五维人格** | `_ocean_delta()` → 衰减更新（`PERSONALITY_DECAY=0.98`） | openness / conscientiousness / extraversion / agreeableness / neuroticism（0-1，默认 0.5） |
| **合成画像** | `get_persona()` → `build_persona_context()` | 语言风格统计占比 + 人格标签 + 行为偏好文本 |

**人格更新机制**：

```python
# 衰减 + 新样本加权
new_val = old * decay + delta * (1 - decay)  # decay=0.98
personality[dim] = clamp(new_val, 0.0, 1.0)
```

**人格标签映射**（`get_persona()` 中的 `_dim_label`）：

| 维度 | < 0.55 | ≥ 0.55 |
|------|--------|--------|
| openness | 守成型 | 探索型 |
| conscientiousness | 随性型 | 严谨型 |
| extraversion | 内敛型 | 外放型 |
| agreeableness | 对抗型 | 亲和型 |
| neuroticism | 稳定型（< 0.45） | 敏感型（≥ 0.45） |

### 4.5 与 Agent 的集成

```python
chat(message)
  ↓
append_short_term(session_id, "user", message)   # 写入用户输入
  ↓
_get_previous_turns()                     # 取上一轮问题/回答（evidence 三源引用）
  ↓
_decide_with_retry(message, max_retries=5)  # 两阶段：模式判定 → 动作校验循环
  ├─ 第一轮消息：system prompt（动作格式 + 查询类型参考场景）
  │   + 上一轮问答原文 + 压缩摘要（概念禁止用作 entities/attrs）+ 画像
  └─ LLM 决策（query/search/import/chat）
  ↓
执行动作 → _second_pass(message, context, action)  # 第二轮：带上下文 + 历史（跳过 reasoning）
  ↓
append_short_term(session_id, "assistant"/"reasoning", ...)
                                          # 写入助手回复/推理（自动剥离 <<ACTION>> 标签）
record_habit(message, is_rag, ..., kb)   # 记录习惯 + 语言分析 + OCEAN 更新
↓ 如果检索结果为空
record_gap(query, kb)                    # 记录知识缺口
```

**历史隔离**（v0.8.0）：第一轮决策不传完整历史对话，仅传压缩摘要作为 system context。第二轮 `_second_pass()` 仍携带带 `[历史对话]` 前缀的历史消息，保证跨轮追问的上下文连贯性。

**ACTION 剥离**（v0.8.0）：写入记忆时自动使用 `re.sub(r'<{1,2}\s*ACTION\s+.*?>{1,2}', '', content, flags=re.DOTALL|re.IGNORECASE)` 剥离内部指令标签。

**记忆角色**：user / assistant / reasoning 三种角色写入短期记忆；reasoning 单独记录，第二轮历史消息构建时跳过（防止连续 role 破坏消息序列）。

### 4.6 会话管理

| 方法 | 功能 |
|------|------|
| `new_session()` | 新建会话；活跃会话数超 `memory.max_sessions`（默认 20）自动归档最旧的非活跃会话 |
| `list_sessions()` | 列出活跃 + 已归档会话（含首条用户消息预览 60 字符），按创建时间倒序 |
| `archive_session()` | 会话移入 `archives/sessions/`，压缩摘要同步移入 `archives/memory/` |
| `delete_session()` | 永久删除会话文件（含归档目录与压缩记忆） |

对应 Web 端点：`/api/session/new|list|switch|archive|restore|delete`。

---

## 五、外部接口

### 5.1 Python 编程接口（API）

| 类 | 入口方法 | 返回格式 |
|----|---------|---------|
| `Agent` | `.chat(message) → dict` | `{"text", "success", "reasoning", "kb", ...}` |
| | `.reset_session()` | 无返回值 |
| `Memory` | `.get_short_term(id) → str` | 对话历史文本 |
| | `.append_short_term(id, role, content)` | 无返回值 |
| | `.get_gaps(min_count) → list[dict]` | `[{"query", "kb", "count", ...}]` |
| | `.get_habits() → dict` | `{"total_queries", "chat_ratio", "personality", ...}` |
| | `.get_persona() → dict` | `{"linguistic_summary", "personality", "behavior"}` |
| `LLMClient` | `.chat(messages) → dict` | `{"text", "reasoning", "raw"}` |
| | `.list_models() → list[str]` | 模型名列表 |
| | `.check_health() → bool` | 连接状态 |
| `RAGWrapper` | `.query(question, kb_name) → dict` | `{"context", "docs", "kb", "has_context"}` |
| | `.import_file(path, kb_name) → dict` | `{"success", "doc_count", "kb"}` |
| | `.import_text(text, kb_name, title) → dict` | `{"success", "doc_count", "kb"}` |
| | `.list_kbs() → dict` | 知识库字典 |
| `WebSearch` | `.search(query, max_results) → dict` | `{"results": [{"title", "url", "snippet"}], "success"}` |

### 5.2 技能依赖接口

| 技能模块 | 导入函数 | 用途 |
|---------|---------|------|
| `rag_core` | `retrieve_context` | 检索主入口（路由→检索→reranker→NLI→build） |
| `rag_core` | `get_embeddings` | 嵌入模型管理（单例缓存） |
| `rag_core` | `build_context` | 上下文构建（含 NLI 标签渲染） |
| `knowledge_base_manager` | `list_knowledge_bases` | 知识库枚举 |
| `knowledge_base_manager` | `_load_rules` / `auto_classify` | 入库路由 |
| `knowledge_base_manager` | `sm3` | SM3 国密哈希去重 |
| `config` | `load_config / save_config` | 配置持久化 + 模型路径自动修正 |
| `prompt_manager` | `build_second_pass_prompt` | 3 插槽 prompt 构建 |
| `prompt_manager` | `build_persona_prompt` | 用户画像注入 |
| `nli_classifier` | `NLIClassifier.classify` / `NLIClassifier.verify` | NLI 三向分类 / evidence 语义二次判断（§3.1） |

### 5.3 Agent 动作协议（LLM ↔ Agent 通信）

LLM 在回复中嵌入 `<<ACTION ...>>` 标记控制 Agent 行为：

```python
<<ACTION type="query" entities="实体1,实体2" attrs="属性A,属性B" rel="关系词"
          evidence='{"词":"原文出处"}' kb="知识库名（可选，必须用户原话提及）">>
<<ACTION type="search" query="搜索词">>
<<ACTION type="import" content="入库的完整文本内容">
<<ACTION type="import" path="MANIFEST">        # 批量导入所有待入库文件
<<ACTION type="chat">>                          # 闲聊/直接回答也必须显式声明
```

- **不使用 question 参数**（不会生效），成分一律标注进 entities/attrs
- 所有回复都必须显式声明动作类型（包括纯聊天），系统通过标记决定处理方式

**LLM 分词语义规则**（三槽位，v0.9.0 重写）：
- `entities`：取主体/名词。问题中涉及的核心事物、人物、概念，每个 entity 必须是单个概念（禁拼接分隔符）
- `attrs`：取目的/限定域。用户想查询的目标/用途/对象，可以是复合短语；排除比较意图词（异同、区别、对比等，归 rel）与疑问词（为什么/怎么/如何，非搜索维度）
- `rel`：取行为。实体间的动作/关系，填一个最贴切的词（如"对比"）
- `evidence`：**每个 entity 和 attr 都必须提供原文出处**。key 与 entities/attrs 写法精确一致，value 是原文单个连续子串，可来自当前消息/上一轮问题/上一轮回答三源；entity/attr 可对原文凝缩提炼，但提炼词须在原文有对应短语

**场景层（可配置的前置分类）**：槽位怎么填由查询类型场景约束——内置 4 类（fact/compare/opposition/analysis）+ 用户自定义（同 key 覆盖），LLM 不声明类型，参照最匹配场景的规则填槽。详见 §1.4。

### 5.4 Prompt 3 插槽架构 + 自定义预设 — `prompt_manager.py`

系统提示词框架锁定不可改，暴露 3 个插槽由用户配置：

| 插槽 | 默认值 | 作用 |
|------|--------|------|
| `cite_format` | "每个结论后面用 [n] 标注来源的段落编号" | 控制引用标注格式 |
| `output_style` | "用 Markdown 格式输出" | 控制输出风格 / 格式 |
| `fallback` | "如果资料中没有明确结论，可以结合资料进行分析推理，但不能编造不存在的内容" | 控制无资料时的处理策略 |

**预设管理**：4 个内置预设（标准模式 / 深度分析 / 对比分析 / 友好对话）+ 用户自定义预设 CRUD。RAG 配置页 UI 中以下拉 `<optgroup>` 分区显示，内置预设不可删除。

---

## 六、流程详解

### 6.1 完整请求生命周期

```
用户发送消息
  ↓
web_ui.py → POST /api/chat
  ↓
agent.chat(message)
  ↓
记忆写入 → _get_previous_turns()（上一轮问答，供 evidence 三源引用）→ _compress_if_needed()
  ↓
_decide_with_retry（两阶段：模式判定单次调用 → 动作校验循环 ≤5 次，禁止逃逸）
  ↓ 第一轮消息：system prompt（动作格式 + 查询类型参考场景规则）
  │            + 上一轮问答原文 + 压缩摘要（概念禁止用作 entities/attrs）+ 画像 + 当前消息
  ↓
_parse_action(reply)
  ├─ chat（显式 type="chat" 或无标记）→ 直接聊天回复 ✅
  └─ 解析成功/错误 → 阶段 2 动作校验循环 → _validate_action()
       ↓
       ↓ 通过
       ↓
       → type == "query"
         → _exec_query(entities, attrs, rel, kb)
           → 三层切片展开（entity 单独 / entity×attr / rel 语义两两配对）
           → for each slice:
                rag.query(slice, kb_name, include_header=True)
                  → retrieve_context(slice, ...)
                    → route_query → retrieve_documents → reranker → NLI → build_context
           → SM3 去重合并 + 源文档头部块回填
           → [插件·Ranker 后点位] pm.run_before_response() — input_return 插件注入上下文（见 §3.10）
           → return {context, docs, kb}
         → _second_pass(message, context, action)
           → build_second_pass_prompt(context, question, kb)  # 3 插槽（含插件来源引用规则）
           → LLM 基于上下文生成回答
           → [插件] pm.run_after_response() — input_output 插件副作用
           → 引用门禁校验
           → 记忆写入（user/assistant/reasoning）→ record_habit() → record_gap()
       → type == "search"
         → search.search(query)
         → _second_pass(...)
       → type == "import"
         → path == "MANIFEST" → 批量导入
         → path == 具体路径 → import_file()
         → 含 content → import_text()
       ↓
回答返回前端（含插件注入内容）
```

### 6.2 导入生命周期 — 完整管道

```
用户上传文件 (Web UI drag & drop)
  ↓
POST /api/agent/upload-files → 保存到 data/imports/ + 写入 import_manifest.json
  ↓
用户说"入库" → LLM 输出 <<ACTION type="import" path="MANIFEST">>
  ↓
_exec_import() → 读取 manifest → 逐个文件:
  1. _do_import(path, kb)
  2. 入库路由（auto_classify 决定目标 KB）
  3. RAGWrapper.import_file() → import_documents_to_kb()
     ├─ 文档加载（PDF: pypdfium2 提取 + 三层 OCR 判断; 其他: TextLoader）
     ├─ 三层切分流水线（守卫栈 → 主策略 → 后处理）
     ├─ ChromaDB 写入（SM3 去重 + SQLite+HNSW 写入前备份 + 写入失败自动回滚）
     └─ KB 签名自动更新（BCE 语义质心 → jieba → 停用词过滤 → BCE 排序 → top-12）
  ↓
manifest try/finally 清空 + 临时文件清理
  ↓
返回各 KB 分布明细
```

### 6.3 SM3 去重策略

```python
import hashlib
seen = set()
for doc in all_docs:
    content = doc.page_content
    h = hashlib.new('sm3', content.encode("utf-8")).hexdigest()
    if h not in seen:
        seen.add(h)
        unique_docs.append(doc)
```

### 6.4 ChromaDB 容灾（v0.7.0+）

| 场景 | 行为 |
|------|------|
| 写入前 | `_backup_kb()` 备份 chroma.sqlite3 + HNSW 索引 |
| 写入失败 | `_restore_kb()` 自动回滚到备份 |
| 查询 HNSW 损坏 | `_try_repair_kb()` 自动清理损坏索引并重建 |
| 配置路径无效 | `load_config()` 自动指向第一个已下载的同类型模型 |

### 6.5 文本切分架构 — `engine/text_splitter.py`

**插件注册架构**：

```
文本输入
  ↓
守卫栈（多选：mermaid / code / math / table / html）
  ↓
主策略（单选：fixed / recursive / headers / sentence / semantic）
  ↓
后处理（单选/不选）
  ↓
chunks 输出
```

通过 `register_strategy()` / `register_guard()` 扩展自定义策略。

### 6.6 智能体插件系统 — `plugins/`（v2.1.0+）

针对应答链路的**可扩展旁路增强**，不侵入核心决策循环。

**插件在智能体生命周期中的位置：**

```
用户提问 → LLM 决策 → RAG 检索管道（route → retrieve → rerank → NLI → build_context，无插件点位）
        → [input_return 插件注入·Ranker 后点位] → LLM 生成回答 → [input_output 插件副作用] → 返回
                                  ↑ 检索完成后、回答前注入                        ↑ 回答后执行副作用
```

**两种插件类型（已实现）：**

| 类型 | 时机 | 用途 | 示例 |
|------|------|------|------|
| `input_return` | 检索管道（含 rerank）完成后、回答生成**前** | 结果注入 LLM 上下文 | 联网搜索补充（web_search）、网络 API 大模型（web_llm） |
| `input_output` | 回答生成**后** | 副作用（不注入上下文） | 日志记录、结果缓存 |

**6 字段池（智能体裁剪传递）：**
`question` / `answer_draft` / `thinking` / `rag_context` / `session_id` / `plugin_dir`

**安全层级（5 道防线）：**

| 防线 | 机制 |
|------|------|
| 信息隔离 | 只传插件声明的 `input_fields`，其余字段不可见 |
| 文件沙箱 | 运行时数据仅限 `data/plugins/<name>/` |
| 超时熔断 | 每个插件独立 timeout，连续 3 次失败自动禁用 |
| 输出校验 | 返回 `type` 非 `markdown/json/csv/plain_text` 则丢弃 |
| SM3 签名 | 可选国密哈希校验插件代码完整性 |

**标准化接口：**

```python
class PluginBase(abc.ABC):
    async def execute(self, inputs: dict) -> dict:
        # 返回: {"type":"markdown|json|csv|plain_text","content":"...","priority":0}
```

**目录结构：**

```
rag_assistant/plugins/              ← 插件框架代码
├── base.py                         ← PluginBase 基类
├── manager.py                      ← 发现/注册/生命周期/熔断
└── builtin/                        ← 内置插件（随系统发布）
    ├── web_search/                 ← 联网搜索
    └── web_llm/                    ← 远程大模型调用

data/plugins/                       ← 运行时数据目录
├── <builtin_plugin>/config.json    ← 内置插件运行时配置
└── <user_plugin>/                  ← 用户安装插件（代码 + 数据）
    ├── plugin.json
    ├── plugin_xxx.py
    └── config.json
```

**AI 插件生成器（Web UI 插件 Tab）：**

插件 Tab 采用左右分栏布局——左侧 LLM 对话面板生成插件，右侧插件管理面板（启用/禁用/配置）。生成流程为二阶段 + 7 步校验：

```
用户描述需求 → 阶段1: LLM 评估可行性 → 确认 → 阶段2: LLM 生成代码
→ ① plugin.json 合法性 → ② Python 语法 (ast.parse)
→ ③ AST 结构检查（防 PluginBase 重定义）
→ ④ 目录规划（user→data/plugins/）→ ⑤ 原子写入 (tempfile+rename)
→ ⑥ SM3 签名 → ⑦ discover_and_register 刷新注册
```

**配置项（`llm_config.json`）：**

插件生成调用与主智能体共享 LLM 配置（model / max_tokens / timeout），仅 `temperature=0.3` 固定用于代码生成确定性。

---

## 七、部署与启动流程

### 7.1 启动模式

| 模式 | 命令 | 说明 |
|------|------|------|
| Web 界面 | `python main.py` | 默认 port 8765，自动分配 RAG 配置子进程端口 |
| CLI 对话 | `python main.py --no-web` | stdin 交互，支持 `/reset` 指令 |
| 批量处理 | `python main.py --batch --input q.json --output r.json` | 结构化输入输出 |
| 管道 JSONL | `cat queries.jsonl \| python main.py --jsonl` | 逐行处理 |
| 数据迁移 | `python main.py migrate` | 从 local-rag-builder 技能迁移知识库/模型 |

### 7.2 Windows 一键启动 — `setup.bat`

```
setup.bat
  ↓
1. 检测 Python 3.9+（缺失则自动下载安装 Python 3.11）
2. pip install -r requirements.txt（首次装依赖）
3. 通过 server.pid 杀掉旧进程
4. 启动服务器（chcp 65001 修复中文乱码）
5. 轮询端口等待就绪（自适应等待，非硬编码秒数）
6. 自动打开浏览器 http://localhost:8765
```

### 7.3 PyPI 发布

- **蓝图文件**：`blueprint_rag.json` 定义发布时包含/排除的文件
- **版本号**：`rag_assistant/__init__.py` 唯一源
- **GitHub Actions**：`permissions.attestations: write` + `skip-existing: true`

### 7.4 CLI 参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--port` | int | 8765 | Web 端口 |
| `--host` | string | 0.0.0.0 | 监听地址 |
| `--data-dir` | string | `./data` | 数据目录 |
| `--config` | string | — | 覆盖配置文件 |
| `--no-web` | flag | false | CLI 对话模式 |
| `--batch` | flag | false | 批量处理模式 |
| `--input` | string | — | JSON 输入文件 |
| `--output` | string | — | JSON 输出文件 |
| `--jsonl` | flag | false | 管道 JSONL 模式 |
| `--pidfile` | string | — | PID 文件路径 |
| `migrate` | subcommand | — | 数据迁移 |

### 7.5 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 全部成功 |
| 1 | 部分失败 |
| 2 | 严重错误 |

---

## 八、依赖与存储

### 8.1 Python 包依赖

```
langchain>=0.1                    # LangChain 框架
langchain-community>=0.3          # 社区加载器（TextLoader 等；PDF 已直用 pypdfium2）
langchain-huggingface>=0.1        # HuggingFace 嵌入
langchain-chroma>=0.1             # ChromaDB 向量存储
langchain-text-splitters>=0.3     # 文本切分
chromadb>=0.5                     # 向量数据库
sentence-transformers>=3.0        # 句子嵌入
huggingface-hub>=0.20             # HF 模型下载
modelscope>=1.15                  # ModelScope 模型下载（国内源）
openai>=1.0                       # OpenAI 兼容 API（LM Studio）
easyocr>=1.7                      # OCR（扫描版 PDF）
requests>=2.28                    # HTTP 客户端
duckduckgo_search>=4.0            # 联网搜索（可选）
jieba>=0.42                       # 中文分词（KB 签名关键词提取，v0.5.x 新增）
numpy>=1.24                       # 向量余弦相似度计算
```

### 8.2 外部服务

| 服务 | 用途 | 备注 |
|------|------|------|
| LM Studio | LLM 推理（localhost:1234） | OpenAI 兼容 API |
| Ollama | LLM 推理（localhost:11434） | /api/chat 接口 |
| ModelScope | 模型下载源（国内首选） | 外部 API |
| HuggingFace Mirror | 模型下载源（国内备用） | 外部 API |
| HuggingFace Official | 模型下载源（国际备用） | 外部 API |
| HuggingFace Direct | 模型下载源（最后兜底） | 外部 API |
| DuckDuckGo | 联网搜索 | 免费 API，无需 Key |
| Tavily | 联网搜索（备选） | 需配置 API Key |

### 8.3 存储依赖

| 存储 | 路径 | 说明 |
|------|------|------|
| ChromaDB | `data/kb/{name}/` | 向量知识库（每库一个 SQLite + HNSW 索引） |
| JSON 文件 | `data/config/rag_config.json` | 引擎配置（含 llm 子字典、prompt_slots、kb_paused） |
| JSON 文件 | `data/kb/kb_index.json` | 知识库索引 |
| JSON 文件 | `data/kb/kb_signatures.json` | KB 签名关键词 |
| JSON 文件 | `data/kb/auto_classify_rules.json` | 自动分类规则 |
| JSON 文件 | `data/models/model_index.json` | 模型索引（含 type 字段：embedding/reranker/nli） |
| JSON 文件 | `data/memory/kb_gaps.json` | 知识缺口（最多 200 条） |
| JSON 文件 | `data/memory/user_habits.json` | 用户习惯 + OCEAN 人格画像 |
| JSON 文件 | `data/prompts/custom_presets.json` | 自定义 prompt 预设 |
| TXT 文件 | `data/sessions/{id}.txt` | 短期对话 |
| TXT 文件 | `data/memory/compressed_{id}.txt` | LLM 压缩摘要 |

### 8.4 配置机制

- **配置文件**：`data/config/rag_config.json`
- **默认配置**：在 `engine/config.py` 的 `DEFAULT_CONFIG` 中硬编码
- **配置加载顺序**：
  1. `DEFAULT_CONFIG` 默认值
  2. `rag_config.json` 实际值（合并到默认上）
  3. 旧版 LLM key 自动迁移到 `llm` 子字典
  4. 模型路径自动修正（失效路径 → 第一个已下载的同类型模型）
- **极客模式**（v0.8.3）：8 区块分区编辑（Prompt / 嵌入模型&检索 / 重排序 / 切片 / 路由层 / 知识库 / LLM / 其他）

---

## 九、安全与隐私

- **无外部调用**：所有 LLM 请求发向本地 LM Studio / Ollama，不上传数据
- **本地知识库**：ChromaDB 向量库存储在本地 `data/kb/`，不离开用户机器
- **联网搜索可选**：默认关闭，需用户手动启用
- **模型本地加载**：所有模型（嵌入/路由/reranker/NLI）通过本地磁盘加载，`local_files_only=True`
- **自包含 vendor**：`vendor/` 嵌入 bs4 / pypdfium2 / markdownify 等第三方库，零外部 pip 安装也可运行

---

## 十、版本演进要点

| 版本 | 新增/变更要点 |
|------|-------------|
| 文档同步 2026-09-04 | 对照代码 v2.4.1 全文复核：决策循环两阶段重写（模式判定 + 动作校验循环 max_retries=5 + 禁止逃逸）、evidence 原文锚定校验（三源 + NLI verify）、查询类型场景层（§1.4，v1.0.1 引入 analysis、后续修复长期存在）、Ranker 后插件点位解析（§3.10，before_response 点位实测锚定）、会话管理补录（§4.6）、Web 端点表补全 |
| v2.1.0b2 | AI 插件生成器（二阶段 LLM + 7 阶段校验管道）；web_llm 多 profile 配置系统；setup.bat HNSW 修复 |
| v2.1.0b1 | 智能体插件系统（PluginBase + PluginManager + 5 道防线）；内置联网搜索插件；插件 Web UI 管理面板 |
| v2.0.0b1 | 1.x → 2.x HNSW 索引引擎更换；Chroma 适配器重构；setup.bat 全量重建提示 |
| v1.8.0 | 外部 API 端口独立（8767）；引擎独立化（engine/ 副本自包含） |
| v1.7.0 | PROTOCOL 协议升级；KB 签名多向量路由 |
| v2.4.1 | 版本号重发（2.4.0 内容） |
| v2.4.0 | PDF 引擎迁移 pypdf → pypdfium2；乱码三层检测（二进制类型/信号2词间距/信号4常用字覆盖）；vendor 替换 |
| v2.3.0 | top-N 多 KB 路由（router.top_n/classify_threshold）；外部 API top_n 参数；死代码清理（FallbackRouter） |
| v1.5.0b1 | Web 配置页面内嵌（iframe 模式）；双端口架构 |
| v1.3.0-beta | 双面板 Web UI（配置 + 对话） |
| v1.2.0 | 组合检索（LLM 分词 + entities × attrs 穷举展开） |
| v1.1.0 | 四层记忆系统（短时/压缩/习惯/缺口） |
| v1.0.0 | 从 local-rag-builder 仓库外项目独立为正式版 |
| v0.9.5 | README 架构图补 NLI；NLI 模型探测遍历所有源修复 |
| v0.9.0 | NLI 三向分类器；网络探测并行化；Config 自动修正模型路径；组合查询两两配对 + 中文逗号 |
| v0.8.0 | KB 暂停写入；历史对话隔离；引用校验；OCR 触发条件修复 |
| v0.7.0 | KB 签名新流程（BCE→jieba→停用词→BCE排序）；精排/路由解耦；ChromaDB 容灾 |
| v0.6.0 | 用户习惯画像系统（OCEAN + 语言分析）；Prompt 自定义预设 |
| v0.5.0 | 出库路由彻底弃用 reranker，改用嵌入模型余弦相似度；KB 签名反哺 |
| v0.4.0 | 入库路由独立（kb.auto_classify）；多知识库主开关（kb.enabled）|
| v0.3.0 | ChromaDB 崩溃修复；状态机解析器重写；MANIFEST 批量导入 |
| v0.2.0 | PROTOCOL.md；llms.txt；--batch / --jsonl 模式 |
| v0.1.0 | 从 local-rag-builder v1.5.0 抽取为独立智能体 |
