<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
Licensed under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0).
See https://creativecommons.org/licenses/by-sa/4.0/ for details.
-->

# silprespec-orchestrator 架构文档 — v0.1.0

> 前置规范编排器 — 基于"我思故我写"方法论的多 agent 协同头部规划器。根据用户任务+工具集，从 14 种穷举的原子化组合里选最合适的，PY 确定性组合，LLM 填空执行，输出给工具（智能体）走内部流程。
> 作者：wUwproject | 许可证：Apache 2.0
> 更新：2026-08-31

---

## 一、系统概览

silprespec-orchestrator 是**前置规范编排器**，核心理念：**LLM 只填空不决策，前置规范 > 后置验证，PY 确定性组合，槽位是减法不是加法**。

```
用户输入 + 工具集
  → [Orchestrator 主控]
       ├─ 输入分类（穷举 6 类别，LLM 填空分类 → PY 查表映射）
       ├─ 选编排模式（serial / parallel，PY 确定性）
       ├─ 分解子任务（LLM 填空，每子任务指定一个工具）
       └─ 生成进度地图（ProgressMap，贯穿全局）
  → [逐子任务执行]
       for each subtask:
         Mapper（选 14 种组合之一 + 设参 + output_limit）
           → LLM 填空选组合编号，PY 查表验证
         Composer（PY 确定性组合，调 exec_recipe）
           → 生成原子(LLM 填空) → 后处理原子(PY) → 校验原子(PY) → 观测原子(PY)
           ↳ 不通过则 retry loop（最多 max_retry 次）
         Executor（LLM 填空生成工具输入 → HTTP 调智能体 API）
         Adapter（步骤间适配：能直通则直传，不能则 loop 回 Mapper 选适配组合）
  → 汇总输出
```

**编排器不替智能体干活。** 智能体自带领域能力（RAG 检索在 rag-assistant、写作在 structured-writer），编排器只做头部规划：选前置规范 → 填空 → 交付给智能体走内部流程。

### 1.1 核心设计原则

| 原则 | 说明 |
|------|------|
| **LLM 只填空不决策** | LLM 出现在选组合（填编号）、生成内容（填槽位/填文本），**不决定流程走向**。流程由 PY 确定性查表驱动 |
| **前置规范 > 后置验证** | 先约束再生成（14 种组合在生成前就钉死格式/值域/槽位），不是生成后检查 |
| **PY 确定性组合** | 每个组合骨架是 `生成→后处理→校验→观测`，PY 部分确定性查表，只有生成那步是概率的 |
| **槽位是减法不是加法** | 槽位定义"只准填这些"，多余 key 是编造，不是"多给了信息" |
| **保留聪明剥夺自由度** | LLM 负责填空（聪明），PY 负责约束（剥夺自由度）。两者正交不冲突 |
| **穷举 > 猜测** | 14 种组合在当前原子库下穷举完，不存在第 15 种。不靠 LLM 猜该用什么规范 |
| **进度地图贯穿全局** | 每步 LLM 都看到完整用户初始输入 + 输入分类 + 全局进度，不盲目执行 |
| **递归自举** | 编排器自身的前置规范也来自 14 种组合（Adapter 适配时 loop 回 Mapper 选组合） |
| **配置推动** | CLI > config.json > DEFAULT_CONFIG，max_tokens / timeout 从配置读取 |

### 1.2 与 Orchestrator 的关键差异

| 维度 | Orchestrator（链驱动） | silprespec-orchestrator（前置规范编排） |
|------|----------------------|----------------------------------------|
| **核心定位** | 技能链执行（subprocess 跑脚本） | 前置规范选择+填空（LLM 填空 → 调智能体 API） |
| **LLM 角色** | 前处理 + 输出整理（两头） | 选组合 + 填空生成（贯穿每步，但只填空不决策） |
| **中间执行** | subprocess 真跑 skill 脚本 | PY 确定性组合（exec_recipe）+ HTTP 调智能体 |
| **规范来源** | 用户编排 Pipeline | 14 种穷举组合自动选择 |
| **loop 语义** | for 真循环（次数固定） | retry loop（校验不通过则重试）+ Adapter loop（适配回 Mapper） |
| **端口** | 8788 | 8789 |

---

## 二、目录结构

```
silprespec-orchestrator/
├── main.py                               # CLI 入口（Web UI / 单次查询 / 检测）
├── setup.bat                             # Windows 一键启动（端口 8789）
├── requirements.txt                      # 依赖清单（零第三方依赖，纯标准库）
├── config.json                           # 配置（LLM + orchestrator + combos）
├── CHANGELOG.md                          # 版本更新日志
├── PROTOCOL.md                           # 接口契约
├── llms.txt                              # AI 可读项目自描述
├── README.md                             # 项目说明
│
├── silprespec_orchestrator/              # ★ 智能体核心包
│   ├── __init__.py                       # 导出 + __version__ 唯一源（0.1.0）
│   ├── orchestrator.py                   # 编排器主控（分类→选模式→分解→执行→汇总）
│   ├── progress_map.py                   # 进度地图 + 输入分类 + 编排模式选择
│   ├── mapper.py                         # 选组合 + 设参（LLM 填空选，PY 查表验证）
│   ├── composer.py                       # PY 确定性组合器（调 exec_recipe）
│   ├── executor.py                       # LLM 填空 + HTTP 调智能体 API
│   ├── adapter.py                        # 步骤间适配（直通 or loop 回 Mapper）
│   ├── combo_registry.py                 # 14 种穷举组合声明
│   ├── tool_registry.py                  # ToolSpec/FieldSpec/ExampleSpec + 三智能体注册
│   ├── atoms.py                          # 原子库（10 原子 + Recipe + exec_recipe 通用执行器）
│   ├── pipeline_model.py                 # 数据模型（WayConfig/WayResult/5 种方式）
│   ├── llm_client.py                     # LLM 统一客户端（LM Studio/Ollama/自定义）
│   ├── web_ui.py                         # Web UI 服务器（http.server）
│   └── static/                           # 前端静态资源
│       ├── index.html                    # 四 Tab 页面（编排/组合/工具/配置）
│       ├── style.css                     # 样式（深色 Tab + #667eea 主色）
│       └── web_ui.js                     # 前端逻辑（LLM 配置 + 工具详情 + 组合展示）
```

---

## 三、核心编排架构

### 3.1 主控流程（orchestrator.py）

```
Orchestrator.run(user_input, tool_names):
  ① 分类（穷举 6 类别）
     classify_input(user_input, chat)
       → LLM 填空分类（只输出类别 id）→ PY 查表映射
       → (extract / generate / analyze / verify / transform / orchestrate)

  ② 选工具
     _select_tools(tool_names) → 从 TOOL_REGISTRY 取 ToolSpec 列表

  ③ 分解子任务（LLM 填空）
     _decompose(user_input, category, tools, chat)
       → LLM 根据工具清单把任务拆为子任务数组
       → 每子任务：{"name":"步骤名", "desc":"描述", "tool":"工具名"}
       → 失败回退为单任务

  ④ 选编排模式（PY 确定性）
     select_orchestration_mode(category, num_steps)
       → num_steps ≤ 1 → serial
       → extract/transform/verify → parallel
       → generate/analyze → serial
       → 默认 → serial

  ⑤ 生成进度地图（ProgressMap）
     记录 user_input + category + mode + 每步状态
     贯穿全局，每步 LLM 都能看到

  ⑥ 执行
     serial → _run_serial（串行，前步输出经 Adapter 传下一步）
     parallel → _run_parallel（ThreadPoolExecutor 并行）

  ⑦ 汇总输出
     _summarize → 编排结果 + 每步状态 + 组合标签 + 工具标签
```

### 3.2 串行执行与步骤间适配（_run_serial）

```
_run_serial(subtasks, pm):
  prev_output = {}
  for i, st in enumerate(subtasks):
    step = pm.steps[i]
    tool = get_tool(st["tool"])

    ① 步骤间适配（Adapter）
       if tool and prev_output:
         adapted = adapter.adapt(prev_output, tool, pm)
           → can_accept？上一步输出的 key ⊇ 下一步工具的必填字段
           → 能直通 → 直接传递（prev_output）
           → 不能直通 → loop 回 Mapper 选适配组合 → Composer 执行适配
       else:
         step.input_data = {"query": st["desc"]}

    ② 选组合 + 设参（Mapper）
       combo, config = mapper.map(tool, st["desc"], pm)
         → LLM 填空选组合编号（1-14）→ PY 查表验证
         → 设参数 + output_limit（从 combo.output_limit 和配置合并）

    ③ PY 确定性组合（Composer）
       comp_result = composer.compose(combo.id, st["desc"], config)
         → exec_recipe(way_id, wc, user_input, chat)
         → 生成原子 → 后处理原子 → 校验原子 → 观测原子
         ↳ 不通过则 retry loop（最多 max_retry 次）

    ④ 调智能体（Executor）
       exec_input = comp_result.get("filled", step.input_data)
       exec_result = executor.execute(tool_name, exec_input, pm)
         → LLM 填空生成工具输入 JSON → HTTP POST 调智能体 API

    ⑤ 记录状态
       success → pm.mark_done(step_id, exec_result)
       failure → pm.mark_error(step_id, error)
       prev_output = exec_result  # 传下一步
```

### 3.3 并行执行（_run_parallel）

```
_run_parallel(subtasks, pm):
  ThreadPoolExecutor(max_workers=min(4, len(subtasks))):
    每子任务独立 _run_one：
      Mapper → Composer → Executor（无 Adapter，并行步无依赖）
    as_completed 收集结果 → pm.mark_done / mark_error
```

并行步之间无前步输出传递（无 Adapter），各步独立执行后汇总。

---

## 四、三层 loop 架构

### 4.1 retry loop — exec_recipe 内部（atoms.py:576）

```
exec_recipe(way_id, wc, user_input, chat):
  for attempt in range(max_retry + 1):     # ← retry loop
    ctx = AtomCtx(user_input, cfg, chat, attempt)
    GENERATORS[recipe.generate](ctx)        # LLM 填空生成
    for pp in recipe.postprocess:
      POSTPROCESSORS[pp](ctx)               # PY 后处理
    VALIDATORS[recipe.validate](ctx)        # PY 校验
    if ctx.valid or not recipe.retry:
      wr.filled = _filled_for(...)          # 通过 → 取结果
      break
  else:
    wr.exhausted = True                     # 耗尽 → 取最后一次
  for ob in recipe.observe:
    OBSERVERS[ob](ctx, wr, attempts)        # PY 观测
```

**retry 语义**：校验不通过时重试 LLM 生成（最多 max_retry 次），不是无限循环。每次重试 LLM 看到相同的 prompt，靠概率性生成尝试不同输出。`recipe.retry=False` 的组合（如 deterministic_pin）不重试——代码钉死后一次定论。

### 4.2 Adapter loop — 步骤间适配（adapter.py:20）

```
Adapter.adapt(prev_output, next_tool, pm):
  if next_tool.can_accept(prev_output.keys()):
    return prev_output                      # ← 直通（贯穿直通点）
  else:
    # ← loop 回 Mapper 选适配组合
    combo, config = mapper.map(next_tool, adapt_subtask, pm)
    result = composer.compose(combo.id, prev_text, config)
    return adapted_input
```

**Adapter loop 语义**：上一步输出不能直通下一步时，loop 回 Mapper 选一个适配组合，用 Composer 把上一步输出转换为下一步工具所需的输入格式。这是"递归自举"——编排器自身的前置规范也来自 14 种组合。

### 4.3 串行 loop — 子任务遍历（orchestrator.py:111）

```
_run_serial(subtasks, pm):
  for i, st in enumerate(subtasks):         # ← 串行 loop
    adapted = adapter.adapt(prev_output, tool, pm)
    combo, config = mapper.map(tool, st["desc"], pm)
    comp_result = composer.compose(combo.id, st["desc"], config)
    exec_result = executor.execute(tool_name, exec_input, pm)
    prev_output = exec_result               # 输出回传下一步
```

**串行 loop 语义**：子任务依次执行，每步输出经 Adapter 适配后传下一步。类似编程的 `for` 循环（次数固定=子任务数），轮间串行（依赖上一轮输出）。

---

## 五、前置规范 — 14 种穷举组合

### 5.1 组合分类

| 分类 | 编号 | 名称 | PY 范式 | 场景 |
|------|------|------|---------|------|
| **基础方式** | 1 | pure_guide | LLM生成→PY校验(约束) | 开放生成、续写、摘要 |
| | 2 | diverge_correct | LLM生成→PY后处理(正则)→PY校验(纠偏目标) | 创意生成、文案、扩写 |
| | 3 | deterministic_pin | LLM生成→PY后处理(钉死)→PY校验(封死目标) | 格式固定、编号重排 |
| | 4 | detect_report | LLM生成→PY后处理(检出)→PY校验(有检出即成功) | 数值核查、事实核查 |
| **值域限定** | 5 | enum_select | LLM生成(选词)→PY校验(集合内) | 分类、标注、情绪判断 |
| | 6 | condense_enum | LLM生成(凝练)→PY后处理(过滤)→PY校验(无编造) | 标签凝练、主题提取 |
| | 7 | slot_extract | LLM生成(填槽)→PY后处理(解析)→PY校验(无多余key) | 信息提取、结构化 |
| | 8 | required_min | LLM生成(填槽)→PY后处理(解析)→PY校验(必填齐全) | 表单填写、必填校验 |
| **复合后处理** | 9 | diverge_detect | LLM生成→PY后处理(纠偏+检出)→PY校验(有检出) | 创意+核查 |
| | 10 | diverge_condense | LLM生成→PY后处理(纠偏+过滤)→PY校验(无编造) | 创意+标签 |
| | 11 | detect_condense | LLM生成→PY后处理(检出+过滤)→PY校验(无编造) | 核查+标签 |
| **精确校验生成** | 12 | range_bound_gen | LLM生成(填槽)→PY后处理(解析)→PY校验(区间内) | 数值校验、范围检查 |
| | 13 | exact_match_gen | LLM生成(填槽)→PY后处理(解析)→PY校验(精确相等) | 精确提取、固定值 |
| | 14 | enum_filter_fabricate | LLM生成(选词)→PY后处理(过滤)→PY校验(无编造) | 分类+防编造 |

**穷举完备性**：当前原子库（3 生成 + 4 后处理 + 10 校验 + 6 观测）下穷举完，不存在第 15 种。每个组合 = Recipe（PY 确定性查表）+ output_limit + 场景标签。

### 5.2 Recipe 结构

```python
@dataclass
class Recipe:
    generate: str = "text"          # 生成原子：text / select / slot
    generate_arg: str = ""          # 生成参数：extra_check / required_min
    postprocess: list = []          # 后处理原子链：[deterministic, enum_filter, ...]
    validate: str = "none"          # 校验原子：in_set / no_extra / required_full / ...
    retry: bool = True              # 是否重试
    observe: list = []              # 观测原子：[hit, fabricated, extra_keys, ...]
```

执行顺序：`生成 → 后处理（链式）→ 校验 → 观测`。PY 部分确定性查表，只有生成那步是 LLM 概率填空。

### 5.3 前置规范 vs 后置验证

| 维度 | 前置规范（本系统） | 后置验证（传统） |
|------|-------------------|-----------------|
| **约束时机** | 生成前钉死格式/值域/槽位 | 生成后检查再修 |
| **LLM 自由度** | 填空（槽位已定义） | 自由生成后校验 |
| **失败处理** | retry loop（重新填空） | 后处理修复 |
| **确定性** | PY 后处理 + 校验 | LLM 自修复 |

---

## 六、原子库（atoms.py）

复用自 silprespec-emulator，为编排器提供原子化执行能力。

### 6.1 五类原子

| 类别 | 原子 | 数量 | 说明 |
|------|------|------|------|
| **生成** | text / select / slot | 3 | LLM 填空生成（自由文本 / 候选词选择 / 槽位填充） |
| **后处理** | deterministic / enum_filter / detect_report / json_parse | 4 | PY 确定性后处理（正则替换 / 枚举过滤 / 检出上报 / JSON 解析） |
| **校验** | in_set / no_extra / required_full / in_range / eq_exact / guide / diverge / deterministic / detect_report / none | 10 | PY 确定性校验 |
| **控制流** | retry | 1 | 校验不通过则重试 |
| **观测** | hit / fabricated / extra_keys / left_empty / flagged / changed | 6 | PY 确定性观测指标 |

### 6.2 通用执行器（exec_recipe）

```
exec_recipe(way_id, wc, user_input, chat):
  recipe = recipe_for(way_id) 或 wc.recipe（custom）
  for attempt in range(max_retry + 1):
    ctx = AtomCtx(...)
    GENERATORS[recipe.generate](ctx)         # 生成
    for pp in recipe.postprocess:
      POSTPROCESSORS[pp](ctx)                # 后处理链
    VALIDATORS[recipe.validate](ctx)         # 校验
    if ctx.valid or not recipe.retry: break
  for ob in recipe.observe:
    OBSERVERS[ob](ctx, wr, attempts)         # 观测
  return WayResult(filled, success, metrics)
```

---

## 七、工具接口规范（tool_registry.py）

### 7.1 三层泛化结构

```
ToolSpec（工具契约）
  ├── input_fields[]  → FieldSpec（每个输入字段）
  │     ├── name / type / required / default / description / example / options
  ├── output_fields[] → FieldSpec（每个输出字段）
  ├── examples[]      → ExampleSpec（引导示例）
  │     ├── title / input / output / explanation
  ├── internal_prespec[]  → 内部前置规范链（如 路由→检索→重排序→NLI→生成）
  ├── capabilities[]      → 能力标签
  └── limitations[]       → 局限标签
```

### 7.2 已注册三智能体

| 工具 | 端口 | 接口 | 内部前置规范 |
|------|------|------|-------------|
| **rag-assistant** | 8767 | `/api/kb/query` | 路由 → 向量检索 → 重排序 → NLI验证 → 提示词模板 |
| **structured-writer** | 8770 | `/api/write` | 模板选择 → 大纲规划 → 逐段生成 → 引用后处理 → RAG素材检索 |
| **silprespec-emulator** | 8789 | `/api/emulate` | 原子库(10原子) → Recipe配方 → 14种穷举组合 → 验证指标 |

### 7.3 直通判定（can_accept）

```python
def can_accept(self, available_keys: list) -> bool:
    required = [f.name for f in self.input_fields if f.required]
    return all(r in available_keys for r in required)
```

上一步输出的 key 包含下一步工具的所有必填字段 → 直通；否则 → Adapter loop 回 Mapper 选适配组合。

---

## 八、组件详解

### 8.1 Mapper — 选组合 + 设参（mapper.py）

```
Mapper.map(tool, subtask, progress_map):
  ① 选组合（LLM 填空 + PY 查表验证）
     prompt = "为子任务选最合适的前置规范组合（只输出编号 1-14）"
     out = llm.chat(prompt, max_tokens=10, temperature=0.1)
     → 提取数字 → get_combo(id) → PY 查表验证存在
     → 失败回退为 combo[0]（pure_guide）

  ② 设参 + output_limit
     config = default_config(combo.way_id)
     合并 combo.output_limit 和配置的 output_limit_cfg
     → max_length → 写入 output_constraints
     → max_fields → 截断 slots
```

**LLM 只填空选编号**，不决定流程。PY 查表验证编号合法，失败回退为最安全的纯引导。

### 8.2 Composer — PY 确定性组合（composer.py）

```
Composer.compose(combo_id, user_input, config):
  combo = get_combo(combo_id)               # PY 查表
  wc = WayConfig(way=combo.way_id, config=config)
  result = exec_recipe(combo.way_id, wc, user_input, chat)
  return result.to_dict()
```

**零 LLM 决策**。Composer 只做 PY 查表 + 调 exec_recipe。LLM 填空发生在 exec_recipe 内部的生成原子。

### 8.3 Executor — LLM 填空 + 调智能体（executor.py）

```
Executor.execute(tool_name, input_data, progress_map):
  ① 构造提示词
     prompt = 进度地图 + 目标工具 + 工具说明 + 输入要求 + 输出格式 + 当前输入数据
     → "请生成调用该工具所需的输入参数（JSON）"

  ② LLM 填空生成工具输入
     llm_out = llm.chat(prompt, max_tokens=800, temperature=0.3)
     tool_input = parse_json(llm_out)       # 提取 JSON

  ③ HTTP 调智能体 API
     POST tool.url + tool.endpoint → 返回工具输出
```

### 8.4 Adapter — 步骤间适配（adapter.py）

```
Adapter.adapt(prev_output, next_tool, progress_map):
  if next_tool.can_accept(prev_output.keys()):
    return prev_output                      # ← 贯穿直通
  else:
    # ← loop 回 Mapper
    adapt_subtask = "把上一步输出适配为 {tool} 所需的输入格式"
    combo, config = mapper.map(next_tool, adapt_subtask, pm)
    result = composer.compose(combo.id, prev_text, config)
    return adapted_input
```

**贯穿直通点**：上一步输出的 key ⊇ 下一步工具必填字段时，直接传递，零 LLM 调用。否则 loop 回 Mapper 选适配组合，用 Composer 执行格式转换。

---

## 九、进度地图（progress_map.py）

### 9.1 输入分类（穷举 6 类别）

| 类别 | 说明 |
|------|------|
| extract | 信息提取（实体/关系/属性） |
| generate | 内容生成（文案/文章/摘要） |
| analyze | 分析推理（比较/评估） |
| verify | 数据核查（数值/事实/合规） |
| transform | 格式转换（重构/翻译） |
| orchestrate | 多步编排（复杂任务） |

LLM 填空分类（只输出类别 id）→ PY 查表映射。失败回退为 orchestrate。

### 9.2 编排模式（穷举 3 模式）

| 模式 | 触发条件 | 说明 |
|------|---------|------|
| serial | num_steps ≤ 1 / generate / analyze / 默认 | 串行，前步输出传下一步 |
| parallel | extract / transform / verify | 并行，ThreadPoolExecutor |
| loop | （预留） | 循环，每轮结果回传 |

### 9.3 ProgressMap

```python
@dataclass
class ProgressMap:
    user_input: str              # 完整用户初始输入（贯穿全局）
    category: str                # 输入分类
    orchestration_mode: str      # 编排模式
    steps: list[StepStatus]      # 每步状态
    completed: list              # 已完成步骤
```

每步 LLM 都通过 `progress_map.summary()` 看到全局进度，不盲目执行。

---

## 十、Web UI 架构

### 10.1 HTTP 服务器

基于 Python 标准库 `http.server`，零外部依赖。端口 8789。

| 路由 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 主页面（static/index.html） |
| `/static/*` | GET | 静态资源（CSS/JS） |
| `/api/combos` | GET | 列出 14 种组合 |
| `/api/tools` | GET | 列出已注册工具（含完整 ToolSpec） |
| `/api/config` | GET | 获取配置 |
| `/api/llm/models` | GET | 列出 LLM 可用模型 |
| `/api/llm/test` | GET | 测试 LLM 连接 |
| `/api/config` | POST | 保存配置到文件 + 更新内存 |
| `/api/run` | POST | 执行编排 |

### 10.2 四 Tab 布局

| Tab | 功能 |
|-----|------|
| **编排** | 任务输入 + 工具勾选 + 执行编排 + 结果展示 |
| **组合** | 14 种穷举组合表格（编号/名称/描述/方式/场景/输出限制）+ 点击查看 Recipe |
| **工具** | 三智能体完整接口契约（输入字段/输出字段/引导示例/能力/局限/内部前置规范） |
| **配置** | LLM 后端选择 / 模型下拉 / 测试连接 / 超时+MaxTokens / 编排参数 / 保存配置 |

### 10.3 样式统一

深色 Tab 栏 `#2d2d44` + 主色 `#667eea`，与 Orchestrator/rag-assistant/structured-writer 统一。

---

## 十一、LLM 客户端（llm_client.py）

基于纯 `urllib` 的 OpenAI 兼容客户端，支持多后端：

| 后端 | 地址 | 模型发现 |
|------|------|---------|
| LM Studio | `http://localhost:1234/v1` | `/v1/models` |
| Ollama | `http://localhost:11434` | `/api/tags` |
| 自定义 | 任意 OpenAI 兼容 | `/v1/models` |

统一接口：`chat` / `chat_detailed` / `test_connection` / `list_models`（30 秒缓存）。

---

## 十二、配置系统

### 12.1 配置文件（config.json）

```json
{
  "llm": {
    "backend": "lm-studio",
    "base_url": "http://localhost:1234",
    "model": "qwen/qwen3.6-35b-a3b",
    "api_key": "not-needed",
    "timeout": 180,
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "orchestrator": {
    "max_steps": 20,
    "max_retry": 3,
    "verbose": true,
    "output_limit": {
      "soft_guide_max_length": 500,
      "diverge_correct_max_length": 800,
      "slot_extract_max_fields": 5
    }
  },
  "combos": {
    "default_output_limit": { "max_length": 500, "max_fields": 5 }
  }
}
```

### 12.2 配置优先级

```
CLI 参数 > config.json > DEFAULT_CONFIG（main.py 常量）
```

### 12.3 配置持久化链路

```
界面保存 → POST /api/config → 合并到 server.config → 落盘 config.json
→ 下次启动 load_config 读取 → make_llm 从配置构造 LLMClient
```

工具配置由 `tool_registry.py` 的 `_init_default_tools()` 硬编码注册（含完整 FieldSpec/ExampleSpec），不从 config.json 读取。

---

## 十三、CLI 接口

```
python main.py --web                   # Web UI（主模式，默认 8789）
python main.py --query "分析这份报告"   # 单次任务执行
python main.py --check                 # 检测 LLM 连接
python main.py --list-combos           # 列出 14 种穷举组合
python main.py --list-tools            # 列出已注册工具
python main.py --backend ollama        # 切换 Ollama 后端
python main.py --port 8789             # 指定端口
```

---

## 十四、数据流总览

```
用户输入 "分析茅台酒工艺并写报告"
  │
  ├─ classify_input → ("analyze", "分析推理")
  ├─ _decompose → [
  │    {"name":"查询工艺", "desc":"茅台酒制作工艺", "tool":"rag-assistant"},
  │    {"name":"写报告", "desc":"基于工艺写分析报告", "tool":"structured-writer"}
  │  ]
  ├─ select_orchestration_mode → "serial"
  ├─ ProgressMap(user_input, "analyze", "serial", 2 steps)
  │
  ├─ Step 0: 查询工艺
  │    ├─ Adapter: 无前步 → input_data = {"query": "茅台酒制作工艺"}
  │    ├─ Mapper: LLM 选组合[1] pure_guide → config = {guide_prompt, output_constraints}
  │    ├─ Composer: exec_recipe("pure_guide", ...) → LLM 填空生成 → PY 校验
  │    ├─ Executor: LLM 填空生成工具输入 → POST rag-assistant:8767/api/kb/query
  │    └─ prev_output = {answer, docs, summary, sources}
  │
  ├─ Step 1: 写报告
  │    ├─ Adapter: can_accept? {answer,docs,...} ⊇ {topic, template}?
  │    │    → 不能直通 → loop 回 Mapper 选适配组合
  │    │    → Composer 把 {answer, docs} 适配为 {topic, template, material}
  │    ├─ Mapper: LLM 选组合[1] pure_guide → config
  │    ├─ Composer: exec_recipe → LLM 填空生成
  │    ├─ Executor: LLM 填空生成工具输入 → POST structured-writer:8770/api/write
  │    └─ prev_output = {article, outline, references}
  │
  └─ _summarize → 编排结果 + 每步状态 + 组合标签 + 工具标签
```