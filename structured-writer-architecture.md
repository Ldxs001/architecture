<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
Licensed under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0).
See https://creativecommons.org/licenses/by-sa/4.0/ for details.
-->

# Structured Writer 架构文档

> 结构化写作智能体 — 双线架构：通用写作线（模板驱动子结构级逐段写作）+ 小说模式线（章级规划→写作→章检→修复→全文三检）。
> 作者：wUwproject | 许可证：Apache 2.0
> 更新：2026-08-18 (v3.1.0b5)

---

## 一、系统概览

Structured Writer 是**双线架构**的结构化写作智能体：

**通用写作线**（v1.x 起）：模板驱动 + 子结构逐段生成 + 两级 RAG 增强：

```
用户选择/创建模板
  → [模板系统] 模板定义 meta+content+style+logic 四元结构
  → [用户填写] meta 字段（标题/作者/单位等），content 字段自动参与大纲
  → [大纲规划器] LLM 根据模板 content 生成结构化 JSON 大纲
      节 1: 引言 → [子结构A, 子结构B, 子结构C]
      ...
  → [交互式大纲] 用户可调整勾选/排序/字数/重点/RAG/辅助知识/局部重规划
  → [串行写作器] 逐子结构执行: 两级 RAG → 引用注入 → 前文注入 → LLM 写作 → 续写 → 引用后处理
  → [合并输出] 全文章节拼接为 .md
```

**小说模式线**（v2.0.0b0 起，独立一条线）：

```
场景配置（人物/时代/地点/冲突）
  → 章数组（短3-6/中8-10/长11-15）+ 因果链验证
  → 逐章循环:
      章内子结构规划（S01-S05，用户确认门控）
      → 逐段写作（上下文注入：角色表/人格/实体关系/时间线/情绪/上章轨迹）
      → 章检（4维 8B + 格式 + 逻辑 + 推理 R1）
      → HARD → 修复弹窗（T0 自动修 / T1 重构 / 跳过=通过）
  → 全书所有章 done → 全文三检（忠实度 / 承诺 / 收束）→ 三检修复弹窗
```

### 1.1 核心设计原则

| 原则 | 说明 |
|------|------|
| **模板 > 空白** | 文章结构由模板定义（meta+content），LLM 和用户都在模板确定的边界内操作 |
| **子结构 > 整段** | 节拆分为 2-4 个子结构逐段写作，每段独立调 LLM，避免长上下文注意力衰减 |
| **材料分级 > 一股脑** | 节级 RAG 提供背景上下文，子结构级 RAG 提供针对性素材，文档元数据全局共享 |
| **引用后处理 > LLM 格式** | LLM 写自然语言标记（引用自{文件名}），确定性代码替换为编号 [N] 并生成参考文献 |
| **续写 > 截断** | token 耗尽时不丢弃已写内容，自动续写最多 5 轮 |
| **可配置 > 黑盒** | 模板所有字段可编辑，大纲所有字段均可交互调整 |
| **容错 > 崩溃** | RAG 超时不塞 prompt，空内容跳过，写作者异常降级为错误提示 |
| **状态持久 > 内存** | 进度写入 state_manager，断线重连可恢复 |
| **文件真相源 > session 状态** | 章级/段级续写跳过判定以磁盘文件为准，防 session 与磁盘分叉重复重写 |
| **跳过 = 通过** | 修复弹窗：勾选=重构，不勾选/全部跳过=立即标记通过（不再重检） |
| **全文三检只检全文** | 全文三检仅在全书所有章 done 后触发一次（"if 规划 else 全文三检"） |

---

## 二、后端架构（v3.1.0b1 定稿：LM Studio 统一管理）

> **历史决策**：v3.1.0b1 起 **llama.cpp 直挂后端整体废弃**——llama-cpp-python 0.3.34 旧内核无新 MoE 优化，35B 写作仅 8 t/s vs LM Studio 20+ t/s。llm_client.py 删除全部 llama.cpp 分支，保留纯 HTTP 客户端。

| 角色 | 模型 | 后端 | 生命周期 |
|------|------|------|---------|
| 写作/规划（35B） | qwen/qwen3.6-35b-a3b | **LM Studio**（lms load → GPU → HTTP localhost:1234） | 任务内复用，任务结束自动卸载 |
| 判定 4维（8B） | qwen3-8b | LM Studio（统一管理勾选）/ transformers 3B（不勾） | 章检测完即卸（lms unload） |
| 判定 R1（7B） | deepseek-r1-distill-qwen-7b | 同上 | 同上 |
| 实体/行为/时间线提取（3B） | Qwen2.5-3B | **永远 transformers（CPU）** | 常驻复用 |
| 通用线写作 | 用户配置（LM Studio/Ollama） | HTTP（1234 / 11434） | 会话内 |

- **统一管理勾选**：planner/writer 后端都是 LM Studio 时可勾选 → 判定 8B/7B 走 LM Studio GPU；不勾 → transformers 3B/1.5B
- **ollama 场景**：写作后端为 Ollama 时统一管理禁用（判定模型仍是 LM Studio/transformers）
- **LM Studio 生命周期**：`novel/lmstudio_probe.py` 封装 lms.exe（load/unload/ps/import/server start）；判定模型用 `make_lms_handle`（带 `_lms_model_key` 标记）→ `release` 识别 lms 句柄 → lms unload
- **模型管理**：8B/7B GGUF 位于 LM Studio 模型库 `~/.lmstudio/models/`（本地移入或自动下载 + lms import）；`judge_model_keys` 从 lms ls 解析（支持裸名 key 与 user/repo 形态）
- **窗口**：判定模型固定 16384（R1 思考链+JSON ≈13K）；8B 判定带 `/no_think` 关思考（LM Studio 分离 reasoning_content 字段）

---

## 三、三层架构

| 层 | 组件 | 职责 |
|---|------|------|
| **表现层** | `web_ui.py` (port 8770) / 配置 Tab / 对话 Tab | Web 界面、LLM 配置面板、模板编辑器、大纲交互、小说质检配置、修复面板、进度展示 |
| **业务层** | `planner.py` / `writer.py` / `rag_client.py` / `llm_client.py` / `state_manager.py` / `citation_validator.py` + `novel/*` 子包 | 通用线（大纲规划、逐段写作、RAG、LLM、状态、引用）+ 小说线（规划/写作/章检/全文三检/修复） |
| **基础设施** | `config_manager.py` / `main.py` / `data/` / `setup.bat` | 配置读写、服务入口、数据持久化、一键启动 |

### 3.1 完整文件结构

```
structured-writer/
├── main.py                            # ★ 入口（HTTP 服务器 + 对外写作 API 8777）
├── setup.bat                          # Windows 一键启动（任意 Python 版本，自动装 transformers）
├── requirements.txt                   # 依赖清单（transformers/torch，无 llama-cpp-python）
├── CHANGELOG.md                       # 版本更新日志（1279 行，v0.1.0 → v3.1.0b5）
├── SCHEMA.md                          # 方案文档
├── README.md                          # 项目说明
├── LICENSE                            # Apache 2.0
├── blueprint.json                     # PyPI 发布蓝图
├── config.json                        # 默认配置（不含模板）
│
├── structured_writer/                 # ★ 智能体核心包（PyPI 包名 structured-writer-ldxs）
│   ├── __init__.py                    # 版本号唯一源（3.1.0b5）
│   ├── web_ui.py                      # HTTP 服务器 + 前端（~7000 行，11 个 /api/novel/* 端点）
│   ├── planner.py                     # 通用线大纲规划器（LLM 生成 JSON 大纲）
│   ├── writer.py                      # 通用线串行写作器（两级 RAG + 续写 + 引用后处理）
│   ├── rag_client.py                  # RAG 客户端（调 rag-assistant :8767）
│   ├── llm_client.py                  # LLM 统一客户端（纯 HTTP：LM Studio / Ollama）
│   ├── state_manager.py               # 会话状态管理 + 修复提示（_repair_hints + repair_pending）
│   ├── citation_validator.py          # 引用验证（扫描+报告）
│   ├── config_manager.py              # 配置读写 + 模板分离存储 + 旧格式迁移
│   ├── external_api.py                # 对外写作 API（/api/write，8777 独立端口）
│   ├── aux_parser.py                  # 辅助解析
│   ├── md2tex.py                      # md → tex + xelatex 编译
│   ├── novel/                         # ★ 小说模式子包
│   │   ├── novel_bridge.py            # 场景配置→章数组→因果链→outline→项目初始化→plan-chapter
│   │   ├── novel_writer.py            # 小说写作引擎（逐章 plan-chapter + 写作 + 章检门控 + 全文三检触发）
│   │   ├── novel_workflow_engine.py   # 章检/全文三检编排（子进程 finalize-chapter/finalize-novel）
│   │   ├── novel_repair_engine.py     # 修复引擎（T0 自动修/T1 重构、轮次、三检当场重检）
│   │   ├── novel_4dim_check.py        # 章检 4 维判定（时间/情绪/话题/角色，8B 或 3B）
│   │   ├── novel_reasoning_check.py   # 推理审核 R1（7B，5 维）
│   │   ├── novel_fidelity.py          # 大纲忠实度检查（全文三检）
│   │   ├── novel_pledge_check.py      # 全文承诺检查（全文三检）
│   │   ├── novel_logic_check.py       # 逻辑检查（4维 回退链）
│   │   ├── novel_entity_extractor.py  # 实体提取（3B + 正则兜底）
│   │   ├── novel_behavior_extractor.py# 行为提取（3B + 正则兜底）
│   │   ├── novel_timeline*.py         # 时间线提取（3B + 正则兜底，day 累计解析）
│   │   ├── novel_state_manager.py     # novel_state.json 读写
│   │   ├── novel_atomic_writer.py     # 原子写入 + 末行标记
│   │   ├── novel_character_registry.py# 角色注册表（name+aliases，占位符挡截）
│   │   ├── novel_continuity.py        # 规则连通性检查（4维 回退）
│   │   ├── novel_style_check.py       # 风格检查
│   │   ├── model_backend.py           # 判定模型后端路由（LM Studio / transformers）+ _model_profile
│   │   ├── lmstudio_probe.py          # LM Studio 环境探查 + lms 生命周期封装
│   │   └── model_env_check.py         # 环境探测（transformers/torch 缺失自动安装）
│   └── plugins/                       # 数据源插件系统
│       ├── base.py / manager.py
│       └── builtin/db_source/         # 数据库数据源插件（SQLite/MySQL/PG/CSV）
│
└── data/                              # 运行时数据（不出库）
    ├── config.json                    # 运行时配置
    ├── sessions/{id}.json             # 对话状态
    ├── archives/sessions/             # 归档会话
    ├── outputs/{name}_{ts}/           # 生成结果（md + 图片集）
    ├── templates/user_templates.json  # 用户自定义模板（内置模板在代码中）
    ├── examples/examples.json         # 快速范例
    ├── novel/projects/{id}/           # 小说项目（data/novel_state.json + chapters/<章>/*.txt）
    └── models/                        # transformers 模型（Qwen2.5-3B / R1-1.5B 等）
```

---

## 四、模板系统

### 4.1 模板结构

每个模板由四个部分组成（小说模板额外带 `novel` 标记）：

```
{
  "meta": [...],       // 元数据区 — 短标识信息（标题/作者/单位/文号等）
  "content": [...],    // 内容树区 — 文章正文结构
  "style": "...",      // 风格提示词 — 控制文风语气
  "logic": "..."       // 逻辑提示词 — 控制 LLM 写作认知流程顺序
  // 小说模板: "novel": {"mode": true, "kind": "chapters"} 等
}
```

**meta 字段**：每条含 `name/show_label/desc/source`。source 分三类：

| source | 含义 |
|--------|------|
| user | 用户必须填写（如作者、单位、文号） |
| auto | 用户可选填，留空由 LLM 生成（如标题） |
| llm | 由 LLM 生成（如关键词），推荐放 content |

**content 字段**：每条含 `name/show_label/type/kind/desc`（通用线）+ `citation_check/citation_format`（引用节）。

| type | 含义 |
|------|------|
| leaf | 单段内容，不拆子结构（摘要、关键词、参考文献） |
| section | 需要拆 2-4 个子结构（引言、方法、结果、结论） |

| kind（小说模板特有） | 含义 |
|------|------|
| setting | 设定节点（世界观设定/人物表），不输出正文，存状态 |
| chapters | 正文（多章锚点，由 AI 自由展开 L01-L15） |

**logical_order**：控制 LLM 写作的认知流程顺序，而非文章最终顺序（0=先写 / 1=其次 / 2=最后写）。

### 4.2 内置模板 vs 用户模板

- 内置 9 套（代码常量，只读）：日常写作 / 学术论文 / 正式公文 / 新闻报道 / 技术报告 / 通用公文 / 论文综述 / 自定义 / **小说**
- 用户模板存 `data/templates/user_templates.json`，可创建/编辑/删除（内置只读）
- 另存为副本继承 novel.mode/kind；小说模板「题材」「篇幅」字段锁定（UI 禁用 + 保存校验双保险）

### 4.3 引用校验

content 字段支持 `citation_check` 和 `citation_format` 配置（`[x]=1.` 格式：`=` 前为行内标记模板，后为参考文献列表前缀）。字段名含"参考文献"或"引用"时 `_normalize_template()` 自动设 `citation_check=true`。

### 4.4 模板生成（对话生成）

`POST /api/gen-template` → LLM 生成模板 → 多级 JSON 容错解析（最多重试 3 次）→ `_normalize_template()` 校验补默认值 → 存用户模板。

---

## 五、组件详解

### 5.1 通用线大纲规划器 — `planner.py`

`plan_outline()` 调用 LLM 根据模板的 meta+content 生成结构化 JSON 大纲。`parse_outline()` 4 种解析策略（直接 json.loads / ```json 提取 / ``` 提取 / 首 `{` 截取），失败追加纠正指令重试（最多 3 次）。子结构规范化：leaf 不补、section 自动补默认子结构、补全 id/summary/word_count/_checked/_logical_order。

### 5.2 通用线串行写作器 — `writer.py`

`generate_article()` 逐节逐子结构串行调用 LLM：

- **两级 RAG**：节级查询（标题+节标题+summary）→【背景资料】；子结构级查询 →【针对性资料】；`all_rag_headers`（文档元数据）全局共享
- **引用后处理**：正则扫描 `引用自{文件名}` → 去重编号 → 替换 `[N]` → 构建参考文献节
- **续写机制**：`finish_reason=="length"` 时追加"请继续写"重试（最多 5 次）；空内容放弃
- **事实自检**：内嵌标记法 `【事实待核查】`（零额外 LLM 调用），文末汇总「建议人工复审」清单
- **错误容错**：LLM 异常写错误提示、空内容跳过、RAG 超时不塞 prompt

### 5.3 小说线入口 — `novel_bridge.py`

```
generate_scene_config(topic, template)   # 场景配置（人物含 MBTI+荣格原型/时代/地点/冲突/文风）
generate_chapters(setting, topic, length) # 章数组（短3-6/中8-10/长11-15，概述≥12字符+因果动词）
verify_causality(chapters)               # 因果链验证（不过 → 反馈重生成，最多 2 次）
init_novel_project(project_id, ...)      # 项目初始化 data/novel/projects/{id}/
plan_chapter_subs(state_path, chapter)   # 章内子结构规划（S01-S05，tone/emotions/writing_prompt≥50 硬校验，末章 is_ending）
plan_novel_outline(...)                  # 主入口：场景配置 → 章数组 → 因果链 → outline + 项目初始化
```

### 5.4 小说线写作引擎 — `novel_writer.py`

`generate_novel_article()` 逐章循环（每章规划→确认→写作→章检）：

- **续写恢复（文件为真相源）**：章子结构文件齐全 → 无论 session 状态跳过 + 同步 done；文件不齐按状态降级
- **章级门控**：仅 pending 章规划子结构；planning 等待用户确认（`_wait_confirm` 轮询）
- **上下文注入**：角色表/人格/实体关系网/时间线/情绪基调/上章行为轨迹/写作命题框（三层分区：目的★★★/背景★★/参考★）
- **写入**：进程内直接落盘（`_write_sub_inline`，原子写 + 别名拦截 + 实体提取 + 字数三档校验），失败停止整章
- **章检门控**：`finalize_novel_chapter`（子进程）→ 有 HARD/FAIL → 修复轮次循环（`repair_rounds` 默认 3）→ 通过标章 done
- **全文三检守卫**：`_all_done = all(section.status == 'done')`——全书所有章 done 才执行 `finalize_novel_full`（"if 规划 else 全文三检"）

### 5.5 章检与全文三检 — `novel_workflow_engine.py`

**章检（finalize-chapter，每章）**：

| 检查 | 内容 | 模型 |
|------|------|------|
| 4维 | 时间衔接/情绪匹配/话题过渡/角色承接（共享上下文 + 判定提示词分隔，叙事目的哲学） | 8B（/no_think）或 3B |
| 格式 | 末行标记/禁用模式/文件数 | 规则（毫秒级） |
| 逻辑 | 角色消失/时间回退/概述偏离/实体关系断裂 | 3B（4维 回退链） |
| 推理 R1 | 因果合理性/情绪弧/行为一致/对话匹配/论证可靠性（5 维） | 7B |

**全文三检（finalize-novel，全书 done 后）**：

| 检查 | 内容 | 模型 |
|------|------|------|
| fidelity 大纲忠实度 | L1 词面全量筛 → 覆盖率<0.6 可疑段 3B 复核 | 3B |
| pledge 全文承诺 | 3B 按正文提取 flag → writer 推理判已兑现/未兑现/悬停 | 3B + writer |
| ending 结尾收束 | 末章末段 → 3B 判封闭/开放/悬停三型 | 3B |

问题写入 `novel_state._full_repair` → novel_writer 同步进 `session._repair_hints[chapter].full_items`（与章检 issues 同层统一判定）。

### 5.6 修复引擎 — `novel_repair_engine.py`

`run(state_path, chapter_dir, chapter, issues, mode, checked_subs, repair_types)`：

- **T0 自动修**（纯格式：末行编号/禁用模式）：代码直改正文，不弹窗
- **T1 重构**（内容问题）：勾选的子结构 → 写作模型重构（整段契约：保留首行标题/末行编号/别名行/字数 ±15%/只输出正文）→ 校验 → 原子写 + 备份
- **R1 引导式局部改写**：`_build_guided_prompt`（完整正文 + R1 detail 问题描述，writer 自行定位局部改写）→ `_validate_guided`（三行保留 + 输出与原文有差异）
- **三检类型化重构**：fidelity/pledge/ending 变体指令 + `source_text` 定位；pledge 减法 = 移除悬置承诺+平滑衔接
- **当场重检**：勾选修复 = 重构成功后当场重跑对应检查（章检六项 / fidelity / pledge / ending），通过才移除修复项
- **模式**：手动（无上限，刷新面板）/ 自动（`repair_rounds` 上限）；跳过=通过（`_repair_result.skipped` → 不再重检不重置）
- **共享实例**：`_create_repair_client` 复用共享 35B（规划/写作/修复同一模型只加载一次）；`_release_repair_client` 去 close（防僵尸实例）

### 5.7 判定模型后端 — `model_backend.py`

- `judge_backend(cfg)`：统一管理勾选 → lmstudio；否则 transformers
- `judge_model_keys`：lms ls 解析 8B/7B key（裸名 key 与 user/repo 形态）
- `lms_generate`：HTTP 生成（Qwen 系 chatml）；`make_lms_handle`：可调用句柄（带 `_lms_model_key` 标记）
- `ensure_judge_models`：缺失检测（库无 8B/7B → 明确提示下载 + 回退 transformers 3B）
- `release`：识别 lms 句柄 → lms unload（测完即卸）；transformers 句柄 → del + gc
- `_model_profile(model_cfg)`：按后端取配置槽（profiles 分槽，web_ui/repair 共用，旧格式兼容）

### 5.8 LLM 客户端 — `llm_client.py`

纯 HTTP 客户端（LM Studio / Ollama 双后端）：

| 后端 | 协议 | 接口 | 默认端口 |
|------|------|------|---------|
| LM Studio | HTTP (OpenAI 兼容) | `/v1/chat/completions` | 1234 |
| Ollama | HTTP (Ollama API) | `/api/chat` | 11434 |

- `chat_detailed()` 返回 `{content, finish_reason}`（续写检测）；`chat()` 返回纯文本
- `list_models()` 30 秒 TTL 缓存（key=backend|base_url——LM Studio API 实测 2 秒，缓存后秒回）
- max_tokens/temperature 从 config 读取存储为实例属性

### 5.9 状态管理器 — `state_manager.py`

管理会话全生命周期：`load/get_state/set_phase/update_section/get_progress/set_status_text/fingerprint_check` + 修复提示：

- `save_repair_hint(chapter, result)`：覆盖时**保留已有 `_repaired`**（防跳过被章检覆盖又弹）
- `get_progress()` 的 `repair_pending`：章检 issues HARD/FAIL 或三检 full_items 非空且未 `_repaired` → 覆盖式最近章

### 5.10 配置管理器 — `config_manager.py`

- config.json 原子写入（tmp → replace），深层合并默认值
- planner/writer 模型配置：**profiles 分槽结构** `{backend, profiles: {lmstudio, ollama}}`（v3.1.0b1 移除 llama.cpp profile，v3.0.0b37 引入分槽，前端切后端自动恢复对应槽）
- 内置模板 `DEFAULT_TEMPLATES` + 用户模板 `data/templates/user_templates.json`
- 旧格式迁移 `_migrate_old_templates()`

---

## 六、外部接口

### 6.1 HTTP 端点（Web UI，8770）

**通用线：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` 或 `/index.html` | GET | 主页面（配置 Tab + 对话 Tab） |
| `/api/config` | GET/POST | 读取/保存配置（含模型 profiles 分槽） |
| `/api/llm/models` | GET | 扫描模型列表（30s 缓存） |
| `/api/llm/test` | POST | 测试 LLM 连接 |
| `/api/llm/window` | GET | 窗口信息提示（只提示不强制） |
| `/api/plan` | POST | 生成/重新规划大纲 |
| `/api/generate` | POST | 启动生成任务 |
| `/api/progress` | GET | 获取生成进度 |
| `/api/result` | GET | 获取最终结果 |
| `/api/stop` | POST | 停止生成 |
| `/api/sessions` | GET | 会话列表 |
| `/api/session/new|load|archive|restore|delete` | - | 会话管理 |
| `/api/chat` | POST | 对话消息处理（含写作意图检测） |
| `/api/gen-template` | POST | LLM 生成模板 |
| `/api/rag/status|start|stop` | - | RAG 状态/冷启动/停止 |
| `/api/batch_auto` / `/api/batch_progress` | - | 批量自动撰写 |
| `/api/outputs` / `read` / `delete` | - | 已完成文章管理 |
| `/api/examples` | - | 快速范例 |

**小说线（/api/novel/*）：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/novel/status` | GET | 小说质检状态（判定后端/模型就绪/配置） |
| `/api/novel/checks` | POST | 保存质检配置（章检/全文三检开关/统一管理/修复轮次） |
| `/api/novel/install` | POST | 安装缺失模型（8B/7B 下载到 LM Studio 模型库 + import） |
| `/api/novel/confirm` | POST | 章内子结构确认（勾选/字数覆盖/重点） |
| `/api/novel/replan_sub` | POST | 子结构级重规划 |
| `/api/novel/replan_status` | GET | 重规划 in-flight 状态 |
| `/api/novel/repair/preview` | GET | 修复面板分级清单 |
| `/api/novel/repair/apply` | POST | 开始修复（checked_subs + repair_types） |
| `/api/novel/repair/rollback` | POST | 回滚正文+state |
| `/api/novel/repair/skip` | POST | 全部跳过（= 标记通过，不再弹） |
| `/api/novel/repair/status` | GET | 修复进度轮询（带 session_id 会话隔离） |

**对外写作 API（8777 独立端口）：** `POST /api/write`（同步写作：prompt/template/images/rag/format）、`GET /api/health`、`GET /api/capabilities`。

### 6.2 RAG 外部依赖

| 依赖 | 端口 | 说明 |
|------|------|------|
| rag-assistant 外部 API | 8767 | 知识库查询（/api/kb/query），v2.2.10+ 提供文档元数据 |
| rag-assistant 冷启动 | 18765 | 子进程 Web UI 端口（冷启动用） |

### 6.3 配置结构（config.json）

```json
{
  "planner_model": {"backend": "lmstudio", "profiles": {"lmstudio": {...}, "ollama": {...}}},
  "writer_model": {"backend": "lmstudio", "profiles": {"lmstudio": {...}, "ollama": {...}}},
  "selected_template": "通用公文",
  "rag_path": "",
  "context_review_length": 8000,
  "fact_check_enabled": false,
  "max_sessions": 20,
  "novel_checks": {"chapter": true, "format": true, "reason": true,
                   "full_fidelity": true, "full_pledge": true, "full_ending": true,
                   "auto_repair": false, "repair_rounds": 3,
                   "unified_management": true}
}
```

- 模型配置为 **profiles 分槽**：切后端（lmstudio/ollama）自动恢复对应落盘配置（地址/模型/参数互不覆盖）
- 小说质检配置存 `novel_checks`（章内 4维/格式/推理 R1 + 全文三检三开关 + 自动修复/轮次 + 统一管理）

---

## 七、UI 布局

对话界面为三栏布局（会话管理 / 对话交互 / 已完成文章）。配置 Tab 含：模型配置（后端下拉 LM Studio/Ollama + 地址 + 模型列表）、模板管理、RAG 配置、写作参数、**小说质检区**（章内检测/全文检测分组 + 点位标注 + 统一管理勾选 + 检测模型按钮）。

### 7.1 小说确认面板

章内子结构规划完成后弹出：勾选（取消=跳过）、字数覆盖、重点标记。确认后进入写作。

### 7.2 修复面板（章检 HARD / 三检问题）

```
┌─ L02《信号与躯壳》全文质检需处理 ─────────────┐
│  HARD ☑ SOFT ☑（级别过滤，未勾选级别子结构隐藏） │
│  ☑ [4维] S02：话题过渡无叙事目的                │
│  ☑ [推理] S02：对话匹配度（用词超出角色）        │
│  ☐ [R1] S04：情绪弧转变突兀                     │
│  勾选 = 用写作模型重构修复；不勾选 = 立即标记通过 │
│  [全部跳过]              [开始修复]             │
└───────────────────────────────────────────────┘
```

- T0 自动修不弹窗；T1/三检进弹窗；跳过=通过（不再弹）
- 手动模式无上限（修复→自动重检→刷新面板）；自动模式有轮次上限

---

## 八、写作管线

### 8.1 通用线完整请求生命周期

```
用户点击"开始生成"
  ↓
POST /api/generate → _handle_generate()
  ├─ 加载会话状态 → 应用勾选过滤 → 应用排序
  ├─ 探测 RAG 8767 → 创建 RAGClient（如果在线）
  ├─ 从模板构建 citation_config → 创建 LLMClient（配置读取）
  └─ 启动后台线程 _run_generation()
      ↓
generate_article(outline, rag_options, llm_client, state_mgr, rag_client, template, citation_config)
  ├─ 逐节（按 logical_order 排序写作，按 content[] 顺序输出）
  │   ├─ 节级 RAG（all_rag_headers 累积）→ 写入 ## 节标题
  │   └─ 逐子结构: 子结构 RAG → 构建 prompt → LLM → 续写 → 事实标记 → 写入 ### 子标题
  ├─ 引用后处理（citation_check）→ 事实自检汇总 → 引用验证
  ├─ 写入 .md → data/outputs/{timestamp}_{title}/
  └─ 更新 phase="done"
```

### 8.2 小说线完整请求生命周期

```
选择「小说」模板 → 输入题材/篇幅 → 生成
  ↓
plan_novel_outline()：场景配置 → 章数组 → 因果链验证 → 项目初始化
  ↓
generate_novel_article() 逐章循环：
  ├─ 章内子结构规划（plan_chapter_subs）→ 确认面板门控（_wait_confirm）
  ├─ 逐段写作（三层上下文注入 + 原子写 + 实体/行为/时间线提取）
  ├─ 章检（finalize_novel_chapter 子进程）→ HARD 拦截 → 修复轮次循环
  │   └─ 修复引擎 run()：T0 自动修 / T1 重构 / R1 引导式 / 三检类型化 → 当场重检
  ├─ 通过 → 标章 done → 章级 md 落盘
  ↓
全书所有章 done → 全文三检（finalize_novel_full）→ 三检修复项同步 session.full_items
  ↓
三检修复弹窗（勾选修复当场重检 / 全部跳过）→ 处理完放行 → 整本拼合（手动）
```

---

## 九、版本演进要点

| 版本 | 新增/变更要点 |
|------|-------------|
| v3.1.0b5 | 8B/7B 全链路实机验证（7B 推理审核 / 8B /no_think 关思考）；纯验证无代码改动 |
| v3.1.0b4 | lms ls 裸名 key 过滤修复；8B/7B 移入 LM Studio 模型库（自动识别无需 import） |
| v3.1.0b3 | 判定窗口 UI 移除（固定 16384）；ollama 场景禁用统一管理 |
| v3.1.0b2 | setup.bat 去 py 3.11 优先（任意 Python 版本） |
| v3.1.0b1 | **llama.cpp 直挂后端整体废弃 → LM Studio 统一管理**（写作/规划 35B + 判定 8B/7B）；新增 lmstudio_probe.py；llm_client 删全部 llama.cpp 分支；config 移除 llama.cpp profile |
| v3.0.0b33-41 | llama.cpp 推理参数优化（后被 b1 废弃）；模型配置 profiles 分槽；模型恢复修复（_modelValues 内存值）；模型列表缓存 |
| v3.0.0b29-32 | 跳过=通过；全文三检触发守卫（if 规划 else 全文三检） |
| v3.0.0b20-28 | 35B 不常驻（weakref 共享）；修复引擎共享/独立/防重入/会话隔离/静默失败修复/超窗降级 |
| v3.0.0b17-19 | llama.cpp 实例进程级共享；判定模型弱引用（测完即卸） |
| v3.0.0b15-16 | 修复面板 HARD/SOFT 级别过滤 |
| v3.0.0b10-14 | 章检 prompt 哲学（内容一致→叙事目的）；KV 量化 flash_attn；窗口动态；n_gpu_layers VMM 修复 |
| v3.0.0b0 | 门禁体系废除；模型架构 3→2（去 bge）；全文三检全 LLM 化；三检修复弹窗复用 + 当场重检 |
| v2.4.0b0 | 重规划全链路 UI；三层分区上下文；三提取器统一（实体/行为/时间线） |
| v2.3.x | 续写文件真相源；实体清洗死循环；章检 HARD 拦截（ok→issues 判定） |
| v2.0.0b0 | **小说模式引入**（P1-P4：模板+路由 / novel 子包 / 模型层 / 检查体系） |
| v1.9.0b0 | 插件系统（数据源插件）；大表蓝皮书取数 |
| v1.7.0 | 对外写作 API（8777）；md2tex/pdf；快速范例；两级局部重规划；_tmpl_key 血缘 |
| v1.2.0 | 辅助资料（图片/文字/表格特化管线）；输出目录化 |
| v1.1.0b9 | 模板存储分离；引用校验字段；IMRaD 内置模板；三栏布局 |
| v1.0.28 | 事实自检内嵌标记法；temperature 可配置；RAG 停止；批量自动撰写；会话归档 |
| v0.2.5b3 | PyPI 发布准备：app/ → structured_writer/ |
| v0.1.0 | 项目骨架、LLM 客户端、会话管理、大纲规划器、串行写作器 |

---

*最后更新：2026-08-18 (v3.1.0b5)*
