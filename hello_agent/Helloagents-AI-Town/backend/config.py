"""
配置管理模块

负责管理应用的所有配置项
包括 API 服务配置、NPC 行为配置、LLM 配置和 CORS 配置
配置值优先从环境变量读取，提供默认值作为后备
"""

import os
from typing import Optional

class Settings:
    """
    应用配置类
    
    集中管理所有配置项，支持从环境变量读取
    使用类变量存储配置，方便全局访问
    """
    
    # ===================================================================
    # API 服务配置
    # ===================================================================
    API_TITLE = "赛博小镇 API"  # FastAPI 文档标题
    API_VERSION = "1.0.0"       # API 版本号
    API_HOST = "0.0.0.0"        # 监听地址（0.0.0.0 表示监听所有网卡）
    API_PORT = 8000             # 监听端口
    
    # ===================================================================
    # NPC 行为配置
    # ===================================================================
    # NPC 自主行为更新间隔（秒）
    # NPC 会定期更新自己的状态（如闲逛、工作等）
    NPC_UPDATE_INTERVAL = 30
    
    # ===================================================================
    # LLM 配置（从环境变量读取）
    # ===================================================================
    # HelloAgents 框架使用自定义 LLM 配置
    # 支持多种 LLM 服务提供商（OpenAI、ModelScope 等）
    
    # LLM 模型 ID
    # 默认使用 ModelScope 的 Qwen2.5-72B-Instruct 模型
    LLM_MODEL_ID: str = os.getenv("LLM_MODEL_ID", "Qwen/Qwen2.5-72B-Instruct")
    
    # LLM API 密钥
    # 必须在 .env 文件中配置
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY")
    
    # LLM 服务地址
    # 默认使用 ModelScope 的推理服务
    # 也可以配置为 OpenAI、LMStudio 等其他服务
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api-inference.modelscope.cn/v1/")

    # ===================================================================
    # CORS 跨域配置
    # ===================================================================
    # 允许的跨域来源列表
    # "*" 表示允许所有来源（仅用于开发环境）
    # 生产环境应限制为具体的域名，如 ["http://localhost:3000"]
    CORS_ORIGINS = ["*"]

    @classmethod
    def validate(cls):
        """
        验证配置的有效性
        
        检查必需的配置项是否已设置
        主要验证 LLM API 密钥是否配置
        
        Returns:
            bool: 配置是否有效
        """
        # 检查 LLM API 密钥
        if not cls.LLM_API_KEY:
            print("警告: 未设置 LLM_API_KEY 环境变量")
            print("请在 .env 文件中配置 LLM_API_KEY")
            print("示例: LLM_API_KEY=\"your-api-key\"")
            return False

        # 打印 LLM 配置信息
        print("LLM 配置:")
        print(f"  模型: {cls.LLM_MODEL_ID}")
        print(f"  服务地址: {cls.LLM_BASE_URL}")
        return True

settings = Settings()

