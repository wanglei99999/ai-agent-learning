"""
条件边工作流示例
==================
演示 LangGraph 中条件边的使用：
- 使用 add_conditional_edges 实现动态路由
- 根据状态条件决定下一步执行哪个节点
- 实现分支逻辑和条件判断

这是学习 LangGraph 的第三个示例，展示了：
1. add_conditional_edges 的基本用法
2. 如何定义路由函数（route_question）
3. 如何根据状态动态选择下一个节点
4. 节点函数（返回字典更新状态）vs 路由函数（返回字符串用于路由）的区别

执行流程：
  START → classify (分析问题，设置 category)
           ↓
         [route_question 路由函数读取 category]
           ↓
         refund / shopping / product / other (根据分类处理)
           ↓
         END

场景说明：
- 客户服务系统：根据客户问题自动分类并路由到对应的处理节点
- 分类节点（classify_question）：分析问题内容，设置 category 到状态
- 路由函数（route_question）：读取 category，返回节点名称用于路由
- 处理节点：根据分类提供相应的服务响应
"""

# 用户将在这里填写代码


from langgraph.graph import StateGraph,START,END
from typing_extensions import TypedDict
from typing import Annotated
import operator

class CustomerState(TypedDict):
  question: str  # 问题
  category: str  # 类别
  answer: str    # 答案
  total_consumption: Annotated[int, operator.add]  # 消费总和（累加）

#处理节点
def handle_refund(state:CustomerState):
  return {"answer":"退款专员，请提供订单号，3个工作日内处理。","total_consumption":-100}
def handle_shopping(state:CustomerState):
  return {"answer":"购物专员，请提供商品名称，我将为您打包下单。","total_consumption":100}
def handle_product(state:CustomerState):
  return {"answer":"产品专员，请提供产品名称，我将为您讲解产品细节。","total_consumption":0}
def handle_other(state:CustomerState):
  return {"answer":"其他专员，请提供问题描述，我将为您解答。","total_consumption":0}
#分类节点
def classify_question(state:CustomerState):
  """根据问题内容自动分类"""
  question = state["question"].lower()
  if "退款" in question or "退货" in question:
    category = "refund"
  elif "购物" in question or "购买" in question:
    category = "shopping"
  elif "产品" in question or "咨询" in question:
    category = "product"
  else:
    category = "other"
  return {"category": category}
#路由函数
def route_question(state:CustomerState):
  return state["category"]

#创建图
graph = StateGraph(CustomerState)
#创建节点
graph.add_node("classify",classify_question)
graph.add_node("refund",handle_refund)
graph.add_node("shopping",handle_shopping)
graph.add_node("product",handle_product)
graph.add_node("other",handle_other)
#创建边
graph.add_edge(START,"classify")
graph.add_conditional_edges("classify",route_question,{
  "refund":"refund",
  "shopping":"shopping",
  "product":"product",
  "other":"other"
})
graph.add_edge("refund", END)
graph.add_edge("shopping", END)
graph.add_edge("product", END)
graph.add_edge("other", END)
#编译图
graph = graph.compile()
# 测试​
test_questions = [
    "我想申请退款",
    "我的快递到哪了？",
    "这个产品怎么使用？",
]
for question in test_questions:
  result = graph.invoke({
    "question": question,
    "category": "",  # 初始为空，会被 classify 节点设置
    "answer": "",    # 初始为空，会被处理节点设置
    "total_consumption": 0  # 初始为0，会被累加
  })
  print(f"问题: {question}")
  print(f"答案: {result['answer']}")
  print(f"总消费: {result['total_consumption']}")
  print("-" * 50)

