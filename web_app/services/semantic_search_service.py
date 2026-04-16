import chromadb
from sentence_transformers import SentenceTransformer
from opencc import OpenCC
from typing import List


class SemanticSearchService:
    def __init__(self, chroma_path: str):
        self.model = SentenceTransformer("shibing624/text2vec-base-chinese")
        self.t2s = OpenCC("t2s")  # 繁體 → 簡體，與訓練時一致
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_collection("restaurants")

    def search(self, query: str, top_k: int = 50) -> List[str]:
        """回傳按相似度排序的餐廳 ID list"""
        query_simp = self.t2s.convert(query)
        query_emb = self.model.encode([query_simp]).tolist()
        results = self.collection.query(
            query_embeddings=query_emb,
            n_results=top_k,
            include=["distances"],
        )
        return results["ids"][0]  # 已按相似度排好的 ID list
