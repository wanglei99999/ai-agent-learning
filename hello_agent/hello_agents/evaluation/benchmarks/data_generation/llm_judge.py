"""
LLM Judge Evaluator

学习笔记模块作用
使用 LLM 作为评委评估 AI 生成数学题目的质量。

什么是 LLM Judge？
- 用 LLM（如 GPT-4）作为评委
- 从多个维度评估题目质量
- 给出 1-5 分的评分和详细理由
- 适用于主观质量评估

为什么用 LLM Judge？
1. 主观质量难以量化
   - 题目清晰度、难度匹配等难以用算法衡量
   - LLM 可以像人一样理解和评估

2. 多维度评估
   - 同时考虑正确性、清晰度、难度、完整性
   - 给出综合评价

3. 可解释性
   - 不只给分数，还给出详细理由
   - 帮助理解问题所在

评估维度：
1. Correctness（正确性）：数学逻辑和答案是否正确
2. Clarity（清晰度）：问题表述和解答是否清晰
3. Difficulty Match（难度匹配）：是否符合 AIME 标准
4. Completeness（完整性）：解答步骤是否完整

使用流程：
  生成题目 → 构建评估 prompt → LLM 评分 → 解析结果 → 计算统计指标
"""

import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from hello_agents.core.llm import HelloAgentsLLM


class LLMJudgeEvaluator:
    """LLM Judge 评估器
    
    【学习笔记】核心功能
    使用 LLM 作为评委，从多个维度评估题目质量。
    
    评估方式：
    - 给每个维度打分（1-5 分）
    - 计算总分（四个维度的平均分）
    - 给出详细评价理由
    
    输出指标：
    - average_total_score: 平均总分
    - dimension_averages: 各维度平均分
    - pass_rate: 通过率（总分 >= 3.5）
    - excellent_rate: 优秀率（总分 >= 4.5）
    
    使用场景：
    - 评估生成题目的绝对质量
    - 分析生成模型的优劣势
    - 为模型改进提供方向
    """
    
    # 评估维度（四个核心维度）
    EVALUATION_DIMENSIONS = [
        "correctness",      # 正确性：数学逻辑和答案是否正确
        "clarity",          # 清晰度：问题表述和解答是否清晰
        "difficulty_match", # 难度匹配：是否符合 AIME 标准（6-9/15）
        "completeness"      # 完整性：解答步骤是否完整
    ]
    
    def __init__(
        self,
        llm: Optional[HelloAgentsLLM] = None,
        judge_model: str = "gpt-4o"
    ):
        """初始化 LLM Judge 评估器
        
        【学习笔记】初始化说明
        设置评委 LLM 模型。
        
        评委模型选择：
        - 默认: gpt-4o（推荐，评估质量高）
        - 可选: gpt-4, claude-3-opus 等
        - 要求: 需要较强的理解和评估能力
        
        为什么用 GPT-4o？
        - 数学能力强：能理解 AIME 级别的题目
        - 评估公正：评分相对客观
        - 输出稳定：能按要求输出 JSON 格式
        
        示例：
            # 使用默认模型
            evaluator = LLMJudgeEvaluator()
            
            # 指定模型
            evaluator = LLMJudgeEvaluator(judge_model="gpt-4")
            
            # 使用自定义 LLM 实例
            my_llm = HelloAgentsLLM(model="claude-3-opus")
            evaluator = LLMJudgeEvaluator(llm=my_llm)
        
        Args:
            llm: LLM 实例，如果为 None 则创建新实例
            judge_model: 评委模型名称
        """
        # 创建或使用提供的 LLM 实例
        self.llm = llm or HelloAgentsLLM(model=judge_model)
        # 保存模型名称
        self.judge_model = judge_model
        
    def evaluate_single(
        self,
        problem: Dict[str, Any],
        reference: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """评估单个问题
        
        【学习笔记】单题评估流程
        对单个题目进行详细评估。
        
        评估步骤：
        1. 构建评估 prompt
           - 包含待评估题目
           - 可选包含参考题目（AIME 真题）
           - 说明评估维度和评分标准
        
        2. 调用 LLM 评分
           - 发送 prompt 给评委 LLM
           - LLM 返回 JSON 格式的评分
        
        3. 解析评分
           - 提取四个维度的分数
           - 处理解析失败的情况
        
        4. 计算总分
           - 总分 = 四个维度的平均分
        
        为什么需要 reference？
        - 提供参考标准：让 LLM 知道 AIME 真题的水平
        - 对比评估：帮助 LLM 更准确地评估难度和质量
        - 可选提供：也可以不提供
        
        示例：
            evaluator = LLMJudgeEvaluator()
            
            # 无参考评估
            result = evaluator.evaluate_single(generated_problem)
            print(f"总分: {result['total_score']:.2f}")
            print(f"正确性: {result['scores']['correctness']}")
            
            # 有参考评估
            result = evaluator.evaluate_single(
                problem=generated_problem,
                reference=aime_problem
            )
        
        Args:
            problem: 待评估的问题
            reference: 参考问题（可选，通常是 AIME 真题）
        
        Returns:
            评估结果字典
        """
        start_time = time.time()
        
        # 步骤1: 构建评估提示词
        prompt = self._build_evaluation_prompt(problem, reference)

        # 步骤2: 调用 LLM 进行评估
        messages = [{"role": "user", "content": prompt}]
        response = self.llm.invoke(messages)
        
        # 步骤3: 解析评估结果
        scores = self._parse_evaluation_response(response)
        
        # 步骤4: 计算总分（四个维度的平均分）
        total_score = sum(scores.values()) / len(scores)
        
        execution_time = time.time() - start_time
        
        # 返回评估结果
        return {
            "problem_id": problem.get("problem_id", "unknown"),  # 题目 ID
            "scores": scores,  # 各维度评分
            "total_score": total_score,  # 总分
            "evaluation_text": response,  # LLM 的完整评价
            "execution_time": execution_time  # 执行时间
        }
    
    def evaluate_batch(
        self,
        problems: List[Dict[str, Any]],
        references: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """批量评估问题
        
        【学习笔记】批量评估流程
        对多个题目进行批量评估，并计算统计指标。
        
        评估流程：
        1. 逐个评估题目
           - 调用 evaluate_single() 评估每个题目
           - 每 10 个题目显示一次进度
        
        2. 计算统计指标
           - 平均总分
           - 各维度平均分
           - 通过率（>= 3.5 分）
           - 优秀率（>= 4.5 分）
        
        3. 返回结果
           - 详细结果（每个题目）
           - 统计指标
           - 评估元数据
        
        references 参数说明：
        - 如果提供，应与 problems 一一对应
        - 每个生成题目对应一个参考题目
        - 可以不提供，则所有题目都无参考
        
        示例：
            evaluator = LLMJudgeEvaluator()
            
            # 批量评估（无参考）
            results = evaluator.evaluate_batch(generated_problems)
            print(f"平均分: {results['metrics']['average_total_score']:.2f}")
            print(f"通过率: {results['metrics']['pass_rate']:.2%}")
            
            # 批量评估（有参考）
            results = evaluator.evaluate_batch(
                problems=generated_problems,
                references=aime_problems
            )
        
        Args:
            problems: 待评估的问题列表
            references: 参考问题列表（可选）
        
        Returns:
            评估结果汇总
        """
        print(f"\n 开始 LLM Judge 评估")
        print(f"   评委模型: {self.judge_model}")
        print(f"   评估数量: {len(problems)}")
        print(f"   评估维度: {', '.join(self.EVALUATION_DIMENSIONS)}")
        
        # 逐个评估题目
        results = []
        for idx, problem in enumerate(problems):
            print(f"\n   评估进度: {idx + 1}/{len(problems)}")
            
            # 获取对应的参考题目（如果有）
            reference = references[idx] if references and idx < len(references) else None
            
            # 评估单个题目
            result = self.evaluate_single(problem, reference)
            results.append(result)
            
            # 显示评分
            print(f"   ✓ {problem.get('problem_id', 'unknown')}: {result['total_score']:.2f}/5.0")
        
        # 计算统计指标
        metrics = self._compute_metrics(results)
        
        # 返回完整结果
        return {
            "results": results,  # 每个题目的详细评估结果
            "metrics": metrics,  # 统计指标
            "evaluation_date": datetime.now().isoformat(),  # 评估日期
            "judge_model": self.judge_model,  # 评委模型
            "num_problems": len(problems)  # 评估题目数
        }
    
    def _build_evaluation_prompt(
        self,
        problem: Dict[str, Any],
        reference: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建评估提示词"""
        prompt = f"""你是一位专业的数学题目评估专家。请评估以下AIME风格数学题目的质量。

【待评估题目】
问题: {problem.get('problem', '')}
答案: {problem.get('answer', '')}
解答: {problem.get('solution', '')}
"""
        
        if reference:
            prompt += f"""
【参考题目（AIME真题）】
问题: {reference.get('problem', '')}
答案: {reference.get('answer', '')}
解答: {reference.get('solution', '')}
"""
        
        prompt += """
请从以下四个维度评估题目质量（每个维度1-5分）：

1. **正确性 (Correctness)**: 数学逻辑是否正确，答案是否准确
2. **清晰度 (Clarity)**: 问题表述是否清晰，解答是否易懂
3. **难度匹配 (Difficulty Match)**: 难度是否符合AIME标准（6-9/15）
4. **完整性 (Completeness)**: 解答步骤是否完整，是否包含必要的推理

请按以下JSON格式输出评分：
```json
{
    "correctness": 5,
    "clarity": 4,
    "difficulty_match": 4,
    "completeness": 5,
    "comments": "详细评价..."
}
```
"""
        return prompt
    
    def _parse_evaluation_response(self, response: str) -> Dict[str, float]:
        """解析 LLM 评估响应
        
        【学习笔记】JSON 解析策略
        从 LLM 的回复中提取评分 JSON。
        
        解析策略（按顺序尝试）：
        1. 查找 ```json ... ``` 代码块
        2. 查找 ``` ... ``` 代码块
        3. 直接解析整个回复
        
        预期的 JSON 格式：
            {
                "correctness": 5,
                "clarity": 4,
                "difficulty_match": 4,
                "completeness": 5,
                "comments": "详细评价..."
            }
        
        容错处理：
        - 如果解析失败，返回默认评分（每个维度 3.0 分）
        - 如果某个维度缺失，使用 3.0 分
        - 打印警告信息但不中断评估
        
        为什么需要多种解析策略？
        - LLM 输出格式可能不一致
        - 有时带代码块，有时不带
        - 提高解析成功率
        
        Args:
            response: LLM 的完整回复
        
        Returns:
            各维度评分字典
        """
        try:
            # 策略1: 提取 JSON 代码块
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            # 策略2: 解析 JSON
            data = json.loads(json_str)
            
            # 策略3: 提取评分（容错处理）
            scores = {}
            for dim in self.EVALUATION_DIMENSIONS:
                scores[dim] = float(data.get(dim, 3.0))  # 缺失时默认 3.0 分
            
            return scores
            
        except Exception as e:
            # 解析失败，返回默认评分
            print(f" 解析评估响应失败: {e}")
            # 所有维度都给 3.0 分（中等水平）
            return {dim: 3.0 for dim in self.EVALUATION_DIMENSIONS}
    
    def _compute_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算评估指标
        
        【学习笔记】统计指标计算
        从所有评估结果中计算统计指标。
        
        计算的指标：
        1. average_total_score: 平均总分
           - 所有题目总分的平均值
           - 反映整体质量水平
        
        2. dimension_averages: 各维度平均分
           - 每个维度的平均分
           - 帮助发现优劣势（哪个维度表现好/差）
        
        3. pass_rate: 通过率
           - 总分 >= 3.5 的题目比例
           - 3.5 分以上认为质量合格
        
        4. excellent_rate: 优秀率
           - 总分 >= 4.5 的题目比例
           - 4.5 分以上认为质量优秀
        
        评分标准：
        - 1.0-2.4: 不合格
        - 2.5-3.4: 勉强合格
        - 3.5-4.4: 合格
        - 4.5-5.0: 优秀
        
        示例输出：
            {
                "average_total_score": 4.2,
                "dimension_averages": {
                    "correctness": 4.5,
                    "clarity": 4.0,
                    "difficulty_match": 4.1,
                    "completeness": 4.2
                },
                "pass_rate": 0.85,  # 85% 通过
                "excellent_rate": 0.30  # 30% 优秀
            }
        
        Args:
            results: 所有题目的评估结果列表
        
        Returns:
            统计指标字典
        """
        if not results:
            return {}
        
        # 收集所有评分
        dimension_scores = {dim: [] for dim in self.EVALUATION_DIMENSIONS}
        total_scores = []
        
        for result in results:
            total_scores.append(result["total_score"])
            for dim in self.EVALUATION_DIMENSIONS:
                dimension_scores[dim].append(result["scores"][dim])
        
        # 计算各项指标
        metrics = {
            # 平均总分
            "average_total_score": sum(total_scores) / len(total_scores),
            
            # 各维度平均分
            "dimension_averages": {
                dim: sum(scores) / len(scores)
                for dim, scores in dimension_scores.items()
            },
            
            # 通过率（>= 3.5 分）
            "pass_rate": sum(1 for s in total_scores if s >= 3.5) / len(total_scores),
            
            # 优秀率（>= 4.5 分）
            "excellent_rate": sum(1 for s in total_scores if s >= 4.5) / len(total_scores)
        }
        
        return metrics
    
    def export_results(
        self,
        results: Dict[str, Any],
        output_path: str
    ):
        """导出评估结果
        
        【学习笔记】结果导出
        将评估结果保存为 JSON 文件。
        
        导出内容：
        - results: 每个题目的详细评估结果
        - metrics: 统计指标
        - evaluation_date: 评估日期
        - judge_model: 评委模型
        - num_problems: 评估题目数
        
        文件格式：
        - JSON 格式
        - UTF-8 编码
        - 缩进 2 个空格（易读）
        - 中文不转义（ensure_ascii=False）
        
        使用场景：
        - 保存评估结果供后续分析
        - 对比不同模型的评估结果
        - 生成评估报告
        
        示例：
            evaluator = LLMJudgeEvaluator()
            results = evaluator.evaluate_batch(problems)
            evaluator.export_results(results, "llm_judge_results.json")
        
        Args:
            results: evaluate_batch() 返回的结果
            output_path: 输出文件路径
        """
        # 写入 JSON 文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n 评估结果已保存: {output_path}")

