"""
web_app/utils/llm_utils.py

用途：
- 使用免費本機 Ollama 模型產生「自然語言推薦理由」
- 不需要 OpenAI API key
- LLM 只負責生成文字，不負責推薦排序

推薦排序仍然是：
TF-IDF + Cosine Similarity + click/favorite/booking 權重

負責把原本這種文字：
「因為你近期瀏覽過 韓式料理 類型餐廳，推薦相似餐廳」

改寫成：
「你最近常看韓式料理，這間也主打韓式風味，很適合下次聚餐時參考。」
"""

import os
import logging
from typing import Dict, List

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


logger = logging.getLogger(__name__)


# ============================================================
# LLM 設定
# ============================================================

# .env 裡 ENABLE_LLM_REASON=1 才啟用
ENABLE_LLM_REASON = os.getenv("ENABLE_LLM_REASON", "1") == "1"

# 目前使用 Ollama
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# Ollama 本機 API 位置
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

# Ollama 模型名稱
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


def _source_to_zh(source: str) -> str:
    """
    將推薦來源轉成中文，方便 LLM 理解。

    source 可能是：
    - click：使用者近期瀏覽
    - favorite：使用者收藏
    - booking：使用者訂位
    - age：年齡層偏好
    - similarity：相似度推薦
    - hot：熱門 fallback
    """
    mapping = {
        "click": "近期瀏覽",
        "favorite": "收藏紀錄",
        "booking": "訂位紀錄",
        "age": "年齡層偏好",
        "similarity": "相似度推薦",
        "hot": "熱門餐廳",
    }
    return mapping.get(source or "", "個人偏好")


def _safe_join(items: List[str], limit: int = 3) -> str:
    """
    將 list 安全轉成中文頓號字串。

    例如：
    ["韓式料理", "聚餐"] -> "韓式料理、聚餐"
    """
    clean_items = [str(x).strip() for x in items if str(x).strip()]
    return "、".join(clean_items[:limit])


def generate_llm_recommend_reason(
    restaurant: Dict,
    recommend_reason: str,
    recommend_source: str,
    recommend_reason_tags: List[str],
) -> str:
    """
    使用 Ollama 產生自然推薦理由。

    Args:
        restaurant:
            單筆餐廳資料，例如 Name / City / TagsStr / Description / PriceLevel
        recommend_reason:
            原本規則式推薦理由
        recommend_source:
            推薦來源，例如 click / favorite / booking / age
        recommend_reason_tags:
            這次命中的推薦標籤，例如 ["韓式料理"]

    Returns:
        str:
            LLM 生成的推薦理由。
            如果 Ollama 沒開、模型失敗、逾時，就回傳空字串。
            前端會 fallback 顯示 recommend_reason。
    """

    # 如果 .env 關閉 LLM，就直接回空字串
    if not ENABLE_LLM_REASON:
        return ""

    # 目前只支援 Ollama
    if LLM_PROVIDER != "ollama":
        return ""

    # 取餐廳資料
    name = restaurant.get("Name") or "這間餐廳"
    city = restaurant.get("City") or ""
    tags = restaurant.get("TagsStr") or restaurant.get("TagStr") or ""
    price = restaurant.get("PriceLevel") or ""
    description = restaurant.get("Description") or ""

    # 避免 prompt 太長，簡介取前 120 字即可
    short_description = description[:120] if description else ""

    source_zh = _source_to_zh(recommend_source)
    hit_tags_text = _safe_join(recommend_reason_tags, limit=3)

    # ========================================================
    # Prompt 設計
    # ========================================================
    prompt = f"""
你是一個餐廳訂位網站的 AI 推薦文案助理。

請根據以下資料，產生一句自然、親切、適合顯示在餐廳卡片上的推薦理由。

【推薦資料】
- 餐廳名稱：{name}
- 城市：{city}
- 餐廳標籤：{tags}
- 價位：{price}
- 餐廳簡介：{short_description}
- 推薦來源：{source_zh}
- 命中的偏好類別：{hit_tags_text}
- 原始推薦理由：{recommend_reason}

【輸出規則】
1. 請使用繁體中文。
2. 只輸出一句話，不要換行。
3. 字數控制在 25～45 個中文字左右。
4. 語氣自然，像 App 裡的推薦文案。
5. 不要提到演算法、TF-IDF、Cosine Similarity、分數。
6. 不要誇大，不要寫「最好吃」「一定喜歡」「保證」。
7. 不要使用引號。
"""

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        # stream=False 才會一次回完整 JSON，FastAPI 比較好處理
        "stream": False,
        "options": {
            # temperature 低一點，文案比較穩定
            "temperature": 0.6,
            # 限制輸出長度，避免模型講太多
            "num_predict": 80,
        },
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            # 最多等 8 秒
            # 超過就放棄 LLM，回傳空字串
            # 前端會改顯示原本的 recommend_reason
            timeout=8,
        )

        response.raise_for_status()
        data = response.json()

        # Ollama /api/chat 回傳格式通常是：
        # {
        #   "message": {
        #       "role": "assistant",
        #       "content": "..."
        #   }
        # }
        text = data.get("message", {}).get("content", "").strip()

        # 保險處理：避免換行
        text = text.replace("\n", " ").strip()

        return text

    except Exception as e:
        # Ollama 沒啟動、模型沒下載、逾時，都不要讓推薦 API 掛掉
        logger.warning("Ollama LLM reason failed: %s", e)
        return ""


def generate_llm_reasons_for_list(
    restaurants: List[Dict], max_llm_count: int = 10
) -> List[Dict]:
    """
    批次替推薦餐廳加上 llm_reason。

    為什麼只對前 max_llm_count 筆做？
    - 本機模型會比雲端 API 慢
    - 首頁一次推薦 10 筆，如果每筆都跑 LLM，等待時間會太久
    - 所以建議先只對前 5 筆產生 LLM 理由

    Args:
        restaurants:
            推薦餐廳列表
        max_llm_count:
            最多幾筆要產生 LLM 文案

    Returns:
        List[Dict]:
            每筆資料會多一個 llm_reason 欄位
    """

    result = []

    for index, item in enumerate(restaurants):
        new_item = dict(item)

        # 預設先放空字串
        # 前端會用 llm_reason || recommend_reason 顯示
        new_item["llm_reason"] = ""

        # 超過前 max_llm_count 筆就不呼叫 LLM
        if index >= max_llm_count:
            result.append(new_item)
            continue

        recommend_reason = new_item.get("recommend_reason") or ""
        recommend_source = new_item.get("recommend_source") or ""
        recommend_reason_tags = new_item.get("recommend_reason_tags") or []

        # 如果沒有規則推薦理由，就不呼叫 LLM
        if not recommend_reason:
            result.append(new_item)
            continue

        # 熱門 fallback 可以先不產生 LLM，避免浪費時間
        if recommend_source == "hot":
            result.append(new_item)
            continue

        llm_reason = generate_llm_recommend_reason(
            restaurant=new_item,
            recommend_reason=recommend_reason,
            recommend_source=recommend_source,
            recommend_reason_tags=recommend_reason_tags,
        )

        new_item["llm_reason"] = llm_reason
        result.append(new_item)

    return result
