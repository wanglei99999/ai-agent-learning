from typing import Dict,List,Any,Optional

class Memory:
    """
    一个简单的短期记忆力模块，用于存储智能体的行动与反思轨迹。
    """
    def __init__(self):
        """
        初始化一个空列表来存储所有记录
        """
        self.records: List[Dict[str,Any]] = []

    def add_record(self,record_type:str,content:str):
        """
        向记忆中添加一条记录。

        参数：
        - record_type(str): 记录的类型
        - content(str): 记录的具体内容
        """

        record = {"type":record_type,"content":content}
        self.records.append(record)
        print(f"记忆已更新，新增一条'{record_type}'记录")
    def get_trajectory(self)->str:
        """
        将所有记忆记录格式化为一个连贯的字符串文本，用于构建提示词。
        """
        if not self.records:
            return "暂无历史记录"
        trajectory_parts = []
        for record in self.records:
            if record['type'] == 'execution':
                # 执行记录：Agent 尝试的代码或行动
                trajectory_parts.append(f"---上一轮尝试(代码)---\n{record['content']}")
            elif record['type'] =='reflection':
                # 反思记录：评审员的反馈
                trajectory_parts.append(f"--- 评审员反馈 ---\n{record['content']}")
        return '\n\n'.join(trajectory_parts)

    def get_last_execution(self)->Optional[str]:
        """
        获取最近一次的执行结果
        如果不存在，则返回None
        """
        for record in reversed(self.records):
            if record['type']=='execution':
                return record['content']
        return None
