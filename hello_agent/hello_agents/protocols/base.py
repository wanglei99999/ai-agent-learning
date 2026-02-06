"""协议基类（概念性）

本模块定义了协议的基本接口概念。
实际实现中，各协议根据自己的特点独立实现，不强制继承这个基类。

协议接口概念：
- 协议标识：每个协议有唯一的名称和版本
- 消息传递：支持发送和接收消息
- 信息查询：可以获取协议的基本信息

实际使用：
- MCP: 使用 fastmcp 库实现
- A2A: 使用官方 a2a 库实现
- ANP: 使用概念性实现

注意：这个基类主要用于文档说明，实际协议实现不需要继承它。
"""

from enum import Enum


class ProtocolType(Enum):
    """协议类型枚举
    
    【学习笔记】
    Enum（枚举）是 Python 中定义一组固定常量的方式。
    使用枚举而非字符串常量的好处：
    - 类型安全：IDE 可以自动补全和检查
    - 防止拼写错误：ProtocolType.MCP 比 "mcp" 更不容易出错
    - 可迭代：可以用 for p in ProtocolType 遍历所有协议类型
    
    三种协议的定位：
    - MCP: "工具调用协议" — LLM 通过它调用外部工具和获取数据（类似给 AI 装上手和眼睛）
    - A2A: "Agent 对话协议" — 多个 Agent 之间互相发消息、协作完成任务
    - ANP: "Agent 网络协议" — 更底层的网络发现和通信机制
    """
    MCP = "mcp"  # Model Context Protocol — LLM ↔ 工具/数据源
    A2A = "a2a"  # Agent-to-Agent Protocol — Agent ↔ Agent
    ANP = "anp"  # Agent Network Protocol — Agent 网络层通信


# 为了向后兼容，保留 Protocol 类的定义
# 但标记为概念性，不建议实际使用
class Protocol:
    """协议基类（概念性，不建议继承）
    
    这个类定义了协议的基本概念，但实际实现不需要继承它。
    各协议根据自己的特点独立实现。
    
    【学习笔记 - 设计思路】
    这是一种 "文档型基类" 设计：
    - 它展示了协议应该具备的基本属性（名称、版本）
    - 但不强制继承，因为 MCP/A2A/ANP 各自依赖不同的第三方库
      (MCP 用 fastmcp, A2A 用官方 a2a 库)，强制统一接口反而增加复杂度
    - 如果你想了解实际实现，请查看 protocols/mcp/、protocols/a2a/、protocols/anp/ 目录
    
    【学习笔记 - Python 语法要点】
    - @property 装饰器：将方法变成只读属性，调用时不需要加括号
      例如: p.protocol_name 而不是 p.protocol_name()
    - _前缀变量（如 self._version）：Python 约定的 "私有" 变量，
      外部不应直接访问，而是通过 @property 提供的接口访问
    - __str__ 和 __repr__：Python 的魔术方法，
      分别控制 print(obj) 和交互式环境中显示对象时的输出格式
    """
    
    def __init__(self, protocol_type: ProtocolType, version: str = "1.0.0"):
        """初始化协议
        
        Args:
            protocol_type: 协议类型
            version: 协议版本
        """
        self._protocol_type = protocol_type
        self._version = version
    
    @property
    def protocol_name(self) -> str:
        """获取协议名称"""
        return self._protocol_type.value
    
    @property
    def version(self) -> str:
        """获取协议版本"""
        return self._version
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(protocol={self.protocol_name}, version={self.version})"
    
    def __repr__(self) -> str:
        return self.__str__()

