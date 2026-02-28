"""
POI（兴趣点）API 路由模块

本模块提供 POI 相关的 RESTful API 接口，类似 Java 的 @RestController
主要功能：
1. POI 详情查询 - 根据 ID 获取景点详细信息
2. POI 搜索 - 根据关键词搜索景点
3. 景点图片获取 - 从 Unsplash 获取景点图片
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
# 导入服务层，类似 Java 的 @Autowired Service
from ...services.amap_service import get_amap_service
from ...services.unsplash_service import get_unsplash_service

# =============================================================================
# 创建路由器实例
# 类似 Java: @RestController + @RequestMapping("/poi")
# =============================================================================
router = APIRouter(prefix="/poi", tags=["POI"])


# =============================================================================
# 响应模型定义
# 局部响应模型，仅在此文件使用
# =============================================================================
class POIDetailResponse(BaseModel):
    """
    POI 详情响应模型
    
    类似 Java 的响应 DTO
    """
    success: bool                      # 是否成功
    message: str                       # 消息
    data: Optional[dict] = None        # POI 详情数据（字典格式）


# =============================================================================
# GET /api/poi/detail/{poi_id} - POI 详情查询接口
# 类似 Java: @GetMapping("/detail/{poi_id}")
# {poi_id} 是路径参数，类似 @PathVariable
# =============================================================================
@router.get(
    "/detail/{poi_id}",
    response_model=POIDetailResponse,
    summary="获取POI详情",
    description="根据POI ID获取详细信息,包括图片"
)
async def get_poi_detail(poi_id: str):  # poi_id 从 URL 路径自动提取
    """
    获取POI详情
    
    Args:
        poi_id: POI ID
        
    Returns:
        POI详情响应
    """
    try:
        # 获取高德地图服务实例
        amap_service = get_amap_service()
        
        # 调用服务层获取 POI 详情（通过 MCP 调用高德地图 API）
        result = amap_service.get_poi_detail(poi_id)
        
        # 返回响应
        return POIDetailResponse(
            success=True,
            message="获取POI详情成功",
            data=result
        )
        
    except Exception as e:
        # 异常处理：打印日志并抛出 HTTP 异常
        print(f"获取POI详情失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取POI详情失败: {str(e)}"
        )


# =============================================================================
# GET /api/poi/search - POI 搜索接口
# 类似 Java: @GetMapping("/search")
# keywords 和 city 是查询参数，类似 @RequestParam
# =============================================================================
@router.get(
    "/search",
    summary="搜索POI",
    description="根据关键词搜索POI"
)
async def search_poi(
    keywords: str,           # 必填参数：搜索关键词
    city: str = "北京"      # 可选参数：城市，默认北京
):
    """
    搜索POI

    Args:
        keywords: 搜索关键词
        city: 城市名称

    Returns:
        搜索结果
    """
    try:
        # 获取服务实例
        amap_service = get_amap_service()
        
        # 调用服务层搜索 POI
        result = amap_service.search_poi(keywords, city)

        # 返回搜索结果（字典格式）
        return {
            "success": True,
            "message": "搜索成功",
            "data": result
        }

    except Exception as e:
        print(f"搜索POI失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"搜索POI失败: {str(e)}"
        )


# =============================================================================
# GET /api/poi/photo - 景点图片获取接口
# 类似 Java: @GetMapping("/photo")
# 从 Unsplash 图库获取景点图片，用于美化行程展示
# =============================================================================
@router.get(
    "/photo",
    summary="获取景点图片",
    description="根据景点名称从Unsplash获取图片"
)
async def get_attraction_photo(name: str):  # name: 景点名称
    """
    获取景点图片

    Args:
        name: 景点名称

    Returns:
        图片URL
    """
    try:
        # 获取 Unsplash 图片服务实例
        unsplash_service = get_unsplash_service()

        # 首先尝试搜索：景点名 + China landmark（提高准确度）
        photo_url = unsplash_service.get_photo_url(f"{name} China landmark")

        if not photo_url:
            # 如果没找到，降级为只用景点名称搜索
            photo_url = unsplash_service.get_photo_url(name)

        # 返回图片 URL
        return {
            "success": True,
            "message": "获取图片成功",
            "data": {
                "name": name,
                "photo_url": photo_url  # 可能为 None（未找到）
            }
        }

    except Exception as e:
        print(f"获取景点图片失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取景点图片失败: {str(e)}"
        )

