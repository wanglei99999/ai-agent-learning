# MCP 服务器详解

MCP 服务器是通过标准化协议接口向 AI 应用暴露特定能力的程序。常见的 MCP 服务器包括：文件系统服务器、数据库服务器、GitHub 服务器、Slack 服务器、日历服务器等。

> 本文内容基于 [MCP 官方文档](https://modelcontextprotocol.io) 整理，内容已重新组织以符合许可要求。

## 服务器核心功能

服务器通过三个构建块提供功能：

| 功能 | 说明 | 示例 | 控制方 |
|------|------|------|--------|
| Tools | LLM 可主动调用的函数，根据用户请求决定何时使用 | 搜索航班、发送消息、创建日历事件 | 模型 |
| Resources | 被动数据源，提供只读信息作为上下文 | 获取文档、访问知识库、读取日历 | 应用 |
| Prompts | 预构建的指令模板，指导模型使用特定工具和资源 | 规划假期、总结会议、起草邮件 | 用户 |

## Tools（工具）

工具让 AI 模型能够执行操作。每个工具定义一个具有类型化输入输出的特定操作。

### 工作原理

- 工具是 LLM 可调用的 schema 定义接口
- MCP 使用 JSON Schema 进行验证
- 每个工具执行单一操作，输入输出明确定义
- 工具执行前可能需要用户同意，确保用户对模型操作保持控制

### 协议操作

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `tools/list` | 发现可用工具 | 工具定义数组（含 schema） |
| `tools/call` | 执行特定工具 | 工具执行结果 |

### 工具定义示例

```typescript
{
  name: "searchFlights",
  description: "Search for available flights",
  inputSchema: {
    type: "object",
    properties: {
      origin: { type: "string", description: "Departure city" },
      destination: { type: "string", description: "Arrival city" },
      date: { type: "string", format: "date", description: "Travel date" }
    },
    required: ["origin", "destination", "date"]
  }
}
```

### 实际应用：旅行预订

工具让 AI 应用能代表用户执行操作：

```python
# 航班搜索
searchFlights(origin="NYC", destination="Barcelona", date="2024-06-15")
# 查询多家航空公司，返回结构化航班选项

# 日历阻塞
createCalendarEvent(title="Barcelona Trip", startDate="2024-06-15", endDate="2024-06-22")
# 在用户日历中标记旅行日期

# 邮件通知
sendEmail(to="team@work.com", subject="Out of Office", body="...")
# 向同事发送自动外出消息
```

### 用户交互模型

工具是模型控制的，AI 模型可以自动发现和调用。但 MCP 强调人类监督：

- 在 UI 中显示可用工具，让用户定义特定交互中是否可用
- 单个工具执行的审批对话框
- 预批准某些安全操作的权限设置
- 显示所有工具执行及结果的活动日志

## Resources（资源）

资源提供结构化的信息访问，AI 应用可以检索并作为上下文提供给模型。

### 工作原理

资源从文件、API、数据库或任何其他来源暴露数据。应用可以直接访问这些信息并决定如何使用——选择相关部分、使用嵌入搜索，或全部传递给模型。

每个资源有唯一的 URI（如 `file:///path/to/document.md`）并声明 MIME 类型。

### 发现模式

| 模式 | 说明 | 示例 |
|------|------|------|
| 直接资源 | 指向特定数据的固定 URI | `calendar://events/2024` |
| 资源模板 | 带参数的动态 URI | `travel://activities/{city}/{category}` |

资源模板包含元数据（标题、描述、MIME 类型），使其可发现且自文档化。

### 协议操作

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `resources/list` | 列出可用直接资源 | 资源描述符数组 |
| `resources/templates/list` | 发现资源模板 | 资源模板定义数组 |
| `resources/read` | 检索资源内容 | 带元数据的资源数据 |
| `resources/subscribe` | 监控资源变化 | 订阅确认 |

### 实际应用：获取旅行规划上下文

```python
# 日历数据 - 检查用户可用性
calendar://events/2024

# 旅行文档 - 访问重要文件
file:///Documents/Travel/passport.pdf

# 历史行程 - 参考过去的旅行和偏好
trips://history/barcelona-2023
```

AI 应用检索这些资源并决定如何处理——使用嵌入或关键词搜索选择子集，或直接传递原始数据给模型。

### 资源模板示例

```json
{
  "uriTemplate": "weather://forecast/{city}/{date}",
  "name": "weather-forecast",
  "title": "Weather Forecast",
  "description": "Get weather forecast for any city and date",
  "mimeType": "application/json"
}

{
  "uriTemplate": "travel://flights/{origin}/{destination}",
  "name": "flight-search",
  "title": "Flight Search",
  "description": "Search available flights between cities",
  "mimeType": "application/json"
}
```

### 参数补全

动态资源支持参数补全：

- 输入 "Par" 作为 `weather://forecast/{city}` 的输入，可能建议 "Paris" 或 "Park City"
- 输入 "JFK" 作为 `flights://search/{airport}` 的输入，可能建议 "JFK - John F. Kennedy International"

### 用户交互模型

资源是应用驱动的，在检索、处理和呈现可用上下文方面有灵活性：

- 树形或列表视图浏览资源
- 搜索和过滤界面查找特定资源
- 基于启发式或 AI 选择的自动上下文包含
- 单个或批量选择资源的界面

## Prompts（提示词）

提示词提供可复用的模板，允许 MCP 服务器作者为特定领域提供参数化提示词，或展示如何最佳使用 MCP 服务器。

### 工作原理

- 提示词是定义预期输入和交互模式的结构化模板
- 用户控制，需要显式调用而非自动触发
- 可感知上下文，引用可用资源和工具创建完整工作流
- 支持参数补全，帮助用户发现有效参数值

### 协议操作

| 方法 | 用途 | 返回值 |
|------|------|--------|
| `prompts/list` | 发现可用提示词 | 提示词描述符数组 |
| `prompts/get` | 获取提示词详情 | 完整提示词定义（含参数） |

### 提示词定义示例

```json
{
  "name": "plan-vacation",
  "title": "Plan a vacation",
  "description": "Guide through vacation planning process",
  "arguments": [
    { "name": "destination", "type": "string", "required": true },
    { "name": "duration", "type": "number", "description": "days" },
    { "name": "budget", "type": "number", "required": false },
    { "name": "interests", "type": "array", "items": { "type": "string" } }
  ]
}
```

### 使用流程

不同于非结构化的自然语言输入，提示词系统支持：

1. 选择 "Plan a vacation" 模板
2. 结构化输入：Barcelona, 7 天, $3000, ["beaches", "architecture", "food"]
3. 基于模板的一致工作流执行

### 用户交互模型

提示词是用户控制的，需要显式调用。常见 UI 模式：

- 斜杠命令（输入 "/" 查看可用提示词如 `/plan-vacation`）
- 可搜索的命令面板
- 常用提示词的专用 UI 按钮
- 建议相关提示词的上下文菜单

## 多服务器协作

MCP 的真正威力在于多个服务器协同工作，通过统一接口组合它们的专业能力。

### 示例：多服务器旅行规划

假设一个个性化 AI 旅行规划应用，连接三个服务器：

| 服务器 | 功能 |
|--------|------|
| Travel Server | 处理航班、酒店和行程 |
| Weather Server | 提供气候数据和预报 |
| Calendar/Email Server | 管理日程和通信 |

### 完整流程

**1. 用户调用带参数的提示词：**

```json
{
  "prompt": "plan-vacation",
  "arguments": {
    "destination": "Barcelona",
    "departure_date": "2024-06-15",
    "return_date": "2024-06-22",
    "budget": 3000,
    "travelers": 2
  }
}
```

**2. 用户选择要包含的资源：**

- `calendar://my-calendar/June-2024`（来自 Calendar Server）
- `travel://preferences/europe`（来自 Travel Server）
- `travel://past-trips/Spain-2023`（来自 Travel Server）

**3. AI 使用工具处理请求：**

AI 首先读取所有选定资源收集上下文——从日历识别可用日期，从旅行偏好了解首选航空公司和酒店类型，从过去旅行发现之前喜欢的地点。

使用这些上下文，AI 执行一系列工具：

```
searchFlights()      → 查询 NYC 到 Barcelona 的航班
checkWeather()       → 获取旅行日期的气候预报
bookHotel()          → 在预算内查找酒店（需用户批准）
createCalendarEvent() → 将行程添加到用户日历
sendEmail()          → 发送包含行程详情的确认邮件
```

**结果：** 通过多个 MCP 服务器，用户研究并预订了符合其日程的 Barcelona 之旅。"Plan a Vacation" 提示词引导 AI 跨不同服务器组合资源（日历可用性和旅行历史）与工具（搜索航班、预订酒店、更新日历）——收集上下文并执行预订。原本可能需要数小时的任务，使用 MCP 在几分钟内完成。

## 三大功能对比

| 维度 | Tools | Resources | Prompts |
|------|-------|-----------|---------|
| 性质 | 可执行函数 | 被动数据源 | 指令模板 |
| 控制方 | 模型 | 应用 | 用户 |
| 触发方式 | 模型自动决定 | 应用主动获取 | 用户显式调用 |
| 典型操作 | 写入、调用、修改 | 读取、检索 | 引导、组织 |
| 发现方法 | `tools/list` | `resources/list` | `prompts/list` |
| 执行方法 | `tools/call` | `resources/read` | `prompts/get` |

## 核心概念速查表

| 概念 | 说明 |
|------|------|
| Tools | 模型可调用的函数，执行实际操作 |
| Resources | 提供上下文的只读数据源 |
| Prompts | 用户调用的结构化模板 |
| URI | 资源的唯一标识符 |
| Resource Template | 带参数的动态资源 URI |
| Parameter Completion | 参数值的自动补全建议 |
| 模型控制 | 模型自动决定何时使用（Tools） |
| 应用控制 | 应用决定如何获取和处理（Resources） |
| 用户控制 | 需要用户显式调用（Prompts） |

## 参考链接

- [MCP 官方文档](https://modelcontextprotocol.io)
- [MCP Server Concepts](https://modelcontextprotocol.io/docs/concepts/servers)
