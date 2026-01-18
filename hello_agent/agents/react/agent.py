"""
ReAct Agent 实现

ReAct (Reasoning + Acting) 是一种让 LLM 能够"思考-行动-观察"循环工作的 Agent 架构。

核心思想：
1. Reasoning（推理）：LLM 分析问题，决定下一步做什么
2. Acting（行动）：调用外部工具执行具体操作
3. Observing（观察）：获取工具执行结果，继续思考
4. 循环往复，直到得到最终答案

架构组件：
- LLM Client：大脑，负责思考和决策
- Tool Executor：手脚，负责执行具体工具
- Prompt Template：使用说明书，告诉 LLM 如何输出
- History：记忆，记录每一步的思考和行动

工作流程：
用户问题 → 构造 Prompt → LLM 思考 → 解析 Action → 执行工具
→ 获取 Observation → 加入 History → 继续循环 → 直到 Finish
"""

import re
from hello_agent.core.llm import HelloAgentsLLM
from hello_agent.core.tool_executor import ToolExecutor
from hello_agent.agents.react.prompts import REACT_PROMPT_TEMPLATE


class ReactAgent:
    def __init__(
        self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 5
    ):
        """
        初始化 ReAct Agent

        参数：
            llm_client: LLM 客户端，负责思考和决策（大脑）
            tool_executor: 工具执行器，负责调用外部工具（手脚）
            max_steps: 最大循环步数，防止无限循环（默认5步）
        """
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.history = []

    def run(self, question: str):
        """
        运行 ReAct 智能体来回答问题

        这是 Agent 的主循环，实现 "思考→行动→观察" 的循环流程：
        1. 构造包含工具列表、问题、历史的 Prompt
        2. LLM 根据 Prompt 输出 Thought 和 Action
        3. 解析 Action，如果是 Finish 则返回答案，否则执行工具
        4. 将工具执行结果（Observation）加入历史
        5. 重复步骤 1-4，直到得到最终答案或达到最大步数

        参数：
            question: 用户的问题

        返回：
            最终答案字符串，如果失败则返回 None
        """
        self.history = []
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1
            print(f"--- 第 {current_step} 步 ---")

            # ========== 步骤1: 构造 Prompt ==========
            tool_desc = self.tool_executor.get_available_tools()
            history_str = "\n".join(self.history)
            prompt = REACT_PROMPT_TEMPLATE.format(
                tools=tool_desc, question=question, history=history_str
            )

            # ========== 步骤2: LLM 思考 ==========
            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm_client.think(messages=messages)

            if not response_text:
                print("错误：LLM 未能返回有效响应")
                break

            # ========== 步骤3: 解析 LLM 输出 ==========
            thought, action = self._parse_output(response_text)

            if thought:
                print(f"思考：{thought}")
            if not action:
                print("警告：未能解析出有效的 Action，流程终止")
                break

            # ========== 步骤4: 执行 Action ==========
            if action.startswith("Finish"):
                match = re.match(r"Finish\[(.*)\]", action)
                if match:
                    final_answer = match.group(1)
                    print(f"最终答案：{final_answer}")
                    return final_answer
                else:
                    print(f"警告：无法解析 Finish 格式：{action}")
                    return None

            # 情况2: 工具调用
            tool_name, tool_input = self._parse_action(action)
            if not tool_name or not tool_input:
                print("警告：无法解析 Action 格式")
                continue
            print(f"行动：{tool_name}[{tool_input}]")

            # ========== 步骤5: 执行工具并获取观察结果 ==========
            tool_function = self.tool_executor.get_tool(tool_name)
            if not tool_function:
                observation = f"错误：未找到名为 {tool_name} 的工具"
            else:
                observation = tool_function(tool_input)

            print(f"观察：{observation}")

            # ========== 步骤6: 将 Action 和 Observation 加入历史 ==========
            self.history.append(f"Action: {action}")
            self.history.append(f"Observation: {observation}")

        print("已达到最大步数，流程终止")
        return None

    def _parse_output(self, text: str):
        """解析 LLM 的输出，提取 Thought 和 Action"""
        thought_match = re.search(r"Thought:(.*)", text)
        action_match = re.search(r"Action:(.*)", text)
        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None
        return thought, action

    def _parse_action(self, action_text: str):
        """解析 Action 字符串，提取工具名称和输入"""
        match = re.match(r"(\w+)\[(.*)\]", action_text.strip())
        if match:
            return match.group(1), match.group(2)
        return None, None
