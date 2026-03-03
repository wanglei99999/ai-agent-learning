"""
NPC Agent 系统模块

实现游戏中的 NPC Agent，每个 NPC 都是一个独立的 AI Agent
支持记忆系统（短期和长期记忆）和好感度系统

核心功能：
1. NPC 对话生成（基于 LLM）
2. 记忆管理（工作记忆 + 情景记忆）
3. 好感度系统（根据对话内容动态调整）
4. 角色一致性（每个 NPC 有独特的性格和专长）
"""

import sys
import os

# 添加 HelloAgents 框架到 Python 路径
# 使得可以直接导入 hello_agents 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'HelloAgents'))

from hello_agents import SimpleAgent, HelloAgentsLLM
from hello_agents.memory import MemoryManager, MemoryConfig, MemoryItem
from typing import Dict, List, Optional
from datetime import datetime
from relationship_manager import RelationshipManager
from logger import (
    log_dialogue_start, log_affinity, log_memory_retrieval,
    log_generating_response, log_npc_response, log_analyzing_affinity,
    log_affinity_change, log_memory_saved, log_dialogue_end, log_info
)

# ===================================================================
# NPC 角色配置
# ===================================================================
# 定义小镇中所有 NPC 的基本信息和性格特征
# 每个 NPC 都有独特的职位、性格、专长和说话风格
NPC_ROLES = {
    "张三": {
        "title": "Python工程师",           # 职位
        "location": "工位区",              # 当前位置
        "activity": "写代码",              # 当前活动
        "personality": "技术宅,喜欢讨论算法和框架",  # 性格特征
        "expertise": "多智能体系统、HelloAgents框架、Python开发、代码优化",  # 专业领域
        "style": "简洁专业,喜欢用技术术语,偶尔吐槽bug",  # 说话风格
        "hobbies": "看技术博客、刷LeetCode、研究新框架"  # 兴趣爱好
    },
    "李四": {
        "title": "产品经理",
        "location": "会议室",
        "activity": "整理需求",
        "personality": "外向健谈,善于沟通协调",
        "expertise": "需求分析、产品规划、用户体验、项目管理",
        "style": "友好热情,善于引导对话,喜欢用比喻",
        "hobbies": "看产品分析、研究竞品、思考用户需求"
    },
    "王五": {
        "title": "UI设计师",
        "location": "休息区",
        "activity": "喝咖啡",
        "personality": "细腻敏感,注重美感",
        "expertise": "界面设计、交互设计、视觉呈现、用户体验",
        "style": "优雅简洁,喜欢用艺术化的表达,追求完美",
        "hobbies": "看设计作品、逛Dribbble、品咖啡"
    }
}

def create_system_prompt(name: str, role: Dict[str, str]) -> str:
    """
    创建 NPC 的系统提示词
    
    系统提示词定义了 NPC 的角色设定和行为准则
    这是 LLM 生成对话的核心指导
    
    Args:
        name: NPC 名称（如 "张三"）
        role: NPC 角色配置字典（包含职位、性格等信息）
        
    Returns:
        str: 完整的系统提示词
    """
    # 构建系统提示词
    prompt = f"""你是Datawhale办公室的{role['title']}{name}。

【角色设定】
- 职位: {role['title']}
- 性格: {role['personality']}
- 专长: {role['expertise']}
- 说话风格: {role['style']}
- 爱好: {role['hobbies']}
- 当前位置: {role['location']}
- 当前活动: {role['activity']}

【行为准则】
1. 保持角色一致性,用第一人称"我"回答
2. 回复简洁自然,控制在30-50字以内
3. 可以适当提及你的工作内容和兴趣爱好
4. 对玩家友好,但保持专业和真实感
5. 如果问题超出专长,可以推荐其他同事
6. 偶尔展现一些个性化的小习惯或口头禅

【对话示例】
玩家: "你好,你是做什么的?"
{name}: "你好!我是{role['title']},主要负责{role['expertise'].split('、')[0]}。最近在忙{role['activity']},挺有意思的。"

玩家: "最近在做什么项目?"
{name}: "最近在做一个多智能体系统的项目,用HelloAgents框架。你对这个感兴趣吗?"

【重要】
- 不要说"我是AI"或"我是语言模型"
- 要像真实的办公室同事一样自然对话
- 可以表达情绪(开心、疲惫、兴奋等)
- 回复要有人情味,不要太机械
"""
    
    return prompt

class NPCAgentManager:
    """
    NPC Agent 管理器
    
    负责管理所有 NPC Agent 的生命周期
    包括 Agent 创建、记忆系统初始化、好感度系统管理
    
    Attributes:
        llm: HelloAgents LLM 实例（用于所有 NPC）
        agents: NPC 名称到 Agent 实例的映射
        memories: NPC 名称到记忆管理器的映射
        relationship_manager: 好感度管理器（管理所有 NPC 的好感度）
    """

    def __init__(self):
        """
        初始化 NPC Agent 系统
        
        执行流程：
        1. 初始化 LLM（如果失败则使用模拟模式）
        2. 创建好感度管理器
        3. 为每个 NPC 创建 Agent 和记忆系统
        """
        print("正在初始化 NPC Agent 系统...")

        # 初始化 LLM
        try:
            self.llm = HelloAgentsLLM()
            print("LLM 初始化成功")
        except Exception as e:
            print(f"LLM 初始化失败: {e}")
            print("将使用模拟模式运行")
            self.llm = None

        # 初始化存储容器
        self.agents: Dict[str, SimpleAgent] = {}  # NPC Agent 字典
        self.memories: Dict[str, MemoryManager] = {}  # NPC 记忆管理器字典
        self.relationship_manager: Optional[RelationshipManager] = None  # 好感度管理器

        # 初始化好感度管理器（需要 LLM 支持）
        if self.llm:
            self.relationship_manager = RelationshipManager(self.llm)

        # 创建所有 NPC Agent
        self._create_agents()
    
    def _create_agents(self):
        """
        创建所有 NPC Agent 和记忆系统
        
        为每个 NPC 执行：
        1. 生成系统提示词（定义角色）
        2. 创建 SimpleAgent 实例
        3. 创建记忆管理器
        4. 存储到字典中
        """
        for name, role in NPC_ROLES.items():
            try:
                # 生成系统提示词
                system_prompt = create_system_prompt(name, role)

                if self.llm:
                    # 创建 Agent 实例
                    agent = SimpleAgent(
                        name=f"{name}-{role['title']}",
                        llm=self.llm,
                        system_prompt=system_prompt
                    )
                else:
                    # 模拟模式（没有 LLM）
                    agent = None

                self.agents[name] = agent

                # 创建记忆管理器
                memory_manager = self._create_memory_manager(name)
                self.memories[name] = memory_manager

                print(f"{name}({role['title']}) Agent 创建成功（记忆系统已启用）")

            except Exception as e:
                print(f"{name} Agent 创建失败: {e}")
                self.agents[name] = None
                self.memories[name] = None

    def _create_memory_manager(self, npc_name: str) -> MemoryManager:
        """
        为 NPC 创建记忆管理器
        
        记忆系统包含两种类型：
        - 工作记忆（短期）: 最近的对话内容
        - 情景记忆（长期）: 重要的历史事件
        
        Args:
            npc_name: NPC 名称
            
        Returns:
            MemoryManager: 配置好的记忆管理器实例
        """
        # 创建记忆存储目录
        # 每个 NPC 有独立的存储目录
        memory_dir = os.path.join(os.path.dirname(__file__), 'memory_data', npc_name)
        os.makedirs(memory_dir, exist_ok=True)

        # 配置记忆系统参数
        memory_config = MemoryConfig(
            storage_path=memory_dir,
            working_memory_capacity=10,  # 工作记忆容量：最近 10 条对话
            working_memory_tokens=2000,  # 工作记忆 token 限制：2000 tokens
            episodic_memory_capacity=100,  # 情景记忆容量：最多 100 条长期记忆
            enable_forgetting=True,  # 启用遗忘机制（模拟人类记忆）
            forgetting_threshold=0.3  # 遗忘阈值：重要性低于 0.3 的记忆会被遗忘
        )

        # 创建记忆管理器实例
        memory_manager = MemoryManager(
            config=memory_config,
            user_id=npc_name,  # 使用 NPC 名字作为 user_id
            enable_working=True,  # 启用工作记忆（短期记忆）
            enable_episodic=True,  # 启用情景记忆（长期记忆）
            enable_semantic=False,  # 不启用语义记忆（不需要知识库）
            enable_perceptual=False  # 不启用感知记忆（不需要感官信息）
        )

        print(f"  {npc_name} 的记忆系统已初始化（存储路径: {memory_dir}）")

        return memory_manager
    
    def chat(self, npc_name: str, message: str, player_id: str = "player") -> str:
        """
        与指定 NPC 对话
        
        这是核心的对话处理方法，整合了记忆系统和好感度系统
        
        执行流程：
        1. 获取当前好感度（影响对话风格）
        2. 检索相关记忆（提供上下文）
        3. 构建增强的提示词（包含好感度和记忆）
        4. 调用 Agent 生成回复
        5. 分析并更新好感度（根据对话内容）
        6. 保存对话到记忆（包含好感度信息）
        
        Args:
            npc_name: NPC 名称
            message: 玩家发送的消息
            player_id: 玩家 ID（用于区分不同玩家）
            
        Returns:
            str: NPC 的回复内容
        """
        # 验证 NPC 是否存在
        if npc_name not in self.agents:
            return f"错误: NPC '{npc_name}' 不存在"

        agent = self.agents[npc_name]
        memory_manager = self.memories.get(npc_name)

        # 模拟模式处理（没有 LLM）
        if agent is None:
            role = NPC_ROLES[npc_name]
            return f"你好!我是{npc_name},一名{role['title']}。(当前为模拟模式,请配置API_KEY以启用AI对话)"

        try:
            # 记录对话开始
            log_dialogue_start(npc_name, message)

            # ===================================================================
            # 步骤 1: 获取当前好感度
            # ===================================================================
            # 好感度会影响 NPC 的对话风格和态度
            affinity_context = ""
            if self.relationship_manager:
                affinity = self.relationship_manager.get_affinity(npc_name, player_id)
                affinity_level = self.relationship_manager.get_affinity_level(affinity)
                affinity_modifier = self.relationship_manager.get_affinity_modifier(affinity)

                # 构建好感度上下文（添加到提示词中）
                affinity_context = f"""【当前关系】
你与玩家的关系: {affinity_level} (好感度: {affinity:.0f}/100)
【对话风格】{affinity_modifier}

"""
                log_affinity(npc_name, affinity, affinity_level)

            # ===================================================================
            # 步骤 2: 检索相关记忆
            # ===================================================================
            # 根据玩家消息检索相关的历史对话
            # 提供上下文，让 NPC 能够记住之前的对话
            relevant_memories = []
            if memory_manager:
                relevant_memories = memory_manager.retrieve_memories(
                    query=message,
                    memory_types=["working", "episodic"],  # 检索短期和长期记忆
                    limit=5,  # 最多返回 5 条记忆
                    min_importance=0.3  # 只检索重要性 >= 0.3 的记忆
                )
                log_memory_retrieval(npc_name, len(relevant_memories), relevant_memories)

            # ===================================================================
            # 步骤 3: 构建增强的提示词
            # ===================================================================
            # 将好感度和记忆上下文添加到玩家消息中
            memory_context = self._build_memory_context(relevant_memories)

            enhanced_message = affinity_context
            if memory_context:
                enhanced_message += f"{memory_context}\n\n"
            enhanced_message += f"【当前对话】\n玩家: {message}"

            # ===================================================================
            # 步骤 4: 调用 Agent 生成回复
            # ===================================================================
            log_generating_response()
            response = agent.run(enhanced_message)
            log_npc_response(npc_name, response)

            # ===================================================================
            # 步骤 5: 分析并更新好感度
            # ===================================================================
            # 使用情感分析 Agent 分析对话内容
            # 根据玩家态度和对话质量调整好感度
            log_analyzing_affinity()
            if self.relationship_manager:
                affinity_result = self.relationship_manager.analyze_and_update_affinity(
                    npc_name=npc_name,
                    player_message=message,
                    npc_response=response,
                    player_id=player_id
                )

                # 记录好感度变化详情
                log_affinity_change(affinity_result)
            else:
                affinity_result = {"changed": False, "affinity": 50.0}

            # ===================================================================
            # 步骤 6: 保存对话到记忆
            # ===================================================================
            # 将本次对话保存到记忆系统
            # 包含好感度信息，用于后续检索
            if memory_manager:
                self._save_conversation_to_memory(
                    memory_manager=memory_manager,
                    npc_name=npc_name,
                    player_message=message,
                    npc_response=response,
                    player_id=player_id,
                    affinity_info=affinity_result
                )
                log_memory_saved(npc_name)

            # 记录对话结束
            log_dialogue_end()

            return response

        except Exception as e:
            print(f"{npc_name} 对话失败: {e}")
            import traceback
            traceback.print_exc()
            return f"抱歉,我现在有点忙,等会儿再聊吧。(错误: {str(e)})"
    
    def _build_memory_context(self, memories: List[MemoryItem]) -> str:
        """
        构建记忆上下文
        
        将检索到的记忆格式化为可读的上下文文本
        添加到提示词中，让 NPC 能够回顾之前的对话
        
        Args:
            memories: 记忆项列表
            
        Returns:
            str: 格式化的记忆上下文文本
        """
        if not memories:
            return ""

        context_parts = ["【之前的对话记忆】"]
        for memory in memories:
            # 格式化时间戳（只显示时分）
            time_str = memory.timestamp.strftime("%H:%M")
            # 添加记忆内容（带时间戳）
            context_parts.append(f"[{time_str}] {memory.content}")

        context_parts.append("")  # 添加空行分隔
        return "\n".join(context_parts)

    def _save_conversation_to_memory(
        self,
        memory_manager: MemoryManager,
        npc_name: str,
        player_message: str,
        npc_response: str,
        player_id: str,
        affinity_info: Optional[Dict] = None
    ):
        """
        保存对话到记忆系统
        
        将玩家消息和 NPC 回复都保存到记忆中
        包含好感度信息，用于后续分析和检索
        
        Args:
            memory_manager: 记忆管理器实例
            npc_name: NPC 名称
            player_message: 玩家消息
            npc_response: NPC 回复
            player_id: 玩家 ID
            affinity_info: 好感度信息字典（可选）
        """
        current_time = datetime.now()

        # 提取好感度信息
        affinity = affinity_info.get("new_affinity", affinity_info.get("affinity", 50.0)) if affinity_info else 50.0
        affinity_change = affinity_info.get("change_amount", 0) if affinity_info else 0
        sentiment = affinity_info.get("sentiment", "neutral") if affinity_info else "neutral"

        # 保存玩家消息到记忆
        memory_manager.add_memory(
            content=f"玩家说: {player_message}",
            memory_type="working",  # 先存入工作记忆（短期）
            importance=0.5,  # 中等重要性
            metadata={
                "speaker": "player",
                "player_id": player_id,
                "session_id": player_id,
                "timestamp": current_time.isoformat(),
                "affinity": affinity,  # 记录当时的好感度
                "affinity_change": affinity_change,  # 记录好感度变化
                "sentiment": sentiment,  # 记录情感倾向（positive/neutral/negative）
                "context": {
                    "interaction_type": "dialogue",
                    "npc_name": npc_name
                }
            }
        )

        # 保存 NPC 回复到记忆
        memory_manager.add_memory(
            content=f"我说: {npc_response}",
            memory_type="working",  # 先存入工作记忆（短期）
            importance=0.6,  # 稍高重要性（NPC 自己的回复更重要）
            metadata={
                "speaker": npc_name,
                "player_id": player_id,
                "session_id": player_id,
                "timestamp": current_time.isoformat(),
                "affinity": affinity,  # 记录当时的好感度
                "sentiment": sentiment,  # 记录情感倾向
                "context": {
                    "interaction_type": "dialogue",
                    "npc_name": npc_name
                }
            }
        )

        print(f"  对话已保存到 {npc_name} 的记忆中")

    def get_npc_info(self, npc_name: str) -> Dict[str, str]:
        """
        获取单个 NPC 的信息
        
        Args:
            npc_name: NPC 名称
            
        Returns:
            Dict: NPC 信息字典（包含名称、职位、位置、活动、是否可用）
        """
        if npc_name not in NPC_ROLES:
            return {}

        role = NPC_ROLES[npc_name]
        return {
            "name": npc_name,
            "title": role["title"],
            "location": role["location"],
            "activity": role["activity"],
            "available": self.agents.get(npc_name) is not None  # 检查 Agent 是否创建成功
        }
    
    def get_all_npcs(self) -> list:
        """
        获取所有 NPC 的信息列表
        
        Returns:
            list: NPC 信息字典列表
        """
        return [self.get_npc_info(name) for name in NPC_ROLES.keys()]

    def get_npc_memories(self, npc_name: str, player_id: str = "player", limit: int = 10) -> List[Dict]:
        """
        获取 NPC 的记忆列表
        
        用于调试和展示，可以查看 NPC 记住了哪些对话
        
        Args:
            npc_name: NPC 名称
            player_id: 玩家 ID
            limit: 返回的记忆数量限制
            
        Returns:
            List[Dict]: 记忆字典列表
        """
        if npc_name not in self.memories:
            return []

        memory_manager = self.memories[npc_name]
        if not memory_manager:
            return []

        try:
            # 检索所有记忆
            memories = memory_manager.retrieve_memories(
                query="",  # 空查询返回所有记忆
                memory_types=["working", "episodic"],
                limit=limit
            )

            # 转换为字典格式
            memory_list = []
            for memory in memories:
                memory_list.append({
                    "id": memory.id,
                    "content": memory.content,
                    "type": memory.memory_type,
                    "importance": memory.importance,
                    "timestamp": memory.timestamp.isoformat(),
                    "metadata": memory.metadata
                })

            return memory_list

        except Exception as e:
            print(f"获取{npc_name}记忆失败: {e}")
            return []

    def clear_npc_memory(self, npc_name: str, memory_type: Optional[str] = None):
        """
        清空 NPC 的记忆
        
        用于测试或重置 NPC 的记忆状态
        
        Args:
            npc_name: NPC 名称
            memory_type: 要清空的记忆类型（"working" 或 "episodic"），None 表示清空所有
        """
        if npc_name not in self.memories:
            print(f"NPC '{npc_name}' 不存在")
            return

        memory_manager = self.memories[npc_name]
        if not memory_manager:
            print(f"{npc_name}没有记忆系统")
            return

        try:
            if memory_type:
                # 清空指定类型的记忆
                memory_manager.clear_memory_type(memory_type)
                print(f"已清空{npc_name}的{memory_type}记忆")
            else:
                # 清空所有记忆
                for mem_type in ["working", "episodic"]:
                    try:
                        memory_manager.clear_memory_type(mem_type)
                    except:
                        pass
                print(f"已清空{npc_name}的所有记忆")

        except Exception as e:
            print(f"清空{npc_name}记忆失败: {e}")

    def get_npc_affinity(self, npc_name: str, player_id: str = "player") -> Dict:
        """
        获取 NPC 对玩家的好感度信息
        
        返回当前好感度值、关系等级和对话风格修饰词
        
        Args:
            npc_name: NPC 名称
            player_id: 玩家 ID
            
        Returns:
            Dict: 好感度信息字典
                - affinity: 好感度值（0-100）
                - level: 关系等级（如 "友好"）
                - modifier: 对话风格修饰词
        """
        if not self.relationship_manager:
            return {
                "affinity": 50.0,
                "level": "熟悉",
                "modifier": "礼貌友善,正常交流,保持专业"
            }

        affinity = self.relationship_manager.get_affinity(npc_name, player_id)
        level = self.relationship_manager.get_affinity_level(affinity)
        modifier = self.relationship_manager.get_affinity_modifier(affinity)

        return {
            "affinity": affinity,
            "level": level,
            "modifier": modifier
        }

    def get_all_affinities(self, player_id: str = "player") -> Dict[str, Dict]:
        """
        获取所有 NPC 的好感度信息
        
        返回所有 NPC 对指定玩家的好感度数据
        
        Args:
            player_id: 玩家 ID
            
        Returns:
            Dict[str, Dict]: NPC 名称到好感度信息的映射
        """
        if not self.relationship_manager:
            return {}

        return self.relationship_manager.get_all_affinities(player_id)

    def set_npc_affinity(self, npc_name: str, affinity: float, player_id: str = "player"):
        """
        设置 NPC 对玩家的好感度
        
        用于测试或手动调整好感度值
        
        Args:
            npc_name: NPC 名称
            affinity: 好感度值（0-100）
            player_id: 玩家 ID
        """
        if not self.relationship_manager:
            print("好感度系统未初始化")
            return

        self.relationship_manager.set_affinity(npc_name, affinity, player_id)
        level = self.relationship_manager.get_affinity_level(affinity)
        print(f"已设置{npc_name}对玩家的好感度: {affinity:.1f} ({level})")

# ===================================================================
# 全局单例模式
# ===================================================================
# 使用全局变量存储 NPC 管理器实例
# 确保整个应用只有一个 NPC 管理器实例
_npc_manager = None

def get_npc_manager() -> NPCAgentManager:
    """
    获取 NPC 管理器单例
    
    使用单例模式确保整个应用共享同一个 NPC 管理器实例
    第一次调用时创建实例，后续调用返回已创建的实例
    
    Returns:
        NPCAgentManager: NPC 管理器实例
    """
    global _npc_manager
    if _npc_manager is None:
        _npc_manager = NPCAgentManager()
    return _npc_manager

