"""MCP (Model Context Protocol) 协议实现

基于 fastmcp 和 mcp 库的封装，提供简洁的 API 用于：
- 创建 MCP 服务器（需要 fastmcp）
- 连接 MCP 服务器（需要 mcp，可选）
- 管理模型上下文

【学习笔记】
这个文件是 MCP 包的入口，它的作用是：
1. 统一导出：让外部可以用 `from protocols.mcp import MCPServer` 直接导入
2. 优雅降级：用 try/except 包装可选依赖，没装 fastmcp 也不会崩溃

这种“懒加载 + 优雅降级”是 Python 包设计的常见模式：
- 核心功能（utils）无条件导入
- 可选功能（server/client）用 try/except 包装，缺少依赖时提供清晰的错误提示
"""

# 工具函数无额外依赖，始终可用
from .utils import create_context, parse_context

# 服务器需要 fastmcp 库
# 【学习笔记】
# 这里用 try/except 实现“优雅降级”：
# - 如果装了 fastmcp，正常导入 MCPServer
# - 如果没装，创建一个“占位类”，在真正使用时才报错并提示安装命令
# 这样即使用户只想用 Client 而不用 Server，也不会因为缺少 fastmcp 而报错
try:
    from .server import MCPServer
    MCP_SERVER_AVAILABLE = True  # 可以用这个变量检查 Server 是否可用
except ImportError:
    MCP_SERVER_AVAILABLE = False
    # 占位类：实例化时抛出 ImportError，提示用户安装依赖
    class MCPServer:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "MCP server requires the 'fastmcp' library. "
                "Install it with: pip install fastmcp"
            )

# 客户端需要 mcp 库（同样的优雅降级模式）
try:
    from .client import MCPClient
    MCP_CLIENT_AVAILABLE = True
except ImportError:
    MCP_CLIENT_AVAILABLE = False
    class MCPClient:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "MCP client requires the 'mcp' library. "
                "Install it with: pip install mcp"
            )

__all__ = [
    "MCPClient",
    "MCPServer",
    "create_context",
    "parse_context",
]

