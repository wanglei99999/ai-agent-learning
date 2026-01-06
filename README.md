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
| 12 | [护栏详解](./langchain/12-护栏详解.md) | PII 检测、人工审核、安全过滤 |
| 13 | [运行时详解](./langchain/13-运行时详解.md) | Runtime、Context、依赖注入 |
| 14 | [上下文工程详解](./langchain/14-上下文工程详解.md) | 模型/工具/生命周期上下文 |

### LangGraph

待添加...

## 核心概念速查

| 概念 | 说明 |
|------|------|
| Agent | 大模型 + 工具 + 自主决策 |
| ReAct | 推理 + 行动的循环模式 |
| State | 短期记忆，对话级 |
| Store | 长期记忆，跨对话 |
| Context | 运行时配置，只读 |
| Middleware | 中间件，控制 Agent 行为 |
| Checkpointer | 状态持久化 |

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
