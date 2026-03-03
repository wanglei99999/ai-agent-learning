"""
数据模型定义模块

定义所有 API 请求和响应的数据模型
使用 Pydantic 进行数据验证和序列化
所有模型都包含示例数据，用于 API 文档展示
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class ChatRequest(BaseModel):
    """
    NPC 对话请求模型
    
    用于玩家与 NPC 进行对话时的请求数据
    客户端（Godot 或 Web）发送此模型到 /chat 接口
    
    Attributes:
        npc_name: NPC 的名称（如 "张三"）
        message: 玩家发送的消息内容
    """
    npc_name: str = Field(..., description="NPC名称")
    message: str = Field(..., description="玩家消息")
    
    class Config:
        # 为 API 文档提供示例数据
        json_schema_extra = {
            "example": {
                "npc_name": "张三",
                "message": "你好,你在做什么?"
            }
        }

class ChatResponse(BaseModel):
    """
    NPC 对话响应模型
    
    NPC Agent 处理对话后返回的响应数据
    包含 NPC 的回复内容和相关元信息
    
    Attributes:
        npc_name: NPC 的名称
        npc_title: NPC 的职位（如 "Python工程师"）
        message: NPC 的回复内容（由 LLM 生成）
        success: 对话是否成功处理
        timestamp: 对话时间戳（自动生成）
    """
    npc_name: str = Field(..., description="NPC名称")
    npc_title: str = Field(..., description="NPC职位")
    message: str = Field(..., description="NPC回复")
    success: bool = Field(default=True, description="是否成功")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="时间戳")
    
    class Config:
        # 为 API 文档提供示例数据
        json_schema_extra = {
            "example": {
                "npc_name": "张三",
                "npc_title": "Python工程师",
                "message": "你好!我正在写代码,调试一个多智能体系统的bug。",
                "success": True
            }
        }

class NPCInfo(BaseModel):
    """
    NPC 基本信息模型
    
    描述单个 NPC 的基本属性和当前状态
    用于 NPC 列表展示和状态查询
    
    Attributes:
        name: NPC 名称
        title: NPC 职位/角色
        location: NPC 当前所在位置（如 "办公区"）
        activity: NPC 当前正在进行的活动（如 "写代码"）
        available: NPC 是否可以对话（忙碌时为 False）
    """
    name: str = Field(..., description="NPC名称")
    title: str = Field(..., description="NPC职位")
    location: str = Field(..., description="NPC位置")
    activity: str = Field(..., description="当前活动")
    available: bool = Field(default=True, description="是否可对话")

class NPCStatusResponse(BaseModel):
    """
    NPC 状态响应模型
    
    返回所有 NPC 的当前状态信息
    用于客户端定期轮询 NPC 的自主行为更新
    
    Attributes:
        dialogues: NPC 名称到当前对话内容的映射
                   记录每个 NPC 最近的自言自语或状态描述
        last_update: 上次状态更新的时间
        next_update_in: 距离下次自动更新的秒数
                        客户端可据此设置轮询间隔
    """
    dialogues: Dict[str, str] = Field(..., description="NPC当前对话内容")
    last_update: Optional[datetime] = Field(None, description="上次更新时间")
    next_update_in: int = Field(..., description="下次更新倒计时(秒)")
    
    class Config:
        # 为 API 文档提供示例数据
        json_schema_extra = {
            "example": {
                "dialogues": {
                    "张三": "终于把这个bug修复了,测试通过!",
                    "李四": "下周的产品评审会需要准备一下资料。",
                    "王五": "这个界面的配色方案还需要优化一下。"
                },
                "last_update": "2024-01-15T10:30:00",
                "next_update_in": 25
            }
        }

class NPCListResponse(BaseModel):
    """
    NPC 列表响应模型
    
    返回小镇中所有 NPC 的列表信息
    用于客户端初始化时获取所有 NPC 数据
    
    Attributes:
        npcs: NPC 信息对象列表
        total: NPC 总数（方便客户端分页或统计）
    """
    npcs: List[NPCInfo] = Field(..., description="NPC列表")
    total: int = Field(..., description="NPC总数")

