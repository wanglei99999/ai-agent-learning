"""Agent基类"""
from abc import ABC, abstractmethod
from typing import Optional, Any
from .message import Message
from .llm import HelloAgentsLLM
from .config import Config


class Agent(ABC):
    """
    Agent抽象基类
    
    所有具体的Agent实现（如SimpleAgent、ReActAgent等）都必须继承此类，
    并实现run()方法来定义自己的执行逻辑。
    
    关键特性：
    - 抽象基类（不能直接实例化，必须由子类继承）
    - 统一的接口规范（所有Agent都有相同的方法签名）
    - 内置历史记录管理
    """
    
    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None
    ):
        """
        初始化Agent
        
        参数：
            name: Agent的名称（用于标识和日志）
            llm: LLM客户端实例（用于调用大语言模型）
            system_prompt: 系统提示词（可选，定义Agent的角色和行为）
            config: 配置对象（可选，包含各种运行参数）
        """
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.config = config or Config()
        self._history: list[Message] = []  # 对话历史记录（私有属性，用下划线开头）

    @abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
        """
        运行Agent（抽象方法，必须由子类实现）
        
        这是Agent的核心方法，定义了Agent如何处理输入并返回输出。
        不同类型的Agent有不同的实现：
        - SimpleAgent: 直接调用LLM
        - ReActAgent: 循环"推理-行动-观察"
        - ReflectionAgent: 执行-评估-反思-改进
        
        参数：
            input_text: 用户输入的文本
            **kwargs: 其他可选参数（如max_iterations、temperature等）
        
        返回：
            str: Agent的最终响应
        """
        pass

    def add_message(self, message: Message):
        """
        添加消息到历史记录
        
        用于记录对话过程中的所有消息（用户输入、AI回复、工具调用等）。
        通常在run()方法内部调用。
        
        参数：
            message: 消息对象
        """
        self._history.append(message)
    
    def clear_history(self):
        """
        清空历史记录
        
        使用场景：
        - 开始新任务时需要清除旧的上下文
        - 避免历史过长导致token消耗过多
        - 测试时需要干净的初始状态
        """
        self._history.clear()
    
    def get_history(self) -> list[Message]:
        """
        获取历史记录的副本
        
        返回副本而非原始列表，防止外部代码意外修改内部状态。
        
        返回：
            list[Message]: 历史消息列表的副本
        """
        return self._history.copy()
    
    def __str__(self) -> str:
        """
        返回Agent的字符串表示
        
        用于print()和日志输出，提供友好的可读信息。
        
        返回：
            str: 格式化的Agent信息
        """
        return f"Agent(name={self.name}, provider={self.llm.provider})"