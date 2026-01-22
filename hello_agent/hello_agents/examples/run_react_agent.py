"""
ReAct Agent 运行示例

演示如何使用 ReAct Agent 来回答问题
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from hello_agent.core.llm import HelloAgentsLLM
from hello_agent.core.tool_executor import ToolExecutor
from hello_agent.agents.react import ReactAgent
from hello_agent.tools.search import search


def main():
    """主函数"""
    print("=" * 60)
    print("ReAct Agent 示例")
    print("=" * 60)

    # 1. 初始化 LLM 客户端
    print("\n[1] 初始化 LLM 客户端...")
    llm = HelloAgentsLLM()

    # 2. 初始化工具执行器并注册工具
    print("[2] 注册工具...")
    tool_executor = ToolExecutor()
    tool_executor.register_tool(
        name="Search",
        description="网页搜索工具。当你需要回答关于时事、实时信息时使用此工具。",
        func=search,
    )

    # 3. 创建 ReAct Agent
    print("[3] 创建 ReAct Agent...")
    agent = ReactAgent(llm_client=llm, tool_executor=tool_executor, max_steps=5)

    # 4. 运行 Agent 回答问题
    print("\n" + "=" * 60)
    question = "英伟达最新的GPU型号是什么？"
    print(f"问题：{question}")
    print("=" * 60 + "\n")

    answer = agent.run(question)

    print("\n" + "=" * 60)
    if answer:
        print(f"✅ 成功获得答案：{answer}")
    else:
        print("❌ 未能获得答案")
    print("=" * 60)


if __name__ == "__main__":
    main()
