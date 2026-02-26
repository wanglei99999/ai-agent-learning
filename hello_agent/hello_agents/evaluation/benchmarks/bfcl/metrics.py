"""
BFCL 评估指标模块

本模块提供各种评估指标的计算方法，用于量化模型在函数调用任务上的表现。

核心职责:
  1. 计算基础指标: 准确率、成功率
  2. 计算高级指标: F1分数、精确率、召回率
  3. 计算参数准确率: 评估参数填写的正确性
  4. 计算AST匹配度: 评估函数调用结构的相似性
  5. 统计分析: 按类别统计、函数调用统计、分数分布

在评估流程中的位置:
  evaluator.py 收集原始结果 → metrics.py 计算统计指标 → 输出可读报告
  
  原始结果示例:
    [{success: True, score: 1.0}, {success: False, score: 0.0}, ...]
  
  计算后的指标:
    {accuracy: 0.5, precision: 0.6, recall: 0.7, f1: 0.65, ...}
"""

from typing import Dict, Any, List, Optional
import json
import ast
import numpy as np


class BFCLMetrics:
    """BFCL 评估指标计算器

    提供静态方法和实例方法来计算各种评估指标。

    主要指标说明:
    
    1. 准确率 (Accuracy)
       定义: 完全正确的样本数 / 总样本数
       示例: 10个样本中8个正确 → accuracy = 0.8
    
    2. AST 匹配度 (AST Match)
       定义: 通过抽象语法树比较函数调用的结构相似性
       用途: 判断两个函数调用在语义上是否等价
       示例: "func(a=1, b=2)" 和 "func(b=2, a=1)" → AST匹配度 = 1.0
    
    3. 参数准确率 (Parameter Accuracy)
       定义: 正确参数数量 / 总参数数量
       示例: 3个参数中2个正确 → param_accuracy = 0.67
    
    4. 精确率 (Precision)
       定义: 预测为正确的样本中真正正确的比例
       公式: TP / (TP + FP)
    
    5. 召回率 (Recall)
       定义: 所有正确样本中被预测出来的比例
       公式: TP / (TP + FN)
    
    6. F1 分数
       定义: 精确率和召回率的调和平均
       公式: 2 * (precision * recall) / (precision + recall)
    
    使用示例:
        >>> metrics = BFCLMetrics()
        >>> results = [{"success": True, "score": 1.0}, ...]
        >>> stats = metrics.compute_metrics(results)
        >>> print(stats["accuracy"])  # 0.8
    """

    @staticmethod
    def calculate_accuracy(predictions: List[Any], references: List[Any]) -> float:
        """计算准确率 (逐元素对比)

        对比两个列表中对应位置的元素，计算完全匹配的比例。
        
        计算公式:
            accuracy = 匹配元素数 / min(预测列表长度, 参考列表长度)
        
        示例:
            predictions = ["A", "B", "C", "D"]
            references  = ["A", "X", "C", "D"]
            
            逐个对比:
              "A" == "A" ✓
              "B" == "X" ✗
              "C" == "C" ✓
              "D" == "D" ✓
            
            accuracy = 3/4 = 0.75

        Args:
            predictions: 预测结果列表
            references: 参考答案列表

        Returns:
            准确率 (0.0-1.0)
        """
        if not predictions or not references:
            return 0.0

        # 取较短列表的长度，避免索引越界
        min_len = min(len(predictions), len(references))
        
        # 逐个对比，统计匹配数量
        correct = sum(1 for p, r in zip(predictions[:min_len], references[:min_len]) if p == r)
        
        return correct / min_len

    @staticmethod
    def calculate_ast_match(predicted: str, expected: str) -> float:
        """计算 AST 匹配度

        通过解析抽象语法树来比较两个函数调用的结构相似性。
        
        为什么用 AST 而不是字符串比较?
        因为以下两个调用在语义上完全等价，但字符串不同:
          "calculate_area(base=10, height=5)"
          "calculate_area(height=5, base=10)"  # 参数顺序不同
        
        AST 解析后会提取出结构，忽略表面差异。
        
        评估流程:
          1. 尝试将两个字符串解析为 AST
          2. 转换为字符串表示 (ast.dump)
          3. 如果完全匹配 → 返回 1.0
          4. 如果部分匹配 → 计算相似度 (0.0-1.0)
          5. 如果解析失败 → 回退到字符串相似度
        
        示例1 (完全匹配):
            predicted = "func(a=1, b=2)"
            expected  = "func(b=2, a=1)"
            → AST结构相同 → 返回 1.0
        
        示例2 (部分匹配):
            predicted = "func(a=1, b=2)"
            expected  = "func(a=1, c=3)"
            → AST结构不同 → 计算相似度 → 返回 0.5

        Args:
            predicted: 预测的函数调用字符串
            expected: 期望的函数调用字符串

        Returns:
            匹配度 (0.0-1.0)，1.0表示完全匹配
        """
        try:
            # 步骤1: 解析为AST (mode='eval' 表示解析表达式)
            pred_ast = ast.parse(predicted, mode='eval')
            exp_ast = ast.parse(expected, mode='eval')

            # 步骤2: 转换为字符串表示，便于比较
            # ast.dump() 会输出类似: "Call(func=Name(id='func'), keywords=[...])"
            pred_dump = ast.dump(pred_ast)
            exp_dump = ast.dump(exp_ast)

            # 步骤3: 完全匹配检查
            if pred_dump == exp_dump:
                return 1.0

            # 步骤4: 计算结构相似度 (基于词汇重叠)
            similarity = BFCLMetrics._calculate_string_similarity(pred_dump, exp_dump)
            return similarity

        except SyntaxError:
            # 步骤5: AST解析失败时回退到简单字符串相似度
            # 例如输入不是合法的Python表达式
            return BFCLMetrics._calculate_string_similarity(predicted, expected)

    @staticmethod
    def _calculate_string_similarity(s1: str, s2: str) -> float:
        """计算字符串相似度 (基于词汇重叠的 Jaccard 相似度)
        
        算法: Jaccard 相似度 = 交集大小 / 并集大小
        
        步骤:
          1. 将字符串按空格分词
          2. 转换为集合
          3. 计算交集和并集
          4. 返回 |交集| / |并集|
        
        示例:
            s1 = "calculate area base height"
            s2 = "calculate area width length"
            
            set1 = {"calculate", "area", "base", "height"}
            set2 = {"calculate", "area", "width", "length"}
            
            交集 = {"calculate", "area"}  → 2个词
            并集 = {"calculate", "area", "base", "height", "width", "length"}  → 6个词
            
            相似度 = 2/6 = 0.33
        
        Args:
            s1: 第一个字符串
            s2: 第二个字符串
        
        Returns:
            相似度 (0.0-1.0)
        """
        # 边界情况: 完全相同
        if s1 == s2:
            return 1.0
        
        # 边界情况: 有空字符串
        if not s1 or not s2:
            return 0.0

        # 步骤1-2: 分词并转换为集合
        set1 = set(s1.split())
        set2 = set(s2.split())

        if not set1 or not set2:
            return 0.0

        # 步骤3: 计算交集和并集
        intersection = len(set1 & set2)  # & 是集合交集运算符
        union = len(set1 | set2)          # | 是集合并集运算符

        # 步骤4: 返回 Jaccard 相似度
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def calculate_parameter_accuracy(
        predicted_params: Dict[str, Any],
        expected_params: Dict[str, Any]
    ) -> float:
        """计算参数准确率

        逐个参数对比，计算正确参数的比例。
        
        计算公式:
            param_accuracy = 正确参数数 / 期望参数总数
        
        示例:
            predicted_params = {"base": 10, "height": 5, "unit": "cm"}
            expected_params  = {"base": 10, "height": 8, "unit": "cm"}
            
            逐个对比:
              "base": 10 == 10 ✓
              "height": 5 == 8 ✗
              "unit": "cm" == "cm" ✓
            
            param_accuracy = 2/3 = 0.67
        
        边界情况:
          - 期望参数为空 且 预测参数也为空 → 1.0 (都对)
          - 期望参数为空 但 预测参数不为空 → 0.0 (多余参数)
          - 预测参数为空 但 期望参数不为空 → 0.0 (缺少参数)

        Args:
            predicted_params: 预测的参数字典
            expected_params: 期望的参数字典

        Returns:
            参数准确率 (0.0-1.0)
        """
        # 边界情况1: 期望参数为空
        if not expected_params:
            return 1.0 if not predicted_params else 0.0

        # 边界情况2: 预测参数为空但期望不为空
        if not predicted_params:
            return 0.0

        # 逐个参数对比
        correct = 0
        for key, expected_value in expected_params.items():
            if key in predicted_params:
                predicted_value = predicted_params[key]
                # 使用智能匹配 (支持数值容差、字符串忽略大小写等)
                if BFCLMetrics._values_match(predicted_value, expected_value):
                    correct += 1

        return correct / len(expected_params)

    @staticmethod
    def _values_match(v1: Any, v2: Any) -> bool:
        """智能值匹配 (支持多种类型的容错比较)
        
        根据值的类型选择不同的比较策略:
        
        1. 数值类型 (int, float):
           使用容差比较，避免浮点数精度问题
           示例: 10.0 和 10.000001 → True (差值 < 1e-6)
        
        2. 字符串类型:
           忽略大小写和首尾空格
           示例: "  Hello  " 和 "hello" → True
        
        3. 列表类型:
           递归比较每个元素
           示例: [1, "a"] 和 [1, "A"] → True (字符串忽略大小写)
        
        4. 字典类型:
           递归比较每个键值对
           示例: {"a": 1} 和 {"a": 1.0} → True (数值容差)
        
        5. 其他类型:
           使用 == 直接比较
        
        Args:
            v1: 第一个值
            v2: 第二个值
        
        Returns:
            是否匹配
        """
        # 策略1: 数值类型 - 容差比较
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            # 允许 1e-6 的误差，避免浮点数精度问题
            return abs(v1 - v2) < 1e-6

        # 策略2: 字符串类型 - 忽略大小写和空格
        if isinstance(v1, str) and isinstance(v2, str):
            return v1.strip().lower() == v2.strip().lower()

        # 策略3: 列表类型 - 递归比较
        if isinstance(v1, list) and isinstance(v2, list):
            if len(v1) != len(v2):
                return False
            # 逐元素递归比较
            return all(BFCLMetrics._values_match(a, b) for a, b in zip(v1, v2))

        # 策略4: 字典类型 - 递归比较
        if isinstance(v1, dict) and isinstance(v2, dict):
            # 先检查键是否相同
            if set(v1.keys()) != set(v2.keys()):
                return False
            # 逐键值对递归比较
            return all(BFCLMetrics._values_match(v1[k], v2[k]) for k in v1.keys())

        # 策略5: 其他类型 - 直接比较
        return v1 == v2

    def compute_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算综合指标 (从原始评估结果中提取各种统计信息)

        这是 metrics 模块的核心方法，将 evaluator 收集的原始结果转换为可读的统计报告。
        
        输入示例 (evaluator 传入的 results):
            [
                {"success": True, "score": 1.0, "category": "simple_python", "execution_time": 0.5, ...},
                {"success": False, "score": 0.0, "category": "multiple", "execution_time": 0.3, ...},
                ...
            ]
        
        输出示例:
            {
                "total_samples": 10,
                "success_count": 8,
                "accuracy": 0.8,
                "average_score": 0.85,
                "average_execution_time": 0.4,
                "category_metrics": {"simple_python": {"total": 5, "success": 4, "accuracy": 0.8}},
                "function_call_stats": {"total_function_calls": 12, "successful_calls": 10, ...},
                "score_distribution": {"min": 0.0, "max": 1.0, "mean": 0.85, ...}
            }

        Args:
            results: 评估结果列表，每个元素是一个样本的评估结果字典

        Returns:
            综合指标字典，包含准确率、分类统计、函数调用统计等
        """
        if not results:
            return self._empty_metrics()

        total = len(results)

        # === 基础指标 ===
        # 统计成功样本数和准确率
        success_count = sum(1 for r in results if r.get("success", False))
        accuracy = success_count / total

        # === 分数统计 ===
        # 提取所有样本的分数并计算平均值
        scores = [r.get("score", 0.0) for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # === 执行时间统计 ===
        # 计算平均执行时间 (只统计有记录的样本)
        execution_times = [r.get("execution_time", 0.0) for r in results if "execution_time" in r]
        avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0.0

        # === 按类别统计 ===
        # 分别统计每个类别 (simple_python, multiple 等) 的表现
        category_metrics = self._compute_category_metrics(results)

        # === 函数调用统计 ===
        # 统计函数调用的总数、成功数、唯一函数名等
        function_call_stats = self._compute_function_call_stats(results)

        return {
            "total_samples": total,
            "success_count": success_count,
            "accuracy": accuracy,
            "average_score": avg_score,
            "average_execution_time": avg_execution_time,
            "category_metrics": category_metrics,
            "function_call_stats": function_call_stats,
            "score_distribution": self._compute_score_distribution(scores)
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        """返回空指标 (当没有评估结果时使用)
        
        用于边界情况处理，避免返回 None 或抛出异常。
        """
        return {
            "total_samples": 0,
            "success_count": 0,
            "accuracy": 0.0,
            "average_score": 0.0,
            "average_execution_time": 0.0,
            "category_metrics": {},
            "function_call_stats": {},
            "score_distribution": {}
        }

    def _compute_category_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """计算分类别指标 (按 BFCL 类别分组统计)
        
        将结果按类别 (simple_python, multiple, parallel 等) 分组，
        分别计算每个类别的准确率和平均分数。
        
        示例:
            输入 results:
                [
                    {"category": "simple_python", "success": True, "score": 1.0},
                    {"category": "simple_python", "success": False, "score": 0.0},
                    {"category": "multiple", "success": True, "score": 1.0},
                ]
            
            输出:
                {
                    "simple_python": {
                        "total": 2,
                        "success": 1,
                        "accuracy": 0.5,
                        "average_score": 0.5
                    },
                    "multiple": {
                        "total": 1,
                        "success": 1,
                        "accuracy": 1.0,
                        "average_score": 1.0
                    }
                }
        
        Returns:
            按类别分组的指标字典
        """
        categories = {}

        # 第一遍遍历: 收集每个类别的原始数据
        for result in results:
            category = result.get("category", "unknown")
            if category not in categories:
                categories[category] = {
                    "total": 0,
                    "success": 0,
                    "scores": []
                }

            categories[category]["total"] += 1
            if result.get("success", False):
                categories[category]["success"] += 1
            categories[category]["scores"].append(result.get("score", 0.0))

        # 第二遍遍历: 计算每个类别的统计信息
        category_metrics = {}
        for category, stats in categories.items():
            accuracy = stats["success"] / stats["total"] if stats["total"] > 0 else 0.0
            avg_score = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0.0

            category_metrics[category] = {
                "total": stats["total"],
                "success": stats["success"],
                "accuracy": accuracy,
                "average_score": avg_score
            }

        return category_metrics

    def _compute_function_call_stats(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算函数调用统计 (分析模型调用了哪些函数)
        
        统计所有样本中模型预测的函数调用情况，包括:
        - 总调用次数
        - 成功调用次数
        - 唯一函数名数量
        - 平均每样本调用次数
        
        示例:
            输入 results:
                [
                    {"predicted": [{"name": "func_a"}, {"name": "func_b"}], "success": True},
                    {"predicted": [{"name": "func_a"}], "success": False},
                ]
            
            输出:
                {
                    "total_function_calls": 3,      # 总共调用了3次函数
                    "successful_calls": 2,          # 第一个样本成功，2次调用算成功
                    "unique_functions": 2,          # 用到了2个不同的函数
                    "function_names": ["func_a", "func_b"],
                    "avg_calls_per_sample": 1.5     # 平均每样本1.5次调用
                }
        
        Returns:
            函数调用统计字典
        """
        total_calls = 0
        successful_calls = 0
        function_names = set()

        for result in results:
            predicted = result.get("predicted", [])
            if isinstance(predicted, list):
                total_calls += len(predicted)
                for call in predicted:
                    if isinstance(call, dict) and "name" in call:
                        function_names.add(call["name"])
                        # 如果整个样本成功，则该样本的所有调用都算成功
                        if result.get("success", False):
                            successful_calls += 1

        return {
            "total_function_calls": total_calls,
            "successful_calls": successful_calls,
            "unique_functions": len(function_names),
            "function_names": sorted(list(function_names)),
            "avg_calls_per_sample": total_calls / len(results) if results else 0.0
        }

    def _compute_score_distribution(self, scores: List[float]) -> Dict[str, Any]:
        """计算分数分布 (统计学分析)
        
        计算分数的各种统计量，帮助理解模型表现的分布情况。
        
        统计量说明:
        - min/max: 最低/最高分
        - mean: 平均分
        - median: 中位数 (排序后中间的值)
        - std: 标准差 (衡量分数的离散程度)
        - quartiles: 四分位数 (Q1=25%, Q2=50%, Q3=75%)
        
        示例:
            scores = [0.0, 0.5, 0.8, 0.9, 1.0]
            
            输出:
                {
                    "min": 0.0,
                    "max": 1.0,
                    "mean": 0.64,
                    "median": 0.8,
                    "std": 0.36,
                    "quartiles": {"q1": 0.5, "q2": 0.8, "q3": 0.9}
                }
        
        Returns:
            分数分布统计字典
        """
        if not scores:
            return {}

        return {
            "min": min(scores),
            "max": max(scores),
            "mean": sum(scores) / len(scores),
            "median": sorted(scores)[len(scores) // 2],
            "std": np.std(scores) if len(scores) > 1 else 0.0,
            "quartiles": {
                "q1": sorted(scores)[len(scores) // 4],      # 第一四分位数 (25%)
                "q2": sorted(scores)[len(scores) // 2],      # 第二四分位数 (50%, 即中位数)
                "q3": sorted(scores)[3 * len(scores) // 4]   # 第三四分位数 (75%)
            }
        }

    @staticmethod
    def calculate_f1_score(precision: float, recall: float) -> float:
        """计算 F1 分数 (精确率和召回率的调和平均)

        F1 分数综合考虑了精确率和召回率，是两者的调和平均数。
        
        公式:
            F1 = 2 * (precision * recall) / (precision + recall)
        
        为什么用调和平均而不是算术平均?
        因为调和平均对极端值更敏感，能更好地平衡两个指标。
        
        示例:
            precision = 0.8, recall = 0.6
            
            算术平均: (0.8 + 0.6) / 2 = 0.7
            调和平均 (F1): 2 * (0.8 * 0.6) / (0.8 + 0.6) = 0.686
            
            F1 更接近较低的那个值，鼓励两个指标都高。

        Args:
            precision: 精确率 (0.0-1.0)
            recall: 召回率 (0.0-1.0)

        Returns:
            F1 分数 (0.0-1.0)
        """
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    @staticmethod
    def calculate_precision_recall(
        predicted: List[Dict[str, Any]],
        expected: List[Dict[str, Any]]
    ) -> tuple[float, float]:
        """计算精确率和召回率 (基于函数名匹配)

        精确率 (Precision): 预测为正确的函数中真正正确的比例
        召回率 (Recall): 所有正确函数中被预测出来的比例
        
        计算公式:
            precision = TP / (TP + FP) = 正确预测数 / 总预测数
            recall = TP / (TP + FN) = 正确预测数 / 总期望数
        
        示例:
            predicted = [{"name": "func_a"}, {"name": "func_b"}, {"name": "func_c"}]
            expected  = [{"name": "func_a"}, {"name": "func_b"}]
            
            预测的函数名: {"func_a", "func_b", "func_c"}
            期望的函数名: {"func_a", "func_b"}
            交集 (TP): {"func_a", "func_b"}  → 2个
            
            precision = 2 / 3 = 0.67  (预测了3个，对了2个)
            recall = 2 / 2 = 1.0      (期望2个，都预测到了)
        
        注意: 这是简化版本，只比较函数名，不比较参数。

        Args:
            predicted: 预测的函数调用列表
            expected: 期望的函数调用列表

        Returns:
            (precision, recall) 元组
        """
        # 边界情况1: 期望为空
        if not expected:
            return 1.0 if not predicted else 0.0, 1.0

        # 边界情况2: 预测为空
        if not predicted:
            return 0.0, 0.0

        # 提取函数名集合 (简化版本：只比较函数名)
        pred_names = set(call.get("name", "") for call in predicted if isinstance(call, dict))
        exp_names = set(call.get("name", "") for call in expected if isinstance(call, dict))

        # 计算真阳性 (True Positives): 预测对的函数名
        true_positives = len(pred_names & exp_names)

        # 计算精确率和召回率
        precision = true_positives / len(pred_names) if pred_names else 0.0
        recall = true_positives / len(exp_names) if exp_names else 0.0

        return precision, recall

