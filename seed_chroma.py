"""
seed_chroma.py
從 0408_V6_2_Final_Fixed_Results.csv 重建 ChromaDB

新增 scenario metadata，讓語意搜尋可以在 Stage 1 就過濾情境。

執行：
    cd /Users/hazel/Desktop/Taipei2025/restaurant-fastapi
    .venv/bin/python3 seed_chroma.py
"""

import os
import ast
import shutil
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer
from opencc import OpenCC
from tqdm import tqdm

# ── 設定 ──────────────────────────────────────────────────────────
CSV_PATH   = "0408_V6_2_Final_Fixed_Results.csv"
CHROMA_PATH = "chroma_db"
MODEL_NAME  = "shibing624/text2vec-base-chinese"  # 與 semantic_search_service.py 一致

# ── 1. 載入資料 ────────────────────────────────────────────────────
print("📥 載入 CSV...")
df = pd.read_csv(CSV_PATH)
print(f"   共 {len(df)} 筆")

# ── 2. 載入模型 ────────────────────────────────────────────────────
print("⏳ 載入 embedding 模型...")
model = SentenceTransformer(MODEL_NAME)
t2s = OpenCC("t2s")
print("✅ 模型就緒")

# ── 3. 清空並重建 ChromaDB ─────────────────────────────────────────
if os.path.exists(CHROMA_PATH):
    shutil.rmtree(CHROMA_PATH)
    print(f"🗑️  舊 {CHROMA_PATH} 已刪除")

client = chromadb.PersistentClient(path=CHROMA_PATH)
col = client.create_collection("restaurants")
print(f"✅ 新 collection 'restaurants' 已建立")

# ── 4. 逐筆寫入 ────────────────────────────────────────────────────
ids, embeddings, documents, metadatas = [], [], [], []

for _, row in tqdm(df.iterrows(), total=len(df), desc="Embedding"):
    # ID
    rid = str(row["ID"]).strip()

    # 文件：用精煉描述做 embedding
    doc = str(row.get("Refined_Text") or row.get("Description") or "").strip()
    if not doc:
        continue

    # Embedding（繁轉簡再計算）
    emb = model.encode(t2s.convert(doc)).tolist()

    # Tags 解析
    tags_raw = row.get("Tags", {})
    if isinstance(tags_raw, str):
        try:
            tags_raw = ast.literal_eval(tags_raw)
        except Exception:
            tags_raw = {}

    category      = str(tags_raw.get("category") or row.get("Category") or "").strip()
    has_parking   = tags_raw.get("has_parking", False)
    is_late_night = tags_raw.get("is_late_night", False)
    price_level   = str(tags_raw.get("price_level") or row.get("PriceLevel") or "").strip()
    scenarios     = tags_raw.get("scenario", [])
    if isinstance(scenarios, str):
        scenarios = [s.strip() for s in scenarios.split(",") if s.strip()]

    city = str(row.get("City") or "").strip()

    # scenario 各自存為獨立 boolean 欄位，支援 ChromaDB 精確過濾
    _SCENARIO_KEYS = {
        "浪漫約會氛圍": "s_romance",
        "適合家庭聚餐": "s_family",
        "文青設計感空間": "s_artsy",
        "坐擁絕佳景觀": "s_scenic",
        "親子友善空間": "s_kids",
        "日式和風裝潢": "s_japanese",
        "在地庶民風味": "s_local",
        "微醺餐酒氣息": "s_bar",
        "簡潔用餐環境": "s_simple",
    }
    scenario_meta = {v: ("True" if k in scenarios else "False") for k, v in _SCENARIO_KEYS.items()}

    metadata = {
        "name":          str(row.get("Name") or "").strip(),
        "city":          city,
        "category":      category,
        "has_parking":   "True" if has_parking else "False",
        "is_late_night": "True" if is_late_night else "False",
        "price_level":   price_level,
        **scenario_meta,
    }

    ids.append(rid)
    embeddings.append(emb)
    documents.append(doc)
    metadatas.append(metadata)

# ── 5. 批次寫入（每批 50 筆）──────────────────────────────────────
BATCH = 50
for i in range(0, len(ids), BATCH):
    col.add(
        ids=ids[i:i+BATCH],
        embeddings=embeddings[i:i+BATCH],
        documents=documents[i:i+BATCH],
        metadatas=metadatas[i:i+BATCH],
    )

print(f"\n✅ ChromaDB 重建完成！共寫入 {col.count()} 筆")

# ── 6. 快速驗證 ────────────────────────────────────────────────────
print("\n🔍 抽樣驗證（前 3 筆）：")
sample = col.get(limit=3, include=["metadatas", "documents"])
for sid, meta, doc in zip(sample["ids"], sample["metadatas"], sample["documents"]):
    print(f"  [{sid}] {meta['name']}")
    print(f"    city={meta['city']}  category={meta['category']}")
    print(f"    scenario={meta.get('scenario', '—')}")
    print(f"    doc[:60]: {doc[:60]}")
