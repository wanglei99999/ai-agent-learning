"""
配置管理模块

本模块负责管理应用的所有配置项，类似 Java Spring 的 @ConfigurationProperties
主要功能：
1. 从 .env 文件加载环境变量
2. 定义配置类（应用、服务器、API密钥等）
3. 提供配置验证和打印功能
4. 使用 Pydantic 自动验证和类型转换

Java 对比：
- BaseSettings → @ConfigurationProperties
- .env 文件 → application.properties/application.yml
- Settings 类 → 配置 Bean
"""

import os
from pathlib import Path
from typing import List
# Pydantic Settings: 自动从环境变量加载配置，类似 Spring Boot 的配置绑定
from pydantic_settings import BaseSettings
# dotenv: 从 .env 文件加载环境变量到 os.environ
from dotenv import load_dotenv

# =============================================================================
# 加载环境变量
# 类似 Java Spring 读取 application.properties，但这里从 .env 文件读取
# =============================================================================

# 1. 首先加载当前项目的 .env 文件（backend/.env）
#    load_dotenv() 会自动查找当前目录及父目录的 .env 文件
load_dotenv()

# 2. 然后尝试加载 HelloAgents 框架的全局 .env（如果存在）
#    这样可以共享 LLM API Key 等全局配置
helloagents_env = Path(__file__).parent.parent.parent.parent / "HelloAgents" / ".env"
if helloagents_env.exists():
    load_dotenv(helloagents_env, override=False)  # override=False 表示不覆盖已有的环境变量


# =============================================================================
# 配置类定义
# 继承 BaseSettings 后，Pydantic 会自动从环境变量读取配置
# 类似 Java: @ConfigurationProperties(prefix="app")
# =============================================================================
class Settings(BaseSettings):
    """
    应用配置类
    
    Pydantic BaseSettings 特性：
    1. 自动从环境变量读取（大小写不敏感）
    2. 自动类型转换（str → int/bool 等）
    3. 提供默认值
    4. 支持 .env 文件
    
    Java 等价：@ConfigurationProperties + @Value
    """

    # ========== 应用基本配置 ==========
    app_name: str = "HelloAgents智能旅行助手"  # 应用名称
    app_version: str = "1.0.0"                 # 版本号
    debug: bool = False                        # 调试模式

    # ========== 服务器配置 ==========
    host: str = "0.0.0.0"  # 监听地址，0.0.0.0 表示监听所有网卡
    port: int = 8000       # 监听端口

    # ========== CORS 跨域配置 ==========
    # 允许访问的前端地址列表（逗号分隔）
    # 类似 Java: @CrossOrigin(origins = {...})
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # ========== 高德地图 API 配置 ==========
    # 从环境变量 AMAP_API_KEY 读取，必填项
    amap_api_key: str = ""

    # ========== Unsplash 图片 API 配置 ==========
    # 用于获取旅行目的地图片（可选）
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""

    # ========== LLM（大语言模型）配置 ==========
    # HelloAgents 会优先使用 LLM_API_KEY 环境变量
    # 这里的配置作为备用
    openai_api_key: str = ""                      # OpenAI API Key
    openai_base_url: str = "https://api.openai.com/v1"  # API 基础 URL（支持自定义，如 DeepSeek）
    openai_model: str = "gpt-4"                   # 使用的模型名称

    # ========== 日志配置 ==========
    log_level: str = "INFO"  # 日志级别：DEBUG/INFO/WARNING/ERROR

    # ========== Pydantic 配置 ==========
    class Config:
        """Pydantic Settings 配置，类似 Java 的配置元数据"""
        env_file = ".env"           # 从 .env 文件读取配置
        case_sensitive = False      # 环境变量名不区分大小写（AMAP_API_KEY = amap_api_key）
        extra = "ignore"            # 忽略未定义的额外环境变量，避免报错

    def get_cors_origins_list(self) -> List[str]:
        """
        获取 CORS 允许的域名列表
        
        将逗号分隔的字符串转换为列表
        类似 Java: String.split(",")
        
        Returns:
            域名列表，如 ["http://localhost:5173", "http://localhost:3000"]
        """
        return [origin.strip() for origin in self.cors_origins.split(',')]


# =============================================================================
# 创建全局配置实例（单例模式）
# 类似 Java: @Bean 或 @Component
# 整个应用共享同一个配置对象
# =============================================================================
settings = Settings()


def get_settings() -> Settings:
    """
    获取配置实例（单例模式）
    
    类似 Java: @Autowired 注入配置 Bean
    
    Returns:
        全局配置对象
    """
    return settings


# =============================================================================
# 配置验证函数
# 在应用启动时调用，确保必要的配置项已设置
# 类似 Java: @PostConstruct 中的配置检查
# =============================================================================
def validate_config():
    """
    验证配置是否完整
    
    检查必填配置项（如 API Key）是否已设置
    - errors: 必填项缺失，抛出异常阻止启动
    - warnings: 可选项缺失，仅打印警告
    
    Raises:
        ValueError: 必填配置项缺失时抛出
    
    Returns:
        True: 配置验证通过
    """
    errors = []    # 存储错误信息（必填项）
    warnings = []  # 存储警告信息（可选项）

    # 检查高德地图 API Key（必填）
    if not settings.amap_api_key:
        errors.append("AMAP_API_KEY未配置")

    # 检查 LLM API Key（可选，但影响核心功能）
    # HelloAgents 框架会优先使用 LLM_API_KEY 环境变量
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_api_key:
        warnings.append("LLM_API_KEY或OPENAI_API_KEY未配置,LLM功能可能无法使用")

    # 如果有错误，抛出异常阻止应用启动
    if errors:
        error_msg = "配置错误:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    # 如果有警告，打印到控制台
    if warnings:
        print("\n配置警告:")
        for w in warnings:
            print(f"  - {w}")

    return True


# =============================================================================
# 配置打印函数（用于调试）
# 在应用启动时打印配置信息，方便排查问题
# 类似 Java: 在启动日志中打印配置摘要
# =============================================================================
def print_config():
    """
    打印当前配置（隐藏敏感信息）
    
    用于应用启动时展示配置摘要，帮助开发者确认配置是否正确
    敏感信息（如 API Key）只显示是否已配置，不显示具体值
    """
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"服务器: {settings.host}:{settings.port}")
    
    # 敏感信息只显示是否已配置，不显示具体值（安全考虑）
    print(f"高德地图API Key: {'已配置' if settings.amap_api_key else '未配置'}")

    # 检查 LLM 配置（优先使用环境变量，其次使用 Settings 中的默认值）
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_base_url = os.getenv("LLM_BASE_URL") or settings.openai_base_url
    llm_model = os.getenv("LLM_MODEL_ID") or settings.openai_model

    print(f"LLM API Key: {'已配置' if llm_api_key else '未配置'}")
    print(f"LLM Base URL: {llm_base_url}")  # 可以显示 URL，不敏感
    print(f"LLM Model: {llm_model}")        # 可以显示模型名，不敏感
    print(f"日志级别: {settings.log_level}")


# =============================================================================
# 使用说明
# =============================================================================
# 1. 在项目根目录创建 .env 文件，填入配置项：
#    AMAP_API_KEY=your_amap_key
#    LLM_API_KEY=your_llm_key
#    LLM_BASE_URL=https://api.deepseek.com/v1  # 可选，使用其他 LLM 提供商
#    LLM_MODEL_ID=deepseek-chat                # 可选，指定模型
#
# 2. 在代码中使用配置：
#    from app.config import settings
#    api_key = settings.amap_api_key
#
# 3. 环境变量优先级：
#    .env 文件 > 系统环境变量 > Settings 类中的默认值
# =============================================================================
