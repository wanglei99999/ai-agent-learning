"""文档处理模块（早期实现，已废弃）

注意：这是早期的面向对象实现，当前系统使用 pipeline.py 中的字典结构。
这个文件保留用于参考和兼容性，但实际项目中不再使用。

主要区别：
- 早期实现：使用类（Document, DocumentChunk）
- 当前实现：使用字典 {"id": ..., "content": ..., "metadata": {...}}
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib

@dataclass
class Document:
    """文档类（早期实现）
    
    教学理解：
    - 这是面向对象的设计，将文档封装为一个类
    - 当前 pipeline.py 使用字典结构，更简单灵活
    
    属性：
        content: 文档内容（完整文本）
        metadata: 元数据字典（来源、类型等信息）
        doc_id: 文档唯一标识符（自动生成）
    """
    content: str
    metadata: Dict[str, Any]
    doc_id: Optional[str] = None
    
    def __post_init__(self):
        """初始化后自动执行的方法"""
        if self.doc_id is None:
            # ========== 自动生成文档 ID ==========
            # 使用 MD5 哈希基于内容生成唯一 ID
            # 相同内容 → 相同 ID（用于去重）
            self.doc_id = hashlib.md5(self.content.encode()).hexdigest()

@dataclass 
class DocumentChunk:
    """文档块类（早期实现）
    
    教学理解：
    - 表示文档的一个片段（chunk）
    - 当前 pipeline.py 使用字典：{"id": ..., "content": ..., "metadata": {...}}
    
    属性：
        content: chunk 内容
        metadata: 元数据（包含文档信息、位置等）
        chunk_id: chunk 唯一标识符（自动生成）
        doc_id: 所属文档的 ID
        chunk_index: chunk 在文档中的索引（第几个 chunk）
    """
    content: str
    metadata: Dict[str, Any]
    chunk_id: Optional[str] = None
    doc_id: Optional[str] = None
    chunk_index: int = 0
    
    def __post_init__(self):
        """初始化后自动执行的方法"""
        if self.chunk_id is None:
            # ========== 自动生成 chunk ID ==========
            # 组合：文档ID + chunk索引 + 内容前50字符
            # 确保 chunk ID 的唯一性和稳定性
            chunk_content = f"{self.doc_id}_{self.chunk_index}_{self.content[:50]}"
            self.chunk_id = hashlib.md5(chunk_content.encode()).hexdigest()

class DocumentProcessor:
    """文档处理器（早期实现）
    
    教学理解：
    - 负责将文档切分为 chunks
    - 当前 pipeline.py 使用函数式设计：
      - _split_paragraphs_with_headings()
      - _chunk_paragraphs()
    
    参数：
        chunk_size: chunk 目标大小（字符数）
        chunk_overlap: chunk 重叠大小（字符数）
        separators: 分隔符列表（优先级从高到低）
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ):
        # ========== 初始化参数 ==========
        self.chunk_size = chunk_size          # chunk 大小
        self.chunk_overlap = chunk_overlap    # 重叠大小
        # 分隔符优先级：段落 > 句子 > 标点 > 空格
        self.separators = separators or ["\n\n", "\n", "。", ".", " "]
    
    def process_document(self, document: Document) -> List[DocumentChunk]:
        """
        处理文档，分割成块
        
        Args:
            document: 输入文档
            
        Returns:
            文档块列表
        """
        # ========== 步骤1：切分文本 ==========
        # 调用 _split_text() 将文档内容切分为多个文本片段
        chunks = self._split_text(document.content)
        
        # ========== 步骤2：创建 DocumentChunk 对象 ==========
        document_chunks = []
        for i, chunk_content in enumerate(chunks):
            # 步骤2.1：复制文档元数据
            chunk_metadata = document.metadata.copy()
            
            # 步骤2.2：添加 chunk 特定的元数据
            chunk_metadata.update({
                "doc_id": document.doc_id,           # 所属文档 ID
                "chunk_index": i,                    # chunk 索引
                "total_chunks": len(chunks),         # 总 chunk 数
                "processed_at": datetime.now().isoformat()  # 处理时间
            })
            
            # 步骤2.3：创建 DocumentChunk 对象
            chunk = DocumentChunk(
                content=chunk_content,
                metadata=chunk_metadata,
                doc_id=document.doc_id,
                chunk_index=i
            )
            document_chunks.append(chunk)
        
        return document_chunks
    
    def process_documents(self, documents: List[Document]) -> List[DocumentChunk]:
        """
        批量处理文档
        
        Args:
            documents: 文档列表
            
        Returns:
            所有文档块列表
        """
        all_chunks = []
        for document in documents:
            chunks = self.process_document(document)
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def _split_text(self, text: str) -> List[str]:
        """
        分割文本为块（早期实现的简单切分策略）
        
        教学理解：
        - 这是基于字符数的简单切分
        - 当前 pipeline.py 使用更智能的策略：
          - 按段落切分（_split_paragraphs_with_headings）
          - 按 token 数切分（_chunk_paragraphs）
          - 保留标题层级信息
        
        Args:
            text: 输入文本
            
        Returns:
            文本块列表
        """
        # ========== 步骤1：检查文本长度 ==========
        if len(text) <= self.chunk_size:
            return [text]  # 文本足够短，不需要切分
        
        # ========== 步骤2：循环切分 ==========
        chunks = []
        start = 0  # 当前 chunk 的起始位置
        
        while start < len(text):
            # 步骤2.1：确定 chunk 的结束位置
            end = start + self.chunk_size
            
            # 步骤2.2：处理最后一个 chunk
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # 步骤2.3：寻找合适的分割点（避免截断句子）
            split_point = self._find_split_point(text, start, end)
            
            if split_point == -1:
                # 没找到合适的分割点，强制在 end 位置分割
                split_point = end
            
            # 步骤2.4：添加当前 chunk
            chunks.append(text[start:split_point])
            
            # 步骤2.5：计算下一个 chunk 的起始位置（考虑重叠）
            # 重叠的目的：保留上下文，避免信息丢失
            start = max(start + 1, split_point - self.chunk_overlap)
        
        return chunks
    
    def _find_split_point(self, text: str, start: int, end: int) -> int:
        """
        在指定范围内寻找最佳分割点
        
        教学理解：
        - 优先在段落、句子边界切分，避免截断句子
        - 分隔符优先级：段落 > 换行 > 句号 > 点 > 空格
        
        Args:
            text: 文本
            start: 开始位置
            end: 结束位置
            
        Returns:
            分割点位置，-1表示未找到
        """
        # ========== 按优先级寻找分隔符 ==========
        # 遍历分隔符列表（优先级从高到低）
        for separator in self.separators:
            # 在 end 附近寻找分隔符（最后 100 个字符）
            search_start = max(start, end - 100)
            
            # 从后往前搜索（优先选择靠近 end 的分隔符）
            for i in range(end - len(separator), search_start - 1, -1):
                if text[i:i + len(separator)] == separator:
                    # 找到分隔符，返回分隔符之后的位置
                    return i + len(separator)
        
        # 没找到任何分隔符
        return -1
    
    def merge_chunks(self, chunks: List[DocumentChunk], max_length: int = 2000) -> List[DocumentChunk]:
        """
        合并小的文档块
        
        Args:
            chunks: 文档块列表
            max_length: 合并后的最大长度
            
        Returns:
            合并后的文档块列表
        """
        if not chunks:
            return []
        
        merged_chunks = []
        current_chunk = chunks[0]
        
        for next_chunk in chunks[1:]:
            # 检查是否可以合并
            combined_length = len(current_chunk.content) + len(next_chunk.content)
            
            if (combined_length <= max_length and 
                current_chunk.doc_id == next_chunk.doc_id):
                # 合并块
                current_chunk.content += "\n" + next_chunk.content
                current_chunk.metadata["total_chunks"] = current_chunk.metadata.get("total_chunks", 1) + 1
            else:
                # 不能合并，保存当前块
                merged_chunks.append(current_chunk)
                current_chunk = next_chunk
        
        # 添加最后一个块
        merged_chunks.append(current_chunk)
        
        return merged_chunks
    
    def filter_chunks(self, chunks: List[DocumentChunk], min_length: int = 50) -> List[DocumentChunk]:
        """
        过滤太短的文档块
        
        Args:
            chunks: 文档块列表
            min_length: 最小长度
            
        Returns:
            过滤后的文档块列表
        """
        return [chunk for chunk in chunks if len(chunk.content.strip()) >= min_length]
    
    def add_chunk_metadata(self, chunks: List[DocumentChunk], metadata: Dict[str, Any]) -> List[DocumentChunk]:
        """
        为文档块添加额外元数据
        
        Args:
            chunks: 文档块列表
            metadata: 要添加的元数据
            
        Returns:
            更新后的文档块列表
        """
        for chunk in chunks:
            chunk.metadata.update(metadata)
        
        return chunks

def load_text_file(file_path: str, encoding: str = "utf-8") -> Document:
    """
    加载文本文件为文档
    
    Args:
        file_path: 文件路径
        encoding: 文件编码
        
    Returns:
        文档对象
    """
    with open(file_path, 'r', encoding=encoding) as f:
        content = f.read()
    
    metadata = {
        "source": file_path,
        "type": "text_file",
        "loaded_at": datetime.now().isoformat()
    }
    
    return Document(content=content, metadata=metadata)

def create_document(content: str, **metadata) -> Document:
    """
    创建文档的便捷函数
    
    Args:
        content: 文档内容
        **metadata: 元数据
        
    Returns:
        文档对象
    """
    return Document(content=content, metadata=metadata)
