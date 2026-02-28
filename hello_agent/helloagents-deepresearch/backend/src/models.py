"""
数据模型定义模块

本模块定义深度研究工作流使用的所有数据模型
类似 Java 的 DTO (Data Transfer Object) 和 Entity

主要功能：
1. 定义 TODO 任务项模型
2. 定义研究状态模型
3. 定义输入输出模型

Java 对比：
- @dataclass → @Data 注解（Lombok）
- TodoItem → POJO/DTO 类
- SummaryState → 状态管理对象
"""

import operator
from dataclasses import dataclass, field
from typing import List, Optional

from typing_extensions import Annotated


# =============================================================================
# TODO 任务项模型
# 表示单个研究任务，类似 Java 的 Task 实体类
# =============================================================================
@dataclass(kw_only=True)
class TodoItem:
    """
    TODO 任务项模型
    
    表示一个待执行的研究任务
    类似 Java: @Data public class TodoItem { ... }
    
    工作流：
    1. TODO Agent 生成任务列表
    2. 每个任务包含 id、标题、意图、查询等
    3. 执行后更新 status 和 summary
    """

    id: int                                      # 任务 ID（唯一标识）
    title: str                                   # 任务标题
    intent: str                                  # 任务意图（为什么要做这个任务）
    query: str                                   # 搜索查询（用于搜索引擎）
    status: str = field(default="pending")      # 任务状态（pending/completed/failed）
    summary: Optional[str] = field(default=None) # 任务总结（执行后生成）
    sources_summary: Optional[str] = field(default=None)  # 来源总结
    notices: list[str] = field(default_factory=list)      # 通知/警告列表
    note_id: Optional[str] = field(default=None)          # 笔记 ID（如果启用笔记工具）
    note_path: Optional[str] = field(default=None)        # 笔记路径
    stream_token: Optional[str] = field(default=None)     # 流式传输令牌


# =============================================================================
# 研究状态模型
# 跟踪整个研究过程的状态，类似 Java 的 Session 或 Context 对象
# =============================================================================
@dataclass(kw_only=True)
class SummaryState:
    """
    研究状态模型
    
    跟踪整个深度研究过程的状态信息
    类似 Java: @Data public class ResearchContext { ... }
    
    状态包括：
    - 研究主题
    - 搜索结果
    - TODO 任务列表
    - 循环计数
    - 最终报告
    """
    
    research_topic: str = field(default=None)  # 研究主题（用户输入）
    search_query: str = field(default=None)    # 搜索查询（已废弃）
    
    # Annotated[list, operator.add] 表示列表可以累加（追加元素）
    web_research_results: Annotated[list, operator.add] = field(default_factory=list)  # 网络搜索结果列表
    sources_gathered: Annotated[list, operator.add] = field(default_factory=list)      # 收集的来源列表
    
    research_loop_count: int = field(default=0)  # 研究循环计数（当前第几轮）
    running_summary: str = field(default=None)   # 运行中的总结（旧字段）
    
    todo_items: Annotated[list, operator.add] = field(default_factory=list)  # TODO 任务列表
    
    structured_report: Optional[str] = field(default=None)      # 结构化报告（最终输出）
    report_note_id: Optional[str] = field(default=None)         # 报告笔记 ID
    report_note_path: Optional[str] = field(default=None)       # 报告笔记路径


# =============================================================================
# 输入模型
# 定义用户输入的数据结构
# =============================================================================
@dataclass(kw_only=True)
class SummaryStateInput:
    """
    研究输入模型
    
    定义用户启动研究时的输入
    类似 Java: @Data public class ResearchRequest { ... }
    """
    
    research_topic: str = field(default=None)  # 研究主题（用户输入的问题）


# =============================================================================
# 输出模型
# 定义返回给用户的数据结构
# =============================================================================
@dataclass(kw_only=True)
class SummaryStateOutput:
    """
    研究输出模型
    
    定义研究完成后返回的结果
    类似 Java: @Data public class ResearchResponse { ... }
    """
    
    running_summary: str = field(default=None)                  # 运行总结（向后兼容）
    report_markdown: Optional[str] = field(default=None)        # Markdown 格式的报告
    todo_items: List[TodoItem] = field(default_factory=list)    # 执行的 TODO 任务列表

