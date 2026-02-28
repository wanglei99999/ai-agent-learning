"""
地图服务 API 路由模块

本模块提供地图相关的 RESTful API 接口，类似 Java Spring 的 @RestController
主要功能：
1. POI（兴趣点）搜索 - 搜索景点、餐厅等
2. 天气查询 - 获取城市天气信息
3. 路线规划 - 规划两点之间的行驶/步行/公交路线
4. 健康检查 - 检查地图服务状态

所有接口都调用高德地图 MCP 服务获取实时数据
"""

# FastAPI 核心组件
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
# 导入数据模型（请求/响应结构），类似 Java 的 DTO
from ...models.schemas import (
    POISearchRequest,     # POI 搜索请求模型
    POISearchResponse,    # POI 搜索响应模型
    RouteRequest,         # 路线规划请求模型
    RouteResponse,        # 路线规划响应模型
    WeatherResponse       # 天气查询响应模型
)
# 导入高德地图服务，类似 Java 的 @Autowired Service
from ...services.amap_service import get_amap_service

# =============================================================================
# 创建路由器实例
# 类似 Java: @RestController + @RequestMapping("/map")
# prefix="/map" 表示所有接口都以 /api/map 开头（main.py 中已加 /api 前缀）
# tags 用于 Swagger 文档分组
# =============================================================================
router = APIRouter(prefix="/map", tags=["地图服务"])


# =============================================================================
# GET /api/map/poi - POI 搜索接口
# 类似 Java: @GetMapping("/poi")
# response_model: 自动验证响应数据并生成文档，类似 @ApiResponse
# Query(...): 查询参数，... 表示必填，类似 @RequestParam(required=true)
# =============================================================================
@router.get(
    "/poi",                              # 接口路径
    response_model=POISearchResponse,     # 响应模型（自动序列化和文档生成）
    summary="搜索POI",                    # 接口简短描述
    description="根据关键词搜索POI(兴趣点)"  # 接口详细描述
)
async def search_poi(
    # Query 参数定义，类似 @RequestParam
    keywords: str = Query(..., description="搜索关键词", example="故宫"),
    city: str = Query(..., description="城市", example="北京"),
    citylimit: bool = Query(True, description="是否限制在城市范围内")
):
    """
    搜索POI
    
    Args:
        keywords: 搜索关键词
        city: 城市
        citylimit: 是否限制在城市范围内
        
    Returns:
        POI搜索结果
    """
    try:
        # 获取高德地图服务实例（单例模式）
        service = get_amap_service()
        
        # 调用服务层方法搜索 POI（底层通过 MCP 调用高德地图 API）
        pois = service.search_poi(keywords, city, citylimit)
        
        # 返回响应对象（FastAPI 自动序列化为 JSON）
        # 类似 Java: return ResponseEntity.ok(response)
        return POISearchResponse(
            success=True,
            message="POI搜索成功",
            data=pois
        )
        
    except Exception as e:
        # 异常处理：打印日志并抛出 HTTP 异常
        # HTTPException 类似 Java 的 @ExceptionHandler
        print(f"POI搜索失败: {str(e)}")
        raise HTTPException(
            status_code=500,              # HTTP 状态码
            detail=f"POI搜索失败: {str(e)}"  # 错误详情
        )


# =============================================================================
# GET /api/map/weather - 天气查询接口
# 类似 Java: @GetMapping("/weather")
# =============================================================================
@router.get(
    "/weather",
    response_model=WeatherResponse,
    summary="查询天气",
    description="查询指定城市的天气信息"
)
async def get_weather(
    city: str = Query(..., description="城市名称", example="北京")
):
    """
    查询天气
    
    Args:
        city: 城市名称
        
    Returns:
        天气信息
    """
    try:
        # 获取服务实例
        service = get_amap_service()
        
        # 调用服务层查询天气（通过 MCP 调用高德地图天气 API）
        weather_info = service.get_weather(city)
        
        # 返回天气信息
        return WeatherResponse(
            success=True,
            message="天气查询成功",
            data=weather_info
        )
        
    except Exception as e:
        print(f"天气查询失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"天气查询失败: {str(e)}"
        )


# =============================================================================
# POST /api/map/route - 路线规划接口
# 类似 Java: @PostMapping("/route")
# request: RouteRequest - 请求体参数，类似 @RequestBody
# =============================================================================
@router.post(
    "/route",
    response_model=RouteResponse,
    summary="规划路线",
    description="规划两点之间的路线"
)
async def plan_route(request: RouteRequest):  # 请求体自动解析为 RouteRequest 对象
    """
    规划路线
    
    Args:
        request: 路线规划请求
        
    Returns:
        路线信息
    """
    try:
        # 获取服务实例
        service = get_amap_service()
        
        # 调用服务层规划路线（支持驾车/步行/公交等多种方式）
        # 底层通过 MCP 调用高德地图路线规划 API
        route_info = service.plan_route(
            origin_address=request.origin_address,           # 起点地址
            destination_address=request.destination_address, # 终点地址
            origin_city=request.origin_city,                 # 起点城市
            destination_city=request.destination_city,       # 终点城市
            route_type=request.route_type                    # 路线类型（driving/walking/transit）
        )
        
        # 返回路线规划结果
        return RouteResponse(
            success=True,
            message="路线规划成功",
            data=route_info
        )
        
    except Exception as e:
        print(f"路线规划失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"路线规划失败: {str(e)}"
        )


# =============================================================================
# GET /api/map/health - 健康检查接口
# 类似 Java Spring Actuator 的 /actuator/health
# 用于监控系统、负载均衡器探测服务是否正常
# =============================================================================
@router.get(
    "/health",
    summary="健康检查",
    description="检查地图服务是否正常"
)
async def health_check():
    """健康检查：验证 MCP 服务连接和可用工具数量"""
    try:
        # 尝试获取服务实例，验证 MCP 连接是否正常
        service = get_amap_service()
        
        # 返回服务状态信息
        return {
            "status": "healthy",                                      # 服务状态
            "service": "map-service",                                 # 服务名称
            "mcp_tools_count": len(service.mcp_tool._available_tools) # 可用的 MCP 工具数量
        }
    except Exception as e:
        # 服务不可用时返回 503 状态码
        raise HTTPException(
            status_code=503,  # 503 Service Unavailable
            detail=f"服务不可用: {str(e)}"
        )

