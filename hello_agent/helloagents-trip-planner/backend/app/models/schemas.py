"""
数据模型定义模块

本模块定义所有 API 的请求和响应数据模型，类似 Java 的 DTO (Data Transfer Object)
使用 Pydantic BaseModel 实现：
1. 自动数据验证（类型检查、范围检查等）
2. 自动 JSON 序列化/反序列化
3. 自动生成 API 文档（OpenAPI/Swagger）
4. 提供字段描述和示例

Java 对比：
- BaseModel → POJO + @Valid 注解
- Field(...) → @NotNull + @ApiModelProperty
- field_validator → @AssertTrue 自定义验证
"""

from typing import List, Optional, Union
# Pydantic: Python 数据验证库，类似 Java Bean Validation
from pydantic import BaseModel, Field, field_validator
from datetime import date


# =============================================================================
# 请求模型 (Request DTOs)
# 定义 API 接收的请求参数结构，类似 Java 的 @RequestBody
# =============================================================================

class TripRequest(BaseModel):
    """
    旅行规划请求模型
    
    用于 POST /api/trip/plan 接口
    类似 Java: public class TripRequest { ... }
    """
    # Field(...) 中的 ... 表示必填字段，类似 @NotNull
    # ge=1, le=30 表示范围验证，类似 @Min(1) @Max(30)
    city: str = Field(..., description="目的地城市", example="北京")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", example="2025-06-01")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", example="2025-06-03")
    travel_days: int = Field(..., description="旅行天数", ge=1, le=30, example=3)  # 1-30天范围验证
    transportation: str = Field(..., description="交通方式", example="公共交通")
    accommodation: str = Field(..., description="住宿偏好", example="经济型酒店")
    # default=[] 表示可选字段，类似 Java 的默认值
    preferences: List[str] = Field(default=[], description="旅行偏好标签", example=["历史文化", "美食"])
    free_text_input: Optional[str] = Field(default="", description="额外要求", example="希望多安排一些博物馆")
    
    # Pydantic 配置：定义 JSON Schema 示例，用于 API 文档展示
    # 类似 Java Swagger 的 @ApiModelProperty(example = "...")
    class Config:
        json_schema_extra = {
            "example": {
                "city": "北京",
                "start_date": "2025-06-01",
                "end_date": "2025-06-03",
                "travel_days": 3,
                "transportation": "公共交通",
                "accommodation": "经济型酒店",
                "preferences": ["历史文化", "美食"],
                "free_text_input": "希望多安排一些博物馆"
            }
        }


class POISearchRequest(BaseModel):
    """POI（兴趣点）搜索请求模型"""
    keywords: str = Field(..., description="搜索关键词", example="故宫")
    city: str = Field(..., description="城市", example="北京")
    citylimit: bool = Field(default=True, description="是否限制在城市范围内")  # 默认 True


class RouteRequest(BaseModel):
    """路线规划请求模型"""
    origin_address: str = Field(..., description="起点地址", example="北京市朝阳区阜通东大街6号")
    destination_address: str = Field(..., description="终点地址", example="北京市海淀区上地十街10号")
    # Optional[str] 表示可选字段，类似 Java 的 @Nullable
    origin_city: Optional[str] = Field(default=None, description="起点城市")
    destination_city: Optional[str] = Field(default=None, description="终点城市")
    route_type: str = Field(default="walking", description="路线类型: walking/driving/transit")  # 默认步行


# =============================================================================
# 响应模型 (Response DTOs)
# 定义 API 返回的数据结构，类似 Java 的响应 DTO
# =============================================================================

class Location(BaseModel):
    """地理位置坐标模型"""
    longitude: float = Field(..., description="经度")  # float 自动验证数字类型
    latitude: float = Field(..., description="纬度")


class Attraction(BaseModel):
    """
    景点信息模型
    
    包含景点的详细信息，用于行程规划
    """
    name: str = Field(..., description="景点名称")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")  # 嵌套模型，类似 Java 的组合对象
    visit_duration: int = Field(..., description="建议游览时间(分钟)")
    description: str = Field(..., description="景点描述")
    category: Optional[str] = Field(default="景点", description="景点类别")
    rating: Optional[float] = Field(default=None, description="评分")
    # default_factory=list 表示默认空列表，避免可变默认值问题
    photos: Optional[List[str]] = Field(default_factory=list, description="景点图片URL列表")
    poi_id: Optional[str] = Field(default="", description="POI ID")
    image_url: Optional[str] = Field(default=None, description="图片URL")
    ticket_price: int = Field(default=0, description="门票价格(元)")


class Meal(BaseModel):
    """餐饮信息模型"""
    type: str = Field(..., description="餐饮类型: breakfast/lunch/dinner/snack")  # 早/午/晚餐/小吃
    name: str = Field(..., description="餐饮名称")
    address: Optional[str] = Field(default=None, description="地址")
    location: Optional[Location] = Field(default=None, description="经纬度坐标")
    description: Optional[str] = Field(default=None, description="描述")
    estimated_cost: int = Field(default=0, description="预估费用(元)")


class Hotel(BaseModel):
    """酒店信息模型"""
    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="酒店地址")
    location: Optional[Location] = Field(default=None, description="酒店位置")
    price_range: str = Field(default="", description="价格范围")
    rating: str = Field(default="", description="评分")
    distance: str = Field(default="", description="距离景点距离")
    type: str = Field(default="", description="酒店类型")
    estimated_cost: int = Field(default=0, description="预估费用(元/晚)")


class DayPlan(BaseModel):
    """
    单日行程模型
    
    包含一天的完整行程安排：景点、餐饮、住宿等
    """
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_index: int = Field(..., description="第几天(从0开始)")  # 0表示第1天
    description: str = Field(..., description="当日行程描述")
    transportation: str = Field(..., description="交通方式")
    accommodation: str = Field(..., description="住宿")
    hotel: Optional[Hotel] = Field(default=None, description="推荐酒店")
    # 列表类型，包含多个景点和餐饮
    attractions: List[Attraction] = Field(default=[], description="景点列表")
    meals: List[Meal] = Field(default=[], description="餐饮列表")


class WeatherInfo(BaseModel):
    """天气信息模型"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_weather: str = Field(default="", description="白天天气")
    night_weather: str = Field(default="", description="夜间天气")
    # Union[int, str] 表示可以是整数或字符串，类似 Java 的泛型
    day_temp: Union[int, str] = Field(default=0, description="白天温度")
    night_temp: Union[int, str] = Field(default=0, description="夜间温度")
    wind_direction: str = Field(default="", description="风向")
    wind_power: str = Field(default="", description="风力")

    # ==========================================================================
    # 自定义验证器：解析温度字符串
    # 类似 Java 的 @AssertTrue 或自定义验证器
    # @field_validator 装饰器标记验证方法
    # mode='before' 表示在 Pydantic 类型转换之前执行
    # ==========================================================================
    @field_validator('day_temp', 'night_temp', mode='before')
    @classmethod
    def parse_temperature(cls, v):
        """
        解析温度字符串，移除单位符号
        
        将 "25°C" 或 "25℃" 转换为整数 25
        
        Args:
            v: 原始温度值（可能是字符串或整数）
            
        Returns:
            int: 解析后的温度整数值
        """
        if isinstance(v, str):
            # 移除各种温度单位符号
            v = v.replace('°C', '').replace('℃', '').replace('°', '').strip()
            try:
                return int(v)  # 转换为整数
            except ValueError:
                return 0  # 转换失败返回 0
        return v  # 已经是整数，直接返回


class Budget(BaseModel):
    """预算信息模型"""
    total_attractions: int = Field(default=0, description="景点门票总费用")
    total_hotels: int = Field(default=0, description="酒店总费用")
    total_meals: int = Field(default=0, description="餐饮总费用")
    total_transportation: int = Field(default=0, description="交通总费用")
    total: int = Field(default=0, description="总费用")  # 所有费用之和


class TripPlan(BaseModel):
    """
    完整旅行计划模型
    
    包含整个旅行的所有信息：行程、天气、预算等
    这是 Agent 生成的最终结果
    """
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: List[DayPlan] = Field(..., description="每日行程")  # 多日行程列表
    weather_info: List[WeatherInfo] = Field(default=[], description="天气信息")
    overall_suggestions: str = Field(..., description="总体建议")  # Agent 生成的旅行建议
    budget: Optional[Budget] = Field(default=None, description="预算信息")


class TripPlanResponse(BaseModel):
    """
    旅行计划 API 响应模型
    
    统一的响应格式，包含成功标志、消息和数据
    类似 Java 的 ResponseEntity<TripPlan>
    """
    success: bool = Field(..., description="是否成功")  # true/false
    message: str = Field(default="", description="消息")  # 成功或错误消息
    data: Optional[TripPlan] = Field(default=None, description="旅行计划数据")  # 实际数据


class POIInfo(BaseModel):
    """POI（兴趣点）信息模型"""
    id: str = Field(..., description="POI ID")  # 高德地图的 POI 唯一标识
    name: str = Field(..., description="名称")
    type: str = Field(..., description="类型")  # 如：景点、餐厅、酒店等
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="经纬度坐标")
    tel: Optional[str] = Field(default=None, description="电话")


class POISearchResponse(BaseModel):
    """POI 搜索 API 响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[POIInfo] = Field(default=[], description="POI列表")  # POI 数组


class RouteInfo(BaseModel):
    """路线规划信息模型"""
    distance: float = Field(..., description="距离(米)")  # 浮点数，单位：米
    duration: int = Field(..., description="时间(秒)")  # 整数，单位：秒
    route_type: str = Field(..., description="路线类型")  # walking/driving/transit
    description: str = Field(..., description="路线描述")  # 文字描述


class RouteResponse(BaseModel):
    """路线规划 API 响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[RouteInfo] = Field(default=None, description="路线信息")


class WeatherResponse(BaseModel):
    """天气查询 API 响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: List[WeatherInfo] = Field(default=[], description="天气信息")  # 多日天气列表


# =============================================================================
# 错误响应模型
# 统一的错误响应格式，类似 Java 的异常处理
# =============================================================================

class ErrorResponse(BaseModel):
    """
    错误响应模型
    
    当 API 发生错误时返回此格式
    类似 Java 的 @ExceptionHandler 返回的错误对象
    """
    success: bool = Field(default=False, description="是否成功")  # 固定为 False
    message: str = Field(..., description="错误消息")  # 错误描述
    error_code: Optional[str] = Field(default=None, description="错误代码")  # 可选的错误码

