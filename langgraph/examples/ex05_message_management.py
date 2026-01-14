"""
消息管理工作流示例
==================
演示 LangGraph 中消息管理的核心概念：
- MessagesState：自动管理消息列表
- add_messages：智能 Reducer（自动追加、去重、保持顺序）
- 如何在状态中添加自定义字段

这是学习 LangGraph 的第五个示例，专注于消息管理，展示了：
1. MessagesState 的基本用法（自动提供 messages 字段）
2. add_messages 的智能处理机制
3. 消息的添加和自动管理
4. 状态中自定义字段的使用

执行流程：
  START → add_user_message → add_ai_message → END
  (演示消息如何自动管理)
"""

from langgraph.graph import StateGraph,START,END,MessagesState
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage,AIMessage,SystemMessage
from typing_extensions import TypedDict
from typing import Annotated
from langchain_core.messages import BaseMessage

#方式1.手动定义消息追加
class MessagesState_Manual(TypedDict):
    messages: Annotated[list[BaseMessage],add_messages]
    message_count: int

class MessageState(MessagesState):
    """消息状态：继承MessagesState，自动获得messages字段"""
    # MessagesState 自动提供 messages: Annotated[list[BaseMessage], add_messages]
    message_count: int

def add_user_message(state:MessageState):
    """添加用户信息节点"""
    return {
        "messages": [HumanMessage(content="你好，我想学习 LangGraph")],
        "message_count": 1  # 更新消息计数
    }
def add_ai_message(state:MessageState):
    """添加AI信息节点"""
    last_message = state["messages"][-1].content if state["messages"] else "无消息"
    #这里模拟的llm消息
    ai_message = f"我收到了你的消息：{last_message}"
    return {
        "messages": [AIMessage(content=ai_message)],
        "message_count": state.get("message_count",0) + 1
    }
def add_system_message(state:MessageState):
    """添加系统信息节点"""
    return {
        "messages": [SystemMessage(content="你是一个LangGraph专家，负责回答用户问题")],
        "message_count": state.get("message_count",0) + 1
    }

graph = StateGraph(MessageState)
# 添加节点
graph.add_node("add_user", add_user_message)
graph.add_node("add_ai", add_ai_message)
graph.add_node("add_system", add_system_message)

# 创建边
graph.add_edge(START, "add_system")      # START → 添加系统消息
graph.add_edge("add_system", "add_user")  # 系统消息 → 添加用户消息
graph.add_edge("add_user", "add_ai")     # 用户消息 → 添加 AI 消息
graph.add_edge("add_ai", END)           # AI 消息 → END
#编译图
app = graph.compile()
#测试
result = app.invoke({})
if __name__ == "__main__":
    # 初始化状态
    initial_state = {
        "messages": [],  # 空消息列表
        "message_count": 0
    }
    
    print("=" * 60)
    print("消息管理示例")
    print("=" * 60)
    print()
    
    # 执行工作流
    result = app.invoke(initial_state)
    
    # 查看结果
    print(f"消息总数: {result['message_count']}")
    print(f"消息列表长度: {len(result['messages'])}")
    print()
    print("消息历史（按顺序）：")
    print("-" * 60)
    
    for i, msg in enumerate(result["messages"], 1):
        msg_type = type(msg).__name__
        print(f"{i}. [{msg_type}] {msg.content}")
    
    print("-" * 60)
    print()
    print("关键点：")
    print("1. MessagesState 自动提供 messages 字段")
    print("2. add_messages 会自动追加新消息，不会覆盖")
    print("3. 消息按添加顺序排列")
    print("4. 可以添加自定义字段（如 message_count）")








