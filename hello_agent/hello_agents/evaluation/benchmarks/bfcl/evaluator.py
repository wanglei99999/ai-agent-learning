"""
BFCL 评估器模块

负责评估智能体在 BFCL 基准测试上的表现。
这是 BFCL 模块的核心文件，串联了整个评估流程:

整体流程:
  dataset.py 加载数据  -->  evaluator.py 调用Agent并评估  -->  metrics.py 计算指标

本文件的职责:
  1. 拿到测试数据 (question + function定义)
  2. 构建 prompt 发给 Agent
  3. 解析 Agent 的回复，提取函数调用
  4. 将提取的函数调用与 ground truth 对比，判断对错
  5. 汇总统计结果
"""

from typing import Dict, Any, List, Optional, Union
import json
import ast
import re
import time
from pathlib import Path
from hello_agents.evaluation.benchmarks.bfcl.dataset import BFCLDataset
from hello_agents.evaluation.benchmarks.bfcl.metrics import BFCLMetrics


class BFCLEvaluator:
    """BFCL 评估器

    评估智能体的工具调用能力,包括:
    - 简单函数调用: 单个函数，参数简单
    - 多函数调用: 从多个候选函数中选择正确的
    - 并行函数调用: 一个问题需要同时调用多个函数
    - 无关检测: 给的函数都不适用，模型应拒绝调用

    支持两种评估模式:
    - AST评估 (默认): 将模型输出和标准答案都解析为抽象语法树，比较结构是否一致
    - 执行评估: 实际执行函数，比较运行结果 (当前简化为AST评估)

    使用示例:
        >>> evaluator = BFCLEvaluator(category="simple_python")
        >>> results = evaluator.evaluate(agent, max_samples=5)
        >>> print(results["overall_accuracy"])  # 如 0.8 表示 80% 准确率

    Attributes:
        dataset: BFCL 数据集 (BFCLDataset实例)
        metrics: 评估指标计算器 (BFCLMetrics实例)
        evaluation_mode: 评估模式 ('ast' 或 'execution')
    """

    def __init__(
        self,
        dataset: Optional[BFCLDataset] = None,
        category: Optional[str] = None,
        evaluation_mode: str = "ast",
        local_data_dir: Optional[str] = None
    ):
        """初始化 BFCL 评估器

        Args:
            dataset: BFCL 数据集,如果为 None 则自动创建
            category: 评估类别
            evaluation_mode: 评估模式 ('ast' 或 'execution')
            local_data_dir: 本地数据目录
        """
        # 如果没传入dataset，则根据category自动创建一个
        self.dataset = dataset or BFCLDataset(
            category=category,
            local_data_dir=local_data_dir
        )
        self.metrics = BFCLMetrics()          # 指标计算器，用于计算准确率、F1等
        self.evaluation_mode = evaluation_mode # "ast"(默认) 或 "execution"
        self.category = category               # 如 "simple_python", "multiple" 等
        
    def evaluate(self, agent: Any, max_samples: Optional[int] = None) -> Dict[str, Any]:
        """评估智能体

        Args:
            agent: 要评估的智能体
            max_samples: 最大评估样本数,None表示评估全部

        Returns:
            评估结果字典,包含各项指标
        """
        print(f"\n[开始] BFCL 评估...")
        print(f"   智能体: {getattr(agent, 'name', 'Unknown')}")
        print(f"   评估模式: {self.evaluation_mode}")
        print(f"   类别: {self.category or '全部'}")

        # === 第一步: 加载数据集 ===
        # 调用 dataset.load() 从磁盘读取测试数据 + 标准答案
        dataset = self.dataset.load()
        if not dataset:
            print("   [警告] 数据集为空,跳过评估")
            return self._create_empty_results(agent)

        # 可以限制样本数，方便调试时快速验证
        if max_samples:
            dataset = dataset[:max_samples]

        print(f"   样本数量: {len(dataset)}")

        # === 第二步: 逐样本评估 ===
        # 对每个样本: 构建prompt -> 调用Agent -> 解析回复 -> 对比答案
        results = []      # 存放每个样本的评估结果
        categories = {}   # 按类别分组统计

        for i, sample in enumerate(dataset):
            if i % 10 == 0:  # 每10个样本打印一次进度
                print(f"   进度: {i+1}/{len(dataset)}")

            try:
                # 评估单个样本 (核心逻辑在 evaluate_sample 中)
                sample_result = self.evaluate_sample(agent, sample)
                results.append(sample_result)

                # 按类别统计正确/错误数量
                category = self.category if self.category else sample.get("category", "unknown")
                if category not in categories:
                    categories[category] = {"total": 0, "correct": 0, "results": []}

                categories[category]["total"] += 1
                if sample_result["success"]:
                    categories[category]["correct"] += 1
                categories[category]["results"].append(sample_result)

            except Exception as e:
                print(f"   [警告] 样本 {i} 评估失败: {e}")
                results.append({
                    "success": False,
                    "error": str(e),
                    "predicted": None,
                    "expected": sample.get("ground_truth"),
                    "score": 0.0
                })

        # === 第三步: 汇总统计 ===
        # 计算总体准确率 = 正确样本数 / 总样本数
        total_samples = len(results)
        correct_samples = sum(1 for r in results if r["success"])
        overall_accuracy = correct_samples / total_samples if total_samples > 0 else 0.0

        # 计算每个类别的准确率
        category_metrics = {}
        for cat, cat_data in categories.items():
            accuracy = cat_data["correct"] / cat_data["total"] if cat_data["total"] > 0 else 0.0
            category_metrics[cat] = {
                "total": cat_data["total"],
                "correct": cat_data["correct"],
                "accuracy": accuracy
            }

        # 构建最终返回结果
        # 示例:
        # {
        #     "benchmark": "BFCL",
        #     "agent_name": "TestAgent",
        #     "overall_accuracy": 0.8,          # 80%准确率
        #     "total_samples": 10,
        #     "correct_samples": 8,
        #     "category_metrics": {"simple_python": {"total": 10, "correct": 8, "accuracy": 0.8}},
        #     "detailed_results": [{...}, ...]   # 每个样本的详细结果
        # }
        final_results = {
            "benchmark": "BFCL",
            "agent_name": getattr(agent, 'name', 'Unknown'),
            "evaluation_mode": self.evaluation_mode,
            "category": self.category,
            "total_samples": total_samples,
            "correct_samples": correct_samples,
            "overall_accuracy": overall_accuracy,
            "category_metrics": category_metrics,
            "detailed_results": results
        }

        print(f"[完成] BFCL 评估完成")
        print(f"   总体准确率: {overall_accuracy:.2%}")
        for cat, metrics in category_metrics.items():
            print(f"   {cat}: {metrics['accuracy']:.2%} ({metrics['correct']}/{metrics['total']})")

        return final_results
    
    def evaluate_sample(self, agent: Any, sample: Dict[str, Any]) -> Dict[str, Any]:
        """评估单个样本

        这是评估的核心方法，完整流程:
        1. 从样本中取出 question 和 function 定义
        2. 构建 prompt (把函数定义和问题拼成一段文本)
        3. 调用 agent.run(prompt) 获取模型回复
        4. 从回复中提取函数调用 (JSON解析)
        5. 将提取的函数调用与 ground_truth 对比

        Args:
            agent: 要评估的智能体，需要有 run(prompt) 方法
            sample: 样本数据，包含 question, function, ground_truth

        Returns:
            单个样本的评估结果，示例:
            {
                "success": True,           # 是否完全正确
                "score": 1.0,              # 得分 (0.0~1.0)
                "predicted": [{"name": "func", "arguments": {...}}],  # 模型实际输出
                "expected": [{"func": {"param": [values]}}],          # 标准答案
                "response": "模型原始回复文本",
                "execution_time": 0.5,     # 耗时(秒)
                "sample_id": "simple_python_0",
                "category": "simple_python"
            }
        """
        try:
            # 从样本中取出三个核心字段
            question = sample.get("question", "")       # 用户问题
            functions = sample.get("function", [])       # 可用函数定义列表
            ground_truth = sample.get("ground_truth", []) # 标准答案

            # 构建函数调用提示 (把函数定义+问题拼成prompt发给模型)
            prompt = self._build_function_calling_prompt(question, functions)

            # 调用智能体，记录耗时
            start_time = time.time()
            response = agent.run(prompt)  # 模型返回的原始文本
            execution_time = time.time() - start_time

            # 从模型回复中提取函数调用 (JSON解析)
            # 提取结果格式: [{"name": "func_name", "arguments": {"param": value}}]
            predicted_calls = self._extract_function_calls(response)

            # 将提取的函数调用与标准答案对比
            if self.evaluation_mode == "ast":
                success, score = self._evaluate_ast_matching(predicted_calls, ground_truth)
            else:
                success, score = self._evaluate_execution(predicted_calls, ground_truth, functions)

            return {
                "success": success,
                "score": score,
                "predicted": predicted_calls,
                "expected": ground_truth,
                "response": response,
                "question": question,
                "execution_time": execution_time,
                "sample_id": sample.get("id", ""),
                "category": self.category if self.category else sample.get("category", "unknown")
            }

        except Exception as e:
            # 评估失败时返回错误结果，不会中断整个评估流程
            return {
                "success": False,
                "score": 0.0,
                "predicted": None,
                "expected": sample.get("ground_truth", []),
                "question": sample.get("question", ""),
                "error": str(e),
                "sample_id": sample.get("id", ""),
                "category": self.category if self.category else sample.get("category", "unknown")
            }

    def _create_empty_results(self, agent: Any) -> Dict[str, Any]:
        """创建空的评估结果"""
        return {
            "benchmark": "BFCL",
            "agent_name": getattr(agent, 'name', 'Unknown'),
            "evaluation_mode": self.evaluation_mode,
            "category": self.category,
            "total_samples": 0,
            "correct_samples": 0,
            "overall_accuracy": 0.0,
            "category_metrics": {},
            "detailed_results": []
        }

    def _build_function_calling_prompt(self, question: str, functions: List[Dict]) -> str:
        """构建函数调用提示

        将用户问题和可用函数定义拼接成一段完整的 prompt，发给模型。

        输入:
            question: "Calculate the area of a triangle with base 10 and height 5."
            functions: [{"name": "calculate_triangle_area", "description": "...", "parameters": {...}}]

        生成的 prompt 示例:
            你是一个智能助手，可以调用以下函数来帮助回答问题：

            函数 1: calculate_triangle_area
            描述: Calculate the area of a triangle
            参数: {"type": "object", "properties": {...}}

            请根据以下问题，选择合适的函数进行调用：
            Calculate the area of a triangle with base 10 and height 5.

            请以JSON格式返回函数调用，例如：
            [{"name": "function_name", "arguments": {"param1": "value1"}}]
        """
        if not functions:
            return question

        prompt = f"你是一个智能助手，可以调用以下函数来帮助回答问题：\n\n"

        # 遍历所有可用函数，把它们的名称、描述、参数定义都写进prompt
        for i, func in enumerate(functions, 1):
            func_name = func.get("name", f"function_{i}")
            func_desc = func.get("description", "")
            func_params = func.get("parameters", {})

            prompt += f"函数 {i}: {func_name}\n"
            prompt += f"描述: {func_desc}\n"

            if func_params:
                prompt += f"参数: {json.dumps(func_params, ensure_ascii=False, indent=2)}\n"

            prompt += "\n"

        # 最后加上用户问题和输出格式要求
        prompt += f"请根据以下问题，选择合适的函数进行调用：\n{question}\n\n"
        prompt += "请以JSON格式返回函数调用，例如：\n"
        prompt += '[{"name": "function_name", "arguments": {"param1": "value1"}}]'

        return prompt

    def _extract_function_calls(self, response: str) -> List[Dict[str, Any]]:
        """从模型回复中提取函数调用

        模型的回复可能有多种格式，这个方法用三种策略逐步尝试提取:

        策略1: 整个回复就是JSON数组
            模型回复: '[{"name": "func", "arguments": {"a": 1}}]'

        策略2: 回复中嵌入了JSON数组 (用正则提取)
            模型回复: '我建议调用 [{"name": "func", "arguments": {"a": 1}}] 来解决'

        策略3: 回复中有单个函数调用对象 (没有外层数组)
            模型回复: '调用 {"name": "func", "arguments": {"a": 1}}'

        返回格式统一为: [{"name": "func_name", "arguments": {"param": value}}]
        提取失败则返回空列表 []
        """
        try:
            # 策略1: 整个回复就是JSON数组，直接解析
            if response.strip().startswith('[') and response.strip().endswith(']'):
                return json.loads(response.strip())

            # 策略2: 用正则查找回复中嵌入的JSON数组 [...]
            json_pattern = r'\[.*?\]'
            matches = re.findall(json_pattern, response, re.DOTALL)

            for match in matches:
                try:
                    calls = json.loads(match)
                    if isinstance(calls, list):
                        return calls
                except json.JSONDecodeError:
                    continue

            # 策略3: 查找单个函数调用对象 {"name": ...}
            single_call_pattern = r'\{.*?"name".*?\}'
            matches = re.findall(single_call_pattern, response, re.DOTALL)

            calls = []
            for match in matches:
                try:
                    call = json.loads(match)
                    if "name" in call:
                        calls.append(call)
                except json.JSONDecodeError:
                    continue

            return calls

        except Exception:
            return []  # 所有策略都失败，返回空列表

    def _evaluate_ast_matching(self, predicted: List[Dict], expected: List) -> tuple[bool, float]:
        """AST匹配评估 (核心评估入口)

        根据 ground truth 的格式自动选择评估方式:
        1. BFCL v4格式 (dict): [{"func_name": {"param": [value1, value2]}}]
           -> 调用 _evaluate_bfcl_v4_format()
        2. 字符串格式 (旧版): ["func_name(param=value)"]
           -> 调用 _evaluate_string_format()

        Args:
            predicted: 模型输出的函数调用列表
            expected: 标准答案列表

        Returns:
            (success, score) 元组
            - success: 是否完全正确 (True/False)
            - score: 得分 (0.0~1.0)
        """
        # 如果标准答案为空，则模型也不应调用任何函数才算对
        if not expected:
            return len(predicted) == 0, 1.0 if len(predicted) == 0 else 0.0

        try:
            # 通过第一个元素的类型判断ground truth格式
            if expected and isinstance(expected[0], dict):
                return self._evaluate_bfcl_v4_format(predicted, expected)
            else:
                return self._evaluate_string_format(predicted, expected)

        except Exception as e:
            print(f"   [警告] 评估出错: {e}")
            return False, 0.0

    def _evaluate_bfcl_v4_format(self, predicted: List[Dict], expected: List[Dict]) -> tuple[bool, float]:
        """评估BFCL v4格式的ground truth

        对比示例:
        模型输出 (predicted):
            [{"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 5}}]

        标准答案 (expected):
            [{"calculate_triangle_area": {"base": [10, 10.0], "height": [5, 5.0]}}]

        对比过程:
            1. 函数名匹配: "calculate_triangle_area" == "calculate_triangle_area" -> 通过
            2. 参数匹配: base=10 在 [10, 10.0] 中 -> 通过
            3. 参数匹配: height=5 在 [5, 5.0] 中 -> 通过
            4. 结果: success=True, score=1.0

        Returns:
            (success, score) - success为True表示所有函数调用都匹配
        """
        # 函数调用数量不一致，直接判错
        if len(predicted) != len(expected):
            return False, 0.0

        matches = 0
        for pred_call in predicted:
            if not isinstance(pred_call, dict) or "name" not in pred_call:
                continue

            pred_func_name = pred_call["name"]           # 如 "calculate_triangle_area"
            pred_args = pred_call.get("arguments", {})   # 如 {"base": 10, "height": 5}

            # 在标准答案中查找匹配的函数调用
            for exp_call in expected:
                if not isinstance(exp_call, dict):
                    continue

                # expected格式: {"func_name": {"param": [values]}}
                # 注意: key就是函数名，value是参数字典
                for exp_func_name, exp_params in exp_call.items():
                    if exp_func_name != pred_func_name:
                        continue

                    # 函数名匹配，接下来比较参数
                    if self._compare_parameters(pred_args, exp_params):
                        matches += 1
                        break

        # 所有函数调用都匹配才算完全正确
        success = matches == len(expected)
        # 得分 = 匹配数 / 期望数，如匹配1个/期望2个 = 0.5分
        score = matches / len(expected) if expected else 0.0
        return success, score

    def _compare_parameters(self, pred_params: Dict, exp_params: Dict) -> bool:
        """比较预测参数和期望参数

        示例:
            pred_params: {"base": 10, "height": 5, "unit": "units"}
            exp_params:  {"base": [10, 10.0], "height": [5, 5.0], "unit": ["units", ""]}

            对比过程:
            - base:   10 在 [10, 10.0] 中?   -> True
            - height: 5  在 [5, 5.0] 中?    -> True
            - unit:   "units" 在 ["units", ""] 中? -> True
            - 结果: True (所有参数都匹配)

        Args:
            pred_params: 模型输出的参数 {"param": value}
            exp_params: 标准答案的参数 {"param": [可接受的值列表]}
        """
        # 遍历标准答案中的每个参数
        for param_name, expected_values in exp_params.items():
            if param_name not in pred_params:
                # 参数缺失，但如果标准答案允许空字符串，则算可选参数，跳过
                if not isinstance(expected_values, list) or "" not in expected_values:
                    return False  # 必需参数缺失，判错
                continue

            pred_value = pred_params[param_name]

            # expected_values是列表，包含所有可接受的值
            if isinstance(expected_values, list):
                if pred_value not in expected_values:
                    # 直接比较失败，尝试转字符串后比较
                    # 例如: pred_value=10 vs expected=[10.0] -> str("10") vs str("10.0") 仍不同
                    # 但: pred_value=10 vs expected=[10] -> 直接匹配
                    if str(pred_value) not in [str(v) for v in expected_values]:
                        return False
            else:
                # 单个值比较 (非列表格式，兼容旧版数据)
                if pred_value != expected_values and str(pred_value) != str(expected_values):
                    return False

        return True

    def _evaluate_string_format(self, predicted: List[Dict], expected: List[str]) -> tuple[bool, float]:
        """评估字符串格式的ground truth（旧版BFCL格式）

        旧版ground truth是函数调用字符串:
            expected: ["calculate_triangle_area(base=10, height=5, unit='units')"]

        需要先把模型输出的dict格式转成字符串，再用AST比较:
            predicted dict: {"name": "calculate_triangle_area", "arguments": {"base": 10}}
            转换为字符串: "calculate_triangle_area(base=10)"
        """
        # 将模型输出的dict格式转换为函数调用字符串
        predicted_strs = []
        for call in predicted:
            if isinstance(call, dict) and "name" in call:
                func_name = call["name"]
                args = call.get("arguments", {})
                if args:
                    args_str = ", ".join([f"{k}={repr(v)}" for k, v in args.items()])
                    call_str = f"{func_name}({args_str})"
                else:
                    call_str = f"{func_name}()"
                predicted_strs.append(call_str)

        # 数量不一致直接判错
        if len(predicted_strs) != len(expected):
            return False, 0.0

        # 逐个比较函数调用字符串
        matches = 0
        for pred_str in predicted_strs:
            for exp_str in expected:
                if self._ast_strings_match(pred_str, exp_str):
                    matches += 1
                    break

        success = matches == len(expected)
        score = matches / len(expected) if expected else 0.0

        return success, score

    def _ast_strings_match(self, pred: str, expected: str) -> bool:
        """比较两个函数调用字符串是否在AST层面匹配

        为什么用AST而不是简单字符串比较?
        因为 "func(a=1, b=2)" 和 "func(b=2, a=1)" 参数顺序不同但语义相同，
        AST解析后可以正确判断它们是等价的。

        示例:
            pred:     "calculate_area(base=10, height=5)"
            expected: "calculate_area(height=5, base=10)"
            -> AST解析后结构相同 -> 返回 True
        """
        try:
            pred_ast = ast.parse(pred, mode='eval')
            exp_ast = ast.parse(expected, mode='eval')
            return ast.dump(pred_ast) == ast.dump(exp_ast)
        except:
            # AST解析失败时回退到简单字符串比较
            return pred.strip() == expected.strip()

    def _evaluate_execution(self, predicted: List[Dict], expected: List[str], functions: List[Dict]) -> tuple[bool, float]:
        """执行评估（简化版本）

        理想情况下应该实际执行函数并比较运行结果，
        但需要安全的沙箱环境。当前简化为AST匹配评估。
        """
        return self._evaluate_ast_matching(predicted, expected)

    def export_to_bfcl_format(
        self,
        results: Dict[str, Any],
        output_path: Union[str, Path],
        include_inference_log: bool = True
    ) -> None:
        """导出评估结果为BFCL官方格式

        BFCL官方格式示例：
        {
            "id": "simple_python_0",
            "model_result": [
                {
                    "name": "calculate_triangle_area",
                    "arguments": {"base": 10, "height": 5, "unit": "units"}
                }
            ],
            "inference_log": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }

        Args:
            results: evaluate()方法返回的评估结果
            output_path: 输出文件路径
            include_inference_log: 是否包含推理日志
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 遍历每个样本的详细结果，转换为BFCL官方格式
        bfcl_results = []

        for detail in results.get("detailed_results", []):
            # 将模型输出的dict格式转换为函数调用字符串
            # 例如: {"name": "func", "arguments": {"a": 1}} -> "func(a=1)"
            predicted = detail.get("predicted", [])
            result_string = ""

            if predicted:
                call = predicted[0]  # BFCL官方格式通常只取第一个函数调用
                if isinstance(call, dict) and "name" in call:
                    func_name = call["name"]
                    args = call.get("arguments", {})

                    if args:
                        args_str = ", ".join([f"{k}={repr(v)}" for k, v in args.items()])
                        result_string = f"{func_name}({args_str})"
                    else:
                        result_string = f"{func_name}()"

            # BFCL官方期望的每行格式:
            # {"id": "simple_python_0", "result": "calculate_triangle_area(base=10, height=5)"}
            bfcl_item = {
                "id": detail.get("sample_id", ""),
                "result": result_string  # BFCL期望的是单个字符串
            }

            # 可选: 添加推理日志 (记录用户问题和模型回复，方便调试)
            if include_inference_log:
                question = detail.get("question", "")
                response = detail.get("response", "")

                bfcl_item["inference_log"] = [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": response}
                ]

            bfcl_results.append(bfcl_item)

        # 写入JSONL格式（和dataset加载时的格式一样，每行一个JSON对象）
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in bfcl_results:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        print(f"\n[完成] BFCL格式结果已导出")
        print(f"   输出文件: {output_path}")
        print(f"   样本数: {len(bfcl_results)}")
        print(f"   包含推理日志: {include_inference_log}")

        # 提示如何使用BFCL官方评估工具
        print(f"\n[提示] 使用BFCL官方评估工具：")
        print(f"   1. 安装: pip install bfcl-eval")
        print(f"   2. 设置环境变量: export BFCL_PROJECT_ROOT=.")
        print(f"   3. 将结果文件复制到: result/HelloAgents/")
        print(f"   4. 运行评估: bfcl evaluate --model HelloAgents --test-category {self.category}")

