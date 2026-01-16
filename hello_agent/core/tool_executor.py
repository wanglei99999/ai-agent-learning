from typing import Dict, Any


class ToolExecutor:
    """
    一个工具执行器，负责管理和执行工具。
    这是 Agent 能够"使用工具"的关键组件——一个工具注册表。
    """
    
    def __init__(self):
        # 工具注册表，结构: {"工具名": {"description": "描述", "func": 函数}}
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, description: str, func: callable):
        """
        向工具箱注册一个新工具。
        
        参数:
            name: 工具名称，LLM 会用这个名字来调用工具
            description: 工具描述，告诉 LLM 这个工具能做什么
            func: 工具的实际执行函数（callable 表示可调用对象，即函数）
        """
        if name in self.tools:
            print(f"warning: 工具：{name}已经存在，将会被新工具覆盖")
        
        # 把工具信息存入注册表
        self.tools[name] = {"description": description, "func": func}
        print(f"工具{name}已经注册")

    def get_tool(self, name: str) -> callable:
        """
        根据名称获取一个工具的执行函数。
        
        返回: 工具函数，如果不存在则返回 None
        """
        # .get(name, {}) - 如果找不到 name，返回空字典 {}
        # .get("func") - 从字典中取 func，如果是空字典则返回 None
        return self.tools.get(name, {}).get("func")

    def get_available_tools(self) -> str:
        """
        获取所有可用工具的格式化描述字符串。
        这个字符串会放到 prompt 里，告诉 LLM 有哪些工具可用。
        
        返回示例:
            - search: 网页搜索工具
            - calculator: 数学计算工具
        """
        return "\n".join([
            f"- {name}: {info['description']}" 
            for name, info in self.tools.items()
        ])
