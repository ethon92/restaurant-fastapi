from fastapi import APIRouter
from web_app.mysql_connection import get_db_cursor
from web_app.utils.llm_utils import generate_llm_reasons_for_list
from datetime import date, datetime
from collections import Counter
from typing import Dict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

router = APIRouter(prefix="/recommend", tags=["recommend"])


# ============================================================
# 權重設定
# ============================================================
# click：只是點進去看，興趣較弱
# favorite：收藏代表明確興趣
# booking：訂位代表真的有消費意圖，所以權重最高

# 使用者行為權重
CLICK_WEIGHT = 1
FAVORITE_WEIGHT = 6
BOOKING_WEIGHT = 10

# 年齡偏好權重，不要太高，避免蓋過真實行為
AGE_WEIGHT = 1

# 類別加分權重
CATEGORY_BONUS_WEIGHT = 0.08

# 最終推薦筆數
TOP_N = 10


# ============================================================
# 計算年齡
# ============================================================
def calculate_age(birthday):
    """
    根據 users.user_birthday 計算年齡。
    birthday 可能是 date / datetime / 字串 / None。
    """
    if not birthday:
        return None

    if isinstance(birthday, str):
        try:
            birthday = datetime.strptime(birthday, "%Y-%m-%d").date()
        except ValueError:
            return None

    if isinstance(birthday, datetime):
        birthday = birthday.date()

    today = date.today()

    return (
        today.year
        - birthday.year
        - ((today.month, today.day) < (birthday.month, birthday.day))
    )


# ============================================================
# 年齡層分類
# ============================================================
def get_age_group(age):
    """
    將年齡轉成年齡層。

    """
    if age is None:
        return "unknown"

    if age <= 25:
        return "young"

    if age <= 40:
        return "adult"

    return "mature"


# ============================================================
# 年齡偏好文字
# ============================================================
def get_age_preference_text(age_group):
    """
    使用者初始沒有任何收藏 / 訂位 / 點擊時，
    用年齡層先建立初始偏好。
    """
    if age_group == "young":
        return "咖啡 甜點 早午餐 韓式 義式 火鍋 聚餐 網美"

    if age_group == "adult":
        return "日式 燒肉 火鍋 餐酒館 義式 中式 約會 聚餐"

    if age_group == "mature":
        return "中式 台菜 合菜 海鮮 素食 家庭 聚餐"

    return ""


# ============================================================
# 建立餐廳文字特徵
# ============================================================
def build_restaurant_text(restaurant):
    """
    把餐廳資料轉成 sklearn 可以讀的文字。

    TF-IDF 會依這段文字建立餐廳向量。
    餐廳資料常用欄位：
    - Name
    - Description
    - TagsStr
    - City
    - PriceLevel
    """
    name = restaurant.get("Name") or ""
    description = restaurant.get("Description") or ""
    tags = restaurant.get("TagsStr") or ""
    city = restaurant.get("City") or ""
    price = restaurant.get("PriceLevel") or ""

    return f"{name} {description} {tags} {city} {price}"


# ============================================================
# 擷取餐廳類別標籤
# ============================================================
def extract_tags(restaurant):
    """
    從 TagsStr 擷取餐廳類別。
    支援常見分隔符號。
    """
    tags_str = restaurant.get("TagsStr") or ""

    if not tags_str:
        return []

    separators = [",", "，", "、", "/", "|"]

    for sep in separators:
        tags_str = tags_str.replace(sep, " ")

    tags = [tag.strip() for tag in tags_str.split() if tag.strip()]

    return tags


# ============================================================
# 建立推薦理由：熱門 fallback 使用
# ============================================================
def build_recommend_reason(
    matched_tags,
    has_booking,
    has_favorite,
    has_click,
    score,
    is_hot=False,
):
    """
    回傳前端可以顯示的推薦理由。
    """
    if is_hot:
        return "目前熱門餐廳，適合新會員先探索"

    if matched_tags:
        tag_text = "、".join(matched_tags[:2])

        if has_booking:
            return f"因為你曾訂位過 {tag_text} 類型餐廳，推薦相似餐廳"

        if has_favorite:
            return f"因為你收藏過 {tag_text} 類型餐廳，推薦相似餐廳"

        if has_click:
            return f"因為你近期瀏覽過 {tag_text} 類型餐廳，推薦相似餐廳"

        return f"依照你的年齡層偏好，推薦 {tag_text} 類型餐廳"

    return f"根據你的偏好相似度推薦，相似度 {round(score, 3)}"


# ============================================================
# 建立推薦理由：精準來源版
# ============================================================
def build_recommend_reason_by_source(matched_tags, preferred_tags_by_source, score):
    """
    回傳更精準的推薦理由與推薦來源。

    回傳格式：
    {
        "reason": "因為你近期瀏覽過 韓式料理 類型餐廳，推薦相似餐廳",
        "source": "click",
        "tags": ["韓式料理"]
    }
    """

    # 如果這間餐廳完全沒有命中任何偏好類別，就用一般相似度文字
    if not matched_tags:
        return {
            "reason": f"根據你的近期偏好推薦相似餐廳，相似度 {round(score, 3)}",
            "source": "similarity",
            "tags": [],
        }

    # 每個來源對應的前端顯示文字
    source_text = {
        "booking": "因為你曾訂位過",
        "favorite": "因為你收藏過",
        "click": "因為你近期瀏覽過",
        "age": "依照你的年齡層偏好",
    }

    # 來源顯示順序：
    # 注意：這裡只用在「分數一樣」時當作排序依據
    # 不再是無條件 favorite 優先 click
    source_priority = {
        "booking": 4,
        "favorite": 3,
        "click": 2,
        "age": 1,
    }

    # 用來存每個來源實際命中的資料
    # 格式範例：
    # {
    #   "click": {
    #       "score": 3,
    #       "tags": ["韓式料理", "火鍋"]
    #   },
    #   "favorite": {
    #       "score": 6,
    #       "tags": ["甜點下午茶"]
    #   }
    # }
    source_hits = {}

    # 逐一檢查每個來源
    for source, tag_counter in preferred_tags_by_source.items():
        hit_tags = []
        source_score = 0

        # 檢查這間餐廳命中的 tag，是否來自該來源
        for tag in matched_tags:
            if tag in tag_counter:
                hit_tags.append(tag)
                source_score += tag_counter[tag]

        # 只有真的有命中的來源才記錄
        if hit_tags:
            source_hits[source] = {
                "score": source_score,
                "tags": hit_tags,
            }

    # 如果沒有任何來源命中，就回一般推薦理由
    if not source_hits:
        return {
            "reason": f"根據你的近期偏好推薦相似餐廳，相似度 {round(score, 3)}",
            "source": "similarity",
            "tags": [],
        }

    # 選出「對這間餐廳貢獻最高」的來源
    # 排序邏輯：
    # 1. 來源分數越高越優先
    # 2. 如果分數一樣，再用 booking > favorite > click > age
    best_source = max(
        source_hits.keys(),
        key=lambda source: (
            source_hits[source]["score"],
            source_priority.get(source, 0),
        ),
    )

    best_tags = source_hits[best_source]["tags"]
    tag_text = "、".join(best_tags[:2])

    return {
        "reason": f"{source_text[best_source]} {tag_text} 類型餐廳，推薦相似餐廳",
        "source": best_source,
        "tags": best_tags[:2],
    }


# ============================================================
# 熱門推薦 fallback
# ============================================================
def get_hot_restaurants(limit=10):
    """
    當使用者沒有任何行為資料時，使用熱門推薦。

    熱門分數來源：
    - 被 click 次數
    - 被 favorite 次數
    - 被 booking 次數
    """
    hot_score = {}

    # 1. click 熱門
    click_sql = """
        SELECT restaurant_id, COUNT(*) AS cnt
        FROM user_behavior
        WHERE action_type = 'click'
        GROUP BY restaurant_id
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(click_sql)
            rows = cursor.fetchall()

        for row in rows:
            rid = row["restaurant_id"]
            hot_score[rid] = hot_score.get(rid, 0) + row["cnt"] * CLICK_WEIGHT

    except Exception as e:
        print("hot click query failed:", e)

    # 2. favorite 熱門
    favorite_sql = """
        SELECT restaurant_id, COUNT(*) AS cnt
        FROM favorite
        GROUP BY restaurant_id
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(favorite_sql)
            rows = cursor.fetchall()

        for row in rows:
            rid = row["restaurant_id"]
            hot_score[rid] = hot_score.get(rid, 0) + row["cnt"] * FAVORITE_WEIGHT

    except Exception as e:
        print("hot favorite query failed:", e)

    # 3. booking 熱門
    booking_sql = """
        SELECT restaurant_id, COUNT(*) AS cnt
        FROM reservations
        GROUP BY restaurant_id
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(booking_sql)
            rows = cursor.fetchall()

        for row in rows:
            rid = row["restaurant_id"]
            hot_score[rid] = hot_score.get(rid, 0) + row["cnt"] * BOOKING_WEIGHT

    except Exception as e:
        print("hot booking query failed:", e)

    if not hot_score:
        # 如果完全沒有任何熱門資料，就直接抓前幾筆餐廳
        fallback_sql = """
            SELECT *
            FROM restaurants
            LIMIT %s
        """

        with get_db_cursor() as cursor:
            cursor.execute(fallback_sql, (limit,))
            restaurants = cursor.fetchall()

        for item in restaurants:
            item["recommend_score"] = 0
            item["recommend_reason"] = "新會員探索推薦"
            item["recommend_source"] = "hot"
            item["recommend_reason_tags"] = []
            item["llm_reason"] = ""

        return restaurants

    sorted_hot_ids = sorted(
        hot_score.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]

    hot_ids = [item[0] for item in sorted_hot_ids]

    placeholders = ",".join(["%s"] * len(hot_ids))

    restaurant_sql = f"""
        SELECT *
        FROM restaurants
        WHERE ID IN ({placeholders})
    """

    with get_db_cursor() as cursor:
        cursor.execute(restaurant_sql, hot_ids)
        restaurants = cursor.fetchall()

    # 補上熱門分數與推薦理由
    for item in restaurants:
        rid = item["ID"]
        item["recommend_score"] = hot_score.get(rid, 0)
        item["recommend_reason"] = build_recommend_reason(
            matched_tags=[],
            has_booking=False,
            has_favorite=False,
            has_click=False,
            score=item["recommend_score"],
            is_hot=True,
        )

        # 熱門 fallback 的來源
        item["recommend_source"] = "hot"

        # 熱門推薦不是因為某個 tag 命中
        item["recommend_reason_tags"] = []

        # 熱門推薦先不呼叫 LLM
        item["llm_reason"] = ""

    restaurants = sorted(
        restaurants,
        key=lambda item: item.get("recommend_score", 0),
        reverse=True,
    )

    return restaurants


# ============================================================
# 個人化推薦 API：sklearn
# ============================================================
@router.get("/{user_id}")
async def get_recommend(user_id: int):
    """
    sklearn 個人化推薦完整版本。

    使用資料：
    1. users.user_birthday：計算年齡層
    2. user_behavior：抓 click
    3. favorite：抓收藏餐廳
    4. reservations：抓訂位餐廳
    5. restaurants：做餐廳內容特徵

    核心技術：
    - TF-IDF：把餐廳文字轉成向量
    - Cosine Similarity：計算使用者偏好和餐廳的相似度
    - 權重模型：click / favorite / booking 給不同分數
    - 類別權重強化：相同 TagsStr 類別加分
    - Top-N 推薦
    - 熱門 fallback
    """

    # ========================================================
    # 1. 取得使用者生日
    # ========================================================
    user_sql = """
        SELECT user_birthday
        FROM users
        WHERE user_id = %s
        LIMIT 1
    """

    with get_db_cursor() as cursor:
        cursor.execute(user_sql, (user_id,))
        user = cursor.fetchone()

    if not user:
        return {
            "data": get_hot_restaurants(TOP_N),
            "message": "user not found, use hot fallback",
        }

    age = calculate_age(user.get("user_birthday"))
    age_group = get_age_group(age)
    age_preference_text = get_age_preference_text(age_group)

    # ========================================================
    # 2. 取得所有餐廳
    # ========================================================
    restaurant_sql = """
        SELECT *
        FROM restaurants
    """

    with get_db_cursor() as cursor:
        cursor.execute(restaurant_sql)
        restaurants = cursor.fetchall()

    if not restaurants:
        return {"data": [], "message": "no restaurants"}

    # ========================================================
    # 3. 建立餐廳 ID 與文字特徵
    # ========================================================
    restaurant_ids = []
    restaurant_texts = []
    restaurant_tags_map = {}

    for restaurant in restaurants:
        rid = restaurant["ID"]

        restaurant_ids.append(rid)
        restaurant_texts.append(build_restaurant_text(restaurant))
        restaurant_tags_map[rid] = extract_tags(restaurant)

    restaurant_id_to_index = {rid: index for index, rid in enumerate(restaurant_ids)}

    # ========================================================
    # 4. TF-IDF：將餐廳文字轉成向量
    # ========================================================
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=8000,
    )

    restaurant_vectors = vectorizer.fit_transform(restaurant_texts)

    # ========================================================
    # 5. 建立使用者偏好向量
    # ========================================================
    user_profile_vector = None
    interacted_ids = set()

    has_click = False
    has_favorite = False
    has_booking = False

    # --------------------------------------------------------
    # 記錄使用者喜歡的類別

    # preferred_tags_counter：
    # - 用來計算總類別加分，維持原本功能
    #
    # preferred_tags_by_source：
    # - 用來判斷推薦理由來源
    # --------------------------------------------------------
    preferred_tags_counter = Counter()

    preferred_tags_by_source = {
        "click": Counter(),
        "favorite": Counter(),
        "booking": Counter(),
        "age": Counter(),
    }

    debug_sources = {
        "click": [],
        "favorite": [],
        "booking": [],
    }

    def add_restaurant_to_profile(restaurant_id, weight, source):
        """
        將某間餐廳依照權重加入使用者偏好向量。

        restaurant_id：餐廳 ID
        weight：權重
        source：來源 click / favorite / booking
        """
        nonlocal user_profile_vector

        if restaurant_id not in restaurant_id_to_index:
            return

        index = restaurant_id_to_index[restaurant_id]

        # 使用 getrow 避免 sparse matrix __getitem__ 型別錯誤
        restaurant_vector = restaurant_vectors.getrow(index)

        if user_profile_vector is None:
            user_profile_vector = restaurant_vector * weight
        else:
            user_profile_vector = user_profile_vector + (restaurant_vector * weight)

        interacted_ids.add(restaurant_id)
        debug_sources[source].append(restaurant_id)

        # 類別加分：維持原本總權重
        tags = restaurant_tags_map.get(restaurant_id, [])
        for tag in tags:
            preferred_tags_counter[tag] += weight

            # 推薦理由來源追蹤：新增
            preferred_tags_by_source[source][tag] += weight

    # ========================================================
    # 6. 加入 click 行為
    # ========================================================
    click_sql = """
        SELECT restaurant_id
        FROM user_behavior
        WHERE user_id = %s
        AND action_type = 'click'
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(click_sql, (user_id,))
            clicks = cursor.fetchall()

        for row in clicks:
            has_click = True
            add_restaurant_to_profile(
                restaurant_id=row["restaurant_id"],
                weight=CLICK_WEIGHT,
                source="click",
            )

    except Exception as e:
        print("click query failed:", e)

    # ========================================================
    # 7. 加入收藏餐廳 favorite
    # ========================================================
    favorite_sql = """
        SELECT restaurant_id
        FROM favorite
        WHERE user_id = %s
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(favorite_sql, (user_id,))
            favorites = cursor.fetchall()

        for row in favorites:
            has_favorite = True
            add_restaurant_to_profile(
                restaurant_id=row["restaurant_id"],
                weight=FAVORITE_WEIGHT,
                source="favorite",
            )

    except Exception as e:
        print("favorite query failed:", e)

    # ========================================================
    # 8. 加入訂位紀錄 reservations
    # ========================================================
    booking_sql = """
        SELECT restaurant_id
        FROM reservations
        WHERE user_id = %s
    """

    try:
        with get_db_cursor() as cursor:
            cursor.execute(booking_sql, (user_id,))
            bookings = cursor.fetchall()

        for row in bookings:
            has_booking = True
            add_restaurant_to_profile(
                restaurant_id=row["restaurant_id"],
                weight=BOOKING_WEIGHT,
                source="booking",
            )

    except Exception as e:
        print("booking query failed:", e)

    # ========================================================
    # 9. 加入年齡偏好向量
    # ========================================================
    if age_preference_text:
        age_vector = vectorizer.transform([age_preference_text])

        # 如果使用者沒有 click / favorite / booking
        # 就用年齡偏好建立初始 user profile
        if user_profile_vector is None:
            user_profile_vector = age_vector * AGE_WEIGHT
        else:
            user_profile_vector = user_profile_vector + (age_vector * AGE_WEIGHT)

        age_tags = age_preference_text.split()

        for tag in age_tags:
            preferred_tags_counter[tag] += AGE_WEIGHT
            preferred_tags_by_source["age"][tag] += AGE_WEIGHT

    # ========================================================
    # 10. 完全沒資料：熱門 fallback
    # ========================================================
    # 注意：現在這裡代表「連年齡偏好文字也沒有」
    if user_profile_vector is None:
        hot_data = get_hot_restaurants(TOP_N)

        return {
            "data": hot_data,
            "debug": {
                "fallback": "hot",
                "age": age,
                "age_group": age_group,
                "sources": debug_sources,
            },
        }

    # ========================================================
    # 11. Cosine Similarity：計算每間餐廳相似度
    # ========================================================
    similarity_scores = cosine_similarity(
        user_profile_vector, restaurant_vectors
    ).flatten()

    # ========================================================
    # 12. 組推薦結果：相似度 + 類別加分
    # ========================================================
    recommend_results = []

    for index, restaurant in enumerate(restaurants):
        rid = restaurant["ID"]

        # 不推薦已經互動過的餐廳
        if rid in interacted_ids:
            continue

        base_score = float(similarity_scores[index])

        restaurant_tags = restaurant_tags_map.get(rid, [])

        # 找出候選餐廳命中的偏好類別
        matched_tags = [tag for tag in restaurant_tags if tag in preferred_tags_counter]
        # 類別加分：使用者越常收藏 / 訂位某類，該類餐廳分數越高
        category_bonus = 0

        for tag in matched_tags:
            category_bonus += preferred_tags_counter[tag] * CATEGORY_BONUS_WEIGHT

        final_score = base_score + category_bonus

        if final_score <= 0:
            continue

        item = dict(restaurant)
        item["recommend_score"] = round(final_score, 4)
        item["base_similarity"] = round(base_score, 4)
        item["category_bonus"] = round(category_bonus, 4)
        item["matched_tags"] = matched_tags

        # ----------------------------------------------------
        # 精準顯示推薦理由
        # ----------------------------------------------------
        reason_info = build_recommend_reason_by_source(
            matched_tags=matched_tags,
            preferred_tags_by_source=preferred_tags_by_source,
            score=final_score,
        )

        # 給前端顯示的文字
        # 例如：
        # - 因為你近期瀏覽過 韓式料理 類型餐廳，推薦相似餐廳
        # - 因為你收藏過 甜點下午茶 類型餐廳，推薦相似餐廳
        item["recommend_reason"] = reason_info["reason"]

        # 給前端 / console debug 用
        # 可以確認這筆推薦到底是 click / favorite / booking / age 哪個來源
        item["recommend_source"] = reason_info["source"]

        # 這次推薦理由實際命中的 tag
        item["recommend_reason_tags"] = reason_info["tags"]

        # 先給空字串，後面 Top-N 排序完成後再產生 LLM 理由
        item["llm_reason"] = ""

        # 把這一筆推薦餐廳加入推薦結果
        recommend_results.append(item)

    # ========================================================
    # 13. Top-N 排序
    # ========================================================
    recommend_results = sorted(
        recommend_results,
        key=lambda item: item["recommend_score"],
        reverse=True,
    )[:TOP_N]

    # ✅ 記錄最後是否真的有使用熱門 fallback
    used_fallback = False

    if not recommend_results:
        used_fallback = True
        recommend_results = get_hot_restaurants(TOP_N)

    else:
        # 只對 Top-N 的前幾筆產生 LLM 推薦理由
        # 預設 llm_utils.py 裡 max_llm_count=5
        recommend_results = generate_llm_reasons_for_list(recommend_results)

    return {
        "data": recommend_results,
        "debug": {
            "fallback": "hot" if used_fallback else None,
            "age": age,
            "age_group": age_group,
            "has_click": has_click,
            "has_favorite": has_favorite,
            "has_booking": has_booking,
            "interacted_ids": list(interacted_ids),
            "preferred_tags": preferred_tags_counter.most_common(),
            # 可以在 console 看每種來源累積了哪些類別
            "preferred_tags_by_source": {
                "click": preferred_tags_by_source["click"].most_common(),
                "favorite": preferred_tags_by_source["favorite"].most_common(),
                "booking": preferred_tags_by_source["booking"].most_common(),
                "age": preferred_tags_by_source["age"].most_common(),
            },
            "sources": debug_sources,
        },
    }
