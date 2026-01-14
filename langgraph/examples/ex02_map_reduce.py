"""
Map-Reduce 模式工作流示例
==========================
演示 LangGraph 中 Map-Reduce 模式的使用：
- 使用 Annotated 和 operator.add 实现自动累加（Reduce 阶段）
- 展示普通字段与累加字段的区别
- 多关卡游戏分数统计场景（Map 多个关卡，Reduce 汇总分数）

这是学习 LangGraph 的第二个示例，展示了：
1. Map-Reduce 模式在 LangGraph 中的应用
2. TypedDict 中 Annotated 字段的用法
3. operator.add 如何实现状态的自动累加（Reduce）
4. 列表字段的累加操作

执行流程：
  START → level1 → level2 → level3 → report → END
  (Map: 多个关卡并行/串行处理 → Reduce: 累加分数)
"""

from langgraph.graph import StateGraph,START,END
from typing_extensions import TypedDict
from typing import Annotated
import operator

class ScoreState(TypedDict):
    player_name:str
    score:Annotated[int,operator.add]
    actions:Annotated[list[str],operator.add]

def level1(state: ScoreState):
  return {"score":10,"actions":["第一关：跳跃，获得10分"]}
def level2(state: ScoreState):
  return {"score":20,"actions":["第二关：攀爬，获得20分"]}

def level3(state: ScoreState):
  return {"score":30,"actions":["第三关：战斗，获得30分"]}

def report(state: ScoreState):
  return {"actions":["游戏结束，总得分：",state["score"]]}

graph = StateGraph(ScoreState)
graph.add_node("level1",level1)
graph.add_node("level2",level2)
graph.add_node("level3",level3)
graph.add_node("report",report)

graph.add_edge(START,"level1")
graph.add_edge("level1","level2")
graph.add_edge("level2","level3")
graph.add_edge("level3","report")
graph.add_edge("report",END)

app = graph.compile()
result = app.invoke({"player_name":"张三","score":0,"actions":[]})
print(result)
