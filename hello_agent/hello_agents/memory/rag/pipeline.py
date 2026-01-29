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
    if not os.path.exists(path):
        return ""
    
    # 对PDF文件使用增强处理
    ext = (os.path.splitext(path)[1] or '').lower()
    if ext == '.pdf':
        return _enhanced_pdf_processing(path)
    
    # 其他格式使用原有MarkItDown
    md_instance = _get_markitdown_instance()
    if md_instance is None:
        return _fallback_text_reader(path)
    
    try:
        result = md_instance.convert(path)
        text = getattr(result, "text_content", None)
        if isinstance(text, str) and text.strip():
            return text
        return ""
    except Exception as e:
        print(f"[WARNING] MarkItDown failed for {path}: {e}")
        return _fallback_text_reader(path)

def _enhanced_pdf_processing(path: str) -> str:
    """
    Enhanced PDF processing with post-processing cleanup.
    """
    print(f"[RAG] Using enhanced PDF processing for: {path}")
    
    # 使用原有MarkItDown提取
    md_instance = _get_markitdown_instance()
    if md_instance is None:
        return _fallback_text_reader(path)
    
    try:
        result = md_instance.convert(path)
        raw_text = getattr(result, "text_content", None)
        if not raw_text or not raw_text.strip():
            return ""
        
        # 后处理：清理和重组文本
        cleaned_text = _post_process_pdf_text(raw_text)
        print(f"[RAG] PDF post-processing completed: {len(raw_text)} -> {len(cleaned_text)} chars")
        return cleaned_text
        
    except Exception as e:
        print(f"[WARNING] Enhanced PDF processing failed for {path}: {e}")
        return _fallback_text_reader(path)

def _post_process_pdf_text(text: str) -> str:
    """
    Post-process PDF text to improve quality.
    """
    import re
    
    # 1. 按行分割并清理
    lines = text.splitlines()
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 移除单个字符的行（通常是噪音）
        if len(line) <= 2 and not line.isdigit():
            continue
            
        # 移除明显的页眉页脚噪音
        if re.match(r'^\d+$', line):  # 纯数字行（页码）
            continue
        if line.lower() in ['github', 'project', 'forks', 'stars', 'language']:
            continue
            
        cleaned_lines.append(line)
    
    # 2. 智能合并短行
    merged_lines = []
    i = 0
    
    while i < len(cleaned_lines):
        current_line = cleaned_lines[i]
        
        # 如果当前行很短，尝试与下一行合并
        if len(current_line) < 60 and i + 1 < len(cleaned_lines):
            next_line = cleaned_lines[i + 1]
            
            # 合并条件：都是内容，不是标题
            if (not current_line.endswith('：') and 
                not current_line.endswith(':') and
                not current_line.startswith('#') and
                not next_line.startswith('#') and
                len(next_line) < 120):
                
                merged_line = current_line + " " + next_line
                merged_lines.append(merged_line)
                i += 2  # 跳过下一行
                continue
        
        merged_lines.append(current_line)
        i += 1
    
    # 3. 重新组织段落
    paragraphs = []
    current_paragraph = []
    
    for line in merged_lines:
        # 检查是否是新段落的开始
        if (line.startswith('#') or  # 标题
            line.endswith('：') or   # 中文冒号结尾
            line.endswith(':') or    # 英文冒号结尾
            len(line) > 150 or       # 长句通常是段落开始
            not current_paragraph):  # 第一行
            
            # 保存当前段落
            if current_paragraph:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
            
            paragraphs.append(line)
        else:
            current_paragraph.append(line)
    
    # 添加最后一个段落
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    
    return '\n\n'.join(paragraphs)


def _fallback_text_reader(path: str) -> str:
    """
    Simple fallback reader for basic text files when MarkItDown is unavailable.
    """
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        try:
            with open(path, 'r', encoding='latin-1', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""


def _detect_lang(sample: str) -> str:
    try:
        from langdetect import detect
        return detect(sample[:1000]) if sample else "unknown"
    except Exception:
        return "unknown"


def _is_cjk(ch: str) -> bool:
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
    # 近似估计：CJK字符按1 token，其他按空白分词
    cjk = sum(1 for ch in text if _is_cjk(ch))
    non_cjk_tokens = len([t for t in text.split() if t])
    return cjk + non_cjk_tokens


def _split_paragraphs_with_headings(text: str) -> List[Dict]:
    lines = text.splitlines()
    heading_stack: List[str] = []
    paragraphs: List[Dict] = []
    buf: List[str] = []
    char_pos = 0
    def flush_buf(end_pos: int):
        if not buf:
            return
        content = "\n".join(buf).strip()
        if not content:
            return
        paragraphs.append({
            "content": content,
            "heading_path": " > ".join(heading_stack) if heading_stack else None,
            "start": max(0, end_pos - len(content)),
            "end": end_pos,
        })
    for ln in lines:
        raw = ln
        if raw.strip().startswith("#"):
            # heading line
            flush_buf(char_pos)
            level = len(raw) - len(raw.lstrip('#'))
            title = raw.lstrip('#').strip()
            if level <= 0:
                level = 1
            if level <= len(heading_stack):
                heading_stack = heading_stack[:level-1]
            heading_stack.append(title)
            char_pos += len(raw) + 1
            continue
        # paragraph accumulation
        if raw.strip() == "":
            flush_buf(char_pos)
            buf = []
        else:
            buf.append(raw)
        char_pos += len(raw) + 1
    flush_buf(char_pos)
    if not paragraphs:
        paragraphs = [{"content": text, "heading_path": None, "start": 0, "end": len(text)}]
    return paragraphs


def _chunk_paragraphs(paragraphs: List[Dict], chunk_tokens: int, overlap_tokens: int) -> List[Dict]:
    chunks: List[Dict] = []
    cur: List[Dict] = []
    cur_tokens = 0
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        p_tokens = _approx_token_len(p["content"]) or 1
        if cur_tokens + p_tokens <= chunk_tokens or not cur:
            cur.append(p)
            cur_tokens += p_tokens
            i += 1
        else:
            # emit current chunk
            content = "\n\n".join(x["content"] for x in cur)
            start = cur[0]["start"]
            end = cur[-1]["end"]
            heading_path = next((x["heading_path"] for x in reversed(cur) if x.get("heading_path")), None)
            chunks.append({
                "content": content,
                "start": start,
                "end": end,
                "heading_path": heading_path,
            })
            # build overlap by keeping tail tokens
            if overlap_tokens > 0 and cur:
                kept: List[Dict] = []
                kept_tokens = 0
                for x in reversed(cur):
                    t = _approx_token_len(x["content"]) or 1
                    if kept_tokens + t > overlap_tokens:
                        break
                    kept.append(x)
                    kept_tokens += t
                cur = list(reversed(kept))
                cur_tokens = kept_tokens
            else:
                cur = []
                cur_tokens = 0
    if cur:
        content = "\n\n".join(x["content"] for x in cur)
        start = cur[0]["start"]
        end = cur[-1]["end"]
        heading_path = next((x["heading_path"] for x in reversed(cur) if x.get("heading_path")), None)
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
    print(f"[RAG] Universal loader start: files={len(paths)} chunk_size={chunk_size} overlap={chunk_overlap} ns={namespace or 'default'}")
    chunks: List[Dict] = []
    seen_hashes = set()
    
    for path in paths:
        if not os.path.exists(path):
            print(f"[WARNING] File not found: {path}")
            continue
            
        print(f"[RAG] Processing: {path}")
        ext = (os.path.splitext(path)[1] or '').lower()
        
        # Convert to markdown using MarkItDown
        markdown_text = _convert_to_markdown(path)
        if not markdown_text.strip():
            print(f"[WARNING] No content extracted from: {path}")
            continue
        
        lang = _detect_lang(markdown_text)
        doc_id = hashlib.md5(f"{path}|{len(markdown_text)}".encode('utf-8')).hexdigest()
        
        # Always use markdown-aware chunking for better structure preservation
        para = _split_paragraphs_with_headings(markdown_text)
        token_chunks = _chunk_paragraphs(para, chunk_tokens=max(1, chunk_size), overlap_tokens=max(0, chunk_overlap))
        
        for ch in token_chunks:
            content = ch["content"]
            start = ch.get("start", 0)
            end = ch.get("end", start + len(content))
            norm = content.strip()
            if not norm:
                continue
                
            content_hash = hashlib.md5(norm.encode('utf-8')).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            
            chunk_id = hashlib.md5(f"{doc_id}|{start}|{end}|{content_hash}".encode('utf-8')).hexdigest()
            chunks.append({
                "id": chunk_id,
                "content": content,
                "metadata": {
                    "source_path": path,
                    "file_ext": ext,
                    "doc_id": doc_id,
                    "lang": lang,
                    "start": start,
                    "end": end,
                    "content_hash": content_hash,
                    "namespace": namespace or "default",
                    "source": source_label,
                    "external": True,
                    "heading_path": ch.get("heading_path"),
                    "format": "markdown",  # Mark all content as markdown-processed
                },
            })
            
    print(f"[RAG] Universal loader done: total_chunks={len(chunks)}")
    return chunks


def build_graph_from_chunks(neo4j, chunks: List[Dict]) -> None:
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
    """
    Preprocess markdown text for better embedding quality.
    Removes excessive markup while preserving semantic content.
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
    """
    Create default Qdrant vector store with RAG-optimized settings.
    使用连接管理器避免重复连接。
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
    if not chunks:
        print("[RAG] No chunks to index")
        return
    
    # Use unified embedding from embedding module
    embedder = get_text_embedder()
    dimension = get_dimension(384)
    
    # Create default Qdrant store if not provided
    if store is None:
        store = _create_default_vector_store()
        print(f"[RAG] Created default Qdrant store with dimension {dimension}")
    
    # Preprocess markdown texts for better embeddings
    processed_texts = []
    for c in chunks:
        raw_content = c["content"]
        processed_content = _preprocess_markdown_for_embedding(raw_content)
        processed_texts.append(processed_content)
    
    print(f"[RAG] Embedding start: total_texts={len(processed_texts)} batch_size={batch_size}")
    
    # Batch encoding with unified embedder
    vecs: List[List[float]] = []
    for i in range(0, len(processed_texts), batch_size):
        part = processed_texts[i:i+batch_size]
        try:
            # Use unified embedder directly (handles caching internally)
            part_vecs = embedder.encode(part)
            
            # Normalize to List[List[float]]
            if not isinstance(part_vecs, list):
                # 单个numpy数组转为列表中的列表
                if hasattr(part_vecs, "tolist"):
                    part_vecs = [part_vecs.tolist()]
                else:
                    part_vecs = [list(part_vecs)]
            else:
                # 检查是否是嵌套列表
                if part_vecs and not isinstance(part_vecs[0], (list, tuple)) and hasattr(part_vecs[0], "__len__"):
                    # numpy数组列表 -> 转换每个数组
                    normalized_vecs = []
                    for v in part_vecs:
                        if hasattr(v, "tolist"):
                            normalized_vecs.append(v.tolist())
                        else:
                            normalized_vecs.append(list(v))
                    part_vecs = normalized_vecs
                elif part_vecs and not isinstance(part_vecs[0], (list, tuple)):
                    # 单个向量被误判为列表，实际应该包装成[[...]]
                    if hasattr(part_vecs, "tolist"):
                        part_vecs = [part_vecs.tolist()]
                    else:
                        part_vecs = [list(part_vecs)]
            
            for v in part_vecs:
                try:
                    # 确保向量是float列表
                    if hasattr(v, "tolist"):
                        v = v.tolist()
                    v_norm = [float(x) for x in v]
                    if len(v_norm) != dimension:
                        print(f"[WARNING] 向量维度异常: 期望{dimension}, 实际{len(v_norm)}")
                        # 用零向量填充或截断
                        if len(v_norm) < dimension:
                            v_norm.extend([0.0] * (dimension - len(v_norm)))
                        else:
                            v_norm = v_norm[:dimension]
                    vecs.append(v_norm)
                except Exception as e:
                    print(f"[WARNING] 向量转换失败: {e}, 使用零向量")
                    vecs.append([0.0] * dimension)
                
        except Exception as e:
            print(f"[WARNING] Batch {i} encoding failed: {e}")
            print(f"[RAG] Retrying batch {i} with smaller chunks...")
            
            # 尝试重试：将批次分解为更小的块
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
    
    # Prepare metadata with RAG tags
    metas: List[Dict] = []
    ids: List[str] = []
    for ch in chunks:
        meta = {
            "memory_id": ch["id"],
            "user_id": "rag_user",
            "memory_type": "rag_chunk",
            "content": ch["content"],  # Keep original markdown content
            "data_source": "rag_pipeline",  # RAG identification tag
            "rag_namespace": rag_namespace,
            "is_rag_data": True,  # Clear RAG data marker
        }
        # Merge chunk metadata
        meta.update(ch.get("metadata", {}))
        metas.append(meta)
        ids.append(ch["id"])
    
    print(f"[RAG] Qdrant upsert start: n={len(vecs)}")
    success = store.add_vectors(vectors=vecs, metadata=metas, ids=ids)
    if success:
        print(f"[RAG] Qdrant upsert done: {len(vecs)} vectors indexed")
    else:
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