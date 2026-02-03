"""NoteTool - 结构化笔记工具

为Agent提供结构化笔记能力，支持：
- 创建/读取/更新/删除笔记
- 按类型组织（任务状态、结论、阻塞项、行动计划等）
- 持久化存储（Markdown格式，带YAML前置元数据）
- 搜索与过滤
- 与MemoryTool集成（可选）

使用场景：
- 长时程任务的状态跟踪
- 关键结论与依赖记录
- 待办事项与行动计划
- 项目知识沉淀

笔记格式示例：
```markdown
---
id: note_20250118_120000_0
title: 项目进展
type: task_state
tags: [milestone, phase1]
created_at: 2025-01-18T12:00:00
updated_at: 2025-01-18T12:00:00
---

# 项目进展

已完成需求分析，下一步：设计方案

## 关键里程碑
- [x] 需求收集
- [ ] 方案设计
```
"""

# ============================================================================
# 导入依赖
# ============================================================================
from typing import Dict, Any, List  # 类型注解，提高代码可读性
from datetime import datetime        # 时间处理，用于生成时间戳
from pathlib import Path             # 路径处理，比 os.path 更现代化
import json                          # JSON 序列化，用于索引文件
import re                            # 正则表达式，用于解析 Markdown

# 从基类导入 Tool 框架组件
# - Tool: 工具基类，定义了工具的基本接口
# - ToolParameter: 参数定义类，描述工具接受的参数
# - tool_action: 装饰器，用于标记可展开的工具动作
from ..base import Tool, ToolParameter, tool_action


# ============================================================================
# NoteTool 类 - 核心实现
# ============================================================================
# 设计模式：这是一个典型的「工具类」设计
# - 继承自 Tool 基类，遵循统一的工具接口规范
# - 使用「命令模式」：通过 action 参数决定执行哪个操作
# - 使用「策略模式」：不同的 action 对应不同的处理策略
# ============================================================================

class NoteTool(Tool):
    """笔记工具
    
    为Agent提供结构化笔记管理能力，支持多种笔记类型：
    - task_state: 任务状态
    - conclusion: 关键结论
    - blocker: 阻塞项
    - action: 行动计划
    - reference: 参考资料
    - general: 通用笔记
    
    用法示例：
    ```python
    note_tool = NoteTool(workspace="./project_notes")
    
    # 创建笔记
    note_tool.run({
        "action": "create",
        "title": "项目进展",
        "content": "已完成需求分析，下一步：设计方案",
        "note_type": "task_state",
        "tags": ["milestone", "phase1"]
    })
    
    # 读取笔记
    notes = note_tool.run({"action": "list", "note_type": "task_state"})
    ```
    """
    
    # ------------------------------------------------------------------------
    # 构造函数 - 初始化工具
    # ------------------------------------------------------------------------
    # 学习要点：
    # 1. 使用默认参数提供合理的默认配置
    # 2. 调用父类 __init__ 注册工具元信息
    # 3. 初始化时确保必要的目录和文件存在
    # ------------------------------------------------------------------------
    def __init__(
        self,
        workspace: str = "./notes",    # 笔记存储目录，默认为当前目录下的 notes 文件夹
        auto_backup: bool = True,       # 是否自动备份（预留功能）
        max_notes: int = 1000,          # 最大笔记数量限制，防止无限增长
        expandable: bool = False        # 是否支持展开模式（将工具拆分为多个子动作）
    ):
        # 调用父类构造函数，注册工具的基本信息
        # name: 工具名称，Agent 通过这个名称调用工具
        # description: 工具描述，帮助 Agent 理解工具的用途
        super().__init__(
            name="note",
            description="笔记工具 - 创建、读取、更新、删除结构化笔记，支持任务状态、结论、阻塞项等类型",
            expandable=expandable
        )
        
        # 使用 Path 对象处理路径，比字符串更安全、更方便
        self.workspace = Path(workspace)
        self.auto_backup = auto_backup
        self.max_notes = max_notes
        
        # 确保工作目录存在
        # parents=True: 如果父目录不存在，一并创建
        # exist_ok=True: 如果目录已存在，不报错
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # 笔记索引文件 - 存储所有笔记的元数据，便于快速检索
        # 这是一种常见的「索引分离」设计模式：
        # - 索引文件(JSON)：存储元数据，体积小，加载快
        # - 内容文件(Markdown)：存储完整内容，独立管理
        self.index_file = self.workspace / "notes_index.json"
        self._load_index()  # 加载索引到内存
    
    # ------------------------------------------------------------------------
    # 索引管理方法 - 私有方法（以 _ 开头）
    # ------------------------------------------------------------------------
    # 学习要点：索引是提高检索效率的关键设计
    # - 避免每次操作都遍历所有文件
    # - 索引与数据分离，各司其职
    # ------------------------------------------------------------------------
    
    def _load_index(self):
        """加载笔记索引
        
        从磁盘加载索引文件到内存。如果索引文件不存在，
        则创建一个空的索引结构。
        """
        if self.index_file.exists():
            # 读取已有的索引文件
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self.notes_index = json.load(f)
        else:
            # 初始化空索引结构
            # 设计说明：索引结构包含两部分
            # - notes: 笔记列表（只存储元数据，不存储内容）
            # - metadata: 索引自身的元数据
            self.notes_index = {
                "notes": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),  # ISO 8601 格式时间
                    "total_notes": 0
                }
            }
            self._save_index()  # 立即保存到磁盘
    
    def _save_index(self):
        """保存笔记索引到磁盘
        
        将内存中的索引数据持久化到 JSON 文件。
        - ensure_ascii=False: 保留中文字符，不转义为 Unicode
        - indent=2: 格式化输出，便于人工查看和调试
        """
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.notes_index, f, ensure_ascii=False, indent=2)
    
    def _generate_note_id(self) -> str:
        """生成唯一的笔记ID
        
        ID 格式: note_{时间戳}_{序号}
        例如: note_20250118_120000_5
        
        设计说明：
        - 时间戳保证大致唯一性
        - 序号进一步避免同一秒内创建多个笔记时的冲突
        - 可读性好，便于调试
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 格式: 年月日_时分秒
        count = len(self.notes_index["notes"])  # 当前笔记总数作为序号
        return f"note_{timestamp}_{count}"
    
    def _get_note_path(self, note_id: str) -> Path:
        """根据笔记ID获取对应的文件路径
        
        每个笔记存储为独立的 Markdown 文件，文件名即笔记ID。
        例如: ./notes/note_20250118_120000_5.md
        """
        return self.workspace / f"{note_id}.md"
    
    # ------------------------------------------------------------------------
    # Markdown 序列化/反序列化方法
    # ------------------------------------------------------------------------
    # 学习要点：YAML Frontmatter 是一种常见的文档格式
    # - 广泛用于静态网站生成器（Jekyll, Hugo 等）
    # - 将元数据与内容分离，结构清晰
    # - 格式：文件开头用 --- 包裹的 YAML 块
    # ------------------------------------------------------------------------
    
    def _note_to_markdown(self, note: Dict[str, Any]) -> str:
        """将笔记对象（字典）序列化为 Markdown 文本
        
        输出格式示例：
        ---
        id: note_20250118_120000_0
        title: 项目进展
        type: task_state
        tags: ["milestone", "phase1"]
        created_at: 2025-01-18T12:00:00
        updated_at: 2025-01-18T12:00:00
        ---
        
        # 项目进展
        
        笔记内容...
        """
        # 第一部分：YAML 前置元数据（Frontmatter）
        frontmatter = "---\n"  # YAML 块开始标记
        frontmatter += f"id: {note['id']}\n"
        frontmatter += f"title: {note['title']}\n"
        frontmatter += f"type: {note['type']}\n"
        if note.get('tags'):  # 只有有标签时才写入
            tags_str = json.dumps(note['tags'])  # 将列表转为 JSON 字符串
            frontmatter += f"tags: {tags_str}\n"
        frontmatter += f"created_at: {note['created_at']}\n"
        frontmatter += f"updated_at: {note['updated_at']}\n"
        frontmatter += "---\n\n"  # YAML 块结束标记
        
        # 第二部分：Markdown 正文内容
        content = f"# {note['title']}\n\n"  # 一级标题
        content += note['content']  # 笔记正文
        
        return frontmatter + content
    
    def _markdown_to_note(self, markdown_text: str) -> Dict[str, Any]:
        """将 Markdown 文本反序列化为笔记对象（字典）
        
        这是 _note_to_markdown 的逆操作，负责解析文件内容。
        
        解析步骤：
        1. 用正则表达式提取 YAML Frontmatter
        2. 逐行解析 YAML 键值对
        3. 提取 Markdown 正文内容
        """
        # 第一步：用正则表达式匹配 YAML Frontmatter
        # 正则解释：
        # ^---\s*\n  : 文件开头的 --- 加换行
        # (.*?)      : 非贪婪匹配任意内容（YAML 内容）
        # \n---\s*\n : 结束的 --- 加换行
        # re.DOTALL  : 让 . 也能匹配换行符
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', markdown_text, re.DOTALL)
        
        if not frontmatter_match:
            raise ValueError("无效的笔记格式：缺少YAML前置元数据")
        
        frontmatter_text = frontmatter_match.group(1)  # 提取 YAML 文本
        content_start = frontmatter_match.end()         # 正文开始位置
        
        # 第二步：解析 YAML（简化版，只支持简单键值对）
        # 注意：这不是完整的 YAML 解析器，复杂场景应使用 PyYAML 库
        note = {}
        for line in frontmatter_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)  # 只分割第一个冒号
                key = key.strip()    # 去除首尾空白
                value = value.strip()
                
                # 特殊处理 tags 字段（JSON 数组）
                if key == 'tags':
                    try:
                        note[key] = json.loads(value)  # 解析 JSON 数组
                    except (json.JSONDecodeError, ValueError):
                        note[key] = []  # 解析失败则返回空列表
                else:
                    note[key] = value
        
        # 第三步：提取正文内容
        markdown_content = markdown_text[content_start:].strip()
        # 移除第一行的 # 标题（因为标题已在 frontmatter 中）
        lines = markdown_content.split('\n')
        if lines and lines[0].startswith('# '):
            markdown_content = '\n'.join(lines[1:]).strip()
        
        note['content'] = markdown_content
        
        # 添加运行时元数据（不持久化）
        note['metadata'] = {
            'word_count': len(markdown_content),
            'status': 'active'
        }
        
        return note
    
    # ------------------------------------------------------------------------
    # run 方法 - 工具的核心入口点
    # ------------------------------------------------------------------------
    # 学习要点：这是「命令模式」的典型实现
    # - 所有操作都通过统一的 run() 入口
    # - 通过 action 参数路由到具体的处理方法
    # - 优点：接口统一，易于扩展，便于 Agent 调用
    # ------------------------------------------------------------------------
    
    def run(self, parameters: Dict[str, Any]) -> str:
        """执行工具（非展开模式）
        
        这是 Agent 调用工具的入口方法。根据 action 参数
        分发到对应的具体方法执行。
        
        Args:
            parameters: 包含 action 和其他参数的字典
            
        Returns:
            操作结果的字符串描述
        """
        # 参数验证（由基类提供）
        if not self.validate_parameters(parameters):
            return "参数验证失败"

        action = parameters.get("action")

        # 命令路由：根据 action 调用对应的方法
        # 这是一种简单的路由实现，更复杂的场景可以用字典映射
        if action == "create":
            return self._create_note(
                title=parameters.get("title"),
                content=parameters.get("content"),
                note_type=parameters.get("note_type", "general"),
                tags=parameters.get("tags")
            )
        elif action == "read":
            return self._read_note(note_id=parameters.get("note_id"))
        elif action == "update":
            return self._update_note(
                note_id=parameters.get("note_id"),
                title=parameters.get("title"),
                content=parameters.get("content"),
                note_type=parameters.get("note_type"),
                tags=parameters.get("tags")
            )
        elif action == "delete":
            return self._delete_note(note_id=parameters.get("note_id"))
        elif action == "list":
            return self._list_notes(
                note_type=parameters.get("note_type"),
                limit=parameters.get("limit", 10)
            )
        elif action == "search":
            return self._search_notes(
                query=parameters.get("query"),
                limit=parameters.get("limit", 10)
            )
        elif action == "summary":
            return self._get_summary()
        else:
            return f"不支持的操作: {action}"
    
    # ------------------------------------------------------------------------
    # get_parameters 方法 - 定义工具的参数规范
    # ------------------------------------------------------------------------
    # 学习要点：这是工具「自描述」能力的关键
    # - Agent 通过此方法了解工具需要哪些参数
    # - 参数定义会被转换为 LLM 能理解的 schema
    # - 类似于 OpenAPI/Swagger 的参数描述
    # ------------------------------------------------------------------------
    
    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义
        
        返回工具接受的所有参数的定义，包括：
        - name: 参数名
        - type: 参数类型
        - description: 参数描述（帮助 LLM 理解如何使用）
        - required: 是否必需
        - default: 默认值
        """
        return [
            ToolParameter(
                name="action",
                type="string",
                description=(
                    "操作类型: create(创建), read(读取), update(更新), "
                    "delete(删除), list(列表), search(搜索), summary(摘要)"
                ),
                required=True
            ),
            ToolParameter(
                name="title",
                type="string",
                description="笔记标题（create/update时必需）",
                required=False
            ),
            ToolParameter(
                name="content",
                type="string",
                description="笔记内容（create/update时必需）",
                required=False
            ),
            ToolParameter(
                name="note_type",
                type="string",
                description=(
                    "笔记类型: task_state(任务状态), conclusion(结论), "
                    "blocker(阻塞项), action(行动计划), reference(参考), general(通用)"
                ),
                required=False,
                default="general"
            ),
            ToolParameter(
                name="tags",
                type="array",
                description="标签列表（可选）",
                required=False
            ),
            ToolParameter(
                name="note_id",
                type="string",
                description="笔记ID（read/update/delete时必需）",
                required=False
            ),
            ToolParameter(
                name="query",
                type="string",
                description="搜索关键词（search时必需）",
                required=False
            ),
            ToolParameter(
                name="limit",
                type="integer",
                description="返回结果数量限制（默认10）",
                required=False,
                default=10
            ),
        ]
    
    # ------------------------------------------------------------------------
    # CRUD 操作方法 - 笔记的增删改查
    # ------------------------------------------------------------------------
    # 学习要点：
    # 1. @tool_action 装饰器：将方法注册为独立的子工具（展开模式）
    # 2. 私有方法（_ 开头）：表示这些方法不应被外部直接调用
    # 3. 每个方法都返回格式化的字符串结果，便于 Agent 理解
    # ------------------------------------------------------------------------
    
    @tool_action("note_create", "创建一条新的结构化笔记")
    # ↑ 装饰器：当 expandable=True 时，此方法会被暴露为独立工具 "note_create"
    def _create_note(self, title: str, content: str, note_type: str = "general", tags: List[str] = None) -> str:
        """创建笔记

        Args:
            title: 笔记标题
            content: 笔记内容
            note_type: 笔记类型 (task_state, conclusion, blocker, action, reference, general)
            tags: 标签列表

        Returns:
            创建结果
        """
        # === 参数校验 ===
        if not title or not content:
            return "创建笔记需要提供 title 和 content"
        
        # 检查笔记数量限制（防止存储无限增长）
        if len(self.notes_index["notes"]) >= self.max_notes:
            return f"笔记数量已达上限 ({self.max_notes})"
        
        # === 生成笔记 ===
        note_id = self._generate_note_id()  # 生成唯一ID
        
        # 构建笔记数据结构
        note = {
            "id": note_id,
            "title": title,
            "content": content,
            "type": note_type,
            "tags": tags if isinstance(tags, list) else [],  # 确保 tags 是列表
            "created_at": datetime.now().isoformat(),  # ISO 8601 时间格式
            "updated_at": datetime.now().isoformat(),
            "metadata": {
                "word_count": len(content),  # 字数统计
                "status": "active"           # 状态标记
            }
        }
        
        # === 持久化存储 ===
        # 1. 保存笔记文件（Markdown 格式，便于人工阅读和编辑）
        note_path = self._get_note_path(note_id)
        markdown_content = self._note_to_markdown(note)
        with open(note_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # 2. 更新索引（只存储元数据，不存储内容，保持索引轻量）
        self.notes_index["notes"].append({
            "id": note_id,
            "title": title,
            "type": note_type,
            "tags": tags if isinstance(tags, list) else [],
            "created_at": note["created_at"]
        })
        self.notes_index["metadata"]["total_notes"] = len(self.notes_index["notes"])
        self._save_index()  # 持久化索引
        
        # 返回友好的操作结果
        return f"笔记创建成功\nID: {note_id}\n标题: {title}\n类型: {note_type}"
    
    # ------------------------------------------------------------------------
    # _read_note - 读取笔记
    # ------------------------------------------------------------------------
    # 这是 _create_note 的逆操作：
    # - create: Dict --> Markdown 文件 (序列化)
    # - read:   Markdown 文件 --> Dict (反序列化)
    # 
    # 注意：读取操作不需要更新索引，因为数据没有变化
    # ------------------------------------------------------------------------
    
    @tool_action("note_read", "读取指定ID的笔记")
    def _read_note(self, note_id: str) -> str:
        """读取笔记
        
        根据笔记ID读取对应的 Markdown 文件，解析后返回格式化的内容。
        
        处理流程：
        1. 参数校验 - 确保提供了 note_id
        2. 文件检查 - 确保笔记文件存在
        3. 读取文件 - 加载 Markdown 文本
        4. 解析内容 - Markdown 转为 Python 字典
        5. 格式化输出 - 转为 Agent 易读的字符串

        Args:
            note_id: 笔记ID，例如 "note_20250118_120000_0"

        Returns:
            格式化的笔记内容字符串，包含标题、类型、标签、正文等
        """
        # === 第一步：参数校验 ===
        # 防御性编程：确保调用方提供了必要的参数
        if not note_id:
            return "读取笔记需要提供 note_id"
        
        # === 第二步：检查文件是否存在 ===
        # _get_note_path() 根据 ID 拼接文件路径，例如：./notes/note_xxx.md
        note_path = self._get_note_path(note_id)
        
        # Path.exists() 检查文件是否存在，避免后续读取时抛出异常
        if not note_path.exists():
            return f"笔记不存在: {note_id}"
        
        # === 第三步：读取 Markdown 文件内容 ===
        # 使用 utf-8 编码确保中文正常读取
        with open(note_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
        
        # === 第四步：解析 Markdown 为 Python 字典 ===
        # _markdown_to_note() 会：
        # 1. 用正则提取 YAML frontmatter（元数据）
        # 2. 逐行解析 YAML 键值对
        # 3. 提取正文内容
        # 返回结构示例：
        # {
        #     "id": "note_xxx",
        #     "title": "笔记标题",
        #     "type": "task_state",
        #     "content": "笔记正文...",
        #     "tags": ["tag1", "tag2"],
        #     ...
        # }
        note = self._markdown_to_note(markdown_text)
        
        # === 第五步：格式化输出 ===
        # _format_note() 将字典转为人类可读的字符串格式
        # 这是给 Agent 看的结果，不是原始数据
        return self._format_note(note)
    
    # ------------------------------------------------------------------------
    # _update_note - 更新笔记
    # ------------------------------------------------------------------------
    # 这是一个典型的「读取-修改-写回」(Read-Modify-Write) 模式：
    # 1. 先读取现有数据
    # 2. 在内存中修改
    # 3. 写回存储
    # 
    # 设计要点：
    # - 支持部分更新：只传需要改的字段，其他保持不变
    # - 需要同时更新：内容文件(.md) 和 索引文件(.json)
    # ------------------------------------------------------------------------
    
    @tool_action("note_update", "更新已存在的笔记")
    def _update_note(self, note_id: str, title: str = None, content: str = None, note_type: str = None, tags: List[str] = None) -> str:
        """更新笔记
        
        支持部分更新，只需要传入要修改的字段。
        
        处理流程：
        1. 参数校验 - 确保提供了 note_id
        2. 读取现有笔记 - 获取当前完整数据
        3. 合并更新 - 用新值覆盖旧值（只覆盖传入的字段）
        4. 保存文件 - 写回 Markdown 文件
        5. 更新索引 - 同步更新索引中的元数据

        Args:
            note_id: 笔记ID（必需）
            title: 新标题（可选，不传则保持原值）
            content: 新内容（可选，不传则保持原值）
            note_type: 新类型（可选，不传则保持原值）
            tags: 新标签列表（可选，不传则保持原值）

        Returns:
            更新结果
        """
        # === 第一步：参数校验 ===
        if not note_id:
            return "更新笔记需要提供 note_id"
        
        # === 第二步：检查笔记是否存在 ===
        note_path = self._get_note_path(note_id)
        if not note_path.exists():
            return f"笔记不存在: {note_id}"
        
        # === 第三步：读取现有笔记（复用 read 的逻辑）===
        # 这就是「读取-修改-写回」模式的第一步：读取
        with open(note_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
        note = self._markdown_to_note(markdown_text)

        # === 第四步：合并更新（部分更新模式）===
        # 关键设计：只更新传入的字段，未传入的保持原值
        # 这样调用方可以只传需要改的字段，而不是每次都传完整数据
        # 
        # 例如：只改标题
        # _update_note(note_id="xxx", title="新标题")
        # 其他字段（content, type, tags）保持不变
        
        if title:  # 如果传入了 title，则更新
            note["title"] = title
        if content:  # 如果传入了 content，则更新
            note["content"] = content
            # 同时更新字数统计（派生数据要保持同步）
            note["metadata"]["word_count"] = len(content)
        if note_type:  # 如果传入了 note_type，则更新
            note["type"] = note_type
        if tags is not None:  # 注意：这里用 is not None 而不是 if tags
            # 原因：空列表 [] 也是有效值（表示清空标签）
            # if tags 会把 [] 当作 False，导致无法清空标签
            note["tags"] = tags if isinstance(tags, list) else []
        
        # 无论改了什么，都更新修改时间
        note["updated_at"] = datetime.now().isoformat()
        
        # === 第五步：保存更新到文件（复用 create 的逻辑）===
        # 这就是「读取-修改-写回」模式的第三步：写回
        markdown_content = self._note_to_markdown(note)
        with open(note_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # === 第六步：同步更新索引 ===
        # 索引中也存了 title, type, tags，需要保持一致
        # 遍历索引找到对应的笔记，更新其元数据
        for idx_note in self.notes_index["notes"]:
            if idx_note["id"] == note_id:
                idx_note["title"] = note["title"]
                idx_note["type"] = note["type"]
                idx_note["tags"] = note["tags"]
                break  # 找到后立即退出循环，提高效率
        self._save_index()  # 持久化索引
        
        return f"笔记更新成功: {note_id}"
    
    @tool_action("note_delete", "删除指定ID的笔记")
    def _delete_note(self, note_id: str) -> str:
        """删除笔记

        Args:
            note_id: 笔记ID

        Returns:
            删除结果
        """
        if not note_id:
            return "删除笔记需要提供 note_id"
        
        note_path = self._get_note_path(note_id)
        if not note_path.exists():
            return f"笔记不存在: {note_id}"
        
        # 删除文件
        note_path.unlink()
        
        # 更新索引
        self.notes_index["notes"] = [
            n for n in self.notes_index["notes"] if n["id"] != note_id
        ]
        self.notes_index["metadata"]["total_notes"] = len(self.notes_index["notes"])
        self._save_index()
        
        return f"笔记已删除: {note_id}"
    
    @tool_action("note_list", "列出所有笔记或指定类型的笔记")
    def _list_notes(self, note_type: str = None, limit: int = 10) -> str:
        """列出笔记

        Args:
            note_type: 笔记类型过滤（可选）
            limit: 返回结果数量限制

        Returns:
            笔记列表
        """
        # 过滤笔记
        filtered_notes = self.notes_index["notes"]
        if note_type:
            filtered_notes = [n for n in filtered_notes if n["type"] == note_type]
        
        # 限制数量
        filtered_notes = filtered_notes[:limit]
        
        if not filtered_notes:
            return "暂无笔记"
        
        result = f"笔记列表（共 {len(filtered_notes)} 条）\n\n"
        for note in filtered_notes:
            result += f"- [{note['type']}] {note['title']}\n"
            result += f"  ID: {note['id']}\n"
            if note.get('tags'):
                result += f"  标签: {', '.join(note['tags'])}\n"
            result += f"  创建时间: {note['created_at']}\n\n"
        
        return result
    
    @tool_action("note_search", "搜索包含关键词的笔记")
    def _search_notes(self, query: str, limit: int = 10) -> str:
        """搜索笔记
        
        全文搜索实现：遍历所有笔记，匹配标题、内容和标签。
        
        注意：这是简单的线性搜索，适合小规模数据。
        大规模场景应考虑：
        - 使用全文搜索引擎（如 Elasticsearch）
        - 建立倒排索引
        - 使用向量数据库做语义搜索

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            搜索结果
        """
        if not query:
            return "搜索需要提供 query"

        query_lower = query.lower()  # 转小写，实现大小写不敏感搜索
        
        # 遍历索引，逐个检查笔记内容
        matched_notes = []
        for idx_note in self.notes_index["notes"]:
            note_path = self._get_note_path(idx_note["id"])
            if note_path.exists():
                # 读取笔记文件
                with open(note_path, 'r', encoding='utf-8') as f:
                    markdown_text = f.read()
                
                try:
                    note = self._markdown_to_note(markdown_text)
                except Exception as e:
                    print(f"解析笔记失败 {idx_note['id']}: {e}")
                    continue
                
                # 多字段匹配：标题 OR 内容 OR 标签
                if (query_lower in note["title"].lower() or
                    query_lower in note["content"].lower() or
                    any(query_lower in tag.lower() for tag in note.get("tags", []))):
                    matched_notes.append(note)
        
        # 限制返回数量
        matched_notes = matched_notes[:limit]
        
        if not matched_notes:
            return f"未找到匹配 '{query}' 的笔记"
        
        # 格式化输出结果
        result = f"搜索结果（共 {len(matched_notes)} 条）\n\n"
        for note in matched_notes:
            result += self._format_note(note, compact=True) + "\n"
        
        return result
    
    @tool_action("note_summary", "获取笔记系统的摘要统计信息")
    def _get_summary(self) -> str:
        """获取笔记摘要

        Returns:
            摘要信息
        """
        total = len(self.notes_index["notes"])
        
        # 按类型统计
        type_counts = {}
        for note in self.notes_index["notes"]:
            note_type = note["type"]
            type_counts[note_type] = type_counts.get(note_type, 0) + 1
        
        result = f"笔记摘要\n\n"
        result += f"总笔记数: {total}\n\n"
        result += "按类型统计:\n"
        for note_type, count in sorted(type_counts.items()):
            result += f"  - {note_type}: {count}\n"
        
        return result
    
    # ------------------------------------------------------------------------
    # 辅助方法 - 格式化输出
    # ------------------------------------------------------------------------
    
    def _format_note(self, note: Dict[str, Any], compact: bool = False) -> str:
        """格式化笔记输出
        
        提供两种输出模式：
        - compact=False: 详细模式，显示所有字段
        - compact=True: 紧凑模式，只显示摘要（用于列表展示）
        """
        if compact:
            return (
                f"[{note['type']}] {note['title']}\n"
                f"ID: {note['id']}\n"
                f"内容: {note['content'][:100]}{'...' if len(note['content']) > 100 else ''}"
            )
        else:
            result = f"笔记详情\n\n"
            result += f"ID: {note['id']}\n"
            result += f"标题: {note['title']}\n"
            result += f"类型: {note['type']}\n"
            if note.get('tags'):
                result += f"标签: {', '.join(note['tags'])}\n"
            result += f"创建时间: {note['created_at']}\n"
            result += f"更新时间: {note['updated_at']}\n"
            result += f"\n内容:\n{note['content']}\n"
            return result
