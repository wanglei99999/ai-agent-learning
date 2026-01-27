"""工作记忆（Working Memory）实现

工作记忆是记忆系统中最基础的类型，用于存储短期、临时的信息。

核心特性：
1. 纯内存存储：不持久化到磁盘，重启后丢失
2. 容量限制：通常 10-20 条记忆
3. TTL 机制：超过一定时间自动过期
4. 优先级管理：使用最小堆维护记忆优先级
5. Token 限制：控制发送给 LLM 的上下文长度

适用场景：
- 对话上下文管理
- 临时任务状态
- 会话级别的信息

数据结构：
- self.memories: List[MemoryItem] - 记忆列表（线性存储）
- self.memory_heap: List[Tuple] - 优先级堆（用于快速找到低优先级记忆）
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import heapq  # Python 标准库的堆（优先级队列）实现

from ..base import BaseMemory, MemoryItem, MemoryConfig

class WorkingMemory(BaseMemory):
    """工作记忆实现
    
    工作记忆是人类认知系统中负责临时存储和处理信息的组件。
    在 AI Agent 中，工作记忆用于维护对话上下文和临时状态。
    
    核心特点：
    1. **容量有限**：通常 10-20 条记忆（模拟人类工作记忆容量）
    2. **时效性强**：会话级别，有 TTL（Time To Live）
    3. **优先级管理**：重要的记忆优先保留
    4. **自动清理**：过期或低优先级的记忆自动删除
    5. **纯内存**：不持久化，速度快
    
    清理策略：
    - TTL 清理：超过 max_age_minutes 的记忆自动删除
    - 容量清理：超过 max_capacity 时删除低优先级记忆
    - Token 清理：超过 max_tokens 时删除低优先级记忆
    
    优先级计算：
    priority = importance × time_decay
    - importance: 记忆的基础重要性（0.0-1.0）
    - time_decay: 时间衰减因子（越旧越小）
    """

    def __init__(self, config: MemoryConfig, storage_backend=None):
        """初始化工作记忆
        
        Args:
            config: 记忆系统配置对象
            storage_backend: 存储后端（工作记忆不使用，传 None）
        """
        # 调用父类初始化
        super().__init__(config, storage_backend)

        # ========== 工作记忆特定配置 ==========
        
        # 容量限制（条数）
        # 超过此数量会触发清理，删除低优先级记忆
        self.max_capacity = self.config.working_memory_capacity
        
        # Token 限制
        # 用于控制发送给 LLM 的上下文长度，避免超过模型限制
        self.max_tokens = self.config.working_memory_tokens
        
        # TTL（Time To Live，生存时间）单位：分钟
        # 从配置中读取，默认 120 分钟（2 小时）
        # 超过此时间的记忆会被自动清理
        self.max_age_minutes = getattr(self.config, 'working_memory_ttl_minutes', 120)
        
        # 当前已使用的 Token 数量
        # 每次添加记忆时累加，删除时减少
        self.current_tokens = 0
        
        # 会话开始时间
        # 用于统计和调试
        self.session_start = datetime.now()
        
        # ========== 数据结构 ==========
        
        # 记忆列表（主存储）
        # 工作记忆不需要持久化，纯内存存储
        self.memories: List[MemoryItem] = []

        # 优先级堆（辅助结构）
        # 用于快速找到最低优先级的记忆（用于删除）
        # 元组格式：(-priority, timestamp, memory_item)
        # - 使用负优先级是因为 heapq 是最小堆，我们需要最大堆效果
        # - timestamp 作为第二排序键，优先级相同时先删除旧的
        self.memory_heap = []

    def add(self, memory_item: MemoryItem) -> str:
        """添加工作记忆
        
        添加流程：
        1. 清理过期记忆（TTL 检查）
        2. 计算新记忆的优先级
        3. 添加到堆和列表
        4. 更新 Token 计数
        5. 检查容量限制（必要时删除低优先级记忆）
        
        Args:
            memory_item: 要添加的记忆项
            
        Returns:
            str: 记忆的唯一标识符（ID）
            
        Example:
            >>> memory = MemoryItem(
            ...     id="mem_001",
            ...     content="用户喜欢喝咖啡",
            ...     memory_type="working",
            ...     user_id="user_123",
            ...     timestamp=datetime.now(),
            ...     importance=0.7
            ... )
            >>> memory_id = working_memory.add(memory)
        """
        # 步骤 1: 清理过期记忆
        # 在添加新记忆前，先删除超过 TTL 的旧记忆
        self._expire_old_memories()
        
        # 步骤 2: 计算优先级
        # priority = importance × time_decay
        # 新记忆的 time_decay 接近 1.0，所以优先级 ≈ importance
        priority = self._calculate_priority(memory_item)

        # 步骤 3: 添加到数据结构
        # 3.1 添加到优先级堆
        # 使用负优先级：-priority，因为 heapq 是最小堆
        # 堆顶是最小值（即原始优先级最低的记忆）
        heapq.heappush(self.memory_heap, (-priority, memory_item.timestamp, memory_item))
        
        # 3.2 添加到记忆列表
        self.memories.append(memory_item)

        # 步骤 4: 更新 Token 计数
        # 简单分词：按空格分割，统计单词数作为 Token 数的近似值
        # 注意：这是简化实现，实际应该使用 tokenizer
        self.current_tokens += len(memory_item.content.split())

        # 步骤 5: 检查容量限制
        # 如果超过容量或 Token 限制，删除低优先级记忆
        self._enforce_capacity_limits()

        # 返回记忆 ID
        return memory_item.id
    
    def retrieve(self, query: str, limit: int = 5, user_id: str = None, **kwargs) -> List[MemoryItem]:
        """检索工作记忆 - 混合语义向量检索和关键词匹配"""
        # 过期清理
        self._expire_old_memories()
        if not self.memories:
            return []
        # 过滤已遗忘的记忆
        active_memories = [m for m in self.memories if not m.metadata.get("forgotten", False)]
        # 按用户ID过滤（如果提供）
        filtered_memories = active_memories
        if user_id:
            filtered_memories = [m for m in active_memories if m.user_id == user_id]

        if not filtered_memories:
            return []
        
        # 尝试语义向量检索（如果有嵌入模型）
        vector_scores = {}
        try:
            # 简单的语义相似度计算（使用TF-IDF或其他轻量级方法）
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            # 准备文档
            documents = [query] + [m.content for m in filtered_memories]
            
            # TF-IDF向量化
            vectorizer = TfidfVectorizer(stop_words=None, lowercase=True)
            tfidf_matrix = vectorizer.fit_transform(documents)
            
            # 计算相似度
            query_vector = tfidf_matrix[0:1]
            doc_vectors = tfidf_matrix[1:]
            similarities = cosine_similarity(query_vector, doc_vectors).flatten()
            
            # 存储向量分数
            for i, memory in enumerate(filtered_memories):
                vector_scores[memory.id] = similarities[i]
                
        except Exception as e:
            # 如果向量检索失败，回退到关键词匹配
            vector_scores = {}
        # 计算最终分数
        query_lower = query.lower()
        scored_memories = []
        
        for memory in filtered_memories:
            content_lower = memory.content.lower()
            
            # 获取向量分数（如果有）
            vector_score = vector_scores.get(memory.id, 0.0)
            
            # 关键词匹配分数
            keyword_score = 0.0
            if query_lower in content_lower:
                keyword_score = len(query_lower) / len(content_lower)
            else:
                # 分词匹配
                query_words = set(query_lower.split())
                content_words = set(content_lower.split())
                intersection = query_words.intersection(content_words)
                if intersection:
                    keyword_score = len(intersection) / len(query_words.union(content_words)) * 0.8

            # 混合分数：向量检索 + 关键词匹配
            if vector_score > 0:
                base_relevance = vector_score * 0.7 + keyword_score * 0.3
            else:
                base_relevance = keyword_score
            
            # 时间衰减
            time_decay = self._calculate_time_decay(memory.timestamp)
            base_relevance *= time_decay
            
            # 重要性权重
            importance_weight = 0.8 + (memory.importance * 0.4)
            final_score = base_relevance * importance_weight
            
            if final_score > 0:
                scored_memories.append((final_score, memory))

    def update(
        self,
        memory_id: str,
        content: str = None,
        importance: float = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """更新工作记忆
        
        允许修改已存在记忆的内容、重要性或元数据。
        更新后会自动重建堆以保持优先级的正确性。
        
        Args:
            memory_id: 要更新的记忆 ID
            content: 新的记忆内容（可选）
            importance: 新的重要性分数 0.0-1.0（可选）
            metadata: 要合并的元数据字典（可选）
            
        Returns:
            bool: 是否更新成功（找到记忆返回 True，否则 False）
            
        Example:
            >>> # 更新内容和重要性
            >>> working_memory.update(
            ...     memory_id="mem_001",
            ...     content="用户非常喜欢咖啡",
            ...     importance=0.9
            ... )
            True
        """
        # 遍历所有记忆，查找匹配的 ID
        for memory in self.memories:
            if memory.id == memory_id:
                # 记录旧的 Token 数量（用于更新计数）
                old_tokens = len(memory.content.split())

                # 1. 更新内容（如果提供）
                if content is not None:
                    memory.content = content
                    
                    # 重新计算 Token 数
                    new_tokens = len(content.split())
                    
                    # 更新总 Token 计数：减去旧的，加上新的
                    # 使用 max(0, ...) 确保不会出现负数
                    self.current_tokens = max(0, self.current_tokens - old_tokens + new_tokens)

                # 2. 更新重要性（如果提供）
                if importance is not None:
                    memory.importance = importance
                
                # 3. 更新元数据（如果提供）
                if metadata is not None:
                    # update() 方法会合并字典，不会覆盖未提供的键
                    memory.metadata.update(metadata)
                
                # 4. 重建堆
                # 因为 importance 或 content 的变化会影响优先级
                # 必须重建堆以保持优先级队列的正确性
                self._update_heap_priority(memory)
                
                return True  # 更新成功
        
        # 未找到匹配的记忆
        return False

    def remove(self, memory_id: str) -> bool:
        """删除工作记忆
        
        从记忆列表和堆中删除指定的记忆。
        
        Args:
            memory_id: 要删除的记忆 ID
            
        Returns:
            bool: 是否删除成功
            
        Example:
            >>> working_memory.remove("mem_001")
            True
        """
        # 遍历记忆列表，找到匹配的记忆
        for i, memory in enumerate(self.memories):  
            if memory.id == memory_id:  
                # 从列表中删除
                removed_memory = self.memories.pop(i)
                
                # 更新 Token 计数
                self.current_tokens -= len(removed_memory.content.split())
                self.current_tokens = max(0, self.current_tokens)
                
                # 重建堆（确保堆和列表同步）
                self._rebuild_heap()
                
                return True
        
        # 未找到匹配的记忆
        return False
    
    def has_memory(self, memory_id: str) -> bool:
        """检查是否存在指定 ID 的记忆
        
        快速检查工作记忆中是否包含某个记忆。
        
        Args:
            memory_id: 要检查的记忆 ID
            
        Returns:
            bool: 存在返回 True，不存在返回 False
            
        时间复杂度：O(n)
        
        Example:
            >>> if working_memory.has_memory("mem_001"):
            ...     print("记忆存在")
        """
        # 使用 any() 和生成器表达式进行高效查找
        # 一旦找到匹配项就立即返回 True，无需遍历所有记忆
        return any(memory.id == memory_id for memory in self.memories)
    
    def clear(self):
        """清空所有工作记忆
        
        删除所有记忆并重置状态。
        通常用于会话结束或需要完全重置记忆系统时。
        
        操作：
        1. 清空记忆列表
        2. 清空优先级堆
        3. 重置 Token 计数为 0
        
        注意：
        - 此操作不可逆
        - session_start 时间不会重置
        
        Example:
            >>> working_memory.clear()
            >>> print(len(working_memory.memories))  # 输出: 0
        """
        # 清空记忆列表
        self.memories.clear()
        
        # 清空优先级堆
        self.memory_heap.clear()
        
        # 重置 Token 计数
        self.current_tokens = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取工作记忆统计信息
        
        返回工作记忆的统计信息，包括记忆数量、Token 使用情况等。
        
        Returns:
            Dict[str, Any]: 统计信息字典
            
        Example:
            >>> stats = working_memory.get_stats()
            >>> print(stats["count"])  # 输出记忆数量
        """
        # 过期清理（惰性）
        self._expire_old_memories()

        # 工作记忆中的记忆都是活跃的（已遗忘的记忆会被直接删除）
        active_memories = self.memories
        return {
            "count": len(active_memories),  # 活跃记忆数量
            "forgotten_count": 0,  # 工作记忆中已遗忘的记忆会被直接删除
            "total_count": len(self.memories),  # 总记忆数量
            "current_tokens": self.current_tokens,
            "max_capacity": self.max_capacity,
            "max_tokens": self.max_tokens,
            "max_age_minutes": self.max_age_minutes,
            "session_duration_minutes": (datetime.now() - self.session_start).total_seconds() / 60,
            "avg_importance": sum(m.importance for m in active_memories) / len(active_memories) if active_memories else 0.0,
            "capacity_usage": len(active_memories) / self.max_capacity if self.max_capacity > 0 else 0.0,
            "token_usage": self.current_tokens / self.max_tokens if self.max_tokens > 0 else 0.0,
            "memory_type": "working"
        }
    def get_recent(self, limit: int = 10) -> List[MemoryItem]:
        """获取最近的记忆"""
        sorted_memories = sorted(
            self.memories, 
            key=lambda x: x.timestamp, 
            reverse=True
        )
        return sorted_memories[:limit]
    
    def get_important(self, limit: int = 10) -> List[MemoryItem]:
        """获取重要记忆"""
        sorted_memories = sorted(
            self.memories,
            key=lambda x: x.importance,
            reverse=True
        )
        return sorted_memories[:limit]

    def get_all(self) -> List[MemoryItem]:
        """获取所有记忆"""
        return self.memories.copy()

    def get_context_summary(self, max_length: int = 500) -> str:
        """获取上下文摘要"""
        if not self.memories:
            return "No working memories available."
         # 按重要性和时间排序
        sorted_memories = sorted(
            self.memories,
            key=lambda m: (m.importance, m.timestamp),
            reverse=True
        )
        summary_parts = []
        current_length = 0
        for memory in sorted_memories:
            content = memory.content
            if current_length + len(content) <= max_length:
                summary_parts.append(content)
                current_length += len(content)
            else:
                # 截断最后一个记忆
                remaining = max_length - current_length
                if remaining > 50:  # 至少保留50个字符
                    summary_parts.append(content[:remaining] + "...")
                break
        
        return "Working Memory Context:\n" + "\n".join(summary_parts)

    def forget(self, strategy: str = "importance_based", threshold: float = 0.1, max_age_days: int = 1) -> int:
        """工作记忆遗忘机制"""
        forgotten_count = 0
        current_time = datetime.now()
        
        to_remove = []
        
        # 始终先执行TTL过期（分钟级）
        cutoff_ttl = current_time - timedelta(minutes=self.max_age_minutes)
        for memory in self.memories:
            if memory.timestamp < cutoff_ttl:
                to_remove.append(memory.id)
        
        if strategy == "importance_based":
            # 删除低重要性记忆
            for memory in self.memories:
                if memory.importance < threshold:
                    to_remove.append(memory.id)
        
        elif strategy == "time_based":
            # 删除过期记忆（工作记忆通常以小时计算）
            cutoff_time = current_time - timedelta(hours=max_age_days * 24)
            for memory in self.memories:
                if memory.timestamp < cutoff_time:
                    to_remove.append(memory.id)
        
        elif strategy == "capacity_based":
            # 删除超出容量的记忆
            if len(self.memories) > self.max_capacity:
                # 按优先级排序，删除最低的
                sorted_memories = sorted(
                    self.memories,
                    key=lambda m: self._calculate_priority(m)
                )
                excess_count = len(self.memories) - self.max_capacity
                for memory in sorted_memories[:excess_count]:
                    to_remove.append(memory.id)
        
        # 执行删除
        for memory_id in to_remove:
            if self.remove(memory_id):
                forgotten_count += 1
        
        return forgotten_count

    def _expire_old_memories(self):
        """按 TTL 清理过期记忆，并同步更新堆与 Token 计数
        
        TTL（Time To Live）机制：
        - 计算截止时间：cutoff_time = now - max_age_minutes
        - 删除所有 timestamp < cutoff_time 的记忆
        - 更新 Token 计数
        - 重建优先级堆
        
        时间复杂度：
        - 遍历记忆列表：O(n)
        - 重建堆：O(n log n)
        
        优化空间：
        - 可以使用惰性删除（标记删除，不立即重建堆）
        - 但为了代码简洁，这里采用立即重建策略
        """
        # 快速检查：如果没有记忆，直接返回
        if not self.memories:
            return
        
        # 计算截止时间点
        # 例如：现在是 15:38，max_age_minutes=120（2小时）
        # cutoff_time = 15:38 - 120分钟 = 13:38
        # 所有在 13:38 之前创建的记忆都过期了
        cutoff_time = datetime.now() - timedelta(minutes=self.max_age_minutes)
        
        # 遍历所有记忆，筛选出未过期的
        kept: List[MemoryItem] = []  # 保留的记忆
        removed_token_sum = 0        # 被删除记忆的 Token 总数
        
        for m in self.memories:
            if m.timestamp >= cutoff_time:
                # 未过期，保留
                kept.append(m)
            else:
                # 已过期，统计其 Token 数（用于更新计数）
                removed_token_sum += len(m.content.split())
        
        # 优化：如果没有记忆被删除，直接返回
        # 避免不必要的堆重建
        if len(kept) == len(self.memories):
            return
        
        # 更新记忆列表
        self.memories = kept
        
        # 更新 Token 计数
        # 使用 max(0, ...) 确保不会出现负数
        self.current_tokens = max(0, self.current_tokens - removed_token_sum)

        # 重建优先级堆
        # 因为删除了一些记忆，堆中可能包含已删除的记忆引用
        # 最简单的方法是清空堆，然后重新添加所有保留的记忆
        self.memory_heap = []
        for mem in self.memories:
            # 重新计算优先级（因为时间衰减会变化）
            priority = self._calculate_priority(mem)
            # 添加到堆中
            heapq.heappush(self.memory_heap, (-priority, mem.timestamp, mem))

    def _calculate_priority(self, memory: MemoryItem) -> float:
        """计算记忆优先级
        
        优先级决定了记忆的保留顺序：
        - 优先级高的记忆优先保留
        - 优先级低的记忆优先删除
        
        计算公式：
        priority = importance × time_decay
        
        组成部分：
        1. importance（重要性）：0.0-1.0
           - 由用户指定或自动计算
           - 反映记忆内容的重要程度
        
        2. time_decay（时间衰减）：0.1-1.0
           - 随时间指数衰减
           - 新记忆 ≈ 1.0，旧记忆逐渐降低
           - 最低保持 0.1（10%）
        
        示例：
        - 新记忆，高重要性：0.9 × 1.0 = 0.9
        - 旧记忆，高重要性：0.9 × 0.7 = 0.63
        - 新记忆，低重要性：0.3 × 1.0 = 0.3
        - 旧记忆，低重要性：0.3 × 0.7 = 0.21
        
        Args:
            memory: 记忆项
            
        Returns:
            float: 优先级分数（0.0-1.0）
        """
        # 基础优先级 = 记忆的重要性分数
        priority = memory.importance
        
        # 应用时间衰减
        # 旧记忆的优先级会逐渐降低
        time_decay = self._calculate_time_decay(memory.timestamp)
        priority *= time_decay
        
        return priority

    def _calculate_time_decay(self, timestamp: datetime) -> float:
        """计算时间衰减因子
        
        时间衰减模拟人类记忆的遗忘曲线：
        - 新记忆清晰（衰减因子 ≈ 1.0）
        - 旧记忆模糊（衰减因子逐渐降低）
        
        衰减公式（指数衰减）：
        decay_factor = base_decay ^ (hours_passed / decay_period)
        
        参数说明：
        - base_decay: 基础衰减率（默认 0.95）
        - decay_period: 衰减周期（6 小时）
        - hours_passed: 经过的小时数
        
        衰减示例（base_decay=0.95）：
        | 时间      | 计算                | 衰减因子 |
        |-----------|---------------------|----------|
        | 刚创建    | 0.95^(0/6)=0.95^0   | 1.000    |
        | 3小时后   | 0.95^(3/6)=0.95^0.5 | 0.975    |
        | 6小时后   | 0.95^(6/6)=0.95^1   | 0.950    |
        | 12小时后  | 0.95^(12/6)=0.95^2  | 0.903    |
        | 24小时后  | 0.95^(24/6)=0.95^4  | 0.815    |
        | 48小时后  | 0.95^(48/6)=0.95^8  | 0.663    |
        
        最小值限制：
        - 衰减因子最低为 0.1（10%）
        - 即使是非常旧的记忆，也保留一定权重
        - 避免完全归零，保持系统稳定性
        
        Args:
            timestamp: 记忆创建时间
            
        Returns:
            float: 时间衰减因子（0.1-1.0）
        """
        # 计算时间差
        time_diff = datetime.now() - timestamp
        
        # 转换为小时数
        # total_seconds() 返回总秒数，除以 3600 得到小时数
        hours_passed = time_diff.total_seconds() / 3600
        
        # 指数衰减计算
        # 工作记忆衰减较快，每 6 小时为一个衰减周期
        # 例如：12 小时后 = 2 个周期 = 0.95^2 = 0.9025
        decay_factor = self.config.decay_factor ** (hours_passed / 6)
        
        # 设置最小值
        # 确保衰减因子不低于 0.1（保留至少 10% 的权重）
        return max(0.1, decay_factor)
    
    def _rebuild_heap(self):
        """重建优先级堆
        
        当记忆被删除后，需要重建堆以保持一致性。
        时间复杂度：O(n log n)
        """
        self.memory_heap = []
        for mem in self.memories:
            priority = self._calculate_priority(mem)
            heapq.heappush(self.memory_heap, (-priority, mem.timestamp, mem))

    def _enforce_capacity_limits(self):
        """强制执行容量限制"""
        # 检查记忆数量限制
        while len(self.memories) >self.max_capacity:
            # 删除优先级最低的记忆
            self._remove_lowest_priority_memory()
        # 检查token限制
        while self.current_tokens > self.max_tokens:
            self._remove_lowest_priority_memory()
    
 

    def _remove_lowest_priority_memory(self):
        """删除优先级最低的记忆（使用堆优化）
        
        从堆中取出优先级最低的记忆并删除。
        时间复杂度：O(log n)
        
        注意：
        - 堆中存储的是 (-priority, timestamp, memory_item)
        - 堆顶是最小值，即原始优先级最低的记忆
        """
        # 检查堆是否为空
        if not self.memory_heap:
            return
        
        # 从堆顶取出最低优先级的记忆
        # heappop 返回并移除堆顶元素
        _, _, lowest_memory = heapq.heappop(self.memory_heap)
        
        # 从记忆列表中删除
        # 使用 in 检查防止堆中有已删除的记忆引用
        if lowest_memory in self.memories:
            self.remove(lowest_memory)
            
            # 更新 Token 计数
            self.current_tokens = max(0, self.current_tokens - len(lowest_memory.content.split()))


    def _update_heap_priority(self, memory: MemoryItem):
        """更新堆中记忆的优先级"""
        # 简单实现：重建堆
        self.memory_heap = []
        for mem in self.memories:
            priority = self._calculate_priority(mem)
            heapq.heappush(self.memory_heap, (-priority, mem.timestamp, mem))