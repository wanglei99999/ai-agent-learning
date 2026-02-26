"""
BFCL 数据集加载模块

负责加载 Berkeley Function Calling Leaderboard (伯克利函数调用排行榜) 数据集。
BFCL 是评估大语言模型"工具调用/函数调用"能力的权威基准测试。

核心概念:
- 测试数据: 包含用户问题(question)和可用函数定义(function)，是给模型的输入
- Ground Truth: 标准答案，即期望模型输出的正确函数调用
- JSONL格式: 每行一个JSON对象的文件格式，BFCL数据集采用此格式存储

数据目录结构:
  bfcl_eval/data/
    BFCL_v4_simple_python.json      # 测试数据文件
    BFCL_v4_multiple.json            # 测试数据文件
    possible_answer/                  # Ground Truth 目录
      BFCL_v4_simple_python.json     # 对应的标准答案
      BFCL_v4_multiple.json          # 对应的标准答案
"""

from typing import List, Dict, Any, Optional, Union
import json
import os
from pathlib import Path


class BFCLDataset:
    """BFCL 数据集加载器

    支持从BFCL官方数据目录加载数据集，包括测试数据和ground truth(标准答案)。

    数据集类别（BFCL v4），按难度递进:

    --- 基础类别 (Non-Live): 由BFCL团队构造的标准测试集 ---
    - simple_python:      简单Python函数调用 (入门级，单个函数，参数简单)
    - simple_java:        简单Java函数调用
    - simple_javascript:  简单JavaScript函数调用
    - multiple:           多函数调用 (需要从多个候选函数中选择正确的那个)
    - parallel:           并行函数调用 (一个问题需要同时调用多个函数)
    - parallel_multiple:  并行+多函数 (最复杂的组合)
    - irrelevance:        无关检测 (给的函数都不适用，模型应拒绝调用)

    --- Live类别: 来自真实用户贡献的测试数据，更贴近实际场景 ---
    - live_simple:            用户贡献的简单函数调用
    - live_multiple:          用户贡献的多函数调用
    - live_parallel:          用户贡献的并行函数调用
    - live_parallel_multiple: 用户贡献的并行多函数调用
    - live_irrelevance:       用户贡献的无关检测
    - live_relevance:         用户贡献的相关性检测

    --- 多轮对话类别: 测试多轮交互中的函数调用能力 ---
    - multi_turn_base:         多轮对话基础
    - multi_turn_miss_func:    多轮对话中缺失函数 (模型需识别出无法完成)
    - multi_turn_miss_param:   多轮对话中缺失参数 (模型需追问用户)
    - multi_turn_long_context: 多轮对话长上下文

    --- 特殊类别 ---
    - memory:     记忆能力测试
    - web_search: 网络搜索能力测试

    Attributes:
        bfcl_data_dir: BFCL官方数据目录路径
        category: 评估类别
        data: 加载的测试数据列表，每个元素是一个dict，包含question、function、ground_truth等字段
        ground_truth: ground truth字典，key为样本id，value为标准答案列表
    """

    # BFCL v4 数据集的标准类别映射
    # key: 简短类别名(代码中使用)  ->  value: 对应的数据文件名前缀(磁盘上的文件名)
    # 例如 category="simple_python" 会去加载 "BFCL_v4_simple_python.json" 文件
    CATEGORY_MAPPING = {
        "simple_python": "BFCL_v4_simple_python",
        "simple_java": "BFCL_v4_simple_java",
        "simple_javascript": "BFCL_v4_simple_javascript",
        "multiple": "BFCL_v4_multiple",
        "parallel": "BFCL_v4_parallel",
        "parallel_multiple": "BFCL_v4_parallel_multiple",
        "irrelevance": "BFCL_v4_irrelevance",
        "live_simple": "BFCL_v4_live_simple",
        "live_multiple": "BFCL_v4_live_multiple",
        "live_parallel": "BFCL_v4_live_parallel",
        "live_parallel_multiple": "BFCL_v4_live_parallel_multiple",
        "live_irrelevance": "BFCL_v4_live_irrelevance",
        "live_relevance": "BFCL_v4_live_relevance",
        "multi_turn_base": "BFCL_v4_multi_turn_base",
        "multi_turn_miss_func": "BFCL_v4_multi_turn_miss_func",
        "multi_turn_miss_param": "BFCL_v4_multi_turn_miss_param",
        "multi_turn_long_context": "BFCL_v4_multi_turn_long_context",
        "memory": "BFCL_v4_memory",
        "web_search": "BFCL_v4_web_search",
    }

    def __init__(
        self,
        bfcl_data_dir: Union[str, Path] = "./temp_gorilla/berkeley-function-call-leaderboard/bfcl_eval/data",
        category: Optional[str] = None
    ):
        """初始化 BFCL 数据集加载器

        Args:
            bfcl_data_dir: BFCL官方数据目录路径（包含BFCL_v4_*.json文件）
            category: 评估类别，如'simple_python', 'multiple'等
        """
        self.bfcl_data_dir = Path(bfcl_data_dir)  # 数据文件所在目录
        self.category = category                      # 要加载哪个类别的数据
        self.data = []                                 # 存放加载后的测试数据
        self.ground_truth = {}                         # 存放标准答案，格式: {样本id: [正确的函数调用]}

        # 验证数据目录是否存在（需要先克隆BFCL官方仓库才会有这个目录）
        if not self.bfcl_data_dir.exists():
            print(f"   [警告] BFCL数据目录不存在: {self.bfcl_data_dir}")
            print(f"   请确保已克隆BFCL仓库到正确位置")

        # possible_answer 目录存放标准答案(ground truth)
        # 目录结构: bfcl_data_dir/possible_answer/BFCL_v4_xxx.json
        self.answer_dir = self.bfcl_data_dir / "possible_answer"
        if not self.answer_dir.exists():
            print(f"   [警告] Ground truth目录不存在: {self.answer_dir}")

    def load(self) -> List[Dict[str, Any]]:
        """加载数据集（包括测试数据和ground truth）

        Returns:
            数据集列表，每个元素包含问题、函数定义、ground truth等
        """
        if not self.bfcl_data_dir.exists():
            print(f"   [警告] 数据目录不存在，无法加载数据")
            return []

        # 根据category决定加载哪个文件
        # 例如 category="simple_python" -> 加载 BFCL_v4_simple_python.json
        if self.category:
            filename = self.CATEGORY_MAPPING.get(self.category)
            if not filename:
                print(f"   [警告] 未知类别: {self.category}")
                print(f"   支持的类别: {list(self.CATEGORY_MAPPING.keys())}")
                return []
            
            self.data = self._load_category(filename)
        else:
            # 未指定类别时，默认加载 simple_python 作为示例
            print(f"   [提示] 未指定类别，将加载simple_python作为示例")
            self.data = self._load_category(self.CATEGORY_MAPPING["simple_python"])

        print(f"[完成] BFCL数据集加载完成")
        print(f"   数据目录: {self.bfcl_data_dir}")
        print(f"   类别: {self.category or 'simple_python'}")
        print(f"   样本数: {len(self.data)}")
        print(f"   Ground truth数: {len(self.ground_truth)}")

        return self.data
    
    def _load_category(self, filename: str) -> List[Dict[str, Any]]:
        """加载指定类别的数据（包括测试数据和ground truth）

        整体流程:
        1. 从 bfcl_data_dir/ 加载测试数据 (包含question和function定义)
        2. 从 bfcl_data_dir/possible_answer/ 加载标准答案
        3. 将标准答案合并到测试数据中，方便后续评估时直接取用

        Args:
            filename: 文件名（不含.json后缀），如'BFCL_v4_simple_python'

        Returns:
            测试数据列表，每个元素已包含ground_truth字段
        """
        # === 第一步: 加载测试数据 ===
        # 测试数据文件路径，如: bfcl_data_dir/BFCL_v4_simple_python.json
        # 每行格式: {"id": "xxx", "question": "用户问题", "function": [函数定义列表]}
        test_file = self.bfcl_data_dir / f"{filename}.json"
        if not test_file.exists():
            print(f"   [警告] 测试数据文件不存在: {test_file}")
            return []

        test_data = self._load_jsonl_file(test_file)
        print(f"   加载测试数据: {test_file.name} ({len(test_data)} 样本)")

        # === 第二步: 加载ground truth(标准答案) ===
        # 标准答案文件路径，如: bfcl_data_dir/possible_answer/BFCL_v4_simple_python.json
        # 每行格式: {"id": "xxx", "ground_truth": [{"func_name": {"param": [可接受的值列表]}}]}
        gt_file = self.answer_dir / f"{filename}.json"
        if gt_file.exists():
            gt_data = self._load_jsonl_file(gt_file)
            # 构建 ground_truth 字典: {样本id -> 标准答案列表}
            # 构建后的结构示例:
            # self.ground_truth = {
            #     "simple_python_0": [
            #         {"calculate_triangle_area": {"base": [10, 10.0], "height": [5, 5.0], "unit": ["units", ""]}}
            #     ],
            #     "simple_python_1": [
            #         {"get_weather": {"city": ["Beijing"], "unit": ["celsius", "c"]}}
            #     ],
            # }
            # 其中参数值是列表，表示多个可接受的答案（如 10 和 10.0 都算对）
            for item in gt_data:
                item_id = item.get("id")
                if item_id:
                    self.ground_truth[item_id] = item.get("ground_truth", [])
            print(f"   加载ground truth: {gt_file.name} ({len(gt_data)} 样本)")
        else:
            print(f"   [警告] Ground truth文件不存在: {gt_file}")

        # === 第三步: 合并 ===
        # 将标准答案直接挂到对应的测试数据上，这样每个样本就同时包含输入和期望输出
        # 合并后的样本结构: {"id": ..., "question": ..., "function": [...], "ground_truth": [...]}
        for item in test_data:
            item_id = item.get("id")
            if item_id and item_id in self.ground_truth:
                item["ground_truth"] = self.ground_truth[item_id]

        return test_data

    def _load_jsonl_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """加载JSONL文件（每行一个JSON对象）

        JSONL (JSON Lines) 格式说明:
        - 文件中每一行是一个独立的JSON对象
        - 不同于普通JSON文件（整个文件是一个JSON），JSONL适合存储大量记录

        磁盘上的文件内容 (每行一个JSON):
            {"id": "simple_0", "question": "计算面积", "function": [...]}
            {"id": "simple_1", "question": "查询天气", "function": [...]}

        解析后的Python对象 (List[Dict]):
            [
                {"id": "simple_0", "question": "计算面积", "function": [...]},
                {"id": "simple_1", "question": "查询天气", "function": [...]},
            ]

        其中每个dict的典型字段:
        - "id":       样本唯一标识，如 "simple_python_0"
        - "question": 用户问题，如 "Calculate the area of a triangle with base 10"
        - "function": 可用函数定义列表，每个函数包含 name, description, parameters

        本方法只做格式转换(文本->Python对象)，ground_truth的合并在 _load_category 中完成。

        Args:
            file_path: JSONL文件路径

        Returns:
            解析后的字典列表
        """
        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:  # 跳过空行
                    try:
                        item = json.loads(line)  # 逐行解析JSON
                        data.append(item)
                    except json.JSONDecodeError as e:
                        print(f"   [警告] JSON解析失败: {e}")
                        continue
        return data

    def get_ground_truth(self, sample_id: str) -> List[Dict[str, Any]]:
        """获取指定样本的ground truth

        Args:
            sample_id: 样本ID，如 "simple_python_0"

        Returns:
            Ground truth列表，示例:
            [
                {
                    "calculate_triangle_area": {
                        "base": [10, 10.0],       # 可接受的值列表
                        "height": [5, 5.0],
                        "unit": ["units", ""]
                    }
                }
            ]
            如果样本ID不存在则返回空列表 []
        """
        return self.ground_truth.get(sample_id, [])

    def get_sample(self, index: int) -> Dict[str, Any]:
        """获取单个样本

        Args:
            index: 样本索引 (从0开始)

        Returns:
            样本数据字典，完整结构示例:
            {
                "id": "simple_python_0",
                "question": "Calculate the area of a triangle with base 10 and height 5.",
                "function": [
                    {
                        "name": "calculate_triangle_area",
                        "description": "Calculate the area of a triangle",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "base": {"type": "number"},
                                "height": {"type": "number"},
                                "unit": {"type": "string"}
                            },
                            "required": ["base", "height"]
                        }
                    }
                ],
                "ground_truth": [
                    {"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units"]}}
                ]
            }
            如果索引越界则返回空字典 {}
        """
        if not self.data:  # 懒加载: 如果还没加载数据，先自动加载
            self.load()
        return self.data[index] if index < len(self.data) else {}

    def get_available_categories(self) -> List[str]:
        """获取所有可用的类别

        Returns:
            类别列表
        """
        return list(self.CATEGORY_MAPPING.keys())

    def __len__(self) -> int:
        """返回数据集大小
        
        实现 len() 协议，使得可以用 len(dataset) 获取样本数量
        """
        if not self.data:  # 懒加载
            self.load()
        return len(self.data)

    def __iter__(self):
        """迭代器
        
        实现迭代协议，使得可以用 for sample in dataset: 遍历所有样本
        """
        if not self.data:  # 懒加载
            self.load()
        return iter(self.data)

