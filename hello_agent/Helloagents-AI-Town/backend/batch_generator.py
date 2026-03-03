"""
NPC 批量对话生成器模块

实现批量生成所有 NPC 对话的功能
核心思路：使用一次 LLM 调用同时生成所有 NPC 的对话，降低 API 成本和延迟

功能：
1. 批量对话生成 - 一次性生成所有 NPC 的对话内容
2. 场景感知 - 根据时间和场景自动调整对话内容
3. 预设对话库 - 当 LLM 不可用时使用预设对话
4. 单例模式 - 全局共享一个生成器实例
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, Optional

# 添加 HelloAgents 框架到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'HelloAgents'))

from hello_agents import HelloAgentsLLM
from agents import NPC_ROLES

class NPCBatchGenerator:
    """
    NPC 批量对话生成器
    
    负责批量生成所有 NPC 的对话内容
    核心思路：一次 LLM 调用生成所有 NPC 的对话，降低 API 成本和延迟
    
    优势：
    - 降低 API 调用次数（3个 NPC 只需 1 次调用）
    - 减少总延迟（并行生成而非串行）
    - 对话更连贯（LLM 可以考虑 NPC 之间的关系）
    
    Attributes:
        llm: HelloAgentsLLM 实例
        enabled: 是否启用 LLM 生成（False 时使用预设对话）
        npc_configs: NPC 角色配置字典
        preset_dialogues: 预设对话库（当 LLM 不可用时使用）
    """
    
    def __init__(self):
        """
        初始化批量生成器
        
        尝试初始化 LLM，如果失败则使用预设对话模式
        """
        print("正在初始化批量对话生成器...")
        
        try:
            # 初始化 LLM
            self.llm = HelloAgentsLLM()
            self.enabled = True
            print("批量生成器初始化成功")
        except Exception as e:
            # LLM 初始化失败，使用预设对话模式
            print(f"批量生成器初始化失败: {e}")
            print("将使用预设对话模式")
            self.llm = None
            self.enabled = False
        
        # 获取 NPC 角色配置
        self.npc_configs = NPC_ROLES
        
        # 预设对话库（当 LLM 不可用时使用）
        # 按时间段分类，提供不同场景的对话
        self.preset_dialogues = {
            "morning": {
                "张三": "早上好!今天要继续优化那个多智能体系统的性能。",
                "李四": "新的一天开始了,先整理一下今天的会议安排。",
                "王五": "早!先来杯咖啡提提神,然后开始设计新界面。"
            },
            "noon": {
                "张三": "写了一上午代码,终于把那个bug修复了!",
                "李四": "上午的需求评审会很顺利,下午继续推进。",
                "王五": "这个配色方案看起来不错,再调整一下细节。"
            },
            "afternoon": {
                "张三": "下午继续写代码,这个算法还需要优化一下。",
                "李四": "正在准备下周的产品规划会,需求文档快完成了。",
                "王五": "设计稿基本完成了,等会儿发给大家看看。"
            },
            "evening": {
                "张三": "今天的代码提交完成,明天继续!",
                "李四": "今天的工作差不多了,整理一下明天的待办事项。",
                "王五": "设计工作告一段落,明天再继续优化。"
            }
        }
    
    def generate_batch_dialogues(self, context: Optional[str] = None) -> Dict[str, str]:
        """
        批量生成所有 NPC 的对话
        
        这是核心方法，执行以下流程：
        1. 检查 LLM 是否可用
        2. 构建批量生成提示词
        3. 调用 LLM 一次性生成所有对话
        4. 解析并返回结果
        5. 如果失败，使用预设对话
        
        Args:
            context: 场景上下文（如 "上午工作时间"、"午餐时间" 等）
                    如果为 None，会根据当前时间自动推断
        
        Returns:
            Dict[str, str]: NPC 名称到对话内容的映射
                例如：{"张三": "正在优化代码...", "李四": "整理需求文档..."}
        """
        # 检查 LLM 是否可用
        if not self.enabled or self.llm is None:
            # LLM 不可用，使用预设对话
            return self._get_preset_dialogues()
        
        try:
            # 步骤 1: 构建批量生成提示词
            prompt = self._build_batch_prompt(context)

            # 步骤 2: 一次 LLM 调用生成所有对话
            # 使用 invoke 方法而不是 chat 方法
            response = self.llm.invoke([
                {"role": "system", "content": "你是一个游戏NPC对话生成器,擅长创作自然真实的办公室对话。"},
                {"role": "user", "content": prompt}
            ])

            # 步骤 3: 解析 JSON 响应
            dialogues = self._parse_response(response)

            if dialogues:
                print(f"批量生成成功: {len(dialogues)}个NPC对话")
                return dialogues
            else:
                # 解析失败，使用预设对话
                print("解析失败,使用预设对话")
                return self._get_preset_dialogues()

        except Exception as e:
            # 生成失败，使用预设对话
            print(f"批量生成失败: {e}")
            return self._get_preset_dialogues()
    
    def _build_batch_prompt(self, context: Optional[str] = None) -> str:
        """
        构建批量生成提示词
        
        根据场景上下文和 NPC 配置，构建完整的生成提示词
        
        Args:
            context: 场景上下文，如果为 None 则自动推断
            
        Returns:
            str: 完整的提示词
        """
        # 如果没有提供场景上下文，根据当前时间自动推断
        if context is None:
            context = self._get_current_context()
        
        # 构建 NPC 描述列表
        npc_descriptions = []
        for name, cfg in self.npc_configs.items():
            desc = f"- {name}({cfg['title']}): 在{cfg['location']}{cfg['activity']},性格{cfg['personality']}"
            npc_descriptions.append(desc)
        
        # 将 NPC 描述列表转换为文本
        npc_desc_text = "\n".join(npc_descriptions)
        
        prompt = f"""请为Datawhale办公室的3个NPC生成当前的对话或行为描述。

【场景】{context}

【NPC信息】
{npc_desc_text}

【生成要求】
1. 每个NPC生成1句话(20-40字)
2. 内容要符合角色设定、当前活动和场景氛围
3. 可以是自言自语、工作状态描述、或简单的思考
4. 要自然真实,像真实的办公室同事
5. 可以体现一些个性化特点和情绪
6. **必须严格按照JSON格式返回**

【输出格式】(严格遵守)
{{"张三": "...", "李四": "...", "王五": "..."}}

【示例输出】
{{"张三": "这个bug真是见鬼了,已经调试两小时了...", "李四": "嗯,这个功能的优先级需要重新评估一下。", "王五": "这杯咖啡的拉花真不错,灵感来了!"}}

请生成(只返回JSON,不要其他内容):
"""
        return prompt
    
    def _parse_response(self, response: str) -> Optional[Dict[str, str]]:
        """
        解析 LLM 响应
        
        尝试多种方法解析 LLM 返回的 JSON 数据：
        1. 直接解析 JSON
        2. 提取 JSON 部分（去除额外文字）
        3. 验证格式是否正确
        
        Args:
            response: LLM 的原始响应文本
            
        Returns:
            Optional[Dict[str, str]]: 解析后的对话字典，失败返回 None
        """
        try:
            # 方法 1: 尝试直接解析 JSON
            dialogues = json.loads(response)
            
            # 验证格式：必须是字典，且包含所有 NPC 的名称
            if isinstance(dialogues, dict) and all(name in dialogues for name in self.npc_configs.keys()):
                return dialogues
            else:
                print(f"JSON格式不正确: {dialogues}")
                return None
                
        except json.JSONDecodeError:
            # 方法 2: 尝试提取 JSON 部分
            # LLM 可能在 JSON 前后添加了额外的文字
            try:
                # 查找第一个 { 和最后一个 }
                start = response.find('{')
                end = response.rfind('}') + 1
                
                if start != -1 and end > start:
                    json_str = response[start:end]
                    dialogues = json.loads(json_str)
                    
                    if isinstance(dialogues, dict):
                        return dialogues
            except:
                pass
            
            # 所有方法都失败
            print(f"无法解析响应: {response[:100]}...")
            return None
    
    def _get_current_context(self) -> str:
        """
        根据当前时间推断场景上下文
        
        将一天的时间分为不同时段，为每个时段提供合适的场景描述
        这些描述会影响 LLM 生成的对话内容
        
        Returns:
            str: 场景上下文描述
        """
        hour = datetime.now().hour
        
        # 根据小时数判断时段
        if 6 <= hour < 9:
            return "清晨时分,大家陆续到达办公室,准备开始新的一天"
        elif 9 <= hour < 12:
            return "上午工作时间,大家都在专注工作,办公室氛围专注而忙碌"
        elif 12 <= hour < 14:
            return "午餐时间,大家在休息放松,聊聊天或者看看手机"
        elif 14 <= hour < 17:
            return "下午工作时间,继续推进项目,偶尔需要喝杯咖啡提神"
        elif 17 <= hour < 19:
            return "傍晚时分,准备收尾今天的工作,整理明天的计划"
        else:
            return "夜晚时分,办公室安静下来,偶尔还有人在加班"
    
    def _get_preset_dialogues(self) -> Dict[str, str]:
        """
        获取预设对话（根据时间）
        
        当 LLM 不可用时，使用预设的对话库
        根据当前时间选择合适的对话内容
        
        Returns:
            Dict[str, str]: NPC 名称到对话内容的映射
        """
        hour = datetime.now().hour
        
        # 根据时间选择对话时段
        if 6 <= hour < 12:
            period = "morning"
        elif 12 <= hour < 14:
            period = "noon"
        elif 14 <= hour < 18:
            period = "afternoon"
        else:
            period = "evening"
        
        # 返回对应时段的预设对话
        return self.preset_dialogues.get(period, self.preset_dialogues["morning"])

# ===================================================================
# 全局单例模式
# ===================================================================
# 使用全局变量存储批量生成器实例
# 确保整个应用只有一个批量生成器实例
_batch_generator = None

def get_batch_generator() -> NPCBatchGenerator:
    """
    获取批量生成器单例
    
    使用单例模式确保全局只有一个批量生成器实例
    避免重复初始化 LLM
    
    Returns:
        NPCBatchGenerator: 批量生成器实例
    """
    global _batch_generator
    if _batch_generator is None:
        _batch_generator = NPCBatchGenerator()
    return _batch_generator

