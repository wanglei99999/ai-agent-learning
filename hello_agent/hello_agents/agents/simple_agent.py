"""SimpleAgent - 最基础的Agent实现"""
import re
import json
from typing import Optional, Iterator, TYPE_CHECKING

from ..core.agent import Agent
from ..core.llm import HelloAgentsLLM
from ..core.config import Config
from ..core.message import Message

if TYPE_CHECKING:
    from ..tools.registry import ToolRegistry


class MySimpleAgent(Agent):
    """
    简单对话Agent
    
    最基础的Agent实现，展示如何基于框架基类构建自定义Agent。
    支持工具调用功能。
    """
    
    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_registry: Optional['ToolRegistry'] = None,
        enable_tool_calling: bool = True
    ):
        """
        初始化SimpleAgent
        
        Args:
            name: Agent名称
            llm: LLM实例
            system_prompt: 系统提示词
            config: 配置对象
            tool_registry: 工具注册表（可选，如果提供则启用工具调用）
            enable_tool_calling: 是否启用工具调用（只有在提供tool_registry时生效）
        """ 
        # 调用父类初始化
        super().__init__(name, llm, system_prompt, config)
        
        # 设置工具相关属性
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling and tool_registry is not None
        
        # 初始化完成

    def run(self, input_text: str, max_tool_iterations: int = 3, **kwargs) -> str:
        """
        运行Agent，处理用户输入并返回响应
        
        参数：
            input_text: 用户输入的文本
            max_tool_iterations: 最大工具调用轮数
            **kwargs: 其他可选参数
        
        返回：
            str: Agent的响应
        """
        # 开始处理用户输入
        
        # 构建消息列表
        messages = []
        
        # 添加系统消息（可能包含工具信息）
        enhanced_system_prompt = self._get_enhanced_system_prompt()
        messages.append({"role": "system", "content": enhanced_system_prompt})
        
        # 添加历史消息
        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": input_text})
        
        # 如果没有启用工具调用，使用简单对话逻辑
        if not self.enable_tool_calling:
            response = self.llm.invoke(messages, **kwargs)
            self.add_message(Message(content=input_text, role="user"))
            self.add_message(Message(content=response, role="assistant"))
            return response
        
        # 支持多轮工具调用的逻辑
        return self._run_with_tools(messages, input_text, max_tool_iterations, **kwargs)
    
    def _get_enhanced_system_prompt(self) -> str:
        """构建增强的系统提示词，包含工具信息"""
        base_prompt = self.system_prompt or "你是一个有用的AI助手。"

        # 如果没有启用工具调用，直接返回基础提示词
        if not self.enable_tool_calling or not self.tool_registry:
            return base_prompt
        
        # 获取工具描述
        tools_description = self.tool_registry.get_tools_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt

        # 构建工具信息部分
        tools_section = "\n\n## 可用工具\n"
        tools_section += "你可以使用以下工具来帮助回答问题:\n"
        tools_section += tools_description + "\n"

        # 添加工具调用格式说明
        tools_section += "\n## 工具调用格式\n"
        tools_section += "当需要使用工具时，请使用以下格式：\n"
        tools_section += "`[TOOL_CALL:{tool_name}:{parameters}]`\n\n"

        tools_section += "### 参数格式说明\n"
        tools_section += "1. **多个参数**：使用 `key=value` 格式，用逗号分隔\n"
        tools_section += "   示例：`[TOOL_CALL:calculator_multiply:a=12,b=8]`\n"
        tools_section += "   示例：`[TOOL_CALL:filesystem_read_file:path=README.md]`\n\n"
        tools_section += "2. **单个参数**：直接使用 `key=value`\n"
        tools_section += "   示例：`[TOOL_CALL:search:query=Python编程]`\n\n"
        tools_section += "3. **简单查询**：可以直接传入文本\n"
        tools_section += "   示例：`[TOOL_CALL:search:Python编程]`\n\n"

        tools_section += "### 重要提示\n"
        tools_section += "- 参数名必须与工具定义的参数名完全匹配\n"
        tools_section += "- 数字参数直接写数字，不需要引号：`a=12` 而不是 `a=\"12\"`\n"
        tools_section += "- 文件路径等字符串参数直接写：`path=README.md`\n"
        tools_section += "- 工具调用结果会自动插入到对话中，然后你可以基于结果继续回答\n"

        # 返回：基础提示词 + 工具信息
        return base_prompt + tools_section

    def _run_with_tools(self, messages: list, input_text: str, max_tool_iterations: int, **kwargs) -> str:
        """
        支持工具调用的运行逻辑
        
        实现循环：LLM响应 → 解析工具调用 → 执行工具 → 将结果反馈给LLM → 继续
        """
        current_iteration = 0
        final_response = ""

        # 工具调用循环，最多执行 max_tool_iterations 次
        while current_iteration < max_tool_iterations:
            # 1. 调用LLM获取响应
            response = self.llm.invoke(messages, **kwargs)
            
            # 2. 检查响应中是否有工具调用标记
            tool_calls = self._parse_tool_calls(response)

            # 3. 如果检测到工具调用
            if tool_calls:
                # 检测到工具调用
                
                # 执行所有工具调用并收集结果
                tool_results = []
                clean_response = response

                for call in tool_calls:
                    # 执行单个工具
                    result = self._execute_tool_call(call['tool_name'], call['parameters'])
                    tool_results.append(result)
                    # 从响应中移除工具调用标记，保留其他文本
                    clean_response = clean_response.replace(call['original'], "")

                # 4. 将LLM的响应（去除工具标记后）添加到消息历史
                messages.append({"role": "assistant", "content": clean_response})

                # 5. 将工具执行结果作为用户消息添加，让LLM基于结果继续回答
                tool_results_text = "\n\n".join(tool_results)
                messages.append({"role": "user", "content": f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"})

                current_iteration += 1
                continue  # 继续下一轮循环
            
            # 6. 没有工具调用，说明这是最终回答
            final_response = response
            break

        # 7. 如果超过最大迭代次数还没有最终答案，强制获取一次
        if current_iteration >= max_tool_iterations and not final_response:
            # 达到最大工具调用次数
            final_response = self.llm.invoke(messages, **kwargs)

        # 8. 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_response, "assistant"))

        return final_response

    def _parse_tool_calls(self, text: str) -> list:
        """
        解析文本中的工具调用
        
        使用正则表达式提取 [TOOL_CALL:tool_name:parameters] 格式的工具调用
        
        返回：
            list: 包含工具调用信息的字典列表
                  [{'tool_name': 'search', 'parameters': 'Python', 'original': '[TOOL_CALL:search:Python]'}]
        """
        # 正则模式：匹配 [TOOL_CALL:工具名:参数]
        pattern = r'\[TOOL_CALL:([^:]+):([^\]]+)\]'
        matches = re.findall(pattern, text)

        tool_calls = []
        for tool_name, parameters in matches:
            tool_calls.append({
                'tool_name': tool_name.strip(),      # 工具名（去除空格）
                'parameters': parameters.strip(),    # 参数（去除空格）
                'original': f'[TOOL_CALL:{tool_name}:{parameters}]'  # 原始字符串（用于替换）
            })
        return tool_calls

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """
        执行工具调用
        
        根据工具名和参数，调用对应的工具并返回结果
        """
        if not self.tool_registry:
            return f"错误:未配置工具注册表"
        
        try:
            # 特殊处理：calculator 工具直接传入表达式字符串
            if tool_name == 'calculator':
                result = self.tool_registry.execute_tool(tool_name, parameters)
            else:
                # 其他工具：先解析参数为字典，再执行
                param_dict = self._parse_tool_parameters(tool_name, parameters)
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    return f"错误:未找到工具 '{tool_name}'"
                result = tool.run(param_dict)

            return f"工具 {tool_name} 执行结果:\n{result}"
        except Exception as e:
            return f"工具调用失败:{str(e)}"

    def _convert_parameter_types(self, tool_name: str, param_dict: dict) -> dict:
        """
        根据工具的参数定义转换参数类型

        Args:
            tool_name: 工具名称
            param_dict: 参数字典

        Returns:
            类型转换后的参数字典
        """
        if not self.tool_registry:
            return param_dict

        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return param_dict

        # 获取工具的参数定义
        try:
            tool_params = tool.get_parameters()
        except:
            return param_dict

        # 创建参数类型映射
        param_types = {}
        for param in tool_params:
            param_types[param.name] = param.type

        # 转换参数类型
        converted_dict = {}
        for key, value in param_dict.items():
            if key in param_types:
                param_type = param_types[key]
                try:
                    if param_type == 'number' or param_type == 'integer':
                        # 转换为数字
                        if isinstance(value, str):
                            converted_dict[key] = float(value) if param_type == 'number' else int(value)
                        else:
                            converted_dict[key] = value
                    elif param_type == 'boolean':
                        # 转换为布尔值
                        if isinstance(value, str):
                            converted_dict[key] = value.lower() in ('true', '1', 'yes')
                        else:
                            converted_dict[key] = bool(value)
                    else:
                        converted_dict[key] = value
                except (ValueError, TypeError):
                    # 转换失败，保持原值
                    converted_dict[key] = value
            else:
                converted_dict[key] = value

        return converted_dict

    def _parse_tool_parameters(self, tool_name: str, parameters: str) -> dict:
        """
        智能解析工具参数
        
        支持三种格式：
        1. JSON 格式：{"action": "search", "query": "Python"}
        2. key=value 格式：query=Python 或 action=search,query=Python
        3. 简化格式：Python（根据工具类型自动推断参数名）
        """
        param_dict = {}

        # 格式1：尝试解析 JSON 格式
        if parameters.strip().startswith('{'):
            try:
                param_dict = json.loads(parameters)
                param_dict = self._convert_parameter_types(tool_name, param_dict)
                return param_dict
            except json.JSONDecodeError:
                pass

        # 格式2：包含 '=' 的标准格式
        if '=' in parameters:
            if ',' in parameters:
                # 多个参数：action=search,query=Python,limit=3
                pairs = parameters.split(',')
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        param_dict[key.strip()] = value.strip()
            else:
                # 单个参数：query=Python
                key, value = parameters.split('=', 1)
                param_dict[key.strip()] = value.strip()
            
            # 类型转换
            param_dict = self._convert_parameter_types(tool_name, param_dict)
            
            # 智能推断 action
            if 'action' not in param_dict:
                param_dict = self._infer_action(tool_name, param_dict)
        else:
            # 格式3：简化格式
            param_dict = self._infer_simple_parameters(tool_name, parameters)
        
        return param_dict
    
    def _infer_action(self, tool_name: str, param_dict: dict) -> dict:
        """根据工具类型和参数推断action"""
        if tool_name == 'memory':
            if 'recall' in param_dict:
                param_dict['action'] = 'search'
                param_dict['query'] = param_dict.pop('recall')
            elif 'store' in param_dict:
                param_dict['action'] = 'add'
                param_dict['content'] = param_dict.pop('store')
            elif 'query' in param_dict:
                param_dict['action'] = 'search'
            elif 'content' in param_dict:
                param_dict['action'] = 'add'
        elif tool_name == 'rag':
            if 'search' in param_dict:
                param_dict['action'] = 'search'
                param_dict['query'] = param_dict.pop('search')
            elif 'query' in param_dict:
                param_dict['action'] = 'search'
            elif 'text' in param_dict:
                param_dict['action'] = 'add_text'

        return param_dict


    def _infer_simple_parameters(self, tool_name: str, parameters: str) -> dict:
        """为简单参数推断完整的参数字典"""
        if tool_name == 'rag':
            return {'action': 'search', 'query': parameters}
        elif tool_name == 'memory':
            return {'action': 'search', 'query': parameters}
        else:
            return {'input': parameters}

    def add_tool(self, tool) -> None:
        """
        添加工具到Agent（便利方法）

        Args:
            tool: Tool对象
            auto_expand: 是否自动展开可展开的工具（默认True）

        如果工具是可展开的（expandable=True），会自动展开为多个独立工具
        """
        if not self.tool_registry:      
            from hello_agents import ToolRegistry
            self.tool_registry = ToolRegistry()
            self.enable_tool_calling = True

        self.tool_registry.register_tool(tool)

    def has_tools(self) -> bool:
        """检查是否有可用工具"""
        return self.tool_registry is not None and len(self.tool_registry.tools) > 0

    def remove_tool(self, tool_name: str) -> bool:
        """移除工具（便利方法）"""
        if self.tool_registry:
            self.tool_registry.unregister(tool_name)
            return True
        return False

    def list_tools(self) -> list:
        """列出所有可用工具"""
        if self.tool_registry:
            return self.tool_registry.list_tools()
        return []

    def stream_run(self, input_text: str, **kwargs) -> Iterator[str]:
        """
        自定义的流式运行方法
        """
        # 开始流式处理
        messages = []

        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        
        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": input_text})

        # 流式调用LLM
        full_response = ""
        # 流式输出
        for chunk in self.llm.invoke(messages, **kwargs):
            full_response += chunk
            print(chunk, end="", flush=True)
            yield chunk
        print()  # 换行

        # 保存完整对话到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(full_response, "assistant"))
