# Agent 的本质理解

> 一个关键发现：所有 Agent 都在做"特征工程"，最终目标都是构建一个好的 Prompt 给 LLM。

## 1. 核心洞察

**Agent 的本质 = Prompt 工程 + 控制流程 + 工具执行**

```
┌─────────────────────────────────────────┐
│            AI Agent 架构                │
├─────────────────────────────────────────┤
│                                         │
│  输入 → [特征工程] → Prompt → LLM      │
│           ↓                             │
│      记忆/工具/反馈                     │
│           ↓                             │
│     动态构建 Prompt                     │
│           ↓                             │
│        LLM 输出                         │
│           ↓                             │
│     解析 + 执行                         │
│           ↓                             │
│     循环/结束                           │
└─────────────────────────────────────────┘
```

## 2. 为什么都是"特征工程"？

因为 **LLM 只能理解文本输入**，所以 Agent 的所有组件最终都要转换成文本：

| Agent 组件 | 本质 | 特征工程方式 |
|-----------|------|-------------|
| **Memory（记忆）** | 存储历史信息 | 格式化成文本插入 Prompt |
| **Tools（工具）** | 外部能力 | 工具描述 + 调用结果转文本 |
| **Reflection（反思）** | 自我评估 | 评估结果转文本反馈 |
| **Planning（规划）** | 任务分解 | 计划列表转文本 |
| **Multi-Agent（多智能体）** | 协作 | 对话历史转文本 |

## 3. 不同 Agent 的特征工程对比

### 3.1 ReAct Agent

```python
# 特征工程：拼接 思考 + 行动 + 观察
prompt = f"""
你有以下工具：
{format_tools(tools)}  # 👈 特征工程：工具描述

问题：{question}

历史：
{format_history(history)}  # 👈 特征工程：格式化历史

请按照 Thought → Action → Observation 格式回答
"""
```

**特征工程重点：** 如何格式化工具列表和历史对话

### 3.2 Plan-Solve Agent

```python
# 特征工程：先规划，再执行
prompt = f"""
任务：{task}

## 第一步：制定计划
{format_plan(plan)}  # 👈 特征工程：结构化计划

## 第二步：执行计划
当前步骤：{current_step}
已完成：{completed_steps}  # 👈 特征工程：进度追踪
"""
```

**特征工程重点：** 如何表示计划结构和执行进度

### 3.3 Reflection Agent

```python
# 特征工程：拼接 执行 + 反思
prompt = f"""
任务：{task}

## 历史轨迹
{memory.get_trajectory()}  # 👈 特征工程：格式化执行和反馈

## 要求
请基于评审员的反馈改进代码
"""
```

**特征工程重点：** 如何组织执行历史和反馈信息

## 4. Agent ≠ 简单的 Prompt

虽然本质是特征工程，但 Agent 的价值在于：

### 4.1 动态 Prompt 构建

```python
# ❌ 静态 Prompt（不是 Agent）
prompt = "帮我搜索北京天气"
response = llm(prompt)

# ✅ 动态 Prompt（Agent）
prompt = f"""
任务：{task}
可用工具：{get_available_tools(context)}  # 根据上下文动态选择
相关记忆：{memory.get_relevant(task)}      # 只取相关记忆
当前状态：{state}                          # 实时状态
"""
response = llm(prompt)
```

### 4.2 控制流程

```python
# Agent 决定何时、如何调用 LLM
while not done:
    # 1. 特征工程：构建 Prompt
    prompt = build_prompt(
        task=task,
        memory=memory.get_trajectory(),
        tools=format_tools(tools),
        state=current_state
    )
    
    # 2. 调用 LLM
    response = llm(prompt)
    
    # 3. 解析输出
    action = parse_action(response)
    
    # 4. 执行工具（真实操作）
    result = execute_tool(action)
    
    # 5. 更新状态（影响下次 Prompt）
    memory.add(result)
    current_state.update(result)
    
    # 6. 判断是否完成
    done = check_completion(result)
```

### 4.3 工具执行

```python
# Prompt 只能生成文本
response = llm("帮我搜索天气")
# 输出："我需要调用搜索工具查询北京天气"

# Agent 能执行真实操作
action = parse(response)  # 解析出：tool="search", query="北京天气"
result = search_tool.run("北京天气")  # 真实 API 调用
# 输出：{"temperature": 15, "condition": "晴"}
```

## 5. Agent 的核心能力拆解

| 能力 | 说明 | 实现方式 | 例子 |
|-----|------|---------|-----|
| **上下文管理** | 决定哪些信息放入 Prompt | Memory 的检索和格式化 | `memory.get_trajectory()` |
| **流程控制** | 决定何时调用 LLM | 循环、条件判断、终止逻辑 | `while not done` |
| **工具编排** | 连接 LLM 和外部世界 | 工具注册、调用、结果处理 | `tool_executor.run()` |
| **状态维护** | 跨轮次的信息传递 | 记忆系统、对话历史 | `memory.add_record()` |
| **输出解析** | 理解 LLM 的意图 | 正则、JSON 解析、结构化输出 | `parse_action()` |

## 6. 设计 Agent 的关键问题

理解"Agent = 特征工程"后，设计 Agent 时要思考：

### 6.1 信息选择
**问题：** 什么信息应该放入 Prompt？

```python
# 不是所有信息都要放入
prompt = f"""
任务：{task}
全部历史：{all_history}  # ❌ 可能太长，超出上下文
"""

# 而是选择相关信息
prompt = f"""
任务：{task}
相关历史：{memory.get_relevant(task, top_k=3)}  # ✅ 只取最相关的
"""
```

### 6.2 信息格式化
**问题：** 如何格式化这些信息？

```python
# ❌ 不好的格式化
history = str(records)  # [{'type': 'execution', 'content': '...'}]

# ✅ 好的格式化
history = """
---上一轮尝试---

def add(a, b):
    return a + b

--- 评审员反馈 ---

缺少类型注解
"""
```

### 6.3 调用时机
**问题：** 何时调用 LLM？

```python
# 不是每次都调用
if can_use_cache(query):
    return cache.get(query)  # 使用缓存

if is_simple_task(task):
    return rule_based_solve(task)  # 规则处理

# 只在需要时调用
return llm(build_prompt(task))
```

### 6.4 输出解析
**问题：** 如何解析 LLM 输出？

```python
# LLM 输出可能不规范
response = "我觉得应该调用搜索工具，查询一下天气"

# 需要鲁棒的解析
action = parse_action(response)
# 提取出：{"tool": "search", "query": "天气"}
```

### 6.5 状态更新
**问题：** 如何更新状态影响下次 Prompt？

```python
# 执行后更新记忆
result = execute_tool(action)
memory.add_record("execution", result)

# 下次 Prompt 会包含这次的结果
next_prompt = build_prompt(
    task=task,
    history=memory.get_trajectory()  # 包含刚才的执行结果
)
```

## 7. 实战示例：Memory 的特征工程

### 7.1 原始数据

```python
records = [
    {"type": "execution", "content": "def add(a, b): return a + b"},
    {"type": "reflection", "content": "缺少类型注解"},
    {"type": "execution", "content": "def add(a: int, b: int) -> int: return a + b"}
]
```

### 7.2 特征工程：格式化

```python
def get_trajectory(self) -> str:
    """将记忆格式化为 Prompt 可用的文本"""
    trajectory_parts = []
    
    for record in self.records:
        if record['type'] == 'execution':
            # 格式化：添加标题和空行
            trajectory_parts.append(
                f"---上一轮尝试---\n\n{record['content']}"
            )
        elif record['type'] == 'reflection':
            trajectory_parts.append(
                f"--- 评审员反馈 ---\n\n{record['content']}"
            )
    
    # 用空行分隔各部分
    return '\n\n'.join(trajectory_parts)
```

### 7.3 最终 Prompt

```python
prompt = f"""
任务：写一个加法函数

## 历史记录
{memory.get_trajectory()}

## 要求
请基于反馈改进代码
"""

# LLM 实际看到的：
"""
任务：写一个加法函数

## 历史记录
---上一轮尝试---

def add(a, b): return a + b

--- 评审员反馈 ---

缺少类型注解

---上一轮尝试---

def add(a: int, b: int) -> int: return a + b

## 要求
请基于反馈改进代码
"""
```

## 8. 类比理解

### 传统编程
```python
def solve(input):
    # 写死的逻辑
    result = process(input)
    return result
```

### Prompt 工程
```python
def solve(input):
    prompt = f"请处理：{input}"
    return llm(prompt)
```

### Agent（Prompt 工程 + 控制流程）
```python
def solve(input):
    state = init_state(input)
    memory = Memory()
    
    while not done:
        # 特征工程：动态构建 Prompt
        prompt = build_prompt(
            task=input,
            memory=memory.get_trajectory(),
            state=state
        )
        
        # LLM 决策
        action = llm(prompt)
        
        # 执行真实操作
        result = execute(action)
        
        # 更新状态（影响下次 Prompt）
        memory.add(result)
        state.update(result)
        
        done = check_done(state)
    
    return state.result
```

## 9. 更高级的理解

### Agent 的数学表达

```
Agent = f(Prompt Engineering, Control Flow, Tool Execution)

其中：
- Prompt Engineering: 如何构建 Prompt
- Control Flow: 何时调用 LLM
- Tool Execution: 如何连接外部世界
```

### Agent 的组成

```python
Agent = {
    "特征工程": {
        "信息选择": "选择哪些信息放入 Prompt",
        "信息格式化": "如何格式化这些信息",
        "上下文管理": "如何管理上下文长度"
    },
    "控制流程": {
        "调用时机": "何时调用 LLM",
        "循环逻辑": "如何迭代优化",
        "终止条件": "何时停止"
    },
    "工具执行": {
        "工具注册": "有哪些工具可用",
        "工具调用": "如何调用工具",
        "结果处理": "如何处理工具返回"
    },
    "状态管理": {
        "记忆系统": "如何存储历史",
        "状态更新": "如何更新状态",
        "信息传递": "如何跨轮次传递信息"
    }
}
```

## 10. 实践启示

### 10.1 设计 Agent 时

1. **先设计 Prompt 模板**：明确需要哪些信息
2. **再设计特征工程**：如何获取和格式化这些信息
3. **最后设计控制流程**：何时调用、如何循环、何时停止

### 10.2 调试 Agent 时

1. **打印 Prompt**：看 LLM 实际收到了什么
2. **检查格式化**：信息是否清晰、结构是否合理
3. **优化特征工程**：调整信息选择和格式化方式

### 10.3 优化 Agent 时

1. **优化 Prompt 质量**：更清晰的结构、更好的格式
2. **优化信息选择**：只放相关信息，避免噪音
3. **优化控制流程**：减少不必要的 LLM 调用

## 11. 关键要点总结

1. **Agent 的本质是特征工程**：所有组件都在为构建好的 Prompt 服务
2. **但 Agent ≠ 简单 Prompt**：动态构建、流程控制、工具执行是关键
3. **设计 Agent = 设计特征工程**：信息选择、格式化、状态管理
4. **优化 Agent = 优化 Prompt**：打印 Prompt、检查格式、调整结构

## 12. 延伸思考

- 如何设计更好的特征工程方法？
- 如何平衡信息量和上下文长度？
- 如何让 LLM 更好地理解结构化信息？
- 如何减少不必要的 LLM 调用？

---

**最后更新：** 2026-01-19

**相关文档：**
- [01-Prompt工程技巧.md](./01-Prompt工程技巧.md)
