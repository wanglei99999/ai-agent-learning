# AI Agent 学习笔记

学习 LangChain、LangGraph 等 AI Agent 开发框架的笔记和示例代码。

## 目录结构

```
├── langchain/                  # LangChain 学习笔记
│   ├── docs/                   # 文档 (01-19)
│   ├── data/                   # 示例数据
│   └── examples/               # 示例代码
├── langgraph/                  # LangGraph 学习笔记
│   ├── docs/                   # 文档 (01-18)
│   ├── data/                   # 数据
│   ├── examples/               # 示例代码
│   └── projects/               # 项目实践
├── hello_agent/                # 从零实现 Agent 框架
│   ├── core/                   # 核心组件（LLM、工具执行器）
│   ├── agents/                 # Agent 实现
│   │   ├── react/              # ReAct Agent
│   │   └── plan_solve/         # Plan-Solve Agent
│   ├── tools/                  # 工具库（搜索等）
│   └── examples/               # 运行示例
├── .env.example                # 环境变量模板
└── README.md
```

## 学习路线

### LangChain

#### 基础篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 01 | [环境搭建](./langchain/docs/01-环境搭建.md) | uv、VSCode、依赖安装 |
| 02 | [Agent 核心概念](./langchain/docs/02-Agent核心概念.md) | Model、Tools、System Prompt |
| 03 | [快速入门完整示例](./langchain/docs/03-快速入门完整示例.md) | 完整天气查询 Agent |
| 04 | [Agent 详解](./langchain/docs/04-Agent详解.md) | ReAct、调用方式、状态管理 |
| 05 | [Models 详解](./langchain/docs/05-Models详解.md) | 模型初始化、调用、工具绑定 |
| 06 | [Messages 详解](./langchain/docs/06-Messages详解.md) | 消息类型、多模态、内容块 |
| 07 | [Tools 详解](./langchain/docs/07-Tools详解.md) | 工具定义、ToolRuntime、状态访问 |

#### 核心功能篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 08 | [记忆系统详解](./langchain/docs/08-记忆系统详解.md) | 短期记忆（State）+ 长期记忆（Store） |
| 09 | [输出控制详解](./langchain/docs/09-输出控制详解.md) | 流式输出 + 结构化输出 |
| 10 | [中间件详解](./langchain/docs/10-中间件详解.md) | 钩子、内置中间件、自定义中间件 |
| 11 | [Guardrails](./langchain/docs/11-Guardrails.md) | 确定性/模型护栏、输入/输出过滤 |
| 12 | [Runtime 详解](./langchain/docs/12-Runtime详解.md) | Runtime、Context、State、Store |
| 13 | [上下文工程详解](./langchain/docs/13-上下文工程详解.md) | 模型/工具/生命周期上下文 |
| 14 | [MCP 详解](./langchain/docs/14-MCP详解.md) | Model Context Protocol、远程工具 |
| 15 | [HITL 详解](./langchain/docs/15-HITL详解.md) | Human-in-the-Loop（人在回路） |

#### 多 Agent 架构篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 16 | [多 Agent 架构详解](./langchain/docs/16-多Agent架构详解.md) | Subagents、Handoffs、Skills、Router、自定义工作流 |

#### LangSmith 工具链篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 17 | [LangSmith 工具链详解](./langchain/docs/17-LangSmith工具链详解.md) | Studio、测试、Chat UI、部署、可观测性 |

#### RAG 与实践篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 18 | [RAG 检索详解](./langchain/docs/18-RAG检索详解.md) | 检索增强生成、2-Step/Agentic/Hybrid RAG |
| 19 | [Deep Research 实践](./langchain/docs/19-Deep%20Research实践.md) | 深度研究 Agent 实战 |

### LangGraph

| 章节 | 内容 | 说明 |
|------|------|------|
| 01 | [LangGraph 概述](./langgraph/docs/01-LangGraph概述.md) | 定位、核心能力、生态 |
| 02 | [快速入门](./langgraph/docs/02-快速入门.md) | Graph API 与 Functional API 两种方式 |
| 03 | [本地服务器](./langgraph/docs/03-本地服务器.md) | 本地开发与调试 |
| 04 | [LangGraph 思维方式](./langgraph/docs/04-LangGraph思维方式.md) | 设计原则与建模方式 |
| 05 | [工作流与 Agent 模式](./langgraph/docs/05-工作流与Agent模式.md) | 常见架构模式 |
| 06 | [持久化详解](./langgraph/docs/06-持久化详解.md) | Checkpointer、状态持久化 |
| 07 | [持久执行详解](./langgraph/docs/07-持久执行详解.md) | Durable Execution |
| 08 | [流式输出详解](./langgraph/docs/08-流式输出详解.md) | stream/astream |
| 09 | [中断机制详解](./langgraph/docs/09-中断机制详解.md) | interrupt / resume |
| 10 | [Time Travel](./langgraph/docs/10-Time%20Travel.md) | 状态回溯与调试 |
| 11 | [记忆系统详解](./langgraph/docs/11-记忆系统详解.md) | 短期+长期记忆 |
| 12 | [子图详解](./langgraph/docs/12-子图详解.md) | 复用与模块化 |
| 13 | [应用结构详解](./langgraph/docs/13-应用结构详解.md) | 项目组织方式 |
| 14 | [测试详解](./langgraph/docs/14-测试详解.md) | 测试策略 |
| 15 | [API 选择指南](./langgraph/docs/15-API选择指南.md) | Graph vs Functional |
| 16 | [Graph API 完整指南](./langgraph/docs/16-Graph%20API完整指南.md) | Graph API：理论 + 实践 |
| 17 | [Functional API 完整指南](./langgraph/docs/17-Functional%20API完整指南.md) | Functional API：理论 + 实践 |
| 18 | [Runtime 详解](./langgraph/docs/18-Runtime详解.md) | Pregel 运行时底层 |

### Hello Agent（从零实现）

手写 Agent 框架，深入理解 Agent 工作原理。

| 组件 | 说明 |
|------|------|
| [ReAct Agent](./hello_agent/agents/react/) | 实现 Thought → Action → Observation 循环 |
| [Plan-Solve Agent](./hello_agent/agents/plan_solve/) | 实现"先规划、再执行"架构 |
| [核心组件](./hello_agent/core/) | LLM 客户端、工具执行器 |
| [工具库](./hello_agent/tools/) | 搜索工具等 |

**运行示例：**
```bash
# ReAct Agent
python hello_agent/examples/run_react_agent.py

# Plan-Solve Agent
python hello_agent/examples/run_plan_solve_agent.py
```

详见 [hello_agent/README.md](./hello_agent/README.md)

## 核心概念速查

| 概念 | 说明 |
|------|------|
| Agent | 大模型 + 工具 + 自主决策 |
| ReAct | 推理 + 行动的循环模式 |
| Context | 只读的配置信息和参数，通过依赖注入传递给工具和中间件 |
| State | 短期记忆，当前会话的状态，存储对话过程信息 |
| Store | 长期记忆，跨对话的持久化存储，用户级数据 |
| Checkpointer | 状态持久化，支持中断恢复 |
| Middleware | 中间件，控制 Agent 行为（钩子机制） |
| Guardrails | 护栏，安全和合规检查（输入/输出过滤） |
| MCP | Model Context Protocol，标准化远程工具协议 |
| HITL | Human-in-the-Loop（人在回路），人工介入机制 |
| **多 Agent 模式** | |
| Subagents | 子 Agent 模式，委派任务给专门化 Agent |
| Handoffs | 控制权转移模式，Agent 间切换 |
| Skills | 技能模式，渐进式披露专门化提示词 |
| Router | 路由模式，语义分发到专门化 Agent |
| **RAG** | |
| RAG | 检索增强生成，用外部知识增强 LLM 回答 |
| 2-Step RAG | 传统 RAG，检索 → 生成 |
| Agentic RAG | Agent 驱动的 RAG，自主决策检索策略 |
| **LangSmith 工具链** | |
| LangSmith Studio | 免费的 Agent 可视化调试工具 |
| AgentEvals | Agent 轨迹评估库（轨迹匹配、LLM 评判） |
| Agent Chat UI | 开源的 Agent 对话界面 |
| Trace | 记录 Agent 执行的完整轨迹 |
| Deployment | LangSmith 托管平台，专为 Agent 设计 |

## 环境配置

### 依赖安装

```bash
# 创建虚拟环境
uv venv --python 3.11
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# 安装依赖
uv pip install langchain langchain-openai langgraph python-dotenv openai google-search-results
```

### API Key 配置

1. 复制 `.env.example` 为 `.env`
2. 填入你的 API Key

```bash
# LLM 提供商（选择一个）
LLM_MODEL_ID=qwen-plus                    # 阿里通义千问
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 或使用 OpenAI
# LLM_MODEL_ID=gpt-4
# LLM_API_KEY=sk-xxx
# LLM_BASE_URL=https://api.openai.com/v1

# 搜索工具（可选）
SERPAPI_API_KEY=your_serpapi_key
```

## 参考资源

- [LangChain 官方文档](https://docs.langchain.com/)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
