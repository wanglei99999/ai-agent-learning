# my_llm.py
import os
from typing import Optional
from openai import OpenAI
from hello_agents import HelloAgentsLLM

class MyLLM(HelloAgentsLLM):
    """
    一个自定义的LLM客户端，通过继承增加了对ModelScope等多服务商的支持。
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = "auto",
        **kwargs
    ):
        # 1. 如果是 auto，先自动检测服务商
        if provider == "auto":
            provider = self._auto_detect_provider(api_key, base_url)
        
        self.provider = provider
        print(f"正在使用 {self.provider} 服务商")
        
        # 2. 根据 provider 获取凭证
        self.api_key, self.base_url = self._resolve_credentials(api_key, base_url)
        
        # 3. 验证凭证是否存在
        if not self.api_key:
            raise ValueError(f"{self.provider} API key not found. Please set the corresponding environment variable.")
        
        # 4. 设置模型和其他参数
        self.model = model or os.getenv("LLM_MODEL_ID", "qwen2.5-coder:latest")
        self.timeout = kwargs.get("timeout", 60)
        
        # 5. 创建 OpenAI 客户端实例
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)

    def _auto_detect_provider(self, api_key: Optional[str], base_url: Optional[str]) -> str:
        """
        自动检测LLM提供商，按优先级顺序：
        1. 特定服务商的环境变量
        2. base_url 域名/端口匹配
        3. API 密钥格式
        4. 默认使用通用配置
        """
        # 1. 检查特定提供商的环境变量（最高优先级）
        if os.getenv("MODELSCOPE_API_KEY"): return "modelscope"
        if os.getenv("OPENAI_API_KEY"): return "openai"
        if os.getenv("ZHIPU_API_KEY"): return "zhipu"
        
        # 获取通用的环境变量
        actual_api_key = api_key or os.getenv("LLM_API_KEY")
        actual_base_url = base_url or os.getenv("LLM_BASE_URL")
        
        # 2. 根据 base_url 判断
        if actual_base_url:
            base_url_lower = actual_base_url.lower()
            if "api-inference.modelscope.cn" in base_url_lower: return "modelscope"
            if "api.openai.com" in base_url_lower: return "openai"
            if "open.bigmodel.cn" in base_url_lower: return "zhipu"
            if "localhost" in base_url_lower or "127.0.0.1" in base_url_lower:
                if ":11434" in base_url_lower: return "ollama"
                if ":8000" in base_url_lower: return "vllm"
                return "local"
        
        # 3. 根据 API 密钥格式辅助判断
        if actual_api_key:
            if actual_api_key.startswith("ms-"): return "modelscope"
            if actual_api_key.startswith("sk-"): return "openai"
        
        # 4. 默认返回通用配置
        return "generic"

    def _resolve_credentials(self, api_key: Optional[str], base_url: Optional[str]) -> tuple:
        """根据 provider 解析 API 密钥和 base_url"""
        if self.provider == "openai":
            resolved_api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
            resolved_base_url = base_url or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1"
        
        elif self.provider == "modelscope":
            resolved_api_key = api_key or os.getenv("MODELSCOPE_API_KEY") or os.getenv("LLM_API_KEY")
            resolved_base_url = base_url or os.getenv("LLM_BASE_URL") or "https://api-inference.modelscope.cn/v1"
        
        elif self.provider == "zhipu":
            resolved_api_key = api_key or os.getenv("ZHIPU_API_KEY") or os.getenv("LLM_API_KEY")
            resolved_base_url = base_url or os.getenv("LLM_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4"
        
        elif self.provider in ("ollama", "vllm", "local"):
            resolved_api_key = api_key or os.getenv("LLM_API_KEY") or "not-needed"
            resolved_base_url = base_url or os.getenv("LLM_BASE_URL") or "http://localhost:11434/v1"
        
        else:  # generic 或其他
            resolved_api_key = api_key or os.getenv("LLM_API_KEY")
            resolved_base_url = base_url or os.getenv("LLM_BASE_URL")
        
        return resolved_api_key, resolved_base_url