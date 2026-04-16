import chromadb
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import CrossEncoder
from opencc import OpenCC
from typing import List, Dict


class SemanticSearchService:
    def __init__(self, chroma_path: str):
        self.model = SentenceTransformer("shibing624/text2vec-base-chinese")
        self.t2s = OpenCC("t2s")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_collection("restaurants")

        try:
            self.reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
            print("✅ Cross-Encoder 精排模型已載入")
        except Exception as e:
            self.reranker = None
            print(f"⚠️  Cross-Encoder 未載入（{e}），使用 bi-encoder 排序")

    def search(self, query: str, recall_k: int = 20,
               where: dict = None) -> List[str]:
        """Stage 1：ChromaDB bi-encoder 召回，回傳候選 ID list

        where: ChromaDB metadata 篩選條件，例如 {"has_parking": "True"}
               多條件用 {"$and": [{"has_parking": "True"}, {"is_late_night": "True"}]}
        """
        query_simp = self.t2s.convert(query)
        query_emb = self.model.encode([query_simp]).tolist()

        kwargs = dict(
            query_embeddings=query_emb,
            n_results=recall_k,
            include=["distances"],
        )
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)
        return results["ids"][0]

    def rerank(self, query: str, candidate_ids: List[str],
               descriptions: Dict[str, str], top_k: int = 5) -> List[str]:
        """
        Stage 2：CrossEncoder 用 MySQL 原始 Description（自然語言）精排
        descriptions: {restaurant_id: description_text}
        """
        if not self.reranker or not descriptions:
            return candidate_ids[:top_k]

        pairs = []
        valid_ids = []
        for id_ in candidate_ids:
            desc = descriptions.get(id_, "")
            if desc:
                pairs.append([query, desc])
                valid_ids.append(id_)

        if not pairs:
            return candidate_ids[:top_k]

        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(valid_ids, scores), key=lambda x: x[1], reverse=True)
        return [id_ for id_, _ in ranked[:top_k]]
