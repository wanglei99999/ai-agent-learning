# Tech Stack

## 语言与运行时

- Python 3.11+
- Jupyter Notebook (用于交互式示例)

## 包管理

- uv (推荐) - Rust 编写的快速 Python 包管理器
- 虚拟环境: `.venv` 目录

## 核心依赖

```
langchain
langchain-core
langchain-community
langchain-openai
langchain-experimental
langgraph
python-dotenv
pandas
```

## LLM 提供商

- 阿里通义千问 (qwen-plus, qwen-max) - 主要使用
- OpenAI (可选)
- Anthropic Claude (可选)

## 常用命令

```bash
# 创建虚拟环境
uv venv --python 3.11

# 激活环境 (Windows cmd)
.venv\Scripts\activate

# 激活环境 (PowerShell)
.venv\Scripts\Activate.ps1

# 安装依赖
uv pip install langchain langchain-openai langgraph python-dotenv

# 运行示例
python langchain/examples/ex01_base_agent.py
```

## 环境变量

复制 `.env.example` 为 `.env`，配置 API Key:
- `DASHSCOPE_API_KEY` - 阿里通义千问
- `OPENAI_API_KEY` - OpenAI (可选)
- `ANTHROPIC_API_KEY` - Anthropic (可选)
