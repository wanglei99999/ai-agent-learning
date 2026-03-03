"""
NPC 状态管理器

负责定时批量更新 NPC 的自主对话状态
这是一个后台服务，通过定时任务自动调用批量生成器

核心功能：
1. 定时任务 - 每隔固定时间自动更新 NPC 对话
2. 状态缓存 - 缓存当前所有 NPC 的对话内容
3. 查询接口 - 提供状态查询和强制更新接口
4. 异步实现 - 使用 asyncio 实现非阻塞定时任务

工作流程：
- 应用启动时立即执行一次批量生成
- 启动后台定时循环任务
- 每隔 update_interval 秒自动更新一次
- 更新失败不会中断服务，继续下一次更新
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional
from batch_generator import get_batch_generator

class NPCStateManager:
    """
    NPC 状态管理器
    
    管理所有 NPC 的自主对话状态，通过定时任务批量更新
    
    核心职责：
    1. 定时批量生成 NPC 对话（降低 API 成本）
    2. 缓存当前 NPC 状态（避免重复调用 LLM）
    3. 提供状态查询接口（供 API 层调用）
    
    属性：
        update_interval: 更新间隔（秒）
        batch_generator: 批量对话生成器实例
        current_dialogues: 当前所有 NPC 的对话内容缓存
        last_update: 上次更新时间
        next_update_time: 下次更新时间
        _update_task: 后台更新任务
        _running: 运行状态标志
    """
    
    def __init__(self, update_interval: int = 30):
        """
        初始化状态管理器
        
        创建状态管理器实例，初始化批量生成器和状态缓存
        
        Args:
            update_interval: 更新间隔（秒），默认 30 秒
                           建议根据实际需求调整：
                           - 开发环境：30-60 秒
                           - 生产环境：60-300 秒（降低 API 成本）
        """
        self.update_interval = update_interval
        # 获取批量生成器单例
        self.batch_generator = get_batch_generator()
        
        # 当前状态缓存
        self.current_dialogues: Dict[str, str] = {}  # {NPC名称: 对话内容}
        self.last_update: Optional[datetime] = None   # 上次更新时间
        self.next_update_time: Optional[datetime] = None  # 下次更新时间
        
        # 后台任务管理
        self._update_task: Optional[asyncio.Task] = None  # asyncio 任务对象
        self._running = False  # 运行状态标志
        
        print(f"NPC状态管理器初始化完成 (更新间隔: {update_interval}秒)")
    
    async def start(self):
        """
        启动后台更新任务
        
        启动定时循环任务，定期批量更新 NPC 对话
        在应用启动时由 lifespan 管理器调用
        
        执行流程：
        1. 检查是否已在运行（避免重复启动）
        2. 立即执行一次更新（确保启动时有初始数据）
        3. 启动异步定时循环任务
        """
        if self._running:
            print("警告: 状态管理器已在运行")
            return
        
        self._running = True
        print("启动NPC状态自动更新...")
        
        # 立即执行一次更新
        # 确保应用启动时就有 NPC 对话数据，而不是等待第一个定时周期
        await self._update_npc_states()
        
        # 启动定时更新任务
        # 使用 asyncio.create_task 创建后台任务，不阻塞主流程
        self._update_task = asyncio.create_task(self._auto_update_loop())
    
    async def stop(self):
        """
        停止后台更新任务
        
        优雅地关闭定时任务，在应用关闭时调用
        确保任务被正确取消，避免资源泄漏
        
        执行流程：
        1. 设置运行标志为 False（通知循环退出）
        2. 取消 asyncio 任务
        3. 等待任务完全结束
        4. 捕获并忽略 CancelledError 异常
        """
        if not self._running:
            return
        
        self._running = False
        
        if self._update_task:
            # 取消任务
            self._update_task.cancel()
            try:
                # 等待任务完全结束
                await self._update_task
            except asyncio.CancelledError:
                # 忽略取消异常（这是正常的）
                pass
        
        print("NPC状态自动更新已停止")
    
    async def _auto_update_loop(self):
        """
        自动更新循环（私有方法）
        
        后台定时任务的主循环，持续运行直到被停止
        
        工作流程：
        1. 等待 update_interval 秒
        2. 执行一次批量更新
        3. 重复上述步骤
        
        异常处理：
        - CancelledError: 任务被取消时退出循环
        - 其他异常: 记录错误但继续运行（保证服务稳定性）
        """
        while self._running:
            try:
                # 等待指定的更新间隔
                await asyncio.sleep(self.update_interval)
                # 执行批量更新
                await self._update_npc_states()
            except asyncio.CancelledError:
                # 任务被取消，退出循环
                break
            except Exception as e:
                # 捕获所有其他异常，避免循环中断
                print(f"自动更新失败: {e}")
                # 继续运行，不中断服务
    
    async def _update_npc_states(self):
        """
        更新 NPC 状态（私有方法）
        
        执行一次批量对话生成并更新缓存
        这是状态管理器的核心方法
        
        执行流程：
        1. 调用批量生成器生成所有 NPC 的对话
        2. 更新状态缓存（current_dialogues）
        3. 更新时间戳（last_update）
        4. 打印更新结果（用于监控）
        
        异常处理：
        - 捕获所有异常，避免影响定时任务
        - 打印错误信息，便于排查问题
        """
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 开始批量更新NPC对话...")
            
            # 调用批量生成器，一次性生成所有 NPC 的对话
            # 这是一个同步方法，但执行时间通常很短（1-2秒）
            new_dialogues = self.batch_generator.generate_batch_dialogues()
            
            # 更新状态缓存
            self.current_dialogues = new_dialogues  # 替换整个缓存
            self.last_update = datetime.now()       # 记录更新时间
            self.next_update_time = datetime.now()  # 下次更新时间（用于计算倒计时）
            
            # 打印更新结果（用于监控和调试）
            print("NPC对话已更新:")
            for npc_name, dialogue in new_dialogues.items():
                print(f"   - {npc_name}: {dialogue}")
            
        except Exception as e:
            # 捕获所有异常，避免定时任务中断
            print(f"更新NPC状态失败: {e}")
    
    def get_current_state(self) -> Dict:
        """
        获取当前状态
        
        返回所有 NPC 的当前对话状态和更新时间信息
        供 API 接口调用，用于前端显示 NPC 的自主行为
        
        Returns:
            Dict: 包含以下字段的字典
                - dialogues: {NPC名称: 对话内容} 的映射
                - last_update: 上次更新的时间戳
                - next_update_in: 距离下次更新的秒数（倒计时）
        
        示例返回值：
        {
            "dialogues": {
                "张三": "正在调试代码...",
                "李四": "整理需求文档..."
            },
            "last_update": datetime(2026, 3, 3, 11, 30, 0),
            "next_update_in": 15
        }
        """
        # 计算下次更新倒计时
        if self.last_update:
            # 计算已经过去的时间
            elapsed = (datetime.now() - self.last_update).total_seconds()
            # 计算剩余时间（不能为负数）
            next_update_in = max(0, int(self.update_interval - elapsed))
        else:
            # 如果还没有更新过，倒计时就是完整的更新间隔
            next_update_in = self.update_interval
        
        return {
            "dialogues": self.current_dialogues,
            "last_update": self.last_update,
            "next_update_in": next_update_in
        }
    
    def get_npc_dialogue(self, npc_name: str) -> Optional[str]:
        """
        获取指定 NPC 的当前对话
        
        从缓存中获取单个 NPC 的对话内容
        
        Args:
            npc_name: NPC 名称（如 "张三"）
        
        Returns:
            Optional[str]: NPC 的当前对话内容，如果 NPC 不存在则返回 None
        """
        return self.current_dialogues.get(npc_name)
    
    async def force_update(self):
        """
        强制立即更新
        
        不等待定时任务，立即执行一次批量更新
        用于测试或需要立即刷新 NPC 状态的场景
        
        使用场景：
        - 测试批量生成功能
        - 手动刷新 NPC 状态
        - API 接口 POST /npcs/status/refresh
        """
        print("强制更新NPC状态...")
        await self._update_npc_states()

# ===================================================================
# 全局单例模式
# ===================================================================
# 使用单例模式确保整个应用只有一个状态管理器实例
# 避免重复创建定时任务和状态缓存

_state_manager = None

def get_state_manager(update_interval: int = 30) -> NPCStateManager:
    """
    获取状态管理器单例
    
    使用单例模式，确保全局只有一个状态管理器实例
    第一次调用时创建实例，后续调用直接返回已创建的实例
    
    Args:
        update_interval: 更新间隔（秒），仅在第一次创建时有效
                        后续调用会忽略此参数
    
    Returns:
        NPCStateManager: 状态管理器单例实例
    
    使用示例：
        # 在 main.py 的 lifespan 中
        state_manager = get_state_manager(settings.NPC_UPDATE_INTERVAL)
        await state_manager.start()
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = NPCStateManager(update_interval)
    return _state_manager

