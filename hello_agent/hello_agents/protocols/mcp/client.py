"""
增强的 MCP 客户端实现

支持多种传输方式的 MCP 客户端，用于教学和实际应用。
这个实现展示了如何使用不同的传输方式连接到 MCP 服务器。

【学习笔记】
MCP Client 的核心作用：连接到 MCP Server，发现并调用它提供的工具/资源/提示词。
类比：如果 MCP Server 是“餐厅”，那 MCP Client 就是“顾客”——
顾客看菜单（list_tools）、点菜（call_tool）、查看食材（list_resources）。

本文件的核心设计：
- 智能推断传输方式：根据传入参数自动判断用 stdio/http/sse/memory
- 异步上下文管理器：用 async with 自动管理连接生命周期
- 统一的操作接口：list_tools/call_tool/list_resources/read_resource 等

支持的传输方式：
1. Memory: 内存传输（用于测试，直接传递 FastMCP 实例）
2. Stdio: 标准输入输出传输（本地进程，Python/Node.js 脚本）
3. HTTP: HTTP 传输（远程服务器）
4. SSE: Server-Sent Events 传输（实时通信）

使用示例：
```python
# 1. 内存传输（测试）
from fastmcp import FastMCP
server = FastMCP("TestServer")
client = MCPClient(server)

# 2. Stdio 传输（本地脚本）
client = MCPClient("server.py")
client = MCPClient(["python", "server.py"])

# 3. HTTP 传输（远程服务器）
client = MCPClient("https://api.example.com/mcp")

# 4. SSE 传输（实时通信）
client = MCPClient("https://api.example.com/mcp", transport_type="sse")

# 5. 配置传输（高级用法）
config = {
    "transport": "stdio",
    "command": "python",
    "args": ["server.py"],
    "env": {"DEBUG": "1"}
}
client = MCPClient(config)
```
"""

from typing import Dict, Any, List, Optional, Union
import asyncio
import os

# 从 fastmcp 库导入客户端和各种传输方式
# - Client: MCP 客户端核心类
# - FastMCP: 服务器类（用于内存传输时直接传入）
# - PythonStdioTransport: 通过标准输入输出与本地 Python 脚本通信
# - SSETransport: 通过 Server-Sent Events 与远程服务器通信
# - StreamableHttpTransport: 通过 HTTP 与远程服务器通信
try:
    from fastmcp import Client, FastMCP
    from fastmcp.client.transports import PythonStdioTransport, SSETransport, StreamableHttpTransport
    FASTMCP_AVAILABLE = True
except ImportError:
    # 优雅降级：如果没装 fastmcp，不会直接崩溃，而是在真正使用时才报错
    FASTMCP_AVAILABLE = False
    Client = None
    FastMCP = None
    PythonStdioTransport = None
    SSETransport = None
    StreamableHttpTransport = None


class MCPClient:
    """MCP 客户端，支持多种传输方式
    
    【学习笔记】
    这个类的核心设计思路：
    1. 智能推断: 根据传入的 server_source 参数类型自动选择传输方式
       - 传 FastMCP 实例 → 内存传输
       - 传 .py 文件路径 → Stdio 传输
       - 传 http:// URL → HTTP 传输
       - 传配置字典 → 根据配置创建
    2. 异步上下文管理器: 用 `async with` 自动管理连接
    3. 统一接口: 无论哪种传输方式，调用方法都一样
    
    使用模式：
    ```python
    async with MCPClient("server.py") as client:
        tools = await client.list_tools()      # 查看有哪些工具
        result = await client.call_tool("calculator", {"expression": "1+1"})  # 调用工具
    # 离开 async with 后自动断开连接
    ```
    """

    def __init__(self,
                 server_source: Union[str, List[str], FastMCP, Dict[str, Any]],
                 server_args: Optional[List[str]] = None,
                 transport_type: Optional[str] = None,
                 env: Optional[Dict[str, str]] = None,
                 **transport_kwargs):
        """
        初始化 MCP 客户端
        
        【学习笔记 - 初始化流程】
        初始化时并不会立即连接服务器，只是准备好传输配置。
        真正的连接发生在 async with 时（即 __aenter__ 方法）。
        
        这种“延迟连接”的设计是因为：
        1. 连接是异步操作，不能在 __init__ 里做（__init__ 不能是 async）
        2. 需要配合上下文管理器确保连接能被正确关闭

        Args:
            server_source: 服务器源，支持多种格式（智能推断传输方式）：
                - FastMCP 实例: 内存传输（用于测试，不走网络）
                - 字符串路径: Python 脚本路径（如 "server.py"）→ Stdio 传输
                - HTTP URL: 远程服务器（如 "https://api.example.com/mcp"）→ HTTP 传输
                - 命令列表: 完整命令（如 ["python", "server.py"]）→ Stdio 传输
                - 配置字典: 详细的传输配置（高级用法）
            server_args: 服务器参数列表（可选，传递给服务器进程的命令行参数）
            transport_type: 强制指定传输类型 ("stdio", "http", "sse", "memory")
                          如果不指定，会根据 server_source 自动推断
            env: 环境变量字典（传递给 MCP 服务器进程）
            **transport_kwargs: 传输特定的额外参数（如 headers, auth 等）

        Raises:
            ImportError: 如果 fastmcp 库未安装
        """
        # === 检查依赖 ===
        if not FASTMCP_AVAILABLE:
            raise ImportError(
                "Enhanced MCP client requires the 'fastmcp' library (version 2.0+). "
                "Install it with: pip install fastmcp>=2.0.0"
            )

        # === 保存配置参数 ===
        self.server_args = server_args or []       # 服务器命令行参数
        self.transport_type = transport_type         # 强制指定的传输类型
        self.env = env or {}                         # 环境变量
        self.transport_kwargs = transport_kwargs      # 传输层额外参数
        
        # === 智能推断并创建传输配置 ===
        # 这是初始化的核心步骤，根据 server_source 的类型自动选择传输方式
        self.server_source = self._prepare_server_source(server_source)
        
        # === 连接状态（初始未连接） ===
        self.client: Optional[Client] = None   # FastMCP 客户端实例，连接后才有值
        self._context_manager = None            # 上下文管理器，用于管理连接生命周期

    def _prepare_server_source(self, server_source: Union[str, List[str], FastMCP, Dict[str, Any]]):
        """准备服务器源，根据类型创建合适的传输配置
        
        【学习笔记 - 智能推断的实现】
        这个方法是本类的核心，它通过 isinstance() 检查参数类型，
        自动选择合适的传输方式。这种设计让用户不需要关心传输细节，
        只需传入服务器地址或实例即可。
        
        【设计模式 - 策略模式】
        这里用的是“策略模式”的变体：
        - 根据输入类型选择不同的传输策略
        - 每种传输方式是一个独立的 Transport 对象
        - 客户端代码不需要知道具体用的哪种传输
        
        判断优先级：
        FastMCP实例 → 配置字典 → HTTP URL → .py文件 → 命令列表 → 自动推断
        
        Args:
            server_source: 服务器源，支持多种类型
            
        Returns:
            配置好的传输对象，传给 FastMCP Client 使用
        """
        
        # === 情况 1: FastMCP 实例 → 内存传输 ===
        # 最快的传输方式，不走网络，直接在内存中调用
        # 适用场景：单元测试、开发调试
        # 示例：
        #   server = FastMCP("test")
        #   client = MCPClient(server)  # 直接传入服务器实例
        if isinstance(server_source, FastMCP):
            print(f"[内存传输] 使用内存传输: {server_source.name}")
            return server_source
        
        # === 情况 2: 配置字典 → 根据配置创建传输 ===
        # 适用场景：需要精细控制传输参数（如环境变量、工作目录等）
        # 示例：
        #   config = {"transport": "stdio", "command": "python", "args": ["server.py"]}
        #   client = MCPClient(config)
        if isinstance(server_source, dict):
            print(f"[配置传输] 使用配置传输: {server_source.get('transport', 'stdio')}")
            return self._create_transport_from_config(server_source)
        
        # === 情况 3: HTTP/HTTPS URL → 远程服务器传输 ===
        # 适用场景：MCP Server 部署在远程服务器上
        # 默认用 HTTP，也可以通过 transport_type="sse" 强制用 SSE
        # 示例：
        #   client = MCPClient("https://api.example.com/mcp")              # HTTP
        #   client = MCPClient("https://api.example.com/mcp", transport_type="sse")  # SSE
        if isinstance(server_source, str) and (server_source.startswith("http://") or server_source.startswith("https://")):
            transport_type = self.transport_type or "http"
            print(f"[远程传输] 使用 {transport_type.upper()} 传输: {server_source}")
            if transport_type == "sse":
                # SSE: 服务器可以主动推送消息，适合实时通信
                return SSETransport(url=server_source, **self.transport_kwargs)
            else:
                # HTTP: 标准的请求-响应模式
                return StreamableHttpTransport(url=server_source, **self.transport_kwargs)

        # === 情况 4: .py 文件路径 → Stdio 传输 ===
        # 最常用的方式！自动启动本地 Python 脚本作为 MCP Server
        # 通过 stdin/stdout 通信，不需要网络
        # 示例：
        #   client = MCPClient("server.py")  # 自动启动 python server.py
        # 底层流程：
        #   1. PythonStdioTransport 启动子进程: python server.py
        #   2. 通过子进程的 stdin 发送 JSON-RPC 请求
        #   3. 从子进程的 stdout 读取 JSON-RPC 响应
        if isinstance(server_source, str) and server_source.endswith(".py"):
            print(f"[Stdio传输] 使用 Stdio 传输 (Python): {server_source}")
            return PythonStdioTransport(
                script_path=server_source,     # Python 脚本路径
                args=self.server_args,          # 传递给脚本的参数
                env=self.env if self.env else None,  # 环境变量
                **self.transport_kwargs
            )

        # === 情况 5: 命令列表 → Stdio 传输 ===
        # 适用场景：需要指定完整的启动命令
        # 示例：
        #   client = MCPClient(["python", "server.py"])       # Python 脚本
        #   client = MCPClient(["node", "server.js"])         # Node.js 脚本
        #   client = MCPClient(["./my-mcp-server", "--port", "8080"])  # 自定义可执行文件
        if isinstance(server_source, list) and len(server_source) >= 1:
            print(f"[Stdio传输] 使用 Stdio 传输 (命令): {' '.join(server_source)}")
            if server_source[0] == "python" and len(server_source) > 1 and server_source[1].endswith(".py"):
                # Python 脚本：使用专用的 PythonStdioTransport
                return PythonStdioTransport(
                    script_path=server_source[1],              # 脚本路径
                    args=server_source[2:] + self.server_args,  # 合并参数
                    env=self.env if self.env else None,
                    **self.transport_kwargs
                )
            else:
                # 非 Python 命令：使用通用的 StdioTransport
                # 支持任何可执行文件（Node.js、Go、Rust 等编写的 MCP Server）
                from fastmcp.client.transports import StdioTransport
                return StdioTransport(
                    command=server_source[0],                   # 命令
                    args=server_source[1:] + self.server_args,  # 参数
                    env=self.env if self.env else None,
                    **self.transport_kwargs
                )
        
        # 情况 6: 其他情况 → 直接返回，让 FastMCP 底层自动推断
        print(f"[自动推断] 自动推断传输: {server_source}")
        return server_source

    def _create_transport_from_config(self, config: Dict[str, Any]):
        """从配置字典创建传输
        
        【学习笔记 - 配置字典格式】
        配置字典支持以下字段：
        {
            "transport": "stdio" | "sse" | "http",  # 传输类型
            "command": "python",                     # 命令（stdio 用）
            "args": ["server.py"],                   # 参数（stdio 用）
            "env": {"DEBUG": "1"},                   # 环境变量（stdio 用）
            "cwd": "/path/to/dir",                   # 工作目录（stdio 用）
            "url": "https://...",                    # 服务器地址（http/sse 用）
            "headers": {"Authorization": "..."},     # 请求头（http/sse 用）
            "auth": ...                              # 认证信息（http/sse 用）
        }
        
        这种配置格式类似 Claude Desktop 的 MCP 配置文件。
        
        Args:
            config: 传输配置字典
            
        Returns:
            配置好的传输对象
            
        Raises:
            ValueError: 不支持的传输类型
        """
        transport_type = config.get("transport", "stdio")
        
        # === Stdio 传输 ===
        if transport_type == "stdio":
            args = config.get("args", [])
            if args and args[0].endswith(".py"):
                # Python 脚本：使用专用传输
                return PythonStdioTransport(
                    script_path=args[0],
                    args=args[1:] + self.server_args,
                    env=config.get("env"),
                    cwd=config.get("cwd"),
                    **self.transport_kwargs
                )
            else:
                # 通用命令：使用通用 Stdio 传输
                from fastmcp.client.transports import StdioTransport
                return StdioTransport(
                    command=config.get("command", "python"),
                    args=args + self.server_args,
                    env=config.get("env"),
                    cwd=config.get("cwd"),
                    **self.transport_kwargs
                )
        # === SSE 传输 ===
        elif transport_type == "sse":
            return SSETransport(
                url=config["url"],              # 服务器地址（必填）
                headers=config.get("headers"),   # 自定义请求头（可选）
                auth=config.get("auth"),         # 认证信息（可选）
                **self.transport_kwargs
            )
        # === HTTP 传输 ===
        elif transport_type == "http":
            return StreamableHttpTransport(
                url=config["url"],              # 服务器地址（必填）
                headers=config.get("headers"),   # 自定义请求头（可选）
                auth=config.get("auth"),         # 认证信息（可选）
                **self.transport_kwargs
            )
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")

    async def __aenter__(self):
        """异步上下文管理器入口 - 建立连接
        
        【学习笔记 - Python 异步上下文管理器】
        
        普通上下文管理器（同步）：
            with open("file.txt") as f:    # __enter__
                data = f.read()
            # __exit__: 自动关闭文件
        
        异步上下文管理器：
            async with MCPClient("server.py") as client:  # __aenter__
                await client.list_tools()
            # __aexit__: 自动断开连接
        
        为什么要用异步版？
        - 建立连接是网络操作，需要等待，用 async 不会阻塞程序
        - 断开连接也是网络操作，同理
        
        好处：
        - 即使中间发生异常，连接也会被正确关闭，不会泄漏资源
        - 不需要手动调用 connect()/disconnect()
        
        Returns:
            self，让 async with ... as client 中的 client 就是 MCPClient 实例
        """
        print("[连接] 连接到 MCP 服务器...")
        # 创建 FastMCP 客户端实例，传入之前准备好的传输配置
        self.client = Client(self.server_source)
        self._context_manager = self.client
        # 调用 FastMCP Client 的 __aenter__，建立底层连接
        await self._context_manager.__aenter__()
        print("[成功] 连接成功！")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口 - 断开连接并清理资源
        
        【学习笔记】
        参数说明：
        - exc_type: 异常类型（如 ValueError），没有异常时为 None
        - exc_val: 异常实例，没有异常时为 None
        - exc_tb: 异常跟踪信息，没有异常时为 None
        
        无论是正常退出还是异常退出，都会执行清理逻辑。
        """
        if self._context_manager:
            # 调用 FastMCP Client 的 __aexit__，断开底层连接
            await self._context_manager.__aexit__(exc_type, exc_val, exc_tb)
            # 清理引用，帮助垃圾回收
            self.client = None
            self._context_manager = None
        print("[断开] 连接已断开")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """列出服务器上所有可用的工具
        
        【学习笔记 - 工具发现】
        这是使用 MCP 的第一步：先查看服务器提供了哪些工具。
        
        返回的每个工具包含三个关键信息：
        - name: 工具名称（如 "calculator"）
        - description: 工具描述（如 "计算数学表达式"）
        - input_schema: JSON Schema，描述工具接受哪些参数
        
        LLM 正是通过这些信息来决定何时以及如何调用工具的。
        
        返回示例：
        [
            {
                "name": "calculator",
                "description": "计算数学表达式",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "数学表达式"}
                    },
                    "required": ["expression"]
                }
            }
        ]
        
        Returns:
            工具信息字典列表
        """
        # === 连接检查 ===
        # 所有操作方法都会先检查是否已连接
        if not self.client:
            raise RuntimeError("Client not connected. Use 'async with client:' context manager.")

        # === 调用 FastMCP 底层 API ===
        result = await self.client.list_tools()

        # === 处理不同的返回格式 ===
        # FastMCP 不同版本可能返回不同格式，这里做兼容处理
        if hasattr(result, 'tools'):
            tools = result.tools          # 新版：返回对象，工具在 .tools 属性中
        elif isinstance(result, list):
            tools = result                # 旧版：直接返回列表
        else:
            tools = []

        # === 统一转换为字典格式 ===
        # 将 FastMCP 的工具对象转换为简单的字典，方便上层使用
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
            }
            for tool in tools
        ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用 MCP 工具
        
        【学习笔记 - MCP 最核心的操作】
        
        完整的工具调用流程：
        1. LLM 看到工具列表后，决定调用某个工具
        2. Client 将工具名和参数封装为 JSON-RPC 请求，发送给 Server
        3. Server 接收请求，找到对应的 Python 函数并执行
        4. Server 将执行结果封装为 JSON-RPC 响应，返回给 Client
        5. Client 解析响应，提取结果返回给调用方
        
        示例：
            result = await client.call_tool("calculator", {"expression": "2+3"})
            print(result)  # "Result: 5"
        
        Args:
            tool_name: 要调用的工具名称
            arguments: 工具参数字典，键值对应工具的 input_schema
            
        Returns:
            工具执行结果（通常是字符串），无结果时返回 None
        """
        if not self.client:
            raise RuntimeError("Client not connected. Use 'async with client:' context manager.")

        # === 发送工具调用请求 ===
        result = await self.client.call_tool(tool_name, arguments)

        # === 解析结果 ===
        # FastMCP 返回的是 ToolResult 对象，包含 content 列表
        # content 中每个元素可能是：
        # - TextContent: 有 .text 属性（最常见）
        # - DataContent: 有 .data 属性（二进制数据）
        if hasattr(result, 'content') and result.content:
            if len(result.content) == 1:
                # 单个结果：直接返回内容
                content = result.content[0]
                if hasattr(content, 'text'):
                    return content.text      # 文本结果（最常见）
                elif hasattr(content, 'data'):
                    return content.data      # 数据结果
            # 多个结果：返回列表
            return [
                getattr(c, 'text', getattr(c, 'data', str(c)))
                for c in result.content
            ]
        return None

    async def list_resources(self) -> List[Dict[str, Any]]:
        """列出服务器上所有可用的资源（只读数据）
        
        【学习笔记】
        资源是只读的数据，每个资源有一个唯一的 URI。
        
        返回的每个资源包含：
        - uri: 资源唯一标识符（如 "config://database"）
        - name: 资源名称
        - description: 资源描述
        - mime_type: 内容类型（如 "application/json"、"text/plain"）
        
        Returns:
            资源信息字典列表
        """
        if not self.client:
            raise RuntimeError("Client not connected. Use 'async with client:' context manager.")

        result = await self.client.list_resources()
        # 将资源对象转换为简单字典
        return [
            {
                "uri": resource.uri,
                "name": resource.name or "",
                "description": resource.description or "",
                "mime_type": getattr(resource, 'mimeType', None)
            }
            for resource in result.resources
        ]

    async def read_resource(self, uri: str) -> Any:
        """根据 URI 读取资源内容
        
        【学习笔记】
        通过 URI 读取服务器上的资源数据。
        
        示例：
            config = await client.read_resource("config://database")
            print(config)  # {"host": "localhost", "port": 5432}
        
        Args:
            uri: 资源 URI，如 "config://database"、"file:///path/to/file"
            
        Returns:
            资源内容（文本或二进制数据），无内容时返回 None
        """
        if not self.client:
            raise RuntimeError("Client not connected. Use 'async with client:' context manager.")

        result = await self.client.read_resource(uri)

        # === 解析资源内容 ===
        # 资源内容可能是：
        # - 文本（.text）：如 JSON、配置文件、代码
        # - 二进制（.blob）：如图片、PDF
        if hasattr(result, 'contents') and result.contents:
            if len(result.contents) == 1:
                content = result.contents[0]
                if hasattr(content, 'text'):
                    return content.text      # 文本资源
                elif hasattr(content, 'blob'):
                    return content.blob      # 二进制资源
            # 多个内容块：返回列表
            return [
                getattr(c, 'text', getattr(c, 'blob', str(c)))
                for c in result.contents
            ]
        return None

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """列出服务器上所有可用的提示词模板
        
        【学习笔记】
        提示词模板是服务器预定义的高质量 Prompt。
        
        返回的每个模板包含：
        - name: 模板名称（如 "code_review"）
        - description: 模板描述（如 "代码审查提示词"）
        - arguments: 模板接受的参数列表（如 ["code", "language"]）
        
        Returns:
            提示词模板信息字典列表
        """
        if not self.client:
            raise RuntimeError("Client not connected. Use 'async with client:' context manager.")

        result = await self.client.list_prompts()
        return [
            {
                "name": prompt.name,
                "description": prompt.description or "",
                "arguments": getattr(prompt, 'arguments', [])
            }
            for prompt in result.prompts
        ]

    async def get_prompt(self, prompt_name: str, arguments: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """获取提示词内容，返回格式化的消息列表
        
        【学习笔记】
        传入参数，获取服务器生成的提示词。
        返回的是消息列表，格式类似 ChatGPT 的对话格式。
        
        示例：
            messages = await client.get_prompt("code_review", {
                "code": "def add(a, b): return a + b",
                "language": "python"
            })
            # 返回: [{"role": "user", "content": "请审查以下 python 代码..."}]
        
        Args:
            prompt_name: 提示词模板名称
            arguments: 模板参数字典（可选）
            
        Returns:
            消息列表，每个消息包含 role 和 content
        """
        if not self.client:
            raise RuntimeError("Client not connected. Use 'async with client:' context manager.")

        result = await self.client.get_prompt(prompt_name, arguments or {})

        # === 解析提示词消息 ===
        # 服务器返回的是消息列表，每个消息有 role（角色）和 content（内容）
        # role 通常是 "user" 或 "assistant"
        if hasattr(result, 'messages') and result.messages:
            return [
                {
                    "role": msg.role,
                    "content": getattr(msg.content, 'text', str(msg.content)) if hasattr(msg.content, 'text') else str(msg.content)
                }
                for msg in result.messages
            ]
        return []

    async def ping(self) -> bool:
        """测试服务器连接是否正常
        
        【学习笔记】
        类似网络中的 ping 命令，用于检查服务器是否在线。
        发送一个轻量级的请求，看服务器是否响应。
        
        Returns:
            True 表示连接正常，False 表示连接异常
        """
        if not self.client:
            raise RuntimeError("Client not connected. Use 'async with client:' context manager.")
        
        try:
            await self.client.ping()
            return True
        except Exception:
            return False

    def get_transport_info(self) -> Dict[str, Any]:
        """获取当前使用的传输方式信息
        
        【学习笔记】
        调试用的方法，可以查看当前用的是哪种传输方式。
        
        示例：
            info = client.get_transport_info()
            # {"status": "connected", "transport_type": "PythonStdioTransport", ...}
        
        Returns:
            传输信息字典，包含连接状态和传输类型
        """
        if not self.client:
            return {"status": "not_connected"}
        
        transport = getattr(self.client, 'transport', None)
        if transport:
            return {
                "status": "connected",
                "transport_type": type(transport).__name__,
                "transport_info": str(transport)
            }
        return {"status": "unknown"}
