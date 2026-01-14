"""
手动实现 ReAct Agent (模拟版本)
================================
ReAct = Reasoning (推理) + Acting (行动)

核心流程：
  START → agent (思考) → [需要工具?] → tools (执行) → agent → ...
                              ↓ (不需要)
                             END

学习重点：
1. Agent 如何决定是否使用工具 (条件边)
2. 工具执行后如何返回给 Agent (循环)
3. 如何防止无限循环

注意：这里用模拟函数代替真实 LLM，专注学习 ReAct 流程
"""

import operator
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END


#1. 定义状态
class AgentState(TypedDict):
    """Agent 状态定义"""
    question: str           # 用户问题
    current_step: int       # 当前执行步骤
    tool_name: str          # 需要调用的工具名称
    tool_args: dict         # 工具参数
    tool_result: any        # 工具执行结果
    answer: str             # 最终答案
    iterations: Annotated[int, operator.add]  # 迭代次数（自动累加）


#2. 定义工具
def multiply(a: int, b: int) -> int:
    """两个数相乘"""
    print(f"   执行工具: multiply({a}, {b})")
    return a * b


def add(a: int, b: int) -> int:
    """两个数相加"""
    print(f"   执行工具: add({a}, {b})")
    return a + b


def divide(a: int, b: int) -> float:
    """两个数相除"""
    print(f"   执行工具: divide({a}, {b})")
    if b == 0:
        return "错误：除数不能为0"
    return a / b


# 工具映射表
tools_map = {
    "multiply": multiply,
    "add": add,
    "divide": divide
}


#3. 定义节点
def agent_think(state: AgentState):
    """
    Agent 思考节点 - 硬编码模拟 LLM 决策过程
    """
    step = state["current_step"]
    question = state["question"]
    
    print(f"\nAgent 思考 (步骤 {step})...")
    
    # 模拟 ReAct 推理过程
    if step == 0:
        # 第一步：分析问题 "计算 (25 * 4) + 10"
        print(f"   问题: {question}")
        print("   推理: 需要先计算 25 * 4")
        return {
            "tool_name": "multiply",
            "tool_args": {"a": 25, "b": 4},
            "current_step": 1,
            "iterations": 1
        }
    
    elif step == 1:
        # 第二步：使用上一步结果
        result = state["tool_result"]
        print(f"   上一步结果: {result}")
        print(f"   推理: 现在需要计算 {result} + 10")
        return {
            "tool_name": "add",
            "tool_args": {"a": result, "b": 10},
            "current_step": 2,
            "iterations": 1
        }
    
    elif step == 2:
        # 第三步：得出最终答案
        result = state["tool_result"]
        print(f"   上一步结果: {result}")
        print(f"   推理: 计算完成，答案是 {result}")
        return {
            "tool_name": "",  # 不再需要工具
            "answer": f"答案是 {result}",
            "current_step": 3,
            "iterations": 1
        }
    
    return {"iterations": 1}


def execute_tool(state: AgentState):
    """工具执行节点"""
    tool_name = state["tool_name"]
    tool_args = state["tool_args"]
    
    print(f"\n执行工具...")
    
    # 从工具映射表中获取工具函数并执行
    tool_func = tools_map[tool_name]
    result = tool_func(**tool_args)
    
    print(f"   结果: {result}")
    
    return {"tool_result": result}


#4. 定义条件边
def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """
    判断是否继续使用工具
    
    返回值：
    - "tools": 继续执行工具
    - "__end__": 结束流程
    """
    tool_name = state.get("tool_name", "")
    
    # 如果有工具名，继续执行工具
    if tool_name:
        return "tools"
    
    # 否则结束
    return "__end__"


# ============ 5. 构建图 ============
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("agent", agent_think)
workflow.add_node("tools", execute_tool)

# 添加边
workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "__end__": END
    }
)
workflow.add_edge("tools", "agent")  # 工具执行后回到 agent

# 编译图
app = workflow.compile()


# ============ 6. 测试 ============
if __name__ == "__main__":
    print("=" * 60)
    print("ReAct Agent 示例 (模拟版本)")
    print("=" * 60)
    
    # 测试问题
    question = "计算 (25 * 4) + 10"
    
    print(f"\n问题: {question}")
    print("=" * 60)
    
    # 执行
    result = app.invoke({
        "question": question,
        "current_step": 0,
        "tool_name": "",
        "tool_args": {},
        "tool_result": None,
        "answer": "",
        "iterations": 0
    })
    
    # 打印结果
    print("\n" + "=" * 60)
    print(f"最终答案: {result['answer']}")
    print(f"总迭代次数: {result['iterations']}")
    print("=" * 60)
    print()
    print("ReAct 循环说明：")
    print("1. Agent 思考 -> 决定使用 multiply(25, 4)")
    print("2. 执行工具 -> 返回 100")
    print("3. Agent 思考 -> 决定使用 add(100, 10)")
    print("4. 执行工具 -> 返回 110")
    print("5. Agent 思考 -> 给出最终答案，结束")
    print()
    print("注意：这是模拟版本，推理步骤是硬编码的")
    print("真实版本需要集成 LLM，让 LLM 自己决策")