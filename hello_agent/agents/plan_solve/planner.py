"""
Planner 类 - 负责生成执行计划

职责：
1. 接收用户问题和可用工具列表
2. 调用 LLM 生成执行计划
3. 解析 LLM 输出的 Python 列表格式
4. 返回计划步骤列表

示例：
输入：问题 = "英伟达最新GPU的型号和特点是什么？"
输出：["搜索英伟达最新GPU型号", "搜索该GPU的主要特点", "综合信息给出答案"]
"""

import ast
from typing import List
from hello_agent.core.llm import HelloAgentsLLM
from hello_agent.agents.plan_solve.prompts import PLAN_PROMPT_TEMPLATE


class Planner:
    """规划器 - 生成执行计划"""

    def __init__(self, llm_client: HelloAgentsLLM):
        """
        初始化 Planner

        参数：
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client

    def plan(self, question: str, tools_desc: str) -> List[str]:
        """
        生成执行计划

        参数：
            question: 用户问题
            tools_desc: 可用工具描述

        返回：
            计划步骤列表，例如：["搜索信息", "分析数据", "给出结论"]
        """
        print("\n🎯 正在生成执行计划...")

        # 步骤1: 构造 Prompt
        prompt = PLAN_PROMPT_TEMPLATE.format(tools=tools_desc, question=question)

        # 步骤2: 调用 LLM
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_client.think(messages=messages)

        if not response:
            print("❌ LLM 未返回有效响应")
            return []

        # 步骤3: 解析计划
        plan = self._parse_plan(response)

        if plan:
            print(f"✅ 成功生成 {len(plan)} 步计划")
        else:
            print("❌ 未能解析出有效计划")

        return plan

    def _parse_plan(self, text: str) -> List[str]:
        """
        解析 LLM 输出的计划

        LLM 应该输出这样的格式：
        ```python
        [
            "第一步",
            "第二步",
            "第三步"
        ]
        ```

        参数：
            text: LLM 的完整输出

        返回：
            计划步骤列表
        """
        try:
            # 提取 ```python 和 ``` 之间的内容
            if "```python" in text:
                code_block = text.split("```python")[1].split("```")[0].strip()
            elif "```" in text:
                # 如果只有 ```，也尝试提取
                code_block = text.split("```")[1].split("```")[0].strip()
            else:
                # 如果没有代码块标记，尝试直接解析
                code_block = text.strip()

            # 使用 ast.literal_eval 安全地解析
            plan = ast.literal_eval(code_block)

            # 检查是否是列表
            if isinstance(plan, list):
                return [str(step) for step in plan]  # 确保每个元素都是字符串
            else:
                print(f"⚠️ 解析结果不是列表: {type(plan)}")
                return []

        except (IndexError, ValueError, SyntaxError) as e:
            print(f"❌ 解析计划时出错: {e}")
            print(f"原始响应: {text[:200]}...")  # 只打印前200个字符
            return []
        except Exception as e:
            print(f"❌ 解析计划时发生未知错误: {e}")
            return []
