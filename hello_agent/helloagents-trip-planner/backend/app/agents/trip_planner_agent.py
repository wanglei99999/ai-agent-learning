"""
多智能体旅行规划系统模块

本模块是整个项目的核心，实现了基于多 Agent 协作的旅行规划功能
这是本项目最重要的文件，连接 Controller 和 Service，实现 AI 驱动的旅行规划

架构位置：
Controller (routes/trip.py)
    ↓
Agent (本文件) ← AI 决策和服务编排
    ↓
Service (services/) ← 外部 API 调用

核心概念：
- 多智能体协作：4 个专业 Agent 分工合作
- Agent 编排：主 Agent 协调各个子 Agent
- MCP 工具调用：Agent 通过 MCP 调用高德地图 API

Java 对比：
- MultiAgentTripPlanner → 复杂的 Service 层业务逻辑
- Agent 协作 → 微服务之间的调用编排
- 无直接对应 → Java 项目通常没有 AI Agent 层
"""

import json
from typing import Dict, Any, List
# HelloAgents 框架的核心类
from hello_agents import SimpleAgent      # 简单 Agent 实现
from hello_agents.tools import MCPTool    # MCP 工具封装
# 导入服务层
from ..services.llm_service import get_llm
# 导入数据模型
from ..models.schemas import TripRequest, TripPlan, DayPlan, Attraction, Meal, WeatherInfo, Location, Hotel
# 导入配置
from ..config import get_settings

# =============================================================================
# Agent 提示词定义
# 提示词 (Prompt) 是 Agent 的行为指南，类似 Java 中的接口文档或规范
# =============================================================================

# =============================================================================
# Agent 1: 景点搜索专家
# 职责：调用高德地图 API 搜索景点
# =============================================================================
ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据城市和用户偏好搜索合适的景点。

**重要提示:**
你必须使用工具来搜索景点!不要自己编造景点信息!

**工具调用格式:**
使用maps_text_search工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=景点关键词,city=城市名]`

**示例:**
用户: "搜索北京的历史文化景点"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=北京]

用户: "搜索上海的公园"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=公园,city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 参数用逗号分隔
"""

# =============================================================================
# Agent 2: 天气查询专家
# 职责：调用高德地图 API 查询天气
# =============================================================================
WEATHER_AGENT_PROMPT = """你是天气查询专家。你的任务是查询指定城市的天气信息。

**重要提示:**
你必须使用工具来查询天气!不要自己编造天气信息!

**工具调用格式:**
使用maps_weather工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_weather:city=城市名]`

**示例:**
用户: "查询北京天气"
你的回复: [TOOL_CALL:amap_maps_weather:city=北京]

用户: "上海的天气怎么样"
你的回复: [TOOL_CALL:amap_maps_weather:city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
"""

# =============================================================================
# Agent 3: 酒店推荐专家
# 职责：调用高德地图 API 搜索酒店
# =============================================================================
HOTEL_AGENT_PROMPT = """你是酒店推荐专家。你的任务是根据城市和景点位置推荐合适的酒店。

**重要提示:**
你必须使用工具来搜索酒店!不要自己编造酒店信息!

**工具调用格式:**
使用maps_text_search工具搜索酒店时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=城市名]`

**示例:**
用户: "搜索北京的酒店"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=酒店,city=北京]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 关键词使用"酒店"或"宾馆"
"""

# =============================================================================
# Agent 4: 行程规划专家
# 职责：整合其他 Agent 的结果，生成最终旅行计划
# 这个 Agent 不调用工具，只负责数据整合和 JSON 生成
# =============================================================================
PLANNER_AGENT_PROMPT = """你是行程规划专家。你的任务是根据景点信息和天气信息,生成详细的旅行计划。

请严格按照以下JSON格式返回旅行计划:
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 116.397128, "latitude": 39.916527},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "详细地址",
          "location": {"longitude": 116.397128, "latitude": 39.916527},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }
  ],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}
```

**重要提示:**
1. weather_info数组必须包含每一天的天气信息
2. 温度必须是纯数字(不要带°C等单位)
3. 每天安排2-3个景点
4. 考虑景点之间的距离和游览时间
5. 每天必须包含早中晚三餐
6. 提供实用的旅行建议
7. **必须包含预算信息**:
   - 景点门票价格(ticket_price)
   - 餐饮预估费用(estimated_cost)
   - 酒店预估费用(estimated_cost)
   - 预算汇总(budget)包含各项总费用
"""


# =============================================================================
# 多智能体旅行规划系统类
# 这是整个项目的核心类，管理 4 个专业 Agent 的协作
# =============================================================================
class MultiAgentTripPlanner:
    """
    多智能体旅行规划系统
    
    管理 4 个专业 Agent 协作完成旅行规划：
    1. 景点搜索 Agent - 搜索景点
    2. 天气查询 Agent - 查询天气
    3. 酒店推荐 Agent - 搜索酒店
    4. 行程规划 Agent - 整合信息生成计划
    
    类似 Java 的服务编排层，但使用 AI Agent 实现
    """

    def __init__(self):
        """
        初始化多智能体系统
        
        创建 4 个 Agent 并为它们配置工具
        类似 Java: @PostConstruct 初始化方法
        """
        print("开始初始化多智能体旅行规划系统...")

        try:
            # 获取配置和 LLM 实例
            settings = get_settings()
            self.llm = get_llm()

            # ===================================================================
            # 创建共享的 MCP 工具（只创建一次，多个 Agent 共享）
            # MCP 工具封装了高德地图 API 的调用
            # ===================================================================
            print("  - 创建共享MCP工具...")
            self.amap_tool = MCPTool(
                name="amap",
                description="高德地图服务",
                server_command=["uvx", "amap-mcp-server"],  # MCP Server 启动命令
                env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
                auto_expand=True  # 自动展开为多个独立工具
            )

            # ===================================================================
            # 创建 Agent 1: 景点搜索专家
            # ===================================================================
            print("  - 创建景点搜索Agent...")
            self.attraction_agent = SimpleAgent(
                name="景点搜索专家",
                llm=self.llm,                          # 使用的 LLM
                system_prompt=ATTRACTION_AGENT_PROMPT  # Agent 的行为提示词
            )
            self.attraction_agent.add_tool(self.amap_tool)  # 添加高德地图工具

            # ===================================================================
            # 创建 Agent 2: 天气查询专家
            # ===================================================================
            print("  - 创建天气查询Agent...")
            self.weather_agent = SimpleAgent(
                name="天气查询专家",
                llm=self.llm,
                system_prompt=WEATHER_AGENT_PROMPT
            )
            self.weather_agent.add_tool(self.amap_tool)  # 添加高德地图工具

            # ===================================================================
            # 创建 Agent 3: 酒店推荐专家
            # ===================================================================
            print("  - 创建酒店推荐Agent...")
            self.hotel_agent = SimpleAgent(
                name="酒店推荐专家",
                llm=self.llm,
                system_prompt=HOTEL_AGENT_PROMPT
            )
            self.hotel_agent.add_tool(self.amap_tool)  # 添加高德地图工具

            # ===================================================================
            # 创建 Agent 4: 行程规划专家（不需要工具）
            # 这个 Agent 只负责整合其他 Agent 的结果，不直接调用外部 API
            # ===================================================================
            print("  - 创建行程规划Agent...")
            self.planner_agent = SimpleAgent(
                name="行程规划专家",
                llm=self.llm,
                system_prompt=PLANNER_AGENT_PROMPT
            )

            # 打印初始化成功信息
            print(f"多智能体系统初始化成功")
            print(f"   景点搜索Agent: {len(self.attraction_agent.list_tools())} 个工具")
            print(f"   天气查询Agent: {len(self.weather_agent.list_tools())} 个工具")
            print(f"   酒店推荐Agent: {len(self.hotel_agent.list_tools())} 个工具")

        except Exception as e:
            # 初始化失败时打印详细错误信息
            print(f"多智能体系统初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    # =========================================================================
    # 核心方法：生成旅行计划
    # 这是整个 Agent 系统的入口方法，协调 4 个 Agent 完成任务
    # =========================================================================
    def plan_trip(self, request: TripRequest) -> TripPlan:
        """
        使用多智能体协作生成旅行计划
        
        执行流程：
        1. 景点搜索 Agent 搜索景点
        2. 天气查询 Agent 查询天气
        3. 酒店推荐 Agent 搜索酒店
        4. 行程规划 Agent 整合信息生成最终计划
        
        类似 Java 的服务编排方法

        Args:
            request: 旅行请求（包含城市、日期、偏好等）

        Returns:
            TripPlan: 完整的旅行计划
        """
        try:
            # 打印任务信息
            print(f"\n{'='*60}")
            print(f"开始多智能体协作规划旅行...")
            print(f"目的地: {request.city}")
            print(f"日期: {request.start_date} 至 {request.end_date}")
            print(f"天数: {request.travel_days}天")
            print(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
            print(f"{'='*60}\n")

            # ===================================================================
            # 步骤 1: 调用景点搜索 Agent
            # ===================================================================
            print("步骤1: 搜索景点...")
            attraction_query = self._build_attraction_query(request)
            attraction_response = self.attraction_agent.run(attraction_query)
            print(f"景点搜索结果: {attraction_response[:200]}...\n")

            # ===================================================================
            # 步骤 2: 调用天气查询 Agent
            # ===================================================================
            print("步骤2: 查询天气...")
            weather_query = f"请查询{request.city}的天气信息"
            weather_response = self.weather_agent.run(weather_query)
            print(f"天气查询结果: {weather_response[:200]}...\n")

            # ===================================================================
            # 步骤 3: 调用酒店推荐 Agent
            # ===================================================================
            print("步骤3: 搜索酒店...")
            hotel_query = f"请搜索{request.city}的{request.accommodation}酒店"
            hotel_response = self.hotel_agent.run(hotel_query)
            print(f"酒店搜索结果: {hotel_response[:200]}...\n")

            # ===================================================================
            # 步骤 4: 调用行程规划 Agent 整合所有信息
            # ===================================================================
            print("步骤4: 生成行程计划...")
            planner_query = self._build_planner_query(request, attraction_response, weather_response, hotel_response)
            planner_response = self.planner_agent.run(planner_query)
            print(f"行程规划结果: {planner_response[:300]}...\n")

            # ===================================================================
            # 解析最终计划（从 JSON 字符串转换为 TripPlan 对象）
            # ===================================================================
            trip_plan = self._parse_response(planner_response, request)

            print(f"{'='*60}")
            print(f"旅行计划生成完成!")
            print(f"{'='*60}\n")

            return trip_plan

        except Exception as e:
            # 异常处理：如果生成失败，返回备用计划
            print(f"生成旅行计划失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_plan(request)
    
    # =========================================================================
    # 辅助方法：构建查询字符串
    # =========================================================================
    def _build_attraction_query(self, request: TripRequest) -> str:
        """
        构建景点搜索查询
        
        根据用户偏好生成搜索关键词，并构造 Agent 的输入
        
        Args:
            request: 旅行请求
            
        Returns:
            str: 景点搜索查询字符串
        """
        # 提取搜索关键词
        keywords = []
        if request.preferences:
            # 只取第一个偏好作为关键词
            keywords = request.preferences[0]
        else:
            keywords = "景点"

        # 构建查询字符串（包含工具调用指令）
        query = f"请使用amap_maps_text_search工具搜索{request.city}的{keywords}相关景点。\n[TOOL_CALL:amap_maps_text_search:keywords={keywords},city={request.city}]"
        return query

    def _build_planner_query(self, request: TripRequest, attractions: str, weather: str, hotels: str = "") -> str:
        """
        构建行程规划查询
        
        整合所有 Agent 的结果，构造最终规划 Agent 的输入
        
        Args:
            request: 旅行请求
            attractions: 景点搜索结果
            weather: 天气查询结果
            hotels: 酒店搜索结果
            
        Returns:
            str: 行程规划查询字符串
        """
        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**景点信息:**
{attractions}

**天气信息:**
{weather}

**酒店信息:**
{hotels}

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
3. 考虑景点之间的距离和交通方式
4. 返回完整的JSON格式数据
5. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        return query
    
    # =========================================================================
    # 辅助方法：解析 Agent 响应
    # =========================================================================
    def _parse_response(self, response: str, request: TripRequest) -> TripPlan:
        """
        解析 Agent 响应
        
        从 Agent 返回的文本中提取 JSON 数据并转换为 TripPlan 对象
        
        Args:
            response: Agent 响应文本（可能包含 JSON 代码块）
            request: 原始请求
            
        Returns:
            TripPlan: 旅行计划对象
        """
        try:
            # ===================================================================
            # 尝试从响应中提取 JSON
            # Agent 可能返回 Markdown 格式的 JSON 代码块
            # ===================================================================
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                # 直接查找JSON对象
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                raise ValueError("响应中未找到JSON数据")
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 转换为TripPlan对象
            trip_plan = TripPlan(**data)
            
            return trip_plan
            
        except Exception as e:
            # 解析失败时使用备用方案
            print(f"解析响应失败: {str(e)}")
            print(f"   将使用备用方案生成计划")
            return self._create_fallback_plan(request)
    
    # =========================================================================
    # 辅助方法：创建备用计划
    # =========================================================================
    def _create_fallback_plan(self, request: TripRequest) -> TripPlan:
        """
        创建备用计划（当 Agent 失败时）
        
        生成一个简单的默认旅行计划，确保系统不会完全失败
        类似 Java 的降级策略或默认实现
        
        Args:
            request: 旅行请求
            
        Returns:
            TripPlan: 备用旅行计划
        """
        from datetime import datetime, timedelta
        
        # 解析日期
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        
        # 创建每日行程
        days = []
        for i in range(request.travel_days):
            current_date = start_date + timedelta(days=i)
            
            day_plan = DayPlan(
                date=current_date.strftime("%Y-%m-%d"),
                day_index=i,
                description=f"第{i+1}天行程",
                transportation=request.transportation,
                accommodation=request.accommodation,
                attractions=[
                    Attraction(
                        name=f"{request.city}景点{j+1}",
                        address=f"{request.city}市",
                        location=Location(longitude=116.4 + i*0.01 + j*0.005, latitude=39.9 + i*0.01 + j*0.005),
                        visit_duration=120,
                        description=f"这是{request.city}的著名景点",
                        category="景点"
                    )
                    for j in range(2)
                ],
                meals=[
                    Meal(type="breakfast", name=f"第{i+1}天早餐", description="当地特色早餐"),
                    Meal(type="lunch", name=f"第{i+1}天午餐", description="午餐推荐"),
                    Meal(type="dinner", name=f"第{i+1}天晚餐", description="晚餐推荐")
                ]
            )
            days.append(day_plan)
        
        return TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            weather_info=[],
            overall_suggestions=f"这是为您规划的{request.city}{request.travel_days}日游行程,建议提前查看各景点的开放时间。"
        )


# =============================================================================
# 全局多智能体系统实例（单例模式）
# 类似 Java Spring 的 @Service Bean 管理
# =============================================================================
_multi_agent_planner = None


def get_trip_planner_agent() -> MultiAgentTripPlanner:
    """
    获取多智能体旅行规划系统实例（单例模式）
    
    确保整个应用只创建一个 Agent 系统实例，节省资源
    类似 Java: @Autowired private MultiAgentTripPlanner planner;
    
    Returns:
        MultiAgentTripPlanner: 多智能体旅行规划系统实例
    """
    global _multi_agent_planner

    # 单例模式：首次调用时创建，后续直接返回
    if _multi_agent_planner is None:
        _multi_agent_planner = MultiAgentTripPlanner()

    return _multi_agent_planner


# =============================================================================
# 使用说明
# =============================================================================
# 在 Controller 中使用：
#   from app.agents.trip_planner_agent import get_trip_planner_agent
#   
#   agent = get_trip_planner_agent()
#   trip_plan = agent.plan_trip(request)
#
# 多 Agent 协作流程：
#   1. Controller 调用 agent.plan_trip()
#   2. Agent 系统内部协调 4 个子 Agent
#   3. 每个子 Agent 调用 MCP 工具获取数据
#   4. 规划 Agent 整合所有数据生成最终计划
#   5. 返回 TripPlan 对象给 Controller
# =============================================================================

