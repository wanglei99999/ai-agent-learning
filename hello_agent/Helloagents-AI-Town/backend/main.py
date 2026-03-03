"""
赛博小镇 FastAPI 后端主程序

这是整个后端服务的入口文件，定义了所有 API 接口
使用 FastAPI 框架提供 RESTful API 服务

主要功能：
1. NPC 对话接口 - 处理玩家与 NPC 的实时对话
2. NPC 状态接口 - 获取和刷新 NPC 的自主状态
3. 记忆管理接口 - 查询和清空 NPC 记忆
4. 好感度接口 - 查询和设置 NPC 好感度
5. 生命周期管理 - 应用启动和关闭时的初始化和清理
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from config import settings
from models import (
    ChatRequest, ChatResponse, 
    NPCStatusResponse, NPCListResponse, NPCInfo
)
from agents import get_npc_manager
from state_manager import get_state_manager

# ===================================================================
# 应用生命周期管理
# ===================================================================
# 使用 FastAPI 的 lifespan 上下文管理器
# 在应用启动时初始化服务，在关闭时清理资源

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    管理应用的启动和关闭流程
    - 启动时：验证配置、初始化管理器、启动定时任务
    - 关闭时：停止定时任务、清理资源
    
    Args:
        app: FastAPI 应用实例
    """
    # ===== 启动阶段 =====
    print("\n" + "="*60)
    print("赛博小镇后端服务启动中...")
    print("="*60)
    
    # 验证配置文件
    # 检查必要的环境变量是否已设置（如 LLM_API_KEY）
    settings.validate()
    
    # 初始化 NPC 管理器
    # 创建所有 NPC 的 Agent 实例、记忆管理器和好感度系统
    npc_manager = get_npc_manager()
    
    # 初始化并启动状态管理器
    # 状态管理器负责定时批量生成 NPC 的自主对话
    state_manager = get_state_manager(settings.NPC_UPDATE_INTERVAL)
    await state_manager.start()
    
    print("\n所有服务已启动!")
    print(f"API地址: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"API文档: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    print("="*60 + "\n")
    
    # yield 之前是启动逻辑，之后是关闭逻辑
    yield
    
    # ===== 关闭阶段 =====
    print("\n正在关闭服务...")
    # 停止状态管理器的定时任务
    await state_manager.stop()
    print("服务已关闭\n")

# ===================================================================
# 创建 FastAPI 应用实例
# ===================================================================

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="赛博小镇 - 基于HelloAgents的AI NPC对话系统",
    lifespan=lifespan  # 绑定生命周期管理函数
)

# ===================================================================
# CORS 跨域配置
# ===================================================================
# 允许前端从不同域名访问 API
# 开发环境通常允许所有来源，生产环境应限制具体域名

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # 允许的来源列表
    allow_credentials=True,                # 允许携带凭证（cookies）
    allow_methods=["*"],                   # 允许所有 HTTP 方法
    allow_headers=["*"],                   # 允许所有请求头
)

# ===================================================================
# 全局管理器实例
# ===================================================================
# 使用全局变量缓存管理器实例，避免重复创建

npc_manager = None
state_manager = None

def get_managers():
    """
    获取管理器实例
    
    使用懒加载模式，第一次调用时创建实例，后续调用直接返回缓存的实例
    
    Returns:
        tuple: (npc_manager, state_manager)
    """
    global npc_manager, state_manager
    if npc_manager is None:
        npc_manager = get_npc_manager()
    if state_manager is None:
        state_manager = get_state_manager()
    return npc_manager, state_manager

# ===================================================================
# API 路由定义
# ===================================================================

# -------------------------------------------------------------------
# 基础接口
# -------------------------------------------------------------------

@app.get("/")
async def root():
    """
    根路径 - API 信息
    
    返回 API 的基本信息和可用端点列表
    用于快速了解 API 的功能和使用方式
    
    Returns:
        dict: API 信息和端点列表
    """
    return {
        "service": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "features": ["AI对话", "NPC记忆系统", "好感度系统", "批量状态更新"],
        "endpoints": {
            "docs": "/docs",
            "chat": "/chat",
            "npcs": "/npcs",
            "npcs_status": "/npcs/status",
            "npc_memories": "/npcs/{npc_name}/memories",
            "npc_affinity": "/npcs/{npc_name}/affinity",
            "all_affinities": "/affinities"
        }
    }

@app.get("/health")
async def health_check():
    """
    健康检查接口
    
    用于监控服务是否正常运行
    可被 负载均衡器或监控系统调用
    
    Returns:
        dict: 健康状态
    """
    return {"status": "healthy", "timestamp": "now"}

# -------------------------------------------------------------------
# 对话接口
# -------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
async def chat_with_npc(request: ChatRequest):
    """
    与 NPC 对话接口
    
    处理玩家与指定 NPC 的实时对话
    使用独立的 Agent 处理每个 NPC 的对话逻辑
    包含记忆检索、好感度更新等完整流程
    
    Args:
        request: 对话请求（包含 NPC 名称和玩家消息）
        
    Returns:
        ChatResponse: NPC 的回复内容
        
    Raises:
        HTTPException: NPC 不存在或对话处理失败
    """
    npc_mgr, _ = get_managers()
    
    # 验证 NPC 是否存在
    npc_info = npc_mgr.get_npc_info(request.npc_name)
    if not npc_info:
        raise HTTPException(
            status_code=404,
            detail=f"NPC '{request.npc_name}' 不存在"
        )
    
    try:
        # 调用 NPC Agent 处理对话
        # 这会触发完整的对话流程：记忆检索 -> 生成回复 -> 好感度分析 -> 保存记忆
        response_text = npc_mgr.chat(request.npc_name, request.message)
        
        return ChatResponse(
            npc_name=request.npc_name,
            npc_title=npc_info["title"],
            message=response_text,
            success=True
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"对话处理失败: {str(e)}"
        )

# -------------------------------------------------------------------
# NPC 信息接口
# -------------------------------------------------------------------

@app.get("/npcs", response_model=NPCListResponse)
async def list_npcs():
    """
    获取所有 NPC 列表
    
    返回所有 NPC 的基本信息（名称、职位、性格等）
    
    Returns:
        NPCListResponse: NPC 列表和总数
    """
    npc_mgr, _ = get_managers()
    
    npcs_data = npc_mgr.get_all_npcs()
    npcs = [NPCInfo(**npc) for npc in npcs_data]
    
    return NPCListResponse(
        npcs=npcs,
        total=len(npcs)
    )

# -------------------------------------------------------------------
# NPC 状态接口
# -------------------------------------------------------------------

@app.get("/npcs/status", response_model=NPCStatusResponse)
async def get_npcs_status():
    """
    获取所有 NPC 的当前状态
    
    返回批量生成的 NPC 对话内容，用于显示 NPC 的自主行为
    这些对话不是玩家触发的，而是 NPC 的自主状态展示
    
    Returns:
        NPCStatusResponse: 所有 NPC 的当前对话、上次更新时间、下次更新倒计时
    """
    _, state_mgr = get_managers()
    
    state = state_mgr.get_current_state()
    
    return NPCStatusResponse(
        dialogues=state["dialogues"],
        last_update=state["last_update"],
        next_update_in=state["next_update_in"]
    )

@app.post("/npcs/status/refresh")
async def refresh_npcs_status():
    """
    强制刷新 NPC 状态
    
    立即触发一次批量对话生成，不等待定时任务
    用于测试或需要立即更新 NPC 状态的场景
    
    Returns:
        dict: 刷新结果和新的对话内容
    """
    _, state_mgr = get_managers()
    
    await state_mgr.force_update()
    state = state_mgr.get_current_state()
    
    return {
        "message": "NPC状态已刷新",
        "dialogues": state["dialogues"]
    }

@app.get("/npcs/{npc_name}")
async def get_npc_info(npc_name: str):
    """
    获取指定 NPC 的详细信息
    
    返回 NPC 的完整信息，包括基本属性和当前对话状态
    
    Args:
        npc_name: NPC 名称
        
    Returns:
        dict: NPC 的详细信息
        
    Raises:
        HTTPException: NPC 不存在
    """
    npc_mgr, state_mgr = get_managers()

    npc_info = npc_mgr.get_npc_info(npc_name)
    if not npc_info:
        raise HTTPException(
            status_code=404,
            detail=f"NPC '{npc_name}' 不存在"
        )

    # 添加当前对话状态
    current_dialogue = state_mgr.get_npc_dialogue(npc_name)
    npc_info["current_dialogue"] = current_dialogue

    return npc_info

# -------------------------------------------------------------------
# 记忆管理接口
# -------------------------------------------------------------------

@app.get("/npcs/{npc_name}/memories")
async def get_npc_memories(npc_name: str, limit: int = 10):
    """
    获取 NPC 的记忆列表
    
    返回 NPC 的历史对话记忆，按时间倒序排列
    
    Args:
        npc_name: NPC 名称
        limit: 返回的记忆数量限制（默认 10 条）

    Returns:
        dict: NPC 的记忆列表和总数
        
    Raises:
        HTTPException: NPC 不存在或获取失败
    """
    npc_mgr, _ = get_managers()

    # 验证NPC是否存在
    npc_info = npc_mgr.get_npc_info(npc_name)
    if not npc_info:
        raise HTTPException(
            status_code=404,
            detail=f"NPC '{npc_name}' 不存在"
        )

    try:
        memories = npc_mgr.get_npc_memories(npc_name, limit=limit)

        return {
            "npc_name": npc_name,
            "memories": memories,
            "total": len(memories)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取记忆失败: {str(e)}"
        )

@app.delete("/npcs/{npc_name}/memories")
async def clear_npc_memories(npc_name: str, memory_type: str = None):
    """
    清空 NPC 的记忆（用于测试）
    
    删除 NPC 的历史对话记忆
    可以指定清空特定类型的记忆，或清空所有记忆

    Args:
        npc_name: NPC 名称
        memory_type: 记忆类型（working/episodic），不指定则清空所有

    Returns:
        dict: 操作结果
        
    Raises:
        HTTPException: NPC 不存在或清空失败
    """
    npc_mgr, _ = get_managers()

    # 验证NPC是否存在
    npc_info = npc_mgr.get_npc_info(npc_name)
    if not npc_info:
        raise HTTPException(
            status_code=404,
            detail=f"NPC '{npc_name}' 不存在"
        )

    try:
        npc_mgr.clear_npc_memory(npc_name, memory_type)

        return {
            "message": f"已清空{npc_name}的记忆",
            "npc_name": npc_name,
            "memory_type": memory_type or "all"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"清空记忆失败: {str(e)}"
        )

# -------------------------------------------------------------------
# 好感度管理接口
# -------------------------------------------------------------------

@app.get("/npcs/{npc_name}/affinity")
async def get_npc_affinity(npc_name: str, player_id: str = "player"):
    """
    获取 NPC 对玩家的好感度
    
    返回好感度值、关系等级和对话风格修饰词

    Args:
        npc_name: NPC 名称
        player_id: 玩家 ID（默认为 "player"）

    Returns:
        dict: 好感度信息
        
    Raises:
        HTTPException: NPC 不存在或获取失败
    """
    npc_mgr, _ = get_managers()

    # 验证NPC是否存在
    npc_info = npc_mgr.get_npc_info(npc_name)
    if not npc_info:
        raise HTTPException(
            status_code=404,
            detail=f"NPC '{npc_name}' 不存在"
        )

    try:
        affinity_info = npc_mgr.get_npc_affinity(npc_name, player_id)

        return {
            "npc_name": npc_name,
            "player_id": player_id,
            **affinity_info
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取好感度失败: {str(e)}"
        )

@app.get("/affinities")
async def get_all_affinities(player_id: str = "player"):
    """
    获取所有 NPC 对玩家的好感度
    
    返回所有 NPC 的好感度信息，用于显示好感度面板

    Args:
        player_id: 玩家 ID（默认为 "player"）

    Returns:
        dict: 所有 NPC 的好感度信息
        
    Raises:
        HTTPException: 获取失败
    """
    npc_mgr, _ = get_managers()

    try:
        affinities = npc_mgr.get_all_affinities(player_id)

        return {
            "player_id": player_id,
            "affinities": affinities
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取好感度失败: {str(e)}"
        )

@app.put("/npcs/{npc_name}/affinity")
async def set_npc_affinity(npc_name: str, affinity: float, player_id: str = "player"):
    """
    设置 NPC 对玩家的好感度（用于测试）
    
    手动设置好感度值，用于测试不同好感度等级的对话效果

    Args:
        npc_name: NPC 名称
        affinity: 好感度值（0-100）
        player_id: 玩家 ID（默认为 "player"）

    Returns:
        dict: 操作结果和新的好感度信息
        
    Raises:
        HTTPException: NPC 不存在、好感度超出范围或设置失败
    """
    npc_mgr, _ = get_managers()

    # 验证NPC是否存在
    npc_info = npc_mgr.get_npc_info(npc_name)
    if not npc_info:
        raise HTTPException(
            status_code=404,
            detail=f"NPC '{npc_name}' 不存在"
        )

    # 验证好感度范围
    if affinity < 0 or affinity > 100:
        raise HTTPException(
            status_code=400,
            detail="好感度必须在0-100之间"
        )

    try:
        npc_mgr.set_npc_affinity(npc_name, affinity, player_id)
        affinity_info = npc_mgr.get_npc_affinity(npc_name, player_id)

        return {
            "message": f"已设置{npc_name}对玩家的好感度",
            "npc_name": npc_name,
            "player_id": player_id,
            **affinity_info
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"设置好感度失败: {str(e)}"
        )

# ===================================================================
# 主程序入口
# ===================================================================
# 直接运行此文件时启动开发服务器
# 生产环境建议使用 gunicorn 或其他 WSGI 服务器

if __name__ == "__main__":
    print("\n启动赛博小镇后端服务...")
    print(f"监听地址: {settings.API_HOST}:{settings.API_PORT}")
    print(f"访问文档: http://localhost:{settings.API_PORT}/docs\n")
    
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,  # 开发模式自动重载（代码修改后自动重启）
        log_level="info"
    )

