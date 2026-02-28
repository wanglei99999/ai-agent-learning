"""
规划服务模块

负责将研究主题转换为可执行的任务列表
调用 TODO Agent 生成结构化的研究任务

核心功能：
1. 调用 TODO Agent 生成任务列表
2. 解析 Agent 响应（支持 JSON 和工具调用格式）
3. 创建 TodoItem 对象
4. 提供降级方案（如果规划失败）
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional

from hello_agents import ToolAwareSimpleAgent

from models import SummaryState, TodoItem
from config import Configuration
from prompts import get_current_date, todo_planner_instructions
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)

# 工具调用模式的正则表达式
# 匹配格式：[TOOL_CALL:tool_name:{json_body}]
TOOL_CALL_PATTERN = re.compile(
    r"\[TOOL_CALL:(?P<tool>[^:]+):(?P<body>[^\]]+)\]",
    re.IGNORECASE,
)

class PlanningService:
    """
    规划服务类
    
    封装 TODO Agent，负责生成结构化的研究任务列表
    处理 Agent 响应的解析和任务对象的创建
    
    Attributes:
        _agent: TODO Agent 实例
        _config: 配置对象
    """

    def __init__(self, planner_agent: ToolAwareSimpleAgent, config: Configuration) -> None:
        """
        初始化规划服务
        
        Args:
            planner_agent: TODO Agent 实例
            config: 配置对象
        """
        self._agent = planner_agent
        self._config = config

    def plan_todo_list(self, state: SummaryState) -> List[TodoItem]:
        """
        生成 TODO 任务列表
        
        调用 TODO Agent 将研究主题分解为具体的可执行任务
        解析 Agent 响应并创建 TodoItem 对象列表
        
        Args:
            state: 研究状态对象
            
        Returns:
            List[TodoItem]: 任务列表
        """
        # ===================================================================
        # 步骤 1: 准备提示词并调用 Agent
        # ===================================================================
        # 填充提示词模板（当前日期和研究主题）
        prompt = todo_planner_instructions.format(
            current_date=get_current_date(),
            research_topic=state.research_topic,
        )

        # 调用 TODO Agent 生成任务列表
        response = self._agent.run(prompt)
        # 清空对话历史，避免影响后续调用
        self._agent.clear_history()

        logger.info("Planner raw output (truncated): %s", response[:500])

        # ===================================================================
        # 步骤 2: 解析 Agent 响应
        # ===================================================================
        tasks_payload = self._extract_tasks(response)
        todo_items: List[TodoItem] = []

        # ===================================================================
        # 步骤 3: 创建 TodoItem 对象
        # ===================================================================
        for idx, item in enumerate(tasks_payload, start=1):
            # 提取任务字段，提供默认值
            title = str(item.get("title") or f"任务{idx}").strip()
            intent = str(item.get("intent") or "聚焦主题的关键问题").strip()
            query = str(item.get("query") or state.research_topic).strip()

            # 确保查询不为空
            if not query:
                query = state.research_topic

            # 创建任务对象
            task = TodoItem(
                id=idx,
                title=title,
                intent=intent,
                query=query,
            )
            todo_items.append(task)

        # 更新状态对象
        state.todo_items = todo_items

        # 记录生成的任务
        titles = [task.title for task in todo_items]
        logger.info("Planner produced %d tasks: %s", len(todo_items), titles)
        return todo_items

    @staticmethod
    def create_fallback_task(state: SummaryState) -> TodoItem:
        """
        创建降级任务
        
        当 TODO Agent 无法生成任务列表时，创建一个默认的基础任务
        确保研究流程可以继续进行
        
        Args:
            state: 研究状态对象
            
        Returns:
            TodoItem: 默认任务对象
        """
        return TodoItem(
            id=1,
            title="基础背景梳理",
            intent="收集主题的核心背景与最新动态",
            query=f"{state.research_topic} 最新进展" if state.research_topic else "基础背景梳理",
        )

    # =========================================================================
    # 解析辅助方法
    # 支持多种响应格式：JSON 对象、JSON 数组、工具调用格式
    # =========================================================================
    def _extract_tasks(self, raw_response: str) -> List[dict[str, Any]]:
        """
        从 Agent 响应中提取任务列表
        
        支持多种格式：
        1. JSON 对象：{"tasks": [...]}
        2. JSON 数组：[{...}, {...}]
        3. 工具调用：[TOOL_CALL:note:{"tasks": [...]}]
        
        Args:
            raw_response: Agent 的原始响应
            
        Returns:
            List[dict]: 任务字典列表
        """
        # 清理响应文本
        text = raw_response.strip()
        
        # 移除思考标记（如果配置启用）
        if self._config.strip_thinking_tokens:
            text = strip_thinking_tokens(text)

        # 尝试提取 JSON 格式的任务
        json_payload = self._extract_json_payload(text)
        tasks: List[dict[str, Any]] = []

        # 处理 JSON 对象格式：{"tasks": [...]}
        if isinstance(json_payload, dict):
            candidate = json_payload.get("tasks")
            if isinstance(candidate, list):
                for item in candidate:
                    if isinstance(item, dict):
                        tasks.append(item)
        # 处理 JSON 数组格式：[{...}, {...}]
        elif isinstance(json_payload, list):
            for item in json_payload:
                if isinstance(item, dict):
                    tasks.append(item)

        # 如果 JSON 解析失败，尝试工具调用格式
        if not tasks:
            tool_payload = self._extract_tool_payload(text)
            if tool_payload and isinstance(tool_payload.get("tasks"), list):
                for item in tool_payload["tasks"]:
                    if isinstance(item, dict):
                        tasks.append(item)

        return tasks

    def _extract_json_payload(self, text: str) -> Optional[dict[str, Any] | list]:
        """
        从文本中提取 JSON 对象或数组
        
        查找文本中的 JSON 结构并解析
        优先尝试对象格式 {...}，然后尝试数组格式 [...]
        
        Args:
            text: 包含 JSON 的文本
            
        Returns:
            dict | list: 解析后的 JSON，如果解析失败则返回 None
        """
        # 尝试提取 JSON 对象 {...}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass  # 继续尝试数组格式

        # 尝试提取 JSON 数组 [...]
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None

        return None

    def _extract_tool_payload(self, text: str) -> Optional[dict[str, Any]]:
        """
        解析工具调用格式
        
        从文本中提取 [TOOL_CALL:tool_name:{...}] 格式的内容
        支持 JSON 格式和键值对格式
        
        Args:
            text: 包含工具调用的文本
            
        Returns:
            dict: 工具调用的参数字典，如果解析失败则返回 None
        """
        # 使用正则表达式匹配工具调用
        match = TOOL_CALL_PATTERN.search(text)
        if not match:
            return None

        # 提取工具调用的 body 部分
        body = match.group("body")

        # 尝试解析为 JSON 格式
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass  # 继续尝试键值对格式

        # 尝试解析为键值对格式：key1=value1, key2=value2
        parts = [segment.strip() for segment in body.split(",") if segment.strip()]
        payload: dict[str, Any] = {}
        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            # 移除引号
            payload[key.strip()] = value.strip().strip('"').strip("'")

        return payload or None
