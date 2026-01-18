"""
Solver 类 - 负责执行计划中的单个步骤

职责：
1. 接收当前要执行的步骤
2. 调用 LLM 决定如何执行
3. 解析 Thought 和 Action
4. 执行工具调用
5. 返回执行结果

示例：
输入：步骤 = "搜索英伟达最新GPU型号"
输出：(thought, action, observation)
"""

import re
from typing import Tuple, List
from hello_agent.core.llm import HelloAgentsLLM
from hello_agent.core.tool_executor import ToolExecutor
from hello_agent.agents.plan_solve.prompts import SOLVE_PROMPT_TEMPLATE


class Solver:
    """执行器 - 执行计划中的单个步骤"""

    def __init__(self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor):
        """
        初始化 Solver

        参数：
            llm_client: LLM 客户端
            tool_executor: 工具执行器
        """
        self.llm_client = llm_client
        self.tool_executor = tool_executor

    def solve_step(
        self, question: str, plan: List[str], current_step_num: int, history: List[str]
    ) -> Tuple[str, str, str]:
        """
        执行单个步骤

        参数：
            question: 原始问题
            plan: 完整计划列表
            current_step_num: 当前步骤编号（从1开始）
            history: 已完成步骤的历史

        返回：
            (thought, action, observation) 元组
            - thought: LLM 的思考
            - action: LLM 的行动（如 "Search[...]" 或 "Finish[...]"）
            - observation: 工具执行结果（如果是 Finish 则为 None）
        """
        # 步骤1: 构造 Prompt
        tools_desc = self.tool_executor.get_available_tools()
        plan_str = "\n".join([f"{i}. {step}" for i, step in enumerate(plan, 1)])
        history_str = "\n".join(history) if history else "(无)"
        current_step_desc = plan[current_step_num - 1]
        total_steps = len(plan)

        prompt = SOLVE_PROMPT_TEMPLATE.format(
            tools=tools_desc,
            question=question,
            plan=plan_str,
            current_step=current_step_num,
            total_steps=total_steps,
            current_step_description=current_step_desc,
            history=history_str,
        )

        # 步骤2: 调用 LLM
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.think(messages=messages)

        if not response:
            print("❌ LLM 未返回有效响应")
            return None, None, None

        # 步骤3: 解析 Thought 和 Action
        thought, action = self._parse_output(response)

        if not action:
            print("⚠️ 未能解析出 Action")
            return thought, None, None

        # 步骤4: 检查是否是 Finish（需要去掉可能的列表前缀）
        action_clean = action.strip()
        if action_clean.startswith('-') or action_clean.startswith('*'):
            action_clean = action_clean[1:].strip()
        
        if action_clean.startswith("Finish"):
            # 如果是 Finish，不需要执行工具
            return thought, action, None

        # 步骤5: 解析工具名和输入
        tool_name, tool_input = self._parse_action(action)
        if not tool_name or not tool_input:
            print("⚠️ 无法解析 Action 格式")
            return thought, action, None

        # 步骤6: 执行工具
        tool_function = self.tool_executor.get_tool(tool_name)
        if not tool_function:
            observation = f"错误：未找到工具 {tool_name}"
        else:
            observation = tool_function(tool_input)

        return thought, action, observation

    def _parse_output(self, text: str) -> Tuple[str, str]:
        """
        解析 LLM 输出的 Thought 和 Action

        参数：
            text: LLM 的完整输出

        返回：
            (thought, action) 元组
        """
        # 匹配 Thought（可能跨多行，直到遇到 Action: 或文本结束）
        thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|$)", text, re.DOTALL)
        
        # 匹配 Action（可能在同一行或下一行，直到遇到换行或文本结束）
        # 支持格式：
        # Action: Search[...]
        # Action: 
        # - Search[...]
        action_match = re.search(r"Action:\s*(.*?)(?:\n\n|$)", text, re.DOTALL)

        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None

        return thought, action

    def _parse_action(self, action_text: str) -> Tuple[str, str]:
        """
        解析 Action 字符串，提取工具名和输入

        格式：工具名[工具输入]
        例如：Search[英伟达最新GPU]
        
        也支持带列表前缀的格式：
        - Search[英伟达最新GPU]
        * Search[英伟达最新GPU]

        参数：
            action_text: Action 字符串

        返回：
            (tool_name, tool_input) 元组
        """
        original_text = action_text
        
        # 去除前后空格
        action_text = action_text.strip()
        
        # 去除可能的列表标记前缀（- 或 *）
        if action_text.startswith('-') or action_text.startswith('*'):
            action_text = action_text[1:].strip()
        
        # 使用更宽松的正则：匹配任意非 [ 字符作为工具名
        match = re.match(r"([^\[]+)\[(.+)\]", action_text)
        if match:
            tool_name = match.group(1).strip()
            tool_input = match.group(2).strip()
            return tool_name, tool_input
        
        # 如果解析失败，打印调试信息
        print(f"⚠️ 无法解析 Action: '{original_text}'")
        print(f"   处理后: '{action_text}'")
        return None, None
