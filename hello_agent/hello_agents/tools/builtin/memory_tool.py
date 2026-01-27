"""记忆工具 - Agent 的记忆能力封装

本模块将记忆系统封装为 Tool，使 Agent 可以通过工具调用来操作记忆。
这是记忆系统与 Agent 之间的桥梁。

设计模式：
- **适配器模式（Adapter）**：将 MemoryManager 的接口适配为 Tool 接口
- **外观模式（Facade）**：简化记忆操作，提供统一的 action 参数

架构位置：
┌─────────────────────────────────────────────────┐
│                    Agent                        │
│         agent.run("记住用户喜欢咖啡")           │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│                 MemoryTool                      │  ← 本模块
│   action="add" → _add_memory()                 │
│   action="search" → _search_memory()           │
│   action="forget" → _forget()                  │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│               MemoryManager                     │
│   add_memory(), retrieve_memories(), ...       │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  WorkingMemory │ EpisodicMemory │ SemanticMemory│
└─────────────────────────────────────────────────┘

支持的操作（action 参数）：
- add: 添加记忆
- search: 搜索记忆
- summary: 获取记忆摘要
- stats: 获取统计信息
- update: 更新记忆
- remove: 删除记忆
- forget: 批量遗忘
- consolidate: 记忆整合
- clear_all: 清空所有记忆

使用示例：
    >>> from hello_agents.tools.builtin import MemoryTool
    >>> 
    >>> # 创建记忆工具
    >>> memory_tool = MemoryTool(user_id="user_123")
    >>> 
    >>> # 添加记忆
    >>> result = memory_tool.run({"action": "add", "content": "用户喜欢咖啡"})
    >>> 
    >>> # 搜索记忆
    >>> result = memory_tool.run({"action": "search", "query": "用户喜好"})
    >>> 
    >>> # 添加到 Agent
    >>> agent = MyAgent(tools=[memory_tool])
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from ..base import Tool, ToolParameter, tool_action
from ...memory import MemoryManager, MemoryConfig

class MemoryTool(Tool):
    """记忆工具 - 让 Agent 具备记忆能力
    
    这是记忆系统的工具封装，继承自 Tool 基类。
    Agent 可以通过调用这个工具来存储、检索和管理记忆。
    
    核心功能：
    1. **记忆存储**：add - 添加新记忆到指定类型
    2. **记忆检索**：search - 语义搜索相关记忆
    3. **记忆管理**：update/remove/forget/consolidate
    4. **状态查询**：summary/stats - 获取记忆系统状态
    
    两种使用模式：
    1. **非展开模式**（expandable=False）：
       - 通过 run() 方法调用，使用 action 参数指定操作
       - 适合 Function Calling 场景
       
    2. **展开模式**（expandable=True）：
       - 每个操作作为独立的工具暴露
       - 适合需要细粒度控制的场景
    
    使用示例：
        >>> # 创建工具
        >>> tool = MemoryTool(user_id="user_123")
        >>> 
        >>> # 添加记忆
        >>> tool.run({"action": "add", "content": "用户喜欢咖啡", "importance": 0.8})
        >>> 
        >>> # 搜索记忆
        >>> tool.run({"action": "search", "query": "用户喜好", "limit": 5})
        >>> 
        >>> # 记忆整合
        >>> tool.run({"action": "consolidate", "from_type": "working", "to_type": "episodic"})
    """

    def __init__(
        self,
        user_id: str = "default_user",
        memory_config: MemoryConfig = None,
        memory_types: List[str] = None,
        expandable: bool = False
    ):
        """初始化记忆工具
        
        Args:
            user_id: 用户标识，用于隔离不同用户的记忆
            memory_config: 记忆系统配置，包含容量限制、衰减因子等
            memory_types: 要启用的记忆类型列表
                - "working": 工作记忆（短期，纯内存）
                - "episodic": 情景记忆（长期，持久化）
                - "semantic": 语义记忆（知识，持久化）
                - "perceptual": 感知记忆（多模态）
            expandable: 是否展开为多个独立工具
                - False: 单一工具，通过 action 参数区分操作
                - True: 每个操作作为独立工具暴露
        """
        # 调用父类构造函数，注册工具基本信息
        super().__init__(
            name="memory",
            description="记忆工具 - 可以存储和检索对话历史、知识和经验",
            expandable=expandable
        )

        # ========== 初始化记忆管理器 ==========
        # 使用传入的配置，或创建默认配置
        self.memory_config = memory_config or MemoryConfig()
        
        # 默认启用三种记忆类型（不含感知记忆）
        self.memory_types = memory_types or ["working", "episodic", "semantic"]

        # 创建 MemoryManager 实例
        # 根据 memory_types 列表决定启用哪些记忆类型
        self.memory_manager = MemoryManager(
            config=self.memory_config,
            user_id=user_id,
            enable_working="working" in self.memory_types,
            enable_episodic="episodic" in self.memory_types,
            enable_semantic="semantic" in self.memory_types,
            enable_perceptual="perceptual" in self.memory_types
        )

        # ========== 会话状态管理 ==========
        # 当前会话 ID，用于关联同一会话的记忆
        self.current_session_id = None
        # 对话轮次计数
        self.conversation_count = 0

    def run(self, parameters: Dict[str, Any]) -> str: 
        """执行工具（非展开模式）- Tool 基类要求的核心方法
        
        这是工具的主入口，根据 action 参数路由到对应的内部方法。
        这种设计让一个工具可以支持多种操作，简化 Agent 的工具管理。
        
        路由表：
        - action="add"         → _add_memory()
        - action="search"      → _search_memory()
        - action="summary"     → _get_summary()
        - action="stats"       → _get_stats()
        - action="update"      → _update_memory()
        - action="remove"      → _remove_memory()
        - action="forget"      → _forget()
        - action="consolidate" → _consolidate()
        - action="clear_all"   → _clear_all()

        Args:
            parameters: 工具参数字典，必须包含 action 参数
                - action: 操作类型（必填）
                - 其他参数根据 action 不同而不同

        Returns:
            str: 执行结果的格式化字符串
        """
        # 参数验证
        if not self.validate_parameters(parameters):
            return "参数验证失败：缺少必需的参数"

        action = parameters.get("action")

        # ========== 根据 action 路由到对应方法 ==========
        if action == "add":
            return self._add_memory(
                content=parameters.get("content", ""),
                memory_type=parameters.get("memory_type", "working"),
                importance=parameters.get("importance", 0.5),
                file_path=parameters.get("file_path"),
                modality=parameters.get("modality")
            )
        elif action == "search":
            return self._search_memory(
                query=parameters.get("query"),
                limit=parameters.get("limit", 5),
                memory_type=parameters.get("memory_type"),
                min_importance=parameters.get("min_importance", 0.1)
            )
        elif action == "summary":
            return self._get_summary(limit=parameters.get("limit", 10))
        elif action == "stats":
            return self._get_stats()
        elif action == "update":
            return self._update_memory(
                memory_id=parameters.get("memory_id"),
                content=parameters.get("content"),
                importance=parameters.get("importance")
            )
        elif action == "remove":
            return self._remove_memory(memory_id=parameters.get("memory_id"))
        elif action == "forget":
            return self._forget(
                strategy=parameters.get("strategy", "importance_based"),
                threshold=parameters.get("threshold", 0.1),
                max_age_days=parameters.get("max_age_days", 30)
            )
        elif action == "consolidate":
            return self._consolidate(
                from_type=parameters.get("from_type", "working"),
                to_type=parameters.get("to_type", "episodic"),
                importance_threshold=parameters.get("importance_threshold", 0.7)
            )
        elif action == "clear_all":
            return self._clear_all()
        else:
            return f"不支持的操作: {action}"

    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义 - Tool 基类要求的接口
        
        返回工具支持的所有参数定义，用于：
        1. 生成 OpenAI Function Calling 的 schema
        2. 参数验证
        3. 帮助文档生成
        
        参数分类：
        - 通用参数：action（必填）
        - 添加相关：content, memory_type, importance, file_path, modality
        - 搜索相关：query, limit, min_importance
        - 更新/删除：memory_id
        - 遗忘相关：strategy, threshold, max_age_days
        - 整合相关：from_type, to_type, importance_threshold
        
        Returns:
            List[ToolParameter]: 参数定义列表
        """
        return [
            ToolParameter(
                name="action",
                type="string",
                description=(
                    "要执行的操作："
                    "add(添加记忆), search(搜索记忆), summary(获取摘要), stats(获取统计), "
                    "update(更新记忆), remove(删除记忆), forget(遗忘记忆), consolidate(整合记忆), clear_all(清空所有记忆)"
                ),
                required=True
            ),
            ToolParameter(name="content", type="string", description="记忆内容（add/update时可用；感知记忆可作描述）", required=False),
            ToolParameter(name="query", type="string", description="搜索查询（search时可用）", required=False),
            ToolParameter(name="memory_type", type="string", description="记忆类型：working, episodic, semantic, perceptual（默认：working）", required=False, default="working"),
            ToolParameter(name="importance", type="number", description="重要性分数，0.0-1.0（add/update时可用）", required=False),
            ToolParameter(name="limit", type="integer", description="搜索结果数量限制（默认：5）", required=False, default=5),
            ToolParameter(name="memory_id", type="string", description="目标记忆ID（update/remove时必需）", required=False),
            ToolParameter(name="file_path", type="string", description="感知记忆：本地文件路径（image/audio）", required=False),
            ToolParameter(name="modality", type="string", description="感知记忆模态：text/image/audio（不传则按扩展名推断）", required=False),
            ToolParameter(name="strategy", type="string", description="遗忘策略：importance_based/time_based/capacity_based（forget时可用）", required=False, default="importance_based"),
            ToolParameter(name="threshold", type="number", description="遗忘阈值（forget时可用，默认0.1）", required=False, default=0.1),
            ToolParameter(name="max_age_days", type="integer", description="最大保留天数（forget策略为time_based时可用）", required=False, default=30),
            ToolParameter(name="from_type", type="string", description="整合来源类型（consolidate时可用，默认working）", required=False, default="working"),
            ToolParameter(name="to_type", type="string", description="整合目标类型（consolidate时可用，默认episodic）", required=False, default="episodic"),
            ToolParameter(name="importance_threshold", type="number", description="整合重要性阈值（默认0.7）", required=False, default=0.7),
        ]

    # ========== 核心操作方法 ==========
    # 以下方法使用 @tool_action 装饰器，支持展开模式
    
    @tool_action("memory_add", "添加新记忆到记忆系统中")
    def _add_memory(
        self,
        content: str = "",
        memory_type: str = "working",
        importance: float = 0.5,
        file_path: str = None,
        modality: str = None
    ) -> str:
        """添加记忆 - 记忆系统的主要入口
        
        将新信息存入指定类型的记忆中。
        支持文本记忆和多模态记忆（图片、音频）。

        Args:
            content: 记忆内容（文本描述）
            memory_type: 记忆类型
                - "working": 工作记忆（短期，自动过期）
                - "episodic": 情景记忆（长期，持久化）
                - "semantic": 语义记忆（知识，持久化）
                - "perceptual": 感知记忆（多模态）
            importance: 重要性分数 0.0-1.0，影响检索排序和遗忘优先级
            file_path: 感知记忆的文件路径（图片/音频）
            modality: 感知记忆的模态类型（text/image/audio）

        Returns:
            str: 执行结果，包含记忆 ID
            
        Example:
            >>> tool._add_memory("用户喜欢咖啡", memory_type="working", importance=0.8)
            '✅ 记忆已添加 (ID: a1b2c3d4...)'
        """
        metadata = {}
        try:
            # 步骤1: 确保会话ID存在（用于关联同一会话的记忆）
            if self.current_session_id is None:
                self.current_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 步骤2: 处理感知记忆（图片/音频）
            # 如果是感知记忆且提供了文件路径，需要推断模态类型
            if memory_type == "perceptual" and file_path:
                #用户指定文件类型或者由路径做推断
                inferred = modality or self._infer_modality(file_path)  # 自动推断或使用指定的模态
                metadata.setdefault("modality", inferred)  # 存储模态类型
                metadata.setdefault("raw_data", file_path)  # 存储文件路径

            # 步骤3: 添加会话信息到元数据（用于追踪和过滤）
            metadata.update({
                "session_id": self.current_session_id,  # 会话标识
                "timestamp": datetime.now().isoformat()  # 创建时间戳
            })

            # 步骤4: 调用 MemoryManager 添加记忆（适配器模式的核心）
            memory_id = self.memory_manager.add_memory(
                content=content,
                memory_type=memory_type,
                importance=importance,
                metadata=metadata,
                auto_classify=False  # 禁用自动分类，使用明确指定的类型
            )

            return f"记忆已添加 (ID: {memory_id[:8]}...)"
        except Exception as e:
            return f"添加记忆失败: {str(e)}"

    def _infer_modality(self, path: str) -> str:
        """根据文件扩展名推断模态类型
        
        用于感知记忆，自动识别文件类型。
        
        Args:
            path: 文件路径
            
        Returns:
            str: 模态类型 ("image", "audio", "text")
        """
        try:
            ext = (path.rsplit('.', 1)[-1] or '').lower()
            # 图片格式
            if ext in {"png", "jpg", "jpeg", "bmp", "gif", "webp"}:
                return "image"
            # 音频格式
            if ext in {"mp3", "wav", "flac", "m4a", "ogg"}:
                return "audio"
            # 默认文本
            return "text"
        except Exception:
            return "text"

    @tool_action("memory_search", "搜索相关记忆")
    def _search_memory(
        self,
        query: str,
        limit: int = 5,
        memory_type: str = None,
        min_importance: float = 0.1
    ) -> str:
        """搜索记忆 - 语义检索相关记忆
        
        根据查询内容，从记忆系统中检索相关记忆。
        使用语义相似度匹配，而非简单的关键词匹配。

        Args:
            query: 搜索查询内容（自然语言）
            limit: 返回结果数量限制（默认 5）
            memory_type: 限定搜索的记忆类型，None 表示搜索所有类型
            min_importance: 最低重要性阈值，过滤低于此值的记忆

        Returns:
            str: 格式化的搜索结果列表
            
        Example:
            >>> tool._search_memory("用户喜好", limit=3)
            '🔍 找到 2 条相关记忆:\n1. [工作记忆] 用户喜欢咖啡 (重要性: 0.80)\n...'
        """
        try:
            # 步骤1: 处理 memory_type 参数（转换为列表格式）
            memory_types = [memory_type] if memory_type else None  # None 表示搜索所有类型

            # 步骤2: 调用 MemoryManager 进行语义检索
            results = self.memory_manager.retrieve_memories(
                query=query,
                limit=limit,
                memory_types=memory_types,
                min_importance=min_importance
            )

            if not results:
                return f"未找到与 '{query}' 相关的记忆"

            # 步骤3: 格式化结果为用户友好的字符串
            formatted_results = []
            formatted_results.append(f"找到 {len(results)} 条相关记忆:")

            for i, memory in enumerate(results, 1):
                # 将英文类型名转换为中文标签
                memory_type_label = {
                    "working": "工作记忆",
                    "episodic": "情景记忆",
                    "semantic": "语义记忆",
                    "perceptual": "感知记忆"
                }.get(memory.memory_type, memory.memory_type)

                # 截断过长的内容（保留前80个字符）
                content_preview = memory.content[:80] + "..." if len(memory.content) > 80 else memory.content
                formatted_results.append(
                    f"{i}. [{memory_type_label}] {content_preview} (重要性: {memory.importance:.2f})"
                )

            return "\n".join(formatted_results)

        except Exception as e:
            return f"搜索记忆失败: {str(e)}"

    @tool_action("memory_summary", "获取记忆系统摘要（包含重要记忆和统计信息）")
    def _get_summary(self, limit: int = 10) -> str:
        """获取记忆摘要 - 记忆系统的整体概览
        
        返回记忆系统的统计信息和重要记忆列表。
        适合用于了解当前记忆状态。

        Args:
            limit: 显示的重要记忆数量（默认 10）

        Returns:
            str: 格式化的摘要信息，包含：
                - 总记忆数
                - 当前会话信息
                - 各类型记忆分布
                - 重要记忆列表
        """
        try:
            stats = self.memory_manager.get_memory_stats()

            summary_parts = [
                f"记忆系统摘要",
                f"总记忆数: {stats['total_memories']}",
                f"当前会话: {self.current_session_id or '未开始'}",
                f"对话轮次: {self.conversation_count}"
            ]

            # 各类型记忆统计
            if stats['memories_by_type']:
                summary_parts.append("\n📋 记忆类型分布:")
                for memory_type, type_stats in stats['memories_by_type'].items():
                    count = type_stats.get('count', 0)
                    avg_importance = type_stats.get('avg_importance', 0)
                    type_label = {
                        "working": "工作记忆",
                        "episodic": "情景记忆",
                        "semantic": "语义记忆",
                        "perceptual": "感知记忆"
                    }.get(memory_type, memory_type)

                    summary_parts.append(f"  • {type_label}: {count} 条 (平均重要性: {avg_importance:.2f})")

            # 获取重要记忆 - 修复重复问题
            important_memories = self.memory_manager.retrieve_memories(
                query="",
                memory_types=None,  # 从所有类型中检索
                limit=limit * 3,  # 获取更多候选，然后去重
                min_importance=0.5  # 降低阈值以获取更多记忆
            )

            if important_memories:
                # 去重处理：使用记忆ID和内容双重去重（防止重复显示）
                seen_ids = set()  # 已见过的记忆ID
                seen_contents = set()  # 已见过的记忆内容
                unique_memories = []  # 去重后的记忆列表
                
                for memory in important_memories:
                    # 使用ID去重
                    if memory.id in seen_ids:
                        continue
                    
                    # 使用内容去重（防止相同内容的不同记忆）
                    content_key = memory.content.strip().lower()
                    if content_key in seen_contents:
                        continue
                    
                    seen_ids.add(memory.id)
                    seen_contents.add(content_key)
                    unique_memories.append(memory)
                
                # 按重要性排序
                unique_memories.sort(key=lambda x: x.importance, reverse=True)
                summary_parts.append(f"\n重要记忆 (前{min(limit, len(unique_memories))}条):")

                for i, memory in enumerate(unique_memories[:limit], 1):
                    content_preview = memory.content[:60] + "..." if len(memory.content) > 60 else memory.content
                    summary_parts.append(f"  {i}. {content_preview} (重要性: {memory.importance:.2f})")

            return "\n".join(summary_parts)

        except Exception as e:
            return f"获取摘要失败: {str(e)}"

    @tool_action("memory_stats", "获取记忆系统的统计信息")
    def _get_stats(self) -> str:
        """获取统计信息 - 简洁的系统状态
        
        返回记忆系统的基本统计信息。
        比 summary 更简洁，适合快速查看状态。

        Returns:
            str: 格式化的统计信息
        """
        try:
            stats = self.memory_manager.get_memory_stats()

            stats_info = [
                f"记忆系统统计",
                f"总记忆数: {stats['total_memories']}",
                f"启用的记忆类型: {', '.join(stats['enabled_types'])}",
                f"会话ID: {self.current_session_id or '未开始'}",
                f"对话轮次: {self.conversation_count}"
            ]

            return "\n".join(stats_info)

        except Exception as e:
            return f"获取统计信息失败: {str(e)}"

    # ========== 便捷方法 ==========
    # 以下方法供 Agent 内部调用，简化常见操作
    
    def auto_record_conversation(self, user_input: str, agent_response: str):
        """自动记录对话 - Agent 的对话历史记录
        
        这个方法可以被 Agent 调用来自动记录每轮对话。
        会同时记录用户输入和 Agent 响应，并根据内容重要性
        决定是否同时存入情景记忆。
        
        记录策略：
        1. 用户输入 → 工作记忆（importance=0.6）
        2. Agent 响应 → 工作记忆（importance=0.7）
        3. 重要对话 → 情景记忆（importance=0.8）
           - 响应长度 > 100
           - 用户说"重要"或"记住"
        
        Args:
            user_input: 用户输入内容
            agent_response: Agent 响应内容
        """
        self.conversation_count += 1
        
        # 步骤1: 记录用户输入到工作记忆（短期）
        self._add_memory(
            content=f"用户: {user_input}",
            memory_type="working",
            importance=0.6,  # 用户输入的重要性稍低
            type="user_input",
            conversation_id=self.conversation_count
        )

        # 步骤2: 记录 Agent 响应到工作记忆（短期）
        self._add_memory(
            content=f"助手: {agent_response}",
            memory_type="working",
            importance=0.7,  # Agent 响应的重要性稍高
            type="agent_response",
            conversation_id=self.conversation_count
        )

        # 步骤3: 判断是否为重要对话，如果是则额外存入情景记忆（长期）
        # 重要对话的判断标准：响应长度>100 或 用户提到"重要"/"记住"
        if len(agent_response) > 100 or "重要" in user_input or "记住" in user_input:
            interaction_content = f"对话 - 用户: {user_input}\n助手: {agent_response}"
            self._add_memory(
                content=interaction_content,
                memory_type="episodic",
                importance=0.8,
                type="interaction",
                conversation_id=self.conversation_count
            )

    @tool_action("memory_update", "更新已存在的记忆")
    def _update_memory(self, memory_id: str, content: str = None, importance: float = None) -> str:
        """更新记忆

        Args:
            memory_id: 要更新的记忆ID
            content: 新的记忆内容
            importance: 新的重要性分数

        Returns:
            执行结果
        """
        try:
            metadata = {}
            success = self.memory_manager.update_memory(
                memory_id=memory_id,
                content=content,
                importance=importance,
                metadata=metadata or None
            )
            return "记忆已更新" if success else "未找到要更新的记忆"
        except Exception as e:
            return f"更新记忆失败: {str(e)}"

    @tool_action("memory_remove", "删除指定的记忆")
    def _remove_memory(self, memory_id: str) -> str:
        """删除记忆

        Args:
            memory_id: 要删除的记忆ID

        Returns:
            执行结果
        """
        try:
            success = self.memory_manager.remove_memory(memory_id)
            return "记忆已删除" if success else "未找到要删除的记忆"
        except Exception as e:
            return f"删除记忆失败: {str(e)}"

    @tool_action("memory_forget", "按照策略批量遗忘记忆")
    def _forget(self, strategy: str = "importance_based", threshold: float = 0.1, max_age_days: int = 30) -> str:
        """遗忘记忆（支持多种策略）

        Args:
            strategy: 遗忘策略：importance_based(基于重要性)/time_based(基于时间)/capacity_based(基于容量)
            threshold: 遗忘阈值（importance_based时使用）
            max_age_days: 最大保留天数（time_based时使用）

        Returns:
            执行结果
        """
        try:
            count = self.memory_manager.forget_memories(
                strategy=strategy,
                threshold=threshold,
                max_age_days=max_age_days
            )
            return f"已遗忘 {count} 条记忆（策略: {strategy}）"
        except Exception as e:
            return f"遗忘记忆失败: {str(e)}"

    @tool_action("memory_consolidate", "将重要的短期记忆整合为长期记忆")
    def _consolidate(self, from_type: str = "working", to_type: str = "episodic", importance_threshold: float = 0.7) -> str:
        """整合记忆（将重要的短期记忆提升为长期记忆）

        Args:
            from_type: 来源记忆类型
            to_type: 目标记忆类型
            importance_threshold: 整合的重要性阈值

        Returns:
            执行结果
        """
        try:
            count = self.memory_manager.consolidate_memories(
                from_type=from_type,
                to_type=to_type,
                importance_threshold=importance_threshold,
            )
            return f"已整合 {count} 条记忆为长期记忆（{from_type} → {to_type}，阈值={importance_threshold}）"
        except Exception as e:
            return f"整合记忆失败: {str(e)}"

    @tool_action("memory_clear", "清空所有记忆（危险操作，请谨慎使用）")
    def _clear_all(self) -> str:
        """清空所有记忆

        Returns:
            执行结果
        """
        try:
            self.memory_manager.clear_all_memories()
            return "已清空所有记忆"
        except Exception as e:
            return f"清空记忆失败: {str(e)}"

    def add_knowledge(self, content: str, importance: float = 0.9):
        """添加知识到语义记忆 - 便捷方法
        
        快速将知识性内容添加到语义记忆中。
        默认使用较高的重要性分数（0.9）。
        
        Args:
            content: 知识内容
            importance: 重要性分数（默认 0.9）
            
        Returns:
            str: 执行结果
        """
        return self._add_memory(
            content=content,
            memory_type="semantic",
            importance=importance,
            knowledge_type="factual",
            source="manual"
        )

    def get_context_for_query(self, query: str, limit: int = 3) -> str:
        """为查询获取相关上下文 - Agent 的上下文增强
        
        这个方法可以被 Agent 调用来获取相关的记忆上下文，
        用于增强 LLM 的回答质量。
        
        典型使用场景：
        1. Agent 收到用户问题
        2. 调用此方法获取相关记忆
        3. 将记忆作为上下文添加到 prompt
        4. 发送给 LLM 生成回答
        
        Args:
            query: 用户查询内容
            limit: 返回的记忆数量（默认 3）
            
        Returns:
            str: 格式化的上下文字符串，如果没有相关记忆则返回空字符串
        """
        results = self.memory_manager.retrieve_memories(
            query=query,
            limit=limit,
            min_importance=0.3
        )

        if not results:
            return ""

        context_parts = ["相关记忆:"]
        for memory in results:
            context_parts.append(f"- {memory.content}")

        return "\n".join(context_parts)

    def clear_session(self):
        """清除当前会话 - 会话结束时调用
        
        重置会话状态并清空工作记忆。
        通常在对话结束或用户切换时调用。
        """
        self.current_session_id = None
        self.conversation_count = 0

        # 清理工作记忆（短期记忆），保留长期记忆（情景/语义）
        wm = self.memory_manager.memory_types.get('working') if hasattr(self.memory_manager, 'memory_types') else None
        if wm:
            wm.clear()  # 清空工作记忆中的所有内容

    def consolidate_memories(self):
        """整合记忆 - 便捷方法
        
        将重要的工作记忆整合到情景记忆中。
        建议在会话结束时调用。
        
        Returns:
            int: 整合的记忆数量
        """
        return self.memory_manager.consolidate_memories()

    def forget_old_memories(self, max_age_days: int = 30):
        """遗忘旧记忆 - 便捷方法
        
        清理超过指定天数的旧记忆。
        建议定期调用以保持记忆系统健康。
        
        Args:
            max_age_days: 最大保留天数（默认 30）
            
        Returns:
            int: 遗忘的记忆数量
        """
        return self.memory_manager.forget_memories(
            strategy="time_based",
            max_age_days=max_age_days
        )

