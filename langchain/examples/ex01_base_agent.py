"""
第一个 Agent 示例--我们调用的是qwen-plus模型，兼容的是openAi接口
==================
演示 LangChain Agent 的基本用法：
- 创建一个带工具的 Agent
- 让 Agent 自主决定是否调用工具
- 获取 Agent 的回答
- 当前使用的是langchain v1.2.0

"""
import os
from dotenv import load_dotenv
load_dotenv()

from langchain.agents import create_agent
from dataclasses import dataclass
from langchain.tools import tool,ToolRuntime
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.structured_output import ToolStrategy

#1.定义系统propmt词
SYSTEM_PROMPT = """You are an expert weather forecaster, who speaks in puns.

You have access to two tools:

- get_weather_for_location: use this to get the weather for a specific location
- get_user_location: use this to get the user's location

If a user asks you for the weather, make sure you know the location.
If you can tell from the question that they mean wherever they are, 
use the get_user_location tool to find their location."""

#2.创建工具
#通过@tool装饰器定义agent工具
@tool 
def get_weather_for_location(city:str)->str:
    """Get weather for a give city."""
    return f"It's always sunny in {city}!"
@dataclass
class Context:
    """Custom runtime context schema."""
    user_id:str

@tool 
def get_user_location(runtime:ToolRuntime[Context])->str:
    """Retrieve user infomation based on user ID."""
    user_id = runtime.context.user_id
    return "Florida" if user_id=="1" else "SF"

#3.配置模型
model = init_chat_model(
    "qwen-plus",
    model_provider="openai",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    temperature=0.5
)
# 4.定义响应格式
#格式化输出，限制ai按照我们的要求进行输出，结合ToolStrategy使用
@dataclass
class ResponseFormat:
    """Response schema for the agent."""
    punny_response: str
    weather_conditions: str|None=None
#5.添加记忆功能
#这里使用记忆体中间件
checkpointer = InMemorySaver()
#6.创建并运行代理
agent = create_agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_user_location,get_weather_for_location],
    context_schema=Context,
    response_format = ToolStrategy(ResponseFormat),
    checkpointer = checkpointer
)
config = {"configurable":{"thread_id":"1"}}
response = agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather outside?"}]},
    config=config,
    context=Context(user_id="1")
)

print(response['structured_response'])
# ResponseFormat(
#     punny_response="Florida is still having a 'sun-derful' day! The sunshine is playing 'ray-dio' hits all day long! I'd say it's the perfect weather for some 'solar-bration'! If you were hoping for rain, I'm afraid that idea is all 'washed up' - the forecast remains 'clear-ly' brilliant!",
#     weather_conditions="It's always sunny in Florida!"
# )


# Note that we can continue the conversation using the same `thread_id`.
response = agent.invoke(
    {"messages": [{"role": "user", "content": "thank you!"}]},
    config=config,
    context=Context(user_id="1")
)

print(response['structured_response'])
# ResponseFormat(
#     punny_response="You're 'thund-erfully' welcome! It's always a 'breeze' to help you stay 'current' with the weather. I'm just 'cloud'-ing around waiting to 'shower' you with more forecasts whenever you need them. Have a 'sun-sational' day in the Florida sunshine!",
#     weather_conditions=None
# )

