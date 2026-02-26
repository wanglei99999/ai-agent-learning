# AI/ML 通用概念学习笔记

本文档记录学习 AI Agent 过程中遇到的通用概念和知识点。

---

## 目录
- [评估指标](#评估指标)
  - [混淆矩阵 (Confusion Matrix)](#混淆矩阵-confusion-matrix)
  - [准确率 (Accuracy)](#准确率-accuracy)
  - [精确率 (Precision)](#精确率-precision)
  - [召回率 (Recall)](#召回率-recall)
  - [F1 分数](#f1-分数)
- [相似度算法](#相似度算法)
  - [Jaccard 相似度](#jaccard-相似度)
- [其他概念](#其他概念)
  - [AST (抽象语法树)](#ast-抽象语法树)

---

## 评估指标

### 混淆矩阵 (Confusion Matrix)

混淆矩阵是评估分类模型性能的基础工具，包含四个核心概念：

```
                    实际情况
                 正例(Positive)  负例(Negative)
              ┌─────────────────┬─────────────────┐
              │                 │                 │
    预测为正例 │   TP            │   FP            │
    (Positive)│ (True Positive) │ (False Positive)│
              │   真阳性         │   假阳性         │
              │   预测对了✓      │   误报✗          │
              ├─────────────────┼─────────────────┤
              │                 │                 │
    预测为负例 │   FN            │   TN            │
    (Negative)│ (False Negative)│ (True Negative) │
              │   假阴性         │   真阴性         │
              │   漏报✗          │   预测对了✓      │
              └─────────────────┴─────────────────┘
```

**四个概念详解：**

- **TP (True Positive - 真阳性)**
  - 预测：正例
  - 实际：正例
  - 结果：✓ 预测对了
  - 例子：模型说"需要调用函数"，实际确实需要

- **FP (False Positive - 假阳性)**
  - 预测：正例
  - 实际：负例
  - 结果：✗ 误报（多预测了）
  - 例子：模型说"需要调用函数"，实际不需要

- **FN (False Negative - 假阴性)**
  - 预测：负例
  - 实际：正例
  - 结果：✗ 漏报（少预测了）
  - 例子：模型说"不需要调用函数"，实际需要

- **TN (True Negative - 真阴性)**
  - 预测：负例
  - 实际：负例
  - 结果：✓ 预测对了
  - 例子：模型说"不需要调用函数"，实际确实不需要

**记忆技巧：**
```
T/F → True/False → 预测对/错
P/N → Positive/Negative → 预测为正/负

TP: True Positive  → 预测正 ✓ 实际正 → 对了
FP: False Positive → 预测正 ✗ 实际负 → 误报
FN: False Negative → 预测负 ✗ 实际正 → 漏报
TN: True Negative  → 预测负 ✓ 实际负 → 对了
```

**具体示例：**
```
场景：有10个函数，实际需要调用其中3个

函数列表: [A, B, C, D, E, F, G, H, I, J]
实际需要: [A, B, C]  ← 正例
实际不需要: [D, E, F, G, H, I, J]  ← 负例

模型预测需要: [A, B, D, E]

分类结果：
TP (真阳性): A, B        ← 预测需要 ✓ 实际需要 ✓
FP (假阳性): D, E        ← 预测需要 ✗ 实际不需要
FN (假阴性): C           ← 预测不需要 ✗ 实际需要
TN (真阴性): F, G, H, I, J  ← 预测不需要 ✓ 实际不需要 ✓

统计：
TP = 2
FP = 2
FN = 1
TN = 5
```

---

### 准确率 (Accuracy)

**定义：** 完全正确的样本占总样本的比例

**公式：**
```
Accuracy = (TP + TN) / (TP + FP + FN + TN)
         = 正确预测数 / 总样本数
```

**示例：**
```python
总样本数 = 10
正确预测 = 7 (TP=2, TN=5)
错误预测 = 3 (FP=2, FN=1)

Accuracy = 7/10 = 0.7 (70%)
```

**特点：**
- ✓ 简单直观
- ✓ 适合平衡数据集
- ✗ 在不平衡数据集上会失真

**不平衡数据集的问题：**
```
场景：100个样本，5个正例，95个负例

模型A：全部预测为负例
  正确 = 95 (所有负例)
  Accuracy = 95/100 = 0.95  ← 看起来很高，但没用
  
模型B：预测了10个正例，5个对
  Accuracy = (5+90)/100 = 0.95  ← 实际更有用
```

---

### 精确率 (Precision)

**定义：** 模型预测为正确的样本中，真正正确的比例

**公式：**
```
Precision = TP / (TP + FP)
          = 真正确 / 模型预测为正的总数
```

**关注点：** 预测的质量（"我预测的有多准？"）

**示例：**
```python
模型预测了5个函数: [func_a, func_b, func_c, func_d, func_e]
实际需要的函数: [func_a, func_b, func_d]

预测对的 (TP): func_a, func_b, func_d → 3个
预测错的 (FP): func_c, func_e → 2个

Precision = 3 / (3+2) = 3/5 = 0.6 (60%)
```

**含义：** 我预测的5个函数中，只有60%是对的

**适用场景：** 关注误报率（如垃圾邮件检测、推荐系统）

---

### 召回率 (Recall)

**定义：** 所有应该找到的结果中，实际找到的比例

**公式：**
```
Recall = TP / (TP + FN)
       = 真正确 / 实际为正的总数
```

**关注点：** 覆盖的完整性（"我找全了吗？"）

**示例：**
```python
模型预测了5个函数: [func_a, func_b, func_c, func_d, func_e]
实际需要的函数: [func_a, func_b, func_d, func_f]

找到的 (TP): func_a, func_b, func_d → 3个
漏掉的 (FN): func_f → 1个

Recall = 3 / (3+1) = 3/4 = 0.75 (75%)
```

**含义：** 应该找到4个函数，我找到了75%

**适用场景：** 关注漏报率（如疾病诊断、安全检测）

---

### Precision vs Recall 对比

| 维度 | Precision（精确率） | Recall（召回率） |
|------|-------------------|-----------------|
| **关注点** | 预测的质量 | 覆盖的完整性 |
| **问题** | "我说对的有多少真对？" | "应该找的我找到多少？" |
| **分母** | 模型预测为正的数量 | 实际为正的数量 |
| **高了说明** | 误报少（FP少） | 漏报少（FN少） |
| **低了说明** | 误报多（FP多） | 漏报多（FN多） |

**权衡关系（Trade-off）：**
```
提高 Precision → 更保守预测 → Recall 可能下降
提高 Recall → 更激进预测 → Precision 可能下降
```

**形象比喻：**
```
场景：在1000个人中找出10个罪犯

模型A（保守型）：
  预测了5个人是罪犯
  - 其中4个真是罪犯 (TP=4)
  - 1个是好人 (FP=1)
  - 漏了6个罪犯 (FN=6)
  
  Precision = 4/5 = 0.8    # 预测准确，误伤少
  Recall = 4/10 = 0.4      # 但漏掉很多

模型B（激进型）：
  预测了50个人是罪犯
  - 其中10个真是罪犯 (TP=10)
  - 40个是好人 (FP=40)
  - 没漏 (FN=0)
  
  Precision = 10/50 = 0.2  # 误伤很多好人
  Recall = 10/10 = 1.0     # 但一个不漏
```

---

### F1 分数

**定义：** 精确率和召回率的调和平均数

**公式：**
```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
```

**为什么用调和平均而不是算术平均？**

调和平均对极端值更敏感，能更好地平衡两个指标。

**示例：**
```python
Precision = 0.8, Recall = 0.6

算术平均: (0.8 + 0.6) / 2 = 0.7
调和平均 (F1): 2 * (0.8 * 0.6) / (0.8 + 0.6) = 0.686

F1 更接近较低的那个值，鼓励两个指标都高。
```

**特点：**
- 综合考虑 Precision 和 Recall
- 鼓励模型在两个指标上都表现良好
- 适合需要平衡质量和完整性的场景

---

## 相似度算法

### Jaccard 相似度

**定义：** 衡量两个集合相似程度的方法

**公式：**
```
Jaccard 相似度 = |A ∩ B| / |A ∪ B|
              = 交集大小 / 并集大小
              = 共同元素数 / 总元素数
```

**取值范围：**
- 0.0：完全不相似（没有共同元素）
- 1.0：完全相同（所有元素都相同）

**图解：**
```
集合 A: {1, 2, 3, 4}
集合 B: {3, 4, 5, 6}

交集 A ∩ B: {3, 4}        ← 共同元素
并集 A ∪ B: {1, 2, 3, 4, 5, 6}  ← 所有元素（去重）

Jaccard = |{3, 4}| / |{1, 2, 3, 4, 5, 6}|
        = 2 / 6
        = 0.33
```

**可视化：**
```
A: ████████
B:     ████████
   ────────────
交: ████        (重叠部分)
并: ████████████ (全部)

相似度 = 重叠部分 / 全部
```

**代码示例：**
```python
s1 = "calculate area base height"
s2 = "calculate area width length"

# 步骤1: 分词
set1 = set(s1.split())  # {"calculate", "area", "base", "height"}
set2 = set(s2.split())  # {"calculate", "area", "width", "length"}

# 步骤2: 计算交集和并集
intersection = set1 & set2  # {"calculate", "area"}
union = set1 | set2         # {"calculate", "area", "base", "height", "width", "length"}

# 步骤3: 计算 Jaccard 相似度
jaccard = len(intersection) / len(union)
# = 2 / 6 = 0.33
```

**更多示例：**

1. **完全相同：**
```python
A = {"apple", "banana", "orange"}
B = {"apple", "banana", "orange"}

交集 = {"apple", "banana", "orange"}  → 3个
并集 = {"apple", "banana", "orange"}  → 3个

Jaccard = 3/3 = 1.0  ✓ 完全相同
```

2. **完全不同：**
```python
A = {"apple", "banana"}
B = {"car", "bike"}

交集 = {}  → 0个
并集 = {"apple", "banana", "car", "bike"}  → 4个

Jaccard = 0/4 = 0.0  ✗ 完全不同
```

3. **部分重叠：**
```python
A = {"apple", "banana", "orange", "grape"}
B = {"banana", "orange", "kiwi"}

交集 = {"banana", "orange"}  → 2个
并集 = {"apple", "banana", "orange", "grape", "kiwi"}  → 5个

Jaccard = 2/5 = 0.4  ~ 中等相似
```

**优点：**
- 简单直观
- 对称性：Jaccard(A, B) = Jaccard(B, A)
- 归一化：结果在 0-1 之间，便于比较
- 适合集合比较：忽略顺序和重复

**与其他相似度的对比：**

| 方法 | 公式 | 特点 |
|------|------|------|
| **Jaccard** | \|A∩B\| / \|A∪B\| | 考虑共同和不同 |
| **Dice** | 2\|A∩B\| / (\|A\|+\|B\|) | 更重视共同部分 |
| **Overlap** | \|A∩B\| / min(\|A\|, \|B\|) | 只看较小集合 |

---

## 其他概念

### AST (抽象语法树)

**定义：** Abstract Syntax Tree，将代码解析为树状结构，表示代码的语法结构

**Python 中的使用：**
```python
import ast  # Python 标准库

# 解析代码字符串为 AST 对象
code = "calculate_area(base=10, height=5)"
tree = ast.parse(code, mode='eval')

# 将 AST 对象转换为字符串表示
dump_str = ast.dump(tree)
print(dump_str)
# 输出: Expression(body=Call(func=Name(id='calculate_area'), ...))
```

**为什么需要 AST？**

比较两个函数调用是否等价时，字符串比较会因为参数顺序、空格等表面差异而失败：

```python
# 字符串比较
"func(a=1, b=2)" == "func(b=2, a=1)"  # False ✗

# AST 比较
ast.dump(ast.parse("func(a=1, b=2)", mode='eval')) == \
ast.dump(ast.parse("func(b=2, a=1)", mode='eval'))  # True ✓
```

**优点：**
- 忽略参数顺序
- 忽略空格差异
- 忽略引号类型
- 关注语义而非表面形式

**应用场景：**
- 代码相似度检测
- 函数调用验证
- 代码重构工具
- 静态分析工具

---

## 学习资源

- [混淆矩阵详解](https://en.wikipedia.org/wiki/Confusion_matrix)
- [Jaccard 相似度](https://en.wikipedia.org/wiki/Jaccard_index)
- [Python AST 文档](https://docs.python.org/3/library/ast.html)

---

**最后更新：** 2026-02-26
