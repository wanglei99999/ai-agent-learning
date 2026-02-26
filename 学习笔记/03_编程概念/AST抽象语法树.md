# AST (抽象语法树)

Abstract Syntax Tree，将代码解析为树状结构，表示代码的语法结构。

---

## 📖 定义

**AST（抽象语法树）** 是源代码的树状表示，它抽象了代码的语法结构，忽略了具体的语法细节（如括号、分号等）。


---

## 🎯 为什么需要 AST？

### 问题：字符串比较的局限性

```python
# 这两个函数调用在语义上完全等价
code1 = "func(a=1, b=2)"
code2 = "func(b=2, a=1)"  # 参数顺序不同

# 但字符串比较会失败
code1 == code2  # False ✗
```

### 解决：AST 比较

```python
import ast

# 解析为 AST
ast1 = ast.parse(code1, mode='eval')
ast2 = ast.parse(code2, mode='eval')

# 转换为字符串后比较
dump1 = ast.dump(ast1)
dump2 = ast.dump(ast2)

dump1 == dump2  # True ✓ (语义相同)
```


---

## � AST 的优点

1. **忽略参数顺序**
   ```python
   func(a=1, b=2) ≈ func(b=2, a=1)
   ```

2. **忽略空格差异**
   ```python
   func(a=1,b=2) ≈ func(a=1, b=2)
   ```

3. **忽略引号类型**
   ```python
   func(name='test') ≈ func(name="test")
   ```

4. **关注语义而非表面形式**
   - 比较的是代码的结构和含义
   - 而不是字面文本

---

## �🐍 Python 实现

### 基本导入
```python
import ast  # Python 标准库，无需安装
```

### 核心方法

#### 1. `ast.parse()` - 解析代码
```python
# 解析代码字符串为 AST 对象
code = "calculate_area(base=10, height=5)"
tree = ast.parse(code, mode='eval')

# mode 参数:
# - 'eval': 解析表达式
# - 'exec': 解析语句
# - 'single': 解析单个交互式语句
```

#### 2. `ast.dump()` - 转换为字符串
```python
# 将 AST 对象转换为可读的字符串表示
dump_str = ast.dump(tree)
print(dump_str)
```

**输出示例：**
```python
Expression(
  body=Call(
    func=Name(id='calculate_area', ctx=Load()),
    args=[],
    keywords=[
      keyword(arg='base', value=Constant(value=10)),
      keyword(arg='height', value=Constant(value=5))
    ]
  )
)
```

---

## 📝 使用示例

### 示例1：参数顺序不同

```python
import ast

code1 = "func(a=1, b=2)"
code2 = "func(b=2, a=1)"

ast1 = ast.parse(code1, mode='eval')
ast2 = ast.parse(code2, mode='eval')

print(ast.dump(ast1))
# Call(func=Name(id='func'), keywords=[
#   keyword(arg='a', value=Constant(value=1)),
#   keyword(arg='b', value=Constant(value=2))
# ])

print(ast.dump(ast2))
# Call(func=Name(id='func'), keywords=[
#   keyword(arg='b', value=Constant(value=2)),
#   keyword(arg='a', value=Constant(value=1))
# ])

# 注意：参数顺序在 dump 中可能不同，但语义相同
# 实际比较时，Python 的 AST 会规范化参数顺序
```

### 示例2：空格差异

```python
code1 = "func(a=1,b=2)"      # 无空格
code2 = "func(a=1, b=2)"     # 有空格

ast.dump(ast.parse(code1, mode='eval')) == \
ast.dump(ast.parse(code2, mode='eval'))
# True ✓ (AST 忽略空格)
```

### 示例3：引号类型

```python
code1 = "func(name='test')"   # 单引号
code2 = 'func(name="test")'   # 双引号

ast.dump(ast.parse(code1, mode='eval')) == \
ast.dump(ast.parse(code2, mode='eval'))
# True ✓ (AST 忽略引号类型)
```

---

## 💻 其他常用方法

### 1. `ast.literal_eval()` - 安全求值

```python
# 安全地执行字符串表达式（只支持字面量）
result = ast.literal_eval("[1, 2, 3]")  # [1, 2, 3]
result = ast.literal_eval("{'a': 1}")   # {'a': 1}

# 比 eval() 更安全，不会执行任意代码
# ast.literal_eval("os.system('rm -rf /')")  # ValueError
```

### 2. `ast.walk()` - 遍历节点

```python
tree = ast.parse("x = 1 + 2")

# 遍历所有节点
for node in ast.walk(tree):
    print(type(node).__name__)

# 输出:
# Module
# Assign
# Name
# BinOp
# Constant
# Constant
```

### 3. 自定义访问器

```python
class FunctionCallVisitor(ast.NodeVisitor):
    def visit_Call(self, node):
        print(f"Found function call: {node.func.id}")
        self.generic_visit(node)

code = "func_a(); func_b()"
tree = ast.parse(code)
visitor = FunctionCallVisitor()
visitor.visit(tree)
# 输出:
# Found function call: func_a
# Found function call: func_b
```

---

## 🎯 应用场景

### 1. 代码相似度检测
```python
# 检测两段代码是否在结构上相似
def are_similar(code1, code2):
    ast1 = ast.dump(ast.parse(code1))
    ast2 = ast.dump(ast.parse(code2))
    return ast1 == ast2
```

### 2. 函数调用验证
```python
# 验证模型输出的函数调用是否正确
def validate_function_call(predicted, expected):
    try:
        pred_ast = ast.parse(predicted, mode='eval')
        exp_ast = ast.parse(expected, mode='eval')
        return ast.dump(pred_ast) == ast.dump(exp_ast)
    except SyntaxError:
        return False
```

### 3. 代码重构工具
- 自动重命名变量
- 提取函数
- 优化代码结构

### 4. 静态分析工具
- 代码质量检查（如 pylint）
- 类型检查（如 mypy）
- 安全漏洞扫描

### 5. BFCL 中的应用

在 BFCL 评估中，使用 AST 比较函数调用的语义等价性：

```python
def _ast_strings_match(pred: str, expected: str) -> bool:
    """比较两个函数调用字符串是否在AST层面匹配"""
    try:
        pred_ast = ast.parse(pred, mode='eval')
        exp_ast = ast.parse(expected, mode='eval')
        return ast.dump(pred_ast) == ast.dump(exp_ast)
    except:
        # AST解析失败时回退到简单字符串比较
        return pred.strip() == expected.strip()
```

---

## 📊 AST 结构示例

### 简单表达式
```python
code = "1 + 2"
tree = ast.parse(code, mode='eval')
print(ast.dump(tree, indent=2))
```

**输出：**
```
Expression(
  body=BinOp(
    left=Constant(value=1),
    op=Add(),
    right=Constant(value=2)
  )
)
```

### 函数调用
```python
code = "print('hello', end='')"
tree = ast.parse(code, mode='eval')
print(ast.dump(tree, indent=2))
```

**输出：**
```
Expression(
  body=Call(
    func=Name(id='print', ctx=Load()),
    args=[Constant(value='hello')],
    keywords=[keyword(arg='end', value=Constant(value=''))]
  )
)
```

---

## 📚 相关资源

- [Python AST 官方文档](https://docs.python.org/3/library/ast.html)
- [Green Tree Snakes - AST 教程](https://greentreesnakes.readthedocs.io/)

---

**最后更新：** 2026-02-26
