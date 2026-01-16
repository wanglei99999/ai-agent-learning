"""
Supervisor 模式 - 多 Agent 协作 (模拟)
==========================================

核心概念：
- 一个 Supervisor 负责任务分配
- 多个专业 Agent 负责执行
- 根据问题类型路由到不同 Agent

应用场景：
客服系统 - 技术支持、销售咨询、账单查询三个专业 Agent

流程：
  START → Supervisor (分析问题) → [路由] → 专业 Agent → END
                                    ↓
                        tech_support / sales / billing

多agent或者路由前的函数都是有内容的，路由节点的函数是只负责分发，决定往哪调用的状态是在路由前就更新好了的
"""

import operator
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END


#1. 定义状态
class SupervisorState(TypedDict):
    """Supervisor 状态"""
    question: str           # 用户问题
    next_agent: str         # 下一个要执行的 Agent
    answer: str             # 最终答案
    route_reason: str       # 路由原因（用于学习）


#2. 定义工具函数
def check_system_status(component: str) -> str:
    """检查系统状态（模拟）"""
    status_map = {
        "server": "服务器运行正常，CPU 使用率 45%",
        "database": "数据库连接正常，响应时间 20ms",
        "network": "网络状态良好，延迟 15ms"
    }
    return status_map.get(component, "未知组件")


def get_product_info(product_name: str) -> str:
    """获取产品信息（模拟）"""
    products = {
        "基础版": "基础版：99元/月，包含基础功能，适合个人用户",
        "专业版": "专业版：299元/月，包含高级功能，适合团队使用",
        "企业版": "企业版：999元/月，包含全部功能，提供专属支持"
    }
    return products.get(product_name, "产品不存在")


def query_billing(order_id: str) -> str:
    """查询账单（模拟）"""
    return f"订单 {order_id}：已支付，金额 299元，发票已开具"


#3. 定义专业 Agent 节点
def tech_support_agent(state: SupervisorState):
    """技术支持 Agent"""
    question = state["question"]
    
    print("\n[技术支持 Agent] 处理中...")
    
    # 根据问题关键词决定检查什么
    if "服务器" in question or "系统" in question:
        result = check_system_status("server")
        answer = f"技术支持：{result}"
    elif "数据库" in question:
        result = check_system_status("database")
        answer = f"技术支持：{result}"
    elif "网络" in question:
        result = check_system_status("network")
        answer = f"技术支持：{result}"
    else:
        answer = "技术支持：请详细描述您遇到的技术问题"
    
    print(f"   回答: {answer}")
    return {"answer": answer}


def sales_agent(state: SupervisorState):
    """销售 Agent"""
    question = state["question"]
    
    print("\n[销售 Agent] 处理中...")
    
    # 检查问题中提到的产品
    for product in ["基础版", "专业版", "企业版"]:
        if product in question:
            info = get_product_info(product)
            answer = f"销售顾问：{info}"
            print(f"   回答: {answer}")
            return {"answer": answer}
    
    # 没有具体产品，给出产品列表
    answer = "销售顾问：我们提供基础版、专业版、企业版三种套餐，您想了解哪个？"
    print(f"   回答: {answer}")
    return {"answer": answer}


def billing_agent(state: SupervisorState):
    """账单 Agent"""
    question = state["question"]
    
    print("\n[账单 Agent] 处理中...")
    
    # 简单模拟：如果问题中有数字，当作订单号
    import re
    order_match = re.search(r'\d+', question)
    
    if order_match:
        order_id = order_match.group()
        result = query_billing(order_id)
        answer = f"账单专员：{result}"
    else:
        answer = "账单专员：请提供您的订单号，我来帮您查询"
    
    print(f"   回答: {answer}")
    return {"answer": answer}


# ============ 4. Supervisor 节点 ============
def supervisor(state: SupervisorState):
    """
    Supervisor 节点 - 分析问题并决定派给哪个 Agent
    """
    question = state["question"]
    
    print(f"\n[Supervisor] 分析问题: {question}")
    
    # 定义关键词
    tech_keywords = ["错误", "bug", "崩溃", "系统", "服务器", "数据库", "网络", "500", "404"]
    sales_keywords = ["价格", "购买", "产品", "套餐", "多少钱", "基础版", "专业版", "企业版"]
    billing_keywords = ["发票", "支付", "退款", "账单", "订单"]
    
    # 根据关键词决定路由
    if any(kw in question for kw in tech_keywords):
        next_agent = "tech_support"
        reason = f"检测到技术关键词，路由到技术支持"
    elif any(kw in question for kw in sales_keywords):
        next_agent = "sales"
        reason = f"检测到销售关键词，路由到销售顾问"
    elif any(kw in question for kw in billing_keywords):
        next_agent = "billing"
        reason = f"检测到账单关键词，路由到账单专员"
    else:
        # 默认路由到销售
        next_agent = "sales"
        reason = "未匹配到特定关键词，默认路由到销售顾问"
    
    print(f"   决策: {reason}")
    print(f"   路由到: {next_agent}")
    
    return {
        "next_agent": next_agent,
        "route_reason": reason
    }


#5. 定义路由函数
def route_to_agent(state: SupervisorState) -> Literal["tech_support", "sales", "billing"]:
    """
    根据 Supervisor 的决策路由到对应的 Agent
    """
    return state["next_agent"]


# ============ 6. 构建图 ============
workflow = StateGraph(SupervisorState)

# 添加节点
workflow.add_node("supervisor", supervisor)
workflow.add_node("tech_support", tech_support_agent)
workflow.add_node("sales", sales_agent)
workflow.add_node("billing", billing_agent)

# 添加边
workflow.add_edge(START, "supervisor")

# 条件边：根据 Supervisor 决策路由
workflow.add_conditional_edges(
    "supervisor",
    route_to_agent,
    {
        "tech_support": "tech_support",
        "sales": "sales",
        "billing": "billing"
    }
)

# 所有 Agent 执行完后结束
workflow.add_edge("tech_support", END)
workflow.add_edge("sales", END)
workflow.add_edge("billing", END)

# 编译
app = workflow.compile()


# ============ 7. 测试 ============
if __name__ == "__main__":
    print("=" * 60)
    print("Supervisor 模式 - 多 Agent 协作示例")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        "我遇到500错误，系统无法访问",
        "专业版多少钱？",
        "我需要查询订单12345的发票",
        "数据库连接失败",
        "你们有什么产品？"
    ]
    
    for i, question in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"测试 {i}: {question}")
        print("=" * 60)
        
        # 执行
        result = app.invoke({
            "question": question,
            "next_agent": "",
            "answer": "",
            "route_reason": ""
        })
        
        # 打印结果
        print(f"\n最终答案: {result['answer']}")
    
    print("\n" + "=" * 60)
    print("Supervisor 模式说明：")
    print("1. Supervisor 分析问题关键词")
    print("2. 根据关键词决定路由到哪个专业 Agent")
    print("3. 专业 Agent 处理问题并返回答案")
    print("4. 流程结束")
    print()
    print("优势：")
    print("- 职责分离：每个 Agent 专注自己的领域")
    print("- 易于扩展：添加新 Agent 只需增加节点和路由规则")
    print("- 逻辑清晰：Supervisor 统一管理路由逻辑")
