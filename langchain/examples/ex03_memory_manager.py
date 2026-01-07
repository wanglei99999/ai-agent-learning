"""
中间件实践 - 动态路由 & 消息管理

【项目概述】
演示 LangChain 中间件的三种类型及其应用场景。

【中间件类型】
1. @wrap_model_call - 包装模型调用，可修改 request/response
2. @before_model - 模型调用前执行，可修改 state
3. @after_model - 模型调用后执行，可修改 state

【实现功能】
1. dynamic_routing (@wrap_model_call)
   - 根据消息复杂度动态选择模型
   - 简单问题 → qwen-plus（便宜）
   - 复杂问题 → qwen-max（强力）
   - 判断条件：消息长度 > 50 或包含关键词

2. trim_messages (@before_model)
   - 模型调用前裁剪消息历史
   - 保留：第1条 + 最近3条
   - 使用 RemoveMessage + REMOVE_ALL_MESSAGES 清空后重建

3. delete_messages (@after_model)
   - 模型调用后删除最早的消息
   - 通过 RemoveMessage(id=msg.id) 删除指定消息

4. SummarizationMiddleware (内置)
   - 自动总结长对话
   - 当消息数 > 5 或 token > 2000 时触发

【关键概念】
- AgentState: Agent 的完整状态（messages + 自定义字段）
- ModelRequest: 单次模型调用的请求包装（包含 state、model、config）
- request.override(): 创建新请求副本并替换指定字段
- Middleware vs Tool: 中间件是后台自动执行，Tool 是模型主动调用
"""

import os
from dotenv import load_dotenv
load_dotenv()

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import ModelRequest,ModelResponse,wrap_model_call
from langchain.messages import HumanMessage
from langchain.agents.middleware import before_model
from langchain.agents.middleware import after_model
from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from langchain.agents import AgentState
from langchain.agents.middleware import SummarizationMiddleware

#创建一个简单模型和一个推理模型
basic_model = init_chat_model(
    "qwen-plus",
    model_provider="openai",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    temperature=0.5
)

reasoner_model = init_chat_model(
    "qwen-max",
    model_provider="openai",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    temperature=0.5
)

#实现推理过程中模型的动态选择 
@wrap_model_call
def dynamic_routing(request:ModelRequest,handler)->ModelResponse:
    """
        根据对话复杂度动态选择模型：
        -简单：qwen-puls
        -复杂：qwen-max
    """
    last_user = ''
    last_len = len(last_user)
    messages = request.state.get("messages",[])
    for m in reversed(messages):
        if(isinstance(m,HumanMessage)):
            if(isinstance(m.content,str)):
                last_user = m.content
                last_len =  len(last_user)
                break
    hard_keyword = ("证明","推导","严谨","规划","多步骤","数学","逻辑","求解")
    is_hard = (
        last_len>50 or 
        any(kw.lower()in last_user.lower() for kw in  hard_keyword ) 
    )

    user_model = reasoner_model if is_hard else basic_model
    return handler(request.override(model=user_model))

@before_model
def trim_messages(state:AgentState,runtime:Runtime)->dict[str,any]|None:
    """模型调用前修剪消息历史，只保留前1条和后3条"""
    messages = state["messages"]
    if len(messages)<=4:
        return None
    first_msg = messages[0]
    new_msg = [first_msg] + messages[-3:]
    print(f"修剪消息：从{len(messages)}条减少到{len(new_msg)}条")

    return {
        'messages':[RemoveMessage(id=REMOVE_ALL_MESSAGES),
        *new_msg
        ]
    }

@after_model
def delete_messages(state:AgentState,runtime:Runtime)->dict|None:
    """调用模型后，删除最早的消息"""
    messages = state['messages']
    if(len(messages)>4):
        removed = [m.id for m in messages[:2]]
        print(f"删除最早的两条消息，id：{removed}")
        return {"messages":[RemoveMessage(id=m.id) for m in messages[:2]]}
    return None

##其实这里定义哪个模型已经没有关系了，因为我们通过wrap_model_call会在model调用前替换一个model
agent = create_agent(
    model= basic_model,
    middleware=[trim_messages,delete_messages,dynamic_routing,
        SummarizationMiddleware(
            model=basic_model,
            tokens = 2000,
            messages = 5 
        )],
    checkpointer = InMemorySaver()
)


response=agent.invoke(
    {"messages":[{"role":"user","content":"你好，我是lee"}]},
    {"configurable":{"thread_id":"1"}}
)
# model_name = response['messages'][-1].response_metadata.get('model_name')
print(response['messages'])
response=agent.invoke(
    {"messages":[{"role":"user","content":"帮我规划一下带记忆体的agent的实现思路，简单一点就行"}]},
    {"configurable":{"thread_id":"1"}}
)

# model_name = response['messages'][-1].response_metadata.get('model_name')
print(response['messages'])

response=agent.invoke(
    {"messages":[{"role":"user","content":"ModelRequest、ModelResponse是什么"}]},
    {"configurable":{"thread_id":"1"}}
)
print(response['messages'])
response=agent.invoke(
    {"messages":[{"role":"user","content":"state和ModelRequest有什么区别"}]},
    {"configurable":{"thread_id":"1"}}
)
print(response['messages'])
response=agent.invoke(
    {"messages":[{"role":"user","content":"你可以更严谨的告诉我吗"}]},
    {"configurable":{"thread_id":"1"}}
)
print(response['messages'])
response=agent.invoke(
    {"messages":[{"role":"user","content":"你知道我是谁吗"}]},
    {"configurable":{"thread_id":"1"}}
)
print(response['messages'])
