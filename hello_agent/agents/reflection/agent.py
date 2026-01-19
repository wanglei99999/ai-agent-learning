from hello_agent.agents.reflection.memory import Memory
from hello_agent.agents.reflection.prompt import INITIAL_PROMPT_TEMPLATE, REFLECTION_PROMPT_TEMPLATE


class ReflectionAgent:
    """
    Reflection Agent: 通过自我反思和迭代优化来改进代码质量
    """
    
    def __init__(self, llm_client, max_iterations=3):
        """
        初始化 Reflection Agent
        
        参数:
        - llm_client: LLM 客户端实例
        - max_iterations: 最大迭代次数
        """
        self.llm_client = llm_client
        self.memory = Memory()
        self.max_iterations = max_iterations
    
    def run(self, task: str):
        """
        执行任务的主流程
        
        参数:
        - task: 任务描述
        
        返回:
        - 最终生成的代码
        """
        print(f"\n--- 开始处理任务 ---\n任务: {task}")
        
        # --- 1. 初始执行 ---
        print("\n--- 正在进行初始尝试 ---")
        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(task=task)
        initial_code = self._get_llm_response(initial_prompt)
        self.memory.add_record("execution", initial_code)
        print(f"初始代码:\n{initial_code}")
        
        # --- 2. 迭代循环: 反思与优化 ---
        for i in range(self.max_iterations):
            print(f"\n--- 第 {i+1}/{self.max_iterations} 轮迭代 ---")
            
            # a. 反思
            print("\n-> 正在进行反思...")
            last_code = self.memory.get_last_execution()
            reflect_prompt = REFLECTION_PROMPT_TEMPLATE.format(task=task, code=last_code)
            feedback = self._get_llm_response(reflect_prompt)
            self.memory.add_record("reflection", feedback)
            print(f"反馈: {feedback}")
            
            # b. 检查是否需要停止
            if "无需改进" in feedback:
                print("\n✅ 反思认为代码已无需改进，任务完成。")
                break
            
            # c. 优化
            print("\n-> 正在进行优化...")
            # 构建优化提示词，包含历史轨迹
            trajectory = self.memory.get_trajectory()
            refine_prompt = f"""
你是一位资深的 Python 程序员。

## 原始任务
{task}

## 历史记录
{trajectory}

## 要求
请根据评审员的反馈，生成改进后的代码。代码必须包含完整的函数签名、文档字符串，并遵守 PEP 8 编码规范。

请直接输出代码，不要包含任何额外的解释。
"""
            refined_code = self._get_llm_response(refine_prompt)
            self.memory.add_record("execution", refined_code)
            print(f"优化后代码:\n{refined_code}")
        
        # --- 3. 返回最终结果 ---
        final_code = self.memory.get_last_execution()
        print(f"\n--- 任务完成 ---\n最终生成的代码:\n```python\n{final_code}\n```")
        return final_code
    
    def _get_llm_response(self, prompt: str) -> str:
        """
        一个辅助方法，用于调用 LLM 并获取完整的响应。
        
        参数:
        - prompt: 提示词
        
        返回:
        - LLM 的响应文本
        """
        messages = [{"role": "user", "content": prompt}]
        response_text = self.llm_client.think(messages=messages) or ""
        return response_text
