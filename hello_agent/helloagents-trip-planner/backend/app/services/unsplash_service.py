"""
Unsplash 图片服务模块

本模块封装 Unsplash 图库 API，用于获取景点图片，类似 Java 的 @Service 层
主要功能：
1. 搜索图片 - 根据关键词搜索相关图片
2. 获取图片 URL - 返回单张图片的 URL

与 amap_service 的区别：
- amap_service 使用 MCP 协议
- unsplash_service 使用传统 HTTP API（requests 库）

Java 对比：
- UnsplashService → @Service 类
- requests.get() → RestTemplate.getForObject()
- 单例模式 → Spring Bean 管理
"""

# Python HTTP 请求库，类似 Java 的 RestTemplate
import requests
from typing import List, Optional
# 导入配置管理
from ..config import get_settings

# =============================================================================
# Unsplash 图片服务类
# 类似 Java 的 @Service 类
# =============================================================================
class UnsplashService:
    """
    Unsplash 图片服务封装类
    
    封装 Unsplash API 调用，提供图片搜索功能
    类似 Java: @Service public class UnsplashService { ... }
    """
    
    def __init__(self):
        """
        初始化服务
        
        从配置中读取 API Key 并设置基础 URL
        类似 Java: @PostConstruct 初始化方法
        """
        settings = get_settings()
        self.access_key = settings.unsplash_access_key  # API 密钥
        self.base_url = "https://api.unsplash.com"     # API 基础 URL
    
    # =========================================================================
    # 图片搜索方法
    # =========================================================================
    def search_photos(self, query: str, per_page: int = 5) -> List[dict]:
        """
        搜索 Unsplash 图片
        
        使用传统 HTTP API 调用（不是 MCP）
        类似 Java: public List<Map> searchPhotos(...) { ... }
        
        Args:
            query: 搜索关键词（如"故宫 China landmark"）
            per_page: 每页返回数量（默认 5 张）
            
        Returns:
            图片信息列表（包含 URL、描述、摄影师等）
        """
        try:
            # ===================================================================
            # 1. 构建 HTTP 请求
            # 类似 Java: restTemplate.getForObject(url, String.class)
            # ===================================================================
            url = f"{self.base_url}/search/photos"
            params = {
                "query": query,              # 搜索关键词
                "per_page": per_page,        # 返回数量
                "client_id": self.access_key # API 密钥（作为查询参数）
            }
            
            # 发送 GET 请求，设置 10 秒超时
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()  # 如果 HTTP 状态码不是 2xx，抛出异常
            
            # ===================================================================
            # 2. 解析 JSON 响应
            # ===================================================================
            data = response.json()        # 将 JSON 字符串转为 Python 字典
            results = data.get("results", [])  # 获取搜索结果数组
            
            # ===================================================================
            # 3. 提取需要的图片信息
            # ===================================================================
            photos = []
            for photo in results:
                photos.append({
                    "id": photo.get("id"),                                      # 图片 ID
                    "url": photo.get("urls", {}).get("regular"),              # 常规尺寸 URL
                    "thumb": photo.get("urls", {}).get("thumb"),              # 缩略图 URL
                    "description": photo.get("description") or photo.get("alt_description"),  # 描述
                    "photographer": photo.get("user", {}).get("name")         # 摄影师名称
                })
            
            return photos
            
        except Exception as e:
            # 异常处理：打印错误并返回空列表
            print(f"Unsplash搜索失败: {str(e)}")
            return []
    
    # =========================================================================
    # 单张图片获取方法
    # =========================================================================
    def get_photo_url(self, query: str) -> Optional[str]:
        """
        获取单张图片的 URL
        
        内部调用 search_photos()，只返回第一张图片的 URL
        类似 Java: public String getPhotoUrl(...) { ... }

        Args:
            query: 搜索关键词（如"故宫"）

        Returns:
            图片 URL 字符串，如果未找到则返回 None
        """
        # 搜索图片（只要 1 张）
        photos = self.search_photos(query, per_page=1)
        
        # 如果找到图片，返回第一张的 URL
        if photos:
            return photos[0].get("url")
        
        # 未找到图片
        return None


# =============================================================================
# 全局服务实例（单例模式）
# 类似 Java Spring 的 @Service Bean 管理
# =============================================================================
_unsplash_service = None


def get_unsplash_service() -> UnsplashService:
    """
    获取 Unsplash 服务实例（单例模式）
    
    确保整个应用只创建一个服务实例
    类似 Java: @Autowired private UnsplashService unsplashService;
    
    Returns:
        UnsplashService: Unsplash 图片服务实例
    """
    global _unsplash_service
    
    # 单例模式：首次调用时创建，后续直接返回
    if _unsplash_service is None:
        _unsplash_service = UnsplashService()
    
    return _unsplash_service


# =============================================================================
# 使用说明
# =============================================================================
# 在 Controller 或 Agent 中使用：
#   from app.services.unsplash_service import get_unsplash_service
#   
#   service = get_unsplash_service()
#   photo_url = service.get_photo_url("故宫 China landmark")
#
# 环境变量配置（.env 文件）：
#   UNSPLASH_ACCESS_KEY=your_access_key
#
# 与 MCP 的区别：
#   - amap_service: 使用 MCP 协议，适合 AI Agent 调用
#   - unsplash_service: 使用传统 HTTP API，简单直接
# =============================================================================

