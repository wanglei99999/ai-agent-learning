from serpapi import SerpApiClient
import os
from dotenv import load_dotenv
load_dotenv()

def search(query: str) -> str:
    """
    一个基于SerpApi的实战网页搜索引擎工具。
    它会智能解析搜索结果，优先返回直接答案或者知识图谱信息。
    """
    print(f"正在使用Serp网页搜索，搜索内容：{query}")
    
    try:
        # 1. 从环境变量获取 API Key
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            return "错误：SERPAPI_API_KEY未在.env文件中配置，请先配置"
        
        # 2. 构造 SerpApi 请求参数
        params = {
            "engine": "google",   # 使用 Google 搜索引擎
            "q": query,           # 搜索关键词
            "api_key": api_key,
            "gl": "cn",           # 地区代码（geolocation）：中国
            "hl": "zh-cn"         # 语言代码（host language）：简体中文
        }

        # 3. 调用 SerpApi，获取搜索结果（返回字典格式）
        client = SerpApiClient(params)
        results = client.get_dict()

        # 4. 智能解析：按优先级返回最有价值的答案
        
        # 优先级1: 答案框列表 - 多个直接答案（如"2024年节假日"会返回多个日期）
        if "answer_box_list" in results:
            return "\n".join(results["answer_box_list"])
        
        # 优先级2: 单个答案框 - 直接答案（如"北京天气"直接显示温度）
        if "answer_box" in results and "answer" in results["answer_box"]:
            return results["answer_box"]["answer"]
        
        # 优先级3: 知识图谱 - 实体描述（如搜"马云"显示人物简介）
        if "knowledge_graph" in results and "description" in results["knowledge_graph"]:
            return results["knowledge_graph"]["description"]
        
        # 优先级4: 普通搜索结果 - 返回前3条的标题和摘要
        if "organic_results" in results and results["organic_results"]:
            snippets = [
                f"[{i+1}] {res.get('title', '')}\n{res.get('snippet', '')}"
                for i, res in enumerate(results["organic_results"][:3])
            ]
            return "\n\n".join(snippets)
        
        return f"对不起，没有找到关于 '{query}' 的信息。"

    except Exception as e:
        return f"搜索时发生错误: {e}"
