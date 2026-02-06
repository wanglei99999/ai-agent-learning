"""
MCP 协议工具函数

提供上下文管理、消息解析等辅助功能。
这些函数主要用于处理 MCP 协议的数据结构。

【学习笔记】
这个文件是 MCP 模块中最简单的部分，全是纯函数（无状态、无副作用）。
它定义了 MCP 协议中"上下文（Context）"的标准数据格式：
- messages: 对话消息列表（用户说了什么、AI 回了什么）
- tools: 可用工具列表（LLM 能调用哪些函数）
- resources: 可用资源列表（LLM 能读取哪些数据）
- metadata: 元数据（额外的附加信息）

建议阅读顺序：create_context → parse_context → 响应函数
"""

# typing 模块提供类型注解，让代码更易读、IDE 能自动补全
# Dict[str, Any] 表示 "键为字符串、值为任意类型的字典"
# Optional[X] 等价于 Union[X, None]，表示参数可以传 None
from typing import Dict, Any, List, Optional, Union
import json


def create_context(
    messages: Optional[List[Dict[str, Any]]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    resources: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建 MCP 上下文对象
    
    【学习笔记】
    这是一个工厂函数，用于构建标准化的上下文字典。
    上下文 = LLM 做决策时需要的所有信息打包在一起。
    
    语法要点：
    - `messages or []`：如果 messages 为 None，则使用空列表 []
      这是 Python 的短路求值技巧，比 `if messages is None: messages = []` 更简洁
    
    Args:
        messages: 消息列表，如 [{"role": "user", "content": "你好"}]
        tools: 工具列表，如 [{"name": "calculator", "description": "计算器"}]
        resources: 资源列表，如 [{"uri": "file://data.txt", "name": "数据文件"}]
        metadata: 元数据，如 {"session_id": "abc123"}
        
    Returns:
        上下文字典，包含 messages、tools、resources、metadata 四个字段
        
    Example:
        >>> context = create_context(
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     tools=[{"name": "calculator", "description": "计算器"}]
        ... )
    """
    return {
        "messages": messages or [],
        "tools": tools or [],
        "resources": resources or [],
        "metadata": metadata or {}
    }


def parse_context(context: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    解析 MCP 上下文
    
    【学习笔记】
    与 create_context 配对使用：
    - create_context: 创建上下文 → 序列化发送
    - parse_context: 接收数据 → 解析为上下文
    
    这个函数体现了"防御性编程"：
    1. 兼容多种输入格式（字符串 or 字典）
    2. 对无效输入抛出明确的错误信息
    3. 用 setdefault 补全缺失字段，避免后续代码报 KeyError
    
    Args:
        context: 上下文字符串或字典
        
    Returns:
        解析后的上下文字典
        
    Raises:
        ValueError: 如果上下文格式无效
        
    Example:
        >>> context_str = '{"messages": [], "tools": []}'
        >>> parsed = parse_context(context_str)
    """
    # 如果传入的是 JSON 字符串，先解析为字典
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON context: {e}")
    
    if not isinstance(context, dict):
        raise ValueError("Context must be a dictionary or JSON string")
    
    # 确保必需字段存在
    # setdefault(key, default): 如果 key 不存在则设为 default，已存在则不动
    # 这样即使传入的上下文缺少某些字段，也不会在后续使用时报 KeyError
    for field in ["messages", "tools", "resources"]:
        context.setdefault(field, [])
    context.setdefault("metadata", {})
    
    return context


def create_error_response(
    error_message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建标准化的错误响应
    
    【学习笔记】
    统一错误格式的好处：调用方只需要检查 response["error"] 是否存在，
    不用猜测错误信息藏在哪个字段里。这是 API 设计的最佳实践。
    
    Args:
        error_message: 错误消息，如 "Tool not found"
        error_code: 错误代码，如 "TOOL_NOT_FOUND"（便于程序判断错误类型）
        details: 错误详情，如 {"tool_name": "calculator"}（便于调试）
        
    Returns:
        错误响应字典，格式: {"error": {"message": ..., "code": ..., "details": ...}}
        
    Example:
        >>> error = create_error_response("Tool not found", "TOOL_NOT_FOUND")
    """
    response = {
        "error": {
            "message": error_message,
            "code": error_code or "UNKNOWN_ERROR"
        }
    }
    
    if details:
        response["error"]["details"] = details
    
    return response


def create_success_response(
    data: Any,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建标准化的成功响应
    
    【学习笔记】
    与 create_error_response 配对，形成统一的响应格式：
    - 成功: {"success": True, "data": ...}
    - 失败: {"error": {"message": ..., "code": ...}}
    调用方通过检查 "success" 或 "error" 键来判断结果。
    
    Args:
        data: 响应数据，可以是任意类型
        metadata: 元数据（可选）
        
    Returns:
        成功响应字典，格式: {"success": True, "data": ..., "metadata": ...}
        
    Example:
        >>> response = create_success_response({"result": 42})
    """
    response = {
        "success": True,
        "data": data
    }
    
    if metadata:
        response["metadata"] = metadata
    
    return response


__all__ = [
    "create_context",
    "parse_context",
    "create_error_response",
    "create_success_response",
]

