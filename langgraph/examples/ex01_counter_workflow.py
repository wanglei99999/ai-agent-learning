"""
计数器工作流示例
==================
演示 LangGraph Graph API 的基本用法：
- 定义状态结构（TypedDict）
- 创建节点函数
- 构建图并连接节点
- 执行工作流并查看结果

这是学习 LangGraph 的第一个基础示例，展示了：
1. 状态如何在节点间传递
2. 如何定义和连接节点
3. 如何记录执行历史

执行流程：
  START → increment (+1) → double (×2) → report → END
"""

from langgraph.graph import StateGraph,START,END
from typing_extensions import TypedDict


# 1. 定义状态结构
class CounterState(TypedDict):
    count:int
    history: list[str]


# 2. 定义节点函数
def increment(state: CounterState):
    """计数器+1"""
    new_count = state["count"] + 1
    message = f"count:{state['count']}->{new_count}"

    return {
        "count": new_count,
        "history":state["history"]+[message]
    }
def double_node(state: CounterState):
    """计数器*2"""
    new_count = state["count"] * 2
    message = f"count:{state['count']}->{new_count}"
    return {
        "count": new_count,
        "history":state["history"]+[message]
    }
def repoet_node(state: CounterState):
    """报告结果"""
    return {
        "history":state['history']+[f"最终结果：{state['count']}"]
    }

# 3. 创建图
workflow = StateGraph(CounterState) 

# 4. 添加节点
workflow.add_node("increment",increment)
workflow.add_node("double",double_node)
workflow.add_node("report",repoet_node)

# 5. 连接节点
workflow.add_edge(START,"increment")
workflow.add_edge("increment","double")
workflow.add_edge("double","report")
workflow.add_edge("report",END)

# 6. 编译
app = workflow.compile()

# 7. 运行
result = app.invoke({
    "count":5,
    "history":["开始执行"]
})
print("执行历史:")
for setp in result["history"]:
    print(f"  - {setp}")
print("\n最终计数:",result["count"])

    # 预期输出：
    # 执行历史:
    #   - 开始执行
    #   - count: 5 → 6
    #   - count: 6 → 12
    #   - 最终结果: 12
    #
    # 最终计数: 12
