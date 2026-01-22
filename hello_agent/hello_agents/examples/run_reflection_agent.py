"""
Reflection Agent 运行示例

演示如何使用 Reflection Agent 通过自我反思来改进代码质量
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from hello_agent.core.llm import HelloAgentsLLM
from hello_agent.agents.reflection.agent import ReflectionAgent


def main():
    """主函数"""
    print("=" * 60)
    print("Reflection Agent 示例")
    print("=" * 60)

    # 1. 初始化 LLM 客户端
    print("\n[1] 初始化 LLM 客户端...")
    llm = HelloAgentsLLM()

    # 2. 创建 Reflection Agent
    print("[2] 创建 Reflection Agent...")
    agent = ReflectionAgent(llm_client=llm, max_iterations=3)

    # 3. 定义任务
    print("\n" + "=" * 60)
    task = "编写一个函数，判断一个数是否为质数"
    print(f"任务：{task}")
    print("=" * 60 + "\n")

    # 4. 运行 Agent
    try:
        final_code = agent.run(task)
        
        print("\n" + "=" * 60)
        print("✅ 任务完成！")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 运行出错：{e}")
        print("=" * 60)


if __name__ == "__main__":
    main()
