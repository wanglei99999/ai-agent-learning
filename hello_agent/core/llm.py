import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()


class HelloAgentsLLM:
    """
    学习 hello agent 过程中写的 LLM 客户端
    """

    def __init__(
        self, model: str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None
    ):
        """初始化客户端。优先使用传入参数，如果未提供，则从环境变量加载"""
        self.model = model or os.getenv("LLM_MODEL_ID")
        apiKey = apiKey or os.getenv("LLM_API_KEY")
        baseUrl = baseUrl or os.getenv("LLM_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, apiKey, baseUrl]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")
        self.client = OpenAI(api_key=apiKey, base_url=baseUrl, timeout=timeout)

    def think(
        self, messages: List[Dict[str, str]], temperature: float = 0, stream: bool = True
    ) -> str:
        """
        调用大语言模型进行思考，并返回响应。
        """
        print(f"正在调用{self.model}进行思考")
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=temperature, stream=stream
            )

            print("响应成功")

            # 收集流式响应的所有内容片段
            collected_content = []

            for chunk in response:
                content = chunk.choices[0].delta.content or ""
                print(content, end="", flush=True)
                collected_content.append(content)

            print()
            return "".join(collected_content)

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            return None
