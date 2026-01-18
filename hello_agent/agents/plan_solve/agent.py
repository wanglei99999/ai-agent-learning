"""
Plan-Solve Agent 实现

Plan-Solve 是一种"先规划、再执行"的 Agent 架构。

工作流程：
1. Plan 阶段：分析问题，生成完整的执行计划
2. Solve 阶段：按计划逐步执行，每步可以调用工具
3. 执行过程中可以根据实际情况调整计划

与 ReAct 的对比：
- ReAct：边想边做，适合探索性任务
- Plan-Solve：先规划后执行，适合结构化任务
"""

import re
from typing import List
from hello_agent.core.llm import HelloAgentsLLM
from hello_agent.core.tool_executor import ToolExecutor
from hello_agent.agents.plan_solve.planner import Planner
from hello_agent.agents.plan_solve.solver import Solver


class PlanSolveAgent:
    """Plan-Solve Agent：先规划、再执行"""

    def __init__(
        self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 10
    ):
        """
        初始化 Plan-Solve Agent

        参数：
            llm_client: LLM 客户端
            tool_executor: 工具执行器
            max_steps: 最大执行步数
        """
        self.planner = Planner(llm_client)
        self.solver = Solver(llm_client, tool_executor)
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.plan = []
        self.history = []

    def run(self, question: str) -> str:
        """
        运行 Plan-Solve Agent

        流程：
        1. Plan 阶段：生成执行计划
        2. Solve 阶段：按计划执行

        参数：
            question: 用户问题

        返回：
            最终答案
        """
        print("\n" + "=" * 60)
        print("Plan-Solve Agent 开始运行")
        print("=" * 60)

        # ========== 阶段1：Plan（规划）==========
        print("\n【阶段1：制定计划】")
        tools_desc = self.tool_executor.get_available_tools()
        self.plan = self.planner.plan(question, tools_desc)

        if not self.plan:
            print("❌ 无法生成有效的执行计划")
            return None

        print("\n📋 生成的执行计划：")
        for i, step in enumerate(self.plan, 1):
            print(f"  {i}. {step}")

        # ========== 阶段2：Solve（执行）==========
        print("\n【阶段2：执行计划】")
        self.history = []

        for step_num in range(1, len(self.plan) + 1):
            if step_num > self.max_steps:
                print(f"\n⚠️ 达到最大步数限制 ({self.max_steps})")
                break

            print(f"\n--- 执行步骤 {step_num}/{len(self.plan)} ---")
            current_step_desc = self.plan[step_num - 1]
            print(f"📌 当前步骤：{current_step_desc}")

            # 执行当前步骤
            thought, action, observation = self.solver.solve_step(
                question, self.plan, step_num, self.history
            )

            # 打印执行结果
            if thought:
                print(f"💭 思考：{thought}")

            if not action:
                print("⚠️ 未能获取有效的 Action，继续下一步")
                continue

            # 检查是否完成
            if action.strip().startswith("Finish"):
                match = re.match(r"Finish\[(.*)\]", action.strip())
                if match:
                    final_answer = match.group(1)
                    print(f"\n✅ 获得最终答案")
                    return final_answer
                else:
                    print(f"⚠️ 无法解析 Finish 格式：{action}")
                    continue

            # 打印行动和观察
            print(f"🔧 行动：{action}")
            if observation:
                print(f"👁️ 观察：{observation}")

                # 记录到历史
                self.history.append(f"步骤{step_num}: {current_step_desc}")
                self.history.append(f"  Action: {action}")
                self.history.append(f"  Observation: {observation}")

        print("\n⚠️ 所有步骤执行完毕，但未获得最终答案")
        return None
