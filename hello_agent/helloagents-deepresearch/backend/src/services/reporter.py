"""
报告生成服务模块

负责整合所有任务结果，生成最终的结构化研究报告
调用 Report Agent 将任务总结汇总为完整报告

核心功能：
1. 整合所有任务的总结和来源
2. 准备报告生成的上下文
3. 调用 Report Agent 生成报告
4. 清理报告文本（移除工具调用标记）
"""

from __future__ import annotations

import json

from hello_agents import ToolAwareSimpleAgent

from models import SummaryState
from config import Configuration
from utils import strip_thinking_tokens
from services.text_processing import strip_tool_calls


class ReportingService:
    """
    报告生成服务类
    
    封装 Report Agent，负责生成最终的研究报告
    整合所有任务的总结、来源和笔记信息
    
    Attributes:
        _agent: Report Agent 实例
        _config: 配置对象
    """

    def __init__(self, report_agent: ToolAwareSimpleAgent, config: Configuration) -> None:
        """
        初始化报告生成服务
        
        Args:
            report_agent: Report Agent 实例
            config: 配置对象
        """
        self._agent = report_agent
        self._config = config

    def generate_report(self, state: SummaryState) -> str:
        """
        生成最终研究报告
        
        整合所有任务的总结、来源和笔记信息
        调用 Report Agent 生成结构化的研究报告
        
        Args:
            state: 研究状态对象（包含所有任务信息）
            
        Returns:
            str: 最终研究报告（Markdown 格式）
        """
        # ===================================================================
        # 步骤 1: 整合所有任务信息
        # ===================================================================
        tasks_block = []
        for task in state.todo_items:
            # 提取任务的总结和来源，提供默认值
            summary_block = task.summary or "暂无可用信息"
            sources_block = task.sources_summary or "暂无来源"
            
            # 构建任务信息块（Markdown 格式）
            tasks_block.append(
                f"### 任务 {task.id}: {task.title}\n"
                f"- 任务目标：{task.intent}\n"
                f"- 检索查询：{task.query}\n"
                f"- 执行状态：{task.status}\n"
                f"- 任务总结：\n{summary_block}\n"
                f"- 来源概览：\n{sources_block}\n"
            )

        # ===================================================================
        # 步骤 2: 收集笔记引用信息
        # ===================================================================
        note_references = []
        for task in state.todo_items:
            # 如果任务有关联的笔记，添加到引用列表
            if task.note_id:
                note_references.append(
                    f"- 任务 {task.id}《{task.title}》：note_id={task.note_id}"
                )

        # 构建笔记引用部分
        notes_section = "\n".join(note_references) if note_references else "- 暂无可用任务笔记"

        # ===================================================================
        # 步骤 3: 准备工具调用模板（供 Agent 参考）
        # ===================================================================
        # 读取笔记的工具调用模板
        read_template = json.dumps({"action": "read", "note_id": "<note_id>"}, ensure_ascii=False)
        
        # 创建结论笔记的工具调用模板
        create_conclusion_template = json.dumps(
            {
                "action": "create",
                "title": f"研究报告：{state.research_topic}",
                "note_type": "conclusion",
                "tags": ["deep_research", "report"],
                "content": "请在此沉淀最终报告要点",
            },
            ensure_ascii=False,
        )

        # ===================================================================
        # 步骤 4: 构建 Report Agent 的提示词
        # ===================================================================
        # 将所有信息整合到提示词中
        prompt = (
            f"研究主题：{state.research_topic}\n"
            f"任务概览：\n{''.join(tasks_block)}\n"
            f"可用任务笔记：\n{notes_section}\n"
            f"请针对每条任务笔记使用格式：[TOOL_CALL:note:{read_template}] 读取内容，整合所有信息后撰写报告。\n"
            f"如需输出汇总结论，可追加调用：[TOOL_CALL:note:{create_conclusion_template}] 保存报告要点。"
        )

        # ===================================================================
        # 步骤 5: 调用 Report Agent 生成报告
        # ===================================================================
        response = self._agent.run(prompt)
        # 清空对话历史
        self._agent.clear_history()

        # ===================================================================
        # 步骤 6: 清理报告文本
        # ===================================================================
        report_text = response.strip()
        
        # 移除思考标记（如果配置启用）
        if self._config.strip_thinking_tokens:
            report_text = strip_thinking_tokens(report_text)

        # 移除工具调用标记（[TOOL_CALL:...]）
        report_text = strip_tool_calls(report_text).strip()

        # 返回最终报告
        return report_text or "报告生成失败，请检查输入。"

