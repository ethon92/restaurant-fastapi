from fastapi import APIRouter, HTTPException, Query, Path
from web_app.mysql_connection import get_db_cursor
import pymysql
from typing import List, Optional, Annotated
from web_app.models.schema import ReservationRequest
from web_app.models.schema import RestaurantSchema 

router = APIRouter()


# 建立reservation的table
def create_reservations_table(cursor):
    create_query = """
    CREATE TABLE reservations (
            booking_id INT AUTO_INCREMENT PRIMARY KEY,
            restaurant_name varchar(100),
            user_id int,
            user_name Varchar(50),
            phone varchar(20),
            email varchar(100),
            party_size int,
            note text,
            booking_time datetime,
            booking_status Varchar(30) DEFAULT 'confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_reservations_user
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
            CONSTRAINT unique_booking UNIQUE (user_id, booking_time)
        );
    """
    cursor.execute("show tables like %s", ("reservations",))
    result = cursor.fetchone()
    if result is None:
        try:
            cursor.execute(create_query)
            print("reservations table created (Normalized Version)!!!")
        except pymysql.Error as e:
            print(f"Error create table: {e}")


# 建立comment的table
def create_comment_table(cursor):
    create_query = """
    create table comments (
        comment_id int primary key auto_increment,
        user_id int not null,
        restaurant_id varchar(50) not null,             
        comment_content varchar(255) not null,   
        rating int not null check(rating >= 1 AND rating <= 5),              
        comment_time DATETIME DEFAULT CURRENT_TIMESTAMP 
    );
    """
    cursor.execute("show tables like %s", ("comments"))
    result = cursor.fetchone()
    # 當沒有table時才建立
    if result is None:
        try:
            cursor.execute(create_query)
            print("comments table is created!!")
        except pymysql.Error as e:
            print(f"Error create comment table: {e}")


# 查詢評論餐廳路由
@router.get("/RestaurantComment/{restaurant_id}")
def get_restaurant_comment(restaurant_id: str):
    try:
        with get_db_cursor() as cursor:
            sql = """
                select comment_id, user_id, Name, comment_content, rating, comment_time from comments join restaurants on restaurant_id = ID where restaurant_id=%s
                """
            cursor.execute(sql, (restaurant_id,))
            results = cursor.fetchall()
        return {"status": "Success", "restaurant_id": restaurant_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{e}")


class RestaurantSystem:
    def get_list(self, skip: int = 0, limit: int = 20):
        """[DB] 取得分頁清單"""
        sql = "SELECT * FROM restaurants LIMIT %s OFFSET %s"
        with get_db_cursor() as cursor:
            cursor.execute(sql, (limit, skip))
            result = cursor.fetchall()
            return result

    def search(
        self,
        q: Optional[str] = None,
        tags: Optional[List[str]] = None,
        city: Optional[str] = None,
        price_level: Optional[str] = None,
    ):
        """[DB] 搜尋功能 (動態 SQL 拼裝)"""
        # 1. 檢查關鍵字 (排除 None 和 空字串)
        has_q = q is not None and q.strip() != ""
        # 2. 檢查地點 (排除 None 和 "全部")
        has_city = city is not None and city != "全部"
        # 3. 檢查價格 (排除 None 和 "全部")
        has_price = price_level is not None and price_level != "全部"
        # 4. 檢查標籤 (排除 None、空列表、以及列表裡只有空字串的情況)
        has_tags = tags is not None and any(t.strip() for t in tags)
        # 如果「沒有」任何有效條件，直接回傳空列表 []
        if not any([has_q, has_city, has_price, has_tags]):
            print(" 未輸入搜尋條件，回傳預設前 20 筆")
            return self.get_list(skip=0, limit=20)

        # 1. 基礎 SQL
        sql = "SELECT * FROM restaurants WHERE 1=1"
        params = []

        # 2. 關鍵字過濾 (名稱、描述、地址)
        if q:
            sql += " AND (Name LIKE %s OR Description LIKE %s OR `Add` LIKE %s)"
            keyword = f"%{q.strip()}%"
            params.extend([keyword, keyword, keyword])

        # 3. 縣市過濾
        if city and city != "全部":
            sql += " AND City = %s"
            params.append(city)

        # 4. 價格等級過濾
        if price_level and price_level != "全部":
            sql += " AND PriceLevel = %s"
            params.append(price_level)

        # 5. 標籤過濾
        # 邏輯：只要符合其中一個標籤即可 (OR 邏輯)
        if tags:
            tag_conditions = []
            for t in tags:
                if t.strip():
                    tag_conditions.append("TagsStr LIKE %s")
                    params.append(f"%{t.strip()}%")

            if tag_conditions:
                sql += " AND (" + " OR ".join(tag_conditions) + ")"

        # 執行查詢
        with get_db_cursor() as cursor:
            cursor.execute(sql, tuple(params))
            return cursor.fetchall()

    def get_detail_by_id(self, restaurant_id: str):
        """[DB] 取得單一餐廳詳情"""
        sql = "SELECT * FROM restaurants WHERE ID = %s"
        with get_db_cursor() as cursor:
            cursor.execute(sql, (restaurant_id,))
            return cursor.fetchone()

    def get_restaurants_by_bounds(
        self, min_lat: float, max_lat: float, min_lng: float, max_lng: float
    ):
        
        sql = """SELECT ID, Name, `Add`, Px, Py, GoogleMap, CoverImage, TagsStr 
             FROM restaurants WHERE 
             Py BETWEEN %s AND %s 
             AND Px BETWEEN %s AND %s"""
        
        params = (min_lat, max_lat, min_lng, max_lng)
        
        with get_db_cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    
        
    def save_reservation(self, booking_data: dict):
        """[DB] 寫入預約資料到 MySQL"""
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
                new_id = cursor.lastrowid
                return new_id
        except pymysql.err.IntegrityError as e:
            if e.args[0] == 1062:
                raise ValueError("DuplicateBooking")
            if e.args[0] == 1452:
                raise ValueError("InvalidUser")
            raise e

    # 用來刪除資料的
    def cancel_reservation(self, reservation_id: int):
        """
        [DB] 真正的刪除 (Hard Delete)
        直接從資料庫移除該筆預約紀錄
        """
        sql = "DELETE FROM reservations WHERE booking_id = %s"

        with get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, (reservation_id,))
            return cursor.rowcount > 0


# --- 實例化管理系統 ---
sys = RestaurantSystem()

# --- API 路由區 ---


# 1. [全部餐廳列表]
@router.get("/api/restaurants")
async def get_all_restaurants(skip: int = 0, limit: int = 20):
    return sys.get_list(skip, limit)


# 2. [連動搜尋 API]
@router.get("/api/search", response_model=List[RestaurantSchema])
def search_restaurants(
    q: Optional[str] = None,
    tags: List[str] = Query(None), 
    city: Optional[str] = None,
    price_level: Optional[str] = None,
):
    results = sys.search(q=q, tags=tags, city=city, price_level=price_level)
    return results 
    


# 3. [詳情 API]
@router.get("/api/restaurant/{id}")
def get_restaurant_detail(id: str):
    info = sys.get_detail_by_id(id)

    if not info:
        raise HTTPException(status_code=404, detail="找不到此餐廳")
    gallery_images = []
    if info.get("CoverImage"):
        gallery_images.append(info["CoverImage"])

    return {"info": info, "gallery": gallery_images}


# 4.[地圖搜尋範圍API]
@router.get("api/restaurant/map-searching")
async def get_restaurants_by_bounds(
    min_lat: float, max_lat: float, min_lng: float, max_lng: float
):
    results = sys.get_restaurants_by_bounds(min_lat, max_lat, min_lng, max_lng)
    if not results:
        return[]
    return results


# 5. [新增預約 API]
@router.post("/api/reservations")
def add_reservations(booking: ReservationRequest):
    try:
        new_id = sys.save_reservation(booking.dict())
        full_data = None

        with get_db_cursor() as cursor:
            sql = """
                SELECT r.*, u.user_name as member_name
                FROM reservations r 
                JOIN users u ON r.user_id = u.user_id 
                WHERE r.booking_id = %s
            """
            cursor.execute(sql, (new_id,))
            full_data = cursor.fetchone()
        if not full_data:
            return {
                "status": "success",
                "message": "預約成功！(系統忙碌中，請稍後至後台查看詳情)",
                "data": {"booking_id": new_id},
            }
        return {
            "status": "success",
            "message": f"預約成功！歡迎 {full_data['member_name']} 會員",
            "data": full_data,
        }
    except ValueError as ve:
        if str(ve) == "DuplicateBooking":
            raise HTTPException(
                status_code=409, detail="該時段您已有預約，請勿重複提交!!"
            )
        if str(ve) == "InvalidUser":
            raise HTTPException(status_code=400, detail="無效的會員 ID，請先註冊!!")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"系統錯誤: {e}")


# 6. [刪除預約 API]
@router.delete("/api/reservations/{user_id}/{booking_id}")
def delete_reservation(
    user_id: Annotated[int, Path(title="The ID of user", gt=0)], booking_id: int
):
    try:
        with get_db_cursor(commit=True) as cursor:
            check_sql = "SELECT * FROM reservations WHERE user_id=%s AND booking_id=%s"
            cursor.execute(check_sql, (user_id, booking_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="找不到此筆預約資料!!")

            delete_sql = "DELETE FROM reservations WHERE user_id=%s AND booking_id=%s"
            cursor.execute(delete_sql, (user_id, booking_id))
            return {"status": "Success", "message": "預約已成功取消"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤：{e}")


# 7.  商家後台專用：查詢所有訂單 (b2b)
# @router.get("/api/admin/reservations")
# def get_admin_reservations(
# 這裡加入 params，設為必填 (因為老闆一定屬於某家店)
#     restaurant_name: str = Query(..., description="請輸入餐廳名稱")
# ):
#     try:
#         with get_db_cursor() as cursor:
#             sql = """
#                 SELECT
#                     r.booking_id,
#                     r.booking_time,
#                     r.party_size,
#                     r.note,
#                     r.booking_status,
#                     u.user_name,
#                     u.user_phone
#                 FROM reservations r
#                 JOIN users u ON r.user_id = u.user_id
#                 WHERE r.restaurant_name = %s
#                 ORDER BY r.booking_time DESC
#             """
#             cursor.execute(sql, (restaurant_name,))

#             results = cursor.fetchall()
#             return {"status": "Success", "results": results}

#     except Exception as e:
#         print(f"Admin Error: {e}")
#         raise HTTPException(status_code=500, detail="資料庫查詢失敗")
