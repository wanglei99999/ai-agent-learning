"""
ReAct (Reasoning + Acting) 提示词模板

这个模板定义了智能体与 LLM 之间交互的规范：

1. 角色定义：
   "你是一个有能力调用外部工具的智能助手"，设定了 LLM 的角色。

2. 工具清单 ({tools}):
   告知 LLM 它有哪些可用的"手脚"。

3. 格式规约 (Thought/Action):
   这是最重要的部分，它强制 LLM 的输出具有结构性，
   使我们能通过代码精确解析其意图。

4. 动态上下文 ({question}/{history}):
   将用户的原始问题和不断累积的交互历史注入，
   让 LLM 基于完整的上下文进行决策。

关键技术细节：
--------------
- 双花括号 {{tool_name}} 的作用：
  在 Python 的 .format() 方法中，双花括号会被转义为单花括号。
  例如：{{tool_name}} 经过 .format() 后变成 {tool_name}
  这样 LLM 看到的是 {tool_name}，理解为"这里应该填入工具名"。

- Action 格式解析：
  LLM 输出的 Action 是代码和 LLM 之间的通信协议。
  格式：Action: 工具名[工具输入]
  示例：Action: Search[英伟达最新GPU]
  代码需要用正则表达式解析出工具名和输入，然后调用对应的工具函数。

- ReAct 循环流程：
  用户问题 → LLM 思考 → 输出 Action → 代码解析并执行工具
  → 返回 Observation → LLM 继续思考 → 直到输出 Finish[答案]

使用示例：
---------
from hello_agent.agents.react.prompts import REACT_PROMPT_TEMPLATE

prompt = REACT_PROMPT_TEMPLATE.format(
    tools="- Search: 网页搜索工具\\n- Calculator: 数学计算工具",
    question="英伟达最新的GPU是什么？",
    history=""
)
# 将 prompt 发送给 LLM，LLM 会按照规定格式返回 Thought 和 Action
"""

REACT_PROMPT_TEMPLATE = """
请注意，你是一个有能力调用外部工具的智能助手。

可用工具如下：
{tools}

请严格按照以下格式进行回应：

Thought: 你的思考过程，用于分析问题、拆解任务和规划下一步的行动。
Action: 你决定采取的行动，必须是以下格式之一：
- `{{tool_name}}[{{tool_input}}]`: 调用一个可用工具
- `Finish[最终答案]`: 当你认为已经获得最终答案时。
- 当你收集到足够的信息，能够回答用户的最终问题时，你必须在 Action: 字段后使用 Finish[最终答案] 来输出最终答案

现在，请开始回答以下问题：
Question: {question}
History: {history}
"""
