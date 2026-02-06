"""
CodebaseMaintainer - 代码库维护助手

完整的长程智能体实现，整合:
1. ContextBuilder - 上下文管理
2. NoteTool - 结构化笔记
3. TerminalTool - 即时文件访问
4. MemoryTool - 对话记忆

关键改进：使用 Agentic 方式，让 agent 自主决定使用哪些工具
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from hello_agents import HelloAgentsLLM
from hello_agents.agents import FunctionCallAgent
from hello_agents.context import ContextBuilder, ContextConfig, ContextPacket
from hello_agents.tools import MemoryTool, NoteTool, TerminalTool
from hello_agents.tools.registry import ToolRegistry
from hello_agents.core.message import Message


class CodebaseMaintainer:
    """代码库维护助手 - 长程智能体示例

    整合 ContextBuilder + NoteTool + TerminalTool + MemoryTool
    实现跨会话的代码库维护任务管理
    
    核心特性：
    - Agent 自主使用工具探索代码库
    - 不预定义工作流，完全基于 agent 决策
    - 跨会话记忆和上下文管理
    """

    def __init__(
        self,
        project_name: str,
        codebase_path: str,
        llm: Optional[HelloAgentsLLM] = None
    ):
        """初始化代码库维护助手
        
        Args:
            project_name: 项目名称，用于标识和组织笔记/记忆
            codebase_path: 代码库路径，TerminalTool 的工作目录
            llm: 大语言模型实例，如果不提供则使用默认配置
        """
        # === 基础配置 ===
        self.project_name = project_name
        self.codebase_path = codebase_path
        # 生成唯一会话ID，用于跟踪和区分不同的维护会话
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # === 初始化 LLM（大语言模型） ===
        self.llm = llm or HelloAgentsLLM()

        # === 初始化三大工具（对应架构图的工具层） ===
        
        # 1. MemoryTool - 持久记忆工具
        #    - 用于存储跨会话的关键信息
        #    - user_id: 以项目名作为用户标识
        #    - memory_types: ["working"] 表示工作记忆（短期记忆）
        self.memory_tool = MemoryTool(
            user_id=project_name,
            memory_types=["working"]
        )
        
        # 2. NoteTool - 结构化笔记工具
        #    - 用于记录任务、问题、结论等结构化信息
        #    - workspace: 笔记存储目录
        self.note_tool = NoteTool(workspace=f"./{project_name}_notes")
        
        # 3. TerminalTool - 即时文件访问工具
        #    - 用于执行 shell 命令（ls, cat, grep, find 等）
        #    - workspace: 命令执行的工作目录
        #    - timeout: 命令执行超时时间（秒）
        self.terminal_tool = TerminalTool(workspace=codebase_path, timeout=60)

        # === 初始化上下文构建器（对应架构图的上下文管理层） ===
        # ContextBuilder 负责实现 GSFC Pipeline:
        # - Gather: 收集信息（记忆、对话历史、笔记）
        # - Select: 筛选相关信息（基于相关性分数）
        # - Structure: 结构化组织（按优先级排序）
        # - Compress: 压缩优化（控制 token 数量）
        self.context_builder = ContextBuilder(
            memory_tool=self.memory_tool,  # 提供记忆检索能力
            rag_tool=None,  # 本案例不使用 RAG（检索增强生成）
            config=ContextConfig(
                max_tokens=4000,           # 上下文最大 token 数（Compress）
                reserve_ratio=0.15,        # 为新内容预留 15% 空间（Structure）
                min_relevance=0.2,         # 最低相关性阈值（Select）
                enable_compression=True    # 启用压缩优化（Compress）
            )
        )

        # === 创建工具注册表并注册所有工具 ===
        # 工具注册表统一管理所有可用工具，Agent 可以从中选择使用
        self.tool_registry = ToolRegistry()
        self.tool_registry.register_tool(self.terminal_tool)  # 注册终端工具
        self.tool_registry.register_tool(self.note_tool)      # 注册笔记工具
        self.tool_registry.register_tool(self.memory_tool)    # 注册记忆工具

        # === 创建 Agent（对应架构图的应用层） ===
        # FunctionCallAgent 是支持函数调用的智能体
        # 核心特性：能够自主决定何时使用哪些工具
        self.agent = FunctionCallAgent(
            name="CodebaseMaintainer",                      # Agent 名称
            llm=self.llm,                                   # 使用的大语言模型
            system_prompt=self._build_base_system_prompt(), # 系统提示词（定义 Agent 能力和行为）
            tool_registry=self.tool_registry,               # 可用工具注册表
            enable_tool_calling=True,                       # 启用工具调用能力
            max_tool_iterations=30                          # 最大工具调用次数（防止无限循环）
        )

        # === 对话历史管理 ===
        # 存储用户和助手的对话记录，用于上下文构建
        self.conversation_history: List[Message] = []

        # === 统计信息 ===
        # 跟踪会话中的各种活动指标
        self.stats = {
            "session_start": datetime.now(),  # 会话开始时间
            "commands_executed": 0,           # 执行的终端命令数
            "notes_created": 0,               # 创建的笔记数
            "issues_found": 0,                # 发现的问题数
            "tool_calls": 0                   # 工具调用总次数
        }

        print(f"[初始化完成] 代码库维护助手已初始化: {project_name} (Agentic Mode)")
        print(f"[工作目录] {codebase_path}")
        print(f"[会话ID] {self.session_id}")
        print(f"[可用工具] {', '.join(self.tool_registry.list_tools())}")

    def run(self, user_input: str, mode: str = "auto") -> str:
        """运行助手（Agentic 方式）
        
        这是核心方法，实现了完整的 Agentic 工作流：
        1. 检索相关笔记（Gather）
        2. 构建优化上下文（GSFC Pipeline）
        3. Agent 自主决策和执行（Agentic）
        4. 统计和记录（Tracking）

        Args:
            user_input: 用户输入的问题或指令
            mode: 运行模式提示（给 agent 提供方向性建议，但不强制）
                - "auto": 自动决策是否使用工具
                - "explore": 建议 agent 侧重代码探索
                - "analyze": 建议 agent 侧重问题分析
                - "plan": 建议 agent 侧重任务规划

        Returns:
            str: 助手的回答
        """
        print(f"\n{'='*80}")
        print(f"[用户] {user_input}")
        print(f"{'='*80}\n")

        # === 第一步: 检索相关笔记（Gather 阶段）===
        # 从笔记系统中检索与当前问题相关的历史笔记
        # 这些笔记会作为额外上下文提供给 Agent
        relevant_notes = self._retrieve_relevant_notes(user_input)
        note_packets = self._notes_to_packets(relevant_notes)

        # === 第二步: 构建优化的上下文（GSFC Pipeline）===
        # ContextBuilder 会执行完整的 GSFC 流程：
        # - Gather: 收集用户查询、对话历史、系统指令、笔记
        # - Select: 根据相关性筛选信息
        # - Structure: 结构化组织信息
        # - Compress: 压缩到合适的 token 范围
        context = self.context_builder.build(
            user_query=user_input,                           # 当前用户输入
            conversation_history=self.conversation_history,  # 历史对话
            system_instructions=self._build_system_instructions(mode),  # 系统指令
            additional_packets=note_packets                  # 相关笔记
        )

        # === 第三步: 让 Agent 自主决策和使用工具（Agentic 核心）===
        print("[Agent] 正在思考并决定使用哪些工具...\n")
        
        # 更新 agent 的系统提示（包含优化后的上下文）
        self.agent.system_prompt = context
        
        # 调用 agent 执行任务
        # Agent 会：
        # 1. 理解用户意图
        # 2. 自主决定是否需要使用工具
        # 3. 选择合适的工具并调用
        # 4. 整合工具结果生成回答
        response = self.agent.run(user_input)

        # === 第四步: 统计工具使用情况 ===
        self._track_tool_usage()

        # === 第五步: 更新对话历史 ===
        self._update_history(user_input, response)

        print(f"\n[助手] {response}\n")
        print(f"{'='*80}\n")

        return response

    def _build_base_system_prompt(self) -> str:
        """构建基础系统提示"""
        return f"""你是 {self.project_name} 项目的代码库维护助手。

你的核心能力:
1. 使用 TerminalTool 探索代码库
   - 你可以执行任何 shell 命令: ls, cat, grep, find, git 等
   - 工作目录: {self.codebase_path}
   
2. 使用 NoteTool 记录发现和任务
   - 创建笔记记录重要发现
   - 笔记类型: blocker(阻塞问题)、action(行动计划)、task_state(任务状态)、conclusion(结论)
   
3. 使用 MemoryTool 存储关键信息
   - 记住重要的上下文信息
   - 跨会话保持连贯性

当前会话ID: {self.session_id}

重要原则:
- 你要自主决定使用哪些工具、执行什么命令
- 探索代码库时，先了解整体结构，再深入细节
- 发现重要信息时，主动使用 NoteTool 记录
- 保持回答的专业性和实用性
"""

    def _track_tool_usage(self):
        """统计工具使用情况"""
        # 从 agent 的执行历史中统计
        if hasattr(self.agent, 'message_history'):
            for msg in self.agent.message_history[-10:]:  # 只看最近10条
                if msg.role == "tool":
                    self.stats["tool_calls"] += 1
                    # 根据工具名统计
                    if "terminal" in str(msg.content).lower() or "command" in str(msg.content).lower():
                        self.stats["commands_executed"] += 1
                    elif "note" in str(msg.content).lower():
                        if "create" in str(msg.content).lower():
                            self.stats["notes_created"] += 1

    def _retrieve_relevant_notes(self, query: str, limit: int = 3) -> List[Dict]:
        """检索相关笔记
        
        检索策略：
        1. 优先检索 blocker 类型笔记（阻塞问题最重要）
        2. 基于查询语义搜索相关笔记
        3. 合并去重，限制数量
        
        Args:
            query: 查询字符串
            limit: 返回笔记数量上限
            
        Returns:
            相关笔记列表
        """
        try:
            # === 策略1: 优先检索 blocker 类型笔记 ===
            # blocker 代表阻塞问题，优先级最高
            blockers_raw = self.note_tool.run({
                "action": "list",
                "note_type": "blocker",
                "limit": 2
            })
            blockers = self._normalize_note_results(blockers_raw)

            # === 策略2: 基于语义搜索相关笔记 ===
            # 使用用户查询搜索所有类型的相关笔记
            search_results_raw = self.note_tool.run({
                "action": "search",
                "query": query,
                "limit": limit
            })
            search_results = self._normalize_note_results(search_results_raw)

            # === 合并去重 ===
            # 使用字典去重，保证每个笔记只出现一次
            all_notes = {}
            for note in blockers + search_results:
                if not isinstance(note, dict):
                    continue
                note_id = note.get('note_id') or note.get('id')
                if not note_id:
                    continue
                if note_id not in all_notes:
                    all_notes[note_id] = note

            # 返回限制数量的笔记
            return list(all_notes.values())[:limit]

        except Exception as e:
            print(f"[WARNING] 笔记检索失败: {e}")
            return []

    def _normalize_note_results(self, result: Any) -> List[Dict]:
        """将笔记工具的返回值转换为笔记字典列表
        
        NoteTool.run() 的返回值格式不确定，可能是：
        - 字典: {"note_id": "1", "title": "..."}
        - 列表: [{"note_id": "1"}, {"note_id": "2"}]
        - JSON字符串: '{"note_id": "1"}' 或 '[{...}]'
        - 空值: None 或 ""
        
        这个方法统一处理所有情况，保证返回 List[Dict] 格式
        
        Args:
            result: NoteTool 的原始返回值
            
        Returns:
            标准化的笔记字典列表
        """
        # === 情况1: 空值处理 ===
        # None、空字符串、空列表都返回空列表
        if not result:
            return []

        # === 情况2: 单个字典 ===
        # 如果是单个笔记字典，包装成列表
        # 例: {"id": 1} -> [{"id": 1}]
        if isinstance(result, dict):
            return [result]

        # === 情况3: 列表 ===
        # 过滤掉非字典元素，只保留有效的笔记字典
        # 例: [{"id": 1}, "invalid", {"id": 2}] -> [{"id": 1}, {"id": 2}]
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]

        # === 情况4: JSON 字符串 ===
        # 如果是 JSON 格式的字符串，先解析再递归处理
        if isinstance(result, str):
            text = result.strip()
            if not text:
                return []
            # 判断是否是 JSON 格式（以 { 或 [ 开头）
            if text.startswith("{") or text.startswith("["):
                try:
                    parsed = json.loads(text)
                    # 递归调用自己处理解析后的结果
                    # 例: '[{"id": 1}]' -> 解析 -> 递归 -> [{"id": 1}]
                    return self._normalize_note_results(parsed)
                except Exception:
                    # JSON 解析失败，返回空列表
                    return []
            return []

        # === 兜底: 未知类型 ===
        # 其他未知类型一律返回空列表
        return []

    def _notes_to_packets(self, notes: List[Dict]) -> List[ContextPacket]:
        """将笔记转换为上下文包（ContextPacket）
        
        ContextPacket 是 ContextBuilder 的输入格式，包含：
        - content: 内容文本
        - timestamp: 时间戳
        - token_count: token 数量估算
        - relevance_score: 相关性分数（用于 Select 阶段筛选）
        - metadata: 元数据
        
        Args:
            notes: 笔记字典列表
            
        Returns:
            上下文包列表
        """
        packets = []

        for note in notes:
            if not isinstance(note, dict):
                continue
            
            # === 根据笔记类型设置不同的相关性分数 ===
            # 相关性分数决定了笔记在 Select 阶段的优先级
            # blocker（阻塞问题）优先级最高，conclusion（结论）相对较低
            relevance_map = {
                "blocker": 0.9,      # 阻塞问题 - 最高优先级
                "action": 0.8,       # 行动计划 - 高优先级
                "task_state": 0.75,  # 任务状态 - 中高优先级
                "conclusion": 0.7    # 结论 - 中等优先级
            }

            note_type = note.get('type', 'general')
            relevance = relevance_map.get(note_type, 0.6)

            content = f"[笔记:{note.get('title', 'Untitled')}]\n类型: {note_type}\n\n{note.get('content', '')}"
            updated_at = note.get('updated_at')
            try:
                note_timestamp = datetime.fromisoformat(updated_at) if updated_at else datetime.now()
            except (ValueError, TypeError):
                note_timestamp = datetime.now()

            packets.append(ContextPacket(
                content=content,
                timestamp=note_timestamp,
                token_count=len(content) // 4,
                relevance_score=relevance,
                metadata={
                    "type": "note",
                    "note_type": note_type,
                    "note_id": note.get('note_id') or note.get('id')
                }
            ))

        return packets

    def _build_system_instructions(self, mode: str) -> str:
        """构建系统指令（Agentic 方式）
        
        系统指令 = 基础提示词 + 模式提示
        
        关键设计：
        - 不强制 Agent 的行为，只提供"建议策略"
        - Agent 仍然可以自主决定是否遵循建议
        - 这体现了 Agentic 的核心：自主决策权
        
        Args:
            mode: 运行模式（explore/analyze/plan/auto）
            
        Returns:
            完整的系统指令字符串
        """
        base_instructions = self._build_base_system_prompt()

        # === 不同模式的提示策略 ===
        # 注意：这些是"建议"，不是"命令"
        mode_hints = {
            "explore": """
用户当前关注: 探索代码库

建议策略:
- 考虑使用 TerminalTool 了解代码结构（如 find, ls, tree）
- 查看关键文件（如 README, 主要模块）
- 将架构信息记录到笔记方便后续查阅
""",
            "analyze": """
用户当前关注: 分析代码质量

建议策略:
- 考虑使用 grep 查找潜在问题（TODO, FIXME, BUG）
- 分析代码复杂度和结构
- 将发现的问题记录为 blocker 或 action 笔记
""",
            "plan": """
用户当前关注: 任务规划

建议策略:
- 回顾历史笔记了解当前进度
- 基于已有信息制定行动计划
- 创建或更新 task_state 类型的笔记
""",
            "auto": """
用户当前关注: 自由对话

建议策略:
- 根据用户需求灵活决策
- 在需要时主动使用工具获取信息
- 不需要时可以直接回答
"""
        }

        return base_instructions + "\n" + mode_hints.get(mode, mode_hints["auto"])


    def _update_history(self, user_input: str, response: str):
        """更新对话历史"""
        self.conversation_history.append(
            Message(content=user_input, role="user", timestamp=datetime.now())
        )
        self.conversation_history.append(
            Message(content=response, role="assistant", timestamp=datetime.now())
        )

        # 限制历史长度(保留最近10轮对话)
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    # ============================================================
    # === 便捷方法（High-level API）===
    # ============================================================
    # 这些方法封装了常见的使用场景，简化调用
    # 本质上都是调用 run() 方法，只是预设了不同的 mode 和提示

    def explore(self, target: str = ".") -> str:
        """探索代码库（Agentic 方式）
        
        使用场景：初次接触代码库，需要了解整体结构
        
        Agent 会自主决定：
        - 使用哪些命令（ls, find, tree, cat README 等）
        - 查看哪些文件
        - 是否创建笔记记录架构信息
        
        Args:
            target: 探索目标路径，默认为当前目录
            
        Returns:
            探索结果和分析
        """
        return self.run(f"请探索 {target} 的代码结构，了解项目组织方式", mode="explore")

    def analyze(self, focus: str = "") -> str:
        """分析代码质量（Agentic 方式）
        
        使用场景：评估代码质量，发现潜在问题
        
        Agent 会自主决定：
        - 使用 grep 查找 TODO/FIXME/BUG
        - 分析代码复杂度
        - 是否创建 blocker 笔记记录问题
        
        Args:
            focus: 分析重点（可选），如 "安全性" 或 "性能"
            
        Returns:
            分析结果和建议
        """
        query = f"请分析代码质量" + (f"，重点关注{focus}" if focus else "")
        return self.run(query, mode="analyze")

    def plan_next_steps(self) -> str:
        """规划下一步任务（Agentic 方式）
        
        使用场景：基于已有分析，规划后续工作
        
        Agent 会自主决定：
        - 回顾哪些历史笔记
        - 如何组织任务优先级
        - 是否创建 task_state 笔记
        
        Returns:
            任务规划和建议
        """
        return self.run("根据我们之前的分析和当前进度，规划下一步任务", mode="plan")

    def execute_command(self, command: str) -> str:
        """执行终端命令"""
        result = self.terminal_tool.run({"command": command})
        self.stats["commands_executed"] += 1
        return result

    def create_note(
        self,
        title: str,
        content: str,
        note_type: str = "general",
        tags: List[str] = None
    ) -> str:
        """创建笔记"""
        result = self.note_tool.run({
            "action": "create",
            "title": title,
            "content": content,
            "note_type": note_type,
            "tags": tags or [self.project_name]
        })
        self.stats["notes_created"] += 1
        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        duration = (datetime.now() - self.stats["session_start"]).total_seconds()

        # 获取笔记摘要
        try:
            note_summary = self.note_tool.run({"action": "summary"})
        except:
            note_summary = {}

        return {
            "session_info": {
                "session_id": self.session_id,
                "project": self.project_name,
                "duration_seconds": duration
            },
            "activity": {
                "commands_executed": self.stats["commands_executed"],
                "notes_created": self.stats["notes_created"],
                "issues_found": self.stats["issues_found"]
            },
            "notes": note_summary
        }

    def generate_report(self, save_to_file: bool = True) -> Dict[str, Any]:
        """生成会话报告"""
        report = self.get_stats()

        if save_to_file:
            report_file = f"maintainer_report_{self.session_id}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            report["report_file"] = report_file
            print(f"📄 报告已保存: {report_file}")

        return report


def main():
    """主函数 - 演示 CodebaseMaintainer 的使用（Agentic 版本）
    
    这个演示展示了完整的 Agentic 工作流：
    
    架构层次：
    1. 应用层：CodebaseMaintainer 协调整体流程
    2. 上下文管理层：ContextBuilder 执行 GSFC Pipeline
    3. 工具层：TerminalTool, NoteTool, MemoryTool 提供能力
    
    核心特性：
    - Agent 自主决定使用哪些工具（不预定义工作流）
    - 上下文自动优化（GSFC Pipeline）
    - 跨会话记忆和笔记管理
    """
    print("=" * 80)
    print("CodebaseMaintainer 演示（Agentic 版本）")
    print("=" * 80 + "\n")

    # 初始化助手
    maintainer = CodebaseMaintainer(
        project_name="my_flask_app",
        codebase_path="./my_flask_app",
        llm=HelloAgentsLLM()
    )

    # 探索代码库（Agent 自主决定如何探索）
    print("\n### 探索代码库（Agent 自主探索）###")
    response = maintainer.explore()

    # 分析代码质量（Agent 自主决定分析方法）
    print("\n### 分析代码质量（Agent 自主分析）###")
    response = maintainer.analyze()

    # 规划下一步（Agent 基于历史信息规划）
    print("\n### 规划下一步任务（Agent 自主规划）###")
    response = maintainer.plan_next_steps()

    # 生成报告
    print("\n### 生成会话报告 ###")
    report = maintainer.generate_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))

    print("\n" + "=" * 80)
    print("演示完成!")
    print("=" * 80)


if __name__ == "__main__":
    main()
