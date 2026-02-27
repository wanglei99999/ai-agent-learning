"""BFCL 官方评估工具集成模块

【学习笔记】模块作用
本模块是本地评估框架与 BFCL 官方评估工具之间的桥梁。

为什么需要这个模块？
1. 本地评估 (BFCLEvaluator):
   - 优点: 灵活、可定制、方便调试
   - 缺点: 可能与官方标准有细微差异

2. 官方评估 (BFCL CLI 工具):
   - 优点: 权威、可提交到排行榜、与官方完全一致
   - 缺点: 需要特定的文件格式和目录结构

3. 集成模块的价值:
   - 自动安装官方工具
   - 转换文件格式和路径
   - 调用官方命令行工具
   - 解析官方评估结果
   → 让你既能本地快速迭代，又能获得官方认证的分数

工作流程:
  本地评估 → 导出结果 → 转换格式 → 官方评估 → 解析分数 → 提交排行榜
  (快速)     (灵活)     (自动)     (权威)     (标准化)   (认证)
"""

# === 标准库导入 ===
import subprocess  # 用于执行命令行命令 (pip install, bfcl evaluate)
import json        # 用于解析评估结果 JSON 文件
import os          # 用于设置环境变量
from pathlib import Path  # 用于路径操作
from typing import Dict, Any, Optional, Union  # 类型注解


class BFCLIntegration:
    """BFCL 官方评估工具集成类
    
    【学习笔记】核心功能
    这个类封装了与 BFCL 官方命令行工具的所有交互，让你无需手动操作。
    
    提供的功能:
    1. is_installed()      - 检查官方工具是否已安装
    2. install()           - 自动安装官方工具 (pip install bfcl-eval)
    3. prepare_result_file() - 转换为官方要求的文件格式和路径
    4. run_evaluation()    - 调用官方命令行工具进行评估
    5. parse_results()     - 解析官方生成的评分文件
    6. get_summary_csv()   - 获取汇总 CSV 文件
    7. print_usage_guide() - 打印使用指南
    
    官方工具的要求:
    - 文件路径格式: result/{model_name}/BFCL_v3_{category}_result.json
    - 评分输出路径: score/{model_name}/BFCL_v3_{category}_score.json
    - 汇总 CSV: score/data_overall.csv
    - 环境变量: BFCL_PROJECT_ROOT
    
    完整使用流程示例:
        # 步骤1: 初始化
        integration = BFCLIntegration(project_root="./bfcl_project")
        
        # 步骤2: 检查并安装官方工具
        if not integration.is_installed():
            integration.install()
        
        # 步骤3: 准备结果文件 (转换为官方格式)
        integration.prepare_result_file(
            source_file="my_results.json",
            model_name="HelloAgents",
            category="simple_python"
        )
        
        # 步骤4: 运行官方评估
        success = integration.run_evaluation(
            model_name="HelloAgents",
            category="simple_python"
        )
        
        # 步骤5: 解析官方评分
        if success:
            scores = integration.parse_results(
                model_name="HelloAgents",
                category="simple_python"
            )
            print(f"官方评分: {scores}")
            
            # 步骤6: 查看汇总结果
            csv_file = integration.get_summary_csv()
    
    与本地评估的配合:
        # 先用本地评估器快速迭代
        evaluator = BFCLEvaluator()
        results = evaluator.evaluate(agent, dataset)
        evaluator.export_results(results, "my_results.json")
        
        # 再用官方工具获得权威分数
        integration = BFCLIntegration()
        integration.run_evaluation(
            model_name="MyAgent",
            category="simple_python",
            result_file="my_results.json"
        )
    """
    
    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        """初始化 BFCL 集成
        
        【学习笔记】目录结构
        BFCL 官方工具要求特定的目录结构:
        
        project_root/
        ├── result/                    # 评估结果输入目录
        │   └── {model_name}/
        │       └── BFCL_v3_{category}_result.json  # 结果文件
        └── score/                     # 评分输出目录
            ├── {model_name}/
            │   └── BFCL_v3_{category}_score.json  # 评分文件
            └── data_overall.csv        # 汇总 CSV
        
        示例:
            # 使用当前目录
            integration = BFCLIntegration()
            # project_root = 当前工作目录
            
            # 指定项目目录
            integration = BFCLIntegration(project_root="./bfcl_project")
            # project_root = ./bfcl_project
            # result_dir = ./bfcl_project/result
            # score_dir = ./bfcl_project/score
        
        Args:
            project_root: BFCL 项目根目录，如果为 None 则使用当前目录
        """
        # 设置项目根目录 (如果未指定则使用当前工作目录)
        self.project_root = Path(project_root) if project_root else Path.cwd()
        
        # 设置结果文件目录 (官方工具从这里读取评估结果)
        self.result_dir = self.project_root / "result"
        
        # 设置评分输出目录 (官方工具将评分写入这里)
        self.score_dir = self.project_root / "score"
    
    def is_installed(self) -> bool:
        """检查 BFCL 评估工具是否已安装
        
        【学习笔记】检查机制
        通过尝试运行 'bfcl --version' 命令来检查工具是否存在。
        
        可能的情况:
        1. 命令执行成功 (returncode == 0) → 已安装
        2. FileNotFoundError → 命令不存在，未安装
        3. TimeoutExpired → 命令超时，视为未安装
        
        subprocess.run() 参数说明:
        - capture_output=True: 捕获输出 (不显示到控制台)
        - text=True: 输出为字符串而非字节
        - timeout=5: 5秒超时
        
        示例:
            integration = BFCLIntegration()
            if integration.is_installed():
                print("已安装 BFCL 工具")
            else:
                print("未安装，需要先安装")
        
        Returns:
            True 如果已安装，False 否则
        """
        try:
            # 尝试运行 'bfcl --version' 命令
            result = subprocess.run(
                ["bfcl", "--version"],
                capture_output=True,  # 捕获输出
                text=True,            # 输出为字符串
                timeout=5             # 5秒超时
            )
            # returncode == 0 表示命令执行成功
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # 命令不存在或超时，说明未安装
            return False
    
    def install(self) -> bool:
        """安装 BFCL 评估工具
        
        【学习笔记】安装过程
        通过 pip 安装 BFCL 官方评估工具包 'bfcl-eval'。
        
        安装命令:
            pip install bfcl-eval
        
        安装后可以使用的命令:
            bfcl --version                    # 查看版本
            bfcl evaluate --model {name} ...  # 运行评估
        
        超时设置:
        - timeout=300: 5分钟超时 (安装可能需要下载依赖)
        
        错误处理:
        1. returncode != 0: 安装命令执行失败
        2. TimeoutExpired: 安装超时 (>五分钟)
        3. Exception: 其他异常情况
        
        示例:
            integration = BFCLIntegration()
            if not integration.is_installed():
                success = integration.install()
                if success:
                    print("安装成功，可以开始评估")
        
        Returns:
            True 如果安装成功，False 否则
        """
        print(" 正在安装 BFCL 评估工具...")
        print("   运行: pip install bfcl-eval")
        
        try:
            # 执行 pip install 命令
            result = subprocess.run(
                ["pip", "install", "bfcl-eval"],
                capture_output=True,  # 捕获输出
                text=True,            # 输出为字符串
                timeout=300           # 5分钟超时
            )
            
            if result.returncode == 0:
                print(" BFCL 评估工具安装成功")
                return True
            else:
                # 安装失败，打印错误信息
                print(f" 安装失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            # 安装超时 (>五分钟)
            print(" 安装超时")
            return False
        except Exception as e:
            # 其他异常
            print(f" 安装出错: {e}")
            return False
    
    def prepare_result_file(
        self,
        source_file: Union[str, Path],
        model_name: str,
        category: str
    ) -> Path:
        """准备 BFCL 评估所需的结果文件
        
        【学习笔记】文件路径转换
        BFCL 官方工具要求结果文件必须放在特定路径，并且文件名必须符合特定格式。
        
        官方要求的路径格式:
            result/{model_name}/BFCL_v3_{category}_result.json
        
        示例:
            # 本地评估生成的结果文件
            source_file = "my_evaluation_results.json"
            
            # 转换为官方格式
            integration.prepare_result_file(
                source_file="my_evaluation_results.json",
                model_name="HelloAgents",
                category="simple_python"
            )
            
            # 结果:
            # my_evaluation_results.json 被复制到
            # result/HelloAgents/BFCL_v3_simple_python_result.json
        
        操作步骤:
        1. 创建目标目录: result/{model_name}/
        2. 确定目标文件名: BFCL_v3_{category}_result.json
        3. 复制源文件到目标路径
        
        Args:
            source_file: 源结果文件路径 (本地评估生成的文件)
            model_name: 模型名称 (如 "HelloAgents")
            category: 评估类别 (如 "simple_python")
            
        Returns:
            目标文件路径 (Path 对象)
        """
        source_file = Path(source_file)
        
        # 步骤1: 创建目标目录 result/{model_name}/
        target_dir = self.result_dir / model_name
        target_dir.mkdir(parents=True, exist_ok=True)  # parents=True 递归创建父目录
        
        # 步骤2: 确定目标文件名 (BFCL 官方要求的格式)
        target_file = target_dir / f"BFCL_v3_{category}_result.json"
        
        # 步骤3: 复制文件
        if source_file.exists():
            import shutil
            shutil.copy2(source_file, target_file)  # copy2 保留元数据
            print(f" 结果文件已准备")
            print(f"   源文件: {source_file}")
            print(f"   目标文件: {target_file}")
        else:
            print(f" 源文件不存在: {source_file}")
        
        return target_file
    
    def run_evaluation(
        self,
        model_name: str,
        category: str,
        result_file: Optional[Union[str, Path]] = None
    ) -> bool:
        """运行 BFCL 官方评估
        
        【学习笔记】调用官方工具
        这个方法调用 BFCL 官方命令行工具进行评估。
        
        执行的命令:
            bfcl evaluate --model {model_name} --test-category {category}
        
        命令参数说明:
        - --model: 模型名称 (用于查找 result/{model_name}/ 目录)
        - --test-category: 评估类别 (如 simple_python, multiple 等)
        
        环境变量:
        - BFCL_PROJECT_ROOT: 告诉官方工具项目根目录在哪里
        
        工作流程:
        1. 如果提供了 result_file，先调用 prepare_result_file() 准备文件
        2. 设置环境变量 BFCL_PROJECT_ROOT
        3. 构建并执行 bfcl evaluate 命令
        4. 官方工具会:
           - 读取: result/{model_name}/BFCL_v3_{category}_result.json
           - 生成: score/{model_name}/BFCL_v3_{category}_score.json
           - 更新: score/data_overall.csv
        
        超时设置:
        - timeout=600: 10分钟超时 (评估可能需要较长时间)
        
        示例:
            integration = BFCLIntegration()
            
            # 方式1: 直接评估 (假设文件已准备好)
            integration.run_evaluation(
                model_name="HelloAgents",
                category="simple_python"
            )
            
            # 方式2: 提供结果文件 (自动准备)
            integration.run_evaluation(
                model_name="HelloAgents",
                category="simple_python",
                result_file="my_results.json"
            )
        
        Args:
            model_name: 模型名称
            category: 评估类别
            result_file: 结果文件路径 (可选，如果提供则先准备文件)
            
        Returns:
            True 如果评估成功，False 否则
        """
        # 步骤1: 如果提供了结果文件，先准备 (转换为官方格式)
        if result_file:
            self.prepare_result_file(result_file, model_name, category)
        
        # 步骤2: 设置环境变量 (告诉官方工具项目根目录)
        env = os.environ.copy()  # 复制当前环境变量
        env["BFCL_PROJECT_ROOT"] = str(self.project_root)  # 添加 BFCL 项目根目录
        
        print(f"\n 运行 BFCL 官方评估...")
        print(f"   模型: {model_name}")
        print(f"   类别: {category}")
        print(f"   项目根目录: {self.project_root}")
        
        # 步骤3: 构建命令
        cmd = [
            "bfcl", "evaluate",           # 官方工具命令
            "--model", model_name,         # 模型名称
            "--test-category", category    # 评估类别
        ]
        
        print(f"   命令: {' '.join(cmd)}")
        
        try:
            # 步骤4: 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,  # 捕获输出
                text=True,            # 输出为字符串
                timeout=600,          # 10分钟超时
                env=env               # 使用设置好的环境变量
            )
            
            if result.returncode == 0:
                # 评估成功
                print(" BFCL 评估完成")
                print(result.stdout)  # 打印官方工具的输出
                return True
            else:
                # 评估失败
                print(f" 评估失败")
                print(f"   错误信息: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            # 评估超时 (>10分钟)
            print(" 评估超时")
            return False
        except Exception as e:
            # 其他异常
            print(f" 评估出错: {e}")
            return False
    
    def parse_results(
        self,
        model_name: str,
        category: str
    ) -> Optional[Dict[str, Any]]:
        """解析 BFCL 评估结果
        
        【学习笔记】读取官方评分
        官方工具运行后会生成评分文件，这个方法读取并解析该文件。
        
        官方评分文件路径:
            score/{model_name}/BFCL_v3_{category}_score.json
        
        评分文件内容示例:
            {
                "accuracy": 0.85,
                "precision": 0.88,
                "recall": 0.82,
                "f1_score": 0.85,
                "total_samples": 100,
                "correct_samples": 85,
                ...
            }
        
        使用流程:
            # 步骤1: 运行官方评估
            integration.run_evaluation(
                model_name="HelloAgents",
                category="simple_python"
            )
            
            # 步骤2: 解析评分
            scores = integration.parse_results(
                model_name="HelloAgents",
                category="simple_python"
            )
            
            # 步骤3: 使用评分
            if scores:
                print(f"准确率: {scores['accuracy']}")
                print(f"F1 分数: {scores['f1_score']}")
        
        Args:
            model_name: 模型名称
            category: 评估类别
            
        Returns:
            评估结果字典，如果文件不存在则返回 None
        """
        # 构建评分文件路径 (BFCL 官方工具生成的文件)
        score_file = self.score_dir / model_name / f"BFCL_v3_{category}_score.json"
        
        # 检查文件是否存在
        if not score_file.exists():
            print(f" 评估结果文件不存在: {score_file}")
            print(f"   请先运行 run_evaluation() 生成评分")
            return None
        
        try:
            # 读取 JSON 文件
            with open(score_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            print(f"\n BFCL 评估结果")
            print(f"   模型: {model_name}")
            print(f"   类别: {category}")
            
            # 提取并打印关键指标 (只打印数值类型的指标)
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, (int, float)):
                        print(f"   {key}: {value}")
            
            return results
            
        except Exception as e:
            print(f" 解析结果失败: {e}")
            return None
    
    def get_summary_csv(self) -> Optional[Path]:
        """获取汇总 CSV 文件路径
        
        【学习笔记】汇总结果
        BFCL 官方工具会生成多个 CSV 文件，汇总不同类别的评估结果。
        
        BFCL 生成的 CSV 文件:
        - data_overall.csv: 总体评分 (所有类别的汇总)
        - data_live.csv: Live 数据集评分
        - data_non_live.csv: Non-Live 数据集评分
        - data_multi_turn.csv: 多轮对话评分
        
        CSV 文件内容示例:
            model_name,simple_python,multiple,parallel,...,overall
            HelloAgents,0.85,0.78,0.72,...,0.80
            GPT-4,0.92,0.88,0.85,...,0.89
            ...
        
        使用场景:
        - 比较多个模型的表现
        - 查看不同类别的得分
        - 生成评估报告
        
        示例:
            integration = BFCLIntegration()
            
            # 运行多个类别的评估
            for category in ["simple_python", "multiple", "parallel"]:
                integration.run_evaluation(
                    model_name="HelloAgents",
                    category=category
                )
            
            # 获取汇总 CSV
            csv_file = integration.get_summary_csv()
            if csv_file:
                # 可以用 pandas 读取并分析
                import pandas as pd
                df = pd.read_csv(csv_file)
                print(df)
        
        Returns:
            data_overall.csv 的路径，如果不存在则返回 None
        """
        # 汇总 CSV 文件路径
        csv_file = self.score_dir / "data_overall.csv"
        
        if csv_file.exists():
            print(f"\n 汇总 CSV 文件: {csv_file}")
            return csv_file
        else:
            print(f"  汇总 CSV 文件不存在: {csv_file}")
            print(f"   请先运行 run_evaluation() 生成评分")
            return None
    
    def print_usage_guide(self):
        """打印使用指南
        
        【学习笔记】帮助信息
        为用户提供完整的使用指南，包括安装、配置、运行和查看结果的步骤。
        
        适用场景:
        - 第一次使用 BFCL 官方工具
        - 忘记具体命令
        - 需要手动运行官方工具
        
        示例:
            integration = BFCLIntegration()
            integration.print_usage_guide()
            # 会打印详细的使用步骤
        """
        print("\n" + "="*60)
        print("BFCL 官方评估工具使用指南")
        print("="*60)
        
        print("\n步骤1: 安装 BFCL 评估工具")
        print("   pip install bfcl-eval")
        
        print("\n步骤2: 设置环境变量 (可选)")
        print(f"   export BFCL_PROJECT_ROOT={self.project_root}")
        print("   # 或者在 Python 中设置: os.environ['BFCL_PROJECT_ROOT'] = '...'")
        
        print("\n步骤3: 准备结果文件")
        print("   将评估结果放在: result/{model_name}/BFCL_v3_{category}_result.json")
        print("   # 可以使用 prepare_result_file() 方法自动准备")
        
        print("\n步骤4: 运行评估")
        print("   bfcl evaluate --model {model_name} --test-category {category}")
        print("   # 或者使用 run_evaluation() 方法")
        
        print("\n步骤5: 查看结果")
        print("   评估结果在: score/{model_name}/BFCL_v3_{category}_score.json")
        print("   汇总结果在: score/data_overall.csv")
        print("   # 可以使用 parse_results() 和 get_summary_csv() 方法")
        
        print("\n" + "="*60)
        print("提示: 使用 BFCLIntegration 类可以自动化以上所有步骤")
        print("="*60)

