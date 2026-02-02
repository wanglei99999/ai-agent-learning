"""ContextBuilder - GSSC流水线实现（上下文工程的核心引擎）

你在学习 `hello-agent` 架构时，可以把这个模块理解为：
- 上层 Agent 负责"任务规划 + 工具调用"
- 本模块负责"上下文构建"：把分散的信息源整合成结构化 prompt

核心数据流（建议先记住这 4 条）：
1) Gather:   多源信息 → ContextPacket[] （广撒网，从 Memory/RAG/History 收集）
2) Select:   ContextPacket[] → 筛选 + 评分 → 高价值子集 （精挑细选，控制预算）
3) Structure: 高价值子集 → 分区模板 → 结构化文本 （6区模板：Role/Task/State/Evidence/Context/Output）
4) Compress: 结构化文本 → 预算守护 → 最终 prompt （超预算则截断）

对外入口：ContextBuilder.build() 返回结构化上下文字符串：
- user_query: 用户问题（必需）
- conversation_history: 对话历史（可选）
- system_instructions: 系统指令（可选）
- additional_packets: 自定义信息包（可选）

关于预算管理：
- ContextConfig.max_tokens 控制总预算（默认 8000）
- reserve_ratio=0.15 为模型输出预留 15% 空间
- Select 阶段按 token 数贪心填充，Compress 阶段双重保险
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import tiktoken
import math

from ..core.message import Message
from ..tools import MemoryTool, RAGTool


# ============================================================================
# 数据结构定义：上下文信息的基本单元
# ============================================================================

@dataclass
class ContextPacket:
    """上下文信息包 - 封装单条上下文信息的容器
    
    设计理念：
    - 每个信息片段都是独立的"包"，带有元数据和评分
    - 便于在 Select 阶段进行筛选和排序
    - 自动计算 token 数，方便预算管理
    
    阅读提示：这是最小的信息单元，类似"积木块"
    """
    content: str  # 实际内容
    timestamp: datetime = field(default_factory=datetime.now)  # 时间戳（用于新近性计算）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据（如类型、重要性）
    token_count: int = 0  # token 数量（自动计算）
    relevance_score: float = 0.0  # 相关性分数（0.0-1.0，在 Select 阶段计算）
    
    def __post_init__(self):
        """自动计算token数 - 创建对象后立即执行"""
        if self.token_count == 0:
            self.token_count = count_tokens(self.content)


@dataclass
class ContextConfig:
    """上下文构建配置 - 控制 GSSC 流水线的行为参数
    
    设计理念：
    - 集中管理所有可调参数，便于实验和优化
    - 预算管理：max_tokens 和 reserve_ratio 控制上下文大小
    - 质量控制：min_relevance 过滤低质量信息
    - 多样性控制：enable_mmr 和 mmr_lambda 平衡相关性与多样性
    
    阅读提示：这是"控制面板"，调整这些参数可以改变上下文构建策略
    """
    max_tokens: int = 8000  # 总预算（上下文窗口大小）
    reserve_ratio: float = 0.15  # 生成余量（10-20%），为模型输出预留空间
    min_relevance: float = 0.3  # 最小相关性阈值（低于此值的信息会被过滤）
    enable_mmr: bool = True  # 启用最大边际相关性（多样性）- 当前未实现
    mmr_lambda: float = 0.7  # MMR平衡参数（0=纯多样性, 1=纯相关性）- 当前未实现
    system_prompt_template: str = ""  # 系统提示模板（预留）
    enable_compression: bool = True  # 启用压缩（超预算时截断）
    
    def get_available_tokens(self) -> int:
        """获取可用token预算（扣除余量）
        
        例如：max_tokens=8000, reserve_ratio=0.15
        可用预算 = 8000 * (1 - 0.15) = 6800 tokens
        剩余 1200 tokens 留给模型生成输出
        """
        return int(self.max_tokens * (1 - self.reserve_ratio))


# ============================================================================
# 核心类：ContextBuilder - GSSC 流水线的实现
# ============================================================================

class ContextBuilder:
    """上下文构建器 - GSSC流水线
    
    设计理念：
    - 实现 Gather-Select-Structure-Compress 四阶段流水线
    - 统一接口：build() 方法封装整个流程
    - 可扩展：通过 memory_tool 和 rag_tool 接入不同数据源
    - 可配置：通过 ContextConfig 调整行为
    
    核心流程：
    1. Gather  → 从多源收集候选信息（_gather）
    2. Select  → 基于评分筛选和排序（_select）
    3. Structure → 组织成结构化模板（_structure）
    4. Compress → 压缩到预算内（_compress）
    
    用法示例：
    ```python
    builder = ContextBuilder(
        memory_tool=memory_tool,  # 可选：长期记忆
        rag_tool=rag_tool,        # 可选：知识库检索
        config=ContextConfig(max_tokens=8000)
    )
    
    context = builder.build(
        user_query="用户问题",
        conversation_history=[...],
        system_instructions="系统指令"
    )
    ```
    
    阅读提示：
    - 先看 build() 方法了解整体流程
    - 再依次看 _gather → _select → _structure → _compress
    """
    
    def __init__(
        self,
        memory_tool: Optional[MemoryTool] = None,
        rag_tool: Optional[RAGTool] = None,
        config: Optional[ContextConfig] = None
    ):
        self.memory_tool = memory_tool  # 长期记忆工具（用于检索任务状态、历史结论）
        self.rag_tool = rag_tool  # RAG工具（用于检索知识库）
        self.config = config or ContextConfig()  # 配置参数
        self._encoding = tiktoken.get_encoding("cl100k_base")  # token计数器
    
    # ========================================================================
    # 主入口：build() - GSSC 流水线的编排者
    # ========================================================================
    
    def build(
        self,
        user_query: str,
        conversation_history: Optional[List[Message]] = None,
        system_instructions: Optional[str] = None,
        additional_packets: Optional[List[ContextPacket]] = None
    ) -> str:
        """构建完整上下文 - GSSC 流水线的主入口
        
        这是唯一的公开方法，内部调用四个私有方法完成流水线。
        
        Args:
            user_query: 用户查询（必需）
            conversation_history: 对话历史（可选）
            system_instructions: 系统指令（可选）
            additional_packets: 额外的上下文包（可选，用于注入自定义信息）
            
        Returns:
            结构化上下文字符串（可直接作为 LLM 的 prompt）
            
        阅读提示：
        这是"总指挥"，按顺序调用四个阶段，每个阶段的输出是下一阶段的输入
        """
        # 1. Gather: 收集候选信息（从记忆、RAG、历史等多源收集）
        packets = self._gather(
            user_query=user_query,
            conversation_history=conversation_history or [],
            system_instructions=system_instructions,
            additional_packets=additional_packets or []
        )
        
        # 2. Select: 筛选与排序（基于相关性、新近性、预算）
        selected_packets = self._select(packets, user_query)
        
        # 3. Structure: 组织成结构化模板（分区模板：Role/Task/State/Evidence/Context/Output）
        structured_context = self._structure(
            selected_packets=selected_packets,
            user_query=user_query,
            system_instructions=system_instructions
        )
        
        # 4. Compress: 压缩与规范化（如果超预算则截断）
        final_context = self._compress(structured_context)
        
        return final_context
    
    # ========================================================================
    # 阶段1: Gather - 从多源收集候选信息
    # ========================================================================
    
    def _gather(
        self,
        user_query: str,
        conversation_history: List[Message],
        system_instructions: Optional[str],
        additional_packets: List[ContextPacket]
    ) -> List[ContextPacket]:
        """Gather: 收集候选信息 - 广撒网，先不考虑预算
        
        设计理念：
        - 从多个数据源收集所有可能相关的信息
        - 不做过滤，只做收集（过滤在 Select 阶段）
        - 每个信息源对应一个优先级（P0-P3）
        
        信息源优先级：
        - P0: 系统指令（强约束，必须保留）
        - P1: 记忆（任务状态、关键结论）
        - P2: RAG（事实证据、知识库）
        - P3: 对话历史（辅助材料）
        
        阅读提示：
        这是"采购员"，负责从各个渠道收集原材料（信息包）
        """
        packets = []
        
        # P0: 系统指令（强约束）
        if system_instructions:
            packets.append(ContextPacket(
                content=system_instructions,
                metadata={"type": "instructions"}
            ))
        
        # P1: 从记忆中获取任务状态与关键结论
        if self.memory_tool:
            try:
                # 搜索任务状态相关记忆
                state_results = self.memory_tool.execute(
                    "search",
                    query="(任务状态 OR 子目标 OR 结论 OR 阻塞)",
                    min_importance=0.7,
                    limit=5
                )
                if state_results and "未找到" not in state_results:
                    packets.append(ContextPacket(
                        content=state_results,
                        metadata={"type": "task_state", "importance": "high"}
                    ))
                
                # 搜索与当前查询相关的记忆
                related_results = self.memory_tool.execute(
                    "search",
                    query=user_query,
                    limit=5
                )
                if related_results and "未找到" not in related_results:
                    packets.append(ContextPacket(
                        content=related_results,
                        metadata={"type": "related_memory"}
                    ))
            except Exception as e:
                print(f"记忆检索失败: {e}")
        
        # P2: 从RAG中获取事实证据
        if self.rag_tool:
            try:
                rag_results = self.rag_tool.run({
                    "action": "search",
                    "query": user_query,
                    "limit": 5
                })
                if rag_results and "未找到" not in rag_results and "错误" not in rag_results:
                    packets.append(ContextPacket(
                        content=rag_results,
                        metadata={"type": "knowledge_base"}
                    ))
            except Exception as e:
                print(f"RAG检索失败: {e}")
        
        # P3: 对话历史（辅助材料）
        if conversation_history:
            # 只保留最近N条
            recent_history = conversation_history[-10:]
            history_text = "\n".join([
                f"[{msg.role}] {msg.content}"
                for msg in recent_history
            ])
            packets.append(ContextPacket(
                content=history_text,
                metadata={"type": "history", "count": len(recent_history)}
            ))
        
        # 添加额外包
        packets.extend(additional_packets)
        
        return packets
    
    # ========================================================================
    # 阶段2: Select - 基于评分筛选和排序
    # ========================================================================
    
    def _select(
        self,
        packets: List[ContextPacket],
        user_query: str
    ) -> List[ContextPacket]:
        """Select: 基于分数与预算的筛选 - 精挑细选，控制预算
        
        设计理念：
        - 计算每个包的复合分数（相关性 + 新近性）
        - 过滤低质量信息（低于 min_relevance）
        - 按预算填充（优先高分，直到预算用完）
        - 系统指令特殊处理（固定纳入，不参与排序）
        
        评分公式：
        - 相关性 = 关键词重叠度（query tokens ∩ content tokens）
        - 新近性 = exp(-Δt / τ)，τ=3600秒（1小时衰减）
        - 复合分 = 0.7 × 相关性 + 0.3 × 新近性
        
        阅读提示：
        这是"质检员"，负责筛选出最有价值的信息包，同时控制总量
        """
        # 1) 计算相关性（关键词重叠）
        query_tokens = set(user_query.lower().split())
        for packet in packets:
            content_tokens = set(packet.content.lower().split())
            if len(query_tokens) > 0:
                overlap = len(query_tokens & content_tokens)
                packet.relevance_score = overlap / len(query_tokens)
            else:
                packet.relevance_score = 0.0
        
        # 2) 计算新近性（指数衰减）
        def recency_score(ts: datetime) -> float:
            delta = max((datetime.now() - ts).total_seconds(), 0)
            tau = 3600  # 1小时时间尺度，可暴露到配置
            return math.exp(-delta / tau)
        
        # 3) 计算复合分：0.7*相关性 + 0.3*新近性
        scored_packets: List[Tuple[float, ContextPacket]] = []
        for p in packets:
            rec = recency_score(p.timestamp)
            score = 0.7 * p.relevance_score + 0.3 * rec
            scored_packets.append((score, p))
        
        # 4) 系统指令单独拿出，固定纳入
        system_packets = [p for (_, p) in scored_packets if p.metadata.get("type") == "instructions"]
        remaining = [p for (s, p) in sorted(scored_packets, key=lambda x: x[0], reverse=True)
                     if p.metadata.get("type") != "instructions"]
        
        # 5) 依据 min_relevance 过滤（对非系统包）
        filtered = [p for p in remaining if p.relevance_score >= self.config.min_relevance]
        
        # 6) 按预算填充
        available_tokens = self.config.get_available_tokens()
        selected: List[ContextPacket] = []
        used_tokens = 0
        
        # 先放入系统指令（不排序）
        for p in system_packets:
            if used_tokens + p.token_count <= available_tokens:
                selected.append(p)
                used_tokens += p.token_count
        
        # 再按分数加入其余
        for p in filtered:
            if used_tokens + p.token_count <= available_tokens:
                selected.append(p)
                used_tokens += p.token_count
        
        return selected
    
    # ========================================================================
    # 阶段3: Structure - 组织成结构化模板
    # ========================================================================
    
    def _structure(
        self,
        selected_packets: List[ContextPacket],
        user_query: str,
        system_instructions: Optional[str]
    ) -> str:
        """Structure: 组织成结构化上下文模板 - 分区组织，清晰呈现
        
        设计理念：
        - 采用固定的分区模板（6个区域）
        - 每个区域有明确的语义（角色、任务、状态、证据、历史、输出）
        - 便于 LLM 快速定位和理解不同类型的信息
        
        模板结构：
        [Role & Policies]  - P0: 系统指令（强约束）
        [Task]             - 当前任务（用户问题）
        [State]            - P1: 任务状态（进展、未决问题）
        [Evidence]         - P2: 事实证据（记忆、RAG、工具结果）
        [Context]          - P3: 辅助材料（对话历史）
        [Output]           - 输出约束（格式要求）
        
        阅读提示：
        这是"编辑"，负责把筛选后的信息包按主题分类排版
        """
        sections = []
        
        # [Role & Policies] - 系统指令
        p0_packets = [p for p in selected_packets if p.metadata.get("type") == "instructions"]
        if p0_packets:
            role_section = "[Role & Policies]\n"
            role_section += "\n".join([p.content for p in p0_packets])
            sections.append(role_section)
        
        # [Task] - 当前任务
        sections.append(f"[Task]\n用户问题：{user_query}")
        
        # [State] - 任务状态
        p1_packets = [p for p in selected_packets if p.metadata.get("type") == "task_state"]
        if p1_packets:
            state_section = "[State]\n关键进展与未决问题：\n"
            state_section += "\n".join([p.content for p in p1_packets])
            sections.append(state_section)
        
        # [Evidence] - 事实证据
        p2_packets = [
            p for p in selected_packets
            if p.metadata.get("type") in {"related_memory", "knowledge_base", "retrieval", "tool_result"}
        ]
        if p2_packets:
            evidence_section = "[Evidence]\n事实与引用：\n"
            for p in p2_packets:
                evidence_section += f"\n{p.content}\n"
            sections.append(evidence_section)
        
        # [Context] - 辅助材料（历史等）
        p3_packets = [p for p in selected_packets if p.metadata.get("type") == "history"]
        if p3_packets:
            context_section = "[Context]\n对话历史与背景：\n"
            context_section += "\n".join([p.content for p in p3_packets])
            sections.append(context_section)
        
        # [Output] - 输出约束
        output_section = """[Output]
                            请按以下格式回答：
                            1. 结论（简洁明确）
                            2. 依据（列出支撑证据及来源）
                            3. 风险与假设（如有）
                            4. 下一步行动建议（如适用）"""
        sections.append(output_section)
        
        return "\n\n".join(sections)
    
    # ========================================================================
    # 阶段4: Compress - 压缩到预算内
    # ========================================================================
    
    def _compress(self, context: str) -> str:
        """Compress: 压缩与规范化 - 最后的守门员
        
        设计理念：
        - 检查是否超预算（理论上 Select 阶段已控制，但这是双保险）
        - 如果超预算，执行截断（按段落保留结构）
        - 实际应用中可用 LLM 做高保真摘要（当前是简单截断）
        
        截断策略：
        - 按行截断（保留完整段落，避免截断到句子中间）
        - 优先保留前面的内容（因为重要信息在前）
        
        阅读提示：
        这是"安检员"，确保最终上下文不超过预算限制
        """
        if not self.config.enable_compression:
            return context
        
        current_tokens = count_tokens(context)
        available_tokens = self.config.get_available_tokens()
        
        if current_tokens <= available_tokens:
            return context
        
        # 简单截断策略（保留前N个token）
        # TODO: 实际应用中可用LLM做高保真摘要（压缩整合策略）
        print(f"上下文超预算 ({current_tokens} > {available_tokens})，执行截断")
        
        # 按段落截断，保留结构
        lines = context.split("\n")
        compressed_lines = []
        used_tokens = 0
        
        for line in lines:
            line_tokens = count_tokens(line)
            if used_tokens + line_tokens > available_tokens:
                break
            compressed_lines.append(line)
            used_tokens += line_tokens
        
        return "\n".join(compressed_lines)


# ============================================================================
# 工具函数：token 计数
# ============================================================================

def count_tokens(text: str) -> int:
    """计算文本token数（使用tiktoken）
    
    设计理念：
    - 使用 OpenAI 的 tiktoken 库精确计算 token 数
    - 降级方案：如果 tiktoken 失败，用粗略估算（1 token ≈ 4 字符）
    
    阅读提示：
    这是"计量器"，用于预算管理的基础工具
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")  # GPT-3.5/4 使用的编码
        return len(encoding.encode(text))
    except Exception:
        # 降级方案：粗略估算（1 token ≈ 4 字符）
        return len(text) // 4

