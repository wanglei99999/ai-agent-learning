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
│   ├── 08-短期记忆详解.md
│   ├── 09-流式输出详解.md
│   ├── 10-结构化输出详解.md
│   ├── 11-中间件详解.md
│   ├── 12-护栏详解.md
│   ├── 13-运行时详解.md
│   ├── 14-上下文工程详解.md
│   ├── 15-MCP详解.md
│   ├── 16-HITL详解.md
│   ├── 17-多Agent概述.md
│   ├── 18-Subagents模式.md
│   ├── 19-Handoffs模式.md
│   ├── 20-Skills模式.md
│   ├── 21-Router模式.md
│   ├── 22-自定义工作流.md
│   ├── 23-RAG检索详解.md
│   ├── 24-长期记忆详解.md
│   ├── 25-LangSmith Studio详解.md
│   ├── 26-Agent测试详解.md
│   ├── 27-Agent Chat UI详解.md
│   ├── 28-LangSmith部署详解.md
│   ├── 29-LangSmith可观测性详解.md
│   └── examples/
├── langgraph/              # LangGraph 学习笔记（待添加）
└── README.md
```

## 学习路线

### LangChain

| 章节 | 内容 | 说明 |
|------|------|------|
| 01 | [环境搭建](./langchain/01-环境搭建.md) | uv、VSCode、依赖安装 |
| 02 | [Agent 核心概念](./langchain/02-Agent核心概念.md) | Model、Tools、System Prompt |
| 03 | [快速入门完整示例](./langchain/03-快速入门完整示例.md) | 完整天气查询 Agent |
| 04 | [Agent 详解](./langchain/04-Agent详解.md) | ReAct、调用方式、状态管理 |
| 05 | [Models 详解](./langchain/05-Models详解.md) | 模型初始化、调用、工具绑定 |
| 06 | [Messages 详解](./langchain/06-Messages详解.md) | 消息类型、多模态、内容块 |
| 07 | [Tools 详解](./langchain/07-Tools详解.md) | 工具定义、ToolRuntime、状态访问 |
| 08 | [短期记忆详解](./langchain/08-短期记忆详解.md) | Checkpointer、消息裁剪/删除/总结 |
| 09 | [流式输出详解](./langchain/09-流式输出详解.md) | updates/messages/custom 模式 |
| 10 | [结构化输出详解](./langchain/10-结构化输出详解.md) | Pydantic、ToolStrategy、ProviderStrategy |
| 11 | [中间件详解](./langchain/11-中间件详解.md) | 钩子、内置中间件、自定义中间件 |
| 12 | [护栏详解](./langchain/12-护栏详解.md) | 确定性/模型护栏、输入/输出过滤 |
| 13 | [运行时详解](./langchain/13-运行时详解.md) | Runtime、Context、State、Store |
| 14 | [上下文工程详解](./langchain/14-上下文工程详解.md) | 模型/工具/生命周期上下文 |
| 15 | [MCP 详解](./langchain/15-MCP详解.md) | Model Context Protocol、远程工具、拦截器 |
| 16 | [HITL 详解](./langchain/16-HITL详解.md) | Human-in-the-Loop（人在回路）、approve/edit/reject |
| 17 | [多 Agent 概述](./langchain/17-多Agent概述.md) | 多 Agent 架构、模式选择 |
| 18 | [Subagents 模式](./langchain/18-Subagents模式.md) | 子 Agent 委派、独立上下文 |
| 19 | [Handoffs 模式](./langchain/19-Handoffs模式.md) | Agent 间控制权转移 |
| 20 | [Skills 模式](./langchain/20-Skills模式.md) | 渐进式披露、提示词专门化 |
| 21 | [Router 模式](./langchain/21-Router模式.md) | 语义路由、条件分发 |
| 22 | [自定义工作流](./langchain/22-自定义工作流.md) | LangGraph 状态机、复杂流程编排 |
| 23 | [RAG 检索详解](./langchain/23-RAG检索详解.md) | 检索增强生成、2-Step/Agentic/Hybrid RAG |
| 24 | [长期记忆详解](./langchain/24-长期记忆详解.md) | Store、跨会话持久化、namespace/key |
| 25 | [LangSmith Studio 详解](./langchain/25-LangSmith%20Studio详解.md) | 可视化调试、执行轨迹、热重载 |
| 26 | [Agent 测试详解](./langchain/26-Agent测试详解.md) | 单元测试、轨迹匹配、LLM 评判 |
| 27 | [Agent Chat UI 详解](./langchain/27-Agent%20Chat%20UI详解.md) | 对话界面、工具可视化、时间旅行 |
| 28 | [LangSmith 部署详解](./langchain/28-LangSmith部署详解.md) | 生产部署、GitHub 集成、API 调用 |
| 29 | [LangSmith 可观测性详解](./langchain/29-LangSmith可观测性详解.md) | Trace 追踪、元数据、监控 |

### LangGraph

待添加...

## 核心概念速查

| 概念 | 说明 |
|------|------|
| Agent | 大模型 + 工具 + 自主决策 |
| ReAct | 推理 + 行动的循环模式 |
| Context | 只读的配置信息和参数，通过依赖注入传递给工具和中间件 |
| State | 当前会话的记忆，存储对话过程信息，作为上下文发送给模型 |
| Store | 跨对话的持久化存储，功能与 State 类似但范围从会话级上升到用户级 |
| Middleware | 中间件，控制 Agent 行为（钩子机制） |
| Checkpointer | 状态持久化，支持中断恢复 |
| MCP | Model Context Protocol，标准化远程工具协议 |
| HITL | Human-in-the-Loop（人在回路），人工介入机制 |
| Multi-Agent | 多 Agent 协作架构 |
| Subagents | 子 Agent 模式，委派任务给专门化 Agent |
| Handoffs | 控制权转移模式，Agent 间切换 |
| Skills | 技能模式，渐进式披露专门化提示词 |
| Router | 路由模式，语义分发到专门化 Agent |
| RAG | 检索增强生成，用外部知识增强 LLM 回答 |
| LangSmith Studio | 免费的 Agent 可视化调试工具 |
| AgentEvals | Agent 轨迹评估库 |
| Agent Chat UI | 开源的 Agent 对话界面 |
| Trace | 记录 Agent 执行的完整轨迹 |

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
