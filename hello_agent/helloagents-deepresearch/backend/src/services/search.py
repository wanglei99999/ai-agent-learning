"""
搜索服务模块

负责执行网络搜索并处理搜索结果
使用 HelloAgents 的 SearchTool 支持多种搜索引擎

核心功能：
1. 调度搜索请求到配置的搜索引擎
2. 规范化搜索响应格式
3. 准备研究上下文（去重、格式化）
4. 处理搜索通知和错误
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from hello_agents.tools import SearchTool

from config import Configuration
from utils import (
    deduplicate_and_format_sources,
    format_sources,
    get_config_value,
)

logger = logging.getLogger(__name__)

# 每个搜索结果的最大 token 数量
# 限制单个来源的内容长度，避免上下文过长
MAX_TOKENS_PER_SOURCE = 2000

# 全局搜索工具实例
# 使用 hybrid 后端，支持多种搜索引擎的自动切换
_GLOBAL_SEARCH_TOOL = SearchTool(backend="hybrid")


def dispatch_search(
    query: str,
    config: Configuration,
    loop_count: int,
) -> Tuple[dict[str, Any] | None, list[str], Optional[str], str]:
    """
    执行搜索并规范化响应
    
    调用配置的搜索引擎执行搜索，处理响应并提取关键信息
    支持多种搜索后端：DuckDuckGo、Perplexity、Tavily 等
    
    Args:
        query: 搜索查询字符串
        config: 配置对象（包含搜索引擎选择）
        loop_count: 当前研究循环计数（用于日志）
        
    Returns:
        tuple: (搜索结果字典, 通知列表, AI答案文本, 后端标签)
            - 搜索结果字典: {"results": [...], "backend": "...", "answer": "..."}
            - 通知列表: 搜索过程中的警告或提示
            - AI答案文本: 某些搜索引擎提供的直接答案
            - 后端标签: 实际使用的搜索引擎名称
    """

    # 获取配置的搜索引擎（如 "duckduckgo", "perplexity" 等）
    search_api = get_config_value(config.search_api)

    # ===================================================================
    # 执行搜索
    # ===================================================================
    try:
        raw_response = _GLOBAL_SEARCH_TOOL.run(
            {
                "input": query,                              # 搜索查询
                "backend": search_api,                       # 搜索引擎
                "mode": "structured",                        # 结构化模式（返回 JSON）
                "fetch_full_page": config.fetch_full_page,  # 是否获取完整页面
                "max_results": 5,                            # 最多返回 5 个结果
                "max_tokens_per_source": MAX_TOKENS_PER_SOURCE,  # 每个来源的最大 token 数
                "loop_count": loop_count,                    # 循环计数（用于日志）
            }
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        # 搜索失败，记录错误并抛出异常
        logger.exception("Search backend %s failed: %s", search_api, exc)
        raise

    # ===================================================================
    # 处理搜索响应
    # ===================================================================
    if isinstance(raw_response, str):
        # 如果响应是字符串（通常是错误或警告消息）
        notices = [raw_response]
        logger.warning("Search backend %s returned text notice: %s", search_api, raw_response)
        # 构建空结果的标准格式
        payload: dict[str, Any] = {
            "results": [],
            "backend": search_api,
            "answer": None,
            "notices": notices,
        }
    else:
        # 正常的字典响应
        payload = raw_response
        notices = list(payload.get("notices") or [])

    # ===================================================================
    # 提取关键信息
    # ===================================================================
    backend_label = str(payload.get("backend") or search_api)  # 实际使用的后端
    answer_text = payload.get("answer")                        # AI 直接答案（某些引擎提供）
    results = payload.get("results", [])                       # 搜索结果列表

    # 记录搜索通知（如果有）
    if notices:
        for notice in notices:
            logger.info("Search notice (%s): %s", backend_label, notice)

    # 记录搜索摘要
    logger.info(
        "Search backend=%s resolved_backend=%s answer=%s results=%s",
        search_api,
        backend_label,
        bool(answer_text),
        len(results),
    )

    # 返回搜索结果和元信息
    return payload, notices, answer_text, backend_label


def prepare_research_context(
    search_result: dict[str, Any] | None,
    answer_text: Optional[str],
    config: Configuration,
) -> tuple[str, str]:
    """
    准备研究上下文
    
    将搜索结果处理为结构化的上下文，供 Summarizer Agent 使用
    包括去重、格式化、添加 AI 答案等处理
    
    Args:
        search_result: 搜索结果字典
        answer_text: AI 直接答案（可选）
        config: 配置对象
        
    Returns:
        tuple: (来源摘要, 完整上下文)
            - 来源摘要: 简短的来源列表（标题 + URL）
            - 完整上下文: 详细的搜索结果内容（用于 Agent 分析）
    """
    # ===================================================================
    # 步骤 1: 格式化来源摘要
    # ===================================================================
    # 生成简短的来源列表（标题 + URL）
    sources_summary = format_sources(search_result)
    
    # ===================================================================
    # 步骤 2: 构建详细上下文
    # ===================================================================
    # 去重并格式化搜索结果，生成详细的上下文内容
    context = deduplicate_and_format_sources(
        search_result or {"results": []},
        max_tokens_per_source=MAX_TOKENS_PER_SOURCE,
        fetch_full_page=config.fetch_full_page,
    )

    # ===================================================================
    # 步骤 3: 添加 AI 直接答案（如果有）
    # ===================================================================
    # 某些搜索引擎（如 Perplexity）会提供 AI 生成的直接答案
    if answer_text:
        context = f"AI直接答案：\n{answer_text}\n\n{context}"

    return sources_summary, context
