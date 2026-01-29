"""RAG Pipeline（RAG 引擎层：文档解析 / 切分 / 向量化 / 检索）

你在学习 `hello-agent` 架构时，可以把这个模块理解为：
- 上层 `RAGTool` 负责“对外工具接口 + 参数整理 + 输出格式”。
- 本模块负责“真正的 RAG 引擎”：把文件入库到向量库、把 query 检索出相关 chunk。

核心数据流（建议先记住这 3 条）：
1) 入库（Indexing）：file_paths → load_and_chunk_texts → index_chunks → Qdrant
2) 基础检索（Retrieval）：query → embed_query → search_vectors → Qdrant
3) 高级检索（Advanced）：search_vectors_expanded（MQE/HyDE 查询扩展）→ 多路检索聚合

对外入口：create_rag_pipeline() 返回一个 dict（可以当作轻量 Facade）：
- add_documents(file_paths, chunk_size, chunk_overlap) -> int
- search(query, top_k, score_threshold) -> List[Dict]
- search_advanced(query, top_k, enable_mqe, enable_hyde, score_threshold) -> List[Dict]
- get_stats() -> Dict[str, Any]
- store: QdrantVectorStore

关于 sqlite3/cache_db：
- 本文件 import 了 sqlite3，并且 index_chunks() 预留了 cache_db 参数。
- 但当前实现里没有看到 sqlite3.connect(...) 的实际使用，更像是历史遗留/预留扩展点。
"""

from typing import List, Dict, Optional, Any
import os
import hashlib
import sqlite3
import time
import json
from ..embedding import get_text_embedder, get_dimension
from ..storage.qdrant_store import QdrantVectorStore


def _get_markitdown_instance():
    """获取 MarkItDown 实例（用于多格式文档解析）

    MarkItDown 是一个“多格式文件 → Markdown/文本”的统一转换工具。
    在 RAG 入库阶段，我们希望优先用它把 PDF/Office/图片/音频/网页等转成文本，
    这样后面的切分、embedding 才能统一处理。

    Returns:
        MarkItDown | None: 未安装 `markitdown` 时返回 None（调用方会降级到 `_fallback_text_reader`）。
    """
    try:
        from markitdown import MarkItDown
        return MarkItDown()
    except ImportError:
        print("[WARNING] MarkItDown not available. Install with: pip install markitdown")
        return None

def _is_markitdown_supported_format(path: str) -> bool:
    """
    Check if the file format is supported by MarkItDown.
    Supports: PDF, Office docs (docx, xlsx, pptx), images (jpg, png, gif, bmp, tiff), 
    audio (mp3, wav, m4a), HTML, text formats (txt, md, csv, json, xml), ZIP files, etc.

    教学理解：
    - 这里只做“文件后缀名”级别判断，不读取文件内容。
    - 常用于决定：该文件是否可以交给 MarkItDown 解析；不行就走 fallback reader。

    Args:
        path: 文件路径。

    Returns:
        bool: True 表示后缀名在支持列表中。
    """
    ext = (os.path.splitext(path)[1] or '').lower()
    supported_formats = {
        # Documents
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        # Text formats
        '.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm',
        # Images (OCR + metadata)
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp',
        # Audio (transcription + metadata) 
        '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg',
        # Archives
        '.zip', '.tar', '.gz', '.rar',
        # Code files
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.css', '.scss',
        # Other text
        '.log', '.conf', '.ini', '.cfg', '.yaml', '.yml', '.toml'
    }
    return ext in supported_formats

def _convert_to_markdown(path: str) -> str:
    """统一文档读取入口：文件 → 文本（markdown/纯文本）

    教学理解：
    - 后续的 chunking、embedding 都只处理字符串，因此任何输入文件都要先在这里被“转成文本”。
    - 这个函数尽量保证“失败可降级”：MarkItDown 不可用或失败时，会改用 `_fallback_text_reader`。

    处理策略：
    1) 文件不存在：返回空字符串
    2) PDF：走 `_enhanced_pdf_processing`（额外做清洗/重组，利于后续切分）
    3) 其他格式：优先 `MarkItDown.convert(...)`
    4) 异常：fallback reader

    Args:
        path: 文件路径。

    Returns:
        str: 提取到的文本内容；失败时返回空字符串。
    """
    # 步骤1：文件存在性检查（防御性编程，避免后续 open() 报错）
    if not os.path.exists(path):
        return ""  # 文件不存在，返回空字符串（不抛异常，让调用方继续处理其他文件）
    
    # 步骤2：提取文件扩展名并判断是否为 PDF
    # 对PDF文件使用增强处理，pdf处理起来麻烦很多
    ext = (os.path.splitext(path)[1] or '').lower()  # 提取扩展名："/path/to/file.PDF" → ".pdf"
    if ext == '.pdf':
        # PDF 需要特殊处理（额外清理噪声），走专用通道
        return _enhanced_pdf_processing(path)
    
    # 步骤3：其他格式使用 MarkItDown 通用转换
    md_instance = _get_markitdown_instance()  # 获取 MarkItDown 实例（延迟加载）
    if md_instance is None:
        # MarkItDown 未安装，熔断到简单文本读取
        return _fallback_text_reader(path)
    
    try:
        # 步骤4：调用 MarkItDown 转换文件
        result = md_instance.convert(path)  # 转换文件（支持 Word/Excel/图片/音频等）
        
        # 步骤5：从结果对象中提取文本内容
        text = getattr(result, "text_content", None)  # 防御性编程：如果没有该属性，返回 None
        
        # 步骤6：检查文本是否有效
        if isinstance(text, str) and text.strip():
            # 文本有效（是字符串且不是空白），返回文本
            return text
        
        # 文本无效（None 或空白字符串），返回空字符串
        return ""
        
    except Exception as e:
        # 步骤7：异常处理（熔断机制）
        # MarkItDown 转换失败（如文件损坏、格式不支持等），打印警告并降级
        print(f"[WARNING] MarkItDown failed for {path}: {e}")
        return _fallback_text_reader(path)  # 熔断到最简单的文本读取

def _enhanced_pdf_processing(path: str) -> str:
    """增强型 PDF 处理：提取 + 后处理清理

    教学理解：
    - PDF 文件通过 OCR 或文本提取后，常含有页眉/页脚/页码等噪声。
    - 本函数在 MarkItDown 提取基础上，额外做后处理清理，提升文本质量。

    处理流程：
    1) 使用 MarkItDown 提取原始文本
    2) 调用 `_post_process_pdf_text()` 进行后处理：
       - 移除页码、页眉页脚等噪声
       - 智能合并被断行的短句
       - 重组段落结构

    Args:
        path: PDF 文件路径。

    Returns:
        str: 清理后的文本内容；提取失败时返回空字符串。
    """
    # 打印日志：告知用户正在使用增强模式处理 PDF
    print(f"[RAG] Using enhanced PDF processing for: {path}")
    
    # 步骤1：获取 MarkItDown 实例（延迟加载，避免未安装时报错）
    md_instance = _get_markitdown_instance()
    if md_instance is None:
        # 如果 MarkItDown 未安装，熔断到最简单的文本读取（虽然 PDF 读不了，但保证不崩溃）
        return _fallback_text_reader(path)
    
    try:
        # 步骤2：使用 MarkItDown 提取 PDF 的原始文本
        result = md_instance.convert(path)  # convert() 返回对象，不是字符串
        
        # 步骤3：从结果对象中提取文本内容（使用 getattr 防御性编程）
        raw_text = getattr(result, "text_content", None)  # 如果没有 text_content 属性，返回 None
        
        # 步骤4：检查提取的文本是否有效
        if not raw_text or not raw_text.strip():
            # 文本为空或只有空白字符，直接返回空字符串
            return ""
        
        # 步骤5：后处理清理（核心步骤！）
        # 调用 _post_process_pdf_text() 清理页眉页脚、合并断行、重组段落
        cleaned_text = _post_process_pdf_text(raw_text)
        
        # 步骤6：打印处理结果（显示清理前后的字符数变化）
        print(f"[RAG] PDF post-processing completed: {len(raw_text)} -> {len(cleaned_text)} chars")
        return cleaned_text
        
    except Exception as e:
        # 步骤7：异常处理（熔断机制）
        # 如果增强处理失败（如 PDF 损坏），打印警告并降级到简单读取
        print(f"[WARNING] Enhanced PDF processing failed for {path}: {e}")
        return _fallback_text_reader(path)

def _post_process_pdf_text(text: str) -> str:
    """PDF 文本后处理：清理噪声 + 智能合并段落

    教学理解：
    - PDF 提取的文本常有"断行"问题：一句话被拆成多行。
    - 本函数通过启发式规则，将碎片化的行重新组织成完整段落。

    处理步骤：
    1) **清理噪声行**：
       - 移除单字符行、纯数字页码行
       - 过滤常见页眉页脚关键词（如 'github', 'project'）
    2) **智能合并短行**：
       - 如果当前行 < 60 字符且下一行 < 120 字符，尝试合并
       - 避免合并标题行（以 '#' 或 '：' 结尾）
    3) **重组段落**：
       - 识别段落边界（标题、长句、冒号结尾等）
       - 将同一段落的行用空格连接，段落间用双换行分隔

    Args:
        text: 原始 PDF 提取文本。

    Returns:
        str: 清理并重组后的文本。
    """
    import re
    
    # ========== 第一阶段：清理噪声行 ==========
    # 将文本按行分割，逐行检查并过滤噪声
    lines = text.splitlines()  # 分割成行列表：["第一行", "第二行", ...]
    cleaned_lines = []  # 存储清理后的行
    
    for line in lines:
        # 去除行首行尾的空白字符（空格、制表符等）
        line = line.strip()
        
        # 过滤规则1：跳过空行
        if not line:
            continue
            
        # 过滤规则2：移除单字符或双字符行（通常是噪音，如 "a", "1"）
        # 但保留纯数字（如页码 "12"），后续会单独处理
        if len(line) <= 2 and not line.isdigit():
            continue
            
        # 过滤规则3：移除明显的页眉页脚噪音
        # 3.1 纯数字行（页码）：如 "1", "23", "456"
        if re.match(r'^\d+$', line):
            continue
        
        # 3.2 常见的页眉页脚关键词（不区分大小写）
        # 如 GitHub 项目页面的 "GitHub", "Project", "Forks" 等
        if line.lower() in ['github', 'project', 'forks', 'stars', 'language']:
            continue
            
        # 通过所有过滤规则，保留这一行
        cleaned_lines.append(line)
    
    # ========== 第二阶段：智能合并短行 ==========
    # PDF 常见问题：一句话被断成多行，如 "这是一段很长的句子被\n断成了两行"
    # 本阶段将这些被断开的短行重新合并成完整句子
    merged_lines = []  # 存储合并后的行
    i = 0  # 当前处理的行索引
    
    while i < len(cleaned_lines):
        current_line = cleaned_lines[i]
        
        # 合并条件判断：当前行很短（< 60 字符）且还有下一行
        if len(current_line) < 60 and i + 1 < len(cleaned_lines):
            next_line = cleaned_lines[i + 1]
            
            # 检查是否应该合并（避免合并标题行）
            # 不合并的情况：
            # 1. 当前行以冒号结尾（可能是标题或列表项）
            # 2. 当前行或下一行以 '#' 开头（Markdown 标题）
            # 3. 下一行太长（> 120 字符，可能是独立段落）
            if (not current_line.endswith('：') and 
                not current_line.endswith(':') and
                not current_line.startswith('#') and
                not next_line.startswith('#') and
                len(next_line) < 120):
                
                # 满足合并条件：用空格连接两行
                merged_line = current_line + " " + next_line
                merged_lines.append(merged_line)
                i += 2  # 跳过下一行（已经合并了）
                continue
        
        # 不满足合并条件，直接保留当前行
        merged_lines.append(current_line)
        i += 1
    
    # ========== 第三阶段：重新组织段落 ==========
    # 将合并后的行重新组织成段落结构（段落间用双换行分隔）
    paragraphs = []  # 存储最终的段落列表
    current_paragraph = []  # 当前正在构建的段落（多行组成）
    
    for line in merged_lines:
        # 判断是否是新段落的开始（段落边界识别）
        is_paragraph_start = (
            line.startswith('#') or      # 条件1：Markdown 标题（如 "# 第一章"）
            line.endswith('：') or       # 条件2：中文冒号结尾（如 "引言："）
            line.endswith(':') or        # 条件3：英文冒号结尾（如 "Introduction:"）
            len(line) > 150 or           # 条件4：长句（> 150 字符，通常是段落开始）
            not current_paragraph        # 条件5：第一行（当前段落为空）
        )
        
        if is_paragraph_start:
            # 这是新段落的开始，先保存之前累积的段落
            if current_paragraph:
                # 将当前段落的多行用空格连接成一个段落
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []  # 清空，准备构建新段落
            
            # 将当前行作为独立段落（标题或段落开始）
            paragraphs.append(line)
        else:
            # 这是段落的延续，累积到当前段落
            current_paragraph.append(line)
    
    # 处理最后一个段落（循环结束后可能还有未保存的段落）
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    
    # 将所有段落用双换行连接（Markdown 段落分隔符）
    return '\n\n'.join(paragraphs)

def _fallback_text_reader(path: str) -> str:
    """降级文本读取器：当 MarkItDown 不可用时的备选方案

    教学理解：
    - 如果 MarkItDown 未安装或解析失败，本函数提供最基础的文本读取。
    - 仅适用于纯文本文件（.txt, .md, .py 等），不支持 PDF/Office 等复杂格式。

    编码处理：
    - 优先尝试 UTF-8 编码
    - 失败时降级到 Latin-1 编码（兼容性更好，但可能乱码）
    - 使用 `errors='ignore'` 忽略无法解码的字符

    Args:
        path: 文件路径。

    Returns:
        str: 文件文本内容；读取失败时返回空字符串。
    """
    try:
        # 策略1：优先使用 UTF-8 编码读取（最常用的编码）
        # errors='ignore'：遇到无法解码的字节直接跳过，不抛异常
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()  # 成功读取，返回文本内容
            
    except Exception:
        # UTF-8 读取失败，尝试降级方案
        try:
            # 策略2：使用 Latin-1 编码读取（兼容性最好，可以解码任何字节）
            # Latin-1 的特点：0-255 的每个字节都有对应字符，不会抛 UnicodeDecodeError
            # 缺点：可能乱码，但至少能读取内容
            with open(path, 'r', encoding='latin-1', errors='ignore') as f:
                return f.read()  # 成功读取，返回文本内容（可能乱码）
                
        except Exception:
            # 策略3：彻底失败（文件无法打开，如权限问题、文件被占用等）
            return ""  # 返回空字符串（熔断机制的最后一道防线，绝不崩溃）

def _detect_lang(sample: str) -> str:
    """检测文本语言（用于后续分词/chunking 策略）

    教学理解：
    - 不同语言的分词规则不同：中文按字符，英文按空格。
    - 本函数使用 langdetect 库检测语言代码（如 'zh-cn', 'en', 'ja'）。

    实现细节：
    - 只取前 1000 字符进行检测（提高速度，避免超长文本）
    - 如果 langdetect 未安装或检测失败，返回 "unknown"

    Args:
        sample: 待检测的文本样本。

    Returns:
        str: 语言代码（如 'zh-cn', 'en'）或 "unknown"。
    """
    try:
        from langdetect import detect
        return detect(sample[:1000]) if sample else "unknown"
    except Exception:
        return "unknown"


def _is_cjk(ch: str) -> bool:
    """判断字符是否为 CJK（中日韩）字符

    教学理解：
    - CJK 字符包括中文汉字、日文汉字、韩文汉字。
    - 用于 token 长度估算：CJK 字符通常按 1 字符 = 1 token，而英文按单词计数。

    Unicode 范围（覆盖常用和扩展区）：
    - 0x4E00-0x9FFF: CJK 统一表意文字（基本区，最常用）
    - 0x3400-0x4DBF: CJK 扩展 A
    - 0x20000-0x2A6DF: CJK 扩展 B
    - 0x2A700-0x2B73F: CJK 扩展 C/D
    - 0x2B740-0x2B81F: CJK 扩展 E
    - 0x2B820-0x2CEAF: CJK 扩展 F
    - 0xF900-0xFAFF: CJK 兼容表意文字

    Args:
        ch: 单个字符。

    Returns:
        bool: True 表示该字符是 CJK 字符。
    """
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF or
        0x3400 <= code <= 0x4DBF or
        0x20000 <= code <= 0x2A6DF or
        0x2A700 <= code <= 0x2B73F or
        0x2B740 <= code <= 0x2B81F or
        0x2B820 <= code <= 0x2CEAF or
        0xF900 <= code <= 0xFAFF
    )


def _approx_token_len(text: str) -> int:
    """近似估算文本的 token 长度（用于 chunking）

    教学理解：
    - LLM 的输入限制通常以 token 为单位（如 GPT-3.5 的 4096 tokens）。
    - 本函数提供快速估算，避免调用真实 tokenizer（速度慢）。

    估算规则：
    - **CJK 字符**：1 字符 ≈ 1 token（中文"你好"≈ 2 tokens）
    - **非 CJK 文本**：按空格分词，1 单词 ≈ 1 token（英文 "hello world" ≈ 2 tokens）
    - 这是粗略估算，实际 token 数可能有 ±20% 误差，但足够用于 chunking。

    Args:
        text: 待估算的文本。

    Returns:
        int: 估算的 token 数量。
    """
    # 近似估计：CJK字符按1 token，其他按空白分词
    cjk = sum(1 for ch in text if _is_cjk(ch))
    non_cjk_tokens = len([t for t in text.split() if t])
    return cjk + non_cjk_tokens


def _split_paragraphs_with_headings(text: str) -> List[Dict]:
    """按 Markdown 标题层级切分段落，并记录章节路径

    教学理解：
    - Markdown 文档有层级结构（# 一级标题，## 二级标题...）。
    - 本函数识别标题，将文档切分为段落，并为每个段落记录它所属的"章节路径"。

    为什么要记录章节路径？
    - 检索时可以显示"这段文本来自哪个章节"，提升可读性。
    - 例如："第3章 > 3.2 RAG 原理 > 3.2.1 向量检索"

    实现逻辑：
    1) 维护一个 `heading_stack`（标题栈），记录当前所在的章节层级
    2) 遇到标题行（以 '#' 开头）：
       - 计算标题级别（'#' 的数量）
       - 更新 `heading_stack`（弹出更深层级，压入当前标题）
    3) 遇到普通文本行：累积到 `buf`，遇到空行时 flush 成一个段落
    4) 每个段落记录：`content`, `heading_path`, `start`, `end`（字符偏移）

    Args:
        text: Markdown 格式的文本。

    Returns:
        List[Dict]: 段落列表，每项包含：
            - content: 段落文本
            - heading_path: 章节路径（如 "第1章 > 1.1 简介"）
            - start: 起始字符位置
            - end: 结束字符位置
    """
    # 步骤1：按行分割文本（保留原始行内容）
    lines = text.splitlines()
    
    # 步骤2：初始化核心数据结构
    heading_stack: List[str] = []  # 标题栈：记录当前章节层级，如 ["第1章", "1.1节"]
    paragraphs: List[Dict] = []    # 输出的段落列表
    buf: List[str] = []            # 当前段落的行缓冲区（累积文本行）
    char_pos = 0                   # 当前字符位置（用于记录段落的 start/end）
    
    # 步骤3：定义内部函数 flush_buf（将缓冲区内容保存为一个段落）
    def flush_buf(end_pos: int):
        """将缓冲区的行合并成一个段落并保存"""
        # 检查1：缓冲区为空，直接返回
        if not buf:
            return
        
        # 检查2：合并缓冲区的所有行，并去除首尾空白
        content = "\n".join(buf).strip()  # 用换行符连接所有行
        if not content:  # 内容为空（只有空白字符），直接返回
            return
        
        # 检查3：保存段落到输出列表
        paragraphs.append({
            "content": content,  # 段落文本
            "heading_path": " > ".join(heading_stack) if heading_stack else None,  # 章节路径（如 "第1章 > 1.1节"）
            "start": max(0, end_pos - len(content)),  # 起始字符位置（粗略估算）
            "end": end_pos,  # 结束字符位置
        })
    # 步骤4：逐行处理文本
    for ln in lines:
        raw = ln  # 保存原始行（包含前导空格）
        
        # ========== 情况1：标题行（以 '#' 开头）==========
        if raw.strip().startswith("#"):
            # 步骤4.1：先保存之前累积的段落（标题是段落的分隔符）
            flush_buf(char_pos)
            
            # 步骤4.2：计算标题级别（'#' 的数量）
            # 例如："## 1.1节" → level = 2
            level = len(raw) - len(raw.lstrip('#'))  # 原始长度 - 去除 '#' 后的长度 = '#' 的数量
            
            # 步骤4.3：提取标题文本（去除 '#' 和空白）
            # 例如："## 1.1节  " → "1.1节"
            title = raw.lstrip('#').strip()
            
            # 步骤4.4：修正级别（至少为 1）
            if level <= 0:
                level = 1
            
            # 步骤4.5：更新标题栈（维护章节层级）
            # 如果新标题的级别 <= 栈的长度，需要弹出更深层级的标题
            # 例如：栈 = ["第1章", "1.1节", "1.1.1小节"]，新标题级别 = 2
            #      → 弹出到 ["第1章"]，然后压入新标题
            if level <= len(heading_stack):
                heading_stack = heading_stack[:level-1]  # 保留前 level-1 个标题
            
            # 步骤4.6：将当前标题压入栈
            heading_stack.append(title)
            
            # 步骤4.7：更新字符位置（+1 是换行符）
            char_pos += len(raw) + 1
            continue  # 跳过后续处理，继续下一行
        # ========== 情况2：普通文本行 ==========
        if raw.strip() == "":
            # 情况2.1：空行（段落分隔符）
            flush_buf(char_pos)  # 保存当前段落
            buf = []  # 清空缓冲区，准备下一个段落
        else:
            # 情况2.2：非空行（段落内容）
            buf.append(raw)  # 累积到缓冲区
        
        # 更新字符位置（+1 是换行符）
        char_pos += len(raw) + 1
    
    # 步骤5：处理最后一个段落（循环结束后可能还有未保存的段落）
    flush_buf(char_pos)
    
    # 步骤6：兜底处理（如果整个文档没有标题和空行，返回整个文本作为一个段落）
    if not paragraphs:
        paragraphs = [{"content": text, "heading_path": None, "start": 0, "end": len(text)}]
    
    return paragraphs


def _chunk_paragraphs(paragraphs: List[Dict], chunk_size: int = 800, chunk_overlap: int = 100) -> List[Dict]:
    """将段落列表按 token 长度合并成 chunks（支持重叠）

    教学理解：
    - 段落可能太短（几十字）或太长（几千字），不适合直接作为检索单元。
    - 本函数将多个段落合并成"大小适中"的 chunk，并支持 chunk 间重叠。

    为什么要重叠？
    - 避免关键信息被切分到两个 chunk 的边界处，导致检索时丢失上下文。
    - 例如：chunk1 末尾是"RAG 的核心是"，chunk2 开头是"向量检索"。
      如果有重叠，chunk2 会包含"RAG 的核心是向量检索"，语义更完整。

    实现逻辑：
    1) 维护当前 chunk 的段落列表 `cur` 和累计长度 `cur_len`
    2) 逐个添加段落，如果 `cur_len >= chunk_size`，则 flush 成一个 chunk
    3) Flush 后，保留最后几个段落（总长度 ≈ chunk_overlap）作为下一个 chunk 的开头

    Args:
        paragraphs: `_split_paragraphs_with_headings()` 的输出。
        chunk_size: 目标 chunk 大小（按 token 估算）。
        chunk_overlap: chunk 重叠大小（按 token 估算）。

    Returns:
        List[Dict]: chunk 列表，每项包含：
            - content: 合并后的文本
            - start: 起始字符位置（取第一个段落的 start）
            - end: 结束字符位置（取最后一个段落的 end）
            - heading_path: 章节路径（取最后一个有 heading_path 的段落）
    """
    # 步骤1：初始化核心数据结构
    chunks: List[Dict] = []  # 输出的 chunk 列表
    cur: List[Dict] = []     # 当前正在构建的 chunk（段落列表）
    cur_tokens = 0           # 当前 chunk 的累计 token 数
    i = 0                    # 段落索引（当前处理到第几个段落）
    
    # 步骤2：逐个处理段落，合并成 chunks
    while i < len(paragraphs):
        # 步骤2.1：获取当前段落并估算其 token 数
        p = paragraphs[i]
        p_tokens = _approx_token_len(p["content"]) or 1  # 估算 token 数（至少为 1，避免除零错误）
        
        # 步骤2.2：判断是否可以将当前段落添加到当前 chunk
        # 条件1：添加后不超过 chunk_size
        # 条件2：当前 chunk 为空（必须至少有一个段落，即使超限）
        if cur_tokens + p_tokens <= chunk_size or not cur:
            # 可以添加：将段落加入当前 chunk
            cur.append(p)
            cur_tokens += p_tokens  # 更新累计 token 数
            i += 1  # 移动到下一个段落
        else:
            # ========== 步骤2.3：不能添加，需要 flush 当前 chunk ==========
            
            # 步骤2.3.1：合并当前 chunk 的所有段落
            content = "\n\n".join(x["content"] for x in cur)  # 用双换行连接段落（Markdown 段落分隔符）
            
            # 步骤2.3.2：提取 chunk 的元数据
            start = cur[0]["start"]  # 第一个段落的起始位置
            end = cur[-1]["end"]     # 最后一个段落的结束位置
            
            # 步骤2.3.3：提取 heading_path（从后往前找第一个有 heading_path 的段落）
            # 为什么从后往前？因为最后一个段落的 heading_path 最能代表整个 chunk 的主题
            heading_path = next((x["heading_path"] for x in reversed(cur) if x.get("heading_path")), None)
            
            # 步骤2.3.4：保存 chunk 到输出列表
            chunks.append({
                "content": content,
                "start": start,
                "end": end,
                "heading_path": heading_path,
            })
            # ========== 步骤2.3.5：构建重叠（保留当前 chunk 的末尾部分作为下一个 chunk 的开头）==========
            # 注意：代码中应该是 chunk_overlap，这里假设变量名为 overlap_tokens
            if chunk_overlap > 0 and cur:
                # 从后往前保留段落，直到累计 token 数接近 chunk_overlap
                kept: List[Dict] = []  # 保留的段落列表
                kept_tokens = 0        # 保留的累计 token 数
                
                # 从后往前遍历当前 chunk 的段落
                for x in reversed(cur):
                    t = _approx_token_len(x["content"]) or 1  # 估算段落的 token 数
                    
                    # 如果加上这个段落会超过重叠限制，停止
                    if kept_tokens + t > chunk_overlap:
                        break
                    
                    # 保留这个段落
                    kept.append(x)
                    kept_tokens += t
                
                # 反转回正序（因为是从后往前遍历的）
                cur = list(reversed(kept))
                cur_tokens = kept_tokens
            else:
                # 不需要重叠，清空当前 chunk
                cur = []
                cur_tokens = 0
    # 步骤3：处理最后一个 chunk（循环结束后可能还有未保存的段落）
    if cur:
        # 合并段落
        content = "\n\n".join(x["content"] for x in cur)
        
        # 提取元数据
        start = cur[0]["start"]
        end = cur[-1]["end"]
        heading_path = next((x["heading_path"] for x in reversed(cur) if x.get("heading_path")), None)
        
        # 保存最后一个 chunk
        chunks.append({
            "content": content,
            "start": start,
            "end": end,
            "heading_path": heading_path,
        })
    
    return chunks
 
 
def load_and_chunk_texts(paths: List[str], chunk_size: int = 800, chunk_overlap: int = 100, namespace: Optional[str] = None, source_label: str = "rag") -> List[Dict]:
    """加载文件并切分为 chunks（RAG 入库阶段的核心一步）

    你可以把这个函数理解为：
    - **输入是一堆文件**（`paths`）
    - **输出是一堆可入库的文本片段**（chunks：每条都带 `content` 和 `metadata`）

    这个函数做的事情（按顺序）：
    1) 对每个文件调用 `_convert_to_markdown(path)`：把不同格式统一变成文本/Markdown。
    2) `_split_paragraphs_with_headings(text)`：识别 markdown 标题层级，把段落与章节路径关联起来。
    3) `_chunk_paragraphs(...)`：按“近似 token 长度”把段落合并成 chunk，并用 `chunk_overlap` 做重叠。
    4) 为每个 chunk 生成：
       - `id`: 稳定的 chunk id（基于 doc_id、位置、hash）
       - `content`: chunk 文本
       - `metadata`: 来源文件、语言、字符偏移、heading_path 等

    Args:
        paths: 文件路径列表。
        chunk_size: chunk 目标大小（本实现使用近似 token 计数）。
        chunk_overlap: chunk 重叠大小（同样按近似 token 计数）。
        namespace: 写入到 `metadata["namespace"]` 的逻辑命名空间（用于隔离不同知识库）。
        source_label: 写入到 `metadata["source"]` 的来源标识。

    Returns:
        List[Dict]: chunk 列表。每项形如：
 
            - `{"id": str, "content": str, "metadata": Dict[str, Any]}`
 
        初学者通常只需要先关注：
        - `chunk["content"]`
        - `chunk["metadata"]["source_path"]`
        - `chunk["metadata"]["heading_path"]`

    Example:
        >>> chunks = load_and_chunk_texts([
        ...     "./docs/intro.pdf",
        ...     "./notes.md",
        ... ], chunk_size=400, chunk_overlap=50, namespace="default")
        >>> len(chunks)
        42
        >>> list(chunks[0].keys())
        ['id', 'content', 'metadata']
        >>> chunks[0]['metadata'].get('source_path')
        './docs/intro.pdf'
    """
    # 打印开始日志（方便调试和监控）
    print(f"[RAG] Universal loader start: files={len(paths)} chunk_size={chunk_size} overlap={chunk_overlap} ns={namespace or 'default'}")
    
    # 初始化输出列表和去重集合
    chunks: List[Dict] = []  # 最终输出的 chunk 列表
    seen_hashes = set()      # 用于去重的内容哈希集合（避免重复内容被多次索引）
    
    # ========== 步骤1：遍历所有文件 ==========
    for path in paths:
        # 步骤1.1：检查文件是否存在
        if not os.path.exists(path):
            print(f"[WARNING] File not found: {path}")
            continue  # 跳过不存在的文件
            
        print(f"[RAG] Processing: {path}")
        
        # 步骤1.2：提取文件扩展名（用于记录到 metadata）
        # 例如："./docs/intro.pdf" → ".pdf"
        ext = (os.path.splitext(path)[1] or '').lower()
        
        # ========== 步骤2：转换为 Markdown ==========
        # 使用 MarkItDown 将各种格式（PDF、Word、Excel 等）统一转换为 Markdown
        markdown_text = _convert_to_markdown(path)
        
        # 步骤2.1：检查是否成功提取内容
        if not markdown_text.strip():
            print(f"[WARNING] No content extracted from: {path}")
            continue  # 跳过空文件
        
        # ========== 步骤3：检测语言并生成文档 ID ==========
        # 步骤3.1：检测文档语言（如 "zh-cn", "en"）
        lang = _detect_lang(markdown_text)
        
        # 步骤3.2：生成文档 ID（基于路径和文本长度的 MD5 哈希）
        # 为什么用 MD5？确保相同文件生成相同 ID，支持增量更新
        doc_id = hashlib.md5(f"{path}|{len(markdown_text)}".encode('utf-8')).hexdigest()
        
        # ========== 步骤4：切分文档为 chunks ==========
        # 步骤4.1：按标题和段落切分（保留章节结构）
        para = _split_paragraphs_with_headings(markdown_text)
        
        # 步骤4.2：按 token 大小合并段落（控制 chunk 大小）
        # max(1, chunk_size) 确保至少为 1，避免参数错误
        token_chunks = _chunk_paragraphs(para, chunk_tokens=max(1, chunk_size), overlap_tokens=max(0, chunk_overlap))
        
        # ========== 步骤5：为每个 chunk 生成完整对象 ==========
        for ch in token_chunks:
            # 步骤5.1：提取 chunk 的基本信息
            content = ch["content"]  # chunk 文本内容
            start = ch.get("start", 0)  # 起始字符位置
            end = ch.get("end", start + len(content))  # 结束字符位置
            
            # 步骤5.2：去除首尾空白并检查是否为空
            norm = content.strip()
            if not norm:
                continue  # 跳过空 chunk
                
            # ========== 步骤5.3：内容去重 ==========
            # 计算内容的 MD5 哈希（用于检测重复内容）
            content_hash = hashlib.md5(norm.encode('utf-8')).hexdigest()
            
            # 检查是否已经处理过相同内容
            if content_hash in seen_hashes:
                continue  # 跳过重复内容（避免重叠部分被多次索引）
            seen_hashes.add(content_hash)  # 记录已处理的内容哈希
            
            # ========== 步骤5.4：生成稳定的 chunk ID ==========
            # 组成：doc_id + 位置信息 + 内容哈希
            # 为什么这样设计？确保相同内容在相同位置生成相同 ID，支持增量更新
            chunk_id = hashlib.md5(f"{doc_id}|{start}|{end}|{content_hash}".encode('utf-8')).hexdigest()
            
            # ========== 步骤5.5：组装完整的 chunk 对象 ==========
            chunks.append({
                "id": chunk_id,  # 唯一标识符
                "content": content,  # chunk 文本内容
                "metadata": {
                    # 来源信息
                    "source_path": path,  # 原始文件路径
                    "file_ext": ext,  # 文件扩展名（如 ".pdf"）
                    "doc_id": doc_id,  # 文档 ID
                    
                    # 文本属性
                    "lang": lang,  # 语言（如 "zh-cn"）
                    "start": start,  # 起始字符位置
                    "end": end,  # 结束字符位置
                    "content_hash": content_hash,  # 内容哈希（用于去重）
                    
                    # 命名空间和来源标签（用于隔离和过滤）
                    "namespace": namespace or "default",  # 逻辑命名空间（隔离不同知识库）
                    "source": source_label,  # 来源标识（如 "rag_pipeline"）
                    "external": True,  # 外部数据标记
                    
                    # 章节信息
                    "heading_path": ch.get("heading_path"),  # 章节路径（如 "第1章 > 1.1节"）
                    
                    # 格式标记
                    "format": "markdown",  # 标记所有内容都经过 Markdown 处理
                },
            })
            
    # 打印完成日志
    print(f"[RAG] Universal loader done: total_chunks={len(chunks)}")
    return chunks


def build_graph_from_chunks(neo4j, chunks: List[Dict]) -> None:
    """从 chunks 构建知识图谱（可选功能，需要 Neo4j）

    教学理解：
    - 除了向量检索，还可以用图数据库（Neo4j）存储文档结构关系。
    - 本函数将 chunks 转换为图节点和边，便于后续做图遍历查询。

    图结构设计：
    - **节点类型**：
      - `Document`：文档节点（一个文件对应一个 Document）
      - `Memory`：chunk 节点（每个 chunk 对应一个 Memory）
    - **关系类型**：
      - `HAS_CHUNK`：Document → Memory（文档包含哪些 chunks）

    使用场景：
    - 查询"这个文档有哪些 chunks"
    - 查询"这个 chunk 来自哪个文档"
    - 结合向量检索和图遍历，实现混合检索

    Args:
        neo4j: Neo4j 图数据库实例（需实现 add_entity/add_relationship 接口）。
        chunks: `load_and_chunk_texts()` 的输出。

    Returns:
        None（直接写入 Neo4j，异常时静默忽略）。
    """
    created_docs = set()
    for ch in chunks:
        mem_id = ch["id"]
        meta = ch.get("metadata", {})
        source_path = meta.get("source_path")
        doc_id = meta.get("doc_id")
        if doc_id and doc_id not in created_docs:
            created_docs.add(doc_id)
            try:
                neo4j.add_entity(
                    entity_id=doc_id,
                    name=os.path.basename(source_path or doc_id),
                    entity_type="Document",
                    properties={"source_path": source_path, "lang": meta.get("lang")}
                )
            except Exception:
                pass
        try:
            neo4j.add_entity(entity_id=mem_id, name=mem_id, entity_type="Memory", properties={
                "source_path": source_path,
                "doc_id": doc_id,
                "start": meta.get("start"),
                "end": meta.get("end"),
            })
        except Exception:
            pass
        if doc_id:
            try:
                neo4j.add_relationship(from_id=doc_id, to_id=mem_id, rel_type="HAS_CHUNK", properties={})
            except Exception:
                pass


def _preprocess_markdown_for_embedding(text: str) -> str:
    """预处理 Markdown 文本，提升 embedding 质量

    教学理解：
    - Markdown 标记符号（如 `**`, `#`, `[]()`）对语义贡献不大，但会占用 token。
    - 本函数移除这些标记，保留纯文本内容，让 embedding 模型更专注于语义。

    处理规则：
    1) **移除标题符号**：`# 标题` → `标题`
    2) **移除链接标记**：`[文本](url)` → `文本`
    3) **移除强调标记**：`**粗体**` → `粗体`，`*斜体*` → `斜体`
    4) **移除代码标记**：`` `代码` `` → `代码`，` ```代码块``` ` → `代码块`
    5) **清理多余空白**：连续换行 → 双换行，多个空格 → 单空格

    为什么要做这个？
    - Embedding 模型对"RAG 原理"和"**RAG 原理**"可能产生不同向量。
    - 预处理后统一格式，提升检索一致性。

    Args:
        text: 原始 Markdown 文本。

    Returns:
        str: 清理后的纯文本。
    """
    import re
    
    # Remove markdown headers symbols but keep the text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Remove markdown links but keep the text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Remove markdown emphasis markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # italic
    text = re.sub(r'`([^`]+)`', r'\1', text)        # inline code
    
    # Remove markdown code blocks but keep content
    text = re.sub(r'```[^\n]*\n([\s\S]*?)```', r'\1', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()


def _create_default_vector_store(dimension: int = None) -> QdrantVectorStore:
    """创建默认的 Qdrant 向量库实例（RAG 专用配置）

    教学理解：
    - Qdrant 是一个向量数据库，专门用于存储和检索高维向量。
    - 本函数创建一个配置好的 Qdrant 实例，供 RAG pipeline 使用。

    配置说明：
    - **dimension**：向量维度（由 embedding 模型决定，如 384 或 768）
    - **distance**：相似度度量方式，使用 "cosine"（余弦相似度）
    - **collection_name**：集合名称，默认 "hello_agents_rag_vectors"
    - **连接管理器**：使用单例模式，避免重复创建连接

    环境变量：
    - `QDRANT_URL`：Qdrant 服务地址（如 "http://localhost:6333"）
    - `QDRANT_API_KEY`：API 密钥（云端 Qdrant 需要）

    Args:
        dimension: 向量维度，None 时自动从 embedding 模型获取。

    Returns:
        QdrantVectorStore: 配置好的 Qdrant 实例。
    """
    if dimension is None:
        dimension = get_dimension(384)
    
    # Check for Qdrant configuration
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
    # 使用连接管理器
    from ..storage.qdrant_store import QdrantConnectionManager
    return QdrantConnectionManager.get_instance(
        url=qdrant_url,
        api_key=qdrant_api_key,
        collection_name="hello_agents_rag_vectors",
        vector_size=dimension,
        distance="cosine"
    )


# Cache functions removed - using unified embedder with internal caching


def index_chunks(
    store = None, 
    chunks: List[Dict] = None, 
    cache_db: Optional[str] = None, 
    batch_size: int = 64,
    rag_namespace: str = "default"
) -> None:
    """把 chunks 向量化并写入 Qdrant（入库阶段的“写入”部分）

    教学理解：
    - `load_and_chunk_texts()` 解决“文件怎么切成片段”。
    - `index_chunks()` 解决“片段怎么变成向量，并写到向量库”。

    Steps（按代码执行顺序）：
    1) 获取 embedding 模型：`embedder = get_text_embedder()`。
    2) 预处理文本：`_preprocess_markdown_for_embedding`，减少 markdown 符号噪声。
    3) 分批 `embedder.encode(part)` 得到向量（包含异常处理与维度兜底）。
    4) 为每条 chunk 组装写入的 `metadata`，并补充 RAG 专用标签，便于检索过滤：
       - `memory_type: "rag_chunk"`
       - `is_rag_data: True`
       - `data_source: "rag_pipeline"`
       - `rag_namespace: <namespace>`
    5) 调用 `store.add_vectors(vectors=..., metadata=..., ids=...)` 写入。

    Args:
        store: QdrantVectorStore（或兼容接口）。None 时会创建默认 store。
        chunks: `load_and_chunk_texts()` 的输出列表。
        cache_db: 预留参数（当前实现未使用；本文件虽 import sqlite3，但未实际 connect）。
        batch_size: embedding 批大小。
        rag_namespace: 写入/检索用的命名空间标签。

    Returns:
        None

    Raises:
        RuntimeError: 当写入向量库失败时抛出。

    Example:
        >>> store = _create_default_vector_store()
        >>> chunks = load_and_chunk_texts(["./docs/intro.pdf"], namespace="default")
        >>> index_chunks(store=store, chunks=chunks, rag_namespace="default")
        >>> # 写入成功时无返回值；失败会抛 RuntimeError
    """
    # ========== 步骤0：前置检查 ==========
    if not chunks:
        print("[RAG] No chunks to index")
        return  # 没有 chunks 需要索引，直接返回
    
    # ========== 步骤1：获取 embedding 模型和向量维度 ==========
    # 获取统一的 embedding 模型（可能是云端 API 或本地模型）
    embedder = get_text_embedder()
    # 获取向量维度（由 embedding 模型决定，如 384 或 1536）
    dimension = get_dimension(384)  # 默认 384，实际会从模型配置中获取
    
    # ========== 步骤2：创建或使用向量库 ==========
    if store is None:
        # 如果没有提供 store，创建默认的 Qdrant 实例
        store = _create_default_vector_store()
        print(f"[RAG] Created default Qdrant store with dimension {dimension}")
    
    # ========== 步骤3：预处理文本（移除 Markdown 标记） ==========
    # 为什么要预处理？
    # - 移除 Markdown 符号（如 **, #, []()），减少噪声
    # - 统一格式，提升 embedding 质量和检索一致性
    processed_texts = []
    for c in chunks:
        raw_content = c["content"]  # 原始 Markdown 文本
        # 移除 Markdown 标记，保留纯文本
        processed_content = _preprocess_markdown_for_embedding(raw_content)
        processed_texts.append(processed_content)
    
    print(f"[RAG] Embedding start: total_texts={len(processed_texts)} batch_size={batch_size}")
    
    # ========== 步骤4：批量向量化 ==========
    # 为什么要批量处理？提升效率，一次处理多个文本
    vecs: List[List[float]] = []  # 存储所有向量
    
    for i in range(0, len(processed_texts), batch_size):
        # 步骤4.1：获取当前批次的文本
        part = processed_texts[i:i+batch_size]  # 切片获取一批文本
        
        try:
            # 步骤4.2：调用 embedding 模型进行向量化
            # embedder.encode() 内部会处理缓存，避免重复计算
            part_vecs = embedder.encode(part)
            
            # ========== 步骤4.3：标准化向量格式 ==========
            # 为什么要标准化？不同 embedding 模型的返回格式不同：
            # - OpenAI: List[List[float]]
            # - SentenceTransformer: numpy.ndarray
            # - 本地模型: 可能是各种格式
            # 我们需要统一转换为 List[List[float]]
            
            if not isinstance(part_vecs, list):
                # 情况1：返回的是单个 numpy 数组（如只有一个文本）
                if hasattr(part_vecs, "tolist"):
                    part_vecs = [part_vecs.tolist()]  # numpy.ndarray → [[...]]
                else:
                    part_vecs = [list(part_vecs)]  # 其他可迭代对象 → [[...]]
            else:
                # 情况2：返回的是列表，但需要检查内部元素的类型
                if part_vecs and not isinstance(part_vecs[0], (list, tuple)) and hasattr(part_vecs[0], "__len__"):
                    # 情况2.1：列表中的元素是 numpy 数组
                    # 例如：[array([0.1, 0.2]), array([0.3, 0.4])]
                    normalized_vecs = []
                    for v in part_vecs:
                        if hasattr(v, "tolist"):
                            normalized_vecs.append(v.tolist())  # numpy → list
                        else:
                            normalized_vecs.append(list(v))  # 其他 → list
                    part_vecs = normalized_vecs
                elif part_vecs and not isinstance(part_vecs[0], (list, tuple)):
                    # 情况2.2：单个向量被误判为列表
                    # 例如：[0.1, 0.2, 0.3] 应该是 [[0.1, 0.2, 0.3]]
                    if hasattr(part_vecs, "tolist"):
                        part_vecs = [part_vecs.tolist()]
                    else:
                        part_vecs = [list(part_vecs)]
            
            # ========== 步骤4.4：逐个处理向量并检查维度 ==========
            for v in part_vecs:
                try:
                    # 步骤4.4.1：确保向量是 float 列表
                    if hasattr(v, "tolist"):
                        v = v.tolist()  # numpy → list
                    v_norm = [float(x) for x in v]  # 确保每个元素都是 float
                    
                    # 步骤4.4.2：检查向量维度是否正确
                    if len(v_norm) != dimension:
                        print(f"[WARNING] 向量维度异常: 期望{dimension}, 实际{len(v_norm)}")
                        
                        # 维度不匹配时的兜底处理
                        if len(v_norm) < dimension:
                            # 维度不足：用零填充
                            v_norm.extend([0.0] * (dimension - len(v_norm)))
                        else:
                            # 维度过多：截断
                            v_norm = v_norm[:dimension]
                    
                    vecs.append(v_norm)  # 添加到向量列表
                    
                except Exception as e:
                    # 向量转换失败：使用零向量兜底（保证不崩溃）
                    print(f"[WARNING] 向量转换失败: {e}, 使用零向量")
                    vecs.append([0.0] * dimension)
                
        except Exception as e:
            # ========== 步骤4.5：批次失败时的重试机制 ==========
            print(f"[WARNING] Batch {i} encoding failed: {e}")
            print(f"[RAG] Retrying batch {i} with smaller chunks...")
            
            # 为什么要重试？
            # - 云端 API 可能有频率限制
            # - 大批次可能导致超时
            # 策略：将批次分解为更小的块（8个一组）
            success = False
            for j in range(0, len(part), 8):  # 更小的批次
                small_part = part[j:j+8]
                try:
                    import time
                    time.sleep(2)  # 等待2秒避免频率限制
                    
                    small_vecs = embedder.encode(small_part)
                    # Normalize to List[List[float]]
                    if isinstance(small_vecs, list) and small_vecs and not isinstance(small_vecs[0], list):
                        small_vecs = [small_vecs]
                    
                    for v in small_vecs:
                        if hasattr(v, "tolist"):
                            v = v.tolist()
                        try:
                            v_norm = [float(x) for x in v]
                            if len(v_norm) != dimension:
                                print(f"[WARNING] 向量维度异常: 期望{dimension}, 实际{len(v_norm)}")
                                if len(v_norm) < dimension:
                                    v_norm.extend([0.0] * (dimension - len(v_norm)))
                                else:
                                    v_norm = v_norm[:dimension]
                            vecs.append(v_norm)
                            success = True
                        except Exception as e2:
                            print(f"[WARNING] 小批次向量转换失败: {e2}")
                            vecs.append([0.0] * dimension)
                except Exception as e2:
                    print(f"[WARNING] 小批次 {j//8} 仍然失败: {e2}")
                    # 为这个小批次创建零向量
                    for _ in range(len(small_part)):
                        vecs.append([0.0] * dimension)
            
            if not success:
                print(f"[ERROR] 批次 {i} 完全失败，使用零向量")
        
        print(f"[RAG] Embedding progress: {min(i+batch_size, len(processed_texts))}/{len(processed_texts)}")
    
    # ========== 步骤5：组装 metadata 并补充 RAG 专用标签 ==========
    metas: List[Dict] = []  # metadata 列表
    ids: List[str] = []     # chunk ID 列表
    
    for ch in chunks:
        # 步骤5.1：创建基础 metadata（包含 RAG 专用字段）
        meta = {
            "memory_id": ch["id"],  # chunk 的唯一标识符
            "user_id": "rag_user",  # 用户标识（RAG 数据统一使用 "rag_user"）
            "memory_type": "rag_chunk",  # 内存类型标记（用于过滤）
            "content": ch["content"],  # 保留原始 Markdown 内容（用于显示）
            "data_source": "rag_pipeline",  # 数据来源标识（用于过滤）
            "rag_namespace": rag_namespace,  # 命名空间（隔离不同知识库）
            "is_rag_data": True,  # RAG 数据标记（用于过滤）
        }
        
        # 步骤5.2：合并 chunk 自带的 metadata
        # 包含：source_path, file_ext, doc_id, lang, heading_path 等
        meta.update(ch.get("metadata", {}))
        
        metas.append(meta)
        ids.append(ch["id"])
    
    # ========== 步骤6：写入向量库 ==========
    print(f"[RAG] Qdrant upsert start: n={len(vecs)}")
    
    # 调用 store.add_vectors() 批量写入
    # 参数说明：
    # - vectors: 向量列表 List[List[float]]
    # - metadata: 元数据列表 List[Dict]
    # - ids: ID 列表 List[str]
    success = store.add_vectors(vectors=vecs, metadata=metas, ids=ids)
    
    # 步骤6.1：检查写入结果
    if success:
        print(f"[RAG] Qdrant upsert done: {len(vecs)} vectors indexed")
    else:
        # 写入失败：抛出异常（让上层知道出错了）
        print(f"[RAG] Qdrant upsert failed")
        raise RuntimeError("Failed to index vectors to Qdrant")


def embed_query(query: str) -> List[float]:
    """把用户 query 文本转换为向量（embedding）

    教学理解：
    - 向量检索的前提是：**文档 chunk 和 query 必须使用同一个 embedding 模型**。
    - 本项目通过 `get_text_embedder()` 获取统一 embedder（可能是云端 embedding，也可能是本地模型）。

    这个函数做了两类“工程化兜底”，避免检索阶段因为模型返回格式不同而崩溃：
    - 返回值归一化：把 numpy/嵌套列表等情况转成 `List[float]`
    - 维度兜底：如果维度不等于 `get_dimension(384)`，则用填充/截断对齐

    Args:
        query: 用户查询文本。

    Returns:
        List[float]: 长度为 `dimension` 的向量；异常时返回零向量（保证下游不崩）。

     Example:
         >>> vec = embed_query("什么是 RAG？")
         >>> len(vec) == get_dimension(384)
         True
     """
    embedder = get_text_embedder()
    dimension = get_dimension(384)
    try:
        vec = embedder.encode(query)
        
        # Normalize to List[float]
        if hasattr(vec, "tolist"):
            vec = vec.tolist()
        
        # 处理嵌套列表情况
        if isinstance(vec, list) and vec and isinstance(vec[0], (list, tuple)):
            vec = vec[0]  # Extract first vector if nested
        
        # 转换为float列表
        result = [float(x) for x in vec]
        
        # 检查维度
        if len(result) != dimension:
            print(f"[WARNING] Query向量维度异常: 期望{dimension}, 实际{len(result)}")
            # 用零向量填充或截断
            if len(result) < dimension:
                result.extend([0.0] * (dimension - len(result)))
            else:
                result = result[:dimension]
        
        return result
    except Exception as e:
        print(f"[WARNING] Query embedding failed: {e}")
        # Return zero vector as fallback
        return [0.0] * dimension


def search_vectors(
    store = None, 
    query: str = "", 
    top_k: int = 8, 
    rag_namespace: Optional[str] = None, 
    only_rag_data: bool = True, 
    score_threshold: Optional[float] = None
) -> List[Dict]:
    """基础检索：query → embedding → Qdrant 相似搜索

    教学理解：
    - 这是 RAG 的“检索（R）”阶段：把 query 向量化，然后在向量库里找相近向量。
    - 本函数只做“检索”，不做重排/摘要/拼接；上层可以基于结果继续处理。

    过滤条件（where）：
    - 始终要求 `memory_type == "rag_chunk"`
    - `only_rag_data=True` 时，会额外要求 `is_rag_data=True` 与 `data_source="rag_pipeline"`
    - 如果提供 `rag_namespace`，会再加上命名空间过滤

    Args:
        store: 向量库实例。None 时创建默认 Qdrant store。
        query: 用户查询。
        top_k: 返回 top_k 条结果。
        rag_namespace: 命名空间过滤（隔离不同知识库）。
        only_rag_data: 是否只检索本 pipeline 写入的 RAG 数据。
        score_threshold: 相似度阈值（低于该阈值的结果可能被过滤，取决于 store 实现）。

    Returns:
        List[Dict]: 检索命中列表（结构由 `store.search_similar` 决定）。通常包含：
        - `score`: 相似度
        - `metadata`: 含 `content/source_path/heading_path/...`

    Example:
        >>> pipeline = create_rag_pipeline(rag_namespace="default")
        >>> _ = pipeline["add_documents"](["./docs/intro.pdf"])
        >>> hits = search_vectors(store=pipeline["store"], query="RAG", top_k=3, rag_namespace="default")
        >>> hits[0].keys()
        dict_keys(['id', 'score', 'metadata'])
    """
    if not query:
        return []
    
    # Create default store if not provided
    if store is None:
        store = _create_default_vector_store()
    
    # Embed query with unified embedder
    qv = embed_query(query)
    
    # Build filter for RAG data
    where = {"memory_type": "rag_chunk"}
    if only_rag_data:
        where["is_rag_data"] = True
        where["data_source"] = "rag_pipeline"
    if rag_namespace:
        where["rag_namespace"] = rag_namespace
    
    try:
        return store.search_similar(
            query_vector=qv, 
            limit=top_k, 
            score_threshold=score_threshold, 
            where=where
        )
    except Exception as e:
        print(f"[WARNING] RAG search failed: {e}")
        return []


def search_vectors_expanded(
    store = None,
    query: str = "",
    top_k: int = 8,
    rag_namespace: Optional[str] = None,
    only_rag_data: bool = True,
    score_threshold: Optional[float] = None,
    enable_mqe: bool = False,
    mqe_expansions: int = 2,
    enable_hyde: bool = False,
    candidate_pool_multiplier: int = 4,
) -> List[Dict]:
    """高级检索：查询扩展（MQE/HyDE）+ 多路检索结果聚合

    教学理解（为什么要“扩展查询”）：
    - 用户的 query 可能太短/歧义大，单次检索容易漏召回。
    - 让 LLM 生成多个“不同说法”的查询，再分别检索，可以提升召回率。

    扩展来源：
    - MQE（Multi-Query Expansion）：`_prompt_mqe(query, n)` 生成 n 个改写查询。
    - HyDE（Hypothetical Document Embeddings）：`_prompt_hyde(query)` 生成一段“假想答案段落”，
      将其视作 query 文本来检索（有时能更贴近文档表述）。

    聚合方式：
    - 每个扩展 query 都会进行一次向量搜索
    - 结果按 `memory_id` 去重：同一个 chunk 只保留最高分
    - 最终按 score 排序，返回 top_k

    Args:
        store: 向量库实例。
        query: 原始 query。
        top_k: 最终返回条数。
        rag_namespace: 命名空间过滤。
        only_rag_data: 是否只检索本 pipeline 写入的数据。
        score_threshold: 相似度阈值。
        enable_mqe: 是否启用 MQE。
        mqe_expansions: MQE 生成的扩展 query 数量。
        enable_hyde: 是否启用 HyDE。
        candidate_pool_multiplier: 候选池倍率；越大表示每路检索拉回更多候选用于聚合。

    Returns:
        List[Dict]: 聚合后的 top_k 命中结果。

    Example:
        >>> pipeline = create_rag_pipeline(rag_namespace="default")
        >>> _ = pipeline["add_documents"](["./docs/intro.pdf"])
        >>> hits = search_vectors_expanded(
        ...     store=pipeline["store"],
        ...     query="RAG 的索引流程",
        ...     top_k=5,
        ...     rag_namespace="default",
        ...     enable_mqe=True,
        ...     enable_hyde=True,
        ... )
        >>> len(hits)
        5
    """
    if not query:
        return []
    
    # Create default store if not provided
    if store is None:
        store = _create_default_vector_store()
    
    # expansions
    expansions: List[str] = [query]
    
    if enable_mqe and mqe_expansions > 0:
        expansions.extend(_prompt_mqe(query, mqe_expansions))
    if enable_hyde:
        hyde_text = _prompt_hyde(query)
        if hyde_text:
            expansions.append(hyde_text)

    # unique and trim
    uniq: List[str] = []
    for e in expansions:
        if e and e not in uniq:
            uniq.append(e)
    expansions = uniq[: max(1, len(uniq))]

    # distribute pool per expansion
    pool = max(top_k * candidate_pool_multiplier, 20)
    per = max(1, pool // max(1, len(expansions)))

    # Build filter for RAG data
    where = {"memory_type": "rag_chunk"}
    if only_rag_data:
        where["is_rag_data"] = True
        where["data_source"] = "rag_pipeline"
    if rag_namespace:
        where["rag_namespace"] = rag_namespace

    # collect hits across expansions
    agg: Dict[str, Dict] = {}
    for q in expansions:
        qv = embed_query(q)
        hits = store.search_similar(query_vector=qv, limit=per, score_threshold=score_threshold, where=where)
        for h in hits:
            mid = h.get("metadata", {}).get("memory_id", h.get("id"))
            s = float(h.get("score", 0.0))
            if mid not in agg or s > float(agg[mid].get("score", 0.0)):
                agg[mid] = h
    # return top by score
    merged = list(agg.values())
    merged.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    return merged[:top_k]


def _try_load_cross_encoder(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder(model_name)
    except Exception:
        return None


def rerank_with_cross_encoder(query: str, items: List[Dict], model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_k: int = 10) -> List[Dict]:
    ce = _try_load_cross_encoder(model_name)
    if ce is None or not items:
        return items[:top_k]
    pairs = [[query, it.get("content", "")] for it in items]
    try:
        scores = ce.predict(pairs)
        for it, s in zip(items, scores):
            it["rerank_score"] = float(s)
        items.sort(key=lambda x: x.get("rerank_score", x.get("score", 0.0)), reverse=True)
        return items[:top_k]
    except Exception:
        return items[:top_k]


def compute_graph_signals_from_pool(vector_hits: List[Dict], same_doc_weight: float = 1.0, proximity_weight: float = 1.0, proximity_window_chars: int = 1600) -> Dict[str, float]:
    """
    Compute graph signals with direct parameters instead of environment variables.
    """

    # group by doc
    by_doc: Dict[str, List[Dict]] = {}
    for h in vector_hits:
        meta = h.get("metadata", {})
        did = meta.get("doc_id")
        if not did:
            # fall back to memory_id grouping if doc missing
            did = meta.get("memory_id") or h.get("id")
        by_doc.setdefault(did, []).append(h)

    # same-doc density score
    doc_counts = {d: len(arr) for d, arr in by_doc.items()}
    max_count = max(doc_counts.values()) if doc_counts else 1

    # proximity score per hit within same doc
    graph_signal: Dict[str, float] = {}
    for did, arr in by_doc.items():
        arr.sort(key=lambda x: x.get("metadata", {}).get("start", 0))
        # precompute density
        density = doc_counts.get(did, 1) / max_count
        # proximity accumulation
        for i, h in enumerate(arr):
            mid = h.get("metadata", {}).get("memory_id", h.get("id"))
            pos_i = h.get("metadata", {}).get("start", 0)
            prox_acc = 0.0
            # look around neighbors within window
            # two-pointer expansion
            # left
            j = i - 1
            while j >= 0:
                pos_j = arr[j].get("metadata", {}).get("start", 0)
                dist = abs(pos_i - pos_j)
                if dist > proximity_window_chars:
                    break
                prox_acc += max(0.0, 1.0 - (dist / max(1.0, float(proximity_window_chars))))
                j -= 1
            # right
            j = i + 1
            while j < len(arr):
                pos_j = arr[j].get("metadata", {}).get("start", 0)
                dist = abs(pos_i - pos_j)
                if dist > proximity_window_chars:
                    break
                prox_acc += max(0.0, 1.0 - (dist / max(1.0, float(proximity_window_chars))))
                j += 1
            # combine
            score = same_doc_weight * density + proximity_weight * prox_acc
            graph_signal[mid] = graph_signal.get(mid, 0.0) + score

    # normalize to [0,1]
    if graph_signal:
        max_v = max(graph_signal.values())
        if max_v > 0:
            for k in list(graph_signal.keys()):
                graph_signal[k] = graph_signal[k] / max_v
    return graph_signal


def rank(vector_hits: List[Dict], graph_signals: Optional[Dict[str, float]] = None, w_vector: float = 0.7, w_graph: float = 0.3) -> List[Dict]:
    """
    Rank results with direct weight parameters instead of environment variables.
    """
    items: List[Dict] = []
    graph_signals = graph_signals or {}
    for h in vector_hits:
        mid = h.get("metadata", {}).get("memory_id", h.get("id"))
        g = float(graph_signals.get(mid, 0.0))
        v = float(h.get("score", 0.0))
        score = w_vector * v + w_graph * g
        items.append({
            "memory_id": mid,
            "score": score,
            "vector_score": v,
            "graph_score": g,
            "content": h.get("metadata", {}).get("content", ""),
            "metadata": h.get("metadata", {}),
        })
    items.sort(key=lambda x: x["score"], reverse=True)
    return items


def merge_snippets(ranked_items: List[Dict], max_chars: int = 1200) -> str:
    out: List[str] = []
    total = 0
    for it in ranked_items:
        text = it.get("content", "").strip()
        if not text:
            continue
        if total + len(text) > max_chars:
            remain = max_chars - total
            if remain <= 0:
                break
            out.append(text[:remain])
            total += remain
            break
        out.append(text)
        total += len(text)
    return "\n\n".join(out)


def expand_neighbors_from_pool(selected: List[Dict], pool: List[Dict], neighbors: int = 1, max_additions: int = 5) -> List[Dict]:
    if not selected or not pool or neighbors <= 0:
        return selected
    # index pool by doc_id and sort by start
    by_doc: Dict[str, List[Dict]] = {}
    for it in pool:
        meta = it.get("metadata", {})
        did = meta.get("doc_id")
        if not did:
            continue
        by_doc.setdefault(did, []).append(it)
    for did, arr in by_doc.items():
        arr.sort(key=lambda x: (x.get("metadata", {}).get("start", 0)))
    selected_ids = set(it.get("memory_id") for it in selected)
    additions: List[Dict] = []
    for it in selected:
        meta = it.get("metadata", {})
        did = meta.get("doc_id")
        if not did or did not in by_doc:
            continue
        arr = by_doc[did]
        # find index
        try:
            idx = next(i for i, x in enumerate(arr) if x.get("memory_id") == it.get("memory_id"))
        except StopIteration:
            continue
        for offset in range(1, neighbors + 1):
            for j in (idx - offset, idx + offset):
                if 0 <= j < len(arr):
                    cand = arr[j]
                    mid = cand.get("memory_id")
                    if mid not in selected_ids:
                        additions.append(cand)
                        selected_ids.add(mid)
                        if len(additions) >= max_additions:
                            break
            if len(additions) >= max_additions:
                break
        if len(additions) >= max_additions:
            break
    # keep relative order by score
    extended = list(selected) + additions
    extended.sort(key=lambda x: (x.get("rerank_score", x.get("score", 0.0))), reverse=True)
    return extended


def merge_snippets_grouped(ranked_items: List[Dict], max_chars: int = 1200, include_citations: bool = True) -> str:
    # Group by doc_id and aggregate doc score
    by_doc: Dict[str, List[Dict]] = {}
    doc_score: Dict[str, float] = {}
    for it in ranked_items:
        meta = it.get("metadata", {})
        did = meta.get("doc_id") or meta.get("source_path") or "unknown"
        by_doc.setdefault(did, []).append(it)
        doc_score[did] = doc_score.get(did, 0.0) + float(it.get("score", 0.0))
    # Sort docs by aggregate score
    ordered_docs = sorted(by_doc.keys(), key=lambda d: doc_score.get(d, 0.0), reverse=True)
    # Within doc, order by start offset to preserve context
    for d in ordered_docs:
        by_doc[d].sort(key=lambda x: (x.get("metadata", {}).get("start", 0)))
    out: List[str] = []
    citations: List[Dict] = []
    total = 0
    cite_index = 1
    for did in ordered_docs:
        parts = by_doc[did]
        for it in parts:
            text = (it.get("content", "") or "").strip()
            if not text:
                continue
            # add citation marker if enabled
            suffix = ""
            if include_citations:
                suffix = f" [{cite_index}]"
            need = len(text) + (len(suffix) if suffix else 0)
            if total + need > max_chars:
                remain = max_chars - total
                if remain <= 0:
                    break
                clipped = text[: max(0, remain - len(suffix))]
                if clipped:
                    out.append(clipped + suffix)
                    total += len(clipped) + len(suffix)
                    if include_citations:
                        m = it.get("metadata", {})
                        citations.append({
                            "index": cite_index,
                            "source_path": m.get("source_path"),
                            "doc_id": m.get("doc_id"),
                            "start": m.get("start"),
                            "end": m.get("end"),
                            "heading_path": m.get("heading_path"),
                        })
                        cite_index += 1
                break
            out.append(text + suffix)
            total += need
            if include_citations:
                m = it.get("metadata", {})
                citations.append({
                    "index": cite_index,
                    "source_path": m.get("source_path"),
                    "doc_id": m.get("doc_id"),
                    "start": m.get("start"),
                    "end": m.get("end"),
                    "heading_path": m.get("heading_path"),
                })
                cite_index += 1
        if total >= max_chars:
            break
    merged = "\n\n".join(out)
    if include_citations and citations:
        lines: List[str] = [merged, "", "References:"]
        for c in citations:
            loc = ""
            if c.get("start") is not None and c.get("end") is not None:
                loc = f" ({c['start']}-{c['end']})"
            hp = f" – {c['heading_path']}" if c.get("heading_path") else ""
            sp = c.get("source_path") or c.get("doc_id") or "source"
            lines.append(f"[{c['index']}] {sp}{loc}{hp}")
        return "\n".join(lines)
    return merged


def compress_ranked_items(ranked_items: List[Dict], enable_compression: bool = True, max_per_doc: int = 2, join_gap: int = 200) -> List[Dict]:
    """
    Compress ranked items with direct parameters instead of environment variables.
    """
    if not enable_compression:
        return ranked_items
    by_doc_count: Dict[str, int] = {}
    last_by_doc: Dict[str, Dict] = {}
    new_items: List[Dict] = []
    for it in ranked_items:
        meta = it.get("metadata", {})
        did = meta.get("doc_id") or meta.get("source_path") or "unknown"
        start = int(meta.get("start") or 0)
        end = int(meta.get("end") or (start + len(it.get("content", "") or "")))
        if did not in last_by_doc:
            last_by_doc[did] = it
            by_doc_count[did] = 1
            new_items.append(it)
            continue
        last = last_by_doc[did]
        lmeta = last.get("metadata", {})
        lstart = int(lmeta.get("start") or 0)
        lend = int(lmeta.get("end") or (lstart + len(last.get("content", "") or "")))
        if start - lend <= join_gap and start >= lstart:
            # merge into last
            merged_text = (last.get("content", "") or "").strip()
            add_text = (it.get("content", "") or "").strip()
            if add_text:
                if merged_text:
                    merged_text = merged_text + "\n\n" + add_text
                else:
                    merged_text = add_text
                last["content"] = merged_text
                lmeta["end"] = max(lend, end)
                # keep the higher score
                try:
                    last["score"] = max(float(last.get("score", 0.0)), float(it.get("score", 0.0)))
                except Exception:
                    pass
            last_by_doc[did] = last
        else:
            cnt = by_doc_count.get(did, 0)
            if cnt >= max_per_doc:
                continue
            new_items.append(it)
            last_by_doc[did] = it
            by_doc_count[did] = cnt + 1
    return new_items


def tldr_summarize(text: str, bullets: int = 3) -> Optional[str]:
    try:
        if not text or len(text.strip()) == 0:
            return None
        from ...core.llm import HelloAgentsLLM
        llm = HelloAgentsLLM()
        prompt = [
            {"role": "system", "content": "请将以下内容概括为简洁的要点列表（最多3-5条），用中文，避免重复，突出关键信息。"},
            {"role": "user", "content": f"请用 {max(1, min(5, int(bullets)))} 条要点总结：\n\n{text}"},
        ]
        out = llm.invoke(prompt)
        return out
    except Exception:
        return None

# High-level RAG Pipeline API
# ==================

def create_rag_pipeline(
    qdrant_url: Optional[str] = None,
    qdrant_api_key: Optional[str] = None,
    collection_name: str = "hello_agents_rag_vectors",
    rag_namespace: str = "default"
) -> Dict[str, Any]:
    """创建一个可直接给上层调用的 RAG Pipeline（工厂函数）

    教学理解：
    - 这个函数把“向量库（Qdrant）”和“若干操作函数（入库/检索/统计）”打包成一个 dict。
    - 上层（例如 `RAGTool`）拿到这个 dict，就可以通过 key 调用，而不需要了解内部细节。

    返回的 pipeline（dict）是一个轻量 Facade，常用 key：
    - `pipeline["store"]`: QdrantVectorStore
    - `pipeline["namespace"]`: str
    - `pipeline["add_documents"](file_paths, chunk_size, chunk_overlap) -> int`
    - `pipeline["search"](query, top_k, score_threshold) -> List[Dict]`
    - `pipeline["search_advanced"](query, top_k, enable_mqe, enable_hyde, score_threshold) -> List[Dict]`
    - `pipeline["get_stats"]() -> Dict[str, Any]`

    Args:
        qdrant_url: Qdrant 服务地址（None 时由 store 自行处理/读取环境变量）。
        qdrant_api_key: Qdrant API Key。
        collection_name: Qdrant collection 名称。
        rag_namespace: 逻辑命名空间（会写入 metadata 并用于检索过滤）。

    Returns:
        Dict[str, Any]: 如上所述的 pipeline dict。

    Example:
        >>> pipeline = create_rag_pipeline(rag_namespace="default")
        >>> pipeline.keys()
        dict_keys(['store', 'namespace', 'add_documents', 'search', 'search_advanced', 'get_stats'])
        >>> n = pipeline["add_documents"](["./docs/intro.pdf"], chunk_size=800, chunk_overlap=100)
        >>> hits = pipeline["search"]("RAG", top_k=3)
        >>> stats = pipeline["get_stats"]()
    """
    dimension = get_dimension(384)
    
    store = QdrantVectorStore(
        url=qdrant_url,
        api_key=qdrant_api_key,
        collection_name=collection_name,
        vector_size=dimension,
        distance="cosine"
    )
    
    def add_documents(file_paths: List[str], chunk_size: int = 800, chunk_overlap: int = 100):
        """入库：文件路径列表 → chunks → embedding → 写入向量库

        Args:
            file_paths: 待入库文件路径列表。
            chunk_size: chunk 目标大小。
            chunk_overlap: chunk 重叠大小。

        Returns:
            int: 本次成功写入的 chunk 数量（便于上层显示/统计）。
        """
        chunks = load_and_chunk_texts(
            paths=file_paths,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            namespace=rag_namespace,
            source_label="rag"
        )
        index_chunks(
            store=store,
            chunks=chunks,
            rag_namespace=rag_namespace
        )
        return len(chunks)
    
    def search(query: str, top_k: int = 8, score_threshold: Optional[float] = None):
        """基础检索：直接对 query 做向量搜索"""
        return search_vectors(
            store=store,
            query=query,
            top_k=top_k,
            rag_namespace=rag_namespace,
            score_threshold=score_threshold
        )
    
    def search_advanced(
        query: str, 
        top_k: int = 8, 
        enable_mqe: bool = False,
        enable_hyde: bool = False,
        score_threshold: Optional[float] = None
    ):
        """高级检索：可选 MQE/HyDE 查询扩展，提高召回率"""
        return search_vectors_expanded(
            store=store,
            query=query,
            top_k=top_k,
            rag_namespace=rag_namespace,
            enable_mqe=enable_mqe,
            enable_hyde=enable_hyde,
            score_threshold=score_threshold
        )
    
    def get_stats():
        """获取向量库统计信息（collection 条数/维度/距离度量等，由 store 提供）"""
        return store.get_collection_stats()
    
    return {
        "store": store,
        "namespace": rag_namespace,
        "add_documents": add_documents,
        "search": search,
        "search_advanced": search_advanced,
        "get_stats": get_stats
    }