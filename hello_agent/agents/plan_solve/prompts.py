"""
Plan-Solve Agent 提示词模板

Plan-Solve 是一种"先规划、再执行"的 Agent 架构，分为两个阶段：

阶段1 - Plan（规划）：
  分析问题 → 制定完整的执行计划 → 输出步骤列表

阶段2 - Solve（执行）：
  按计划逐步执行 → 每步可以调用工具 → 根据结果调整后续计划

与 ReAct 的区别：
- ReAct：边想边做，走一步看一步
- Plan-Solve：先想清楚整体方案，再按计划执行

优势：
- 更有条理，执行路径清晰
- 可以提前发现问题
- 便于调试和优化
"""

PLAN_PROMPT_TEMPLATE = """
你是一个善于规划的智能助手。

可用工具如下：
{tools}

请分析以下问题，制定一个详细的执行计划。

问题：{question}

请按照以下格式输出你的计划（必须是 Python 列表格式）：

```python
[
    "第一步要做什么",
    "第二步要做什么",
    "第三步要做什么"
]
```

注意：
- 每一步应该清晰、具体
- 如果需要使用工具，明确说明使用哪个工具
- 计划应该是完整的，能够解决整个问题
- 必须严格按照上述 Python 列表格式输出
"""

SOLVE_PROMPT_TEMPLATE = """
你是一个执行计划的智能助手。

可用工具如下：
{tools}

原始问题：{question}

执行计划（共 {total_steps} 步）：
{plan}

当前执行到：步骤 {current_step}/{total_steps}
{current_step_description}

已完成的步骤：
{history}

请执行当前步骤，按照以下格式输出：

Thought: 你对当前步骤的思考
Action: 你要采取的行动，格式为：
- `{{tool_name}}[{{tool_input}}]`: 调用工具
- `Finish[最终答案]`: **如果这是最后一步（步骤 {current_step}/{total_steps}），且你已经收集到足够信息，必须使用 Finish 给出最终答案**

注意：
- 如果当前是最后一步，你必须综合所有已完成步骤的信息，给出完整的最终答案
- 最终答案应该直接回答原始问题
"""
