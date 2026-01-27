"""记忆管理器 - 记忆核心层的统一管理接口

本模块实现了记忆系统的核心管理层，提供：
- 统一的记忆操作接口（添加、检索、更新、删除）
- 多类型记忆的协调管理（工作记忆、情景记忆、语义记忆、感知记忆）
- 记忆生命周期管理（遗忘、整合）
- 自动分类和重要性评估

设计模式：
- **外观模式（Facade）**：为复杂的记忆子系统提供简单统一的接口
- **策略模式（Strategy）**：不同记忆类型使用不同的存储和检索策略

架构位置：
┌─────────────────────────────────────┐
│           Agent / Tool              │  ← 调用层
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│         MemoryManager               │  ← 本模块（管理层）
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│  Working │ Episodic │ Semantic │ ...│  ← 记忆类型层
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│     SQLite    │    Qdrant    │ ...  │  ← 存储层
└─────────────────────────────────────┘
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid
import logging

from .base import MemoryItem, MemoryConfig
from .types.working import WorkingMemory
from .types.episodic import EpisodicMemory
from .types.semantic import SemanticMemory
from .types.perceptual import PerceptualMemory

logger = logging.getLogger(__name__)

class MemoryManager:
    """记忆管理器 - 统一的记忆操作接口
    
    这是记忆系统的核心入口，Agent 和 Tool 通过它来操作记忆。
    它封装了四种记忆类型的复杂性，提供简单统一的 API。
    
    核心职责：
    1. **统一接口**：add_memory(), retrieve_memories(), update_memory(), remove_memory()
    2. **自动分类**：根据内容自动判断应该存入哪种记忆类型
    3. **重要性评估**：自动计算记忆的重要性分数
    4. **生命周期管理**：遗忘（forget）和整合（consolidate）
    
    四种记忆类型：
    - **working**：工作记忆 - 短期上下文，纯内存，自动过期
    - **episodic**：情景记忆 - 历史事件，SQLite + Qdrant 持久化
    - **semantic**：语义记忆 - 知识概念，知识图谱存储
    - **perceptual**：感知记忆 - 多模态数据（图片、音频等）
    
    使用示例：
        >>> manager = MemoryManager(user_id="user_123")
        >>> 
        >>> # 添加记忆（自动分类）
        >>> manager.add_memory("用户喜欢咖啡")
        >>> manager.add_memory("昨天讨论了 AI 话题")  # 自动分类为 episodic
        >>> 
        >>> # 检索记忆
        >>> memories = manager.retrieve_memories("用户喜好")
        >>> 
        >>> # 记忆整合（工作记忆 → 情景记忆）
        >>> manager.consolidate_memories()
    """
    
    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        user_id: str = "default_user",
        enable_working: bool = True,
        enable_episodic: bool = True,
        enable_semantic: bool = True,
        enable_perceptual: bool = False
    ):
        """初始化记忆管理器
        
        Args:
            config: 记忆系统配置，包含容量限制、衰减因子等参数
            user_id: 用户标识，用于隔离不同用户的记忆
            enable_working: 是否启用工作记忆（默认启用）
            enable_episodic: 是否启用情景记忆（默认启用）
            enable_semantic: 是否启用语义记忆（默认启用）
            enable_perceptual: 是否启用感知记忆（默认禁用，需要额外配置）
        """
        # 使用传入的配置，或创建默认配置
        self.config = config or MemoryConfig()
        self.user_id = user_id
        
        # ========== 初始化各类型记忆 ==========
        # 使用字典存储，方便动态访问和遍历
        # key: 记忆类型名称（字符串）
        # value: 记忆实例（WorkingMemory, EpisodicMemory 等）
        self.memory_types: Dict[str, Any] = {}
        
        # 工作记忆：短期上下文，纯内存
        if enable_working:
            self.memory_types['working'] = WorkingMemory(self.config)
        
        # 情景记忆：历史事件，持久化存储
        if enable_episodic:
            self.memory_types['episodic'] = EpisodicMemory(self.config)
        
        # 语义记忆：知识概念，知识图谱
        if enable_semantic:
            self.memory_types['semantic'] = SemanticMemory(self.config)
        
        # 感知记忆：多模态数据（默认禁用）
        if enable_perceptual:
            self.memory_types['perceptual'] = PerceptualMemory(self.config)
        
        logger.info(f"MemoryManager初始化完成，启用记忆类型: {list(self.memory_types.keys())}")
    
    def add_memory(
        self,
        content: str,
        memory_type: str = "working",
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_classify: bool = True
    ) -> str:
        """添加记忆 - 记忆系统的主要入口
        
        这是最常用的方法，用于将新信息存入记忆系统。
        支持自动分类和重要性评估，简化调用方的使用。
        
        Args:
            content: 记忆内容（必填）
            memory_type: 记忆类型，默认 "working"
                - "working": 工作记忆（短期）
                - "episodic": 情景记忆（历史事件）
                - "semantic": 语义记忆（知识概念）
                - "perceptual": 感知记忆（多模态）
            importance: 重要性分数 0.0-1.0，None 时自动计算
            metadata: 元数据字典，可包含 session_id, context, tags 等
            auto_classify: 是否自动分类（默认 True）
                - True: 根据内容关键词自动判断记忆类型
                - False: 使用指定的 memory_type
            
        Returns:
            str: 记忆的唯一 ID（UUID 格式）
            
        Raises:
            ValueError: 当指定的 memory_type 未启用时
            
        Example:
            >>> # 自动分类
            >>> manager.add_memory("用户喜欢咖啡")  # → working
            >>> manager.add_memory("昨天讨论了 AI")  # → episodic（含时间词）
            >>> manager.add_memory("Python 是一种编程语言")  # → semantic（含定义词）
            >>> 
            >>> # 指定类型
            >>> manager.add_memory("重要会议", memory_type="episodic", auto_classify=False)
        """
        # ========== 步骤 1: 自动分类记忆类型 ==========
        # 如果启用自动分类，根据内容关键词判断应该存入哪种记忆
        if auto_classify:
            memory_type = self._classify_memory_type(content, metadata)
        
        # ========== 步骤 2: 计算重要性 ==========
        # 如果未指定重要性，根据内容和元数据自动计算
        if importance is None:
            importance = self._calculate_importance(content, metadata)
        
        # ========== 步骤 3: 创建记忆项 ==========
        # 封装为统一的 MemoryItem 对象
        memory_item = MemoryItem(
            id=str(uuid.uuid4()),      # 生成唯一 ID
            content=content,            # 记忆内容
            memory_type=memory_type,    # 记忆类型
            user_id=self.user_id,       # 用户标识
            timestamp=datetime.now(),   # 创建时间
            importance=importance,      # 重要性分数
            metadata=metadata or {}     # 元数据
        )
        
        # ========== 步骤 4: 添加到对应的记忆类型 ==========
        if memory_type in self.memory_types:
            # 调用具体记忆类型的 add() 方法
            memory_id = self.memory_types[memory_type].add(memory_item)
            logger.debug(f"添加记忆到 {memory_type}: {memory_id}")
            return memory_id
        else:
            raise ValueError(f"不支持的记忆类型: {memory_type}")
    
    def retrieve_memories(
        self,
        query: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 10,
        min_importance: float = 0.0,
        time_range: Optional[tuple] = None
    ) -> List[MemoryItem]:
        """检索记忆 - 跨类型的统一检索接口
        
        从多个记忆类型中检索相关记忆，合并结果并按重要性排序。
        这是 Agent 获取上下文信息的主要方法。
        
        检索流程：
        1. 确定要检索的记忆类型
        2. 并行从各类型中检索
        3. 合并结果并按重要性排序
        4. 返回 Top-K 结果
        
        Args:
            query: 查询内容（自然语言）
            memory_types: 要检索的记忆类型列表，None 表示检索所有启用的类型
            limit: 返回数量限制（默认 10）
            min_importance: 最小重要性阈值，过滤低于此值的记忆
            time_range: 时间范围过滤 (start_time, end_time)
            
        Returns:
            List[MemoryItem]: 检索到的记忆列表，按重要性降序排列
            
        Example:
            >>> # 从所有类型检索
            >>> memories = manager.retrieve_memories("用户喜好")
            >>> 
            >>> # 只从工作记忆检索
            >>> memories = manager.retrieve_memories("用户喜好", memory_types=["working"])
            >>> 
            >>> # 只检索重要记忆
            >>> memories = manager.retrieve_memories("用户喜好", min_importance=0.7)
        """
        # 如果未指定类型，检索所有启用的记忆类型
        if memory_types is None:
            memory_types = list(self.memory_types.keys())
        
        # ========== 从各个记忆类型中检索 ==========
        all_results = []
        
        # 计算每个类型的检索数量限制
        # 例如：limit=10, 3 个类型 → 每个类型检索 3 条
        per_type_limit = max(1, limit // len(memory_types))

        for memory_type in memory_types:
            if memory_type in self.memory_types: 
                memory_instance = self.memory_types[memory_type] # 获取记忆类型实例
                try:
                    # 调用各记忆类型自己的 retrieve() 方法
                    # 不同类型有不同的检索策略：
                    # - working: TF-IDF + 关键词匹配
                    # - episodic: 向量语义检索（Qdrant）
                    # - semantic: 知识图谱查询
                    type_results = memory_instance.retrieve(
                        query=query,
                        limit=per_type_limit,
                        min_importance=min_importance,
                        user_id=self.user_id
                    )
                    all_results.extend(type_results)
                except Exception as e:
                    # 某个类型检索失败不影响其他类型
                    logger.warning(f"检索 {memory_type} 记忆时出错: {e}")
                    continue

        # ========== 合并排序 ==========
        # 按重要性降序排列，返回 Top-K
        all_results.sort(key=lambda x: x.importance, reverse=True)
        return all_results[:limit]
    
    def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """更新记忆
        
        Args:
            memory_id: 记忆ID
            content: 新内容
            importance: 新重要性
            metadata: 新元数据
            
        Returns:
            是否更新成功
        """
        # 查找记忆所在的类型
        for memory_type, memory_instance in self.memory_types.items():
            if memory_instance.has_memory(memory_id):
                return memory_instance.update(memory_id, content, importance, metadata)
        
        logger.warning(f"未找到记忆: {memory_id}")
        return False
    
    def remove_memory(self, memory_id: str) -> bool:
        """删除记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否删除成功
        """
        for memory_type, memory_instance in self.memory_types.items():
            if memory_instance.has_memory(memory_id):
                return memory_instance.remove(memory_id)
        
        logger.warning(f"未找到记忆: {memory_id}")
        return False
    
    def forget_memories(
        self,
        strategy: str = "importance_based",
        threshold: float = 0.1,
        max_age_days: int = 30
    ) -> int:
        """记忆遗忘机制 - 模拟人类的遗忘过程
        
        定期清理不重要或过期的记忆，保持记忆系统的健康状态。
        这是记忆生命周期管理的重要组成部分。
        
        遗忘策略：
        1. **importance_based**（基于重要性）：
           - 删除重要性低于 threshold 的记忆
           - 适用于清理无关紧要的信息
           
        2. **time_based**（基于时间）：
           - 删除超过 max_age_days 天的记忆
           - 适用于清理过时信息
           
        3. **capacity_based**（基于容量）：
           - 当超过容量限制时，删除最不重要的记忆
           - 适用于控制存储空间
        
        Args:
            strategy: 遗忘策略名称
            threshold: 重要性阈值（用于 importance_based）
            max_age_days: 最大保存天数（用于 time_based）
            
        Returns:
            int: 被遗忘（删除）的记忆数量
            
        Example:
            >>> # 删除重要性低于 0.2 的记忆
            >>> count = manager.forget_memories(strategy="importance_based", threshold=0.2)
            >>> 
            >>> # 删除 30 天前的记忆
            >>> count = manager.forget_memories(strategy="time_based", max_age_days=30)
        """
        total_forgotten = 0
        
        # 遍历所有记忆类型，调用各自的 forget() 方法
        for memory_type, memory_instance in self.memory_types.items():
            if hasattr(memory_instance, 'forget'):
                forgotten = memory_instance.forget(strategy, threshold, max_age_days)
                total_forgotten += forgotten

        logger.info(f"记忆遗忘完成: {total_forgotten} 条记忆")
        return total_forgotten

    def consolidate_memories(
        self,
        from_type: str = "working",
        to_type: str = "episodic",
        importance_threshold: float = 0.7
    ) -> int:
        """记忆整合 - 将重要的短期记忆转换为长期记忆
        
        模拟人类睡眠时的记忆整合过程：
        - 重要的工作记忆 → 情景记忆（长期保存）
        - 重复出现的情景 → 语义记忆（抽象为知识）
        
        整合流程：
        1. 从源记忆中筛选高重要性记忆
        2. 从源记忆中删除
        3. 提升重要性（×1.1）
        4. 添加到目标记忆
        
        典型使用场景：
        - 对话结束时，将重要的工作记忆整合到情景记忆
        - 定期任务，将频繁出现的模式整合为知识
        
        Args:
            from_type: 源记忆类型（默认 "working"）
            to_type: 目标记忆类型（默认 "episodic"）
            importance_threshold: 重要性阈值，只整合高于此值的记忆

        Returns:
            int: 整合的记忆数量
            
        Example:
            >>> # 对话结束时，整合重要的工作记忆
            >>> count = manager.consolidate_memories(
            ...     from_type="working",
            ...     to_type="episodic",
            ...     importance_threshold=0.7
            ... )
            >>> print(f"整合了 {count} 条记忆")
        """
        # 检查记忆类型是否存在
        if from_type not in self.memory_types or to_type not in self.memory_types:
            logger.warning(f"记忆类型不存在: {from_type} -> {to_type}")
            return 0

        # 获取源和目标记忆实例
        source_memory = self.memory_types[from_type]
        target_memory = self.memory_types[to_type]

        # ========== 筛选候选记忆 ==========
        # 只整合重要性高于阈值的记忆
        all_memories = source_memory.get_all()
        candidates = [
            m for m in all_memories
            if m.importance >= importance_threshold
        ]

        # ========== 执行整合 ==========
        consolidated_count = 0
        for memory in candidates:
            # 1. 从源记忆中删除
            if source_memory.remove(memory.id):
                # 2. 修改记忆类型
                memory.memory_type = to_type
                
                # 3. 提升重要性（被整合说明很重要）
                memory.importance = min(1.0, memory.importance * 1.1)
                
                # 4. 添加到目标记忆
                target_memory.add(memory)
                consolidated_count += 1

        logger.info(f"记忆整合完成: {consolidated_count} 条记忆从 {from_type} 转移到 {to_type}")
        return consolidated_count

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        stats = {
            "user_id": self.user_id,
            "enabled_types": list(self.memory_types.keys()),
            "total_memories": 0,
            "memories_by_type": {},
            "config": {
                "max_capacity": self.config.max_capacity,
                "importance_threshold": self.config.importance_threshold,
                "decay_factor": self.config.decay_factor
            }
        }

        for memory_type, memory_instance in self.memory_types.items():
            type_stats = memory_instance.get_stats()
            stats["memories_by_type"][memory_type] = type_stats
            # 使用count字段（活跃记忆数），而不是total_count（包含已遗忘的）
            stats["total_memories"] += type_stats.get("count", 0)

        return stats

    def clear_all_memories(self):
        """清空所有记忆"""
        for memory_type, memory_instance in self.memory_types.items():
            memory_instance.clear()
        logger.info("所有记忆已清空")




    # ========== 内部辅助方法 ==========
    
    def _classify_memory_type(self, content: str, metadata: Optional[Dict[str, Any]]) -> str:
        """自动分类记忆类型
        
        根据内容关键词判断应该存入哪种记忆类型。
        这是一个简单的基于规则的分类器，可以扩展为 ML 模型。
        
        分类优先级：
        1. 元数据中显式指定的类型
        2. 情景记忆（含时间词）
        3. 语义记忆（含定义词）
        4. 工作记忆（默认）
        
        Args:
            content: 记忆内容
            metadata: 元数据
            
        Returns:
            str: 记忆类型名称
        """
        # 优先使用元数据中指定的类型
        if metadata and metadata.get("type"):
            return metadata["type"]
        
        # 基于关键词的简单分类
        if self._is_episodic_content(content):
            return "episodic"
        elif self._is_semantic_content(content):
            return "semantic"
        else:
            return "working"  # 默认存入工作记忆
    
    def _is_episodic_content(self, content: str) -> bool:
        """判断是否为情景记忆内容
        
        情景记忆特征：包含时间相关词汇，描述具体事件
        """
        # 时间相关关键词
        episodic_keywords = ["昨天", "今天", "明天", "上次", "记得", "发生", "经历"]
        return any(keyword in content for keyword in episodic_keywords)
    
    def _is_semantic_content(self, content: str) -> bool:
        """判断是否为语义记忆内容
        
        语义记忆特征：包含定义、概念、知识性描述
        """
        # 知识定义相关关键词
        semantic_keywords = ["定义", "概念", "规则", "知识", "原理", "方法"]
        return any(keyword in content for keyword in semantic_keywords)
    
    def _calculate_importance(self, content: str, metadata: Optional[Dict[str, Any]]) -> float:
        """计算记忆重要性
        
        基于多个因素综合评估记忆的重要性分数。
        
        评分规则：
        - 基础分：0.5
        - 内容长度 > 100：+0.1
        - 含重要关键词：+0.2
        - 元数据 priority=high：+0.3
        - 元数据 priority=low：-0.2
        
        Args:
            content: 记忆内容
            metadata: 元数据
            
        Returns:
            float: 重要性分数 0.0-1.0
        """
        importance = 0.5  # 基础重要性
        
        # 因素 1: 内容长度（长内容可能更重要）
        if len(content) > 100:
            importance += 0.1
        
        # 因素 2: 关键词检测
        important_keywords = ["重要", "关键", "必须", "注意", "警告", "错误"]
        if any(keyword in content for keyword in important_keywords):
            importance += 0.2
        
        # 因素 3: 元数据中的优先级标记
        if metadata:
            if metadata.get("priority") == "high":
                importance += 0.3
            elif metadata.get("priority") == "low":
                importance -= 0.2
        
        # 确保在 [0.0, 1.0] 范围内
        return max(0.0, min(1.0, importance))
    

    def __str__(self) -> str:
        stats = self.get_memory_stats()
        return f"MemoryManager(user={self.user_id}, total={stats['total_memories']})"
