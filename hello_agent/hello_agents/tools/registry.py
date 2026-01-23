"""工具注册表 - HelloAgents原生工具系统"""

from typing import Optional, Any, Callable
from .base import Tool

class ToolRegistry:
    """
    HelloAgents工具注册表

    提供工具的注册、管理和执行功能。
    
    支持两种工具注册方式：
    1. Tool对象注册（推荐）- 功能完整，支持参数定义、类型转换等
    2. 函数直接注册（简便）- 快速注册简单工具，接受字符串参数
    
    Attributes:
        _tools: 存储已注册的Tool对象，key为工具名称
        _functions: 存储已注册的函数工具，key为工具名称，value包含描述和函数
    """

    def __init__(self):
        """初始化工具注册表"""
        self._tools: dict[str, Tool] = {}  # Tool对象存储
        self._functions: dict[str, dict[str, Any]] = {}  # 函数工具存储

    def register_tool(self, tool: Tool, auto_expand: bool = True):
        """
        注册Tool对象到注册表
        
        如果工具是可展开的（包含多个@tool_action装饰的方法），
        会自动将其展开为多个独立的子工具分别注册。

        Args:
            tool: Tool实例，要注册的工具对象
            auto_expand: 是否自动展开可展开的工具（默认True）
                        设置为False时，即使工具可展开也不会展开
        """
        # 检查工具是否可展开
        if auto_expand and hasattr(tool, 'expandable') and tool.expandable:
            expanded_tools = tool.get_expanded_tools()
            if expanded_tools:
                # 注册所有展开的子工具
                for sub_tool in expanded_tools:
                    if sub_tool.name in self._tools:
                        print(f"警告：工具 '{sub_tool.name}' 已存在，将被覆盖。")
                    self._tools[sub_tool.name] = sub_tool
                print(f"工具 '{tool.name}' 已展开为 {len(expanded_tools)} 个独立工具")
                return

        # 普通工具或不展开的工具
        if tool.name in self._tools:
            print(f"警告：工具 '{tool.name}' 已存在，将被覆盖。")

        self._tools[tool.name] = tool
        print(f"工具 '{tool.name}' 已注册。")

    def register_function(self, name: str, description: str, func: Callable[[str], str]):
        """
        直接注册函数作为工具（简便方式）
        
        适用于简单工具的快速注册，函数签名固定为接受字符串参数并返回字符串结果。
        如果需要更复杂的参数定义，请使用Tool对象注册。

        Args:
            name: 工具名称，用于标识和调用工具
            description: 工具描述，说明工具的功能
            func: 工具函数，签名为 (str) -> str
        """
        if name in self._functions:
            print(f"警告：工具 '{name}' 已存在，将被覆盖。")

        self._functions[name] = {
            "description": description,
            "func": func
        }
        print(f"工具 '{name}' 已注册。")

    def unregister(self, name: str):
        """
        注销指定名称的工具
        
        从注册表中移除工具，支持Tool对象和函数工具。
        
        Args:
            name: 要注销的工具名称
        """
        if name in self._tools:
            del self._tools[name]
            print(f"工具 '{name}' 已注销。")
        elif name in self._functions:
            del self._functions[name]
            print(f"工具 '{name}' 已注销。")
        else:
            print(f"警告：工具 '{name}' 不存在。")

    def get_tool(self, name: str) -> Optional[Tool]:
        """
        获取指定名称的Tool对象
        
        Args:
            name: 工具名称
            
        Returns:
            Tool对象，如果不存在则返回None
        """
        return self._tools.get(name)

    def get_function(self, name: str) -> Optional[Callable]:
        """
        获取指定名称的工具函数
        
        Args:
            name: 工具名称
            
        Returns:
            工具函数，如果不存在则返回None
        """
        func_info = self._functions.get(name)
        return func_info["func"] if func_info else None

    def execute_tool(self, name: str, input_text: str) -> str:
        """
        执行指定名称的工具
        
        优先查找Tool对象，如果不存在则查找函数工具。
        执行过程中的异常会被捕获并返回错误信息。

        Args:
            name: 工具名称
            input_text: 输入参数（字符串形式）

        Returns:
            工具执行结果字符串，如果执行失败则返回错误信息
        """
        # 优先查找Tool对象
        if name in self._tools:
            tool = self._tools[name]
            try:
                # 将输入文本包装为字典参数传递给Tool.run()
                return tool.run({"input": input_text})
            except Exception as e:
                return f"错误：执行工具 '{name}' 时发生异常: {str(e)}"

        # 查找函数工具
        elif name in self._functions:
            func = self._functions[name]["func"]
            try:
                # 直接调用函数，传入字符串参数
                return func(input_text)
            except Exception as e:
                return f"错误：执行工具 '{name}' 时发生异常: {str(e)}"

        else:
            return f"错误：未找到名为 '{name}' 的工具。"

    def get_tools_description(self) -> str:
        """
        获取所有可用工具的格式化描述字符串
        
        生成包含所有已注册工具的描述文本，格式为每行一个工具。
        该描述通常用于构建Agent的system prompt，让AI了解可用工具。

        Returns:
            工具描述字符串，格式为 "- 工具名: 工具描述"，每行一个工具
            如果没有工具则返回 "暂无可用工具"
        """
        descriptions = []

        # 收集Tool对象的描述
        for tool in self._tools.values():
            descriptions.append(f"- {tool.name}: {tool.description}")

        # 收集函数工具的描述
        for name, info in self._functions.items():
            descriptions.append(f"- {name}: {info['description']}")

        return "\n".join(descriptions) if descriptions else "暂无可用工具"

    def list_tools(self) -> list[str]:
        """
        列出所有已注册工具的名称
        
        Returns:
            包含所有工具名称的列表
        """
        return list(self._tools.keys()) + list(self._functions.keys())

    def get_all_tools(self) -> list[Tool]:
        """
        获取所有已注册的Tool对象
        
        注意：仅返回Tool对象，不包括函数工具
        
        Returns:
            包含所有Tool对象的列表
        """
        return list(self._tools.values())

    def clear(self):
        """
        清空所有已注册的工具
        
        移除所有Tool对象和函数工具，重置注册表为空状态。
        """
        self._tools.clear()
        self._functions.clear()
        print("所有工具已清空。")

# 全局工具注册表实例
# 提供一个全局单例，方便在整个应用中共享工具注册表
global_registry = ToolRegistry()
