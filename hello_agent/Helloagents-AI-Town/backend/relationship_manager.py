"""
NPC 好感度管理系统模块

实现基于 LLM 的情感分析和好感度动态调整系统
根据玩家与 NPC 的对话内容，自动分析情感倾向并更新好感度

核心功能：
1. 情感分析 - 使用专门的 Agent 分析对话情感
2. 好感度管理 - 维护每个 NPC 对不同玩家的好感度
3. 等级系统 - 将好感度映射到关系等级（陌生/熟悉/友好/亲密/挚友）
4. 对话风格调整 - 根据好感度提供不同的对话风格修饰词
"""

import sys
import os

# 添加 HelloAgents 框架到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'HelloAgents'))

from hello_agents import SimpleAgent, HelloAgentsLLM
from typing import Dict, Optional, Tuple
import json
import re

class RelationshipManager:
    """
    NPC 好感度管理器
    
    负责管理所有 NPC 与玩家之间的好感度关系
    使用 LLM 分析对话内容，自动调整好感度值
    
    功能：
    - 管理 NPC 与玩家的好感度（0-100）
    - 使用 LLM 分析对话情感
    - 自动更新好感度
    - 提供好感度等级和对话风格修饰词
    
    Attributes:
        llm: HelloAgentsLLM 实例
        affinity_scores: 好感度存储字典 {npc_name: {player_id: affinity_score}}
        analyzer_agent: 情感分析 Agent
    """
    
    def __init__(self, llm: HelloAgentsLLM):
        """
        初始化好感度管理器
        
        创建情感分析 Agent，初始化好感度存储结构
        
        Args:
            llm: HelloAgentsLLM 实例（用于情感分析）
        """
        self.llm = llm
        
        # 存储每个 NPC 与玩家的好感度
        # 二级字典结构：{NPC名称: {玩家ID: 好感度值}}
        # 例如：{"张三": {"player": 65.0, "player2": 50.0}}
        self.affinity_scores: Dict[str, Dict[str, float]] = {}
        
        # 创建好感度分析 Agent
        # 这是一个专门用于分析对话情感的 LLM Agent
        self.analyzer_agent = SimpleAgent(
            name="AffinityAnalyzer",
            llm=llm,
            system_prompt=self._create_analyzer_prompt()
        )
        
        print("好感度管理系统已初始化")
    
    def _create_analyzer_prompt(self) -> str:
        """
        创建情感分析 Agent 的系统提示词
        
        定义情感分析 Agent 的行为规则和输出格式
        包括分析维度、好感度变化规则、输出格式和示例
        
        Returns:
            str: 完整的系统提示词
        """
        return """你是一个情感分析专家,负责分析对话中的情感倾向,判断是否应该改变NPC对玩家的好感度。

【任务】
分析玩家与NPC的对话,判断是否应该改变好感度,以及改变的幅度。

【分析维度】
1. **玩家态度**: 友好/中立/不友好
2. **对话内容**: 积极/中立/消极
3. **互动质量**: 深入/一般/敷衍
4. **情感倾向**: 赞美/批评/中性

【好感度变化规则】
- 赞美、感谢、请教: +3 到 +8
- 友好问候、正常交流: +1 到 +3
- 普通闲聊、中性话题: 0
- 批评、质疑、不耐烦: -3 到 -8
- 侮辱、攻击、恶意: -8 到 -15

【输出格式】(严格遵守JSON格式,不要添加任何其他文字)
{
    "should_change": true/false,
    "change_amount": -15到+10之间的整数,
    "reason": "简短说明原因(10字以内)",
    "sentiment": "positive/neutral/negative"
}

【示例1】
玩家: "你好,很高兴认识你!"
NPC: "你好!我也很高兴认识你。"
输出: {"should_change": true, "change_amount": 5, "reason": "友好问候", "sentiment": "positive"}

【示例2】
玩家: "你这个设计太丑了!"
NPC: "抱歉,我会改进的..."
输出: {"should_change": true, "change_amount": -8, "reason": "批评工作", "sentiment": "negative"}

【示例3】
玩家: "今天天气不错"
NPC: "是啊,挺好的。"
输出: {"should_change": false, "change_amount": 0, "reason": "普通闲聊", "sentiment": "neutral"}

【示例4】
玩家: "你的代码写得真棒!"
NPC: "谢谢!我最近在研究新技术。"
输出: {"should_change": true, "change_amount": 8, "reason": "赞美工作", "sentiment": "positive"}

【示例5】
玩家: "能教教我吗?"
NPC: "当然可以!我很乐意分享。"
输出: {"should_change": true, "change_amount": 6, "reason": "请教学习", "sentiment": "positive"}

【重要】
- 只输出JSON,不要添加任何解释或其他文字
- change_amount必须是整数
- reason必须简短(10字以内)
- sentiment必须是positive/neutral/negative之一
"""
    
    def get_affinity(self, npc_name: str, player_id: str = "player") -> float:
        """
        获取 NPC 对玩家的好感度
        
        如果是首次交互，自动初始化为 50.0（中立）
        
        Args:
            npc_name: NPC 名称
            player_id: 玩家 ID（默认为 "player"）
            
        Returns:
            float: 好感度值（0-100）
        """
        # 如果该 NPC 还没有好感度记录，创建空字典
        if npc_name not in self.affinity_scores:
            self.affinity_scores[npc_name] = {}
        
        # 如果该玩家还没有与此 NPC 交互过，初始化为 50.0
        if player_id not in self.affinity_scores[npc_name]:
            self.affinity_scores[npc_name][player_id] = 50.0  # 初始好感度：中立
        
        return self.affinity_scores[npc_name][player_id]
    
    def set_affinity(self, npc_name: str, affinity: float, player_id: str = "player"):
        """
        设置 NPC 对玩家的好感度
        
        自动将好感度值限制在 0-100 范围内
        
        Args:
            npc_name: NPC 名称
            affinity: 好感度值（0-100）
            player_id: 玩家 ID（默认为 "player"）
        """
        # 如果该 NPC 还没有好感度记录，创建空字典
        if npc_name not in self.affinity_scores:
            self.affinity_scores[npc_name] = {}
        
        # 限制好感度在 0-100 范围内
        affinity = max(0.0, min(100.0, affinity))
        self.affinity_scores[npc_name][player_id] = affinity
    
    def analyze_and_update_affinity(
        self,
        npc_name: str,
        player_message: str,
        npc_response: str,
        player_id: str = "player"
    ) -> Dict:
        """
        分析对话并更新好感度
        
        这是核心方法，执行以下流程：
        1. 构建分析提示词
        2. 调用情感分析 Agent
        3. 解析分析结果
        4. 更新好感度（如果需要）
        5. 返回详细的分析结果
        
        Args:
            npc_name: NPC 名称
            player_message: 玩家发送的消息
            npc_response: NPC 的回复
            player_id: 玩家 ID（默认为 "player"）
            
        Returns:
            Dict: 分析结果字典
                - changed: 是否改变了好感度
                - old_affinity: 旧的好感度值
                - new_affinity: 新的好感度值
                - change_amount: 变化量
                - reason: 变化原因
                - sentiment: 情感倾向（positive/neutral/negative）
                - old_level: 旧的关系等级
                - new_level: 新的关系等级
        """
        # 构建分析提示词
        # 将对话内容提供给情感分析 Agent
        prompt = f"""请分析以下对话:

玩家: {player_message}
{npc_name}: {npc_response}

请判断是否应该改变好感度,并给出变化量。
"""
        
        try:
            # 调用情感分析 Agent
            # Agent 会根据系统提示词分析对话，返回 JSON 格式的结果
            response = self.analyzer_agent.run(prompt)
            
            # 解析 LLM 返回的 JSON 响应
            analysis = self._parse_analysis(response)
            
            # 判断是否需要改变好感度
            if analysis["should_change"]:
                # 获取当前好感度
                current_affinity = self.get_affinity(npc_name, player_id)
                
                # 计算新的好感度
                new_affinity = current_affinity + analysis["change_amount"]
                new_affinity = max(0.0, min(100.0, new_affinity))  # 限制在 0-100 范围内

                # 更新好感度
                self.set_affinity(npc_name, new_affinity, player_id)

                # 获取好感度等级（陌生/熟悉/友好/亲密/挚友）
                old_level = self.get_affinity_level(current_affinity)
                new_level = self.get_affinity_level(new_affinity)

                # 注意：日志输出已移到 agents.py 中，避免重复输出

                # 返回详细的变化信息
                return {
                    "changed": True,
                    "old_affinity": current_affinity,
                    "new_affinity": new_affinity,
                    "change_amount": analysis["change_amount"],
                    "reason": analysis["reason"],
                    "sentiment": analysis.get("sentiment", "neutral"),
                    "old_level": old_level,
                    "new_level": new_level
                }
            else:
                # 好感度未改变
                return {
                    "changed": False,
                    "affinity": self.get_affinity(npc_name, player_id),
                    "reason": analysis["reason"],
                    "sentiment": analysis.get("sentiment", "neutral")
                }
        
        except Exception as e:
            # 分析失败时的异常处理
            print(f"好感度分析失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 返回默认结果，保持好感度不变
            return {
                "changed": False,
                "affinity": self.get_affinity(npc_name, player_id),
                "reason": "分析失败",
                "sentiment": "neutral"
            }
    
    def _parse_analysis(self, response: str) -> Dict:
        """
        解析情感分析 Agent 的响应
        
        尝试多种方法解析 LLM 返回的 JSON 数据：
        1. 直接解析 JSON
        2. 提取 JSON 部分（去除额外文字）
        3. 使用正则表达式提取关键字段
        4. 返回默认值（如果所有方法都失败）
        
        Args:
            response: LLM 的原始响应文本
            
        Returns:
            Dict: 解析后的分析结果字典
                - should_change: 是否应该改变好感度
                - change_amount: 变化量
                - reason: 原因说明
                - sentiment: 情感倾向
        """
        try:
            # 方法 1：尝试直接解析 JSON
            analysis = json.loads(response)
            return analysis
        except json.JSONDecodeError:
            # 方法 2：尝试提取 JSON 部分
            # LLM 可能在 JSON 前后添加了额外的文字
            # 查找第一个 { 和最后一个 }
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = response[start:end]
                try:
                    analysis = json.loads(json_str)
                    return analysis
                except json.JSONDecodeError:
                    pass
            
            # 方法 3：使用正则表达式提取关键字段
            # 即使 JSON 格式不完整，也尝试提取关键信息
            should_change_match = re.search(r'"should_change"\s*:\s*(true|false)', response, re.IGNORECASE)
            change_amount_match = re.search(r'"change_amount"\s*:\s*(-?\d+)', response)
            reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', response)
            sentiment_match = re.search(r'"sentiment"\s*:\s*"([^"]+)"', response)
            
            if should_change_match and change_amount_match:
                return {
                    "should_change": should_change_match.group(1).lower() == "true",
                    "change_amount": int(change_amount_match.group(1)),
                    "reason": reason_match.group(1) if reason_match else "未知",
                    "sentiment": sentiment_match.group(1) if sentiment_match else "neutral"
                }
            
            # 方法 4：所有解析方法都失败，返回默认值
            print(f"JSON 解析失败，使用默认值。原始响应: {response[:100]}...")
            return {
                "should_change": False,
                "change_amount": 0,
                "reason": "解析失败",
                "sentiment": "neutral"
            }
    
    def get_affinity_level(self, affinity: float) -> str:
        """
        获取好感度等级
        
        将数值型的好感度映射到文字描述的关系等级
        
        Args:
            affinity: 好感度值（0-100）
            
        Returns:
            str: 好感度等级名称
                - 80-100: 挚友
                - 60-79: 亲密
                - 40-59: 友好
                - 20-39: 熟悉
                - 0-19: 陌生
        """
        if affinity >= 80:
            return "挚友"
        elif affinity >= 60:
            return "亲密"
        elif affinity >= 40:
            return "友好"
        elif affinity >= 20:
            return "熟悉"
        else:
            return "陌生"
    
    def get_affinity_modifier(self, affinity: float) -> str:
        """
        获取好感度修饰词
        
        根据好感度提供对话风格的修饰词
        这些修饰词会被添加到 NPC 的系统提示词中，影响对话风格
        
        Args:
            affinity: 好感度值（0-100）
            
        Returns:
            str: 对话风格修饰词，用于指导 NPC 的对话态度
        """
        if affinity >= 80:
            return "非常热情友好,像老朋友一样亲切,愿意分享私人话题"
        elif affinity >= 60:
            return "友好热情,愿意多聊,会主动关心对方"
        elif affinity >= 40:
            return "礼貌友善,正常交流,保持专业"
        elif affinity >= 20:
            return "礼貌但略显生疏,回答简洁"
        else:
            return "冷淡疏离,不太愿意多说,回答简短"
    
    def get_all_affinities(self, player_id: str = "player") -> Dict[str, Dict]:
        """
        获取所有 NPC 的好感度信息
        
        返回指定玩家与所有 NPC 的好感度数据
        
        Args:
            player_id: 玩家 ID（默认为 "player"）
            
        Returns:
            Dict[str, Dict]: NPC 名称到好感度信息的映射
                每个 NPC 的信息包含：
                - affinity: 好感度值
                - level: 关系等级
                - modifier: 对话风格修饰词
        """
        result = {}
        for npc_name in self.affinity_scores:
            affinity = self.get_affinity(npc_name, player_id)
            result[npc_name] = {
                "affinity": affinity,
                "level": self.get_affinity_level(affinity),
                "modifier": self.get_affinity_modifier(affinity)
            }
        return result

