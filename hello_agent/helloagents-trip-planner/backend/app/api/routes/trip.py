"""
旅行规划 API 路由模块

本模块提供旅行规划的核心 API 接口，类似 Java 的 @RestController
主要功能：
1. 生成旅行计划 - 调用 AI Agent 生成完整的多日旅行行程
2. 健康检查 - 检查 Agent 服务是否正常运行

这是整个应用的核心接口，连接前端和 AI Agent
"""

from fastapi import APIRouter, HTTPException
# 导入数据模型，类似 Java 的 DTO
from ...models.schemas import (
    TripRequest,        # 旅行规划请求模型
    TripPlanResponse,   # 旅行计划响应模型
    ErrorResponse       # 错误响应模型
)
# 导入 Agent 层，这是 AI 核心逻辑
from ...agents.trip_planner_agent import get_trip_planner_agent

# =============================================================================
# 创建路由器实例
# 类似 Java: @RestController + @RequestMapping("/trip")
# =============================================================================
router = APIRouter(prefix="/trip", tags=["旅行规划"])


# =============================================================================
# POST /api/trip/plan - 生成旅行计划接口（核心接口）
# 类似 Java: @PostMapping("/plan")
# 这是整个应用最重要的接口，调用 AI Agent 生成旅行计划
# =============================================================================
@router.post(
    "/plan",
    response_model=TripPlanResponse,  # 响应模型自动验证和序列化
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划"
)
async def plan_trip(request: TripRequest):  # 请求体自动解析为 TripRequest 对象
    """
    生成旅行计划

    Args:
        request: 旅行请求参数

    Returns:
        旅行计划响应
    """
    try:
        # =======================================================================
        # 1. 打印请求信息（用于调试）
        # =======================================================================
        print(f"\n{'='*60}")
        print(f"收到旅行规划请求:")
        print(f"   城市: {request.city}")
        print(f"   日期: {request.start_date} - {request.end_date}")
        print(f"   天数: {request.travel_days}")
        print(f"{'='*60}\n")

        # =======================================================================
        # 2. 获取 AI Agent 实例（单例模式）
        # 类似 Java: @Autowired TripPlannerAgent
        # =======================================================================
        print("获取多智能体系统实例...")
        agent = get_trip_planner_agent()

        # =======================================================================
        # 3. 调用 Agent 生成旅行计划（核心逻辑）
        # Agent 会自动：
        # - 调用高德地图 MCP 工具搜索景点
        # - 调用天气 API 获取天气信息
        # - 使用 LLM 整合信息生成行程
        # =======================================================================
        print("开始生成旅行计划...")
        trip_plan = agent.plan_trip(request)

        print("旅行计划生成成功,准备返回响应\n")

        # =======================================================================
        # 4. 返回响应
        # FastAPI 自动将 TripPlan 对象序列化为 JSON
        # =======================================================================
        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan
        )

    except Exception as e:
        # =======================================================================
        # 异常处理：打印详细错误信息并返回 HTTP 500
        # =======================================================================
        print(f"生成旅行计划失败: {str(e)}")
        import traceback
        traceback.print_exc()  # 打印完整堆栈信息，方便调试
        
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )


# =============================================================================
# GET /api/trip/health - 健康检查接口
# 类似 Java Spring Actuator 的 /actuator/health
# 用于监控系统检查服务是否正常运行
# =============================================================================
@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """
    健康检查：验证 Agent 是否可用
    
    返回 Agent 的基本信息和可用工具数量
    """
    try:
        # 尝试获取 Agent 实例，验证服务是否正常
        agent = get_trip_planner_agent()
        
        # 返回服务状态信息
        return {
            "status": "healthy",                          # 服务状态
            "service": "trip-planner",                    # 服务名称
            "agent_name": agent.agent.name,               # Agent 名称
            "tools_count": len(agent.agent.list_tools())  # 可用工具数量
        }
    except Exception as e:
        # 服务不可用时返回 503 状态码
        raise HTTPException(
            status_code=503,  # 503 Service Unavailable
            detail=f"服务不可用: {str(e)}"
        )

