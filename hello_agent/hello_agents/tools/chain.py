"""工具链管理器 - HelloAgents工具链式调用支持"""

from typing import List, Dict, Any, Optional
from .registry import ToolRegistry


class ToolChain:
    """
    工具链 - 支持多个工具的顺序执行
    
    工具链允许将多个工具按顺序组合执行，前一个工具的输出可以作为后一个工具的输入。
    支持模板变量替换，实现工具间的数据传递。
    
    Attributes:
        name: 工具链名称
        description: 工具链描述
        steps: 工具执行步骤列表，每个步骤包含工具名、输入模板和输出键
    """

    def __init__(self, name: str, description: str):
        """
        初始化工具链
        
        Args:
            name: 工具链名称
            description: 工具链描述
        """
        self.name = name
        self.description = description
        self.steps: List[Dict[str, Any]] = []  # 存储工具执行步骤

    def add_step(self, tool_name: str, input_template: str, output_key: str = None):
        """
        添加工具执行步骤到工具链
        
        步骤按添加顺序执行。输入模板支持使用 {变量名} 格式引用上下文中的变量。
        
        Args:
            tool_name: 要执行的工具名称，必须已在注册表中注册
            input_template: 输入模板字符串，支持变量替换
                          例如: "{input}" 使用初始输入
                               "{search_result}" 使用前一步骤的输出
            output_key: 输出结果的键名，用于后续步骤引用
                       如果为None，自动生成为 "step_N_result"
        """
        # 构建步骤定义
        step = {
            "tool_name": tool_name,
            "input_template": input_template,
            "output_key": output_key or f"step_{len(self.steps)}_result"  # 自动生成输出键名
        }
        self.steps.append(step)
        print(f"工具链 '{self.name}' 添加步骤: {tool_name}")

    def execute(self, registry: ToolRegistry, input_data: str, context: Dict[str, Any] = None) -> str:
        """
        执行工具链中的所有步骤
        
        按顺序执行每个步骤，每个步骤的输出会保存到上下文中供后续步骤使用。
        如果任何步骤执行失败，整个工具链停止执行并返回错误信息。
        
        Args:
            registry: 工具注册表，用于查找和执行工具
            input_data: 初始输入数据，会被保存到上下文的 "input" 键中
            context: 执行上下文字典，用于变量替换
                    如果为None，会创建一个新的空字典
            
        Returns:
            最后一个步骤的执行结果字符串
            如果执行失败，返回错误信息
        """
        if not self.steps:
            return "错误：工具链为空，无法执行"

        print(f"开始执行工具链: {self.name}")
        
        # 初始化执行上下文
        if context is None:
            context = {}
        context["input"] = input_data  # 将初始输入保存到上下文
        
        final_result = input_data
        
        # 顺序执行每个步骤
        for i, step in enumerate(self.steps):
            tool_name = step["tool_name"]
            input_template = step["input_template"]
            output_key = step["output_key"]
            
            print(f"执行步骤 {i+1}/{len(self.steps)}: {tool_name}")
            
            # 使用上下文替换模板中的变量
            try:
                actual_input = input_template.format(**context)
            except KeyError as e:
                return f"错误：模板变量替换失败，变量 {e} 不存在于上下文中"
            
            # 执行工具并保存结果
            try:
                result = registry.execute_tool(tool_name, actual_input)
                context[output_key] = result  # 将结果保存到上下文供后续步骤使用
                final_result = result  # 更新最终结果
                print(f"步骤 {i+1} 完成")
            except Exception as e:
                return f"错误：工具 '{tool_name}' 执行失败: {e}"
        
        print(f"工具链 '{self.name}' 执行完成")
        return final_result


class ToolChainManager:
    """
    工具链管理器
    
    负责管理多个工具链的注册、查询和执行。
    提供统一的工具链管理接口。
    
    Attributes:
        registry: 工具注册表，用于执行工具链中的工具
        chains: 已注册的工具链字典，key为工具链名称
    """

    def __init__(self, registry: ToolRegistry):
        """
        初始化工具链管理器
        
        Args:
            registry: 工具注册表实例
        """
        self.registry = registry
        self.chains: Dict[str, ToolChain] = {}  # 存储已注册的工具链

    def register_chain(self, chain: ToolChain):
        """
        注册工具链到管理器
        
        Args:
            chain: 要注册的工具链实例
        """
        self.chains[chain.name] = chain
        print(f"工具链 '{chain.name}' 已注册")

    def execute_chain(self, chain_name: str, input_data: str, context: Dict[str, Any] = None) -> str:
        """
        执行指定名称的工具链
        
        Args:
            chain_name: 工具链名称
            input_data: 初始输入数据
            context: 执行上下文，可选
            
        Returns:
            工具链执行结果，如果工具链不存在则返回错误信息
        """
        if chain_name not in self.chains:
            return f"错误：工具链 '{chain_name}' 不存在"

        chain = self.chains[chain_name]
        return chain.execute(self.registry, input_data, context)

    def list_chains(self) -> List[str]:
        """
        列出所有已注册的工具链名称
        
        Returns:
            包含所有工具链名称的列表
        """
        return list(self.chains.keys())

    def get_chain_info(self, chain_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定工具链的详细信息
        
        Args:
            chain_name: 工具链名称
            
        Returns:
            包含工具链详细信息的字典，如果工具链不存在则返回None
            字典包含: name, description, steps(步骤数), step_details(步骤详情列表)
        """
        if chain_name not in self.chains:
            return None
        
        chain = self.chains[chain_name]
        return {
            "name": chain.name,
            "description": chain.description,
            "steps": len(chain.steps),
            "step_details": [
                {
                    "tool_name": step["tool_name"],
                    "input_template": step["input_template"],
                    "output_key": step["output_key"]
                }
                for step in chain.steps
            ]
        }


# 便捷函数 - 预定义工具链创建函数

def create_research_chain() -> ToolChain:
    """
    创建一个研究工具链：搜索 -> 计算 -> 总结
    
    这是一个示例工具链，展示如何组合多个工具完成复杂任务。
    
    Returns:
        配置好的研究工具链实例
    """
    chain = ToolChain(
        name="research_and_calculate",
        description="搜索信息并进行相关计算"
    )

    # 步骤1：搜索信息
    chain.add_step(
        tool_name="search",
        input_template="{input}",
        output_key="search_result"
    )

    # 步骤2：基于搜索结果进行计算
    chain.add_step(
        tool_name="my_calculator",
        input_template="2 + 2",  # 简单的计算示例
        output_key="calc_result"
    )

    return chain


def create_simple_chain() -> ToolChain:
    """
    创建一个简单的工具链示例
    
    仅包含一个计算步骤，用于演示工具链的基本用法。
    
    Returns:
        配置好的简单工具链实例
    """
    chain = ToolChain(
        name="simple_demo",
        description="简单的工具链演示"
    )

    # 只包含一个计算步骤
    chain.add_step(
        tool_name="my_calculator",
        input_template="{input}",
        output_key="result"
    )

    return chain
