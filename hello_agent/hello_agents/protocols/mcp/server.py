"""
基于 fastmcp 库的 MCP 服务器实现

使用 fastmcp 库实现 Model Context Protocol 服务器功能。
fastmcp 是一个快速创建 MCP 服务器的 Python 库。

【学习笔记】
MCP Server 的核心作用：把你写的 Python 函数“暴露”给 LLM 使用。
类比：MCP Server 就像一个“菜单”，告诉 LLM “你可以点这些菜”，
LLM 看完菜单后决定调用哪个工具。

Server 提供三种能力：
1. Tool（工具）— 可执行的函数，如计算器、文件读写、API 调用
2. Resource（资源）— 可读取的数据，如数据库记录、配置文件
3. Prompt（提示词模板）— 预定义的 Prompt，如“代码审查模板”

本文件包含两个类：
- MCPServer: 基本服务器，通过 add_tool/add_resource/add_prompt 添加能力
- MCPServerBuilder: 建造者模式封装，支持链式调用
"""

from typing import Dict, Any, List, Optional, Callable

# fastmcp 是 MCP 协议的 Python 实现库，提供了快速创建 MCP Server 的能力
# 安装: pip install fastmcp
try:
    from fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "fastmcp is required for MCP server functionality. "
        "Install it with: pip install fastmcp"
    )


class MCPServer:
    """基于 fastmcp 库的 MCP 服务器
    
    【学习笔记】
    这个类是对 FastMCP 的二次封装，提供更简洁的 API。
    实际上所有能力都委托给 self.mcp（FastMCP 实例）来实现。
    
    使用流程：
    1. 创建服务器: server = MCPServer("my-server")
    2. 添加工具: server.add_tool(my_func)
    3. 启动服务: server.run()
    """
    
    def __init__(
        self,
        name: str,
        description: Optional[str] = None
    ):
        """
        初始化 MCP 服务器
        
        Args:
            name: 服务器名称
            description: 服务器描述
        """
        # FastMCP 是底层实现，所有工具/资源/提示词都注册到这个实例上
        self.mcp = FastMCP(name=name)
        self.name = name
        self.description = description or f"{name} MCP Server"
        
    def add_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        添加工具到服务器
        
        【学习笔记】
        工具是 MCP 最核心的能力。每个工具就是一个 Python 函数，
        LLM 会根据函数名和描述来决定何时调用它。
        
        底层原理：self.mcp.tool() 返回一个装饰器，再用这个装饰器包装 func。
        等价于：
            @self.mcp.tool(name="calculator")
            def calculator(expression: str) -> str: ...
        
        Args:
            func: 工具函数，函数的参数类型注解和 docstring 会自动生成工具描述
            name: 工具名称（可选，默认使用函数名）
            description: 工具描述（可选，默认使用函数文档字符串）
        """
        # 使用装饰器注册工具
        # self.mcp.tool() 返回装饰器 → 装饰器(func) 完成注册
        if name or description:
            self.mcp.tool(name=name, description=description)(func)
        else:
            self.mcp.tool()(func)
        
    def add_resource(
        self,
        func: Callable,
        uri: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        添加资源到服务器
        
        【学习笔记】
        资源与工具的区别：
        - 工具(Tool): 执行操作，有副作用（如发邮件、写文件）
        - 资源(Resource): 只读数据，无副作用（如读配置、查数据库）
        
        URI 是资源的唯一标识，类似网址，如 "config://app" 或 "db://users"
        
        Args:
            func: 资源处理函数，返回资源内容
            uri: 资源 URI（可选），如 "config://database"
            name: 资源名称（可选）
            description: 资源描述（可选）
        """
        # 使用装饰器注册资源
        if uri:
            self.mcp.resource(uri)(func)
        else:
            self.mcp.resource()(func)
        
    def add_prompt(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        添加提示词模板到服务器
        
        【学习笔记】
        Prompt 模板是预定义的提示词，可以带参数。
        例如一个“代码审查”模板，传入代码后自动生成审查用的 Prompt。
        这让 LLM 可以复用预设的高质量 Prompt，而不是每次都从头写。
        
        Args:
            func: 提示词生成函数，接收参数并返回格式化的 Prompt
            name: 提示词名称（可选）
            description: 提示词描述（可选）
        """
        # 使用装饰器注册提示词
        if name or description:
            self.mcp.prompt(name=name, description=description)(func)
        else:
            self.mcp.prompt()(func)
        
    def run(self, transport: str = "stdio", **kwargs):
        """运行服务器
        
        【学习笔记 - 传输方式说明】
        MCP 支持三种传输方式，适用于不同场景：
        - stdio: 标准输入输出，用于本地进程通信（最常用，如 IDE 插件）
        - http: HTTP 请求，用于远程服务器（适合部署到云端）
        - sse: Server-Sent Events，用于实时通信（服务器可主动推送消息）

        Args:
            transport: 传输方式 ("stdio", "http", "sse")
            **kwargs: 传输特定的参数
                - host: HTTP 服务器主机（默认 "127.0.0.1"）
                - port: HTTP 服务器端口（默认 8000）
                - 其他 FastMCP.run() 支持的参数

        Examples:
            # Stdio 传输（默认，最常用）
            server.run()

            # HTTP 传输（远程访问）
            server.run(transport="http", host="0.0.0.0", port=8081)

            # SSE 传输（实时通信）
            server.run(transport="sse", host="0.0.0.0", port=8081)
        """
        self.mcp.run(transport=transport, **kwargs)
        
    def get_info(self) -> Dict[str, Any]:
        """
        获取服务器信息
        
        Returns:
            服务器信息字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "protocol": "MCP"
        }


# 便捷的服务器构建器
class MCPServerBuilder:
    """服务器构建器，提供链式 API
    
    【学习笔记 - 建造者模式 (Builder Pattern)】
    这是一种常见的设计模式，让你可以链式调用来构建对象：
    
    server = (MCPServerBuilder("my-server")
        .with_tool(calculator)       # 每个方法返回 self
        .with_tool(greet)            # 所以可以继续调用
        .with_resource(get_config)   # 一直链下去
        .build())                    # 最后构建出 MCPServer 实例
    
    对比普通写法：
    server = MCPServer("my-server")
    server.add_tool(calculator)
    server.add_tool(greet)
    server.add_resource(get_config)
    
    两种写法效果一样，Builder 更简洁、可读性更好。
    """

    def __init__(self, name: str, description: Optional[str] = None):
        self.server = MCPServer(name, description)
        
    def with_tool(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> 'MCPServerBuilder':
        """添加工具（链式调用）"""
        self.server.add_tool(func, name, description)
        return self
        
    def with_resource(self, func: Callable, uri: Optional[str] = None, name: Optional[str] = None, description: Optional[str] = None) -> 'MCPServerBuilder':
        """添加资源（链式调用）"""
        self.server.add_resource(func, uri, name, description)
        return self
        
    def with_prompt(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> 'MCPServerBuilder':
        """添加提示词（链式调用）"""
        self.server.add_prompt(func, name, description)
        return self
        
    def build(self) -> MCPServer:
        """构建服务器"""
        return self.server
        
    def run(self):
        """构建并运行服务器"""
        self.server.run()


# ==================== 示例代码 ====================
# 下面是一个完整的 MCP Server 示例，可以直接运行：
# python server.py
def create_example_server() -> MCPServer:
    """创建一个示例 MCP 服务器
    
    【学习笔记】
    这个示例展示了创建 MCP Server 的完整流程：
    1. 创建服务器实例
    2. 定义工具函数（注意：函数的参数类型注解和 docstring 很重要，
       它们会被自动转换为工具描述，让 LLM 知道如何使用这个工具）
    3. 注册工具到服务器
    4. 返回服务器实例（在 __main__ 中调用 .run() 启动）
    """
    server = MCPServer(
        name="example-server",
        description="A simple example MCP server with calculator and greeting tools"
    )
    
    # 工具 1: 计算器
    # 注意：参数类型注解 (expression: str) 和返回类型 (-> str) 很重要
    # MCP 会自动从这些注解生成工具的参数描述（JSON Schema）
    def calculator(expression: str) -> str:
        """计算数学表达式
        
        Args:
            expression: 要计算的数学表达式，例如 "2 + 2" 或 "10 * 5"
        """
        try:
            # 安全的表达式求值（仅支持基本运算）
            allowed_chars = set("0123456789+-*/() .")
            if not all(c in allowed_chars for c in expression):
                return f"Error: Invalid characters in expression"
            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    server.add_tool(calculator, name="calculator", description="Calculate a mathematical expression")
    
    # 工具 2: 问候
    def greet(name: str) -> str:
        """生成友好的问候语
        
        Args:
            name: 要问候的人的名字
        """
        return f"Hello, {name}! Welcome to the MCP server example."
    
    server.add_tool(greet, name="greet", description="Generate a friendly greeting")
    
    return server


if __name__ == "__main__":
    # 直接运行这个文件即可启动示例 MCP Server
    # 启动后，可以用 MCPClient 连接并调用工具
    server = create_example_server()
    print(f"🚀 Starting {server.name}...")
    print(f"📝 {server.description}")
    print(f"🔌 Protocol: MCP")
    print(f"📡 Transport: stdio")
    print()
    server.run()

