"""
深度研究 Agent 编排器模块

本模块是整个深度研究系统的核心，实现 TODO-based 研究工作流
这是 DeepResearch 项目最重要的文件，协调所有 Agent 和服务

架构位置：
用户输入
    ↓
DeepResearchAgent (本文件) ← 核心编排器
    ↓
├─ TODO Agent (规划任务)
├─ Summarizer Agent (总结任务)
├─ Report Agent (生成报告)
└─ 搜索服务 (获取信息)

核心概念：
- TODO-based 工作流：动态生成任务列表
- 多 Agent 协作：3 个专业 Agent 分工
- 迭代式研究：多轮搜索深入研究
- 笔记工具：持久化研究进度

Java 对比：
- DeepResearchAgent → 复杂的 Service 编排层
- TODO-based → 任务驱动的工作流引擎
- 无直接对应 → Java 项目通常没有 AI Agent 层
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Any, Callable, Iterator

# HelloAgents 框架核心类
from hello_agents import HelloAgentsLLM, ToolAwareSimpleAgent
from hello_agents.tools import ToolRegistry
from hello_agents.tools.builtin.note_tool import NoteTool

# 导入配置和提示词
from config import Configuration
from prompts import (
    report_writer_instructions,
    task_summarizer_instructions,
    todo_planner_system_prompt,
)
# 导入数据模型
from models import SummaryState, SummaryStateOutput, TodoItem
# 导入服务层
from services.planner import PlanningService
from services.reporter import ReportingService
from services.search import dispatch_search, prepare_research_context
from services.summarizer import SummarizationService
from services.tool_events import ToolCallTracker

logger = logging.getLogger(__name__)


# =============================================================================
# 深度研究 Agent 核心类
# 这是整个系统的编排器，管理所有 Agent 和服务的协作
# =============================================================================
class DeepResearchAgent:
    """
    深度研究 Agent 编排器
    
    使用 TODO-based 工作流协调多个 Agent 完成深度研究任务
    类似 Java 的复杂业务编排服务
    
    核心 Agent：
    1. TODO Agent - 生成研究任务列表
    2. Summarizer Agent - 总结每个任务的结果
    3. Report Agent - 生成最终研究报告
    
    工作流程：
    1. 用户输入研究主题
    2. TODO Agent 生成任务列表
    3. 循环执行每个任务（搜索 + 总结）
    4. Report Agent 整合所有结果生成报告
    """

    def __init__(self, config: Configuration | None = None) -> None:
        """
        初始化深度研究 Agent
        
        创建 3 个专业 Agent 和相关服务
        
        Args:
            config: 配置对象（可选，默认从环境变量加载）
        """
        # ===================================================================
        # 1. 初始化配置和 LLM
        # ===================================================================
        self.config = config or Configuration.from_env()  # 加载配置
        self.llm = self._init_llm()  # 初始化 LLM 实例

        # ===================================================================
        # 2. 初始化笔记工具（可选）
        # 用于持久化研究进度，类似 Java 的持久层
        # ===================================================================
        self.note_tool = (
            NoteTool(workspace=self.config.notes_workspace)
            if self.config.enable_notes
            else None
        )
        
        # 工具注册表（如果启用笔记工具）
        self.tools_registry: ToolRegistry | None = None
        if self.note_tool:
            registry = ToolRegistry()
            registry.register_tool(self.note_tool)
            self.tools_registry = registry

        # ===================================================================
        # 3. 初始化工具调用跟踪器
        # 用于记录和监控工具调用
        # ===================================================================
        self._tool_tracker = ToolCallTracker(
            self.config.notes_workspace if self.config.enable_notes else None
        )
        self._tool_event_sink_enabled = False
        self._state_lock = Lock()  # 线程锁，用于并发控制

        # ===================================================================
        # 4. 创建 3 个专业 Agent
        # ===================================================================
        # Agent 1: TODO 规划 Agent - 生成研究任务列表
        self.todo_agent = self._create_tool_aware_agent(
            name="研究规划专家",
            system_prompt=todo_planner_system_prompt.strip(),
        )
        
        # Agent 2: 报告撰写 Agent - 生成最终研究报告
        self.report_agent = self._create_tool_aware_agent(
            name="报告撰写专家",
            system_prompt=report_writer_instructions.strip(),
        )

        # Agent 3: 任务总结 Agent - 总结每个任务的结果
        # 使用工厂模式，每次需要时创建新实例
        self._summarizer_factory: Callable[[], ToolAwareSimpleAgent] = lambda: self._create_tool_aware_agent(
            name="任务总结专家",
            system_prompt=task_summarizer_instructions.strip(),
        )

        # ===================================================================
        # 5. 创建服务层实例
        # 每个服务封装特定的业务逻辑
        # ===================================================================
        self.planner = PlanningService(self.todo_agent, self.config)        # 规划服务
        self.summarizer = SummarizationService(self._summarizer_factory, self.config)  # 总结服务
        self.reporting = ReportingService(self.report_agent, self.config)   # 报告服务
        
        self._last_search_notices: list[str] = []  # 最后的搜索通知列表

    # =========================================================================
    # 私有辅助方法
    # =========================================================================
    def _init_llm(self) -> HelloAgentsLLM:
        """
        初始化 LLM 实例
        
        根据配置创建 HelloAgentsLLM 实例，支持多种提供商
        类似 Java: @Bean 方法创建 LLM 客户端
        
        Returns:
            HelloAgentsLLM: LLM 实例
        """
        # 基础配置：temperature=0.0 确保输出稳定
        llm_kwargs: dict[str, Any] = {"temperature": 0.0}

        # 设置模型 ID
        model_id = self.config.llm_model_id or self.config.local_llm
        if model_id:
            llm_kwargs["model"] = model_id

        # 设置提供商
        provider = (self.config.llm_provider or "").strip()
        if provider:
            llm_kwargs["provider"] = provider

        # 根据不同提供商配置 API 端点和密钥
        if provider == "ollama":
            llm_kwargs["base_url"] = self.config.sanitized_ollama_url()
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif provider == "lmstudio":
            llm_kwargs["base_url"] = self.config.lmstudio_base_url
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key
        else:
            if self.config.llm_base_url:
                llm_kwargs["base_url"] = self.config.llm_base_url
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key

        # 创建并返回 LLM 实例
        return HelloAgentsLLM(**llm_kwargs)

    def _create_tool_aware_agent(self, *, name: str, system_prompt: str) -> ToolAwareSimpleAgent:
        """
        创建工具感知 Agent
        
        创建一个支持工具调用的 Agent 实例
        所有 Agent 共享工具注册表和跟踪器
        
        Args:
            name: Agent 名称
            system_prompt: 系统提示词
            
        Returns:
            ToolAwareSimpleAgent: Agent 实例
        """
        return ToolAwareSimpleAgent(
            name=name,
            llm=self.llm,
            system_prompt=system_prompt,
            enable_tool_calling=self.tools_registry is not None,
            tool_registry=self.tools_registry,
            tool_call_listener=self._tool_tracker.record,
        )

    def _set_tool_event_sink(self, sink: Callable[[dict[str, Any]], None] | None) -> None:
        """
        设置工具事件接收器
        
        用于流式模式，将工具调用事件实时发送到事件队列
        在阻塞模式下，事件会被缓存，稍后一次性处理
        
        Args:
            sink: 事件处理函数（None 表示禁用实时发送）
        """
        self._tool_event_sink_enabled = sink is not None
        self._tool_tracker.set_event_sink(sink)

    # =========================================================================
    # 公共 API - 主执行方法
    # =========================================================================
    def run(self, topic: str) -> SummaryStateOutput:
        """
        执行研究工作流（阻塞模式）
        
        这是核心的执行方法，实现 TODO-based 工作流
        
        工作流程：
        1. 创建研究状态
        2. TODO Agent 生成任务列表
        3. 循环执行每个任务（搜索 + 总结）
        4. Report Agent 生成最终报告
        5. 返回结果
        
        Args:
            topic: 研究主题（用户输入）
            
        Returns:
            SummaryStateOutput: 研究结果（包含报告和任务列表）
        """
        # ===================================================================
        # 步骤 1: 创建研究状态并生成 TODO 列表
        # ===================================================================
        state = SummaryState(research_topic=topic)
        state.todo_items = self.planner.plan_todo_list(state)  # TODO Agent 生成任务
        self._drain_tool_events(state)

        # 如果没有生成任务，创建一个默认任务
        if not state.todo_items:
            logger.info("No TODO items generated; falling back to single task")
            state.todo_items = [self.planner.create_fallback_task(state)]

        # ===================================================================
        # 步骤 2: 循环执行每个 TODO 任务
        # ===================================================================
        for task in state.todo_items:
            self._execute_task(state, task, emit_stream=False)

        # ===================================================================
        # 步骤 3: 生成最终研究报告
        # ===================================================================
        report = self.reporting.generate_report(state)  # Report Agent 生成报告
        self._drain_tool_events(state)
        state.structured_report = report
        state.running_summary = report
        self._persist_final_report(state, report)  # 持久化报告

        # ===================================================================
        # 步骤 4: 返回结果
        # ===================================================================
        return SummaryStateOutput(
            running_summary=report,
            report_markdown=report,
            todo_items=state.todo_items,
        )

    def run_stream(self, topic: str) -> Iterator[dict[str, Any]]:
        """
        执行研究工作流（流式模式）
        
        与 run() 方法类似，但以流式方式返回进度事件
        适用于需要实时反馈的场景（如 Web UI）
        
        类似 Java: public Stream<ResearchEvent> executeResearchStream(String topic)
        
        工作流程：
        1. 生成 TODO 列表并返回
        2. 并行执行所有任务（多线程）
        3. 实时返回每个任务的进度事件
        4. 生成并返回最终报告
        
        Args:
            topic: 研究主题
            
        Yields:
            dict: 进度事件（类型：status/todo_list/task_status/sources/final_report/done）
        """
        # ===================================================================
        # 步骤 1: 初始化状态
        # ===================================================================
        state = SummaryState(research_topic=topic)
        logger.debug("Starting streaming research: topic=%s", topic)
        yield {"type": "status", "message": "初始化研究流程"}

        state.todo_items = self.planner.plan_todo_list(state)
        for event in self._drain_tool_events(state, step=0):
            yield event
        if not state.todo_items:
            state.todo_items = [self.planner.create_fallback_task(state)]

        channel_map: dict[int, dict[str, Any]] = {}
        for index, task in enumerate(state.todo_items, start=1):
            token = f"task_{task.id}"
            task.stream_token = token
            channel_map[task.id] = {"step": index, "token": token}

        yield {
            "type": "todo_list",
            "tasks": [self._serialize_task(t) for t in state.todo_items],
            "step": 0,
        }

        # 创建事件队列，用于收集多线程产生的事件
        event_queue: Queue[dict[str, Any]] = Queue()

        def enqueue(
            event: dict[str, Any],
            *,
            task: TodoItem | None = None,
            step_override: int | None = None,
        ) -> None:
            """
            将事件放入队列
            
            为事件添加任务 ID、步骤编号、流式令牌等元数据
            确保前端可以正确识别和显示事件
            
            Args:
                event: 原始事件
                task: 关联的任务（可选）
                step_override: 覆盖步骤编号（可选）
            """
            payload = dict(event)
            target_task_id = payload.get("task_id")
            
            # 如果提供了任务对象，使用任务的 ID
            if task is not None:
                target_task_id = task.id
                payload["task_id"] = task.id

            # 从通道映射中获取步骤和令牌信息
            channel = channel_map.get(target_task_id) if target_task_id is not None else None
            if channel:
                payload.setdefault("step", channel["step"])
                payload["stream_token"] = channel["token"]
            
            # 允许覆盖步骤编号
            if step_override is not None:
                payload["step"] = step_override
            
            # 放入队列
            event_queue.put(payload)

        def tool_event_sink(event: dict[str, Any]) -> None:
            enqueue(event)

        self._set_tool_event_sink(tool_event_sink)

        # 线程列表，用于管理并行执行的任务
        threads: list[Thread] = []

        def worker(task: TodoItem, step: int) -> None:
            """
            工作线程函数
            
            在独立线程中执行单个任务
            捕获所有事件并放入队列，供主线程返回给用户
            
            Args:
                task: 要执行的任务
                step: 步骤编号
            """
            try:
                # 发送任务开始事件
                enqueue(
                    {
                        "type": "task_status",
                        "task_id": task.id,
                        "status": "in_progress",
                        "title": task.title,
                        "intent": task.intent,
                        "note_id": task.note_id,
                        "note_path": task.note_path,
                    },
                    task=task,
                )

                # 执行任务，将所有事件放入队列
                for event in self._execute_task(state, task, emit_stream=True, step=step):
                    enqueue(event, task=task)
                    
            except Exception as exc:  # pragma: no cover - defensive guardrail
                # 任务执行失败，记录错误并发送失败事件
                logger.exception("Task execution failed", exc_info=exc)
                enqueue(
                    {
                        "type": "task_status",
                        "task_id": task.id,
                        "status": "failed",
                        "detail": str(exc),
                        "title": task.title,
                        "intent": task.intent,
                        "note_id": task.note_id,
                        "note_path": task.note_path,
                    },
                    task=task,
                )
            finally:
                # 无论成功或失败，都发送任务完成标记
                enqueue({"type": "__task_done__", "task_id": task.id})

        # ===================================================================
        # 启动所有任务线程（并行执行）
        # ===================================================================
        for task in state.todo_items:
            step = channel_map.get(task.id, {}).get("step", 0)
            # 创建守护线程，避免主线程退出时线程仍在运行
            thread = Thread(target=worker, args=(task, step), daemon=True)
            threads.append(thread)
            thread.start()  # 立即启动线程

        # 跟踪任务完成情况
        active_workers = len(state.todo_items)
        finished_workers = 0

        try:
            # ===================================================================
            # 主事件循环：从队列中取出事件并返回给用户
            # ===================================================================
            while finished_workers < active_workers:
                # 阻塞等待事件（如果队列为空会等待）
                event = event_queue.get()
                
                # 检查是否是任务完成标记
                if event.get("type") == "__task_done__":
                    finished_workers += 1
                    continue  # 不返回完成标记，只用于计数
                
                # 返回事件给用户
                yield event

            # ===================================================================
            # 所有任务完成后，清空队列中剩余的事件
            # ===================================================================
            while True:
                try:
                    # 非阻塞获取（如果队列为空立即抛出异常）
                    event = event_queue.get_nowait()
                except Empty:
                    break  # 队列已空，退出循环
                
                # 跳过任务完成标记
                if event.get("type") != "__task_done__":
                    yield event
        finally:
            # ===================================================================
            # 清理工作：禁用事件接收器，等待所有线程结束
            # ===================================================================
            self._set_tool_event_sink(None)
            for thread in threads:
                thread.join()  # 等待线程结束

        report = self.reporting.generate_report(state)
        final_step = len(state.todo_items) + 1
        for event in self._drain_tool_events(state, step=final_step):
            yield event
        state.structured_report = report
        state.running_summary = report

        note_event = self._persist_final_report(state, report)
        if note_event:
            yield note_event

        yield {
            "type": "final_report",
            "report": report,
            "note_id": state.report_note_id,
            "note_path": state.report_note_path,
        }
        yield {"type": "done"}

    # =========================================================================
    # 任务执行辅助方法
    # =========================================================================
    def _execute_task(
        self,
        state: SummaryState,
        task: TodoItem,
        *,
        emit_stream: bool,
        step: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        执行单个 TODO 任务
        
        这是任务执行的核心逻辑，包含搜索和总结两个步骤
        
        执行流程：
        1. 调用搜索服务获取信息
        2. 准备研究上下文
        3. 调用 Summarizer Agent 总结结果
        4. 更新任务状态
        
        Args:
            state: 研究状态
            task: 要执行的任务
            emit_stream: 是否发送流式事件
            step: 步骤编号（用于流式模式）
            
        Yields:
            dict: 任务执行事件（如果 emit_stream=True）
        """
        # ===================================================================
        # 步骤 1: 执行搜索
        # ===================================================================
        task.status = "in_progress"

        # 调用搜索服务（支持多种搜索引擎）
        search_result, notices, answer_text, backend = dispatch_search(
            task.query,
            self.config,
            state.research_loop_count,
        )
        self._last_search_notices = notices
        task.notices = notices

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
        else:
            self._drain_tool_events(state)

        if notices and emit_stream:
            for notice in notices:
                if notice:
                    yield {
                        "type": "status",
                        "message": notice,
                        "task_id": task.id,
                        "step": step,
                    }

        # ===================================================================
        # 步骤 2: 检查搜索结果
        # ===================================================================
        if not search_result or not search_result.get("results"):
            # 没有搜索结果，跳过此任务
            task.status = "skipped"
            if emit_stream:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                yield {
                    "type": "task_status",
                    "task_id": task.id,
                    "status": "skipped",
                    "title": task.title,
                    "intent": task.intent,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                    "step": step,
                }
            else:
                self._drain_tool_events(state)
            return
        else:
            if not emit_stream:
                self._drain_tool_events(state)

        # ===================================================================
        # 步骤 3: 准备研究上下文
        # ===================================================================
        sources_summary, context = prepare_research_context(
            search_result,
            answer_text,
            self.config,
        )

        task.sources_summary = sources_summary

        # 更新全局状态（线程安全）
        with self._state_lock:
            state.web_research_results.append(context)
            state.sources_gathered.append(sources_summary)
            state.research_loop_count += 1

        # ===================================================================
        # 步骤 4: 调用 Summarizer Agent 总结任务结果
        # ===================================================================
        summary_text: str | None = None

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "sources",
                "task_id": task.id,
                "latest_sources": sources_summary,
                "raw_context": context,
                "step": step,
                "backend": backend,
                "note_id": task.note_id,
                "note_path": task.note_path,
            }

            summary_stream, summary_getter = self.summarizer.stream_task_summary(state, task, context)
            try:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                for chunk in summary_stream:
                    if chunk:
                        yield {
                            "type": "task_summary_chunk",
                            "task_id": task.id,
                            "content": chunk,
                            "note_id": task.note_id,
                            "step": step,
                        }
                    for event in self._drain_tool_events(state, step=step):
                        yield event
            finally:
                summary_text = summary_getter()
        else:
            summary_text = self.summarizer.summarize_task(state, task, context)
            self._drain_tool_events(state)

        task.summary = summary_text.strip() if summary_text else "暂无可用信息"
        task.status = "completed"

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "task_status",
                "task_id": task.id,
                "status": "completed",
                "summary": task.summary,
                "sources_summary": task.sources_summary,
                "note_id": task.note_id,
                "note_path": task.note_path,
                "step": step,
            }
        else:
            self._drain_tool_events(state)

    def _drain_tool_events(
        self,
        state: SummaryState,
        *,
        step: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        排空工具调用事件
        
        从工具跟踪器中获取所有待处理的工具调用事件
        在流式模式下，事件已经实时发送，返回空列表
        在阻塞模式下，返回所有缓存的事件
        
        Args:
            state: 研究状态
            step: 步骤编号（用于流式模式）
            
        Returns:
            list: 工具调用事件列表
        """
        events = self._tool_tracker.drain(state, step=step)
        
        # 如果启用了实时事件发送（流式模式），返回空列表
        # 因为事件已经通过 sink 实时发送了
        if self._tool_event_sink_enabled:
            return []
        
        # 阻塞模式下，返回所有缓存的事件
        return events

    @property
    def _tool_call_events(self) -> list[dict[str, Any]]:
        """Expose recorded tool events for legacy integrations."""
        return self._tool_tracker.as_dicts()

    def _serialize_task(self, task: TodoItem) -> dict[str, Any]:
        """
        序列化任务对象
        
        将 TodoItem 数据类转换为字典，用于 JSON 响应
        前端需要这种格式来显示任务信息
        
        Args:
            task: 任务对象
            
        Returns:
            dict: 可序列化的任务字典
        """
        return {
            "id": task.id,
            "title": task.title,
            "intent": task.intent,
            "query": task.query,
            "status": task.status,
            "summary": task.summary,
            "sources_summary": task.sources_summary,
            "note_id": task.note_id,
            "note_path": task.note_path,
            "stream_token": task.stream_token,
        }

    def _persist_final_report(self, state: SummaryState, report: str) -> dict[str, Any] | None:
        """
        持久化最终研究报告
        
        将研究报告保存到笔记工具
        如果已存在报告笔记，则更新；否则创建新笔记
        
        Args:
            state: 研究状态
            report: 研究报告内容
            
        Returns:
            dict: 笔记事件（包含笔记 ID 和路径），如果保存失败则返回 None
        """
        # 检查前置条件
        if not self.note_tool or not report or not report.strip():
            return None

        # 准备笔记元数据
        note_title = f"研究报告：{state.research_topic}".strip() or "研究报告"
        tags = ["deep_research", "report"]
        content = report.strip()

        # 查找是否已存在报告笔记
        note_id = self._find_existing_report_note_id(state)
        response = ""

        # 如果找到已存在的笔记，尝试更新
        if note_id:
            response = self.note_tool.run(
                {
                    "action": "update",
                    "note_id": note_id,
                    "title": note_title,
                    "note_type": "conclusion",
                    "tags": tags,
                    "content": content,
                }
            )
            # 如果更新失败，清空 note_id，稍后创建新笔记
            if response.startswith("❌"):
                note_id = None

        # 如果没有已存在的笔记，或更新失败，创建新笔记
        if not note_id:
            response = self.note_tool.run(
                {
                    "action": "create",
                    "title": note_title,
                    "note_type": "conclusion",
                    "tags": tags,
                    "content": content,
                }
            )
            # 从响应中提取笔记 ID
            note_id = self._extract_note_id_from_text(response)

        # 如果仍然没有 note_id，说明保存失败
        if not note_id:
            return None

        # 更新状态对象
        state.report_note_id = note_id
        if self.config.notes_workspace:
            note_path = Path(self.config.notes_workspace) / f"{note_id}.md"
            state.report_note_path = str(note_path)
        else:
            note_path = None

        # 构建返回的事件
        payload = {
            "type": "report_note",
            "note_id": note_id,
            "title": note_title,
            "content": content,
        }
        if note_path:
            payload["note_path"] = str(note_path)

        return payload

    def _find_existing_report_note_id(self, state: SummaryState) -> str | None:
        """
        查找已存在的报告笔记 ID
        
        从状态对象或工具调用历史中查找报告笔记的 ID
        避免重复创建报告笔记
        
        Args:
            state: 研究状态
            
        Returns:
            str: 笔记 ID，如果未找到则返回 None
        """
        # 首先检查状态对象中是否已有笔记 ID
        if state.report_note_id:
            return state.report_note_id

        # 从工具调用历史中查找（倒序遍历，最新的在前）
        for event in reversed(self._tool_tracker.as_dicts()):
            # 只关注笔记工具的调用
            if event.get("tool") != "note":
                continue

            # 获取调用参数
            parameters = event.get("parsed_parameters") or {}
            if not isinstance(parameters, dict):
                continue

            # 只关注创建或更新操作
            action = parameters.get("action")
            if action not in {"create", "update"}:
                continue

            # 检查笔记类型或标题
            note_type = parameters.get("note_type")
            if note_type != "conclusion":
                # 如果不是 conclusion 类型，检查标题是否以"研究报告"开头
                title = parameters.get("title")
                if not (isinstance(title, str) and title.startswith("研究报告")):
                    continue

            # 尝试获取笔记 ID
            note_id = parameters.get("note_id")
            if not note_id:
                # 如果参数中没有，尝试从结果中提取
                note_id = self._tool_tracker._extract_note_id(event.get("result", ""))  # type: ignore[attr-defined]

            if note_id:
                return note_id

        # 未找到
        return None

    @staticmethod
    def _extract_note_id_from_text(response: str) -> str | None:
        """
        从文本响应中提取笔记 ID
        
        笔记工具的响应格式通常包含 "ID: xxx"
        使用正则表达式提取 ID
        
        Args:
            response: 笔记工具的响应文本
            
        Returns:
            str: 提取的笔记 ID，如果未找到则返回 None
        """
        if not response:
            return None

        # 使用正则表达式匹配 "ID: xxx" 格式
        match = re.search(r"ID:\s*([^\n]+)", response)
        if not match:
            return None

        return match.group(1).strip()


def run_deep_research(topic: str, config: Configuration | None = None) -> SummaryStateOutput:
    """
    便捷函数：执行深度研究
    
    这是一个快捷方式，无需手动创建 DeepResearchAgent 实例
    内部会自动创建 Agent 并执行研究
    
    Args:
        topic: 研究主题
        config: 配置对象（可选）
        
    Returns:
        SummaryStateOutput: 研究结果
        
    Example:
        result = run_deep_research("AI Agent 是什么")
        print(result.report_markdown)
    """
    agent = DeepResearchAgent(config=config)
    return agent.run(topic)
