"""记忆系统基础类和配置

本模块是整个记忆系统的基石，定义了三个核心组件：

1. MemoryItem: 记忆项数据结构
   - 使用 Pydantic BaseModel 提供类型验证和序列化能力
   - 标准化的记忆数据格式，确保所有记忆类型使用统一的数据结构

2. MemoryConfig: 记忆系统配置
   - 集中管理所有记忆类型的配置参数
   - 使用 Pydantic 提供默认值和类型检查

3. BaseMemory: 记忆抽象基类
   - 定义所有记忆类型必须实现的统一接口（CRUD 操作）
   - 使用抽象基类（ABC）强制子类实现核心方法
   - 提供通用的辅助方法（ID 生成、重要性计算等）

设计模式：
- 模板方法模式：BaseMemory 定义算法骨架，子类实现具体步骤
- 策略模式：不同的记忆类型实现不同的存储和检索策略

按照第8章架构设计的基础组件实现。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class MemoryItem(BaseModel):
    """记忆项数据结构
    
    这是记忆系统的基本数据单元，类似于数据库中的一条记录。
    使用 Pydantic BaseModel 提供以下能力：
    - 自动类型验证：确保数据类型正确
    - 序列化/反序列化：方便存储和传输
    - JSON Schema 生成：可用于 API 文档
    
    设计理念：
    - 所有记忆类型（working/episodic/semantic/perceptual）共享此结构
    - 通过 memory_type 字段区分不同类型
    - 通过 metadata 字段支持扩展信息
    """
    
    # 唯一标识符，通常使用 UUID
    # 用途：快速查找、更新、删除特定记忆
    id: str
    
    # 记忆的实际内容（文本形式）
    # 对于文本记忆：直接存储文本
    # 对于多模态记忆：存储描述或路径
    content: str
    
    # 记忆类型标识：working/episodic/semantic/perceptual
    # 用途：路由到正确的记忆管理器，应用对应的存储策略
    memory_type: str
    
    # 用户标识符，用于多用户隔离
    # 确保不同用户的记忆不会混淆
    user_id: str
    
    # 记忆创建时间戳
    # 用途：时间查询、TTL 计算、记忆排序
    timestamp: datetime
    
    # 重要性分数 (0.0-1.0)
    # 用途：遗忘策略、记忆整合、检索排序
    # 默认 0.5 表示中等重要性
    importance: float = 0.5
    
    # 元数据字典，存储额外信息
    # 常见用途：
    # - session_id: 会话标识
    # - source: 记忆来源（conversation/document/tool）
    # - tags: 标签列表
    # - embedding: 向量表示（某些实现中）
    # - file_path: 文件路径（感知记忆）
    # - modality: 模态类型（感知记忆）
    metadata: Dict[str, Any] = {}

    class Config:
        # 允许使用任意类型（如 datetime）
        # Pydantic 默认只支持基本类型，此配置允许使用复杂类型
        arbitrary_types_allowed = True

class MemoryConfig(BaseModel):
    """记忆系统配置
    
    集中管理所有记忆类型的配置参数。
    使用 Pydantic BaseModel 提供：
    - 默认值：开箱即用
    - 类型检查：防止配置错误
    - 验证逻辑：确保参数合理
    
    设计原则：
    - 单一配置对象：避免配置分散
    - 合理默认值：适合大多数场景
    - 易于扩展：添加新配置项不影响现有代码
    """
    
    # ========== 通用配置 ==========
    
    # 记忆数据存储根目录
    # SQLite 数据库、文件等都会存储在此目录下
    storage_path: str = "./memory_data"
    
    # 记忆容量上限（用于统计显示）
    # 注意：这是展示用的参考值，实际容量由各记忆类型自己管理
    max_capacity: int = 100
    
    # 重要性阈值（0.0-1.0）
    # 低于此值的记忆可能被遗忘策略清理
    importance_threshold: float = 0.1
    
    # 重要性衰减因子（0.0-1.0）
    # 用于时间衰减算法：importance_new = importance_old * decay_factor
    # 值越小，衰减越快
    decay_factor: float = 0.95

    # ========== 工作记忆特定配置 ==========
    
    # 工作记忆容量限制（条数）
    # 超过此数量会触发清理策略（删除低重要性或旧记忆）
    working_memory_capacity: int = 10
    
    # 工作记忆 Token 限制
    # 用于控制发送给 LLM 的上下文长度
    working_memory_tokens: int = 2000
    
    # 工作记忆 TTL（Time To Live，生存时间）
    # 单位：分钟，超过此时间的记忆会被自动清理
    # 默认 120 分钟 = 2 小时
    working_memory_ttl_minutes: int = 120

    # ========== 感知记忆特定配置 ==========
    
    # 支持的模态类型列表
    # 感知记忆可以处理多种类型的数据
    # - text: 文本
    # - image: 图片（jpg, png 等）
    # - audio: 音频（mp3, wav 等）
    # - video: 视频（mp4, avi 等）
    perceptual_memory_modalities: List[str] = ["text", "image", "audio", "video"]

class BaseMemory(ABC):
    """记忆抽象基类

    使用抽象基类（ABC）定义所有记忆类型的统一接口。
    
    设计模式：
    1. 模板方法模式：
       - 定义算法骨架（CRUD 操作）
       - 子类实现具体细节（不同的存储策略）
    
    2. 策略模式：
       - WorkingMemory: 纯内存 + TTL 策略
       - EpisodicMemory: SQLite + Qdrant 双存储策略
       - SemanticMemory: Neo4j + Qdrant 图谱策略
       - PerceptualMemory: 多模态存储策略
    
    继承此类的子类必须实现所有 @abstractmethod 标记的方法，
    否则无法实例化（Python 会抛出 TypeError）。
    
    这种设计确保了：
    - 接口一致性：所有记忆类型提供相同的操作接口
    - 多态性：可以用 BaseMemory 类型引用任何子类实例
    - 强制实现：子类必须实现核心方法，避免遗漏
    """

    def __init__(self, config: MemoryConfig, storage_backend=None):
        """初始化记忆基类
        
        Args:
            config: 记忆系统配置对象
            storage_backend: 可选的存储后端（SQLite/Neo4j/Qdrant 等）
        """
        # 保存配置对象，子类可以访问所有配置参数
        self.config = config
        
        # 存储后端引用（可选）
        # 不同记忆类型使用不同的存储：
        # - WorkingMemory: None（纯内存）
        # - EpisodicMemory: SQLiteDocumentStore
        # - SemanticMemory: Neo4jStore
        self.storage = storage_backend
        
        # 自动推断记忆类型名称
        # 例如：WorkingMemory -> "working"
        #       EpisodicMemory -> "episodic"
        # 用途：日志记录、统计信息、调试
        self.memory_type = self.__class__.__name__.lower().replace("memory", "")

    @abstractmethod
    def add(self, memory_item: MemoryItem) -> str:
        """添加记忆项（抽象方法，子类必须实现）
        
        这是记忆系统的核心操作之一。
        不同记忆类型的实现策略：
        
        - WorkingMemory: 
          1. 检查容量限制
          2. 存储到内存字典
          3. 设置过期时间
        
        - EpisodicMemory:
          1. 生成向量表示（embedding）
          2. 存储到 SQLite（结构化数据）
          3. 存储到 Qdrant（向量检索）
        
        - SemanticMemory:
          1. 提取三元组（主语-谓语-宾语）
          2. 存储到 Neo4j（知识图谱）
          3. 存储到 Qdrant（语义检索）

        Args:
            memory_item: 记忆项对象，包含所有必需信息

        Returns:
            str: 记忆的唯一标识符（ID）
            
        Raises:
            可能的异常（由子类实现决定）：
            - ValueError: 参数无效
            - StorageError: 存储失败
            - CapacityError: 容量已满
        """
        pass

    @abstractmethod
    def retrieve(self, query: str, limit: int = 5, **kwargs) -> List[MemoryItem]:
        """检索相关记忆（抽象方法，子类必须实现）
        
        这是记忆系统的核心操作之一。
        不同记忆类型的检索策略：
        
        - WorkingMemory:
          简单的关键词匹配（字符串包含）
        
        - EpisodicMemory:
          1. 时间范围查询（SQLite）
          2. 语义相似度查询（Qdrant）
          3. 混合排序（时间 + 相似度 + 重要性）
        
        - SemanticMemory:
          1. 图谱遍历查询（Neo4j）
          2. 关系推理（多跳查询）
          3. 语义检索（Qdrant）

        Args:
            query: 查询字符串（自然语言）
            limit: 返回结果数量上限（默认 5）
            **kwargs: 扩展参数，可能包括：
                - min_importance: 最小重要性阈值
                - time_range: 时间范围（开始时间，结束时间）
                - memory_types: 指定查询的记忆类型列表
                - similarity_threshold: 相似度阈值

        Returns:
            List[MemoryItem]: 相关记忆列表，按相关性降序排序
            
        Note:
            返回的列表可能少于 limit 个（如果匹配结果不足）
        """
        pass

    @abstractmethod
    def update(self, memory_id: str, content: str = None,
               importance: float = None, metadata: Dict[str, Any] = None) -> bool:
        """更新记忆（抽象方法，子类必须实现）
        
        支持部分更新：只更新提供的字段，其他字段保持不变。
        
        实现注意事项：
        - 如果更新 content，可能需要重新生成 embedding
        - 如果更新 importance，可能影响遗忘策略
        - 应该更新 timestamp 或添加 updated_at 字段

        Args:
            memory_id: 要更新的记忆的唯一标识符
            content: 新的内容（可选，None 表示不更新）
            importance: 新的重要性分数（可选，None 表示不更新）
            metadata: 新的元数据（可选，None 表示不更新）
                     注意：通常是合并而不是替换

        Returns:
            bool: 更新是否成功
                 True: 更新成功
                 False: 记忆不存在或更新失败
        """
        pass

    @abstractmethod
    def remove(self, memory_id: str) -> bool:
        """删除记忆（抽象方法，子类必须实现）
        
        永久删除指定的记忆。
        
        实现注意事项：
        - 如果使用多个存储后端，需要从所有后端删除
        - 考虑是否需要软删除（标记为已删除但不真正删除）
        - 删除操作应该是原子的（要么全部成功，要么全部失败）

        Args:
            memory_id: 要删除的记忆的唯一标识符

        Returns:
            bool: 删除是否成功
                 True: 删除成功
                 False: 记忆不存在或删除失败
        """
        pass

    @abstractmethod
    def has_memory(self, memory_id: str) -> bool:
        """检查记忆是否存在（抽象方法，子类必须实现）
        
        快速检查操作，不返回记忆内容。
        用途：
        - 更新前检查记忆是否存在
        - 避免重复添加
        - 验证记忆 ID 的有效性

        Args:
            memory_id: 要检查的记忆的唯一标识符

        Returns:
            bool: 记忆是否存在
                 True: 存在
                 False: 不存在
        """
        pass

    @abstractmethod
    def clear(self):
        """清空所有记忆（抽象方法，子类必须实现）
        
        危险操作：删除当前用户的所有记忆。
        
        实现注意事项：
        - 应该只删除当前 user_id 的记忆（多用户隔离）
        - 如果使用多个存储后端，需要清空所有后端
        - 考虑是否需要确认机制
        - 可能需要记录日志
        
        用途：
        - 测试环境清理
        - 用户请求删除所有数据
        - 重置会话
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息（抽象方法，子类必须实现）
        
        返回当前记忆系统的统计信息，用于监控和调试。
        
        建议包含的统计项：
        - count: 记忆总数
        - memory_type: 记忆类型名称
        - capacity: 容量限制（如果有）
        - oldest_timestamp: 最早记忆的时间
        - newest_timestamp: 最新记忆的时间
        - avg_importance: 平均重要性
        - storage_size: 存储占用大小（字节）

        Returns:
            Dict[str, Any]: 统计信息字典，至少包含 'count' 键
            
        Example:
            {
                "count": 42,
                "memory_type": "working",
                "capacity": 100,
                "avg_importance": 0.65
            }
        """
        pass

    def _generate_id(self) -> str:
        """生成唯一的记忆 ID
        
        使用 UUID4（随机 UUID）生成全局唯一标识符。
        
        UUID4 特点：
        - 128 位随机数
        - 碰撞概率极低（约 10^-18）
        - 不依赖时间戳或 MAC 地址
        - 格式：xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        
        Returns:
            str: UUID 字符串，例如："550e8400-e29b-41d4-a716-446655440000"
        """
        import uuid
        return str(uuid.uuid4())

    def _calculate_importance(self, content: str, base_importance: float = 0.5) -> float:
        """计算记忆重要性分数
        
        这是一个启发式算法，基于内容特征自动评估重要性。
        子类可以重写此方法以实现更复杂的重要性计算。
        
        当前实现的规则：
        1. 基础分数：base_importance（默认 0.5）
        2. 长度加成：内容超过 100 字符 +0.1
        3. 关键词加成：包含重要关键词 +0.2
        
        改进方向：
        - 使用 LLM 评估重要性
        - 基于用户反馈学习
        - 考虑上下文相关性
        - 使用情感分析

        Args:
            content: 记忆内容文本
            base_importance: 基础重要性分数（0.0-1.0）

        Returns:
            float: 计算后的重要性分数，范围 [0.0, 1.0]
                  0.0 = 完全不重要
                  0.5 = 中等重要
                  1.0 = 极其重要
        """
        importance = base_importance

        # 规则 1: 基于内容长度
        # 假设：较长的内容通常包含更多信息，可能更重要
        if len(content) > 100:
            importance += 0.1

        # 规则 2: 基于关键词匹配
        # 假设：包含特定关键词的内容更重要
        important_keywords = ["重要", "关键", "必须", "注意", "警告", "错误"]
        if any(keyword in content for keyword in important_keywords):
            importance += 0.2

        # 确保分数在有效范围内 [0.0, 1.0]
        return max(0.0, min(1.0, importance))

    def __str__(self) -> str:
        """返回记忆对象的字符串表示（用户友好）
        
        用于 print() 和 str() 函数。
        
        Returns:
            str: 格式化的字符串，例如："WorkingMemory(count=5)"
        """
        stats = self.get_stats()
        return f"{self.__class__.__name__}(count={stats.get('count', 0)})"

    def __repr__(self) -> str:
        """返回记忆对象的官方字符串表示（开发者友好）
        
        用于调试和日志记录。
        在交互式环境中直接输入对象名时显示。
        
        Returns:
            str: 与 __str__ 相同的表示
        """
        return self.__str__()
