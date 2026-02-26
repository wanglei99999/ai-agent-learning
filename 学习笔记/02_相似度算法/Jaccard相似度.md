# Jaccard 相似度

Jaccard 相似度是一种衡量两个集合相似程度的方法。

---

## 📐 定义

### 公式
```
Jaccard 相似度 = |A ∩ B| / |A ∪ B|
              = 交集大小 / 并集大小
              = 共同元素数 / 总元素数
```

### 取值范围
- **0.0**：完全不相似（没有共同元素）
- **1.0**：完全相同（所有元素都相同）

---

## 📊 图解说明

```
集合 A: {1, 2, 3, 4}
集合 B: {3, 4, 5, 6}

交集 A ∩ B: {3, 4}        ← 共同元素
并集 A ∪ B: {1, 2, 3, 4, 5, 6}  ← 所有元素（去重）

Jaccard = |{3, 4}| / |{1, 2, 3, 4, 5, 6}|
        = 2 / 6
        = 0.33
```

### 可视化
```
A: ████████
B:     ████████
   ────────────
交: ████        (重叠部分)
并: ████████████ (全部)

相似度 = 重叠部分 / 全部
```

---

##  与其他相似度的对比

| 方法 | 公式 | 特点 |
|------|------|------|
| **Jaccard** | \|A∩B\| / \|A∪B\| | 考虑共同和不同 |
| **Dice** | 2\|A∩B\| / (\|A\|+\|B\|) | 更重视共同部分 |
| **Overlap** | \|A∩B\| / min(\|A\|, \|B\|) | 只看较小集合 |
| **余弦相似度** | A·B / (\|A\|\|B\|) | 考虑向量角度 |

---

## 🎯 实际应用场景

Jaccard 相似度因其简单高效的特点，在多个领域有广泛应用。

### 1. 文本相似度与去重

**应用：** 检测重复文档、抄袭检测、新闻聚类

```python
doc1 = "machine learning is fun"
doc2 = "deep learning is interesting"

# Jaccard 可以快速判断两个文档的词汇重叠程度
```

**实际案例：**
- **搜索引擎**：去除重复网页
- **新闻聚合**：将相似新闻分组
- **学术检测**：查找论文抄袭

**优势：** 计算快速，适合大规模文档比较

---

### 2. 推荐系统

**应用：** 协同过滤、用户相似度计算、物品推荐

```python
# 基于用户行为的推荐
user1_items = {"item_a", "item_b", "item_c"}
user2_items = {"item_b", "item_c", "item_d"}

similarity = len(user1_items & user2_items) / len(user1_items | user2_items)
# = 2/4 = 0.5

# 如果相似度高，可以推荐 user2 喜欢但 user1 没买的商品
```

**实际案例：**
- **电商平台**：Amazon、淘宝的"看了又看"功能
- **视频平台**：YouTube、B站的相关视频推荐
- **音乐平台**：Spotify 的歌单推荐

**为什么用 Jaccard？**
- 用户行为是集合（买过/没买过）
- 不需要考虑购买次数（只看是否购买）
- 计算简单，适合实时推荐

---

### 3. 生物信息学

**应用：** 基因序列比对、物种分类、蛋白质相似度

```python
# 比较两个物种的基因集合
species1_genes = {"gene_a", "gene_b", "gene_c", "gene_d"}
species2_genes = {"gene_b", "gene_c", "gene_e", "gene_f"}

# 计算物种间的遗传相似度
jaccard = len(species1_genes & species2_genes) / len(species1_genes | species2_genes)
```

**实际案例：**
- **进化树构建**：根据基因相似度判断物种亲缘关系
- **疾病研究**：比较患者与健康人的基因差异
- **药物研发**：寻找相似的化合物结构

---

### 4. 图像检索与计算机视觉

**应用：** 图像去重、相似图片搜索、目标检测

```python
# 图像特征比较（如颜色直方图）
image1_features = {0, 1, 5, 10, 15, 20}  # 主要颜色索引
image2_features = {1, 5, 10, 12, 18, 22}

# 计算图像相似度
similarity = len(image1_features & image2_features) / len(image1_features | image2_features)
```

**实际案例：**
- **Google 图片搜索**：以图搜图功能
- **Pinterest**：相似图片推荐
- **人脸识别**：比较面部特征点

---

### 5. 社交网络分析

**应用：** 好友推荐、社区发现、影响力分析

```python
# 基于共同好友推荐
user_a_friends = {"bob", "charlie", "david", "eve"}
user_b_friends = {"charlie", "david", "frank", "grace"}

# 共同好友越多，越可能认识
common_friends = user_a_friends & user_b_friends  # {"charlie", "david"}
```

**实际案例：**
- **Facebook/微信**："你可能认识的人"
- **LinkedIn**：职业人脉推荐
- **Twitter**：相似兴趣用户推荐

**为什么有效？**
- 共同好友多 → 可能在同一社交圈
- 计算简单 → 可以实时推荐

---

### 6. 代码相似度检测

**应用：** 代码抄袭检测、重复代码发现、代码审查

```python
code1_tokens = {"func", "call", "arg", "base", "return"}
code2_tokens = {"func", "call", "arg", "height", "return"}

# 检测代码片段的相似性
similarity = len(code1_tokens & code2_tokens) / len(code1_tokens | code2_tokens)
```

**实际案例：**
- **GitHub Copilot**：检测生成代码的原创性
- **代码审查工具**：发现重复代码
- **在线编程平台**：检测作业抄袭

---

### 7. 搜索引擎优化 (SEO)

**应用：** 关键词相似度、网页去重、内容聚类

```python
page1_keywords = {"python", "tutorial", "beginner", "programming"}
page2_keywords = {"python", "guide", "beginner", "coding"}

# 判断两个网页主题是否相似
```

**实际案例：**
- **Google 搜索**：过滤重复内容
- **内容管理系统**：自动标签推荐
- **SEO 工具**：分析竞争对手关键词

---

### 8. 市场篮子分析

**应用：** 购物篮分析、商品关联规则、交叉销售

```python
# 分析两个购物篮的相似度
basket1 = {"牛奶", "面包", "鸡蛋", "黄油"}
basket2 = {"牛奶", "面包", "果酱", "咖啡"}

# 相似度高 → 可能是同类型顾客
```

**实际案例：**
- **超市布局**：相似商品放一起
- **促销策略**：捆绑销售相关商品
- **库存管理**：预测商品需求

---

### 9. 网络安全

**应用：** 恶意软件检测、异常行为识别、入侵检测

```python
# 比较程序行为特征
normal_behavior = {"read_file", "write_log", "network_request"}
suspicious_behavior = {"read_file", "delete_file", "encrypt_data", "network_request"}

# 行为差异大 → 可能是恶意软件
```

**实际案例：**
- **杀毒软件**：检测病毒变种
- **防火墙**：识别异常流量模式
- **入侵检测系统**：发现可疑行为

---

### 10. BFCL 评估中的应用

在 BFCL 评估中，当 AST 解析失败时，使用 Jaccard 相似度作为回退方案：

```python
# 如果两个函数调用的 AST 结构不完全相同
# 用 Jaccard 相似度计算它们有多相似

pred_dump = "Call func Name id calculate keywords arg base value 10"
exp_dump  = "Call func Name id calculate keywords arg height value 5"

# 共同词: {"Call", "func", "Name", "id", "calculate", "keywords", "arg", "value"}
# 不同词: {"base", "10"} vs {"height", "5"}

# Jaccard 会给出一个 0-1 的相似度分数
```

---

## 🌟 为什么 Jaccard 这么流行？

### 优势总结

1. **计算简单**
   - 只需要集合的交集和并集
   - 时间复杂度 O(n)，空间复杂度 O(n)

2. **易于理解**
   - 直观的"重叠程度"概念
   - 结果在 0-1 之间，便于解释

3. **适合稀疏数据**
   - 推荐系统中用户只购买少量商品
   - 文本中只包含部分词汇
   - 不需要考虑缺失值

4. **对称性**
   - Jaccard(A, B) = Jaccard(B, A)
   - 适合无方向的相似度计算

5. **可扩展性**
   - 可以处理大规模数据集
   - 支持分布式计算（MapReduce）

### 局限性

1. **忽略频率**
   - 只看是否出现，不看出现次数
   - 不适合需要考虑权重的场景

2. **对集合大小敏感**
   - 小集合容易得到极端值
   - 需要结合其他指标使用

3. **无法处理顺序**
   - 集合是无序的
   - 不适合序列相似度（如时间序列）

---

## 💻 代码实现

### Python 实现
```python
def jaccard_similarity(s1: str, s2: str) -> float:
    """计算两个字符串的 Jaccard 相似度"""
    # 步骤1: 分词
    set1 = set(s1.split())
    set2 = set(s2.split())
    
    # 步骤2: 计算交集和并集
    intersection = set1 & set2  # 交集
    union = set1 | set2          # 并集
    
    # 步骤3: 计算相似度
    if len(union) == 0:
        return 0.0
    return len(intersection) / len(union)

# 示例
s1 = "calculate area base height"
s2 = "calculate area width length"

similarity = jaccard_similarity(s1, s2)
print(f"相似度: {similarity:.2f}")  # 0.33
```

### 详细步骤
```python
s1 = "calculate area base height"
s2 = "calculate area width length"

# 步骤1: 分词并转换为集合
set1 = {"calculate", "area", "base", "height"}
set2 = {"calculate", "area", "width", "length"}

# 步骤2: 计算交集
intersection = set1 & set2  # {"calculate", "area"}
print(f"交集: {intersection}")  # 2个词

# 步骤3: 计算并集
union = set1 | set2  # {"calculate", "area", "base", "height", "width", "length"}
print(f"并集: {union}")  # 6个词

# 步骤4: 计算 Jaccard 相似度
jaccard = len(intersection) / len(union)
print(f"Jaccard: {jaccard}")  # 2/6 = 0.33
```

### 更多示例

#### 示例1：完全相同
```python
A = {"apple", "banana", "orange"}
B = {"apple", "banana", "orange"}

交集 = {"apple", "banana", "orange"}  → 3个
并集 = {"apple", "banana", "orange"}  → 3个

Jaccard = 3/3 = 1.0  ✓ 完全相同
```

#### 示例2：完全不同
```python
A = {"apple", "banana"}
B = {"car", "bike"}

交集 = {}  → 0个
并集 = {"apple", "banana", "car", "bike"}  → 4个

Jaccard = 0/4 = 0.0  ✗ 完全不同
```

#### 示例3：部分重叠
```python
A = {"apple", "banana", "orange", "grape"}
B = {"banana", "orange", "kiwi"}

交集 = {"banana", "orange"}  → 2个
并集 = {"apple", "banana", "orange", "grape", "kiwi"}  → 5个

Jaccard = 2/5 = 0.4  ~ 中等相似
```

---

## 📚 扩展阅读

- [维基百科 - Jaccard Index](https://en.wikipedia.org/wiki/Jaccard_index)
- 其他相似度算法（待补充）

---

**最后更新：** 2026-02-26
