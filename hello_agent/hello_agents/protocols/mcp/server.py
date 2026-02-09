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
        
        【学习笔记 - 工具注册原理】
        工具是 MCP 最核心的能力。每个工具就是一个 Python 函数，
        LLM 会根据函数名和描述来决定何时调用它。
        
        底层原理：self.mcp.tool() 返回一个装饰器，再用这个装饰器包装 func。
        等价于：
            @self.mcp.tool(name="calculator")
            def calculator(expression: str) -> str: ...
        
        【重要】函数签名的要求：
        1. 参数必须有类型注解: def func(name: str, age: int)
        2. 建议有返回类型注解: -> str
        3. 必须有 docstring 说明功能
        4. docstring 中建议用 Args 说明每个参数
        
        这些信息会被 MCP 自动转换为 JSON Schema，让 LLM 知道：
        - 这个工具叫什么名字
        - 这个工具是干什么的
        - 需要传入什么参数
        - 参数的类型是什么
        
        Args:
            func: 工具函数，函数的参数类型注解和 docstring 会自动生成工具描述
            name: 工具名称（可选，默认使用函数名）
            description: 工具描述（可选，默认使用函数文档字符串）
        
        Example:
            def search_web(query: str) -> str:
                '''在网上搜索信息
                
                Args:
                    query: 搜索关键词
                '''
                return f"搜索结果: {query}"
            
            server.add_tool(search_web)
        """
        # === 使用装饰器注册工具 ===
        # self.mcp.tool() 返回装饰器 → 装饰器(func) 完成注册
        # 注册后，FastMCP 会将这个函数暴露为 MCP 工具
        if name or description:
            self.mcp.tool(name=name, description=description)(func)
        else:
            # 如果不指定 name 和 description，使用函数名和 docstring
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
        
        【学习笔记 - 资源 vs 工具】
        资源与工具的核心区别：
        - 工具(Tool): 执行操作，有副作用（如发邮件、写文件、调用 API）
        - 资源(Resource): 只读数据，无副作用（如读配置、查数据库、读文件）
        
        【URI 说明】
        URI 是资源的唯一标识符，类似网址，遵循格式：scheme://path
        常见示例：
        - "config://database" - 数据库配置
        - "file:///path/to/file.txt" - 文件资源
        - "db://users/123" - 数据库记录
        - "api://weather/beijing" - API 数据
        
        【使用场景】
        当 LLM 需要读取某些数据时，会请求对应 URI 的资源。
        例如：LLM 想知道数据库配置，就请求 "config://database"
        
        Args:
            func: 资源处理函数，返回资源内容（通常返回字符串或字典）
            uri: 资源 URI（可选），如 "config://database"
            name: 资源名称（可选）
            description: 资源描述（可选）
        
        Example:
            def get_config() -> dict:
                '''获取应用配置'''
                return {"db_host": "localhost", "db_port": 5432}
            
            server.add_resource(get_config, uri="config://app")
        """
        # === 使用装饰器注册资源 ===
        # 注册后，客户端可以通过 URI 请求这个资源
        if uri:
            self.mcp.resource(uri)(func)
        else:
            # 如果不指定 URI，FastMCP 会自动生成
            self.mcp.resource()(func)
        
    def add_prompt(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ):
        """
        添加提示词模板到服务器
        
        【学习笔记 - Prompt 模板的作用】
        Prompt 模板是预定义的提示词，可以带参数。
        
        使用场景：
        1. 代码审查模板：传入代码，生成审查用的 Prompt
        2. 文档生成模板：传入函数签名，生成文档 Prompt
        3. 测试用例模板：传入需求，生成测试用例 Prompt
        
        好处：
        - 复用高质量的 Prompt，不用每次从头写
        - 保证 Prompt 的一致性和专业性
        - 可以参数化，适应不同输入
        
        【工作流程】
        1. 定义模板函数，接收参数（如代码、语言等）
        2. 函数返回格式化的 Prompt 字符串
        3. LLM 调用模板，传入参数，获取 Prompt
        4. LLM 使用生成的 Prompt 进行推理
        
        Args:
            func: 提示词生成函数，接收参数并返回格式化的 Prompt
            name: 提示词名称（可选）
            description: 提示词描述（可选）
        
        Example:
            def code_review_prompt(code: str, language: str) -> str:
                '''生成代码审查提示词
                
                Args:
                    code: 要审查的代码
                    language: 编程语言
                '''
                return f'''请审查以下 {language} 代码：
                
                ```{language}
                {code}
                ```
                
                请关注：
                1. 代码质量
                2. 潜在 bug
                3. 性能问题
                4. 最佳实践
                '''
            
            server.add_prompt(code_review_prompt)
        """
        # === 使用装饰器注册提示词模板 ===
        # 注册后，客户端可以调用这个模板生成 Prompt
        if name or description:
            self.mcp.prompt(name=name, description=description)(func)
        else:
            self.mcp.prompt()(func)
        
    def run(self, transport: str = "stdio", **kwargs):
        """运行服务器
        
        【学习笔记 - 传输方式详解】
        MCP 支持三种传输方式，适用于不同场景：
        
        1. stdio（标准输入输出）- 默认，最常用
           - 用途：本地进程间通信
           - 场景：IDE 插件、桌面应用、命令行工具
           - 原理：通过 stdin/stdout 传输 JSON-RPC 消息
           - 优点：简单、安全、不需要网络
           - 示例：Claude Desktop 配置本地 MCP Server
        
        2. http（HTTP 请求）
           - 用途：远程服务器部署
           - 场景：云端服务、微服务架构
           - 原理：通过 HTTP POST 请求传输 JSON-RPC
           - 优点：可远程访问、支持负载均衡
           - 注意：需要考虑安全性（HTTPS、认证）
        
        3. sse（Server-Sent Events）
           - 用途：实时通信、流式响应
           - 场景：需要服务器主动推送消息的应用
           - 原理：HTTP 长连接，服务器可持续推送事件
           - 优点：支持实时更新、适合流式输出

        Args:
            transport: 传输方式 ("stdio", "http", "sse")
            **kwargs: 传输特定的参数
                - host: HTTP/SSE 服务器主机（默认 "127.0.0.1"）
                - port: HTTP/SSE 服务器端口（默认 8000）
                - 其他 FastMCP.run() 支持的参数

        Examples:
            # Stdio 传输（默认，最常用）
            # 适合：本地开发、IDE 集成
            server.run()

            # HTTP 传输（远程访问）
            # 适合：部署到服务器、提供 API 服务
            server.run(transport="http", host="0.0.0.0", port=8081)

            # SSE 传输（实时通信）
            # 适合：需要流式响应、实时更新的场景
            server.run(transport="sse", host="0.0.0.0", port=8081)
        
        注意：
        - stdio 模式下，这个方法会阻塞，直到进程被终止
        - http/sse 模式下，会启动 Web 服务器并阻塞
        """
        # 委托给 FastMCP 的 run 方法执行
        # FastMCP 会根据 transport 参数启动相应的传输层
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
    这是一种常见的设计模式，让你可以链式调用来构建对象。
    
    核心思想：
    - 每个方法都返回 self（当前对象）
    - 这样就可以连续调用多个方法
    - 最后调用 build() 返回构建好的对象
    
    链式调用示例：
    server = (MCPServerBuilder("my-server")
        .with_tool(calculator)       # 返回 self
        .with_tool(greet)            # 继续调用
        .with_resource(get_config)   # 继续调用
        .build())                    # 返回 MCPServer
    
    等价的普通写法：
    builder = MCPServerBuilder("my-server")
    builder.with_tool(calculator)
    builder.with_tool(greet)
    builder.with_resource(get_config)
    server = builder.build()
    
    或者直接用 MCPServer：
    server = MCPServer("my-server")
    server.add_tool(calculator)
    server.add_tool(greet)
    server.add_resource(get_config)
    
    三种写法效果完全一样，Builder 模式的优点：
    1. 代码更简洁、可读性更好
    2. 一目了然地看到所有配置
    3. 符合流式编程风格
    """

    def __init__(self, name: str, description: Optional[str] = None):
        self.server = MCPServer(name, description)
        
    def with_tool(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> 'MCPServerBuilder':
        """添加工具（链式调用）
        
        Args:
            func: 工具函数
            name: 工具名称（可选）
            description: 工具描述（可选）
            
        Returns:
            返回 self，支持链式调用
        """
        # 委托给内部的 MCPServer 实例
        self.server.add_tool(func, name, description)
        # 返回 self，支持链式调用
        return self
        
    def with_resource(self, func: Callable, uri: Optional[str] = None, name: Optional[str] = None, description: Optional[str] = None) -> 'MCPServerBuilder':
        """添加资源（链式调用）
        
        Args:
            func: 资源处理函数
            uri: 资源 URI（可选）
            name: 资源名称（可选）
            description: 资源描述（可选）
            
        Returns:
            返回 self，支持链式调用
        """
        self.server.add_resource(func, uri, name, description)
        return self
        
    def with_prompt(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None) -> 'MCPServerBuilder':
        """添加提示词模板（链式调用）
        
        Args:
            func: 提示词生成函数
            name: 提示词名称（可选）
            description: 提示词描述（可选）
            
        Returns:
            返回 self，支持链式调用
        """
        self.server.add_prompt(func, name, description)
        return self
        
    def build(self) -> MCPServer:
        """构建服务器
        
        Returns:
            构建好的 MCPServer 实例
        """
        return self.server
        
    def run(self):
        """构建并运行服务器
        
        这是一个便捷方法，等价于 build().run()
        直接启动服务器，无需手动调用 build()
        """
        self.server.run()


# ==================== 示例代码 ====================
# 下面是一个完整的 MCP Server 示例，可以直接运行：
# python server.py
def create_example_server() -> MCPServer:
    """创建一个示例 MCP 服务器
    
    【学习笔记 - 完整的 MCP Server 创建流程】
    
    这个示例展示了从零创建 MCP Server 的完整步骤：
    
    步骤1: 创建服务器实例
        - 指定服务器名称和描述
        - 名称会在客户端连接时显示
    
    步骤2: 定义工具函数
        - 函数签名要求：参数必须有类型注解
        - 必须有 docstring 说明功能
        - docstring 中建议用 Args 说明参数
        - 这些信息会自动转换为工具的 JSON Schema
    
    步骤3: 注册工具到服务器
        - 使用 add_tool() 方法注册
        - 可以指定自定义的名称和描述
    
    步骤4: 返回服务器实例
        - 在 __main__ 中调用 .run() 启动服务器
        - 服务器启动后等待客户端连接
    
    【重要】工具函数的设计原则：
    1. 单一职责：每个工具只做一件事
    2. 清晰命名：函数名要能表达功能
    3. 详细文档：docstring 要说明用途和参数
    4. 类型安全：参数和返回值都要有类型注解
    5. 错误处理：要捕获异常并返回友好的错误信息
    """
    server = MCPServer(
        name="example-server",
        description="A simple example MCP server with calculator and greeting tools"
    )
    
    # === 工具 1: 计算器 ===
    # 【重要】参数类型注解 (expression: str) 和返回类型 (-> str) 很重要
    # MCP 会自动从这些注解生成工具的参数描述（JSON Schema）
    # 
    # 生成的 JSON Schema 示例：
    # {
    #   "name": "calculator",
    #   "description": "计算数学表达式",
    #   "parameters": {
    #     "type": "object",
    #     "properties": {
    #       "expression": {
    #         "type": "string",
    #         "description": "要计算的数学表达式，例如 '2 + 2' 或 '10 * 5'"
    #       }
    #     },
    #     "required": ["expression"]
    #   }
    # }
    def calculator(expression: str) -> str:
        """计算数学表达式
        
        这是一个简单的计算器工具，支持基本的数学运算。
        
        Args:
            expression: 要计算的数学表达式，例如 "2 + 2" 或 "10 * 5"
                       支持的运算符：+ - * / ( )
        
        Returns:
            计算结果或错误信息
        """
        try:
            # === 安全检查：只允许数字和基本运算符 ===
            # 防止恶意代码注入（eval 是危险的，必须严格限制输入）
            allowed_chars = set("0123456789+-*/() .")
            if not all(c in allowed_chars for c in expression):
                return f"Error: Invalid characters in expression"
            
            # === 执行计算 ===
            # 注意：生产环境应该使用更安全的表达式解析器
            result = eval(expression)
            return f"Result: {result}"
        except Exception as e:
            # === 错误处理 ===
            # 返回友好的错误信息，而不是让程序崩溃
            return f"Error: {str(e)}"
    
    server.add_tool(calculator, name="calculator", description="Calculate a mathematical expression")
    
    # === 工具 2: 问候 ===
    # 这是一个简单的示例，展示最基本的工具结构
    def greet(name: str) -> str:
        """生成友好的问候语
        
        这是一个简单的示例工具，用于演示 MCP 工具的基本结构。
        
        Args:
            name: 要问候的人的名字
        
        Returns:
            包含问候语的字符串
        """
        return f"Hello, {name}! Welcome to the MCP server example."
    
    server.add_tool(greet, name="greet", description="Generate a friendly greeting")
    
    return server


if __name__ == "__main__":
    """
    【学习笔记 - 如何运行 MCP Server】
    
    运行方式：
    1. 直接运行: python server.py
    2. 服务器会通过 stdio（标准输入输出）与客户端通信
    3. 客户端（如 IDE、LLM 应用）通过 stdin/stdout 发送 JSON-RPC 请求
    
    通信流程：
    Client -> stdin -> MCP Server -> stdout -> Client
    
    实际应用场景：
    - Claude Desktop 可以配置 MCP Server，启动后通过 stdio 通信
    - VSCode 插件可以启动 MCP Server 进程，调用其中的工具
    - 任何支持 MCP 协议的 LLM 应用都可以连接
    """
    # 创建示例服务器实例
    server = create_example_server()
    
    # 打印服务器启动信息
    print(f"[启动] Starting {server.name}...")
    print(f"[描述] {server.description}")
    print(f"[协议] Protocol: MCP")
    print(f"[传输] Transport: stdio")
    print()
    
    # 启动服务器（阻塞运行，等待客户端请求）
    # 注意：这个调用会一直阻塞，直到进程被终止
    server.run()

