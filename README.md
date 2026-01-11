# AI Agent 学习笔记

学习 LangChain、LangGraph 等 AI Agent 开发框架的笔记和示例代码。

## 目录结构

```
├── langchain/              # LangChain 学习笔记
│   ├── 01-环境搭建.md
│   ├── 02-Agent核心概念.md
│   ├── 03-快速入门完整示例.md
│   ├── 04-Agent详解.md
│   ├── 05-Models详解.md
│   ├── 06-Messages详解.md
│   ├── 07-Tools详解.md
│   ├── 08-记忆系统详解.md          ⭐ 合并（短期+长期记忆）
│   ├── 09-输出控制详解.md          ⭐ 合并（流式+结构化输出）
│   ├── 10-中间件详解.md
│   ├── 11-Guardrails.md
│   ├── 12-Runtime详解.md
│   ├── 13-上下文工程详解.md
│   ├── 14-MCP详解.md
│   ├── 15-HITL详解.md
│   ├── 16-多Agent架构详解.md      ⭐ 合并（5种模式）
│   ├── 17-LangSmith工具链详解.md  ⭐ 合并（Studio+测试+部署+监控）
│   ├── 18-RAG检索详解.md
│   ├── 19-Deep Research实践.md
│   ├── data/                       # 示例数据
│   └── examples/                   # 示例代码
├── langgraph/              # LangGraph 学习笔记（待添加）
└── README.md
```

## 学习路线

### LangChain

#### 基础篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 01 | [环境搭建](./langchain/01-环境搭建.md) | uv、VSCode、依赖安装 |
| 02 | [Agent 核心概念](./langchain/02-Agent核心概念.md) | Model、Tools、System Prompt |
| 03 | [快速入门完整示例](./langchain/03-快速入门完整示例.md) | 完整天气查询 Agent |
| 04 | [Agent 详解](./langchain/04-Agent详解.md) | ReAct、调用方式、状态管理 |
| 05 | [Models 详解](./langchain/05-Models详解.md) | 模型初始化、调用、工具绑定 |
| 06 | [Messages 详解](./langchain/06-Messages详解.md) | 消息类型、多模态、内容块 |
| 07 | [Tools 详解](./langchain/07-Tools详解.md) | 工具定义、ToolRuntime、状态访问 |

#### 核心功能篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 08 | [记忆系统详解](./langchain/08-记忆系统详解.md) | 短期记忆（State）+ 长期记忆（Store） |
| 09 | [输出控制详解](./langchain/09-输出控制详解.md) | 流式输出 + 结构化输出 |
| 10 | [中间件详解](./langchain/10-中间件详解.md) | 钩子、内置中间件、自定义中间件 |
| 11 | [Guardrails](./langchain/11-Guardrails.md) | 确定性/模型护栏、输入/输出过滤 |
| 12 | [Runtime 详解](./langchain/12-Runtime详解.md) | Runtime、Context、State、Store |
| 13 | [上下文工程详解](./langchain/13-上下文工程详解.md) | 模型/工具/生命周期上下文 |
| 14 | [MCP 详解](./langchain/14-MCP详解.md) | Model Context Protocol、远程工具 |
| 15 | [HITL 详解](./langchain/15-HITL详解.md) | Human-in-the-Loop（人在回路） |

#### 多 Agent 架构篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 16 | [多 Agent 架构详解](./langchain/16-多Agent架构详解.md) | Subagents、Handoffs、Skills、Router、自定义工作流 |

#### LangSmith 工具链篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 17 | [LangSmith 工具链详解](./langchain/17-LangSmith工具链详解.md) | Studio、测试、Chat UI、部署、可观测性 |

#### RAG 与实践篇

| 章节 | 内容 | 说明 |
|------|------|------|
| 18 | [RAG 检索详解](./langchain/18-RAG检索详解.md) | 检索增强生成、2-Step/Agentic/Hybrid RAG |
| 19 | [Deep Research 实践](./langchain/19-Deep%20Research实践.md) | 深度研究 Agent 实战 |

### LangGraph

待添加...

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

1. 复制 `.env.example` 为 `.env`
2. 填入你的 API Key

```bash
# 创建虚拟环境
uv venv --python 3.11
.venv\Scripts\activate

# 安装依赖
uv pip install langchain langchain-openai langgraph python-dotenv
```

## 参考资源

- [LangChain 官方文档](https://docs.langchain.com/)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
