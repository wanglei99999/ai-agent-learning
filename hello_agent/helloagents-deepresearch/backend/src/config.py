"""
配置管理模块

本模块定义深度研究助手的所有配置选项
类似 Java Spring 的 @ConfigurationProperties

主要功能：
1. 定义搜索 API 枚举
2. 定义配置类（LLM、搜索、笔记等）
3. 从环境变量加载配置
4. 提供配置验证和转换

Java 对比：
- Configuration → @ConfigurationProperties 配置类
- from_env() → @Value 注解读取环境变量
- SearchAPI → enum 枚举类
"""

import os
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

# =============================================================================
# 搜索 API 枚举
# 定义支持的搜索引擎类型
# =============================================================================
class SearchAPI(Enum):
    """
    搜索 API 枚举类
    
    定义支持的网络搜索引擎
    类似 Java: public enum SearchAPI { ... }
    """
    PERPLEXITY = "perplexity"    # Perplexity AI 搜索
    TAVILY = "tavily"            # Tavily 搜索 API
    DUCKDUCKGO = "duckduckgo"    # DuckDuckGo 搜索
    SEARXNG = "searxng"          # SearXNG 元搜索引擎
    ADVANCED = "advanced"        # 高级搜索模式


# =============================================================================
# 配置类
# 管理所有应用配置，类似 Java Spring 的 @ConfigurationProperties
# =============================================================================
class Configuration(BaseModel):
    """
    深度研究助手配置类
    
    使用 Pydantic BaseModel 实现配置管理
    支持从环境变量加载、默认值、类型验证
    
    """

    # =========================================================================
    # 研究深度配置
    # =========================================================================
    max_web_research_loops: int = Field(
        default=3,
        title="Research Depth",
        description="Number of research iterations to perform",
    )  # 最大研究迭代次数（默认 3 轮）
    # =========================================================================
    # LLM 配置
    # =========================================================================
    local_llm: str = Field(
        default="llama3.2",
        title="Local Model Name",
        description="Name of the locally hosted LLM (Ollama/LMStudio)",
    )  # 本地 LLM 模型名称
    
    llm_provider: str = Field(
        default="ollama",
        title="LLM Provider",
        description="Provider identifier (ollama, lmstudio, or custom)",
    )  # LLM 提供商（ollama/lmstudio/自定义）
    # =========================================================================
    # 搜索 API 配置
    # =========================================================================
    search_api: SearchAPI = Field(
        default=SearchAPI.DUCKDUCKGO,
        title="Search API",
        description="Web search API to use",
    )  # 使用的搜索引擎（默认 DuckDuckGo）
    # =========================================================================
    # 笔记工具配置
    # =========================================================================
    enable_notes: bool = Field(
        default=True,
        title="Enable Notes",
        description="Whether to store task progress in NoteTool",
    )  # 是否启用笔记工具（用于保存研究进度）
    
    notes_workspace: str = Field(
        default="./notes",
        title="Notes Workspace",
        description="Directory for NoteTool to persist task notes",
    )  # 笔记存储目录
    # =========================================================================
    # 搜索行为配置
    # =========================================================================
    fetch_full_page: bool = Field(
        default=True,
        title="Fetch Full Page",
        description="Include the full page content in the search results",
    )  # 是否获取完整页面内容
    # =========================================================================
    # LLM 服务端点配置
    # =========================================================================
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        title="Ollama Base URL",
        description="Base URL for Ollama API (without /v1 suffix)",
    )  # Ollama API 地址
    
    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1",
        title="LMStudio Base URL",
        description="Base URL for LMStudio OpenAI-compatible API",
    )  # LMStudio API 地址
    # =========================================================================
    # LLM 行为配置
    # =========================================================================
    strip_thinking_tokens: bool = Field(
        default=True,
        title="Strip Thinking Tokens",
        description="Whether to strip <think> tokens from model responses",
    )  # 是否移除思考标记（某些模型会输出 <think> 标签）
    
    use_tool_calling: bool = Field(
        default=False,
        title="Use Tool Calling",
        description="Use tool calling instead of JSON mode for structured output",
    )  # 是否使用工具调用模式（而非 JSON 模式）
    # =========================================================================
    # 自定义 LLM 配置（可选）
    # =========================================================================
    llm_api_key: Optional[str] = Field(
        default=None,
        title="LLM API Key",
        description="Optional API key when using custom OpenAI-compatible services",
    )  # LLM API 密钥（可选）
    
    llm_base_url: Optional[str] = Field(
        default=None,
        title="LLM Base URL",
        description="Optional base URL when using custom OpenAI-compatible services",
    )  # LLM 基础 URL（可选）
    
    llm_model_id: Optional[str] = Field(
        default=None,
        title="LLM Model ID",
        description="Optional model identifier for custom OpenAI-compatible services",
    )  # LLM 模型 ID（可选）

    # =========================================================================
    # 配置加载方法
    # =========================================================================
    @classmethod
    def from_env(cls, overrides: Optional[dict[str, Any]] = None) -> "Configuration":
        """
        从环境变量创建配置对象
        
        
        Args:
            overrides: 覆盖配置字典（可选）
            
        Returns:
            Configuration: 配置对象实例
        """

        raw_values: dict[str, Any] = {}

        # ===================================================================
        # 1. 从环境变量加载配置（基于字段名自动映射）
        # ===================================================================
        for field_name in cls.model_fields.keys():
            env_key = field_name.upper()  # 字段名转大写作为环境变量名
            if env_key in os.environ:
                raw_values[field_name] = os.environ[env_key]

        # ===================================================================
        # 2. 显式环境变量映射（支持特定的环境变量名）
        # ===================================================================
        env_aliases = {
            "local_llm": os.getenv("LOCAL_LLM"),
            "llm_provider": os.getenv("LLM_PROVIDER"),
            "llm_api_key": os.getenv("LLM_API_KEY"),
            "llm_model_id": os.getenv("LLM_MODEL_ID"),
            "llm_base_url": os.getenv("LLM_BASE_URL"),
            "lmstudio_base_url": os.getenv("LMSTUDIO_BASE_URL"),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL"),
            "max_web_research_loops": os.getenv("MAX_WEB_RESEARCH_LOOPS"),
            "fetch_full_page": os.getenv("FETCH_FULL_PAGE"),
            "strip_thinking_tokens": os.getenv("STRIP_THINKING_TOKENS"),
            "use_tool_calling": os.getenv("USE_TOOL_CALLING"),
            "search_api": os.getenv("SEARCH_API"),
            "enable_notes": os.getenv("ENABLE_NOTES"),
            "notes_workspace": os.getenv("NOTES_WORKSPACE"),
        }

        # 合并显式映射的环境变量
        for key, value in env_aliases.items():
            if value is not None:
                raw_values.setdefault(key, value)

        # ===================================================================
        # 3. 应用覆盖配置（优先级最高）
        # ===================================================================
        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    raw_values[key] = value

        # 创建并返回配置对象
        return cls(**raw_values)

    # =========================================================================
    # 工具方法
    # =========================================================================
    def sanitized_ollama_url(self) -> str:
        """
        规范化 Ollama URL
        
        确保 URL 包含 /v1 后缀（OpenAI 客户端要求）
        
        Returns:
            str: 规范化的 URL
        """
        base = self.ollama_base_url.rstrip("/")  # 移除尾部斜杠
        if not base.endswith("/v1"):
            base = f"{base}/v1"  # 添加 /v1 后缀
        return base

    def resolved_model(self) -> Optional[str]:
        """
        解析实际使用的模型 ID
        
        优先使用 llm_model_id，否则使用 local_llm
        
        Returns:
            Optional[str]: 模型 ID
        """
        return self.llm_model_id or self.local_llm

