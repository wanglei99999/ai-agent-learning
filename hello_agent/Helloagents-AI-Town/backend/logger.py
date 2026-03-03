"""
对话日志系统模块

提供结构化的对话日志记录功能
记录 NPC 对话的完整流程，包括好感度变化、记忆检索等
日志同时输出到文件和控制台，便于调试和分析
"""

import logging
import os
from datetime import datetime
from pathlib import Path

# ===================================================================
# 日志配置
# ===================================================================

# 创建日志存储目录
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 创建日志文件名（按日期分割，每天一个日志文件）
today = datetime.now().strftime("%Y-%m-%d")
LOG_FILE = LOGS_DIR / f"dialogue_{today}.log"

# 配置日志格式
LOG_FORMAT = "%(asctime)s - %(message)s"  # 时间戳 + 消息内容
DATE_FORMAT = "%H:%M:%S"  # 只显示时分秒

# 创建专用的对话日志记录器
dialogue_logger = logging.getLogger("dialogue")
dialogue_logger.setLevel(logging.INFO)  # 设置日志级别为 INFO

# 移除已有的 handlers（避免重复添加）
dialogue_logger.handlers.clear()

# 创建文件 handler（将日志写入文件）
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# 创建控制台 handler（将日志输出到控制台）
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# 添加两个 handlers 到 logger
# 这样日志会同时输出到文件和控制台
dialogue_logger.addHandler(file_handler)
dialogue_logger.addHandler(console_handler)

# 防止日志传播到 root logger（避免重复输出）
dialogue_logger.propagate = False

# ===================================================================
# 日志记录函数
# ===================================================================
# 这些函数在 agents.py 的 chat 方法中被调用
# 用于记录对话处理的各个步骤

def log_dialogue_start(npc_name: str, player_message: str):
    """
    记录对话开始
    
    在对话处理流程开始时调用，标记新对话的开始
    
    Args:
        npc_name: NPC 名称
        player_message: 玩家发送的消息
    """
    dialogue_logger.info("=" * 60)
    dialogue_logger.info(f"对话开始: {npc_name} <-> 玩家")
    dialogue_logger.info("=" * 60)
    dialogue_logger.info(f"玩家消息: {player_message}")

def log_affinity(npc_name: str, affinity: float, level: str):
    """
    记录当前好感度
    
    在对话开始时记录 NPC 对玩家的当前好感度
    
    Args:
        npc_name: NPC 名称
        affinity: 好感度值（0-100）
        level: 关系等级（如 "友好"、"熟悉" 等）
    """
    dialogue_logger.info(f"当前好感度: {affinity:.1f}/100 ({level})")

def log_memory_retrieval(npc_name: str, count: int, memories: list = None):
    """
    记录记忆检索结果
    
    记录从记忆系统中检索到的相关历史对话
    
    Args:
        npc_name: NPC 名称
        count: 检索到的记忆数量
        memories: 记忆列表（可选，用于显示详细内容）
    """
    dialogue_logger.info(f"检索到{count}条相关记忆")
    if memories:
        dialogue_logger.info("  相关记忆:")
        # 只显示前 3 条记忆的摘要
        for i, mem in enumerate(memories[:3], 1):
            # 如果内容太长，截断并添加省略号
            content = mem.content[:50] + "..." if len(mem.content) > 50 else mem.content
            dialogue_logger.info(f"    {i}. {content}")

def log_generating_response():
    """
    记录正在生成回复
    
    在调用 LLM 生成回复之前调用
    """
    dialogue_logger.info("正在生成回复...")

def log_npc_response(npc_name: str, response: str):
    """
    记录 NPC 的回复内容
    
    Args:
        npc_name: NPC 名称
        response: NPC 生成的回复内容
    """
    dialogue_logger.info(f"{npc_name}回复: {response}")

def log_analyzing_affinity():
    """
    记录正在分析好感度
    
    在调用好感度分析 Agent 之前调用
    """
    dialogue_logger.info("正在分析好感度变化...")

def log_affinity_change(affinity_result: dict):
    """
    记录好感度变化详情
    
    记录好感度分析的结果，包括变化量、原因、情感倾向等
    
    Args:
        affinity_result: 好感度分析结果字典
            - changed: 是否发生变化
            - old_affinity: 旧的好感度值
            - new_affinity: 新的好感度值
            - change_amount: 变化量
            - reason: 变化原因
            - sentiment: 情感倾向
            - old_level: 旧的关系等级
            - new_level: 新的关系等级
    """
    if affinity_result.get("changed"):
        # 根据变化方向选择符号
        change_symbol = "↑" if affinity_result["change_amount"] > 0 else "↓"
        dialogue_logger.info(
            f"{change_symbol} 好感度变化: {affinity_result['old_affinity']:.1f} -> "
            f"{affinity_result['new_affinity']:.1f} ({affinity_result['change_amount']:+.1f})"
        )
        dialogue_logger.info(f"  原因: {affinity_result['reason']}")
        dialogue_logger.info(f"  情感: {affinity_result['sentiment']}")
        
        # 如果关系等级发生变化，特别标记
        if affinity_result['old_level'] != affinity_result['new_level']:
            dialogue_logger.info(
                f"  关系等级变化: {affinity_result['old_level']} -> {affinity_result['new_level']}"
            )
    else:
        # 好感度未变化
        dialogue_logger.info(f"  好感度未变化 (当前: {affinity_result.get('affinity', 50.0):.1f})")
        dialogue_logger.info(f"  原因: {affinity_result.get('reason', '无')}")

def log_memory_saved(npc_name: str):
    """
    记录记忆保存
    
    在对话保存到记忆系统后调用
    
    Args:
        npc_name: NPC 名称
    """
    dialogue_logger.info(f"  对话已保存到{npc_name}的记忆中")

def log_dialogue_end():
    """
    记录对话结束
    
    在对话处理流程完成时调用，标记对话结束
    """
    dialogue_logger.info("=" * 60)
    dialogue_logger.info("对话完成\n")

def log_info(message: str):
    """
    记录普通信息
    
    通用的信息日志记录函数
    
    Args:
        message: 要记录的消息
    """
    dialogue_logger.info(message)

def log_error(message: str):
    """
    记录错误信息
    
    用于记录错误和异常情况
    
    Args:
        message: 错误消息
    """
    dialogue_logger.error(message)

# ===================================================================
# 启动提示
# ===================================================================
# 在模块加载时输出日志文件位置，方便查看日志
print(f"\n对话日志文件: {LOG_FILE}")
print(f"日志目录: {LOGS_DIR}\n")

