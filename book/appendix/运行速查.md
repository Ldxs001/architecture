<!--
SPDX-License-Identifier: CC-BY-SA-4.0
Copyright (c) 2026 wUwproject
-->

# 附录 B：运行速查

> 七个系统的运行方式完全不同：**技能**由宿主平台加载（无独立进程，跨平台分发）；**编排器与智能体**是独立程序（main.py 起进程、占端口、带 Web UI）。下表全部为真实代码核实（2026-08-31）。

## 一、技能（宿主平台加载，无端口）

| 系统 | 位置 | 版本 | 运行方式 |
|------|------|------|---------|
| skill-standardization | `maby_skills/skill-standardization/` | 2.103.0 | 宿主平台按 SKILL.md 触发（audit/create/update/refactor/bump/readonly 六模式） |
| semantic-split | `maby_skills/semantic-split/` | 3.1.1 | 宿主平台按 SKILL.md 触发（语义拆分 → 结构化规划单元） |
| activity-duration-estimation | `maby_skills/activity-duration-estimation/` | 1.11.7 | 宿主平台按 SKILL.md 触发（WBS 分解 + 三点估算/蒙特卡洛） |

技能发布于 maby_skills 仓库（`<skills>/` 为任意宿主平台安装后的目录）；技能的"运行"= 宿主平台读取 SKILL.md 后按声明调用 `scripts/` 脚本；也可被编排器（orchestrator）以 **subprocess** 直接跑脚本。

## 二、编排器（独立进程 + Web UI）

| 系统 | 位置 | 版本 | 运行方式 |
|------|------|------|---------|
| orchestrator（第 I 代） | `maby_agent/Orchestrator/` | 2.8.1 | `python main.py`（Web UI 端口 8788，支持 `--port auto`；LLM 后端 `--backend custom --base-url ...`） |
| silprespec-orchestrator（第 II 代，实验） | 独立仓库 `silprespec-orchestrator/` | 0.1.0 | `python main.py --web`（Web UI 端口 8789）；依赖外部 LLM 后端（LM Studio / Ollama / OpenAI 兼容 API） |

## 三、智能体（独立 HTTP 服务，maby_agent 仓库）

| 系统 | 位置 | 版本 | 运行方式 |
|------|------|------|---------|
| rag-assistant | `maby_agent/rag-assistant/` | 2.4.1 | `python main.py`（Web 界面 8765；外部 API `--api-port` 指定即启动，如 8767） |
| structured-writer | `maby_agent/structured-writer/` | 3.1.8 | `python main.py`（Web UI 8770；外部 API `--api-port` 指定，如 8777） |

## 四、调用关系速记

- orchestrator ──subprocess──→ **技能**（可执行过滤后的技能池）
- silprespec-orchestrator ──HTTP──→ **智能体 API**（rag-assistant / structured-writer）
- skill-standardization ──审计──→ 其他所有技能与智能体的文档规范（元层，不参与业务调用）

## 五、演进收束篇（架构 08）

架构 08 为纯论述篇（非系统），**无运行实体**——它把编排器两代的变化线（对象/通道迁移、表象 vs 内核、"圈"的 z 轴）立成专文，运行形态以架构 06（orchestrator）与架构 07（silprespec-orchestrator）为准。
