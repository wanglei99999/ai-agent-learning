# Hello Agent

AI Agent 学习项目 - 从零实现各种 Agent 架构

## 📁 项目结构

```
hello_agent/
├── core/                    # 共享的核心组件
│   ├── llm.py              # LLM 客户端（所有 Agent 共用）
│   ├── tool_executor.py    # 工具执行器（所有 Agent 共用）
│   └── __init__.py
│
├── tools/                   # 共享的工具库
│   ├── search.py           # 搜索工具
│   └── __init__.py
│
├── agents/                  # 所有 Agent 实现
│   ├── react/              # ReAct Agent
│   │   ├── agent.py        # Agent 实现
│   │   ├── prompts.py      # 提示词模板
│   │   └── __init__.py
│   │
│   ├── plan_solve/         # Plan-Solve Agent（待实现）
│   │   ├── agent.py        # Agent 实现
│   │   ├── prompts.py      # 提示词模板
│   │   ├── planner.py      # Planner 类
│   │   ├── solver.py       # Solver 类
│   │   └── __init__.py
│   │
│   └── __init__.py
│
├── examples/                # 示例代码
│   ├── run_react_agent.py
│   └── __init__.py
│
└── README.md
```

## 🚀 快速开始

### 1. 配置环境变量

复制项目根目录的 `.env.example` 为 `.env`，配置以下变量：

```bash
# LLM 配置（使用阿里通义千问）
LLM_MODEL_ID=qwen-plus
LLM_API_KEY=your_dashscope_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_TIMEOUT=60

# 搜索工具配置
SERPAPI_API_KEY=your_serpapi_key
```

### 2. 运行 ReAct Agent 示例

```bash
python hello_agent/examples/run_react_agent.py
```

## 📚 已实现的 Agent

### ✅ ReAct Agent

**架构**：Reasoning + Acting（边想边做）

**特点**：
- 循环执行"思考→行动→观察"
- 适合探索性任务
- 灵活但可能效率较低

**使用示例**：
```python
from hello_agent.core import HelloAgentsLLM, ToolExecutor
from hello_agent.agents.react import ReactAgent
from hello_agent.tools import search

# 初始化
llm = HelloAgentsLLM()
tool_executor = ToolExecutor()
tool_executor.register_tool("Search", "搜索工具", search)

# 创建 Agent
agent = ReactAgent(llm, tool_executor, max_steps=5)

# 运行
answer = agent.run("英伟达最新的GPU是什么？")
```

## 🚧 待实现的 Agent

### Plan-Solve Agent

**架构**：先规划、再执行

**特点**：
- 第1阶段：制定完整计划
- 第2阶段：按计划执行
- 更有条理，适合结构化任务

**实现任务**：
- [ ] 创建 `Planner` 类（`agents/plan_solve/planner.py`）
- [ ] 创建 `Solver` 类（`agents/plan_solve/solver.py`）
- [ ] 创建 `PlanSolveAgent` 类（`agents/plan_solve/agent.py`）
- [ ] 创建运行示例（`examples/run_plan_solve_agent.py`）

## 🎯 设计原则

1. **代码复用**：共享组件（LLM、工具）只实现一次
2. **模块化**：每个 Agent 独立目录，互不干扰
3. **易扩展**：添加新 Agent 只需在 `agents/` 下创建新目录
4. **清晰导入**：使用标准的 Python 包导入方式

## 📖 学习路线

1. **ReAct Agent**：理解基本的 Agent 循环
2. **Plan-Solve Agent**：学习规划与执行分离
3. **Reflection Agent**：学习自我反思机制
4. **Multi-Agent**：学习多 Agent 协作

## 🔗 相关资源

- [ReAct 论文](https://arxiv.org/abs/2210.03629)
- [Plan-and-Solve 论文](https://arxiv.org/abs/2305.04091)
- [LangChain 文档](https://python.langchain.com/)
