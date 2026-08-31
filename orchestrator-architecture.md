<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
Licensed under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0).
See https://creativecommons.org/licenses/by-sa/4.0/ for details.
-->

# Orchestrator 架构文档 — v2.8.1

> 链驱动技能编排器 — 人工编排 Pipeline，LLM 只做两头（前处理 + 输出整理），中间由 subprocess 确定性执行技能脚本。
> 作者：wUwproject | 许可证：Apache 2.0
> 更新：2026-08-07

---

## 一、系统概览

Orchestrator 是一个**链驱动技能编排器**，核心理念：**LLM 只做两头，中间是死的**。

```
用户编排 Pipeline（Pipeline Tab）→ 选择链 + 任务描述 + 上传数据（对话 Tab）
  → Round 1：需求分析（LLM + 16 工具，按用户提示词前处理）
    → Round 2：（可选）skill-sub 优化（衔接兼容性检查）
      → Round 3+：死执行（subprocess 跑 skill 脚本，LLM 不参与）
        → 最终输出整理（LLM 按用户提示词整理交付）
```

**Orchestrator 不是聊天工具。** 没有选链就没有对话——普通对话（ReAct）已在 v2.8.0 彻底移除。

### 1.1 核心设计原则

| 原则 | 说明 |
|------|------|
| **链是主体** | 没有链就没有对话。Pipeline 编辑器是主界面，对话区是执行结果展示 |
| **LLM 只做两头** | LLM 出现在需求分析（前处理）与最终输出整理，**不干预链执行** |
| **中间是死的** | 链执行 = subprocess 真跑 skill 脚本，确定性、可复现、可审计 |
| **skill 是原子池** | 每个技能可拆解为可执行原子（CLI/脚本/子步骤），编排 = 挑原子组链 |
| **编排器不替 skill 干活** | skill 自带领域能力（如 RAG 检索在 local-rag-builder 自己的 rag_core.py），编排器只提供通用衔接工具 |
| **纯提示词 skill 不编排** | 无可执行脚本入口的技能直接过滤，不进入 Pipeline 列表 |
| **配置可调** | 超时/max_tokens 从 settings.json 读取，非硬编码 |

### 1.2 与 v2.0 的关键差异

| 维度 | v2.0（LLM 编输出） | v2.8（真执行 + LLM 两头） |
|------|-------------------|--------------------------|
| **执行机制** | 每步 `llm.chat()` 编输出 | **subprocess 真跑 skill 脚本**（chain_engine `_run_script`） |
| **LLM 角色** | 步骤执行器 | **前处理 + 输出整理**，中间不碰 |
| **普通对话** | 无链时回退 ReAct | **已彻底移除**，无链直接拒绝 |
| **工具** | 7 个 | **16 个**（+文件操作 6 + 数据工具 3） |
| **技能过滤** | 全部显示 | **可执行过滤**（有主脚本入口才显示，32 个） |
| **loop** | 输出不回传（假循环） | **输出回传**（每轮结果喂下一轮） |
| **输入通道** | 仅文本 | **对话框纯文本 + 上传通道**（/api/upload） |
| **端口** | 8765/8766 | **8788**（避 RAG 8765-8767、写作 8770/8777） |

---

## 二、双入口架构

```
Orchestrator/
├── main.py                    # CLI 入口（Web UI/批处理/管道）
├── orchestrator/               # Python 包
│   ├── __init__.py            # 导出 + 版本唯一源（__version__）
│   ├── web_ui.py              # Web UI 服务器 + 前端内嵌 HTML
│   ├── agent_loop.py          # ORCHESTRATOR_SYSTEM_PROMPT（编排器本体提示词，非 ReAct）
│   ├── chain_engine.py        # 真执行引擎（_run_script subprocess）
│   ├── chain_model.py         # 数据模型
│   ├── skill_scanner.py       # SKILL.md 扫描器
│   ├── agent_config.py        # 配置管理
│   ├── llm_client.py          # LLM 通信（OpenAI 兼容，多后端）
│   ├── direct_llm_client.py   # GGUF 直载（CLI 用）
│   ├── model_manager.py       # 模型管理
│   ├── memory.py              # 记忆系统
│   ├── static/web_ui.js       # 前端 JS
│   ├── chains/                # 已保存 Pipeline
│   └── tools/                 # 16 个工具（4 模块）
├── data/config/settings.json  # 配置（唯一生效文件）
├── input/                     # 上传文件落盘目录
├── archive/                   # 归档（tkinter gui_agent 等死代码）
├── PROTOCOL.md                # 接口契约
├── README.md                  # 使用手册
├── setup.bat                  # 一键启动（固定 8788）
└── requirements.txt           # 依赖
```

### 2.1 Web UI 模式（主）

```
python main.py --web        # 默认 8788
setup.bat                   # 一键启动（安装依赖 + 启动 + 自动开浏览器）
```

三 Tab：

| Tab | 功能 |
|-----|------|
| **对话** | 选链 + 任务描述 + 上传文件 → 需求分析 → (skill-sub) → 死执行 → 输出整理 |
| **配置** | LLM 后端 / 提示词（系统只读 + 用户提示词）/ 技能路径 |
| **Pipeline** | 可视化 seq/par/loop 编排器（只显示可执行技能） |

### 2.2 批处理 / 管道模式

```
python main.py --batch input.json output.json   # JSON 批处理（真执行）
cat queries.jsonl | python main.py --jsonl       # JSONL 管道（真执行）
```

批处理/管道走 chain_engine 真执行（subprocess 跑技能脚本），LLM 不可用时降级为步骤规划输出。

---

## 三、Web UI 架构

### 3.1 HTTP 服务器

基于 Python 标准库 `http.server.BaseHTTPRequestHandler`，零外部依赖。**ThreadingTCPServer + daemon_threads**（单线程会阻塞全站，已修）。

| 路由 | 方法 | 功能 |
|------|------|------|
| `/` | GET | Web UI 主页面（HTML 内联） |
| `/static/` | GET | 静态资源（web_ui.js、marked.min.js 本地化） |
| `/api/chat` | GET/POST | 链驱动执行（无 pipeline 拒绝）/ 配置重置 |
| `/api/config` | GET/POST | 配置读写（落盘 settings.json，联动 agent.llm） |
| `/api/skills` | GET | 技能列表（**只显示可执行技能**） |
| `/api/llm/models` | GET | 可用模型列表 |
| `/api/llm/test` | POST | LLM 连通性测试 |
| `/api/pipelines` | GET/POST | Pipeline 列表 / 保存 |
| `/api/pipelines/run` | POST | 执行 Pipeline（真执行） |
| `/api/pipelines/delete` | POST | 删除 Pipeline |
| `/api/upload` | POST | 文件上传（base64 → input/，路径穿越净化/50MB/重名序号） |

### 3.2 对话四阶段（LLM 只做两头）

```
Round 1 — 需求分析（前处理）
  LLM(用户任务 + user_prompt + 16 工具清单 + 附件路径)
  → 用工具处理数据（db_query/read_table/image_info），产出最小中间输入
  ↓
Round 2 — skill-sub 优化（可选，勾选开启）
  衔接兼容性检查 → 黏连转换 → 里程碑标记
  ↓
Round 3+ — 死执行
  subprocess 跑 skill 脚本（params → CLI 参数，前步输出 → stdin/下一步输入）
  LLM 不参与，结果原样
  ↓
Round 4 — 最终输出整理（输出侧）
  LLM 按 user_prompt 整理交付（Markdown/表格/文件路径）
  明确：不保证完全按提示词——Pipeline 已产最终形态则如实呈现
```

### 3.3 用户提示词的语义（v2.7.0 定稿）

> **用户提示词 = 你对"理解任务"和"呈现结果"的偏好，不干预链的执行细节。**

- **输入侧**：注入需求分析 prompt（前处理偏好：怎么理解任务、怎么处理数据）
- **输出侧**：注入最终输出整理 prompt（格式偏好：Markdown/表格/简洁）
- **中间执行**：不注入（skill 脚本是死的，提示词插进去也没用）

### 3.4 Pipeline 编辑器

三栏布局，**左侧技能列表只显示可执行技能**（有主脚本入口，32 个）：

| 操作 | 说明 |
|------|------|
| **双击左侧技能** | 添加到画布（seq 模式） |
| **点 +并行组** | 创建 par 容器（ThreadPoolExecutor 真并发） |
| **点 +循环组** | 创建 loop 容器（for 真循环，输出回传） |
| **双击节点** | 编辑参数（params → CLI 参数） |
| **右键模式切换** | seq/par/loop 切换 |
| **保存** | 模态框输入名称 → chains/{name}.json |
| **运行** | 发送到后端真执行引擎 |

---

## 四、执行引擎（真执行）

### 4.1 链执行（_execute_tree）

核心执行函数，支持三种模式，**全部 subprocess 真执行**：

```
_execute_tree(nodes, output, depth, step_counter, prev_output):
  for node in nodes:
    if mode == "seq":
      result = _run_skill_node(name, params, prev_output)  # subprocess
      prev_output = result  # 传递下一步
    elif mode == "par":
      ThreadPoolExecutor:   # 真并发
        for child in children: executor.submit(_run_skill_node, ...)
    elif mode == "loop":
      for t in range(times):  # for 真循环，每轮结果回传下一轮
        last_result = _execute_tree(children, ..., prev_output=loop_input)
        loop_input = last_result  # 输出回传（v2.4.0 修复）
```

**loop 语义澄清**：loop 是"链上这一段子步骤按固定次数重复执行，每次把结果喂给下一次"——类似编程的 `for` 循环（次数固定、无决策），**不是** agent 式 `while` 自适应循环（模型决定何时停）。loop 与 par 正交可嵌套：loop 每轮内部可并行，轮间串行（依赖上一轮输出）。

### 4.2 单技能执行（_run_skill_node → chain_engine）

```
1. _find_skill_dir(name)             # 找技能目录（<skills>/，随宿主平台安装位置而定）
2. _get_skill_scripts(sdir)          # 收集 scripts/ 下可执行脚本
3. _get_main_script(name, scripts)   # 入口匹配（下划线/连字符归一化 + main/cli/run 标准入口 + 排除纯配置脚本）
4. _run_script(main, cli_args, ...)  # subprocess 真跑
   - node.params → CLI 参数（command/args/--key value）
   - 前步输出 → stdin 传入
   - 捕获 stdout/stderr，超时返回 [超时]
```

**入口匹配规则（v2.5.0 定稿）**：
- 技能名下划线/连字符归一化匹配（`workday-calendar` ↔ `workday_calendar.py`）
- 标准入口名：`main.py` / `run.py` / `index.py` / `cli.py`
- **排除纯配置脚本**：`settings.py` / `config.py` / `__init__.py` / `_paths.py` 不算入口
- 其余任意 .py/.sh/.bat 都算可执行入口

**当前可编排技能**：32 个（66 个技能中过滤掉无入口的）。

### 4.3 skill-sub 优化

算法主导的链分析（非 LLM 自由发挥）：

```
1. 读 SKILL.md → 提取 tags/triggers/description
2. 算法规则比较步骤间输入输出兼容性
   - 不兼容 → 插入转换步骤
   - 兼容 → 直接传递
3. LLM 模糊回退（仅当算法无法确定时）
4. 里程碑自动标记
```

---

## 五、数据模型

### 5.1 PipelineNode（chain_model.py）

```python
@dataclass
class PipelineNode:
    id: str               # UUID hex[:8]
    skill_name: str       # 技能 slug
    display_name: str     # 显示名称
    mode: str             # seq | par | loop
    children: list        # 子节点
    loop_times: int       # 循环次数
    input_text: str       # 用户输入
    params: dict          # 技能参数（→ CLI 参数）
    extra: dict           # skill-sub 优化数据（黏连点/里程碑）
```

### 5.2 保存格式（chains/{name}.json）

```json
{
  "name": "my-pipeline",
  "nodes": [...],       // 扁平化节点
  "tree": [...]         // 完整树结构（含 params/extra）
}
```

---

## 六、LLM 客户端

### 6.1 架构

基于纯 `urllib` 的 OpenAI 兼容客户端，支持多后端：

| 后端 | 地址 |
|------|------|
| LM Studio | `http://localhost:1234/v1` |
| Ollama | `http://localhost:11434/v1` |
| OpenAI 兼容 | 自定义 |

### 6.2 关键配置（data/config/settings.json，唯一生效）

```
llm.backend:      lmstudio
llm.base_url:     http://localhost:1234/v1
llm.model_name:   qwen/qwen3.5-35b-a3b   # 配置持久化，启动不再被硬编码覆盖（v2.5.0 修复）
llm.timeout:      1800 秒（链步执行超时）
llm.max_tokens:   40960（每步最大输出）
```

---

## 七、工具系统（16 个）

**分工原则**：skill 自带领域能力（RAG 检索、颜色计算、工作日历都在 skill 自己的 scripts/ 里），编排器只提供**通用衔接工具**。

| 模块 | 工具 | 用途 |
|------|------|------|
| file_tool.py | read_file / write_file / list_directory | 基础文件读写 |
| file_ops_tool.py | copy_file / move_file / delete_file / append_file / make_dir / find_files | **链中间产物流转**（v2.3.0 新增，安全校验：空路径/系统目录/根路径拦截） |
| web_tool.py | web_fetch / web_search / python_execute | 网络 + 代码执行 |
| data_tool.py | db_query / read_table / image_info | **前处理防 token 爆炸**（v2.7.0 新增：SQLite 查询写拦截/csv/xlsx 摘要/图片元数据） |
| skill_loader.py | load_skill | 加载技能定义 |

**前处理阶段**：LLM 通过 `_tools_summary` 注入 16 工具清单，先调工具取必要信息（不整读大文件/数据库）。

---

## 八、配置系统

### 8.1 配置文件（data/config/settings.json）

```json
{
  "llm": { "backend": "lmstudio", "base_url": "http://localhost:1234/v1",
           "model_name": "qwen/qwen3.5-35b-a3b", "timeout": 1800, "max_tokens": 40960 },
  "agent": { "max_steps": 20, "verbose": true },
  "search": { "backend": "duckduckgo", "presets": [] },
  "prompt": { "user": "" },
  "skills": { "dirs": [] }
}
```

**配置持久化链路**：界面保存 → 落盘 settings.json → `_recreate_llm` 联动 agent.llm → 重启后 make_llm 优先用配置值（不硬编码覆盖）。

### 8.2 提示词

| 提示词 | 状态 | 说明 |
|--------|------|------|
| **系统提示词** | 只读 | `ORCHESTRATOR_SYSTEM_PROMPT`（编排器本体：LLM 只做前处理+输出整理，非聊天机器人） |
| **用户提示词** | 可编辑 | 仅作用于前处理与输出格式，不干预 Pipeline 执行 |

---

## 九、CLI 接口

```
python main.py --web                   # Web UI（主模式，默认 8788）
python main.py --batch in.json out.json # 批处理（真执行）
python main.py --jsonl                  # 管道模式（真执行）
python main.py --port 8788              # 指定端口
```

---

## 十、演变路线

| 阶段 | 状态 | 内容 |
|------|------|------|
| v1.0-v1.2 | 完成 | ReAct 初始架构 → Skill Pipeline 基础编排 |
| **v2.0** | 完成 | 链驱动架构重塑：Web UI / 真并行循环 / skill-sub / PROTOCOL |
| v2.1 | 完成 | 致命缺陷修复：双响应崩溃 / 假执行 / 配置加载 / CDN / 单线程 |
| v2.2 | 完成 | 端口 8788 / setup.bat 重写 / 归档 tkinter |
| v2.3 | 完成 | **链执行真执行化**（subprocess）+ 6 文件工具 + 编排过滤 |
| v2.4 | 完成 | loop 真循环（输出回传）+ 技能入口过滤 |
| v2.5 | 完成 | 配置持久化 / 会话历史 / 系统提示词真实化 / 技能 9→32 |
| v2.6 | 完成 | **文件上传通道**（对话框纯文本 + 数据走上传） |
| v2.7 | 完成 | **LLM 只做两头** + 3 数据工具（防 token 爆炸） |
| v2.8 | 完成 | **彻底移除普通对话**，编排器定位纯化 + 文档补齐 |
| v2.9+ | 规划 | 跨链状态共享、分支条件、循环变量 |

---

## 十一、目录结构（agent/Orchestrator/）

```
agent/Orchestrator/
├── main.py               # CLI 入口
├── orchestrator/          # Python 包
│   ├── __init__.py        # 导出 + __version__ 唯一源
│   ├── agent_loop.py      # ORCHESTRATOR_SYSTEM_PROMPT（编排器本体提示词）
│   ├── agent_config.py    # 配置管理
│   ├── chain_engine.py    # 真执行引擎（subprocess）
│   ├── chain_model.py     # 数据模型
│   ├── memory.py          # 记忆系统
│   ├── llm_client.py      # LLM 通信
│   ├── direct_llm_client.py # GGUF 直载（CLI）
│   ├── model_manager.py   # 模型管理
│   ├── skill_scanner.py   # 技能扫描
│   ├── web_ui.py          # Web UI 服务器
│   ├── static/web_ui.js   # 前端 JS
│   ├── chains/            # 已保存 Pipeline
│   └── tools/             # 16 工具（file/file_ops/web/data/skill_loader）
├── data/config/settings.json  # 配置
├── input/                 # 上传文件
├── archive/               # 归档死代码
├── PROTOCOL.md            # 接口文档
├── README.md              # 使用手册
├── setup.bat              # 一键启动
└── requirements.txt       # 依赖
```
