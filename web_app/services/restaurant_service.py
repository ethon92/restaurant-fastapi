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


    def search(self, q: str, tags: List[str], city: List[str], price_level: str, skip: int = 0, limit: int = 5, semantic_svc=None):
        has_q = q.strip() != ""
        has_city = city and len(city) > 0 and "全部" not in city
        has_price = price_level != "全部"
        has_tags = len(tags) > 0 and any(t.strip() for t in tags)

        if not any([has_q, has_city, has_price, has_tags]):
            return self.get_list(skip=0, limit=20)

        # --- 語意搜尋路徑（有 q + 有 semantic_svc）---
        if has_q and semantic_svc:
            candidate_ids = semantic_svc.search(q, top_k=50)
            if not candidate_ids:
                return []

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

            # 保留 Chroma 回傳的相似度排序
            order_ph = ', '.join(['%s'] * len(candidate_ids))
            sql += f" ORDER BY FIELD(ID, {order_ph})"
            params.extend(candidate_ids)

            sql += " LIMIT %s OFFSET %s"
            params.extend([limit, skip])

            with get_db_cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return cursor.fetchall()

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