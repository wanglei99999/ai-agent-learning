# Messages 详解

Messages 是 LangChain 中模型上下文的基本单位。它们表示模型的输入和输出，携带与 LLM 交互时表示对话状态所需的内容和元数据。

Message 对象包含：

- 👤 **Role（角色）** - 标识消息类型（如 `system`、`user`）
- 📁 **Content（内容）** - 表示消息的实际内容（如文本、图像、音频、文档等）
- 🏷️ **Metadata（元数据）** - 可选字段，如响应信息、消息 ID 和 token 使用量

LangChain 提供了跨所有模型提供商工作的标准消息类型，确保无论调用哪个模型都有一致的行为。

## 基本用法

创建消息对象并在调用模型时传递它们：

```python
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, AIMessage, SystemMessage

model = init_chat_model("gpt-4o")

system_msg = SystemMessage("你是一个有帮助的助手。")
human_msg = HumanMessage("你好，你好吗？")

messages = [system_msg, human_msg]
response = model.invoke(messages)  # 返回 AIMessage
```

### 三种输入方式

#### 1. 文本提示（字符串）

最简单的方式，适用于不需要保留对话历史的单次请求：

```python
response = model.invoke("写一首关于春天的俳句")
```

#### 2. 消息列表（Message 对象）

适用于管理多轮对话、处理多模态内容或包含系统指令：

```python
from langchain.messages import SystemMessage, HumanMessage, AIMessage

messages = [
    SystemMessage("你是一个诗歌专家"),
    HumanMessage("写一首关于春天的俳句"),
    AIMessage("樱花绽放时...")
]
response = model.invoke(messages)
```

#### 3. 字典格式（OpenAI 兼容）

直接使用 OpenAI 聊天完成格式：

```python
messages = [
    {"role": "system", "content": "你是一个诗歌专家"},
    {"role": "user", "content": "写一首关于春天的俳句"},
    {"role": "assistant", "content": "樱花绽放时..."}
]
response = model.invoke(messages)
```

## 消息类型

### SystemMessage（系统消息）

设置模型行为的初始指令，用于定义模型的角色、语气和响应准则。

```python
from langchain.messages import SystemMessage, HumanMessage

# 基本指令
system_msg = SystemMessage("你是一个有帮助的编程助手。")

# 详细人设
system_msg = SystemMessage("""你是一个资深 Python 开发者，专精于 Web 框架。
始终提供代码示例并解释你的推理。
解释要简洁但全面。""")

messages = [system_msg, HumanMessage("如何创建 REST API？")]
response = model.invoke(messages)
```

### HumanMessage（用户消息）

表示用户输入和交互，可以包含文本、图像、音频、文件等多模态内容。

```python
from langchain.messages import HumanMessage

# 文本内容
human_msg = HumanMessage("什么是机器学习？")

# 带元数据
human_msg = HumanMessage(
    content="你好！",
    name="alice",      # 可选：标识不同用户
    id="msg_123",      # 可选：用于追踪的唯一标识符
)

# 字符串是单个 HumanMessage 的快捷方式
response = model.invoke("什么是机器学习？")
# 等同于
response = model.invoke([HumanMessage("什么是机器学习？")])
```

### AIMessage（AI 消息）

表示模型调用的输出，可以包含多模态数据、工具调用和提供商特定的元数据。

```python
response = model.invoke("解释 AI")
print(type(response))  # <class 'langchain.messages.AIMessage'>
```

#### 主要属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `text` | string | 消息的文本内容 |
| `content` | string \| dict[] | 消息的原始内容 |
| `content_blocks` | ContentBlock[] | 标准化的内容块 |
| `tool_calls` | dict[] \| None | 模型发起的工具调用 |
| `id` | string | 消息的唯一标识符 |
| `usage_metadata` | dict \| None | 使用元数据（token 计数等） |
| `response_metadata` | dict \| None | 响应元数据 |

#### 手动创建 AIMessage

有时需要手动创建 AIMessage 并插入到消息历史中：

```python
from langchain.messages import AIMessage, SystemMessage, HumanMessage

# 手动创建 AI 消息（例如用于对话历史）
ai_msg = AIMessage("我很乐意帮助你解答这个问题！")

# 添加到对话历史
messages = [
    SystemMessage("你是一个有帮助的助手"),
    HumanMessage("你能帮我吗？"),
    ai_msg,  # 插入，就像它来自模型一样
    HumanMessage("太好了！2+2 等于多少？")
]
response = model.invoke(messages)
```

#### 工具调用

当模型进行工具调用时，它们包含在 AIMessage 中：

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("gpt-4o")

def get_weather(location: str) -> str:
    """获取指定位置的天气"""
    ...

model_with_tools = model.bind_tools([get_weather])
response = model_with_tools.invoke("巴黎的天气怎么样？")

for tool_call in response.tool_calls:
    print(f"工具: {tool_call['name']}")
    print(f"参数: {tool_call['args']}")
    print(f"ID: {tool_call['id']}")
```

#### Token 使用量

```python
response = model.invoke("你好！")
print(response.usage_metadata)
# {
#   'input_tokens': 8,
#   'output_tokens': 304,
#   'total_tokens': 312,
#   'input_token_details': {'audio': 0, 'cache_read': 0},
#   'output_token_details': {'audio': 0, 'reasoning': 256}
# }
```

#### 流式输出和 Chunks

在流式输出期间，你会收到 `AIMessageChunk` 对象，可以组合成完整的消息：

```python
chunks = []
full_message = None

for chunk in model.stream("你好"):
    chunks.append(chunk)
    print(chunk.text)
    full_message = chunk if full_message is None else full_message + chunk
```

### ToolMessage（工具消息）

用于将单个工具执行的结果传回模型。

```python
from langchain.messages import AIMessage, ToolMessage, HumanMessage

# 模型发起工具调用后
ai_message = AIMessage(
    content=[],
    tool_calls=[{
        "name": "get_weather",
        "args": {"location": "旧金山"},
        "id": "call_123"
    }]
)

# 执行工具并创建结果消息
weather_result = "晴天，72°F"
tool_message = ToolMessage(
    content=weather_result,
    tool_call_id="call_123"  # 必须匹配调用 ID
)

# 继续对话
messages = [
    HumanMessage("旧金山的天气怎么样？"),
    ai_message,      # 模型的工具调用
    tool_message,    # 工具执行结果
]
response = model.invoke(messages)  # 模型处理结果
```

#### ToolMessage 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `content` | string | 工具调用的字符串化输出（必需） |
| `tool_call_id` | string | 此消息响应的工具调用 ID（必需） |
| `name` | string | 被调用的工具名称（必需） |
| `artifact` | dict | 不发送给模型但可以程序化访问的附加数据 |

#### artifact 字段

`artifact` 字段存储不会发送给模型但可以程序化访问的补充数据，适用于存储原始结果、调试信息或下游处理的数据：

```python
from langchain.messages import ToolMessage

# 发送给模型的内容
message_content = "这是最好的时代，这是最坏的时代。"

# 下游可用的 artifact
artifact = {"document_id": "doc_123", "page": 0}

tool_message = ToolMessage(
    content=message_content,
    tool_call_id="call_123",
    name="search_books",
    artifact=artifact,
)
```

## 消息内容

消息的内容是发送给模型的数据载体。`content` 属性支持字符串和无类型对象列表（如字典），允许直接在 LangChain 聊天模型中支持提供商原生结构。

### 内容格式

```python
from langchain.messages import HumanMessage

# 1. 字符串内容
human_message = HumanMessage("你好，你好吗？")

# 2. 提供商原生格式（如 OpenAI）
human_message = HumanMessage(content=[
    {"type": "text", "text": "你好，你好吗？"},
    {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
])

# 3. 标准内容块列表
human_message = HumanMessage(content_blocks=[
    {"type": "text", "text": "你好，你好吗？"},
    {"type": "image", "url": "https://example.com/image.jpg"},
])
```

### 标准内容块

LangChain 提供了跨提供商工作的标准消息内容表示。

#### 核心块

**TextContentBlock** - 标准文本输出

```python
{
    "type": "text",
    "text": "Hello world",
    "annotations": []
}
```

**ReasoningContentBlock** - 模型推理步骤

```python
{
    "type": "reasoning",
    "reasoning": "用户在问关于...",
    "extras": {"signature": "abc123"}
}
```

#### 多模态块

**ImageContentBlock** - 图像数据

```python
# 从 URL
{"type": "image", "url": "https://example.com/image.jpg"}

# 从 base64
{
    "type": "image",
    "base64": "AAAAIGZ0eXBtcDQy...",
    "mime_type": "image/jpeg"
}

# 从提供商管理的文件 ID
{"type": "image", "file_id": "file-abc123"}
```

**AudioContentBlock** - 音频数据

```python
{
    "type": "audio",
    "base64": "AAAAIGZ0eXBtcDQy...",
    "mime_type": "audio/wav"
}
```

**VideoContentBlock** - 视频数据

```python
{
    "type": "video",
    "base64": "AAAAIGZ0eXBtcDQy...",
    "mime_type": "video/mp4"
}
```

**FileContentBlock** - 通用文件（PDF 等）

```python
# 从 URL
{"type": "file", "url": "https://example.com/document.pdf"}

# 从 base64
{
    "type": "file",
    "base64": "AAAAIGZ0eXBtcDQy...",
    "mime_type": "application/pdf"
}
```

#### 工具调用块

**ToolCall** - 函数调用

```python
{
    "type": "tool_call",
    "name": "search",
    "args": {"query": "weather"},
    "id": "call_123"
}
```

**ToolCallChunk** - 流式工具调用片段

```python
{
    "type": "tool_call_chunk",
    "name": "search",
    "args": "{\"query\":",  # 可能是不完整的 JSON
    "id": "call_123",
    "index": 0
}
```

**InvalidToolCall** - 格式错误的调用（用于捕获 JSON 解析错误）

```python
{
    "type": "invalid_tool_call",
    "name": "search",
    "args": {},
    "error": "JSON 解析失败"
}
```

#### 服务器端工具执行块

**ServerToolCall** - 服务器端执行的工具调用

```python
{
    "type": "server_tool_call",
    "id": "call_123",
    "name": "web_search",
    "args": {"query": "..."}
}
```

**ServerToolResult** - 服务器端工具结果

```python
{
    "type": "server_tool_result",
    "tool_call_id": "call_123",
    "status": "success",  # 或 "error"
    "output": "..."
}
```

## 多模态输入示例

### 图像输入

```python
# 从 URL
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "描述这张图片的内容。"},
        {"type": "image", "url": "https://example.com/path/to/image.jpg"},
    ]
}

# 从 base64 数据
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "描述这张图片的内容。"},
        {
            "type": "image",
            "base64": "AAAAIGZ0eXBtcDQy...",
            "mime_type": "image/jpeg"
        },
    ]
}
```

### PDF 文档输入

```python
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "描述这个文档的内容。"},
        {"type": "file", "url": "https://example.com/path/to/document.pdf"},
    ]
}
```

### 音频输入

```python
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "描述这段音频的内容。"},
        {
            "type": "audio",
            "base64": "AAAAIGZ0eXBtcDQy...",
            "mime_type": "audio/wav"
        },
    ]
}
```

### 视频输入

```python
message = {
    "role": "user",
    "content": [
        {"type": "text", "text": "描述这个视频的内容。"},
        {
            "type": "video",
            "base64": "AAAAIGZ0eXBtcDQy...",
            "mime_type": "video/mp4"
        },
    ]
}
```

> ⚠️ 并非所有模型都支持所有文件类型。请查看模型提供商的文档了解支持的格式和大小限制。

## 内容块的标准化

不同提供商返回的内容格式可能不同，但 LangChain 的 `content_blocks` 属性会将它们解析为标准格式：

```python
from langchain.messages import AIMessage

# Anthropic 格式
message = AIMessage(
    content=[
        {"type": "thinking", "thinking": "...", "signature": "WaUjzkyp..."},
        {"type": "text", "text": "..."},
    ],
    response_metadata={"model_provider": "anthropic"}
)

# 访问标准化的内容块
print(message.content_blocks)
# [
#   {'type': 'reasoning', 'reasoning': '...', 'extras': {'signature': 'WaUjzkyp...'}},
#   {'type': 'text', 'text': '...'}
# ]
```

## 与聊天模型配合使用

聊天模型接受消息对象序列作为输入，返回 AIMessage 作为输出。交互通常是无状态的，因此简单的对话循环涉及使用不断增长的消息列表调用模型。

```python
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, AIMessage, SystemMessage

model = init_chat_model("gpt-4o")

# 维护对话历史
messages = [SystemMessage("你是一个有帮助的助手。")]

# 第一轮
messages.append(HumanMessage("你好！"))
response = model.invoke(messages)
messages.append(response)

# 第二轮
messages.append(HumanMessage("你能帮我写代码吗？"))
response = model.invoke(messages)
messages.append(response)

# messages 现在包含完整的对话历史
```

## 总结

| 消息类型 | 用途 | 角色 |
|----------|------|------|
| SystemMessage | 设置模型行为和上下文 | system |
| HumanMessage | 用户输入和交互 | user |
| AIMessage | 模型生成的响应 | assistant |
| ToolMessage | 工具执行结果 | tool |
