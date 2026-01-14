"""
循环流程工作流示例
==================
演示 LangGraph 中循环流程的使用：
- 使用条件边指回前面的节点形成循环
- 实现迭代改进机制
- 设置退出条件防止无限循环
- 使用迭代计数器跟踪循环次数

这是学习 LangGraph 的第四个示例，展示了：
1. 如何创建循环流程（条件边指回前面的节点）
2. 如何设置退出条件（质量检查 + 最大迭代次数）
3. 如何使用 Annotated 和 operator.add 实现迭代计数器
4. 循环改进模式的实际应用

执行流程：
  START → generate (生成答案)
           ↓
         check (检查质量)
           ↓
         [质量OK?] 条件判断
           ↓
     不OK → improve (继续改进) → 回到 check (循环)
           ↓
      OK → done → END

关键点：
- 条件边可以指回前面的节点：形成循环
- 必须有退出条件：否则会无限循环
- 建议设置最大迭代次数：兜底保护
"""

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from typing import Annotated
import operator

# ==================== 1. 定义状态结构 ====================
class ImprovementState(TypedDict):
    question: str            # 问题
    answer: str             # 当前答案
    quality_score: float    # 质量分数 (0-1)
    iteration: Annotated[int, operator.add]  # 迭代次数（累加）
    max_iterations: int     # 最大迭代次数
    improved: bool          # 是否已改进


# ==================== 2. 定义节点函数 ====================

# 生成节点：生成初始答案
def generate(state: ImprovementState):
    """生成初始答案"""
    return {
        "answer": f"这是对{state['question']}的初始答案。",
        "iteration": 1  # 注意：这是增量值，因为 iteration 是累加字段
    }

# 检查节点：检查答案质量
def check(state: ImprovementState):
    """检查答案质量"""
    # 根据答案长度或其他指标计算质量分数
    answer_length = len(state["answer"])
    # 简单的质量评分：答案越长，分数越高（模拟）
    quality = min(0.3 + answer_length * 0.01, 0.95)
    
    return {
        "quality_score": quality
    }
def improve(state:ImprovementState):
    """改进答案"""
    current_answer = state["answer"]
    improved_answer = current_answer +"[改进后的答案]"
    return {
        "answer":improved_answer,
        "iteration":1,
        "improved":True
    }

def done(state:ImprovementState):
    """完成答案"""
    return {
        "answer":state["answer"]+"[最终答案]"
    }
#================3.定义路由函数===================
#路由函数：觉得继续改进还是完成
def should_improve(state:ImprovementState):
    """决定是否继续改进"""
    quality_ok = state["quality_score"]>=0.8
    within_limit = state["iteration"]<state["max_iterations"]
    print(f"质量分数: {state['quality_score']:.2f}, 迭代次数: {state['iteration']}, 最大迭代次数: {state['max_iterations']}")
    if(quality_ok or not within_limit):
        return "done"
    else:
        return "improve"

#================4.定义图===================
graph = StateGraph(ImprovementState)
graph.add_node("generate",generate)
graph.add_node("check",check)
graph.add_node("improve",improve)
graph.add_node("done",done)

graph.add_edge(START,"generate")
graph.add_edge("generate","check")
graph.add_conditional_edges("check",
    should_improve,{
    "improve":"improve",
    "done":"done"
})
#关键循环，回到检查节点
graph.add_edge("improve","check")
graph.add_edge("done",END)
#编译图
app = graph.compile()

#================5.测试===================
if __name__ == "__main__":
    test_cases = [
        {
            "question": "什么是人工智能？",
            "answer": "",
            "quality_score": 0.0,
            "iteration": 0,
            "max_iterations": 5,
            "improved": False
        },
        {
            "question": "什么是agent？",
            "answer": "",
            "quality_score": 0.0,
            "iteration": 0,
            "max_iterations": 10,
            "improved": False
        }
    ]
    for test_case in test_cases:
        print(f"问题: {test_case['question']}")
        print(f"最大迭代次数: {test_case['max_iterations']}")
        print("-" * 60)
        
        result = app.invoke(test_case)
        
        print(f"最终答案: {result['answer']}")
        print(f"质量分数: {result['quality_score']:.2f}")
        print(f"总迭代次数: {result['iteration']}")
        print("=" * 60)
        print()