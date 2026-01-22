"""FunctionCallAgent - 使用OpenAI函数调用范式的Agent实现"""

from __future__ import annotations

import json
from typing import Iterator, Optional, Union, TYPE_CHECKING, Any, Dict

from ..core.agent import Agent
from ..core.config import Config
from ..core.llm import HelloAgentsLLM
from ..core.message import Message

if TYPE_CHECKING:
    from ..tools.registry import ToolRegistry


def _map_parameter_type(param_type: str) -> str:
    """将工具参数类型映射为JSON Schema允许的类型"""
    normalized = (param_type or "").lower()
    if normalized in {"string", "number", "integer", "boolean", "array", "object"}:
        return normalized
    return "string"


class FunctionCallAgent(Agent):
    """基于OpenAI原生函数调用机制的Agent"""

    def __init__(
        self,
        name: str,
        llm: HelloAgentsLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_registry: Optional["ToolRegistry"] = None,
        enable_tool_calling: bool = True,
        default_tool_choice: Union[str, dict] = "auto",
        max_tool_iterations: int = 3,
    ):
        super().__init__(name, llm, system_prompt, config)
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling and tool_registry is not None
        self.default_tool_choice = default_tool_choice
        self.max_tool_iterations = max_tool_iterations

    def _get_system_prompt(self) -> str:
        """构建系统提示词，注入工具描述"""
        base_prompt = self.system_prompt or "你是一个可靠的AI助理，能够在需要时调用工具完成任务。"

        if not self.enable_tool_calling or not self.tool_registry:
            return base_prompt

        tools_description = self.tool_registry.get_tools_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt

        prompt = base_prompt + "\n\n## 可用工具\n"
        prompt += "当你判断需要外部信息或执行动作时，可以直接通过函数调用使用以下工具：\n"
        prompt += tools_description + "\n"
        prompt += "\n请主动决定是否调用工具，合理利用多次调用来获得完备答案。"
        return prompt

    def _build_tool_schemas(self) -> list[dict[str, Any]]:
        """
        构建符合 OpenAI Function Calling API 的工具定义列表
        
        将工具注册表中的工具转换为 OpenAI 要求的 JSON Schema 格式。
        支持两种类型的工具：
        1. Tool 对象：完整的工具定义，包含参数、类型、描述等
        2. register_function 注册的简单函数：只接受单个字符串参数
        
        Returns:
            list[dict]: OpenAI tools 参数格式的工具定义列表
            
        示例返回格式:
            [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "获取天气信息",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string", "description": "城市名"}
                            },
                            "required": ["city"]
                        }
                    }
                }
            ]
        """
        # 如果未启用工具调用或没有工具注册表，返回空列表
        if not self.enable_tool_calling or not self.tool_registry:
            return []

        schemas: list[dict[str, Any]] = []

        # ========== 处理 Tool 对象（完整的工具定义）==========
        for tool in self.tool_registry.get_all_tools():
            # 用于存储参数的 JSON Schema properties
            properties: Dict[str, Any] = {}
            # 用于存储必填参数列表
            required: list[str] = []

            # 获取工具的参数定义
            try:
                parameters = tool.get_parameters()
            except Exception:
                # 如果获取失败，使用空参数列表
                parameters = []

            # 遍历每个参数，构建 JSON Schema
            for param in parameters:
                # 构建参数的 schema 定义
                properties[param.name] = {
                    "type": _map_parameter_type(param.type),  # 映射为 JSON Schema 类型
                    "description": param.description or ""     # 参数描述
                }
                # 如果参数有默认值，添加到 schema 中
                if param.default is not None:
                    properties[param.name]["default"] = param.default
                # 如果参数是必填的，添加到 required 列表
                if getattr(param, "required", True):
                    required.append(param.name)

            # 构建符合 OpenAI 格式的工具 schema
            schema: dict[str, Any] = {
                "type": "function",  # 固定值，表示这是一个函数
                "function": {
                    "name": tool.name,                    # 工具名称
                    "description": tool.description or "", # 工具描述
                    "parameters": {                       # 参数定义（JSON Schema）
                        "type": "object",                 # 参数是一个对象
                        "properties": properties          # 具体的参数字段
                    }
                }
            }
            # 如果有必填参数，添加 required 字段
            if required:
                schema["function"]["parameters"]["required"] = required
            
            # 将构建好的 schema 添加到列表
            schemas.append(schema)

        # ========== 处理 register_function 注册的简单函数 ==========
        # 这些函数只接受一个字符串参数 "input"
        function_map = getattr(self.tool_registry, "_functions", {})
        for name, info in function_map.items():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,                           # 函数名
                        "description": info.get("description", ""),  # 函数描述
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "input": {                      # 固定参数名 "input"
                                    "type": "string",           # 类型为字符串
                                    "description": "输入文本"
                                }
                            },
                            "required": ["input"]               # input 是必填参数
                        }
                    }
                }
            )

        return schemas

    @staticmethod
    def _extract_message_content(raw_content: Any) -> str:
        """从OpenAI响应的message.content中安全提取文本"""
        if raw_content is None:
            return ""
        if isinstance(raw_content, str):
            return raw_content
        if isinstance(raw_content, list):
            parts: list[str] = []
            for item in raw_content:
                text = getattr(item, "text", None)
                if text is None and isinstance(item, dict):
                    text = item.get("text")
                if text:
                    parts.append(text)
            return "".join(parts)
        return str(raw_content)

    @staticmethod
    def _parse_function_call_arguments(arguments: Optional[str]) -> dict[str, Any]:
        """解析模型返回的JSON字符串参数"""
        if not arguments:
            return {}

        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _convert_parameter_types(self, tool_name: str, param_dict: dict[str, Any]) -> dict[str, Any]:
        """根据工具定义尽可能转换参数类型"""
        if not self.tool_registry:
            return param_dict

        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return param_dict

        try:
            tool_params = tool.get_parameters()
        except Exception:
            return param_dict

        type_mapping = {param.name: param.type for param in tool_params}
        converted: dict[str, Any] = {}

        for key, value in param_dict.items():
            param_type = type_mapping.get(key)
            if not param_type:
                converted[key] = value
                continue

            try:
                normalized = param_type.lower()
                if normalized in {"number", "float"}:
                    converted[key] = float(value)
                elif normalized in {"integer", "int"}:
                    converted[key] = int(value)
                elif normalized in {"boolean", "bool"}:
                    if isinstance(value, bool):
                        converted[key] = value
                    elif isinstance(value, (int, float)):
                        converted[key] = bool(value)
                    elif isinstance(value, str):
                        converted[key] = value.lower() in {"true", "1", "yes"}
                    else:
                        converted[key] = bool(value)
                else:
                    converted[key] = value
            except (TypeError, ValueError):
                converted[key] = value

        return converted

    def _execute_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """执行工具调用并返回字符串结果"""
        if not self.tool_registry:
            return "❌ 错误：未配置工具注册表"

        tool = self.tool_registry.get_tool(tool_name)
        if tool:
            try:
                typed_arguments = self._convert_parameter_types(tool_name, arguments)
                return tool.run(typed_arguments)
            except Exception as exc:
                return f"❌ 工具调用失败：{exc}"

        func = self.tool_registry.get_function(tool_name)
        if func:
            try:
                input_text = arguments.get("input", "")
                return func(input_text)
            except Exception as exc:
                return f"❌ 工具调用失败：{exc}"

        return f"❌ 错误：未找到工具 '{tool_name}'"

    def _invoke_with_tools(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], tool_choice: Union[str, dict], **kwargs):
        """调用底层OpenAI客户端执行函数调用"""
        client = getattr(self.llm, "_client", None)
        if client is None:
            raise RuntimeError("HelloAgentsLLM 未正确初始化客户端，无法执行函数调用。")

        client_kwargs = dict(kwargs)
        client_kwargs.setdefault("temperature", self.llm.temperature)
        if self.llm.max_tokens is not None:
            client_kwargs.setdefault("max_tokens", self.llm.max_tokens)

        return client.chat.completions.create(
            model=self.llm.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            **client_kwargs,
        )

    def run(
        self,
        input_text: str,
        *,
        max_tool_iterations: Optional[int] = None,
        tool_choice: Optional[Union[str, dict]] = None,
        **kwargs,
    ) -> str:
        """
        执行函数调用范式的对话流程
        
        这是 FunctionCallAgent 的核心方法，实现了完整的工具调用循环：
        1. 构建消息列表（系统提示 + 历史 + 用户输入）
        2. 调用 LLM，如果需要工具则执行工具
        3. 将工具结果反馈给 LLM，继续对话
        4. 重复直到得到最终答案或达到最大迭代次数
        
        Args:
            input_text: 用户输入的问题或指令
            max_tool_iterations: 最大工具调用迭代次数（默认使用初始化时的配置）
            tool_choice: 工具选择策略，"auto"（自动）/"none"（禁用）/指定工具名
            **kwargs: 传递给 LLM 的其他参数
            
        Returns:
            str: Agent 的最终回答
        """
        # ========== 第一步：构建消息列表 ==========
        messages: list[dict[str, Any]] = []
        
        # 添加系统提示词（包含工具描述）
        system_prompt = self._get_system_prompt()
        messages.append({"role": "system", "content": system_prompt})

        # 添加历史对话记录
        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})

        # 添加当前用户输入
        messages.append({"role": "user", "content": input_text})

        # ========== 第二步：构建工具 Schema ==========
        tool_schemas = self._build_tool_schemas()
        
        # 如果没有可用工具，直接进行普通对话
        if not tool_schemas:
            response_text = self.llm.invoke(messages, **kwargs)
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(response_text, "assistant"))
            return response_text

        # ========== 第三步：准备工具调用循环 ==========
        # 确定最大迭代次数（参数优先，否则使用默认配置）
        iterations_limit = max_tool_iterations if max_tool_iterations is not None else self.max_tool_iterations
        # 确定工具选择策略（参数优先，否则使用默认配置）
        effective_tool_choice: Union[str, dict] = tool_choice if tool_choice is not None else self.default_tool_choice

        current_iteration = 0  # 当前迭代次数
        final_response = ""    # 最终回答

        # ========== 第四步：工具调用循环 ==========
        while current_iteration < iterations_limit:
            # 4.1 调用 OpenAI API（带工具定义）
            response = self._invoke_with_tools(
                messages,
                tools=tool_schemas,
                tool_choice=effective_tool_choice,
                **kwargs,
            )

            # 4.2 提取响应内容
            choice = response.choices[0]
            assistant_message = choice.message
            content = self._extract_message_content(assistant_message.content)  # 提取文本内容
            tool_calls = list(assistant_message.tool_calls or [])  # 提取工具调用列表

            # 4.3 如果 LLM 决定调用工具
            if tool_calls:
                # 4.3.1 构建 assistant 消息（包含工具调用请求）
                # 这是 OpenAI Function Calling 的标准格式
                assistant_payload: dict[str, Any] = {"role": "assistant", "content": content}
                assistant_payload["tool_calls"] = []

                # 将每个工具调用转换为标准格式
                for tool_call in tool_calls:
                    assistant_payload["tool_calls"].append(
                        {
                            "id": tool_call.id,              # 工具调用的唯一 ID
                            "type": tool_call.type,          # 类型（通常是 "function"）
                            "function": {
                                "name": tool_call.function.name,           # 工具名称
                                "arguments": tool_call.function.arguments, # JSON 字符串参数
                            },
                        }
                    )
                # 将 assistant 的工具调用请求添加到消息历史
                messages.append(assistant_payload)

                # 4.3.2 执行所有工具调用
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    # 解析 JSON 字符串参数为字典
                    arguments = self._parse_function_call_arguments(tool_call.function.arguments)
                    # 执行工具并获取结果
                    result = self._execute_tool_call(tool_name, arguments)
                    
                    # 将工具执行结果添加到消息历史
                    # 这是 OpenAI Function Calling 的标准格式
                    messages.append(
                        {
                            "role": "tool",                  # 角色：工具
                            "tool_call_id": tool_call.id,    # 对应的工具调用 ID
                            "name": tool_name,               # 工具名称
                            "content": result,               # 工具执行结果
                        }
                    )

                # 4.3.3 增加迭代计数，继续下一轮循环
                # 下一轮会将工具结果发送给 LLM，让它基于结果生成回答
                current_iteration += 1
                continue

            # 4.4 如果 LLM 没有调用工具，说明这是最终回答
            final_response = content
            messages.append({"role": "assistant", "content": final_response})
            break  # 跳出循环

        # ========== 第五步：处理超出迭代次数的情况 ==========
        # 如果达到最大迭代次数仍未得到最终回答
        if current_iteration >= iterations_limit and not final_response:
            # 强制 LLM 生成文本回答（禁用工具调用）
            final_choice = self._invoke_with_tools(
                messages,
                tools=tool_schemas,
                tool_choice="none",  # 禁用工具调用
                **kwargs,
            )
            final_response = self._extract_message_content(final_choice.choices[0].message.content)
            messages.append({"role": "assistant", "content": final_response})

        # ========== 第六步：保存对话历史并返回 ==========
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_response, "assistant"))
        return final_response

    def add_tool(self, tool) -> None:
        """便捷方法：将工具注册到当前Agent"""
        if not self.tool_registry:
            from ..tools.registry import ToolRegistry

            self.tool_registry = ToolRegistry()
            self.enable_tool_calling = True

        if hasattr(tool, "auto_expand") and getattr(tool, "auto_expand"):
            expanded_tools = tool.get_expanded_tools()
            if expanded_tools:
                for expanded_tool in expanded_tools:
                    self.tool_registry.register_tool(expanded_tool)
                print(f"✅ MCP工具 '{tool.name}' 已展开为 {len(expanded_tools)} 个独立工具")
                return

        self.tool_registry.register_tool(tool)

    def remove_tool(self, tool_name: str) -> bool:
        if self.tool_registry:
            before = set(self.tool_registry.list_tools())
            self.tool_registry.unregister(tool_name)
            after = set(self.tool_registry.list_tools())
            return tool_name in before and tool_name not in after
        return False

    def list_tools(self) -> list[str]:
        if self.tool_registry:
            return self.tool_registry.list_tools()
        return []

    def has_tools(self) -> bool:
        return self.enable_tool_calling and self.tool_registry is not None

    def stream_run(self, input_text: str, **kwargs) -> Iterator[str]:
        """流式调用暂未实现，直接回退到一次性调用"""
        result = self.run(input_text, **kwargs)
        yield result
