"""
FastAPI主应用入口文件

本文件是整个后端服务的入口点，类似于 Java Spring Boot 的 Application 主类。
主要职责：
1. 创建 FastAPI 应用实例
2. 配置中间件（如 CORS 跨域）
3. 注册路由模块
4. 定义生命周期事件（启动/关闭）
5. 提供基础端点（健康检查等）
"""

# FastAPI: Python 高性能异步 Web 框架，类似 Java 的 Spring Boot
from fastapi import FastAPI
# CORSMiddleware: 处理跨域请求，类似 Java 的 @CrossOrigin 或 WebMvcConfigurer
from fastapi.middleware.cors import CORSMiddleware
# 从配置模块导入配置相关函数
from ..config import get_settings, validate_config, print_config
# 导入各个路由模块，类似 Java 的 @RestController
from .routes import trip, poi, map as map_routes

# 获取配置实例（单例模式），类似 Java 的 @Value 或 @ConfigurationProperties
settings = get_settings()

# =============================================================================
# 创建 FastAPI 应用实例
# 类似 Java: @SpringBootApplication + Swagger 配置
# FastAPI 会自动生成 API 文档，无需像 Java 那样配置 springfox/springdoc
# =============================================================================
app = FastAPI(
    title=settings.app_name,           # API 文档标题
    version=settings.app_version,      # API 版本号
    description="基于HelloAgents框架的智能旅行规划助手API",  # API 描述
    docs_url="/docs",                  # Swagger UI 地址（自动生成）
    redoc_url="/redoc"                 # ReDoc 文档地址（另一种文档风格）
)

# =============================================================================
# 配置 CORS（跨域资源共享）
# 允许前端（如 Vue/React）从不同端口/域名访问后端 API
# 类似 Java Spring 的 WebMvcConfigurer.addCorsMappings()
# =============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),  # 允许的前端域名列表
    allow_credentials=True,   # 允许携带 Cookie
    allow_methods=["*"],      # 允许所有 HTTP 方法（GET/POST/PUT/DELETE 等）
    allow_headers=["*"],      # 允许所有请求头
)

# =============================================================================
# 注册路由模块
# 类似 Java Spring 的 @ComponentScan 自动扫描 Controller
# 但这里是手动注册，更加显式和可控
# prefix="/api" 表示所有路由都会加上 /api 前缀
# =============================================================================
app.include_router(trip.router, prefix="/api")       # 旅行规划相关接口 /api/trip/*
app.include_router(poi.router, prefix="/api")        # POI 景点搜索接口 /api/poi/*
app.include_router(map_routes.router, prefix="/api") # 地图服务接口 /api/map/*


# =============================================================================
# 应用生命周期事件 - 启动时执行
# 类似 Java 的 @PostConstruct 或实现 ApplicationRunner 接口
# async def: 异步函数，类似 Java 的 CompletableFuture
# =============================================================================
@app.on_event("startup")  # 装饰器：标记为启动事件处理函数
async def startup_event():
    """应用启动事件：初始化配置、验证环境、打印启动信息"""
    print("\n" + "="*60)
    print(f"{settings.app_name} v{settings.app_version}")
    print("="*60)
    
    # 打印配置信息
    print_config()
    
    # 验证配置
    try:
        validate_config()
        print("\n配置验证通过")
    except ValueError as e:
        print(f"\n配置验证失败:\n{e}")
        print("\n请检查.env文件并确保所有必要的配置项都已设置")
        raise
    
    print("\n" + "="*60)
    print("API文档: http://localhost:8000/docs")
    print("ReDoc文档: http://localhost:8000/redoc")
    print("="*60 + "\n")


# =============================================================================
# 应用生命周期事件 - 关闭时执行
# 类似 Java 的 @PreDestroy 或实现 DisposableBean 接口
# 用于清理资源、关闭连接等
# =============================================================================
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件：清理资源、打印关闭信息"""
    print("\n" + "="*60)
    print("应用正在关闭...")
    print("="*60 + "\n")


# =============================================================================
# API 端点定义
# @app.get("/") 类似 Java 的 @GetMapping("/")
# @app.post("/") 类似 Java 的 @PostMapping("/")
# 返回 dict 会自动序列化为 JSON，类似 @ResponseBody
# =============================================================================
@app.get("/")  # HTTP GET 请求，路径为 /
async def root():
    """根路径：返回服务基本信息"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")  # 健康检查端点，用于负载均衡器/K8s 探针
async def health():
    """健康检查：返回服务运行状态，类似 Spring Actuator 的 /health"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version
    }


# =============================================================================
# 直接运行此文件时启动服务器
# 类似 Java 的 public static void main(String[] args)
# uvicorn 是 ASGI 服务器，类似 Java 的 Tomcat/Netty
# =============================================================================
if __name__ == "__main__":
    import uvicorn  # ASGI 服务器，高性能异步服务器
    
    # 启动服务器，类似 SpringApplication.run()
    uvicorn.run(
        "app.api.main:app",  # 应用路径：模块名:应用实例名
        host=settings.host,      # 监听地址，0.0.0.0 表示所有网卡
        port=settings.port,      # 监听端口，默认 8000
        reload=True              # 热重载：代码修改后自动重启（开发模式）
    )

