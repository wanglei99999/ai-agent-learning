"""
高德地图 MCP 服务封装模块

本模块封装高德地图的 MCP (Model Context Protocol) 服务，类似 Java 的 @Service 层
主要功能：
1. POI 搜索 - 搜索景点、餐厅等兴趣点
2. 天气查询 - 获取城市天气信息
3. 路线规划 - 规划步行/驾车/公交路线
4. 地理编码 - 地址转经纬度坐标
5. POI 详情 - 获取景点详细信息

核心概念：
- MCP 协议：让 AI Agent 调用外部工具的标准协议
- 单例模式：全局共享同一个服务实例
- 工具调用：通过 MCP 调用高德地图 API

Java 对比：
- AmapService 类 → @Service 注解的服务类
- get_amap_service() → @Autowired 依赖注入
- MCP 工具 → RestTemplate 或 Feign 客户端
"""

from typing import List, Dict, Any, Optional
# HelloAgents 框架的 MCP 工具类
from hello_agents.tools import MCPTool
# 导入配置管理
from ..config import get_settings
# 导入数据模型
from ..models.schemas import Location, POIInfo, WeatherInfo

# =============================================================================
# 全局 MCP 工具实例（单例模式）
# 类似 Java 的静态变量或 Spring 管理的 Bean
# =============================================================================
_amap_mcp_tool = None


def get_amap_mcp_tool() -> MCPTool:
    """
    获取高德地图 MCP 工具实例（单例模式）
    
    单例模式确保整个应用只创建一次 MCP 连接，提高性能
    类似 Java Spring 的 @Bean 单例管理
    
    Returns:
        MCPTool: 高德地图 MCP 工具实例
        
    Raises:
        ValueError: 如果 API Key 未配置
    """
    global _amap_mcp_tool
    
    # 单例模式：如果已创建则直接返回
    if _amap_mcp_tool is None:
        # 获取配置
        settings = get_settings()
        
        # 验证 API Key 是否配置
        if not settings.amap_api_key:
            raise ValueError("高德地图API Key未配置,请在.env文件中设置AMAP_API_KEY")
        
        # =======================================================================
        # 创建 MCP 工具实例
        # MCP (Model Context Protocol) 是让 AI 调用外部工具的标准协议
        # =======================================================================
        _amap_mcp_tool = MCPTool(
            name="amap",                                      # 工具名称
            description="高德地图服务,支持POI搜索、路线规划、天气查询等功能",  # 工具描述
            server_command=["uvx", "amap-mcp-server"],       # MCP Server 启动命令
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key}, # 环境变量（API Key）
            auto_expand=True  # 自动展开为多个独立工具（每个 API 一个工具）
        )
        
        # 打印初始化信息（用于调试）
        print(f"高德地图MCP工具初始化成功")
        print(f"   工具数量: {len(_amap_mcp_tool._available_tools)}")
        
        # 打印可用工具列表（前5个）
        if _amap_mcp_tool._available_tools:
            print("   可用工具:")
            for tool in _amap_mcp_tool._available_tools[:5]:
                print(f"     - {tool.get('name', 'unknown')}")
            if len(_amap_mcp_tool._available_tools) > 5:
                print(f"     ... 还有 {len(_amap_mcp_tool._available_tools) - 5} 个工具")
    
    return _amap_mcp_tool


# =============================================================================
# 高德地图服务类
# 类似 Java 的 @Service 类，封装业务逻辑
# =============================================================================
class AmapService:
    """
    高德地图服务封装类
    
    封装高德地图的各种功能，提供统一的调用接口
    类似 Java: @Service public class AmapService { ... }
    """
    
    def __init__(self):
        """
        初始化服务
        
        获取 MCP 工具实例并保存为实例变量
        类似 Java: @Autowired private MCPTool mcpTool;
        """
        self.mcp_tool = get_amap_mcp_tool()
    
    # =========================================================================
    # POI 搜索方法
    # =========================================================================
    def search_poi(self, keywords: str, city: str, citylimit: bool = True) -> List[POIInfo]:
        """
        搜索 POI（兴趣点）
        
        通过 MCP 调用高德地图的文本搜索 API
        类似 Java: public List<POIInfo> searchPoi(...) { ... }
        
        Args:
            keywords: 搜索关键词（如"故宫"、"餐厅"）
            city: 城市名称（如"北京"）
            citylimit: 是否限制在城市范围内（默认 True）
            
        Returns:
            POI 信息列表（当前返回空列表，需要解析实际数据）
        """
        try:
            # ===================================================================
            # 调用 MCP 工具
            # self.mcp_tool.run() 类似 Java 的 restTemplate.postForObject()
            # ===================================================================
            result = self.mcp_tool.run({
                "action": "call_tool",              # MCP 动作：调用工具
                "tool_name": "maps_text_search",   # 工具名称：文本搜索
                "arguments": {                      # 工具参数
                    "keywords": keywords,
                    "city": city,
                    "citylimit": str(citylimit).lower()  # 转为小写字符串
                }
            })
            
            # ===================================================================
            # 解析结果
            # 注意：MCP 工具返回的是字符串，需要解析为结构化数据
            # ===================================================================
            print(f"POI搜索结果: {result[:200]}...")  # 打印前200字符用于调试
            
            # TODO: 解析实际的 POI 数据
            # 实际项目中应该：
            # 1. 解析 JSON 字符串
            # 2. 提取 POI 列表
            # 3. 转换为 POIInfo 对象
            return []
            
        except Exception as e:
            # 异常处理：打印错误并返回空列表
            print(f"POI搜索失败: {str(e)}")
            return []
    
    # =========================================================================
    # 天气查询方法
    # =========================================================================
    def get_weather(self, city: str) -> List[WeatherInfo]:
        """
        查询城市天气信息
        
        通过 MCP 调用高德地图的天气查询 API
        
        Args:
            city: 城市名称（如"北京"、"上海"）
            
        Returns:
            天气信息列表（包含未来几天的天气预报）
        """
        try:
            # 调用 MCP 工具查询天气
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_weather",  # 高德地图天气工具
                "arguments": {
                    "city": city
                }
            })
            
            print(f"天气查询结果: {result[:200]}...")
            
            # TODO: 解析实际的天气数据
            # 应该解析 JSON 并转换为 WeatherInfo 对象列表
            return []
            
        except Exception as e:
            print(f"天气查询失败: {str(e)}")
            return []
    
    # =========================================================================
    # 路线规划方法
    # =========================================================================
    def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "walking"
    ) -> Dict[str, Any]:
        """
        规划两点之间的路线
        
        支持步行、驾车、公交三种路线类型
        
        Args:
            origin_address: 起点地址（如"北京市朝阳区阜通东大街6号"）
            destination_address: 终点地址
            origin_city: 起点城市（可选，提高准确性）
            destination_city: 终点城市（可选）
            route_type: 路线类型（walking/driving/transit）
            
        Returns:
            路线信息字典（包含距离、时间、路线描述等）
        """
        try:
            # ===================================================================
            # 1. 根据路线类型选择对应的 MCP 工具
            # 高德地图为不同交通方式提供了不同的 API
            # ===================================================================
            tool_map = {
                "walking": "maps_direction_walking_by_address",    # 步行路线
                "driving": "maps_direction_driving_by_address",    # 驾车路线
                "transit": "maps_direction_transit_integrated_by_address"  # 公交路线
            }
            
            # 获取工具名称，默认使用步行
            tool_name = tool_map.get(route_type, "maps_direction_walking_by_address")
            
            # ===================================================================
            # 2. 构建请求参数
            # ===================================================================
            arguments = {
                "origin_address": origin_address,
                "destination_address": destination_address
            }
            
            # 添加城市参数（可选，但能提高地址解析准确性）
            if route_type == "transit":
                # 公交路线必须提供城市参数
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city
            else:
                # 其他路线类型也可以提供城市参数
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city
            
            # ===================================================================
            # 3. 调用 MCP 工具规划路线
            # ===================================================================
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": tool_name,
                "arguments": arguments
            })
            
            print(f"路线规划结果: {result[:200]}...")
            
            # TODO: 解析实际的路线数据
            # 应该提取：距离、时间、详细路线步骤等
            return {}
            
        except Exception as e:
            print(f"路线规划失败: {str(e)}")
            return {}
    
    # =========================================================================
    # 地理编码方法
    # =========================================================================
    def geocode(self, address: str, city: Optional[str] = None) -> Optional[Location]:
        """
        地理编码（地址转经纬度坐标）
        
        将文本地址转换为地理坐标，用于地图标注
        
        Args:
            address: 地址文本（如"北京市朝阳区阜通东大街6号"）
            city: 城市名称（可选，提高准确性）

        Returns:
            Location 对象（包含经纬度），失败返回 None
        """
        try:
            # 构建参数
            arguments = {"address": address}
            if city:
                arguments["city"] = city

            # 调用地理编码工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_geo",  # 地理编码工具
                "arguments": arguments
            })

            print(f"地理编码结果: {result[:200]}...")

            # TODO: 解析实际的坐标数据
            # 应该从结果中提取经纬度并创建 Location 对象
            return None

        except Exception as e:
            print(f"地理编码失败: {str(e)}")
            return None

    # =========================================================================
    # POI 详情查询方法
    # =========================================================================
    def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        获取 POI 详细信息
        
        根据 POI ID 查询详细信息，包括图片、评分、营业时间等

        Args:
            poi_id: POI 唯一标识符（从搜索结果中获取）

        Returns:
            POI 详情字典（包含名称、地址、图片等信息）
        """
        try:
            # 调用 POI 详情查询工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_search_detail",  # POI 详情工具
                "arguments": {
                    "id": poi_id
                }
            })

            print(f"POI详情结果: {result[:200]}...")

            # ===================================================================
            # 解析结果
            # MCP 返回的可能是 JSON 字符串，需要提取和解析
            # ===================================================================
            import json
            import re

            # 尝试从结果字符串中提取 JSON 部分
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                # 解析 JSON 字符串为字典
                data = json.loads(json_match.group())
                return data

            # 如果无法解析，返回原始结果
            return {"raw": result}

        except Exception as e:
            print(f"获取POI详情失败: {str(e)}")
            return {}


# =============================================================================
# 全局服务实例（单例模式）
# 类似 Java Spring 的 @Service Bean 管理
# =============================================================================
_amap_service = None


def get_amap_service() -> AmapService:
    """
    获取高德地图服务实例（单例模式）
    
    确保整个应用只创建一个服务实例，节省资源
    类似 Java: @Autowired private AmapService amapService;
    
    Returns:
        AmapService: 高德地图服务实例
    """
    global _amap_service
    
    # 单例模式：首次调用时创建，后续直接返回
    if _amap_service is None:
        _amap_service = AmapService()
    
    return _amap_service


# =============================================================================
# 使用说明
# =============================================================================
# 在 Controller 或 Agent 中使用：
#   from app.services.amap_service import get_amap_service
#   
#   service = get_amap_service()
#   pois = service.search_poi("故宫", "北京")
#
# MCP 工具调用流程：
#   1. Controller 调用 Service 方法
#   2. Service 通过 MCP 工具调用高德地图 API
#   3. MCP Server 执行实际的 HTTP 请求
#   4. 结果返回给 Service
#   5. Service 解析并返回给 Controller
# =============================================================================

