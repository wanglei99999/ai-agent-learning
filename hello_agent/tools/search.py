from serpapi.google_search import GoogleSearch
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
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "gl": "cn",
            "hl": "zh-cn",
        }

        # 3. 调用 SerpApi，获取搜索结果
        search_client = GoogleSearch(params)
        results = search_client.get_dict()

        # 4. 智能解析：按优先级返回最有价值的答案

        # 优先级1: 答案框列表
        if "answer_box_list" in results:
            return "\n".join(results["answer_box_list"])

        # 优先级2: 单个答案框
        if "answer_box" in results and "answer" in results["answer_box"]:
            return results["answer_box"]["answer"]

        # 优先级3: 知识图谱
        if "knowledge_graph" in results and "description" in results["knowledge_graph"]:
            return results["knowledge_graph"]["description"]

        # 优先级4: 普通搜索结果 - 返回前3条
        if "organic_results" in results and results["organic_results"]:
            snippets = [
                f"[{i+1}] {res.get('title', '')}\n{res.get('snippet', '')}"
                for i, res in enumerate(results["organic_results"][:3])
            ]
            return "\n\n".join(snippets)

        return f"对不起，没有找到关于 '{query}' 的信息。"

    except Exception as e:
        return f"搜索时发生错误: {e}"
