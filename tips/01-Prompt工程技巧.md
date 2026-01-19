# Prompt 工程技巧

> 在 AI Agent 开发中，编写高质量的 Prompt 是关键技能。本文总结了实用的 Prompt 格式化技巧。

## 1. 核心原则

**Prompt = 纯文本字符串**

- 所有格式符号（`##`、` ``` `、`**` 等）都是作为字符串直接发送给 LLM
- LLM 在训练时见过大量 Markdown 格式文本，学会了这些符号的含义
- 合理使用格式符号可以让 LLM 更好地理解提示词结构

## 2. 使用 Markdown 结构化提示词

### 2.1 标题分隔

使用 `##` 创建清晰的章节结构：

```python
prompt = """
## 任务
{task}

## 输入数据
{input}

## 输出要求
{requirements}
"""
```

**为什么有效：** LLM 能识别 `##` 作为标题，理解这是不同的语义块。

### 2.2 代码块标记

使用 ` ``` ` 包围代码：

```python
PROMPT = """
## 待审查的代码
```python
{code}
```

请分析上述代码的问题。
"""
```

**作用：**
- 告诉 LLM 这是代码，不是指令
- LLM 会用代码理解模式来分析
- 避免代码和指令混淆

**常见错误：**
```python
# ❌ 拼写错误
```pyton
{code}
```

# ❌ 忘记闭合
```python
{code}

# ✅ 正确写法
```python
{code}
```
```

## 3. 强调技巧

### 3.1 Markdown 加粗

```python
prompt = "请专注于 **算法效率** 上的主要瓶颈"
```

**效果：** LLM 会更关注被 `**` 包围的内容

### 3.2 其他强调方式

```python
# 方式1：中文引号
"请关注「算法效率」问题"

# 方式2：大写（英文）
"Focus on ALGORITHM EFFICIENCY"

# 方式3：重复强调
"请专注于算法效率！重点关注算法效率上的主要瓶颈。"
```

### 3.3 避免使用 HTML 标签

```python
# ❌ 不推荐：HTML 标签
"<strong>算法效率</strong>"


# ✅ 推荐：Markdown 语法
"**算法效率**"
```

## 4. 空行的作用

空行是重要的语义分隔符，影响 LLM 对内容的理解。

### 4.1 空行层次

| 空行数 | 用途 | 示例 |
|-------|------|------|
| `\n` | 换行 | 列表项之间 |
| `\n\n` | 段落分隔 | 不同语义块 |
| `\n\n\n` | 章节分隔 | 大的部分之间 |

### 4.2 实际应用

```python
# ❌ 没有空行分隔
prompt = """
## 任务
审查代码
## 代码
def add(a, b): return a + b
## 要求
找出问题
"""

# ✅ 合理使用空行
prompt = """
## 任务
审查代码

## 代码
```python
def add(a, b):
    return a + b
```

## 要求
找出问题
"""
```

### 4.3 标题和内容之间的空行

```python
# 更清晰的格式：标题和内容之间加空行
trajectory_parts.append(f"---上一轮尝试(代码)---\n\n{record['content']}")
```

**效果对比：**

```
# 不加空行（紧凑）
---上一轮尝试(代码)---
def add(a, b): return a + b

# 加空行（更清晰）
---上一轮尝试(代码)---

def add(a, b):
    return a + b
```

## 5. 列表格式

使用列表让要求更清晰：

```python
prompt = """
## 评审要求

如果存在问题，请指出：
- 当前算法的不足
- 具体的改进建议
- 预期的性能提升
"""
```

## 6. 完整示例对比

### ❌ 不好的 Prompt

```python
PROMPT = "审查代码def add(a,b): return a+b找出问题并给出改进建议"
```

**问题：**
- 没有结构
- 代码和指令混在一起
- 要求不清晰

### ✅ 好的 Prompt

```python
PROMPT = """
你是一位代码评审专家。

## 任务
审查以下 Python 代码，找出潜在问题并给出改进建议。

## 待审查的代码
```python
def add(a, b):
    return a + b
```

## 评审要求
请从以下角度分析：
- 类型安全
- 边界条件处理
- 文档完整性
- 代码规范性

## 输出格式
请直接输出你的反馈，不要包含任何额外的解释。
"""
```

**优点：**
- 结构清晰
- 代码和指令分离
- 要求明确
- 易于 LLM 理解

## 7. 实战技巧

### 7.1 Reflection Agent 的 Prompt 设计

```python
# Actor 的 Prompt
ACTOR_PROMPT = """
## 任务
{task}

## 历史记录
{trajectory}

## 要求
基于评审员的反馈，生成改进后的代码。
"""

# Evaluator 的 Prompt
EVALUATOR_PROMPT = """
## 原始任务
{task}

## 待评审的代码
```python
{code}
```

## 评审标准
- 算法效率
- 代码质量
- 边界处理
"""
```

### 7.2 动态内容的格式化

```python
def get_trajectory(self) -> str:
    """将记忆格式化为提示词"""
    trajectory_parts = []
    
    for record in self.records:
        if record['type'] == 'execution':
            # 标题和内容之间加空行
            trajectory_parts.append(
                f"---上一轮尝试---\n\n{record['content']}"
            )
        elif record['type'] == 'reflection':
            trajectory_parts.append(
                f"--- 评审反馈 ---\n\n{record['content']}"
            )
    
    # 各部分之间用两个换行分隔
    return '\n\n'.join(trajectory_parts)
```

## 8. 常见错误总结

| 错误 | 正确写法 |
|-----|---------|
| `<strong>文本<strong>` | `**文本**` |
| ` ```pyton ` | ` ```python ` |
| 忘记闭合 ` ``` ` | 始终成对出现 |
| 没有空行分隔 | 用 `\n\n` 分隔语义块 |
| 指令和数据混在一起 | 用标题和代码块分离 |

## 9. 参考资料

- [OpenAI Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic Prompt Design](https://docs.anthropic.com/claude/docs/prompt-design)
- [LangChain Prompt Templates](https://python.langchain.com/docs/modules/model_io/prompts/)

## 10. 实践建议

1. **先写结构，再填内容**：用 `##` 规划好章节
2. **测试不同格式**：观察 LLM 对不同格式的响应
3. **保持一致性**：在同一个项目中使用统一的格式风格
4. **适度使用强调**：过多强调等于没有强调
5. **留意空行**：合理的空行让提示词更易读

---

**最后更新：** 2026-01-19
