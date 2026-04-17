from web_app.mysql_connection import get_db_cursor
import pymysql
from typing import List, Optional, Any

class RestaurantService:
    def __init__(self):
        pass
    
    def init_tables(self):
        """初始化專案所需的資料表"""
        with get_db_cursor(commit=True) as cursor:
            # 1. 建立 reservations
            cursor.execute("SHOW TABLES LIKE 'reservations'")
            if not cursor.fetchone():
                create_res_sql = """
CREATE TABLE reservations (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_name VARCHAR(100),
    user_id INT,
    user_name VARCHAR(50),
    phone VARCHAR(20),
    email VARCHAR(100),
    party_size INT,
    note TEXT,
    booking_time DATETIME,
    booking_status VARCHAR(30) DEFAULT 'confirmed',
    is_commented TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已評論：0為否，1為是',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reservations_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    CONSTRAINT unique_booking UNIQUE (user_id, booking_time)
);
"""
                cursor.execute(create_res_sql)
                print("Table 'reservations' created.")

            # 2. 建立 comments
            cursor.execute("SHOW TABLES LIKE 'comments'")
            if not cursor.fetchone():
                create_com_sql = """
                CREATE TABLE comments (
                    comment_id int primary key auto_increment,
                    user_id int not null,
                    restaurant_id varchar(50) not null,             
                    comment_content varchar(255) not null,   
                    rating int not null check(rating >= 1 AND rating <= 5),              
                    comment_time DATETIME DEFAULT CURRENT_TIMESTAMP 
                );
                """
                cursor.execute(create_com_sql)
                print("Table 'comments' created.")
                
            # 3.建立效能索引
            indices = {
                "idx_restaurants_px": "CREATE INDEX idx_restaurants_px ON restaurants(Px)",
                "idx_restaurants_py": "CREATE INDEX idx_restaurants_py ON restaurants(Py)"
            }

            for idx_name, sql in indices.items():
                check_index_sql = f"SHOW INDEX FROM restaurants WHERE Key_name = '{idx_name}'"
                cursor.execute(check_index_sql)
                if not cursor.fetchone():
                    try:
                        cursor.execute(sql)
                        print(f" 效能優化：索引 {idx_name} 建立成功！")
                    except Exception as e:
                        print(f" 建立索引 {idx_name} 失敗: {e}")
                        
             # 4.建立restaurant_images關聯表
            cursor.execute("SHOW TABLES LIKE 'restaurant_images'")
            if not cursor.fetchone():
                 create_img_sql = """
            CREATE TABLE restaurant_images (
                image_id INT AUTO_INCREMENT PRIMARY KEY,
                restaurant_id VARCHAR(50),
                image_url VARCHAR(255),
                FOREIGN KEY (restaurant_id) REFERENCES restaurants(ID) ON DELETE CASCADE
            );
            """
            cursor.execute(create_img_sql)
            print("Table 'restaurant_images' created.")
                 

    # --- 餐廳查詢相關邏輯 ---

    def get_list(self, skip: int = 0, limit: int = 20):
        """取得餐廳分頁清單"""
        sql = "SELECT * FROM restaurants LIMIT %s OFFSET %s"
        with get_db_cursor() as cursor:
            cursor.execute(sql, (limit, skip))
            return cursor.fetchall()

    def get_detail_by_id(self, restaurant_id: str):
        """取得單一餐廳詳情，含隨機選取的圖片"""
        sql_main = "SELECT * FROM restaurants WHERE ID = %s"
        
        sql_images = "SELECT image_url FROM restaurant_images WHERE restaurant_id = %s"
        
        with get_db_cursor() as cursor:
            cursor.execute(sql_main, (restaurant_id,))
            restaurant = cursor.fetchone()
            
            if restaurant:
                cursor.execute(sql_images, (restaurant_id,))
            images = cursor.fetchall() 
            restaurant['images'] = images
            
        return restaurant


    # ── 查詢關鍵字 → TagsStr 料理分類對照表 ────────────────────────
    _CUISINE_MAP = {
        # 料理類型
        "美式":   "美式料理",
        "泰式":   "泰式料理",
        "義式":   "義式料理",
        "日式":   "日式料理",
        "中式":   "中式料理",
        "韓式":   "韓式料理",
        "法式":   "法式料理",
        "印度":   "印度料理",
        "越式":   "越式料理",
        "西班牙": "西班牙料理",
        "海鮮":   "海鮮料理",
        # 用餐風格
        "火鍋":   "火鍋",
        "燒烤":   "燒烤",
        "素食":   "素食",
        "早午餐": "早午餐",
        "下午茶": "甜點下午茶",
        "甜點":   "甜點下午茶",
        "景觀":   "景觀餐廳",
        "約會":   "浪漫約會",
        "網美":   "網美打卡",
        "親子":   "親子友善",
        "寵物":   "寵物友善",
        # 小吃 / 庶民
        "小吃":   "在地小吃",
        "小吃店": "在地小吃",
    }

    # ── 城市關鍵字 → ChromaDB city 值對照表 ─────────────────────────
    _CITY_MAP = {
        "台北": ["臺北市"], "臺北": ["臺北市"],
        "新北": ["新北市"],
        "桃園": ["桃園市"],
        "新竹": ["新竹市", "新竹縣"],
        "苗栗": ["苗栗縣"],
        "台中": ["臺中市"], "臺中": ["臺中市"],
        "彰化": ["彰化縣"],
        "南投": ["南投縣"],
        "雲林": ["雲林縣"],
        "嘉義": ["嘉義市", "嘉義縣"],
        "台南": ["臺南市"], "臺南": ["臺南市"],
        "高雄": ["高雄市"],
        "屏東": ["屏東縣"],
        "宜蘭": ["宜蘭縣"],
        "花蓮": ["花蓮縣"],
        "台東": ["臺東縣"], "臺東": ["臺東縣"],
        "澎湖": ["澎湖縣"],
        "金門": ["金門縣"],
        "馬祖": ["連江縣"], "連江": ["連江縣"],
    }

    # ── 私有：從查詢字串偵測料理類型，回傳要注入 SQL 的 tag list ────
    def _extract_cuisine_tags(self, query: str) -> List[str]:
        """從自然語言查詢偵測料理/風格關鍵字，回傳對應的 TagsStr 值。"""
        detected = []
        for kw, tag_value in self._CUISINE_MAP.items():
            if kw in query and tag_value not in detected:
                detected.append(tag_value)
        return detected

    # ── 私有：從查詢字串萃取 ChromaDB metadata 篩選條件 ──────────────
    def _extract_chroma_filters(self, query: str) -> dict:
        """
        從自然語言查詢萃取結構化 metadata 篩選條件。
        ChromaDB metadata 值皆以字串形式儲存（"True"/"False"）。
        城市值為完整地名（例如 "臺南市"），用 $in 做模糊縣市匹配。
        """
        conditions = []

        # 城市偵測：查詢裡有縣市名就鎖定，排除不相關縣市結果
        for kw, cities in self._CITY_MAP.items():
            if kw in query:
                conditions.append({"city": {"$in": cities}})
                break  # 只取第一個命中的城市

        # 店家類別偵測：對應 ChromaDB metadata 的 category 欄位
        # ChromaDB 現有值：特色餐廳 / 特色店家 / 複合式咖啡館 / 甜點冰品店 / 咖啡廳 / 質感餐酒館
        _CATEGORY_FILTER_MAP = [
            (["小吃", "小吃店", "庶民", "路邊攤", "在地"],
             ["特色店家"]),
            (["甜點", "冰品", "剉冰", "冰店", "冰淇淋"],
             ["甜點冰品店"]),
            (["咖啡", "咖啡廳", "café", "cafe"],
             ["複合式咖啡館", "咖啡廳"]),
            (["餐酒", "酒吧", "酒館", "bar"],
             ["質感餐酒館"]),
        ]
        for keywords, categories in _CATEGORY_FILTER_MAP:
            if any(kw in query for kw in keywords):
                conditions.append({"category": {"$in": categories}})
                break  # 只套用第一個命中的分類

        # 停車場
        if any(kw in query for kw in ["停車", "開車", "停車場", "有位停"]):
            conditions.append({"has_parking": "True"})

        # 深夜 / 宵夜營業
        if any(kw in query for kw in ["深夜", "宵夜", "消夜", "半夜", "凌晨", "通宵", "晚點"]):
            conditions.append({"is_late_night": "True"})

        if len(conditions) == 0:
            return {}
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def search(self, q: str, tags: List[str], city: List[str], price_level: str, skip: int = 0, limit: int = 5, semantic_svc=None):
        has_q = q.strip() != ""
        has_city = city and len(city) > 0 and "全部" not in city
        has_price = price_level != "全部"
        has_tags = len(tags) > 0 and any(t.strip() for t in tags)

        if not any([has_q, has_city, has_price, has_tags]):
            return self.get_list(skip=0, limit=20)

        # --- 語意搜尋路徑（有 q + 有 semantic_svc）---
        if has_q and semantic_svc:
            # Stage 1：ChromaDB bi-encoder 召回 20 筆候選（含 metadata pre-filter）
            chroma_where = self._extract_chroma_filters(q)
            candidate_ids = semantic_svc.search(q, recall_k=20, where=chroma_where or None)
            if not candidate_ids:
                return []

            # Stage 2：若有 reranker，從 MySQL 撈原始 Description 做精排
            score_map = {}
            if semantic_svc.reranker:
                id_ph = ', '.join(['%s'] * len(candidate_ids))
                with get_db_cursor() as cursor:
                    cursor.execute(
                        f"SELECT ID, Description FROM restaurants WHERE ID IN ({id_ph})",
                        tuple(candidate_ids)
                    )
                    desc_rows = cursor.fetchall()
                descriptions = {r['ID']: r['Description'] for r in desc_rows if r.get('Description')}
                candidate_ids, score_map = semantic_svc.rerank(q, candidate_ids, descriptions, top_k=limit)

            id_ph = ', '.join(['%s'] * len(candidate_ids))
            sql = f"SELECT * FROM restaurants WHERE ID IN ({id_ph})"
            params: List[Any] = list(candidate_ids)

            if has_city:
                city_ph = ', '.join(['%s'] * len(city))
                sql += f" AND City IN ({city_ph})"
                params.extend(city)

            if has_price:
                sql += " AND PriceLevel = %s"
                params.append(price_level)

            if has_tags:
                tag_conditions = []
                for t in tags:
                    if t.strip():
                        tag_conditions.append("TagsStr LIKE %s")
                        params.append(f"%{t.strip()}%")
                if tag_conditions:
                    sql += " AND (" + " OR ".join(tag_conditions) + ")"

            # 保留 rerank 後的排序
            order_ph = ', '.join(['%s'] * len(candidate_ids))
            sql += f" ORDER BY FIELD(ID, {order_ph})"
            params.extend(candidate_ids)

            sql += " LIMIT %s OFFSET %s"
            params.extend([limit, skip])

            with get_db_cursor() as cursor:
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
            for r in rows:
                r['match_score'] = score_map.get(r['ID'])
            return rows

        # --- 原本的 LIKE 路徑（無 q 或 Chroma 未啟動）---
        sql = "SELECT * FROM restaurants WHERE 1=1"
        params: List[Any] = []

        if has_q:
            sql += " AND (Name LIKE %s OR Description LIKE %s OR `Add` LIKE %s)"
            keyword = f"%{q.strip()}%"
            params.extend([keyword, keyword, keyword])

        if has_city:
            placeholders = ', '.join(['%s'] * len(city))
            sql += f" AND City IN ({placeholders})"
            params.extend(city)

        if has_price:
            sql += " AND PriceLevel = %s"
            params.append(price_level)

        if has_tags:
            tag_conditions = []
            for t in tags:
                if t.strip():
                    tag_conditions.append("TagsStr LIKE %s")
                    params.append(f"%{t.strip()}%")
            if tag_conditions:
                sql += " AND (" + " OR ".join(tag_conditions) + ")"

        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, skip])

        with get_db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            return cursor.fetchall()

    def get_restaurants_by_bounds(self, min_lat: float, max_lat: float, min_lng: float, max_lng: float, q: Optional[str] = None, city: Optional[List[str]] = None):
        """地圖範圍搜尋 (支援關鍵字篩選)"""
        sql = """SELECT ID, Name, `Add`, Px, Py, GoogleMap, CoverImage, TagsStr, PriceLevel 
             FROM restaurants WHERE 
             Py BETWEEN %s AND %s AND Px BETWEEN %s AND %s"""
        params: List[Any] = [min_lat, max_lat, min_lng, max_lng]
        
        if q and q.strip():
            sql += " AND (Name LIKE %s OR Description LIKE %s OR `Add` LIKE %s)"
            keyword = f"%{q.strip()}%"
            params.extend([keyword, keyword, keyword])
        if city and len(city) > 0:
            placeholders = ', '.join(['%s'] * len(city))
            sql += f" AND City IN ({placeholders})"
            params.extend(city)
        
        sql += " LIMIT 150"

        with get_db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            return cursor.fetchall()

    # --- 評論與預約邏輯 ---

    def get_comments_by_restaurant(self, restaurant_id: str):
        """查詢餐廳評論"""
        sql = """
            SELECT c.comment_id, c.user_id, r.Name, c.comment_content, c.rating, c.comment_time 
            FROM comments c
            JOIN restaurants r ON c.restaurant_id = r.ID 
            WHERE c.restaurant_id = %s
        """
        with get_db_cursor() as cursor:
            cursor.execute(sql, (restaurant_id,))
            return cursor.fetchall()

    def save_reservation(self, booking_data: dict):
        """寫入預約資料並回傳新 ID"""
        sql = """
            INSERT INTO reservations 
            (restaurant_name, user_id, user_name, phone, email, party_size, booking_time, booking_status, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            booking_data.get("restaurant_name"),
            booking_data.get("user_id"),
            booking_data.get("user_name"),
            booking_data.get("phone"),
            booking_data.get("email"),
            booking_data.get("party_size"),
            booking_data.get("booking_time"),
            booking_data.get("booking_status", "confirmed"),
            booking_data.get("note"),
        )
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(sql, params)
                return cursor.lastrowid
        except pymysql.err.IntegrityError as e:
            if e.args[0] == 1062: raise ValueError("DuplicateBooking")
            if e.args[0] == 1452: raise ValueError("InvalidUser")
            raise e

    def get_reservation_full_detail(self, booking_id: int):
        """取得預約詳情（包含會員名稱連結）"""
        sql = """
            SELECT r.*, u.user_name as member_name
            FROM reservations r 
            JOIN users u ON r.user_id = u.user_id 
            WHERE r.booking_id = %s
        """
        with get_db_cursor() as cursor:
            cursor.execute(sql, (booking_id,))
            return cursor.fetchone()

    def delete_reservation(self, user_id: int, booking_id: int):
        """刪除預約 (取消)"""
        # 先檢查是否存在
        check_sql = "SELECT 1 FROM reservations WHERE user_id=%s AND booking_id=%s"
        delete_sql = "DELETE FROM reservations WHERE user_id=%s AND booking_id=%s"
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(check_sql, (user_id, booking_id))
            if not cursor.fetchone():
                return False
            cursor.execute(delete_sql, (user_id, booking_id))
            return True