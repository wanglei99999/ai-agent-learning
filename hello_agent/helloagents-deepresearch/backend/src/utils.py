"""
工具函数模块

本模块提供深度研究服务共享的工具函数
类似 Java 的 Utils 或 Helper 类

主要功能：
1. 配置值转换
2. 思考标记移除（某些 LLM 会输出 <think> 标签）
3. 搜索结果去重和格式化
4. 来源信息格式化

Java 对比：
- 工具函数 → static 方法的工具类
- 无直接对应 → Java 通常用专门的工具类
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Union

# =============================================================================
# 常量定义
# =============================================================================
CHARS_PER_TOKEN = 4  # 每个 token 约等于 4 个字符（用于估算）

logger = logging.getLogger(__name__)


# =============================================================================
# 配置相关工具函数
# =============================================================================
def get_config_value(value: Any) -> str:
    """
    获取配置值的字符串表示
    
    处理枚举类型和字符串类型的配置值
    类似 Java: ConfigUtils.getStringValue()
    
    Args:
        value: 配置值（可能是字符串或枚举）
        
    Returns:
        str: 配置值的字符串表示
    """
    return value if isinstance(value, str) else value.value


# =============================================================================
# 文本处理工具函数
# =============================================================================
def strip_thinking_tokens(text: str) -> str:
    """
    移除思考标记
    
    某些 LLM（如 DeepSeek）会在响应中输出 <think>...</think> 标签
    这些标签包含模型的思考过程，需要在返回给用户前移除
    
    类似 Java: StringUtils.removeThinkingTags()
    
    Args:
        text: 包含思考标记的文本
        
    Returns:
        str: 移除思考标记后的文本
        
    Example:
        输入: "答案是<think>让我想想</think>42"
        输出: "答案是42"
    """
    # 循环移除所有 <think>...</think> 标签
    while "<think>" in text and "</think>" in text:
        start = text.find("<think>")
        end = text.find("</think>") + len("</think>")
        text = text[:start] + text[end:]
    return text


# =============================================================================
# 搜索结果处理工具函数
# =============================================================================
def deduplicate_and_format_sources(
    search_response: Dict[str, Any] | List[Dict[str, Any]],
    max_tokens_per_source: int,
    *,
    fetch_full_page: bool = False,
) -> str:
    """
    去重并格式化搜索结果
    
    将搜索引擎返回的结果去重、格式化为适合 LLM 处理的文本
    类似 Java: SearchResultFormatter.format()
    
    Args:
        search_response: 搜索响应（字典或列表）
        max_tokens_per_source: 每个来源的最大 token 数
        fetch_full_page: 是否包含完整页面内容
        
    Returns:
        str: 格式化后的来源文本
        
    处理流程：
    1. 提取搜索结果列表
    2. 按 URL 去重
    3. 格式化每个来源（标题、URL、内容）
    4. 如果启用，添加完整页面内容（截断到限制长度）
    """

    # ===================================================================
    # 步骤 1: 提取搜索结果列表
    # ===================================================================
    if isinstance(search_response, dict):
        sources_list = search_response.get("results", [])
    else:
        sources_list = search_response

    # ===================================================================
    # 步骤 2: 按 URL 去重
    # ===================================================================
    unique_sources: dict[str, Dict[str, Any]] = {}
    for source in sources_list:
        url = source.get("url")
        if not url:
            continue  # 跳过没有 URL 的结果
        if url not in unique_sources:
            unique_sources[url] = source  # 只保留第一次出现的 URL

    # ===================================================================
    # 步骤 3: 格式化每个来源
    # ===================================================================
    formatted_parts: List[str] = []
    for source in unique_sources.values():
        # 提取标题（如果没有标题，使用 URL）
        title = source.get("title") or source.get("url", "")
        content = source.get("content", "")
        
        # 格式化基本信息
        formatted_parts.append(f"信息来源: {title}\n\n")
        formatted_parts.append(f"URL: {source.get('url', '')}\n\n")
        formatted_parts.append(f"信息内容: {content}\n\n")

        # ===================================================================
        # 步骤 4: 如果启用，添加完整页面内容
        # ===================================================================
        if fetch_full_page:
            raw_content = source.get("raw_content")
            if raw_content is None:
                logger.debug("raw_content missing for %s", source.get("url", ""))
                raw_content = ""
            
            # 计算字符限制（token 数 * 每个 token 的字符数）
            char_limit = max_tokens_per_source * CHARS_PER_TOKEN
            
            # 如果内容超过限制，截断并添加提示
            if len(raw_content) > char_limit:
                raw_content = f"{raw_content[:char_limit]}... [truncated]"
            
            formatted_parts.append(
                f"详细信息内容限制为 {max_tokens_per_source} 个 token: {raw_content}\n\n"
            )

    # 合并所有部分并返回
    return "".join(formatted_parts).strip()


def format_sources(search_results: Dict[str, Any] | None) -> str:
    """
    格式化来源列表
    
    将搜索结果格式化为简洁的项目符号列表
    用于在报告中显示参考来源
    
    类似 Java: SourceFormatter.formatAsBulletList()
    
    Args:
        search_results: 搜索结果字典
        
    Returns:
        str: 格式化的来源列表（每行一个来源）
        
    Example:
        输出格式：
        * 标题1 : https://example.com/1
        * 标题2 : https://example.com/2
    """

    # 如果没有搜索结果，返回空字符串
    if not search_results:
        return ""

    # 提取结果列表
    results = search_results.get("results", [])
    
    # 格式化为项目符号列表
    # 格式：* 标题 : URL
    return "\n".join(
        f"* {item.get('title', item.get('url', ''))} : {item.get('url', '')}"
        for item in results
        if item.get("url")  # 只包含有 URL 的结果
    )
