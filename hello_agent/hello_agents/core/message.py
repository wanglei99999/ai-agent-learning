from typing import Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel

# 定义消息角色的类型，限制其取值为 user/assistant/system/tool 四种
MessageRole = Literal["user", "assistant", "system", "tool"]


class Message(BaseModel):
    """
    消息类 - 用于封装 LLM 对话中的单条消息
    
    继承 Pydantic 的 BaseModel，自动获得类型验证和序列化能力
    """

    content: str                              # 消息内容
    role: MessageRole                         # 消息角色：user/assistant/system/tool
    timestamp: datetime = None                # 消息时间戳
    metadata: Optional[Dict[str, Any]] = None # 额外元数据（可选）

    def __init__(self, content: str, role: MessageRole, **kwargs):
        """
        初始化消息
        
        Args:
            content: 消息内容
            role: 消息角色
            **kwargs: 可选参数，包括 timestamp 和 metadata
        """
        # 调用 Pydantic BaseModel 的初始化方法，完成类型验证和赋值
        super().__init__(
            content=content,
            role=role,
            timestamp=kwargs.get('timestamp', datetime.now()),  # 默认使用当前时间
            metadata=kwargs.get('metadata', {})                 # 默认为空字典
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（OpenAI API 格式）
        
        Returns:
            包含 role 和 content 的字典，可直接传给 LLM API
        """
        return {
            "role": self.role,
            "content": self.content
        }
    def __str__(self) -> str:
        """
        返回消息的字符串表示，方便打印和调试
        
        Returns:
            格式为 "[角色] 内容" 的字符串
        """
        return f"[{self.role}] {self.content}"