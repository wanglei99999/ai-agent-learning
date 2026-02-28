"""
FastAPI 主入口文件

本文件是整个后端服务的入口点，类似 Java Spring Boot 的 Application 主类
通过 HTTP API 暴露 DeepResearchAgent 的功能

主要职责：
1. 创建 FastAPI 应用实例
2. 配置中间件（CORS）
3. 定义 API 路由（/research, /research/stream）
4. 处理请求和响应
5. 错误处理和日志记录

Java 对比：
- create_app() → @SpringBootApplication 主类
- @app.post() → @PostMapping 注解
- ResearchRequest → @RequestBody DTO
- ResearchResponse → ResponseEntity<T>
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Iterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from config import Configuration, SearchAPI
from agent import DeepResearchAgent

# =============================================================================
# 日志配置
# 使用 loguru 库配置日志输出，类似 Java 的 Log4j/Logback
# =============================================================================
# 添加控制台日志处理程序（INFO 级别）
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)

# 添加错误日志文件处理程序（ERROR 级别）
logger.add(
    sink=sys.stderr,
    level="ERROR",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)


# =============================================================================
# 请求/响应数据模型
# 类似 Java 的 DTO (Data Transfer Object)
# =============================================================================
class ResearchRequest(BaseModel):
    """
    研究请求模型
    
    定义用户发起研究请求的数据结构
    类似 Java: @Data public class ResearchRequest { ... }
    """

    topic: str = Field(..., description="Research topic supplied by the user")  # 研究主题（必填）
    search_api: SearchAPI | None = Field(
        default=None,
        description="Override the default search backend configured via env",
    )  # 搜索 API（可选，覆盖默认配置）


class ResearchResponse(BaseModel):
    """
    研究响应模型
    
    定义返回给用户的研究结果数据结构
    类似 Java: @Data public class ResearchResponse { ... }
    """

    report_markdown: str = Field(
        ..., description="Markdown-formatted research report including sections"
    )  # Markdown 格式的研究报告
    
    todo_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured TODO items with summaries and sources",
    )  # TODO 任务列表（包含总结和来源）


# =============================================================================
# 工具函数
# =============================================================================
def _mask_secret(value: Optional[str], visible: int = 4) -> str:
    """
    掩码敏感信息
    
    保留前后几个字符，中间用星号替换
    类似 Java: StringUtils.maskSensitiveData()
    
    Args:
        value: 要掩码的字符串
        visible: 保留的可见字符数
        
    Returns:
        str: 掩码后的字符串
    """
    if not value:
        return "unset"

    if len(value) <= visible * 2:
        return "*" * len(value)

    return f"{value[:visible]}...{value[-visible:]}"


def _build_config(payload: ResearchRequest) -> Configuration:
    """
    构建配置对象
    
    根据请求参数覆盖默认配置
    
    Args:
        payload: 研究请求
        
    Returns:
        Configuration: 配置对象
    """
    overrides: Dict[str, Any] = {}

    # 如果请求中指定了搜索 API，覆盖默认配置
    if payload.search_api is not None:
        overrides["search_api"] = payload.search_api

    return Configuration.from_env(overrides=overrides)


# =============================================================================
# FastAPI 应用创建函数
# 类似 Java Spring Boot 的 @SpringBootApplication 主类
# =============================================================================
def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例
    
    配置中间件、路由和生命周期事件
    类似 Java: @SpringBootApplication public class Application { ... }
    
    Returns:
        FastAPI: 应用实例
    """
    app = FastAPI(title="HelloAgents Deep Researcher")

    # 配置 CORS 中间件（允许跨域请求）
    # 类似 Java: @Configuration public class CorsConfig { ... }
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],          # 允许所有来源
        allow_credentials=True,       # 允许携带凭证
        allow_methods=["*"],          # 允许所有 HTTP 方法
        allow_headers=["*"],          # 允许所有请求头
    )

    # =========================================================================
    # 生命周期事件：启动时打印配置信息
    # 类似 Java: @PostConstruct 注解
    # =========================================================================
    @app.on_event("startup")
    def log_startup_configuration() -> None:
        """应用启动时打印配置信息"""
        config = Configuration.from_env()

        if config.llm_provider == "ollama":
            base_url = config.sanitized_ollama_url()
        elif config.llm_provider == "lmstudio":
            base_url = config.lmstudio_base_url
        else:
            base_url = config.llm_base_url or "unset"

        logger.info(
            "DeepResearch configuration loaded: provider=%s model=%s base_url=%s search_api=%s "
            "max_loops=%s fetch_full_page=%s tool_calling=%s strip_thinking=%s api_key=%s",
            config.llm_provider,
            config.resolved_model() or "unset",
            base_url,
            (config.search_api.value if isinstance(config.search_api, SearchAPI) else config.search_api),
            config.max_web_research_loops,
            config.fetch_full_page,
            config.use_tool_calling,
            config.strip_thinking_tokens,
            _mask_secret(config.llm_api_key),
        )

    # =========================================================================
    # API 路由定义
    # =========================================================================
    @app.get("/healthz")
    def health_check() -> Dict[str, str]:
        """
        健康检查接口
        
        类似 Java: @GetMapping("/healthz")
        
        Returns:
            Dict: 状态信息
        """
        return {"status": "ok"}

    @app.post("/research", response_model=ResearchResponse)
    def run_research(payload: ResearchRequest) -> ResearchResponse:
        """
        执行研究（阻塞模式）
        
        接收研究主题，执行完整的研究流程，返回最终报告
        类似 Java: @PostMapping("/research")
        
        Args:
            payload: 研究请求
            
        Returns:
            ResearchResponse: 研究结果
            
        Raises:
            HTTPException: 配置错误或执行失败
        """
        try:
            # 构建配置并创建 Agent
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)
            
            # 执行研究（阻塞模式）
            result = agent.run(payload.topic)
        except ValueError as exc:  # Likely due to unsupported configuration
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guardrail
            raise HTTPException(status_code=500, detail="Research failed") from exc

        # 转换 TODO 任务为字典格式
        todo_payload = [
            {
                "id": item.id,
                "title": item.title,
                "intent": item.intent,
                "query": item.query,
                "status": item.status,
                "summary": item.summary,
                "sources_summary": item.sources_summary,
                "note_id": item.note_id,
                "note_path": item.note_path,
            }
            for item in result.todo_items
        ]

        return ResearchResponse(
            report_markdown=(result.report_markdown or result.running_summary or ""),
            todo_items=todo_payload,
        )

    @app.post("/research/stream")
    def stream_research(payload: ResearchRequest) -> StreamingResponse:
        """
        执行研究（流式模式）
        
        接收研究主题，以流式方式返回研究进度和结果
        适用于需要实时反馈的前端界面
        类似 Java: @PostMapping("/research/stream") 返回 Flux<T>
        
        Args:
            payload: 研究请求
            
        Returns:
            StreamingResponse: SSE 流式响应
            
        Raises:
            HTTPException: 配置错误
        """
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        def event_iterator() -> Iterator[str]:
            """
            事件迭代器
            
            生成 SSE (Server-Sent Events) 格式的事件流
            """
            try:
                # 执行研究（流式模式）
                for event in agent.run_stream(payload.topic):
                    # 将事件转换为 SSE 格式
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:  # pragma: no cover - defensive guardrail
                logger.exception("Streaming research failed")
                error_payload = {"type": "error", "detail": str(exc)}
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

        # 返回流式响应
        return StreamingResponse(
            event_iterator(),
            media_type="text/event-stream",  # SSE 媒体类型
            headers={
                "Cache-Control": "no-cache",   # 禁用缓存
                "Connection": "keep-alive",    # 保持连接
            },
        )

    return app


# =============================================================================
# 应用实例
# =============================================================================
app = create_app()


# =============================================================================
# 主入口
# 直接运行此文件时启动开发服务器
# =============================================================================
if __name__ == "__main__":
    import uvicorn

    # 启动 Uvicorn 服务器
    # 类似 Java: SpringApplication.run(Application.class, args)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",      # 监听所有网卡
        port=8000,           # 监听端口
        reload=True,         # 开发模式：代码变更自动重载
        log_level="info"     # 日志级别
    )
