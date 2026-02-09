# 设计模式学习笔记

> 记录学习过程中遇到的各种设计模式及其应用场景

---

## 📚 目录

1. [适配器模式 (Adapter Pattern)](#适配器模式)
2. [外观模式 (Facade Pattern)](#外观模式)
3. [策略模式 (Strategy Pattern)](#策略模式)
4. [装饰器模式 (Decorator Pattern)](#装饰器模式)
5. [建造者模式 (Builder Pattern)](#建造者模式)

---

## 🔌 适配器模式 (Adapter Pattern)

### 定义
适配器模式是一种结构型设计模式，它能使接口不兼容的对象能够相互合作。

### 核心思想
让两个不兼容的接口能够一起工作，通过创建一个适配器类来转换接口。

### 生活中的例子
- **充电器转换插头**：中国的两脚插头 → 转换插头 → 美国的三脚插座
- **语言翻译**：中文 → 翻译官 → 英文

### 代码示例

```python
# 原有的类（不兼容的接口）
class MemoryManager:
    def add_memory(self, content, memory_type, importance, metadata):
        pass
    
    def retrieve_memories(self, query, limit, memory_types):
        pass

# 目标接口（需要适配的接口）
class Tool:
    def run(self, parameters: Dict[str, Any]) -> str:
        pass
    
    def get_parameters(self) -> List[ToolParameter]:
        pass

# 适配器类
class MemoryTool(Tool):
    def __init__(self):
        self.memory_manager = MemoryManager()  # 包含原有对象
    
    def run(self, parameters):
        # 将 Tool 接口的调用转换为 MemoryManager 接口的调用
        action = parameters.get("action")
        if action == "add":
            return self.memory_manager.add_memory(
                content=parameters.get("content"),
                memory_type=parameters.get("memory_type"),
                importance=parameters.get("importance"),
                metadata={}
            )
```

### 应用场景
- 需要使用一个已存在的类，但其接口不符合需求
- 想创建一个可复用的类，该类可以与其他不相关的类协同工作
- 需要使用多个已存在的子类，但不可能对每一个都进行子类化以匹配接口

### 优点
- 单一职责原则：可以将接口转换代码从业务逻辑中分离
- 开闭原则：可以在不修改现有代码的情况下引入新的适配器

### 缺点
- 代码整体复杂度增加，需要新增一系列接口和类

### 实际应用

**案例 1：MemoryTool 适配器**
- `MemoryTool` 适配 `MemoryManager` 到 `Tool` 接口
- 位置：`hello_agents/tools/builtin/memory_tool.py`

**案例 2：MCP 协议层适配器**
- `MCPClient` 适配 FastMCP Client 到项目统一接口
- `MCPServer` 适配 FastMCP Server 到项目统一接口
- 位置：`hello_agents/protocols/mcp/client.py`、`hello_agents/protocols/mcp/server.py`

```
上层代码（Agent/LLM）
    ↓ 简单的字典和字符串
MCPClient / MCPServer（适配器层）
    ↓ 复杂的协议对象（ToolResult、ResourceResult 等）
FastMCP（第三方库）
    ↓ JSON-RPC
MCP 协议通信
```

```python
# MCPClient 作为适配器的体现：

# FastMCP 原生用法（复杂）：
from fastmcp.client.transports import PythonStdioTransport
transport = PythonStdioTransport(script_path="server.py")
client = Client(transport)
async with client:
    result = await client.call_tool("calculator", {"expression": "1+1"})
    text = result.content[0].text  # 需要手动解析嵌套结构

# MCPClient 适配后（简洁）：
async with MCPClient("server.py") as client:  # 智能推断传输方式
    result = await client.call_tool("calculator", {"expression": "1+1"})
    # result 直接就是 "Result: 2"，已经帮你解析好了
```

**适配器的价值**：
- 上层代码不依赖 FastMCP，将来换库只需改适配器层
- 智能推断传输方式，简化使用
- 统一结果格式，隐藏 FastMCP 复杂的返回值结构

---

## 🏢 外观模式 (Facade Pattern)

### 定义
外观模式是一种结构型设计模式，为子系统中的一组接口提供一个统一的高层接口，使子系统更容易使用。

### 核心思想
为复杂的子系统提供一个简单统一的接口，隐藏系统的复杂性。

### 生活中的例子
- **医院导诊台**：患者只需告诉导诊台症状，导诊台会安排挂号、检验、拍片等所有流程
- **智能家居控制面板**：一个按钮控制灯光、空调、窗帘等多个设备
- **餐厅服务员**：顾客只需点菜，服务员会协调厨房、传菜、收银等多个部门

### 代码示例

```python
# 没有外观模式 - 复杂的调用
agent.add_tool(AddMemoryTool())
agent.add_tool(SearchMemoryTool())
agent.add_tool(UpdateMemoryTool())
agent.add_tool(RemoveMemoryTool())
agent.add_tool(ForgetMemoryTool())
agent.add_tool(ConsolidateMemoryTool())
# ... 需要管理 9 个不同的工具

# 使用外观模式 - 简化的调用
agent.add_tool(MemoryTool())  # 只需要一个工具

# 通过统一的接口访问不同功能
class MemoryTool(Tool):
    def run(self, parameters):
        action = parameters.get("action")
        
        # 一个入口，多种操作
        if action == "add":
            return self._add_memory(...)
        elif action == "search":
            return self._search_memory(...)
        elif action == "update":
            return self._update_memory(...)
        # ... 9 种操作通过一个方法路由
```

### 应用场景
- 需要为复杂的子系统提供一个简单接口
- 客户端与多个子系统之间存在很大的依赖性
- 需要构建一个层次结构的子系统

### 优点
- 简化了客户端的使用，降低了系统的复杂度
- 实现了子系统与客户端之间的松耦合
- 更好的划分访问层次

### 缺点
- 不符合开闭原则，修改很麻烦
- 某些情况下可能违背单一职责原则

### 实际应用
**在 HelloAgents 项目中的应用**：
- `MemoryTool.run()` 方法通过 `action` 参数提供统一入口
- 9 种记忆操作（add/search/update/remove/forget/consolidate/stats/summary/clear_all）通过一个接口访问
- 位置：`hello_agents/tools/builtin/memory_tool.py`

### 路由表
```python
action="add"         → _add_memory()
action="search"      → _search_memory()
action="summary"     → _get_summary()
action="stats"       → _get_stats()
action="update"      → _update_memory()
action="remove"      → _remove_memory()
action="forget"      → _forget()
action="consolidate" → _consolidate()
action="clear_all"   → _clear_all()
```

---

## 🎲 策略模式 (Strategy Pattern)

### 定义
策略模式是一种行为型设计模式，它定义了一系列算法，并将每个算法封装起来，使它们可以相互替换，且算法的变化不会影响使用算法的客户。

### 核心思想
将不同的算法封装成独立的策略类，通过统一的接口调用，客户端可以动态选择使用哪种算法。

### 生活中的例子
- **出行方式选择**：去同一个目的地，可以选择开车、坐地铁、骑自行车、打车等不同策略
- **支付方式**：购物结账时，可以选择微信支付、支付宝、信用卡等不同支付策略
- **排序算法**：对数据排序，可以选择快速排序、归并排序、冒泡排序等不同策略

### 代码示例

```python
# 策略接口（统一的方法签名）
class MemoryBase:
    def retrieve(self, query, limit, min_importance, user_id):
        """所有记忆类型都实现这个方法"""
        raise NotImplementedError

# 具体策略1：工作记忆 - TF-IDF 检索
class WorkingMemory(MemoryBase):
    def retrieve(self, query, limit, min_importance, user_id):
        # 策略1的具体实现
        # 使用 TF-IDF 算法
        # 纯内存检索
        results = self._tfidf_search(query)
        return results

# 具体策略2：情景记忆 - 向量检索
class EpisodicMemory(MemoryBase):
    def retrieve(self, query, limit, min_importance, user_id):
        # 策略2的具体实现
        # 使用 Qdrant 向量数据库
        # 语义相似度检索
        results = self.qdrant_store.search(query)
        return results

# 具体策略3：语义记忆 - 知识图谱查询
class SemanticMemory(MemoryBase):
    def retrieve(self, query, limit, min_importance, user_id):
        # 策略3的具体实现
        # 使用知识图谱
        # 关系推理
        results = self._graph_query(query)
        return results

# 上下文类：MemoryManager
class MemoryManager:
    def __init__(self):
        # 存储不同的策略实例
        self.memory_types = {
            'working': WorkingMemory(),    # 策略1
            'episodic': EpisodicMemory(),  # 策略2
            'semantic': SemanticMemory()   # 策略3
        }
    
    def retrieve_memories(self, query, memory_types=None, limit=10):
        """动态选择和使用策略"""
        all_results = []
        
        # 如果未指定，使用所有策略
        if memory_types is None:
            memory_types = list(self.memory_types.keys())
        
        # 遍历选中的策略
        for memory_type in memory_types:
            memory_instance = self.memory_types[memory_type]
            
            # 调用策略方法（多态）
            results = memory_instance.retrieve(
                query=query,
                limit=limit,
                min_importance=0.0,
                user_id=self.user_id
            )
            all_results.extend(results)
        
        return all_results
```

### 应用场景
- 系统需要在多种算法中动态选择一种
- 一个类定义了多种行为，这些行为在类的方法中以多个条件语句的形式出现
- 算法需要独立于使用它的客户而变化

### 优点
- **开闭原则**：添加新策略不需要修改上下文代码
- **避免条件语句**：消除大量的 if-else 或 switch-case
- **算法独立**：每个策略可以独立演化和测试
- **运行时切换**：可以在运行时动态选择算法

### 缺点
- 客户端必须了解所有策略的区别，以便选择合适的策略
- 策略类数量增多，增加了系统复杂度

### 实际应用

**在 HelloAgents 项目中的应用**：
- `MemoryManager` 管理多种记忆检索策略
- 位置：`hello_agents/memory/manager.py`

**不同记忆类型的检索策略**：

| 记忆类型 | 检索策略 | 存储方式 | 适用场景 |
|---------|---------|---------|---------|
| **Working** | TF-IDF + 关键词匹配 | 纯内存 | 短期上下文 |
| **Episodic** | 向量语义检索 | SQLite + Qdrant | 历史事件 |
| **Semantic** | 知识图谱查询 | 图数据库 | 知识概念 |
| **Perceptual** | 多模态检索 | 文件系统 + 向量 | 图片/音频 |

**核心代码**：
```python
# manager.py 第 245-264 行
for memory_type in memory_types:
    if memory_type in self.memory_types:
        memory_instance = self.memory_types[memory_type]  # 获取策略
        try:
            # 调用策略方法（多态）
            # 不同类型有不同的检索策略
            type_results = memory_instance.retrieve(
                query=query,
                limit=per_type_limit,
                min_importance=min_importance,
                user_id=self.user_id
            )
            all_results.extend(type_results)
        except Exception as e:
            logger.warning(f"检索 {memory_type} 记忆时出错: {e}")
```

### 策略模式的三要素

1. **策略接口（Strategy Interface）**
   - 所有记忆类型都实现 `retrieve()` 方法
   - 统一的方法签名

2. **具体策略（Concrete Strategies）**
   - `WorkingMemory.retrieve()` - TF-IDF 算法
   - `EpisodicMemory.retrieve()` - 向量检索
   - `SemanticMemory.retrieve()` - 图查询

3. **上下文（Context）**
   - `MemoryManager` 持有策略实例
   - 通过 `memory_types` 参数动态选择策略

### 扩展性示例

```python
# 添加新策略非常容易
class VectorMemory(MemoryBase):  # 新策略
    def retrieve(self, query, limit, ...):
        # 使用新的向量检索算法
        return results

# 只需在 MemoryManager 中注册
manager.memory_types['vector'] = VectorMemory()

# 不需要修改 retrieve_memories() 的代码！
# 直接使用新策略
manager.retrieve_memories(query="...", memory_types=['vector'])
```

---

## � 装饰器模式 (Decorator Pattern)

### 定义
装饰器模式是一种结构型设计模式，允许向一个现有的对象动态添加新的功能，同时又不改变其结构。这种模式创建了一个装饰类，用来包装原有的类，并在保持类方法签名完整性的前提下，提供了额外的功能。

### 核心思想
在不修改原有对象的基础上，通过包装的方式为对象动态添加新功能。装饰器与被装饰对象实现相同的接口，可以层层嵌套。

### 生活中的例子
- **咖啡加料**：基础咖啡 → 加牛奶 → 加糖 → 加巧克力，每次加料都是一次装饰
- **手机壳**：手机 → 保护壳 → 支架功能 → 卡包功能，每个配件都增强了功能
- **房屋装修**：毛坯房 → 刷漆 → 贴壁纸 → 挂画，逐步增加装饰

### Python 装饰器语法

Python 提供了语法糖 `@decorator` 来简化装饰器的使用：

```python
# 装饰器函数
def tool_action(name: str, description: str):
    """装饰器：为方法添加工具元数据"""
    def decorator(func):
        # 为函数添加属性（装饰）
        func._is_tool_action = True
        func._tool_name = name
        func._tool_description = description
        return func
    return decorator

# 使用装饰器
class MemoryTool:
    @tool_action("memory_add", "添加新记忆")
    def _add_memory(self, content: str, importance: float = 0.5):
        """添加记忆到系统"""
        return self.memory_manager.add_memory(content, importance)
    
    @tool_action("memory_search", "搜索相关记忆")
    def _search_memory(self, query: str, limit: int = 5):
        """搜索记忆"""
        return self.memory_manager.retrieve_memories(query, limit)

# 等价于（不使用语法糖）
class MemoryTool:
    def _add_memory(self, content: str, importance: float = 0.5):
        return self.memory_manager.add_memory(content, importance)
    
    # 手动装饰
    _add_memory = tool_action("memory_add", "添加新记忆")(_add_memory)
```

### 代码示例

**完整的装饰器实现**：

```python
# base.py - 装饰器定义
def tool_action(name: str = None, description: str = None):
    """装饰器：标记一个方法为可展开的工具 action
    
    这个装饰器为方法添加元数据，使其可以被自动识别和展开为独立工具
    """
    def decorator(func: Callable):
        # 添加标记属性
        func._is_tool_action = True      # 标记这是一个工具方法
        func._tool_name = name           # 工具名称
        func._tool_description = description  # 工具描述
        return func  # 返回被装饰的函数
    return decorator

# 使用装饰器
class MemoryTool(Tool):
    @tool_action("memory_add", "添加新记忆到记忆系统中")
    def _add_memory(self, content: str, memory_type: str = "working", 
                    importance: float = 0.5) -> str:
        """添加记忆"""
        memory_id = self.memory_manager.add_memory(
            content=content,
            memory_type=memory_type,
            importance=importance
        )
        return f"记忆已添加 (ID: {memory_id[:8]}...)"
    
    @tool_action("memory_search", "搜索相关记忆")
    def _search_memory(self, query: str, limit: int = 5) -> str:
        """搜索记忆"""
        results = self.memory_manager.retrieve_memories(query, limit)
        return self._format_results(results)

# 自动识别被装饰的方法
class Tool:
    def get_expanded_tools(self):
        """自动从装饰器标记的方法生成子工具"""
        tools = []
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            # 检查方法是否被 @tool_action 装饰
            if hasattr(method, '_is_tool_action'):
                # 自动生成独立工具
                tool = AutoGeneratedTool(
                    parent=self,
                    method=method,
                    name=method._tool_name,
                    description=method._tool_description
                )
                tools.append(tool)
        return tools
```

### 应用场景
- 需要在运行时动态添加功能
- 需要为对象添加多个可选功能，且功能可以组合
- 不想通过继承来扩展功能（避免类爆炸）
- 需要撤销某些功能

### 优点
- **开闭原则**：无需修改原有代码即可扩展功能
- **灵活组合**：可以动态组合多个装饰器
- **单一职责**：每个装饰器只负责一个功能
- **可撤销**：可以动态添加或移除装饰

### 缺点
- 多层装饰会增加代码复杂度
- 装饰器顺序可能影响结果
- 调试时难以追踪装饰链

### 实际应用

**在 HelloAgents 项目中的应用**：
- `@tool_action` 装饰器为方法添加工具元数据
- 位置：`hello_agents/tools/base.py`

**装饰器的作用**：

1. **元数据注入**
   ```python
   @tool_action("memory_add", "添加新记忆")
   def _add_memory(self, ...):
       pass
   
   # 装饰后，方法获得新属性：
   # _add_memory._is_tool_action = True
   # _add_memory._tool_name = "memory_add"
   # _add_memory._tool_description = "添加新记忆"
   ```

2. **自动工具生成**
   ```python
   # 当 expandable=True 时
   tool = MemoryTool(expandable=True)
   expanded_tools = tool.get_expanded_tools()
   
   # 返回：
   # [
   #   AutoGeneratedTool(name="memory_add", ...),
   #   AutoGeneratedTool(name="memory_search", ...),
   #   AutoGeneratedTool(name="memory_update", ...),
   #   ...
   # ]
   ```

3. **功能增强**
   - 原方法：`_add_memory()` - 普通方法
   - 装饰后：可以被自动识别、展开为独立工具、生成 OpenAI schema

### 装饰器模式 vs 继承

| 对比项 | 装饰器模式 | 继承 |
|-------|-----------|------|
| **扩展方式** | 运行时动态添加 | 编译时静态定义 |
| **灵活性** | 高，可以任意组合 | 低，继承关系固定 |
| **类数量** | 少，通过组合实现 | 多，容易类爆炸 |
| **功能撤销** | 可以动态移除 | 不可撤销 |
| **适用场景** | 需要动态、可选的功能 | 需要固定的功能扩展 |

### 多层装饰示例

```python
# 可以叠加多个装饰器
@log_execution  # 装饰器3：记录执行日志
@validate_params  # 装饰器2：验证参数
@tool_action("memory_add", "添加记忆")  # 装饰器1：添加工具元数据
def _add_memory(self, content: str):
    return self.memory_manager.add_memory(content)

# 执行顺序（从下到上）：
# 1. tool_action 装饰
# 2. validate_params 装饰
# 3. log_execution 装饰
```

### 实际效果对比

**不使用装饰器**：
```python
class MemoryTool(Tool):
    def _add_memory(self, content: str):
        return self.memory_manager.add_memory(content)
    
    def _search_memory(self, query: str):
        return self.memory_manager.retrieve_memories(query)
    
    # 需要手动注册每个方法
    def get_expanded_tools(self):
        return [
            ManualTool(name="memory_add", method=self._add_memory, ...),
            ManualTool(name="memory_search", method=self._search_memory, ...),
            # 每个方法都要手动注册，容易遗漏
        ]
```

**使用装饰器**：
```python
class MemoryTool(Tool):
    @tool_action("memory_add", "添加记忆")
    def _add_memory(self, content: str):
        return self.memory_manager.add_memory(content)
    
    @tool_action("memory_search", "搜索记忆")
    def _search_memory(self, query: str):
        return self.memory_manager.retrieve_memories(query)
    
    # 自动识别所有被装饰的方法，无需手动注册
    # get_expanded_tools() 由父类自动实现
```

---

## 🔨 建造者模式 (Builder Pattern)

### 定义
建造者模式是一种创建型设计模式，它将一个复杂对象的构建过程与其表示分离，使得同样的构建过程可以创建不同的表示。

### 核心思想
将复杂对象的创建过程分解为多个简单步骤，通过链式调用逐步配置，最后一次性构建出完整对象。

### 生活中的例子
- **定制汉堡**：选面包 → 选肉饼 → 选配菜 → 选酱料 → 出餐，每步可选可不选
- **装修房子**：选地板 → 选墙漆 → 选家具 → 选灯具 → 完工，按需定制
- **组装电脑**：选 CPU → 选显卡 → 选内存 → 选硬盘 → 装机，灵活搭配

### 代码示例

```python
# MCPServerBuilder - 建造者模式的实际应用

class MCPServerBuilder:
    """MCP 服务器建造者，支持链式调用"""
    
    def __init__(self, name: str):
        self.name = name
        self._tools = []        # 待注册的工具
        self._resources = []    # 待注册的资源
        self._prompts = []      # 待注册的提示词
    
    def with_tool(self, func, name=None, description=None):
        """添加工具（链式调用，返回 self）"""
        self._tools.append({"func": func, "name": name, "description": description})
        return self  # 关键：返回 self，支持链式调用
    
    def with_resource(self, func, uri=None, name=None):
        """添加资源（链式调用，返回 self）"""
        self._resources.append({"func": func, "uri": uri, "name": name})
        return self  # 关键：返回 self
    
    def with_prompt(self, func, name=None, description=None):
        """添加提示词（链式调用，返回 self）"""
        self._prompts.append({"func": func, "name": name, "description": description})
        return self  # 关键：返回 self
    
    def build(self) -> MCPServer:
        """终结方法：构建并返回 MCPServer 实例"""
        server = MCPServer(self.name)
        for tool in self._tools:
            server.add_tool(**tool)
        for resource in self._resources:
            server.add_resource(**resource)
        for prompt in self._prompts:
            server.add_prompt(**prompt)
        return server
```

### 链式调用的使用

```python
# 不用建造者模式（传统方式）：
server = MCPServer("my-server")
server.add_tool(calculator, name="calculator", description="计算器")
server.add_tool(greet, name="greet", description="打招呼")
server.add_resource(get_config, uri="config://app")
server.run()

# 使用建造者模式（链式调用）：
server = (MCPServerBuilder("my-server")
    .with_tool(calculator, name="calculator", description="计算器")
    .with_tool(greet, name="greet", description="打招呼")
    .with_resource(get_config, uri="config://app")
    .build())
server.run()
```

### 链式调用的原理

```python
# 为什么能链式调用？因为每个方法都 return self

builder = MCPServerBuilder("my-server")  # 返回 builder 实例
builder = builder.with_tool(calculator)   # 返回 self（还是同一个 builder）
builder = builder.with_tool(greet)        # 返回 self（还是同一个 builder）
server = builder.build()                  # 终结方法，返回 MCPServer

# 所以可以连起来写：
server = MCPServerBuilder("my-server").with_tool(calculator).with_tool(greet).build()
```

### 应用场景
- 需要创建的对象有很多可选配置项
- 对象的创建过程需要多个步骤
- 想要创建不可变对象（构建完成后不再修改）
- 构造函数参数过多，难以阅读

### 优点
- **可读性好**：链式调用清晰表达构建意图
- **灵活配置**：每个步骤可选，按需组合
- **构建与表示分离**：同样的构建过程可以创建不同配置的对象
- **避免构造函数爆炸**：不需要写一个有 10 个参数的构造函数

### 缺点
- 需要额外创建 Builder 类，增加代码量
- 如果对象结构简单，使用建造者模式反而过度设计

### 实际应用

**在 HelloAgents 项目中的应用**：
- `MCPServerBuilder` 用于链式构建 MCP 服务器
- 位置：`hello_agents/protocols/mcp/server.py`

### 建造者模式的两种方法

| 方法类型 | 特点 | 返回值 | 示例 |
|---------|------|--------|------|
| **配置方法** | 设置参数，可链式调用 | `return self` | `with_tool()`, `with_resource()` |
| **终结方法** | 执行构建，结束链式调用 | 构建的对象 | `build()`, `run()` |

### 建造者模式 vs 直接构造

```python
# 直接构造：参数多时难以阅读
server = MCPServer(
    name="my-server",
    tools=[calculator, greet, translator],
    resources=[get_config, get_status],
    prompts=[code_review_prompt],
    transport="http",
    host="0.0.0.0",
    port=8080
)

# 建造者模式：每步清晰，按需配置
server = (MCPServerBuilder("my-server")
    .with_tool(calculator)
    .with_tool(greet)
    .with_tool(translator)
    .with_resource(get_config)
    .with_resource(get_status)
    .with_prompt(code_review_prompt)
    .build())
```

---

##  五种模式的对比

| 维度 | 适配器模式 | 外观模式 | 策略模式 | 装饰器模式 | 建造者模式 |
|------|-----------|---------|---------|-----------|----------|
| **类型** | 结构型 | 结构型 | 行为型 | 结构型 | 创建型 |
| **目的** | 解决接口不兼容问题 | 简化复杂系统的使用 | 封装算法，使其可互换 | 动态添加功能 | 分步构建复杂对象 |
| **关注点** | 接口转换 | 提供统一入口 | 算法选择 | 功能增强 | 对象创建过程 |
| **类比** | 充电器转换插头 | 医院导诊台 | 出行方式选择 | 咖啡加料 | 定制汉堡 |
| **结构** | 包装一个对象 | 包装多个子系统 | 封装多个算法 | 层层包装对象 | 链式配置 + 终结构建 |
| **使用场景** | 两个系统接口不匹配 | 系统太复杂，需要简化 | 需要动态选择算法 | 需要动态添加功能 | 对象配置项多且可选 |
| **核心特征** | 转换接口 | 简化调用 | 运行时切换 | 运行时增强 | 链式调用 + return self |

---

## 📝 学习心得

### 五种模式在项目中的协作

在 HelloAgents 项目中，这五种模式各司其职，形成了清晰的层次结构：

#### 1. **适配器模式（MemoryTool）**
- `MemoryTool` 继承 `Tool` 基类（目标接口）
- 内部包含 `MemoryManager` 实例（被适配的对象）
- 将 `Tool.run()` 的调用转换为 `MemoryManager` 的方法调用

#### 2. **外观模式（MemoryTool）**
- `run()` 方法作为统一入口
- 通过 `action` 参数路由到不同的内部方法
- 隐藏了 9 种不同操作的复杂性

#### 3. **策略模式（MemoryManager）**
- 管理多种记忆类型（WorkingMemory、EpisodicMemory 等）
- 每种类型使用不同的检索策略
- 通过 `memory_types` 参数动态选择策略

#### 4. **装饰器模式（@tool_action）**
- 为 MemoryTool 的方法添加元数据
- 支持自动工具展开功能
- 无需修改原方法即可增强功能

#### 5. **建造者模式（MCPServerBuilder）**
- 链式调用逐步配置 MCP 服务器
- 将复杂的服务器创建过程分解为简单步骤
- 位置：`hello_agents/protocols/mcp/server.py`

### 完整的调用链路

```python
# 层次1：Agent 调用 MemoryTool
agent.run({"action": "search", "query": "用户喜好"})
    ↓
# 层次2：MemoryTool（适配器 + 外观）
class MemoryTool(Tool):  # ← 适配器：适配 Tool 接口
    
    def run(self, parameters):  # ← 外观：统一入口
        action = parameters.get("action")
        
        # 外观模式：路由到具体方法
        if action == "search":
            return self._search_memory(...)
    
    def _search_memory(self, query, memory_types, ...):
        # 适配器模式：调用 MemoryManager
        results = self.memory_manager.retrieve_memories(
            query=query,
            memory_types=memory_types
        )
        return formatted_results
    ↓
# 层次3：MemoryManager（策略模式）
class MemoryManager:
    def retrieve_memories(self, query, memory_types=None, ...):
        all_results = []
        
        # 策略模式：遍历并调用不同策略
        for memory_type in memory_types:
            memory_instance = self.memory_types[memory_type]  # 获取策略
            results = memory_instance.retrieve(...)  # 调用策略方法
            all_results.extend(results)
        
        return all_results
    ↓
# 层次4：具体策略实现
WorkingMemory.retrieve()   → TF-IDF 算法
EpisodicMemory.retrieve()  → Qdrant 向量检索
SemanticMemory.retrieve()  → 知识图谱查询
```

### 设计优势

这种多模式组合带来的好处：

1. **清晰的职责分离**
   - MemoryTool：接口适配 + 操作路由
   - MemoryManager：策略管理 + 结果聚合
   - 具体记忆类型：算法实现

2. **高度可扩展**
   - 添加新操作：在 MemoryTool 中添加新的 action
   - 添加新策略：在 MemoryManager 中注册新的记忆类型
   - 优化算法：修改具体策略类，不影响其他层

3. **易于维护**
   - 每个模式解决特定问题
   - 修改影响范围小
   - 代码结构清晰

---

## 🔖 待学习的设计模式

- [ ] 单例模式 (Singleton Pattern)
- [ ] 工厂模式 (Factory Pattern)
- [ ] 观察者模式 (Observer Pattern)
- [x] ~~策略模式 (Strategy Pattern)~~ ✅
- [x] ~~装饰器模式 (Decorator Pattern)~~ ✅
- [x] ~~建造者模式 (Builder Pattern)~~ ✅
- [ ] 代理模式 (Proxy Pattern)

---

**最后更新时间**：2026-02-09
