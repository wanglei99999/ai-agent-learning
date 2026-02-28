"""
任务总结服务模块

负责调用 Summarizer Agent 总结每个任务的搜索结果
支持阻塞模式和流式模式两种总结方式

核心功能：
1. 调用 Summarizer Agent 生成任务总结
2. 支持流式输出（实时返回总结内容）
3. 处理思考标记和工具调用标记
4. 构建总结提示词
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Tuple

from hello_agents import ToolAwareSimpleAgent

from models import SummaryState, TodoItem
from config import Configuration
from utils import strip_thinking_tokens
from services.notes import build_note_guidance
from services.text_processing import strip_tool_calls


class SummarizationService:
    """
    任务总结服务类
    
    封装 Summarizer Agent，负责总结每个任务的搜索结果
    支持同步模式和流式模式两种总结方式
    
    Attributes:
        _agent_factory: Agent 工厂函数（每次调用创建新实例）
        _config: 配置对象
    """

    def __init__(
        self,
        summarizer_factory: Callable[[], ToolAwareSimpleAgent],
        config: Configuration,
    ) -> None:
        """
        初始化任务总结服务
        
        Args:
            summarizer_factory: Agent 工厂函数（每次需要时创建新 Agent）
            config: 配置对象
        """
        self._agent_factory = summarizer_factory
        self._config = config

    def summarize_task(self, state: SummaryState, task: TodoItem, context: str) -> str:
        """
        生成任务总结（阻塞模式）
        
        调用 Summarizer Agent 分析搜索结果并生成任务总结
        等待 Agent 完成后一次性返回完整总结
        
        Args:
            state: 研究状态对象
            task: 要总结的任务
            context: 搜索结果上下文（包含所有搜索内容）
            
        Returns:
            str: 任务总结（Markdown 格式）
        """
        # 构建提示词
        prompt = self._build_prompt(state, task, context)

        # 创建新的 Agent 实例（避免上下文混淆）
        agent = self._agent_factory()
        try:
            # 调用 Agent 生成总结
            response = agent.run(prompt)
        finally:
            # 清空对话历史
            agent.clear_history()

        # 清理总结文本
        summary_text = response.strip()
        
        # 移除思考标记（如果配置启用）
        if self._config.strip_thinking_tokens:
            summary_text = strip_thinking_tokens(summary_text)

        # 移除工具调用标记
        summary_text = strip_tool_calls(summary_text).strip()

        # 返回总结，如果为空则返回默认文本
        return summary_text or "暂无可用信息"

    def stream_task_summary(
        self, state: SummaryState, task: TodoItem, context: str
    ) -> Tuple[Iterator[str], Callable[[], str]]:
        """
        生成任务总结（流式模式）
        
        调用 Summarizer Agent 生成总结，实时返回生成的内容
        同时收集完整输出，供后续使用
        
        Args:
            state: 研究状态对象
            task: 要总结的任务
            context: 搜索结果上下文
            
        Returns:
            tuple: (生成器, 获取完整总结的函数)
                - 生成器: 逐块返回总结内容
                - 获取函数: 调用后返回完整的总结文本
        """
        # 构建提示词
        prompt = self._build_prompt(state, task, context)
        
        # 是否移除思考标记
        remove_thinking = self._config.strip_thinking_tokens
        
        # 缓冲区：存储原始输出和可见输出
        raw_buffer = ""        # 原始输出（包含思考标记）
        visible_output = ""    # 可见输出（移除思考标记后）
        emit_index = 0         # 当前发送位置
        
        # 创建新的 Agent 实例
        agent = self._agent_factory()

        def flush_visible() -> Iterator[str]:
            """
            刷新可见内容
            
            从原始缓冲区中提取可见内容（跳过思考标记）
            实时过滤 <think>...</think> 标签
            """
            nonlocal emit_index, raw_buffer
            while True:
                # 查找下一个思考标记的开始位置
                start = raw_buffer.find("<think>", emit_index)
                
                if start == -1:
                    # 没有更多思考标记，发送剩余内容
                    if emit_index < len(raw_buffer):
                        segment = raw_buffer[emit_index:]
                        emit_index = len(raw_buffer)
                        if segment:
                            yield segment
                    break

                # 发送思考标记之前的内容
                if start > emit_index:
                    segment = raw_buffer[emit_index:start]
                    emit_index = start
                    if segment:
                        yield segment

                # 查找思考标记的结束位置
                end = raw_buffer.find("</think>", start)
                if end == -1:
                    # 思考标记未闭合，等待更多内容
                    break
                
                # 跳过整个思考标记
                emit_index = end + len("</think>")

        def generator() -> Iterator[str]:
            """
            生成器函数
            
            从 Agent 流式接收内容，实时处理并返回
            """
            nonlocal raw_buffer, visible_output, emit_index
            try:
                # 流式调用 Agent
                for chunk in agent.stream_run(prompt):
                    # 添加到原始缓冲区
                    raw_buffer += chunk
                    
                    if remove_thinking:
                        # 移除思考标记模式：实时过滤
                        for segment in flush_visible():
                            visible_output += segment
                            if segment:
                                yield segment
                    else:
                        # 不移除思考标记：直接返回
                        visible_output += chunk
                        if chunk:
                            yield chunk
            finally:
                # 确保所有剩余内容都被发送
                if remove_thinking:
                    for segment in flush_visible():
                        visible_output += segment
                        if segment:
                            yield segment
                # 清空对话历史
                agent.clear_history()

        def get_summary() -> str:
            """
            获取完整总结
            
            在流式输出完成后调用，返回完整的总结文本
            """
            # 清理总结文本
            if remove_thinking:
                cleaned = strip_thinking_tokens(visible_output)
            else:
                cleaned = visible_output

            # 移除工具调用标记并返回
            return strip_tool_calls(cleaned).strip()

        # 返回生成器和获取函数
        return generator(), get_summary

    def _build_prompt(self, state: SummaryState, task: TodoItem, context: str) -> str:
        """
        构建总结提示词
        
        为 Summarizer Agent 准备完整的提示词
        包含任务信息、搜索上下文和笔记协作指导
        
        Args:
            state: 研究状态对象
            task: 要总结的任务
            context: 搜索结果上下文
            
        Returns:
            str: 完整的提示词
        """
        return (
            f"任务主题：{state.research_topic}\n"
            f"任务名称：{task.title}\n"
            f"任务目标：{task.intent}\n"
            f"检索查询：{task.query}\n"
            f"任务上下文：\n{context}\n"
            f"{build_note_guidance(task)}\n"  # 笔记协作指导
            "请按照以上协作要求先同步笔记，然后返回一份面向用户的 Markdown 总结（仍遵循任务总结模板）。"
        )
