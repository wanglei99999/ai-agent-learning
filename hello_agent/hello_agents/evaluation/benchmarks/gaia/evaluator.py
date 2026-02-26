"""GAIA 评估器模块

【学习笔记】模块作用
本模块负责评估智能体在 GAIA (General AI Assistants) 基准测试上的表现。

GAIA vs BFCL 对比:
1. BFCL:
   - 评估重点: 函数调用能力
   - 提示词: 复杂（包含函数定义、格式要求）
   - 评估方式: AST 匹配、参数准确率
   - 任务类型: 结构化函数调用

2. GAIA:
   - 评估重点: 通用问题解决能力
   - 提示词: 简单（只有问题本身）
   - 评估方式: 答案匹配（精确/部分）
   - 任务类型: 真实世界复杂问题

核心流程:
  dataset.py 加载数据 → evaluator.py 调用 Agent 并评估 → metrics.py 计算指标
  
本文件的职责:
  1. 拿到测试问题（可能包含附件文件）
  2. 构建简单 prompt 发给 Agent
  3. 从 Agent 回复中提取答案（支持多种格式）
  4. 将提取的答案与标准答案对比（精确匹配/部分匹配）
  5. 按难度级别汇总统计结果

【学习笔记】类作用
GAIAEvaluator 类负责评估智能体在 GAIA 基准测试上的表现，包括问题理解和推理、多步骤问题解决、工具使用能力和答案准确性等方面。

类结构:
  - __init__: 初始化评估器，加载数据集和指标计算器
  - evaluate: 评估智能体，返回评估结果
  - evaluate_sample: 评估单个样本，返回评估结果

使用示例:
  # 评估所有级别
  evaluator = GAIAEvaluator()
  results = evaluator.evaluate(agent)
  
  # 只评估 Level 2
  evaluator = GAIAEvaluator(level=2)
  results = evaluator.evaluate(agent)
  
  # 使用严格模式（只计算精确匹配）
  evaluator = GAIAEvaluator(strict_mode=True)
  results = evaluator.evaluate(agent)
"""

from typing import Dict, Any, List, Optional, Union
import time
import re
import json
from pathlib import Path
from hello_agents.evaluation.benchmarks.gaia.dataset import GAIADataset
from hello_agents.evaluation.benchmarks.gaia.metrics import GAIAMetrics


class GAIAEvaluator:
    """GAIA 评估器

    【学习笔记】核心功能
    评估智能体的通用 AI 助手能力，包括:
    - 问题理解和推理: 能否正确理解复杂问题
    - 多步骤问题解决: 能否进行多步推理
    - 工具使用能力: 能否使用外部工具（如搜索、计算器）
    - 答案准确性: 最终答案是否正确

    【学习笔记】评估标准
    GAIA 采用两级匹配标准:
    
    1. 精确匹配 (Exact Match):
       - 答案完全一致（经过标准化后）
       - 得分: 1.0
       - 示例: 预测 "Paris", 标准答案 "Paris" → 精确匹配
    
    2. 部分匹配 (Partial Match):
       - 答案包含正确信息但格式不同
       - 或者关键词重叠度 >= 70%
       - 得分: 0.5
       - 示例: 预测 "The capital is Paris", 标准答案 "Paris" → 部分匹配
    
    3. 不匹配:
       - 答案错误
       - 得分: 0.0

    【学习笔记】难度级别
    GAIA 数据集分为三个难度级别:
    - Level 1: 简单问题（1-2 步推理）
    - Level 2: 中等难度（3-4 步推理）
    - Level 3: 困难问题（5+ 步推理）

    使用示例:
        # 评估所有级别
        evaluator = GAIAEvaluator()
        results = evaluator.evaluate(agent)
        
        # 只评估 Level 2
        evaluator = GAIAEvaluator(level=2)
        results = evaluator.evaluate(agent)
        
        # 使用严格模式（只计算精确匹配）
        evaluator = GAIAEvaluator(strict_mode=True)
        results = evaluator.evaluate(agent)

    Attributes:
        dataset: GAIA 数据集加载器
        metrics: 评估指标计算器
        level: 难度级别过滤（1-3，None 表示全部）
        strict_mode: 是否使用严格匹配模式（True 时只计算精确匹配）
    """

    def __init__(
        self,
        dataset: Optional[GAIADataset] = None,
        level: Optional[int] = None,
        local_data_dir: Optional[str] = None,
        strict_mode: bool = True
    ):
        """初始化 GAIA 评估器

        【学习笔记】初始化过程
        设置评估器的核心组件：数据集加载器、指标计算器、评估参数。
        
        参数说明:
        1. dataset: 数据集对象
           - 如果为 None，会自动创建 GAIADataset
           - 可以传入自定义的数据集对象
        
        2. level: 难度级别过滤
           - 1: 只评估 Level 1 简单问题
           - 2: 只评估 Level 2 中等问题
           - 3: 只评估 Level 3 困难问题
           - None: 评估所有级别
        
        3. local_data_dir: 本地数据目录
           - 如果指定，从本地加载数据
           - 否则从 HuggingFace 下载
        
        4. strict_mode: 严格匹配模式
           - True: 只计算精确匹配，部分匹配不计分
           - False: 精确匹配和部分匹配都计分
        
        示例:
            # 默认配置（所有级别，严格模式）
            evaluator = GAIAEvaluator()
            
            # 只评估 Level 2
            evaluator = GAIAEvaluator(level=2)
            
            # 使用本地数据
            evaluator = GAIAEvaluator(local_data_dir="./gaia_data")
            
            # 宽松模式（部分匹配也计分）
            evaluator = GAIAEvaluator(strict_mode=False)

        Args:
            dataset: GAIA 数据集，如果为 None 则自动创建
            level: 难度级别 (1-3)
            local_data_dir: 本地数据目录
            strict_mode: 是否使用严格匹配模式
        """
        # 创建或使用提供的数据集
        self.dataset = dataset or GAIADataset(
            level=level,
            local_data_dir=local_data_dir
        )
        # 创建指标计算器
        self.metrics = GAIAMetrics()
        # 保存难度级别过滤
        self.level = level
        # 保存匹配模式
        self.strict_mode = strict_mode
        
    def evaluate(self, agent: Any, max_samples: Optional[int] = None) -> Dict[str, Any]:
        """评估智能体

        【学习笔记】评估流程
        这是 GAIA 评估的主入口方法，完整的评估流程如下:
        
        1. 加载数据集
           - 从 dataset 对象加载 GAIA 测试数据
           - 如果指定了 level，只加载对应级别的数据
        
        2. 限制样本数量
           - 如果指定了 max_samples，只评估前 N 个样本
           - 用于快速测试或调试
        
        3. 逐个评估样本
           - 调用 evaluate_sample() 评估每个问题
           - 按难度级别统计结果
           - 每 10 个样本打印一次进度
        
        4. 计算总体指标
           - 精确匹配率: exact_matches / total_samples
           - 部分匹配率: partial_matches / total_samples
        
        5. 计算分级指标
           - 每个难度级别单独统计
           - Level_1, Level_2, Level_3 的匹配率
        
        6. 返回结果
           - 包含总体指标、分级指标、详细结果
        
        示例:
            # 评估所有样本
            evaluator = GAIAEvaluator()
            results = evaluator.evaluate(agent)
            print(f"精确匹配率: {results['exact_match_rate']:.2%}")
            
            # 只评估 10 个样本（快速测试）
            results = evaluator.evaluate(agent, max_samples=10)
            
            # 查看 Level 2 的表现
            level_2_metrics = results['level_metrics']['Level_2']
            print(f"Level 2 准确率: {level_2_metrics['exact_match_rate']:.2%}")

        Args:
            agent: 要评估的智能体，必须有 run(prompt) 方法
            max_samples: 最大评估样本数，None 表示评估全部

        Returns:
            评估结果字典，包含各项指标
        """
        print(f"\n 开始 GAIA 评估...")
        print(f"   智能体: {getattr(agent, 'name', 'Unknown')}")
        print(f"   难度级别: {self.level or '全部'}")
        print(f"   匹配模式: {'严格' if self.strict_mode else '宽松'}")
        

        # 步骤1: 加载数据集
        dataset = self.dataset.load()
        if not dataset:
            print("数据集为空,跳过评估")
            return self._create_empty_results(agent)

        # 步骤2: 限制样本数量（用于快速测试）
        if max_samples:
            dataset = dataset[:max_samples]

        print(f"   样本数量: {len(dataset)}")

        # 步骤3: 执行评估
        results = []  # 存储每个样本的评估结果
        
        # 初始化分级统计（每个级别单独统计）
        level_stats = {
            1: {"total": 0, "correct": 0, "partial": 0},  # Level 1 统计
            2: {"total": 0, "correct": 0, "partial": 0},  # Level 2 统计
            3: {"total": 0, "correct": 0, "partial": 0}   # Level 3 统计
        }

        # 遍历每个样本进行评估
        for i, sample in enumerate(dataset):
            # 每 10 个样本打印一次进度
            if i % 10 == 0:
                print(f"   进度: {i+1}/{len(dataset)}")

            try:
                # 评估单个样本
                sample_result = self.evaluate_sample(agent, sample)
                results.append(sample_result)

                # 按级别统计结果
                level = sample.get("level", 1)
                if level in level_stats:
                    level_stats[level]["total"] += 1  # 总数 +1
                    if sample_result["exact_match"]:
                        level_stats[level]["correct"] += 1  # 精确匹配 +1
                    if sample_result["partial_match"]:
                        level_stats[level]["partial"] += 1  # 部分匹配 +1

            except Exception as e:
                # 评估失败，记录错误但不中断
                print(f" 样本 {i} 评估失败: {e}")
                results.append({
                    "exact_match": False,
                    "partial_match": False,
                    "predicted": None,
                    "expected": sample.get("final_answer"),
                    "error": str(e),
                    "score": 0.0
                })

        # 步骤4: 计算总体指标
        total_samples = len(results)  # 总样本数
        exact_matches = sum(1 for r in results if r["exact_match"])  # 精确匹配数
        partial_matches = sum(1 for r in results if r["partial_match"])  # 部分匹配数

        # 计算匹配率
        exact_match_rate = exact_matches / total_samples if total_samples > 0 else 0.0
        partial_match_rate = partial_matches / total_samples if total_samples > 0 else 0.0

        # 步骤5: 计算分级指标（每个难度级别单独统计）
        level_metrics = {}
        for level, stats in level_stats.items():
            if stats["total"] > 0:  # 只统计有样本的级别
                level_metrics[f"Level_{level}"] = {
                    "total": stats["total"],
                    "exact_matches": stats["correct"],
                    "partial_matches": stats["partial"],
                    "exact_match_rate": stats["correct"] / stats["total"],
                    "partial_match_rate": stats["partial"] / stats["total"]
                }

        # 步骤6: 构建最终结果
        final_results = {
            "benchmark": "GAIA",  # 基准测试名称
            "agent_name": getattr(agent, 'name', 'Unknown'),  # Agent 名称
            "strict_mode": self.strict_mode,  # 是否严格模式
            "level_filter": self.level,  # 难度级别过滤
            "total_samples": total_samples,  # 总样本数
            "exact_matches": exact_matches,  # 精确匹配数
            "partial_matches": partial_matches,  # 部分匹配数
            "exact_match_rate": exact_match_rate,  # 精确匹配率
            "partial_match_rate": partial_match_rate,  # 部分匹配率
            "level_metrics": level_metrics,  # 分级指标
            "detailed_results": results  # 详细结果（每个样本）
        }

        # 打印评估结果
        print(f"   GAIA 评估完成")
        print(f"   精确匹配率: {exact_match_rate:.2%}")
        print(f"   部分匹配率: {partial_match_rate:.2%}")
        for level_name, metrics in level_metrics.items():
            print(f"   {level_name}: {metrics['exact_match_rate']:.2%} 精确 / {metrics['partial_match_rate']:.2%} 部分")

        return final_results
    
    def evaluate_sample(self, agent: Any, sample: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个样本

        【学习笔记】单样本评估流程
        这个方法评估 Agent 对单个 GAIA 问题的回答，完整流程如下:
        
        1. 准备输入数据
           - 提取问题文本 (question)
           - 提取标准答案 (final_answer)
           - 提取难度级别 (level)
           - 提取任务ID (task_id)
        
        2. 构建提示词
           - 调用 _build_prompt() 构建简单提示
           - GAIA 的提示词非常简单，只包含问题本身
           - 如果有附件文件，会添加文件提示
        
        3. 调用 Agent
           - 调用 agent.run(prompt) 获取回答
           - 记录执行时间
        
        4. 提取答案
           - 调用 _extract_answer() 从回复中提取答案
           - 支持多种答案格式 (FINAL ANSWER:, 答案:, 等)
        
        5. 评估答案
           - 精确匹配: 调用 _check_exact_match()
           - 部分匹配: 调用 _check_partial_match()
        
        6. 计算分数
           - 精确匹配: 1.0 分
           - 部分匹配: 0.5 分
           - 不匹配: 0.0 分
        
        示例:
            sample = {
                "question": "What is the capital of France?",
                "final_answer": "Paris",
                "level": 1,
                "task_id": "001"
            }
            
            result = evaluator.evaluate_sample(agent, sample)
            # result = {
            #     "task_id": "001",
            #     "level": 1,
            #     "exact_match": True,
            #     "partial_match": True,
            #     "score": 1.0,
            #     "predicted": "Paris",
            #     "expected": "Paris",
            #     "response": "The capital of France is Paris.",
            #     "execution_time": 0.5
            # }

        Args:
            agent: 要评估的智能体，必须有 run(prompt) 方法
            sample: 样本数据字典

        Returns:
            单个样本的评估结果字典
        """
        try:
            # 步骤1: 准备输入数据
            question = sample.get("question", "")  # 问题文本
            expected_answer = sample.get("final_answer", "")  # 标准答案
            level = sample.get("level", 1)  # 难度级别
            task_id = sample.get("task_id", "")  # 任务ID

            # 步骤2: 构建提示词 (GAIA 的提示词非常简单)
            prompt = self._build_prompt(question, sample)

            # 步骤3: 调用智能体并记录时间
            start_time = time.time()
            response = agent.run(prompt)  # Agent 的完整回复
            execution_time = time.time() - start_time

            # 步骤4: 从回复中提取答案
            predicted_answer = self._extract_answer(response)

            # 步骤5: 评估答案（精确匹配和部分匹配）
            exact_match = self._check_exact_match(predicted_answer, expected_answer)
            partial_match = self._check_partial_match(predicted_answer, expected_answer)

            # 步骤6: 计算分数
            if exact_match:
                score = 1.0  # 精确匹配，满分
            elif partial_match:
                score = 0.5  # 部分匹配，半分
            else:
                score = 0.0  # 不匹配，零分

            # 返回评估结果
            return {
                "task_id": task_id,
                "level": level,
                "exact_match": exact_match,
                "partial_match": partial_match,
                "score": score,
                "predicted": predicted_answer,  # Agent 的答案
                "expected": expected_answer,  # 标准答案
                "response": response,  # Agent 的完整回复
                "execution_time": execution_time  # 执行时间（秒）
            }

        except Exception as e:
            # 评估失败，返回错误结果
            return {
                "task_id": sample.get("task_id", ""),
                "level": sample.get("level", 1),
                "exact_match": False,
                "partial_match": False,
                "score": 0.0,
                "predicted": None,
                "expected": sample.get("final_answer", ""),
                "error": str(e)
            }

    def _create_empty_results(self, agent: Any) -> Dict[str, Any]:
        """创建空的评估结果
        
        【学习笔记】空结果处理
        当数据集为空或加载失败时，返回一个空的评估结果，避免程序崩溃。
        
        使用场景:
        - 数据集加载失败
        - 数据集为空
        - 指定的难度级别没有样本
        
        返回的空结果包含所有必要字段，但数值都为 0。
        """
        return {
            "benchmark": "GAIA",  # 基准测试名称
            "agent_name": getattr(agent, 'name', 'Unknown'),  # Agent 名称
            "strict_mode": self.strict_mode,  # 匹配模式
            "level_filter": self.level,  # 级别过滤
            "total_samples": 0,  # 总样本数 = 0
            "exact_matches": 0,  # 精确匹配数 = 0
            "partial_matches": 0,  # 部分匹配数 = 0
            "exact_match_rate": 0.0,  # 精确匹配率 = 0
            "partial_match_rate": 0.0,  # 部分匹配率 = 0
            "level_metrics": {},  # 分级指标 = 空
            "detailed_results": []  # 详细结果 = 空
        }

    def _build_prompt(self, question: str, sample: Dict[str, Any]) -> str:
        """构建评估提示
        
        【学习笔记】GAIA 的简单提示词设计
        GAIA 的提示词非常简单，只包含问题本身，这是有意为之的设计。
        
        设计理念:
        1. 测试 Agent 的原生能力
           - 不提供详细的格式指导
           - 不提供示例
           - 让 Agent 自己决定如何回答
        
        2. 避免提示词工程
           - 评估的是 Agent 能力，不是提示词优化能力
           - 真实场景中用户不会给出详细指导
        
        3. 文件附件提示
           - 如果问题需要参考文件，会添加文件名提示
           - 但不会详细说明如何使用文件
        
        对比 BFCL:
        - BFCL: 详细的函数定义 + 格式要求 + 示例
        - GAIA: 只有问题本身 + 可选的文件提示
        
        示例:
            # 无附件的问题
            question = "What is the capital of France?"
            prompt = "What is the capital of France?"
            
            # 有附件的问题
            question = "What is shown in this image?"
            sample = {"file_name": "image_001.png"}
            prompt = "What is shown in this image?\n\nNote: This question may require reference to the file: image_001.png"
        
        Args:
            question: 问题文本
            sample: 样本数据（可能包含 file_name）
        
        Returns:
            构建好的提示词
        """
        # 提示词就是问题本身
        prompt = f"{question}"

        # 如果有文件附件，添加文件提示
        if sample.get("file_name"):
            prompt += f"\n\nNote: This question may require reference to the file: {sample['file_name']}"

        return prompt

    def _extract_answer(self, response: str) -> str:
        """从响应中提取答案（GAIA 格式）

        【学习笔记】答案提取策略
        GAIA 期望 Agent 使用 "FINAL ANSWER: [answer]" 格式，但为了容错，
        这个方法使用多层回退策略提取答案。
        
        提取策略（按优先级顺序）:
        
        1. GAIA 官方格式（最高优先级）
           - 模式: "FINAL ANSWER: xxx"
           - 不区分大小写
           - 移除可能的方括号 []
        
        2. 其他常见答案标记
           - "答案：xxx"
           - "最终答案：xxx"
           - "Final answer: xxx"
           - "Answer: xxx"
        
        3. 最后一个非空行（回退方案）
           - 如果没有找到任何标记
           - 返回最后一个非空且不以 # 开头的行
           - 忽略注释行
        
        4. 完整回复（最后回退）
           - 如果以上都失败，返回整个回复
        
        示例:
            # 策略1: GAIA 官方格式
            response = "Let me think... FINAL ANSWER: Paris"
            → 提取到 "Paris"
            
            # 策略2: 其他标记
            response = "经过分析，答案：42"
            → 提取到 "42"
            
            # 策略3: 最后一行
            response = "After calculation\nThe result is\n100"
            → 提取到 "100"
        
        Args:
            response: Agent 的完整回复
        
        Returns:
            提取的答案字符串
        """
        # 策略1: 首先尝试提取 GAIA 官方格式的答案
        final_answer_pattern = r'FINAL ANSWER:\s*(.+?)(?:\n|$)'
        match = re.search(final_answer_pattern, response, re.IGNORECASE | re.MULTILINE)
        if match:
            answer = match.group(1).strip()
            # 移除可能的方括号 (GAIA 有时使用 [answer] 格式)
            answer = answer.strip('[]')
            return answer

        # 策略2: 备用方案 - 查找其他答案标记
        answer_patterns = [
            r'答案[：:]\s*(.+)',  # 中文标记
            r'最终答案[：:]\s*(.+)',  # 中文最终答案
            r'Final answer[：:]\s*(.+)',  # 英文标记
            r'Answer[：:]\s*(.+)',  # 简单英文标记
        ]

        for pattern in answer_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # 策略3: 如果没有找到标记，返回最后一个非空行
        lines = response.strip().split('\n')
        for line in reversed(lines):  # 从后往前遍历
            line = line.strip()
            if line and not line.startswith('#'):  # 忽略空行和注释
                return line

        # 策略4: 最后回退 - 返回整个回复
        return response.strip()

    def _check_exact_match(self, predicted: str, expected: str) -> bool:
        """检查精确匹配
        
        【学习笔记】精确匹配判断
        判断 Agent 的答案是否与标准答案完全一致。
        
        匹配流程:
        1. 检查空值
           - 如果任何一个为空，返回 False
        
        2. 标准化处理
           - 调用 _normalize_answer() 标准化两个答案
           - 标准化包括: 转小写、移除冠词、移除符号等
        
        3. 字符串比较
           - 直接比较标准化后的字符串
           - 完全相同才返回 True
        
        示例:
            # 精确匹配
            predicted = "Paris"
            expected = "paris"  # 大小写不同但标准化后相同
            → True
            
            # 精确匹配
            predicted = "The Paris"
            expected = "Paris"  # 移除冠词 "The" 后相同
            → True
            
            # 不匹配
            predicted = "London"
            expected = "Paris"
            → False
        
        Args:
            predicted: Agent 的答案
            expected: 标准答案
        
        Returns:
            True 如果精确匹配，False 否则
        """
        # 检查空值
        if not predicted or not expected:
            return False

        # 标准化处理
        pred_normalized = self._normalize_answer(predicted)
        exp_normalized = self._normalize_answer(expected)

        # 字符串比较
        return pred_normalized == exp_normalized

    def _check_partial_match(self, predicted: str, expected: str) -> bool:
        """检查部分匹配
        
        【学习笔记】部分匹配判断
        判断 Agent 的答案是否包含正确信息，即使格式不完全一致。
        
        匹配策略（按顺序尝试）:
        
        1. 检查空值
           - 如果任何一个为空，返回 False
        
        2. 标准化处理
           - 调用 _normalize_answer() 标准化两个答案
        
        3. 包含关系检查
           - 检查标准答案是否包含在预测中
           - 或预测是否包含在标准答案中
           - 如果是，返回 True
        
        4. 关键词重叠度检查
           - 将两个答案分词
           - 计算共同词汇的比例
           - 如果 >= 70% 的标准答案词汇出现在预测中，认为部分匹配
        
        示例:
            # 包含关系匹配
            predicted = "The capital of France is Paris"
            expected = "Paris"
            → True (标准答案包含在预测中)
            
            # 关键词重叠匹配
            predicted = "New York City"
            expected = "New York"  # 2/2 = 100% 重叠
            → True
            
            # 不匹配
            predicted = "London"
            expected = "Paris New York"  # 0/2 = 0% 重叠
            → False
            
            # 边界情况
            predicted = "The answer is 42 meters"
            expected = "42 meters high"  # "42" "meters" 共同，2/3 = 66.7% < 70%
            → False
        
        Args:
            predicted: Agent 的答案
            expected: 标准答案
        
        Returns:
            True 如果部分匹配，False 否则
        """
        # 检查空值
        if not predicted or not expected:
            return False

        # 标准化处理
        pred_normalized = self._normalize_answer(predicted)
        exp_normalized = self._normalize_answer(expected)

        # 策略1: 检查包含关系
        if exp_normalized in pred_normalized or pred_normalized in exp_normalized:
            return True

        # 策略2: 检查关键词匹配
        pred_words = set(pred_normalized.split())  # 预测答案的词汇集合
        exp_words = set(exp_normalized.split())  # 标准答案的词汇集合

        if not exp_words:  # 标准答案为空
            return False

        # 计算重叠词汇数量
        overlap = len(pred_words & exp_words)  # 交集大小
        # 如果超过 70% 的期望词汇出现在预测中，认为部分匹配
        return overlap / len(exp_words) >= 0.7

    def _normalize_answer(self, answer: str) -> str:
        """标准化答案字符串（GAIA 官方标准化规则）

        【学习笔记】答案标准化规则
        根据 GAIA 论文的标准化规则，将答案转换为统一格式以便比较。
        
        标准化规则:
        1. 数字处理:
           - 移除逗号分隔符 (1,000 → 1000)
           - 移除货币符号 ($, €, £)
           - 移除百分号 (%)
        
        2. 字符串处理:
           - 转小写
           - 移除冠词 (the, a, an)
           - 移除多余空格
           - 移除末尾标点符号
        
        3. 列表处理:
           - 按逗号分隔
           - 每个元素独立标准化
           - 按字母顺序排序（保证顺序一致性）
        
        示例:
            # 数字标准化
            "$1,000" → "1000"
            "50%" → "50"
            
            # 字符串标准化
            "The Paris" → "paris"
            "New  York" → "new york"
            
            # 列表标准化
            "Paris, London, Berlin" → "berlin,london,paris" (排序后)
            "The London, Paris" → "london,paris"
        
        Args:
            answer: 原始答案字符串
        
        Returns:
            标准化后的答案字符串
        """
        if not answer:
            return ""

        answer = answer.strip()

        # 检查是否是逗号分隔的列表
        if ',' in answer:
            # 分隔并标准化每个元素
            parts = [self._normalize_single_answer(p.strip()) for p in answer.split(',')]
            # 按字母顺序排序（GAIA 要求，保证顺序一致性）
            parts.sort()
            return ','.join(parts)
        else:
            # 单个答案，直接标准化
            return self._normalize_single_answer(answer)

    def _normalize_single_answer(self, answer: str) -> str:
        """标准化单个答案（不包含逗号的答案）
        
        【学习笔记】单答案标准化步骤
        对单个答案进行详细的标准化处理。
        
        处理步骤:
        1. 转小写
           - 所有字母转为小写
           - 保证大小写不影响匹配
        
        2. 移除冠词
           - 移除开头的 the, a, an
           - 只移除第一个词，不影响中间的冠词
        
        3. 移除符号
           - 货币符号: $, €, £
           - 百分号: %
        
        4. 处理数字
           - 移除逗号分隔符 (1,000 → 1000)
           - 保留小数点 (3.14 保持不变)
        
        5. 清理空格
           - 移除多余空格
           - 多个空格合并为一个
        
        6. 移除末尾标点
           - 移除末尾的 . , ; : ! ?
        
        示例:
            "The Paris." → "paris"
            "$1,000" → "1000"
            "New  York" → "new york"
            "50%" → "50"
            "3.14" → "3.14" (小数点保留)
        
        Args:
            answer: 原始答案字符串
        
        Returns:
            标准化后的答案字符串
        """
        # 步骤1: 转小写
        answer = answer.strip().lower()

        # 步骤2: 移除常见的冠词（只移除开头的）
        articles = ['the', 'a', 'an']
        words = answer.split()
        if words and words[0] in articles:
            words = words[1:]  # 移除第一个词
            answer = ' '.join(words)

        # 步骤3: 移除货币符号和百分号
        answer = answer.replace('$', '').replace('%', '').replace('€', '').replace('£', '')

        # 步骤4: 移除数字中的逗号分隔符（如 1,000 -> 1000）
        # 但保留小数点（正则只匹配数字间的逗号）
        answer = re.sub(r'(\d),(\d)', r'\1\2', answer)

        # 步骤5: 移除多余空格
        answer = ' '.join(answer.split())

        # 步骤6: 移除末尾的标点符号
        answer = answer.rstrip('.,;:!?')

        return answer

    def export_to_gaia_format(
        self,
        results: Dict[str, Any],
        output_path: Union[str, Path],
        include_reasoning: bool = True
    ) -> None:
        """导出为 GAIA 官方格式

        【学习笔记】官方格式导出
        将评估结果导出为 GAIA 官方要求的 JSONL 格式，用于提交到排行榜。

        GAIA 官方格式要求:
        1. 文件格式: JSONL (JSON Lines)
           - 每行一个 JSON 对象
           - 不是一个 JSON 数组
        
        2. 必需字段:
           - task_id: 任务 ID
           - model_answer: Agent 的答案
        
        3. 可选字段:
           - reasoning_trace: Agent 的完整推理过程
        
        文件示例:
            {"task_id": "001", "model_answer": "Paris", "reasoning_trace": "..."}
            {"task_id": "002", "model_answer": "42", "reasoning_trace": "..."}
            {"task_id": "003", "model_answer": "London", "reasoning_trace": "..."}
        
        使用场景:
        - 提交到 GAIA 官方排行榜
        - 与其他模型比较
        - 存档评估结果
        
        示例:
            # 评估完成后导出
            evaluator = GAIAEvaluator()
            results = evaluator.evaluate(agent)
            
            # 导出为官方格式
            evaluator.export_to_gaia_format(
                results=results,
                output_path="./gaia_submission.jsonl",
                include_reasoning=True  # 包含推理过程
            )

        Args:
            results: 评估结果字典 (evaluate() 方法返回的结果)
            output_path: 输出文件路径 (.jsonl 文件)
            include_reasoning: 是否包含推理轨迹 (Agent 的完整回复)
        """
        # 转换为 Path 对象
        output_path = Path(output_path)
        # 创建父目录（如果不存在）
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 提取详细结果
        detailed_results = results.get("detailed_results", [])

        # 写入 JSONL 文件
        with open(output_path, 'w', encoding='utf-8') as f:
            for result in detailed_results:
                # 构建 GAIA 格式的结果对象
                gaia_result = {
                    "task_id": result.get("task_id", ""),  # 任务 ID
                    "model_answer": result.get("predicted", "")  # Agent 的答案
                }

                # 如果需要，添加推理轨迹
                if include_reasoning:
                    gaia_result["reasoning_trace"] = result.get("response", "")  # Agent 的完整回复

                # 写入一行 JSON
                f.write(json.dumps(gaia_result, ensure_ascii=False) + '\n')

        # 打印导出信息
        print(f" GAIA 格式结果已导出")
        print(f"   输出文件: {output_path}")
        print(f"   样本数: {len(detailed_results)}")
        print(f"   包含推理轨迹: {include_reasoning}")


