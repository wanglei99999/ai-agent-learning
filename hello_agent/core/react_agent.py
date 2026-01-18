class ReactAgent:
    def __init__(self,llm_client:HelloAgentsLLM, tool_executor: ToolExecutor,max_step: int=5):
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_step = max_step
        self.history = []

    def run(self,question:str):
        """
        运行ReAct智能体来回答问题
        """
        self.history=[]
        current_step = 0

        while current_step<self.max_step:
            current_step+=1
            print(f"---第{current_step}步---")

            #1.格式化提示词
            tool_desc = self.tool_executor.get_available_tools()
            history_str = '\n'+join(self.history)
            promt = REACT_PROMPT_TEMPLATE.format(
                tools = tool_desc,
                question = question,
                history = history_str
            )
            #2.调用LLM进行思考
            messages = [{"role":"user","content":promt}]
            response_text = self.llm_client.think(messages = messages)

            if not response_text:
                print("错误：LLM未能返回有效响应")

            #3.解析LLM的输出
            though,action = self._parse_output(response_text)

            if(though):
                print(f"思考：{though}")
            if not action:
                print("警告：未能解析出有效的Action，流程终止")
                break

            #4.执行Action
            if action.startswith('Finish'):
                #如果是Finish之类，提取最终答案并结束
                final_answer = re.match(r"Finish\[(.*)\]",action).group(1)
                print(f"最终答案：{final_answer}")
                return final_answer

            tool_name, tool_input = self._parse_action(action)
            if not tool_name or not tool_input:
                #处理无效的Action格式...
                continue
            print(f"行动:{action_name}[{action_input}]")

            tool_function = self.tool_executor.get_tool(tool_name)
            if not tool_function:
                observation = f"错误：未找到名为：{tool_name}的工具"
            else:
                observation = tool_function(tool_input)
                print(f"观察：{observation}")
                self.history.append(f"Action:{action}")
                self.history.append(f"Observation:{observation}")
        print("已达到最大步数，流程终止")
        return None


    def _parse_output(self,text:str):
        """
        解析LLM的输出，提取thought和Action。
        """
        thought_match = re.search(r"Thought:(.*)",text)
        action_match = re.search(r"Action:(.*)",text)
        thought = thought_match.group(1) if thought_match else None
        action = action_match.group(1) if action_match else None

        return thought,action

    def _parse_action(self,action_text:str):
        """
        解析Action字符串，提取工具名称和输入。
        """
        match = re.match(r"(\w+)\[(.*)\]",action_text)
        if match:
            return match.group(1),match.group(2)
        return None,None