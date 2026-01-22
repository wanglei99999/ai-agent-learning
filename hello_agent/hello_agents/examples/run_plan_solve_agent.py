"""
Plan-Solve Agent 运行示例

演示 Plan-Solve Agent 的"先规划、再执行"工作流程
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from hello_agent.core import HelloAgentsLLM, ToolExecutor
from hello_agent.agents.plan_solve import PlanSolveAgent
from hello_agent.tools import search


def main():
    """主函数"""
    print("=" * 60)
    print("Plan-Solve Agent 示例")
    print("=" * 60)

    # 1. 初始化 LLM 客户端
    print("\n[1] 初始化 LLM 客户端...")
    llm = HelloAgentsLLM()

    # 2. 初始化工具执行器并注册工具
    print("[2] 注册工具...")
    tool_executor = ToolExecutor()
    tool_executor.register_tool(
        name="Search",
        description="网页搜索工具。用于查找实时信息、事实数据等。",
        func=search,
    )

    # 3. 创建 Plan-Solve Agent
    print("[3] 创建 Plan-Solve Agent...")
    agent = PlanSolveAgent(llm_client=llm, tool_executor=tool_executor, max_steps=10)

    # 4. 运行 Agent 回答问题
    question = "英伟达最新GPU是什么？"
    print(f"\n问题：{question}")

    answer = agent.run(question)

    print("\n" + "=" * 60)
    if answer:
        print(f"✅ 最终答案：\n{answer}")
    else:
        print("❌ 未能获得答案")
    print("=" * 60)


if __name__ == "__main__":
    main()
