"""
LLM（大语言模型）服务模块

本模块封装 LLM 服务，类似 Java 的 @Service 层
主要功能：
1. 创建和管理 LLM 实例（单例模式）
2. 自动从环境变量读取配置
3. 支持多种 LLM 提供商（OpenAI、DeepSeek 等）

Java 对比：
- get_llm() → @Autowired LLMService
- HelloAgentsLLM → OpenAI SDK 或 LLM 客户端
- 单例模式 → Spring Bean 管理
"""

# HelloAgents 框架的 LLM 封装类
from hello_agents import HelloAgentsLLM
# 导入配置管理
from ..config import get_settings

# =============================================================================
# 全局 LLM 实例（单例模式）
# 类似 Java 的静态变量或 Spring Bean
# =============================================================================
_llm_instance = None


def get_llm() -> HelloAgentsLLM:
    """
    获取 LLM 实例（单例模式）
    
    单例模式确保整个应用只创建一个 LLM 客户端，节省资源
    类似 Java Spring 的 @Bean 单例管理
    
    Returns:
        HelloAgentsLLM: LLM 实例，可用于调用 GPT/DeepSeek 等模型
    """
    global _llm_instance
    
    # 单例模式：如果已创建则直接返回
    if _llm_instance is None:
        settings = get_settings()
        
        # =======================================================================
        # 创建 HelloAgentsLLM 实例
        # HelloAgentsLLM 会自动从环境变量读取配置：
        # - LLM_API_KEY 或 OPENAI_API_KEY: API 密钥
        # - LLM_BASE_URL 或 OPENAI_BASE_URL: API 基础 URL
        # - LLM_MODEL_ID 或 OPENAI_MODEL: 模型名称
        # =======================================================================
        _llm_instance = HelloAgentsLLM()
        
        # 打印初始化信息（用于调试）
        print(f"LLM服务初始化成功")
        print(f"   提供商: {_llm_instance.provider}")  # 如 openai, deepseek
        print(f"   模型: {_llm_instance.model}")        # 如 gpt-4, deepseek-chat
    
    return _llm_instance


def reset_llm():
    """
    重置 LLM 实例
    
    用于测试或重新配置时清除当前实例
    下次调用 get_llm() 时会重新创建
    
    类似 Java: 重启 Spring 容器或重新加载 Bean
    """
    global _llm_instance
    _llm_instance = None


# =============================================================================
# 使用说明
# =============================================================================
# 在 Agent 或其他服务中使用：
#   from app.services.llm_service import get_llm
#   
#   llm = get_llm()
#   response = llm.chat("Hello, how are you?")
#
# 环境变量配置（.env 文件）：
#   LLM_API_KEY=sk-xxx
#   LLM_BASE_URL=https://api.deepseek.com/v1  # 可选
#   LLM_MODEL_ID=deepseek-chat                # 可选
# =============================================================================

