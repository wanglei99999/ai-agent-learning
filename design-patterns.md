# 设计模式学习笔记

> 记录学习过程中遇到的各种设计模式及其应用场景

---

## 📚 目录

1. [适配器模式 (Adapter Pattern)](#适配器模式)
2. [外观模式 (Facade Pattern)](#外观模式)

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
**在 HelloAgents 项目中的应用**：
- `MemoryTool` 适配 `MemoryManager` 到 `Tool` 接口
- 位置：`hello_agents/tools/builtin/memory_tool.py`

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

## 🎯 两种模式的对比

| 维度 | 适配器模式 | 外观模式 |
|------|-----------|---------|
| **目的** | 解决接口不兼容问题 | 简化复杂系统的使用 |
| **关注点** | 接口转换 | 提供统一入口 |
| **类比** | 充电器转换插头 | 医院导诊台 |
| **结构** | 包装一个对象 | 包装多个子系统 |
| **使用场景** | 两个系统接口不匹配 | 系统太复杂，需要简化 |

---

## 📝 学习心得

### MemoryTool 中的协作

在 `MemoryTool` 中，这两个模式完美配合：

1. **适配器模式**：
   - `MemoryTool` 继承 `Tool` 基类（目标接口）
   - 内部包含 `MemoryManager` 实例（被适配的对象）
   - 将 `Tool.run()` 的调用转换为 `MemoryManager` 的方法调用

2. **外观模式**：
   - `run()` 方法作为统一入口
   - 通过 `action` 参数路由到不同的内部方法
   - 隐藏了 9 种不同操作的复杂性

```python
class MemoryTool(Tool):  # ← 适配器：适配 Tool 接口
    
    def run(self, parameters):  # ← 外观：统一入口
        action = parameters.get("action")
        
        # 外观模式：一个方法处理多种操作
        if action == "add":
            return self._add_memory(...)
        elif action == "search":
            return self._search_memory(...)
    
    def _add_memory(self, ...):
        # 适配器模式：调用 MemoryManager
        return self.memory_manager.add_memory(...)
```

---

## 🔖 待学习的设计模式

- [ ] 单例模式 (Singleton Pattern)
- [ ] 工厂模式 (Factory Pattern)
- [ ] 观察者模式 (Observer Pattern)
- [ ] 策略模式 (Strategy Pattern)
- [ ] 装饰器模式 (Decorator Pattern)
- [ ] 代理模式 (Proxy Pattern)

---

**最后更新时间**：2026-01-27
