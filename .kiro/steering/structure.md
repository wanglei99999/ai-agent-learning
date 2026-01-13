# Project Structure

```
├── langchain/                  # LangChain 学习笔记
│   ├── 01-环境搭建.md          # 基础篇开始
│   ├── ...                     # 按编号递增的章节文档
│   ├── 19-Deep Research实践.md # 最后章节
│   ├── data/                   # 示例数据文件 (CSV等)
│   └── examples/               # Python 示例代码
│       ├── ex01_*.py           # 按编号命名的示例
│       └── ex*.ipynb           # Jupyter Notebook 示例
│
├── langgraph/                  # LangGraph 学习笔记
│   ├── docs/                   # 文档
|        |---fig                # 图片
|
│   ├── data/                   # 数据
│   ├── examples/               # 示例代码
│   └── projects/               # 项目实践
│
├── .env.example                # 环境变量模板
├── .env                        # 实际环境变量 (gitignore)
└── README.md                   # 项目说明和学习路线
```

## 命名约定

- 文档: `{序号}-{主题}.md` (中文命名)
- 示例代码: `ex{序号}_{功能描述}.py` (英文命名)
- 数据文件: 放在对应模块的 `data/` 目录

## 文档结构

每个章节文档通常包含:
1. 概念说明
2. 代码示例
3. 核心概念速查表
4. 参考链接
