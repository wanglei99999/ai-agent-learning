# MCP 详解

MCP（Model Context Protocol）是一个开放协议，标准化了应用程序向 LLM 提供工具和上下文的方式。LangChain Agent 可以通过 `langchain-mcp-adapters` 库使用 MCP 服务器上定义的工具。

## 安装

```bash
# pip
pip install langchain-mcp-adapters

# uv
uv add langchain-mcp-adapters
```

## 快速开始

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

# 连接多个 MCP 服务器
client = MultiServerMCPClient({
    "math": {
        "transport": "stdio",  # 本地子进程通信
        "command": "python",
        "args": ["/path/to/math_server.py"],
    },
    "weather": {
        "transport": "http",  # HTTP 远程服务器
        "url": "http://localhost:8000/mcp",
    }
})

# 获取工具并创建 Agent
tools = await client.get_tools()
agent = create_agent("claude-sonnet-4-5-20250929", tools)

# 使用
result = await agent.ainvoke({
    "messages": [{"role": "user", "content": "(3 + 5) x 12 等于多少？"}]
})
```

> **注意**：`MultiServerMCPClient` 默认是**无状态**的。每次工具调用都会创建新的 MCP `ClientSession`，执行完后清理。

## 传输方式

MCP 支持不同的传输机制：

| 传输方式 | 说明 | 适用场景 |
|----------|------|----------|
| `http` | HTTP 请求通信 | 远程服务器 |
| `stdio` | 标准输入/输出 | 本地工具、简单场景 |

### HTTP 传输

```python
client = MultiServerMCPClient({
    "weather": {
        "transport": "http",
        "url": "http://localhost:8000/mcp",
        # 可选：自定义请求头
        "headers": {
            "Authorization": "Bearer YOUR_TOKEN",
            "X-Custom-Header": "custom-value"
        },
    }
})
```

### stdio 传输

```python
client = MultiServerMCPClient({
    "math": {
        "transport": "stdio",
        "command": "python",
        "args": ["/path/to/math_server.py"],
    }
})
```

## 创建自定义 MCP 服务器

使用 FastMCP 库创建服务器：

```bash
pip install fastmcp
```

### stdio 服务器示例

```python
from fastmcp import FastMCP

mcp = FastMCP("Math")

@mcp.tool()
def add(a: int, b: int) -> int:
    """两数相加"""
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """两数相乘"""
    return a * b

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### HTTP 服务器示例

```python
from fastmcp import FastMCP

mcp = FastMCP("Weather")

@mcp.tool()
async def get_weather(location: str) -> str:
    """获取指定位置的天气"""
    return f"{location} 今天晴朗"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

## 有状态会话

默认情况下每次工具调用都是独立的。如果需要跨工具调用保持状态：

```python
client = MultiServerMCPClient({...})

# 显式创建会话
async with client.session("server_name") as session:
    # 在同一会话中加载工具
    tools = await load_mcp_tools(session)
    agent = create_agent("gpt-4o", tools)
    # 这个会话内的所有工具调用共享状态
```

## 核心功能

### 1. 工具（Tools）

MCP 服务器可以暴露可执行函数，LangChain 会将其转换为 LangChain 工具。

```python
# 加载工具
tools = await client.get_tools()
agent = create_agent("gpt-4o", tools)
```

### 2. 资源（Resources）

MCP 服务器可以暴露数据（文件、数据库记录等），转换为 Blob 对象。

```python
# 加载所有资源
blobs = await client.get_resources("server_name")

# 加载特定资源
blobs = await client.get_resources("server_name", uris=["file:///path/to/file.txt"])

for blob in blobs:
    print(f"URI: {blob.metadata['uri']}")
    print(blob.as_string())  # 文本内容
```

### 3. 提示词（Prompts）

MCP 服务器可以暴露可复用的提示词模板。

```python
# 加载提示词
messages = await client.get_prompt("server_name", "summarize")

# 带参数的提示词
messages = await client.get_prompt(
    "server_name",
    "code_review",
    arguments={"language": "python", "focus": "security"}
)
```

## 拦截器（Interceptors）

MCP 服务器作为独立进程运行，无法访问 LangGraph 运行时信息。**拦截器**可以在 MCP 工具执行时访问运行时上下文。

### 访问 Runtime Context

```python
from dataclasses import dataclass
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

@dataclass
class Context:
    user_id: str
    api_key: str

async def inject_user_context(request: MCPToolCallRequest, handler):
    """将用户信息注入到 MCP 工具调用中"""
    runtime = request.runtime
    user_id = runtime.context.user_id  # 访问 context
    
    # 修改请求参数
    modified_request = request.override(
        args={**request.args, "user_id": user_id}
    )
    return await handler(modified_request)

client = MultiServerMCPClient(
    {...},
    tool_interceptors=[inject_user_context],
)
```

### 访问 Store

```python
async def personalize_search(request: MCPToolCallRequest, handler):
    """使用 Store 中的用户偏好个性化搜索"""
    runtime = request.runtime
    user_id = runtime.context.user_id
    store = runtime.store  # 访问 store
    
    # 读取用户偏好
    prefs = store.get(("preferences",), user_id)
    if prefs and request.name == "search":
        modified_args = {
            **request.args,
            "language": prefs.value.get("language", "en"),
        }
        request = request.override(args=modified_args)
    
    return await handler(request)
```

### 访问 State

```python
async def require_authentication(request: MCPToolCallRequest, handler):
    """敏感工具需要认证"""
    runtime = request.runtime
    state = runtime.state  # 访问 state
    is_authenticated = state.get("authenticated", False)
    
    sensitive_tools = ["delete_file", "update_settings"]
    
    if request.name in sensitive_tools and not is_authenticated:
        return ToolMessage(
            content="需要认证，请先登录。",
            tool_call_id=runtime.tool_call_id,
        )
    
    return await handler(request)
```

### 状态更新与 Command

拦截器可以返回 `Command` 对象来更新 Agent 状态或控制执行流程：

```python
from langgraph.types import Command

async def handle_task_completion(request: MCPToolCallRequest, handler):
    """任务完成后切换到总结 Agent"""
    result = await handler(request)
    
    if request.name == "submit_order":
        return Command(
            update={
                "messages": [result],
                "task_status": "completed",
            },
            goto="summary_agent",  # 跳转到其他节点
        )
    
    return result
```

### 拦截器组合

多个拦截器按"洋葱"顺序执行：

```python
async def outer(request, handler):
    print("outer: before")
    result = await handler(request)
    print("outer: after")
    return result

async def inner(request, handler):
    print("inner: before")
    result = await handler(request)
    print("inner: after")
    return result

client = MultiServerMCPClient(
    {...},
    tool_interceptors=[outer, inner],
)

# 执行顺序：
# outer: before → inner: before → 工具执行 → inner: after → outer: after
```

### 错误处理与重试

```python
import asyncio

async def retry_interceptor(request: MCPToolCallRequest, handler, max_retries=3):
    """失败时指数退避重试"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return await handler(request)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 1.0 * (2 ** attempt)  # 指数退避
                await asyncio.sleep(wait_time)
    
    raise last_error
```

## 回调功能

### 进度通知

```python
from langchain_mcp_adapters.callbacks import Callbacks, CallbackContext

async def on_progress(
    progress: float,
    total: float | None,
    message: str | None,
    context: CallbackContext,
):
    percent = (progress / total * 100) if total else progress
    print(f"[{context.server_name}] 进度: {percent:.1f}% - {message}")

client = MultiServerMCPClient(
    {...},
    callbacks=Callbacks(on_progress=on_progress),
)
```

### 日志

```python
async def on_logging_message(params, context: CallbackContext):
    print(f"[{context.server_name}] {params.level}: {params.data}")

client = MultiServerMCPClient(
    {...},
    callbacks=Callbacks(on_logging_message=on_logging_message),
)
```

## Elicitation（交互式输入）

允许 MCP 服务器在工具执行过程中请求用户输入。

### 服务器端

```python
from pydantic import BaseModel
from mcp.server.fastmcp import Context, FastMCP

server = FastMCP("Profile")

class UserDetails(BaseModel):
    email: str
    age: int

@server.tool()
async def create_profile(name: str, ctx: Context) -> str:
    """创建用户档案，通过 elicitation 请求详细信息"""
    result = await ctx.elicit(
        message=f"请提供 {name} 的档案信息：",
        schema=UserDetails,
    )
    
    if result.action == "accept" and result.data:
        return f"已创建 {name} 的档案：email={result.data.email}, age={result.data.age}"
    if result.action == "decline":
        return f"用户拒绝，已创建 {name} 的最小档案。"
    return "档案创建已取消。"
```

### 客户端

```python
from mcp.types import ElicitResult

async def on_elicitation(mcp_context, params, context):
    """处理 elicitation 请求"""
    # 实际应用中，这里会提示用户输入
    return ElicitResult(
        action="accept",
        content={"email": "user@example.com", "age": 25},
    )

client = MultiServerMCPClient(
    {...},
    callbacks=Callbacks(on_elicitation=on_elicitation),
)
```

### 响应动作

| 动作 | 说明 |
|------|------|
| `accept` | 用户提供了有效输入，数据在 `content` 字段 |
| `decline` | 用户选择不提供请求的信息 |
| `cancel` | 用户取消了整个操作 |

## 总结

| 概念 | 说明 |
|------|------|
| MCP | 标准化 LLM 工具和上下文的开放协议 |
| `MultiServerMCPClient` | 连接多个 MCP 服务器的客户端 |
| 传输方式 | `http`（远程）、`stdio`（本地） |
| 拦截器 | 在工具执行时访问运行时上下文 |
| Tools | MCP 服务器暴露的可执行函数 |
| Resources | MCP 服务器暴露的数据 |
| Prompts | MCP 服务器暴露的提示词模板 |
| Elicitation | 工具执行中请求用户输入 |
