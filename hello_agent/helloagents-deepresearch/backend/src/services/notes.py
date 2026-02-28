"""
笔记协作辅助模块

负责生成笔记工具的使用指导
为 Agent 提供如何使用笔记工具的详细说明

核心功能：
1. 生成笔记工具调用示例
2. 区分创建和更新两种场景
3. 提供笔记协作指引
4. 确保 Agent 间的信息同步
"""

from __future__ import annotations

import json

from models import TodoItem


def build_note_guidance(task: TodoItem) -> str:
    """
    构建笔记协作指引
    
    为特定任务生成笔记工具的使用指导
    根据任务是否已有笔记，生成不同的指导内容
    
    Args:
        task: 任务对象
        
    Returns:
        str: 笔记协作指引文本（包含工具调用示例）
    """
    # 准备笔记标签（用于笔记分类和查找）
    tags_list = ["deep_research", f"task_{task.id}"]
    tags_literal = json.dumps(tags_list, ensure_ascii=False)

    # ===================================================================
    # 场景 1：任务已有笔记（更新模式）
    # ===================================================================
    if task.note_id:
        # 准备读取笔记的工具调用示例
        read_payload = json.dumps({"action": "read", "note_id": task.note_id}, ensure_ascii=False)
        
        # 准备更新笔记的工具调用示例
        update_payload = json.dumps(
            {
                "action": "update",
                "note_id": task.note_id,
                "task_id": task.id,
                "title": f"任务 {task.id}: {task.title}",
                "note_type": "task_state",
                "tags": tags_list,
                "content": "请将本轮新增信息补充到任务概览中",
            },
            ensure_ascii=False,
        )

        # 返回更新模式的指引
        return (
            "笔记协作指引：\n"
            f"- 当前任务笔记 ID：{task.note_id}。\n"
            f"- 在书写总结前必须调用：[TOOL_CALL:note:{read_payload}] 获取最新内容。\n"
            f"- 完成分析后调用：[TOOL_CALL:note:{update_payload}] 同步增量信息。\n"
            "- 更新时保持原有段落结构，新增内容请在对应段落中补充。\n"
            f"- 建议 tags 保持为 {tags_literal}，保证其他 Agent 可快速定位。\n"
            "- 成功同步到笔记后，再输出面向用户的总结。\n"
        )

    # ===================================================================
    # 场景 2：任务还没有笔记（创建模式）
    # ===================================================================
    # 准备创建笔记的工具调用示例
    create_payload = json.dumps(
        {
            "action": "create",
            "task_id": task.id,
            "title": f"任务 {task.id}: {task.title}",
            "note_type": "task_state",
            "tags": tags_list,
            "content": "请记录任务概览、来源概览",
        },
        ensure_ascii=False,
    )

    # 返回创建模式的指引
    return (
        "笔记协作指引：\n"
        f"- 当前任务尚未建立笔记，请先调用：[TOOL_CALL:note:{create_payload}]。\n"
        "- 创建成功后记录返回的 note_id，并在后续所有更新中复用。\n"
        "- 同步笔记后，再输出面向用户的总结。\n"
    )

