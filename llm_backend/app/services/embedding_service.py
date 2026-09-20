from typing import Dict, List, Optional
from sentence_transformers import SentenceTransformer
import asyncio
import numpy as np
import faiss
import json
from pathlib import Path
import os
import hashlib
import time
import PyPDF2

# 纯文本类文件的分块参数，与 GraphRAG settings.yaml 中的 chunks 配置保持一致
TEXT_CHUNK_SIZE = 500
TEXT_CHUNK_OVERLAP = 100

# 按扩展名区分处理方式：PDF 走 PyPDF2，docx 走 python-docx，其余按纯文本读取
TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log", ".tsv"}

class EmbeddingService:
    # 模型首次加载要从 HuggingFace 拉取权重，开销较大，因此改为惰性加载，
    # 避免仅仅实例化服务就阻塞事件循环。
    MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'

    def __init__(self):
        self._model = None
        self.index_dir = Path("indexes")
        self.index_dir.mkdir(exist_ok=True)
        
        # 初始化空索引和文档存储
        self.dimension = 384  # 修改为与模型输出维度一致
        self.current_index = None
        self.current_documents = {}

    @property
    def model(self) -> SentenceTransformer:
        """惰性加载句向量模型"""
        if self._model is None:
            self._model = SentenceTransformer(self.MODEL_NAME)
        return self._model
    
    def _generate_safe_id(self, metadata: dict) -> str:
        """生成安全的文件ID"""
        # 使用时间戳和文件信息生成唯一ID
        timestamp = str(int(time.time()))
        file_info = f"{metadata.get('filename', '')}_{timestamp}"
        # 使用MD5生成安全的文件名
        return hashlib.md5(file_info.encode()).hexdigest()
        
    def _create_index(self) -> faiss.IndexFlatL2:
        """创建新的 FAISS 索引"""
        return faiss.IndexFlatL2(self.dimension)
    
    def _get_index_path(self, file_path: str) -> str:
        """生成索引文件路径"""
        # 使用文件路径的哈希作为索引文件名
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return f"indexes/index_{file_hash}.bin"

    def _split_plain_text(self, text: str) -> List[str]:
        """按固定长度切分纯文本，相邻分块保留重叠，避免语义在边界处被切断"""
        text = text.strip()
        if not text:
            return []
        step = max(TEXT_CHUNK_SIZE - TEXT_CHUNK_OVERLAP, 1)
        return [text[i:i + TEXT_CHUNK_SIZE] for i in range(0, len(text), step)]

    def _extract_chunks(self, file_path: str) -> List[Dict]:
        """按文件类型提取文本分块

        返回 [{"text": str, "metadata": {...}}, ...]。metadata 统一带 source，
        PDF 额外带 page 页码，其余类型带 chunk 序号。
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        chunks: List[Dict] = []

        if suffix == ".pdf":
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page_no, page in enumerate(pdf_reader.pages, start=1):
                    # 扫描版 PDF 的空页会返回 None，必须过滤，否则模型编码会直接报错
                    text = (page.extract_text() or "").strip()
                    if text:
                        chunks.append({"text": text, "metadata": {"page": page_no}})
        elif suffix == ".docx":
            import docx  # python-docx，仅在上传 docx 时才需要

            document = docx.Document(file_path)
            paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
            for i, text in enumerate(self._split_plain_text("\n".join(paragraphs)), start=1):
                chunks.append({"text": text, "metadata": {"chunk": i}})
        elif suffix in TEXT_SUFFIXES or suffix == "":
            raw = path.read_text(encoding="utf-8", errors="ignore")
            for i, text in enumerate(self._split_plain_text(raw), start=1):
                chunks.append({"text": text, "metadata": {"chunk": i}})
        else:
            raise ValueError(f"暂不支持的文件类型: {suffix or '未知'}")

        for chunk in chunks:
            chunk["metadata"]["source"] = str(file_path)
        return chunks

    def _build_index(self, file_path: str, chunks: List[Dict], base_dir: Path) -> Dict:
        """把分块编码成向量并落盘（CPU 密集的阻塞操作）"""
        # 创建索引
        index = self._create_index()

        # 使用 SentenceTransformer 生成向量
        vectors = self.model.encode([c["text"] for c in chunks])
        vectors = np.asarray(vectors, dtype='float32')  # 确保类型正确

        # 添加向量到索引
        index.add(vectors)

        # 生成文件 ID
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        index_id = f"index_{file_hash}"

        # 创建文档数据
        documents = {str(i): chunk for i, chunk in enumerate(chunks)}

        # 保存索引和文档数据
        self._save_index(file_hash, index, documents, base_dir)

        return {
            "status": "success",
            "index_id": index_id,
            "chunks": len(chunks)
        }
    
    async def create_embeddings(self, file_path: str, index_dir: Optional[str] = None) -> Dict:
        """从文件创建向量索引"""
        try:
            base_dir = Path(index_dir) if index_dir else self.index_dir
            base_dir.mkdir(parents=True, exist_ok=True)

            chunks = await asyncio.to_thread(self._extract_chunks, file_path)
            if not chunks:
                raise ValueError(f"未能从文件中提取到有效文本: {file_path}")

            # 模型编码是阻塞调用，放到线程池执行，避免卡住事件循环
            return await asyncio.to_thread(self._build_index, file_path, chunks, base_dir)
            
        except Exception as e:
            raise Exception(f"创建向量失败: {str(e)}")
    
    def _save_index(self, file_id: str, index: faiss.Index, documents: dict,
                    base_dir: Optional[Path] = None):
        """保存索引和文档数据"""
        try:
            target_dir = Path(base_dir) if base_dir else self.index_dir
            # 使用安全的文件名
            index_path = target_dir / f"index_{file_id}.bin"  # 这里添加了 "index_" 前缀
            docs_path = target_dir / f"docs_{file_id}.json"
            
             
            # 保存 FAISS 索引
            faiss.write_index(index, str(index_path))
            
            # 保存文档数据
            with open(docs_path, 'w', encoding='utf-8') as f:
                json.dump(documents, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            raise Exception(f"保存索引失败: {str(e)}")
    
    def _load_index(self, index_id: str):
        """加载索引和文档数据"""
        try:
            # 保持与保存时相同的文件名格式
            index_path = self.index_dir / f"{index_id}.bin"  # 这里没有添加 "index_" 前缀，因为 index_id 已经包含了
            docs_path = self.index_dir / f"docs_{index_id.replace('index_', '')}.json"
            
             
            if not index_path.exists() or not docs_path.exists():
                # 尝试旧的文件名格式
                old_index_path = self.index_dir / f"index_{index_id}.bin"
                old_docs_path = self.index_dir / f"docs_{index_id}.json"
                
                if old_index_path.exists() and old_docs_path.exists():
                    index_path = old_index_path
                    docs_path = old_docs_path
                else:
                    raise FileNotFoundError(f"找不到索引文件: {index_id}")
             
            # 加载索引
            self.current_index = faiss.read_index(str(index_path))
            
            # 验证索引维度
            if self.current_index.d != self.dimension:
                raise ValueError(f"索引维度不匹配: 期望 {self.dimension}, 实际 {self.current_index.d}")
            
            # 加载文档数据
            with open(docs_path, 'r', encoding='utf-8') as f:
                self.current_documents = json.load(f)
            
            # 验证是否有数据
            if not self.current_documents:
                raise ValueError("文档数据为空")
            
            print(f"成功加载索引 {index_id}: {self.current_index.ntotal} 个向量, {len(self.current_documents)} 个文档")
            
        except Exception as e:
            self.current_index = None
            self.current_documents = {}
            raise Exception(f"加载索引失败: {str(e)}")

    def load_index(self, index_id: str) -> None:
        """加载索引的公开入口，供 RAGChatService 调用"""
        self._load_index(index_id)
    
    async def search(self, query: str, top_k: int = 3) -> List[dict]:
        """搜索最相关的文档片段"""
        try:
            if not self.current_index:
                raise Exception("未加载索引")
            
            # 向量编码与检索都是阻塞操作，统一放到线程池执行
            return await asyncio.to_thread(self._search_sync, query, top_k)
                
        except Exception as e:
            raise Exception(f"搜索失败: {str(e)}")

    def _search_sync(self, query: str, top_k: int) -> List[dict]:
        """实际的向量检索逻辑（同步）"""
        # 生成查询向量
        query_vector = self.model.encode([query], convert_to_tensor=False)
        query_vector = np.asarray(query_vector, dtype='float32')

        # 搜索最相似的向量，top_k 不能超过索引里的向量总数，否则 FAISS 会报错
        top_k = min(top_k, self.current_index.ntotal)
        if top_k <= 0:
            return []
        distances, indices = self.current_index.search(query_vector, top_k)

        # 返回结果
        results = []
        for i in range(len(indices[0])):
            idx_str = str(int(indices[0][i]))
            if idx_str in self.current_documents:
                results.append({
                    "score": float(distances[0][i]),
                    "content": self.current_documents[idx_str]["text"],
                    "metadata": self.current_documents[idx_str]["metadata"]
                })

        return results
