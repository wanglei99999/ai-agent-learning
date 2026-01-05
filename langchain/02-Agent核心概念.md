# 02 - Agent 核心概念

## 什么是 Agent

Agent = 大模型 + 工具 + 自主决策能力

普通聊天机器人只能对话，Agent 能**思考**要不要用工具、用哪个工具、怎么用，然后把结果整合成回答。

## 执行流程

```
用户提问 → Agent（大脑）→ 判断需要调用工具 → 调用工具 → 返回结果 → 组织回答
```

## 核心组件

### 1. Model（模型）

Agent 的"大脑"，负责理解问题、决策、组织回答。

```python
model="claude-sonnet-4-5-20250929"  # 指定使用哪个大模型
```

### 2. Tools（工具）

给 AI 用的函数，扩展 AI 的能力边界。

```python
def get_weather(city: str) -> str:
    """Get weather for a given city."""  # docstring 告诉 AI 这个工具干嘛的
    return f"It's always sunny in {city}!"
```

关键点：
- **docstring** 必须写清楚，AI 靠它理解工具用途
- **类型注解** 告诉 AI 参数类型
- AI 会**自己决定**要不要调用、传什么参数

### 3. System Prompt（系统提示词）

定义 AI 的角色和行为规范。

```python
system_prompt="You are a helpful assistant"
```

## 创建 Agent

```python
from langchain.agents import create_agent

agent = create_agent(
    model="claude-sonnet-4-5-20250929",  # 大脑
    tools=[get_weather],              # 工具箱
    system_prompt="You are a helpful assistant",  # 人设
)
```

## 调用 Agent

```python
result = agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
)
```

### invoke 参数说明

```python
{
    "messages": [
        {"role": "user", "content": "用户说的话"},
        {"role": "assistant", "content": "AI 之前的回复"},  # 可选，多轮对话
        {"role": "user", "content": "用户的新问题"},
    ]
}
```

- `role`: 消息角色，`user`（用户）或 `assistant`（AI）
- `content`: 消息内容

## 完整示例

```python
from langchain.agents import create_agent


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


agent = create_agent(
    model="claude-sonnet-4-5-20250929",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
)

print(result)
```

## 执行过程分析

1. 用户问："what is the weather in sf"
2. Agent 分析：这是问天气，我有 `get_weather` 工具
3. Agent 决定调用：`get_weather("sf")`
4. 工具返回：`"It's always sunny in sf!"`
5. Agent 组织语言回答用户

## 类比理解

| LangChain | 类比 |
|-----------|------|
| Agent | 一个有工具箱的助手 |
| Model | 助手的大脑 |
| Tools | 工具箱里的工具 |
| System Prompt | 助手的岗位职责说明 |
| invoke | 给助手派任务 |
