"""
基于 LangChain 构建的数据分析 Agent，使用 Sub-Agent 架构处理用户的数据查询需求。

【架构说明】
主 Agent (tools: writeFormula, ast)
    └── writeFormula (Sub-Agent，生成 pandas 代码)
            └── ast (PythonAstREPLTool，执行代码)

【执行流程】
1. 用户提问 → 主 Agent 调用 writeFormula
2. writeFormula (Sub-Agent) 生成 pandas 代码
3. 主 Agent 调用 ast 执行代码
4. 主 Agent 通过 res_format 返回结构化结果


- Sub-Agent 模式：writeFormula 内部创建独立 Agent，执行完毕后返回控制权
- PythonAstREPLTool：通过 locals 参数注入 telco 数据表
- ToolStrategy：将 Pydantic 模型包装为工具，实现结构化输出
- response_format 本质是 tool_call，模型通过调用"格式化工具"返回结构化数据
"""

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field
from langchain.agents.structured_output import ToolStrategy
import os
from pathlib import Path
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_experimental.tools import PythonAstREPLTool
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

# ==================== 数据集 ====================
# 本次使用数据采用 Telco 数据集，该数据集是Kaggle分享的一个高分数据集（1788 votes）

# 获取当前文件所在目录，构建数据文件的绝对路径
current_dir = Path(__file__).parent
data_path = current_dir / '../data/telco.csv'

telco = pd.read_csv(data_path)
pd.set_option('max_colwidth', 50)


# ==================== 导入工具并验证 ====================
# PythonAstREPLTool 支持通过 locals 参数将外部变量注入工具上下文，让工具直接识别并操作该变量
# 可通过该工具辅助大模型理解 telco 表，并对 telco 表进行解读，
# 并且可以直接执行针对该数据集的 Python 数据分析代码，实现数据解读 + 代码执行的一体化操作

ast = PythonAstREPLTool(locals={"telco": telco})


# ==================== 配置大模型 ====================
model = init_chat_model(
    "qwen-plus",
    model_provider="openai",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    temperature=0.5
)

class WriteFormulaFormat(BaseModel):
    """对用户的数据查询需求编写对应公式"""
    search_formula:str = Field(...,description="对用户的数据查询需求编写对应公式，只允许使用pandas和内置库代码，不返回其它内容。")

@tool
def writeFormula(query:str)->str:
    """
    对用户的需求query，编写对应查询计算的代码公式
    :param query: str,必填-用户输入的查询需求
    :return: search_formula:str, 对用户的数据查询需求编写对应公式，只允许返回pandas和内置库代码，不返回其它内容
    """
    system_prompt =f"""
    你是一位专业的数据分析师，你会耐心思考然后解答用户提出的问题：
    1.你可以访问一个名为“telco”的pandas数据表，你可以使用telco.head().to_markdown()查看数据集的基本信息
    2.首先，请根据用户提出的问题，编写python代码来回答，记住只返回代码，不返回其它内容，而且只允许使用pandas和内置库
    3.仅返回计算需要的代码公式
    """
    conversation = [
        {
            "role":"user","content":query
        }
    ]

    f_agent = create_agent(
        model = model,
        tools = [ast],
        system_prompt  = system_prompt ,
        response_format = ToolStrategy(WriteFormulaFormat)
    )

    formula_res = f_agent.invoke({"messages":conversation})

    search_formula = formula_res['structured_response'].search_formula
    
    return search_formula

# ==================== 编写数据分析代码解释器 ====================

system_prompt = f"""
    你是一位专业的数据分析师，你会耐心思考然后解答用户提出的问题：
    1.你可以访问一个名为“telco”的pandas数据表，你可以使用telco.head().to_markdown()查看数据集的基本信息
    2.首先，请根据用户提出的问题，编写python代码来回答，记住只返回代码，不返回其它内容，而且只允许使用pandas和内置库
    3.将生成的代码送入ast（PythonASTREPLTool）工具进行运行解读，最后返回结果
"""

class res_format(BaseModel):
    """对用户的查Query进行回答，分别为用户问题，计算公式和计算结果"""
    query:str = Field(...,description="对用户的query进行精炼总结 ")
    formula:str = Field(...,description="计算查询的python代码公式")
    result:str = Field(...,description="根据formula计算的结果")

agent = create_agent(
    model=model,
    tools=[ast,writeFormula],
    system_prompt=system_prompt,
    response_format=res_format
)
response =  agent.invoke(
    {"messages":[{"role":"user","content":"我有一张表，名为telco，请帮我计算MonthLyCharges字段的均值。"}]}
)

print(response)
#最后返回值，注意：其实最后的res_format也是用tool调用的，底层还是tool机制
'''
{
    'messages': [
        HumanMessage(
            content='我有一张表，名为telco，请帮我计算MonthLyCharges字段的均值。',
            additional_kwargs={},
            response_metadata={},
            id='60e0f5ec-20f6-4db8-a3f9-dcd0bf8f0b09'
        ),
        AIMessage(
            content='',
            additional_kwargs={'refusal': None},
            response_metadata={
                'token_usage': {
                    'completion_tokens': 24,
                    'prompt_tokens': 558,
                    'total_tokens': 582,
                    'completion_tokens_details': None,
                    'prompt_tokens_details': {'audio_tokens': None, 'cached_tokens': 0}
                },
                'model_provider': 'openai',
                'model_name': 'qwen-plus',
                'system_fingerprint': None,
                'id': 'chatcmpl-82cfcf40-82dd-9c48-b4c7-14823f1da9eb',
                'finish_reason': 'tool_calls',
                'logprobs': None
            },
            id='lc_run--019b98d4-114b-7750-98f4-b9c7961b97f4-0',
            tool_calls=[
                {
                    'name': 'writeFormula',
                    'args': {'query': '计算MonthLyCharges字段的均值'},
                    'id': 'call_7068c19755e143878231fb',
                    'type': 'tool_call'
                }
            ],
            invalid_tool_calls=[],
            usage_metadata={
                'input_tokens': 558,
                'output_tokens': 24,
                'total_tokens': 582,
                'input_token_details': {'cache_read': 0},
                'output_token_details': {}
            }
        ),
        ToolMessage(
            content="telco['MonthlyCharges'].mean()",
            name='writeFormula',
            id='ea08e318-d609-4772-9b49-db473d580a78',
            tool_call_id='call_7068c19755e143878231fb'
        ),
        AIMessage(
            content='',
            additional_kwargs={'refusal': None},
            response_metadata={
                'token_usage': {
                    'completion_tokens': 26,
                    'prompt_tokens': 607,
                    'total_tokens': 633,
                    'completion_tokens_details': None,
                    'prompt_tokens_details': {'audio_tokens': None, 'cached_tokens': 0}
                },
                'model_provider': 'openai',
                'model_name': 'qwen-plus',
                'system_fingerprint': None,
                'id': 'chatcmpl-7775aafb-3184-99c6-97e7-d4f52d585d0b',
                'finish_reason': 'tool_calls',
                'logprobs': None
            },
            id='lc_run--019b98d4-1e67-7e12-a34b-e390685dd9cf-0',
            tool_calls=[
                {
                    'name': 'python_repl_ast',
                    'args': {'query': "telco['MonthlyCharges'].mean()"},
                    'id': 'call_e615447b964b4b5890da49',
                    'type': 'tool_call'
                }
            ],
            invalid_tool_calls=[],
            usage_metadata={
                'input_tokens': 607,
                'output_tokens': 26,
                'total_tokens': 633,
                'input_token_details': {'cache_read': 0},
                'output_token_details': {}
            }
        ),
        ToolMessage(
            content='64.76169246059918',
            name='python_repl_ast',
            id='cd53f677-54d1-41f9-8622-dfc66ae1337b',
            tool_call_id='call_e615447b964b4b5890da49'
        ),
        AIMessage(
            content='',
            additional_kwargs={'refusal': None},
            response_metadata={
                'token_usage': {
                    'completion_tokens': 59,
                    'prompt_tokens': 667,
                    'total_tokens': 726,
                    'completion_tokens_details': None,
                    'prompt_tokens_details': {'audio_tokens': None, 'cached_tokens': 0}
                },
                'model_provider': 'openai',
                'model_name': 'qwen-plus',
                'system_fingerprint': None,
                'id': 'chatcmpl-2c7bc12e-f2ac-9525-978f-dc58fa9daf27',
                'finish_reason': 'tool_calls',
                'logprobs': None
            },
            id='lc_run--019b98d4-2526-7d92-89b9-a1587ffd9513-0',
            tool_calls=[
                {
                    'name': 'res_format',
                    'args': {
                        'query': '计算MonthLyCharges字段的均值',
                        'formula': "telco['MonthlyCharges'].mean()",
                        'result': '64.76169246059918'
                    },
                    'id': 'call_41cbe00a449f449ca191ea',
                    'type': 'tool_call'
                }
            ],
            invalid_tool_calls=[],
            usage_metadata={
                'input_tokens': 667,
                'output_tokens': 59,
                'total_tokens': 726,
                'input_token_details': {'cache_read': 0},
                'output_token_details': {}
            }
        ),
        ToolMessage(
            content="Returning structured response: query='计算MonthLyCharges字段的均值' formula=\"telco['MonthlyCharges'].mean()\" result='64.76169246059918'",
            name='res_format',
            id='31648445-b91d-4315-ad56-49a73f053bc4',
            tool_call_id='call_41cbe00a449f449ca191ea'
        )
    ],
    'structured_response': res_format(
        query='计算MonthLyCharges字段的均值',
        formula="telco['MonthlyCharges'].mean()",
        result='64.76169246059918'
    )
}

'''