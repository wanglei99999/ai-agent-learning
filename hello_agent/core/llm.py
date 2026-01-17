import os
from openai import OpenAI
from dotenv import load_dotenv
from typing import List,Dict

load_dotenv()

class HelloAgentsLLM:
    """
        学习hello agent 过程中写的llm客户端
    """
    def __init__(self,model:str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None):
        """初始化客户端。优先使用传入参数，如果未提供，则从环境变量加载"""
        self.model = model or os.getenv("LLM_MODEL_ID")
        apiKey = apiKey or os.getenv("LLM_API_KEY")
        baseUrl = baseUrl or os.getenv("LLM_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model,apiKey,baseUrl]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")
        self.client = OpenAI(api_key=apiKey,base_url=baseUrl,timeout=timeout)

    def think(self,messages:List[Dict[str,str]], temperature:float = 0,stream:bool=True)->str:
        """
            调用大语言模型进行思考，并返回响应。
        """
        print(f"正在调用{self.model}进行思考")
        try:
            # OpenAI SDK 标准调用链：
            # self.client - OpenAI 客户端实例
            # .chat - 聊天相关的 API 模块（还有 .images 生图、.audio 语音、.embeddings 向量嵌入等模块）
            # .completions - 补全功能（大模型本质就是文本补全）
            # .create() - 创建一次对话请求，对应 POST /chat/completions 接口
            response = self.client.chat.completions.create(
                model=self.model,        # 模型名称
                messages=messages,       # 对话消息列表
                temperature=temperature,  # 温度参数，0=确定性输出，越高越随机
                stream=stream            # 是否流式返回
            )

            print("响应成功")
        
            # 收集流式响应的所有内容片段
            collected_content = []
            
            # 流式响应是一块一块返回的，需要遍历每个 chunk
            for chunk in response:
                # chunk.choices[0] - 获取第一个回复选项（通常只有一个）
                # .delta - 增量内容，流式特有，每次只返回新增的部分
                # .content - 实际的文本内容
                # or "" - 如果 content 是 None（比如结束时），用空字符串代替，防止报错
                content = chunk.choices[0].delta.content or ""
                print(content, end="", flush=True)  # 实时打印，实现打字机效果
                collected_content.append(content)
            
            print()  # 流式输出结束后换行
            return "".join(collected_content)  # 把所有片段拼成完整响应

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            return None

# --- 客户端使用示例 ---
if __name__ == '__main__':
    try:
        llmClient = HelloAgentsLLM()
        
        exampleMessages = [
            {"role": "system", "content": "You are a helpful assistant that writes Python code."},
            {"role": "user", "content": "写一个快速排序算法"}
        ]
        
        print("--- 调用LLM ---")
        responseText = llmClient.think(exampleMessages)
        if responseText:
            print("\n\n--- 完整模型响应 ---")
            print(responseText)

    except ValueError as e:
        print(e)
