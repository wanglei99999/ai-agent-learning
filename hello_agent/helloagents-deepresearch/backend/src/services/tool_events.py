"""
工具调用事件跟踪模块

负责收集和管理 Agent 的工具调用事件
用于日志记录、前端展示和任务状态同步

核心功能：
1. 记录 Agent 的工具调用（如笔记工具）
2. 提取和转换事件为前端可用格式
3. 同步任务的笔记 ID
4. 支持流式模式的实时事件推送
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Optional

from models import SummaryState, TodoItem

logger = logging.getLogger(__name__)


@dataclass
class ToolCallEvent:
    """
    工具调用事件数据类
    
    内部表示单个工具调用事件的所有信息
    用于存储和传递工具调用的详细数据
    
    Attributes:
        id: 事件唯一 ID
        agent: 调用工具的 Agent 名称
        tool: 工具名称（如 "note"）
        raw_parameters: 原始参数字符串
        parsed_parameters: 解析后的参数字典
        result: 工具调用的返回结果
        task_id: 关联的任务 ID（如果有）
        note_id: 关联的笔记 ID（如果有）
    """

    id: int
    agent: str
    tool: str
    raw_parameters: str
    parsed_parameters: dict[str, Any]
    result: str
    task_id: Optional[int]
    note_id: Optional[str]


class ToolCallTracker:
    """
    工具调用跟踪器
    
    收集 Agent 的工具调用事件并转换为前端可用的格式
    支持阻塞模式（缓存事件）和流式模式（实时推送）
    
    Attributes:
        _notes_workspace: 笔记工作目录路径
        _events: 事件列表（按时间顺序）
        _cursor: 当前读取位置（用于增量获取）
        _lock: 线程锁（确保线程安全）
        _event_sink: 事件接收器（流式模式使用）
    """

    def __init__(self, notes_workspace: Optional[str]) -> None:
        """
        初始化工具调用跟踪器
        
        Args:
            notes_workspace: 笔记工作目录路径（可选）
        """
        self._notes_workspace = notes_workspace
        self._events: list[ToolCallEvent] = []  # 事件列表
        self._cursor = 0                         # 读取游标
        self._lock = Lock()                      # 线程锁
        self._event_sink: Optional[Callable[[dict[str, Any]], None]] = None  # 事件接收器

    def record(self, payload: dict[str, Any]) -> None:
        """
        记录工具调用事件
        
        当 Agent 调用工具时，此方法被调用以记录事件详情
        提取关键信息（Agent、工具、参数、结果）并存储
        
        Args:
            payload: 工具调用的原始数据
        """
        # ===================================================================
        # 步骤 1: 提取基本信息
        # ===================================================================
        agent_name = str(payload.get("agent_name") or "unknown")
        tool_name = str(payload.get("tool_name") or "unknown")
        raw_parameters = str(payload.get("raw_parameters") or "")
        parsed_parameters = payload.get("parsed_parameters") or {}
        result_text = str(payload.get("result") or "")

        # 确保参数是字典类型
        if not isinstance(parsed_parameters, dict):
            parsed_parameters = {}

        # ===================================================================
        # 步骤 2: 推断任务 ID 和笔记 ID
        # ===================================================================
        # 从参数中推断任务 ID
        task_id = self._infer_task_id(parsed_parameters)
        note_id: Optional[str] = None

        # 如果是笔记工具，提取笔记 ID
        if tool_name == "note":
            note_id = parsed_parameters.get("note_id")
            if note_id is None:
                # 从结果中提取笔记 ID（创建笔记时）
                note_id = self._extract_note_id(result_text)

        # ===================================================================
        # 步骤 3: 创建事件对象
        # ===================================================================
        event = ToolCallEvent(
            id=len(self._events) + 1,
            agent=agent_name,
            tool=tool_name,
            raw_parameters=raw_parameters,
            parsed_parameters=parsed_parameters,
            result=result_text,
            task_id=task_id,
            note_id=note_id,
        )

        # ===================================================================
        # 步骤 4: 存储事件（线程安全）
        # ===================================================================
        with self._lock:
            self._events.append(event)

        # 记录日志
        logger.info(
            "Tool call recorded: agent=%s tool=%s task_id=%s note_id=%s parsed_parameters=%s",
            agent_name,
            tool_name,
            task_id,
            note_id,
            parsed_parameters,
        )

        # ===================================================================
        # 步骤 5: 实时推送（如果启用流式模式）
        # ===================================================================
        sink = self._event_sink
        if sink:
            sink(self._build_payload(event, step=None))

    # =========================================================================
    # 事件提取方法
    # =========================================================================
    def drain(self, state: SummaryState, *, step: Optional[int] = None) -> list[dict[str, Any]]:
        """
        排空工具调用事件
        
        提取自上次调用以来的所有新事件
        同时更新任务对象的笔记 ID（如果有）
        
        Args:
            state: 研究状态对象
            step: 步骤编号（用于流式模式）
            
        Returns:
            list: 事件负载列表（前端可用格式）
        """
        # ===================================================================
        # 步骤 1: 获取新事件（线程安全）
        # ===================================================================
        with self._lock:
            # 如果没有新事件，返回空列表
            if self._cursor >= len(self._events):
                return []
            # 提取从游标位置到末尾的所有事件
            new_events = self._events[self._cursor :]
            # 更新游标位置
            self._cursor = len(self._events)

        # ===================================================================
        # 步骤 2: 同步笔记 ID 到任务对象
        # ===================================================================
        if state.todo_items:
            for event in new_events:
                task_id = event.task_id
                note_id = event.note_id
                # 如果事件包含任务 ID 和笔记 ID，更新任务对象
                if task_id is None or not note_id:
                    continue
                self._attach_note_to_task(state.todo_items, task_id, note_id)

        # ===================================================================
        # 步骤 3: 转换为前端格式
        # ===================================================================
        payloads: list[dict[str, Any]] = []
        for event in new_events:
            payload = self._build_payload(event, step=step)
            payloads.append(payload)

        return payloads

    def reset(self) -> None:
        """
        重置跟踪器
        
        清空所有记录的事件和游标位置
        """
        with self._lock:
            self._events.clear()
            self._cursor = 0

    def as_dicts(self) -> list[dict[str, Any]]:
        """
        获取所有事件的字典表示
        
        返回所有事件的快照（用于向后兼容）
        
        Returns:
            list: 事件字典列表
        """
        with self._lock:
            return [
                {
                    "id": event.id,
                    "agent": event.agent,
                    "tool": event.tool,
                    "raw_parameters": event.raw_parameters,
                    "parsed_parameters": event.parsed_parameters,
                    "result": event.result,
                    "task_id": event.task_id,
                    "note_id": event.note_id,
                }
                for event in self._events
            ]

    def set_event_sink(self, sink: Optional[Callable[[dict[str, Any]], None]]) -> None:
        """
        设置事件接收器
        
        注册回调函数以接收实时工具事件通知
        用于流式模式，事件发生时立即推送
        
        Args:
            sink: 事件处理回调函数（None 表示禁用）
        """
        self._event_sink = sink

    def _build_payload(self, event: ToolCallEvent, step: Optional[int]) -> dict[str, Any]:
        """
        构建事件负载
        
        将事件对象转换为前端可用的字典格式
        
        Args:
            event: 事件对象
            step: 步骤编号（可选）
            
        Returns:
            dict: 事件负载字典
        """
        # 构建基本负载
        payload = {
            "type": "tool_call",
            "event_id": event.id,
            "agent": event.agent,
            "tool": event.tool,
            "parameters": event.parsed_parameters,
            "result": event.result,
            "task_id": event.task_id,
            "note_id": event.note_id,
        }
        
        # 如果有笔记 ID，添加笔记路径
        if event.note_id and self._notes_workspace:
            note_path = Path(self._notes_workspace) / f"{event.note_id}.md"
            payload["note_path"] = str(note_path)
        
        # 如果有步骤编号，添加到负载
        if step is not None:
            payload["step"] = step
        
        return payload

    # =========================================================================
    # 内部辅助方法
    # =========================================================================
    def _attach_note_to_task(self, tasks: list[TodoItem], task_id: int, note_id: str) -> None:
        """
        将笔记 ID 附加到任务对象
        
        更新匹配的任务对象，设置其笔记 ID 和笔记路径
        确保任务对象包含最新的笔记信息
        
        Args:
            tasks: 任务列表
            task_id: 目标任务 ID
            note_id: 笔记 ID
        """
        for task in tasks:
            # 查找匹配的任务
            if task.id != task_id:
                continue

            # 更新笔记 ID 和路径
            if task.note_id != note_id:
                task.note_id = note_id
                if self._notes_workspace:
                    task.note_path = str(Path(self._notes_workspace) / f"{note_id}.md")
            elif task.note_path is None and self._notes_workspace:
                # 如果笔记 ID 已存在但路径为空，补充路径
                task.note_path = str(Path(self._notes_workspace) / f"{note_id}.md")
            break

    def _infer_task_id(self, parameters: dict[str, Any]) -> Optional[int]:
        """
        推断任务 ID
        
        从工具调用参数中推断任务 ID
        尝试多种方式：直接字段、标签、标题
        
        Args:
            parameters: 工具调用参数
            
        Returns:
            int: 任务 ID，如果无法推断则返回 None
        """
        if not parameters:
            return None

        # 方式 1: 直接从 task_id 字段获取
        if "task_id" in parameters:
            try:
                return int(parameters["task_id"])
            except (TypeError, ValueError):
                pass

        # 方式 2: 从 tags 中提取（如 "task_1"）
        tags = parameters.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                match = re.search(r"task_(\d+)", str(tag))
                if match:
                    return int(match.group(1))

        # 方式 3: 从 title 中提取（如 "任务 1: ..."）
        title = parameters.get("title")
        if isinstance(title, str):
            match = re.search(r"任务\s*(\d+)", title)
            if match:
                return int(match.group(1))

        return None

    def _extract_note_id(self, response: str) -> Optional[str]:
        """
        从响应中提取笔记 ID
        
        笔记工具创建笔记后，响应中包含 "ID: xxx" 格式
        使用正则表达式提取笔记 ID
        
        Args:
            response: 工具调用的响应文本
            
        Returns:
            str: 笔记 ID，如果未找到则返回 None
        """
        if not response:
            return None

        # 使用正则表达式匹配 "ID: xxx" 格式
        match = re.search(r"ID:\s*([^\n]+)", response)
        if match:
            return match.group(1).strip()
        return None
