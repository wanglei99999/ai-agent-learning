"""
AIME Dataset Loader

学习笔记：模块作用
本模块负责加载 AIME 风格的数学题目数据，用于评估 AI 生成题目的质量。

AIME 是什么？
- American Invitational Mathematics Examination（美国数学邀请赛）
- 高中数学竞赛，难度介于 AMC 和 USAMO 之间
- 15 道题，3 小时，答案为 0-999 的整数
- 典型难度：能做对 6-9 题算优秀

为什么用 AIME？
- 题目质量高：经过专业数学家设计
- 难度适中：有挑战性但不至于太难
- 数据可用：有公开的历年真题
- 业界标准：广泛认可的数学题目质量基准

支持的功能：
1. 加载生成数据：AI 生成的题目（待评估）
2. 加载真题数据：AIME 历年真题（评估标准）
3. 数据格式统一：将不同来源的数据转换为统一格式
4. 数据筛选：按主题、难度筛选题目

使用场景：
- 评估 AI 生成的数学题目质量
- 对比生成题目与真题的差距
- 为生成模型提供训练/测试数据
"""

import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from huggingface_hub import snapshot_download


class AIDataset:
    """AIME 数据集加载器
    
    【学习笔记】核心功能
    这个类负责加载和管理 AIME 风格的数学题目数据。
    
    支持两种数据类型：
    1. generated（生成数据）：
       - AI 生成的题目
       - 从本地 JSON 文件加载
       - 用于评估生成质量
    
    2. real（真题数据）：
       - AIME 历年真题
       - 从 HuggingFace 下载
       - 用作评估标准（黄金标准）
    
    数据格式（统一后）：
        {
            "problem_id": "题目ID",
            "problem": "问题描述",
            "answer": "答案",
            "solution": "解答过程",
            "difficulty": "难度",
            "topic": "主题"
        }
    
    使用示例：
        # 加载生成数据
        dataset = AIDataset(
            dataset_type="generated",
            data_path="my_generated_problems.json"
        )
        problems = dataset.load()
        
        # 加载 AIME 2025 真题
        dataset = AIDataset(
            dataset_type="real",
            year=2025
        )
        aime_problems = dataset.load()
        
        # 筛选数据
        geometry_problems = dataset.get_problems_by_topic("geometry")
        hard_problems = dataset.get_problems_by_difficulty(7, 9)
    """
    
    def __init__(
        self,
        dataset_type: str = "generated",  # "generated" or "real"
        data_path: Optional[str] = None,
        year: Optional[int] = None,  # 用于真题数据，如2024, 2025
        cache_dir: Optional[str] = None
    ):
        """初始化 AIME 数据集
        
        【学习笔记】初始化参数
        根据不同的使用场景选择不同的参数组合。
        
        参数说明：
        1. dataset_type: 数据集类型
           - "generated": 加载 AI 生成的题目
             → 需要提供 data_path
             → 用于评估生成质量
           
           - "real": 加载 AIME 真题
             → 需要提供 year
             → 用作评估标准
        
        2. data_path: 本地数据文件路径
           - 仅用于 dataset_type="generated"
           - JSON 格式文件
           - 包含生成的题目列表
        
        3. year: AIME 年份
           - 仅用于 dataset_type="real"
           - 如 2024, 2025
           - 从 HuggingFace 下载对应年份的真题
        
        4. cache_dir: 缓存目录
           - 用于存储从 HuggingFace 下载的数据
           - 默认: ~/.cache/hello_agents/aime
           - 避免重复下载
        
        使用示例：
            # 场景1: 加载生成数据
            dataset = AIDataset(
                dataset_type="generated",
                data_path="./generated_problems.json"
            )
            
            # 场景2: 加载 AIME 2025 真题
            dataset = AIDataset(
                dataset_type="real",
                year=2025
            )
            
            # 场景3: 自定义缓存目录
            dataset = AIDataset(
                dataset_type="real",
                year=2025,
                cache_dir="./my_cache"
            )
        
        Args:
            dataset_type: 数据集类型，"generated"（生成的）或"real"（真题）
            data_path: 本地数据路径（用于 generated 类型）
            year: AIME 年份（用于 real 类型），如 2024, 2025
            cache_dir: 缓存目录
        """
        # 保存配置参数
        self.dataset_type = dataset_type
        self.data_path = data_path
        self.year = year
        self.cache_dir = cache_dir or os.path.expanduser("~/.cache/hello_agents/aime")
        
        # 初始化题目列表（调用 load() 后填充）
        self.problems: List[Dict[str, Any]] = []
        
    def load(self) -> List[Dict[str, Any]]:
        """加载数据集
        
        【学习笔记】数据加载流程
        根据 dataset_type 选择不同的加载方法。
        
        加载流程：
        1. generated 类型：
           → 调用 _load_generated_data()
           → 从本地 JSON 文件读取
           → 统一数据格式
        
        2. real 类型：
           → 调用 _load_real_data()
           → 从 HuggingFace 下载
           → 解析 JSONL 格式
           → 统一数据格式
        
        返回的数据格式（统一后）：
            [
                {
                    "problem_id": "题目ID",
                    "problem": "问题描述",
                    "answer": "答案（0-999的整数）",
                    "solution": "解答过程（可选）",
                    "difficulty": "难度（可选，1-15）",
                    "topic": "主题（可选，如 geometry, algebra）"
                },
                ...
            ]
        
        使用示例：
            dataset = AIDataset(dataset_type="generated", data_path="data.json")
            problems = dataset.load()
            
            print(f"加载了 {len(problems)} 个题目")
            for p in problems:
                print(f"ID: {p['problem_id']}")
                print(f"问题: {p['problem']}")
                print(f"答案: {p['answer']}")
        
        Returns:
            问题列表，每个问题是一个字典
        
        Raises:
            ValueError: 如果 dataset_type 不是 "generated" 或 "real"
        """
        # 根据数据集类型选择加载方法
        if self.dataset_type == "generated":
            return self._load_generated_data()
        elif self.dataset_type == "real":
            return self._load_real_data()
        else:
            raise ValueError(f"Unknown dataset_type: {self.dataset_type}")
    
    def _load_generated_data(self) -> List[Dict[str, Any]]:
        """加载生成的数据
        
        【学习笔记】生成数据加载
        从本地 JSON 文件加载 AI 生成的题目。
        
        加载步骤：
        1. 检查 data_path 是否提供
        2. 检查文件是否存在
        3. 读取 JSON 文件
        4. 统一数据格式（兼容不同字段名）
        5. 返回标准化的题目列表
        
        字段映射（兼容性处理）：
        - problem_id: id → problem_id（如果没有则生成 gen_0, gen_1...）
        - problem: problem 或 question → problem
        - answer: answer → answer
        - solution: solution 或 reasoning → solution
        - difficulty: difficulty → difficulty
        - topic: topic 或 category → topic
        
        为什么需要字段映射？
        - 不同的生成模型可能使用不同的字段名
        - 统一格式方便后续处理
        - 提高代码的兼容性
        
        示例输入文件（generated_problems.json）：
            [
                {
                    "id": "gen_001",
                    "question": "求解方程...",
                    "answer": "42",
                    "reasoning": "首先...",
                    "category": "algebra"
                },
                ...
            ]
        
        Returns:
            标准化的题目列表
        
        Raises:
            ValueError: 如果未提供 data_path
            FileNotFoundError: 如果文件不存在
        """
        # 检查参数
        if not self.data_path:
            raise ValueError("data_path is required for generated dataset")
        
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        print(f" 加载生成数据: {self.data_path}")
        
        # 读取 JSON 文件
        with open(self.data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 统一数据格式（兼容不同字段名）
        problems = []
        for idx, item in enumerate(data):
            problem = {
                # ID: 优先使用 id 字段，否则生成 gen_0, gen_1...
                "problem_id": item.get("id", f"gen_{idx}"),
                
                # 问题: 兼容 problem 和 question
                "problem": item.get("problem", item.get("question", "")),
                
                # 答案
                "answer": item.get("answer", ""),
                
                # 解答: 兼容 solution 和 reasoning
                "solution": item.get("solution", item.get("reasoning", "")),
                
                # 难度（可选）
                "difficulty": item.get("difficulty", None),
                
                # 主题: 兼容 topic 和 category
                "topic": item.get("topic", item.get("category", None))
            }
            problems.append(problem)
        
        # 保存到实例变量
        self.problems = problems
        print(f" 加载了 {len(problems)} 个生成题目")
        return problems
    
    def _load_real_data(self) -> List[Dict[str, Any]]:
        """从 HuggingFace 加载 AIME 真题数据
        
        【学习笔记】真题数据加载
        从 HuggingFace 下载 AIME 历年真题，用作评估标准。
        
        加载步骤：
        1. 检查 year 参数是否提供
        2. 使用 snapshot_download 从 HuggingFace 下载数据集
        3. 查找 JSONL 数据文件
        4. 逐行读取 JSONL 文件
        5. 统一数据格式
        6. 返回标准化的题目列表
        
        HuggingFace 数据集：
        - 数据集 ID: math-ai/aime25
        - 格式: JSONL (JSON Lines)
        - 内容: AIME 2025 真题
        
        JSONL 格式说明：
        - 每行一个 JSON 对象
        - 不是一个 JSON 数组
        - 适合大文件流式读取
        
        为什么使用 snapshot_download？
        - 支持缓存：下载后保存到本地
        - 避免重复下载：下次直接使用缓存
        - 灵活性：支持自定义缓存目录
        
        Returns:
            标准化的题目列表
        
        Raises:
            ValueError: 如果未提供 year
            FileNotFoundError: 如果数据集中没有 JSONL 文件
            Exception: 其他下载或解析错误
        """
        # 检查参数
        if not self.year:
            raise ValueError("year is required for real dataset")

        print(f" 从 HuggingFace 加载 AIME {self.year} 真题...")

        try:
            # 使用AIME 2025数据集
            repo_id = "math-ai/aime25"
            use_datasets_lib = False  # 使用snapshot_download（JSONL格式）

            print(f"   使用数据集: {repo_id}")

            # 步骤1: 使用 snapshot_download 下载数据集
            local_dir = snapshot_download(
                repo_id=repo_id,          # HuggingFace 数据集 ID
                repo_type="dataset",      # 类型为数据集
                cache_dir=self.cache_dir  # 缓存目录
            )

            # 步骤2: 查找 JSONL 数据文件
            data_files = list(Path(local_dir).glob("*.jsonl"))

            if not data_files:
                raise FileNotFoundError(f"No JSONL data file found in {repo_id}")

            data_file = data_files[0]
            print(f"   ✓ 找到数据文件: {data_file.name}")

            # 步骤3: 加载 JSONL 数据（逐行读取）
            data = []
            with open(data_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():  # 跳过空行
                        data.append(json.loads(line))  # 解析每行 JSON
            
            # 步骤4: 统一数据格式（AIME 2025 使用小写字段名）
            problems = []
            for idx, item in enumerate(data):
                problem = {
                    # ID: 优先使用 id 字段，否则生成 aime_2025_0, aime_2025_1...
                    "problem_id": item.get("id", f"aime_2025_{idx}"),
                    
                    # 问题描述
                    "problem": item.get("problem", ""),
                    
                    # 答案（0-999 的整数）
                    "answer": item.get("answer", ""),
                    
                    # 解答过程（AIME 2025 数据集可能没有这个字段）
                    "solution": item.get("solution", ""),
                    
                    # 难度（可选）
                    "difficulty": item.get("difficulty", None),
                    
                    # 主题（可选）
                    "topic": item.get("topic", None)
                }
                problems.append(problem)
            
            # 保存到实例变量
            self.problems = problems
            print(f" 加载了 {len(problems)} 个 AIME {self.year} 真题")
            return problems
            
        except Exception as e:
            # 加载失败，打印错误信息和解决建议
            print(f" 加载失败: {e}")
            print(f"提示: 请确保已安装 huggingface_hub 并配置 HF_TOKEN")
            print(f"   安装: pip install huggingface_hub")
            print(f"   配置: export HF_TOKEN=your_token")
            raise
    
    def get_problem(self, problem_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取问题
        
        【学习笔记】单个题目查询
        根据题目 ID 查找并返回对应的题目。
        
        使用场景：
        - 查看特定题目的详细信息
        - 在评估结果中关联题目数据
        
        示例：
            dataset = AIDataset(dataset_type="real", year=2025)
            dataset.load()
            
            problem = dataset.get_problem("aime_2025_0")
            if problem:
                print(f"问题: {problem['problem']}")
                print(f"答案: {problem['answer']}")
        
        Args:
            problem_id: 题目 ID
        
        Returns:
            题目字典，如果找不到则返回 None
        """
        for problem in self.problems:
            if problem["problem_id"] == problem_id:
                return problem
        return None
    
    def get_problems_by_topic(self, topic: str) -> List[Dict[str, Any]]:
        """根据主题获取问题
        
        【学习笔记】主题筛选
        根据数学主题筛选题目。
        
        常见主题：
        - algebra: 代数
        - geometry: 几何
        - number_theory: 数论
        - combinatorics: 组合
        
        使用场景：
        - 分析特定主题的生成质量
        - 对比不同主题的表现
        
        示例：
            dataset = AIDataset(dataset_type="generated", data_path="data.json")
            dataset.load()
            
            # 获取所有几何题
            geometry_problems = dataset.get_problems_by_topic("geometry")
            print(f"几何题数量: {len(geometry_problems)}")
        
        Args:
            topic: 主题名称
        
        Returns:
            符合主题的题目列表
        """
        return [p for p in self.problems if p.get("topic") == topic]
    
    def get_problems_by_difficulty(self, min_diff: int, max_diff: int) -> List[Dict[str, Any]]:
        """根据难度范围获取问题
        
        【学习笔记】难度筛选
        根据难度范围筛选题目。
        
        AIME 难度范围：
        - 1-15：题目序号，通常后面的题更难
        - 典型难度：6-9 题算中等难度
        
        使用场景：
        - 分析特定难度范围的生成质量
        - 对比简单题和困难题的表现
        
        示例：
            dataset = AIDataset(dataset_type="real", year=2025)
            dataset.load()
            
            # 获取中等难度题目（6-9 题）
            medium_problems = dataset.get_problems_by_difficulty(6, 9)
            
            # 获取困难题目（10-15 题）
            hard_problems = dataset.get_problems_by_difficulty(10, 15)
        
        Args:
            min_diff: 最小难度（包含）
            max_diff: 最大难度（包含）
        
        Returns:
            符合难度范围的题目列表
        """
        return [
            p for p in self.problems 
            if p.get("difficulty") and min_diff <= p["difficulty"] <= max_diff
        ]
    
    def __len__(self) -> int:
        """返回数据集大小
        
        【学习笔记】Python 魔法方法
        实现 __len__ 方法后，可以使用 len(dataset) 获取数据集大小。
        
        示例：
            dataset = AIDataset(dataset_type="generated", data_path="data.json")
            dataset.load()
            print(f"数据集大小: {len(dataset)}")
        """
        return len(self.problems)
    
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """支持索引访问
        
        【学习笔记】Python 魔法方法
        实现 __getitem__ 方法后，可以使用 dataset[i] 访问第 i 个题目。
        
        示例：
            dataset = AIDataset(dataset_type="generated", data_path="data.json")
            dataset.load()
            
            # 访问第一个题目
            first_problem = dataset[0]
            print(f"第一题: {first_problem['problem']}")
            
            # 遍历所有题目
            for problem in dataset:
                print(problem['problem_id'])
        """
        return self.problems[idx]

