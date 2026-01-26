from fastapi import APIRouter, HTTPException
from web_app.mysql_connection import get_db_cursor
import pymysql
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from web_app.models.schema import ReservationRequest
# 引入您的資料庫連線模組
from web_app.mysql_connection import get_db_cursor
import pymysql

router = APIRouter()

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

# 查詢評論餐廳路由(根據 restaurant ID)
@router.get("/RestaurantComment/{restaurant_id}")
def get_restaurant_comment(restaurant_id:str):
    try:
        with get_db_cursor() as cursor:
            sql = """
                select comment_id, user_id, Name, comment_content, rating, comment_time from comments join restaurants on restaurant_id = ID where restaurant_id=%s
                """
            cursor.execute(sql,(restaurant_id))
            results = cursor.fetchall()
        return {
            "status": "Success",
            "restaurant_id": restaurant_id,
            "results": results
        }
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

    def search(self, 
            q: Optional[str] = None, 
            tags: Optional[List[str]] = None, 
            city: Optional[str] = None, 
            price_level: Optional[str] = None):
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
            print(" 未輸入搜尋條件，直接回傳空集合")
            return []
        
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

    def save_reservation(self, booking_data: dict):
        """[DB] 寫入預約資料到 MySQL"""
        sql = """
            INSERT INTO reservations 
            (restaurant_name, user_id, user_name, phone, party_size, booking_time, booking_status, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            booking_data.get("restaurant_name"),
            booking_data.get("user_id"),
            booking_data.get("user_name"), # 對應 user_name
            booking_data.get("phone"),
            booking_data.get("party_size"),
            booking_data.get("booking_time"),
            booking_data.get("booking_status", "confirmed"),                     
            booking_data.get("note")          
        )
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(sql, params)
        except pymysql.err.IntegrityError as e:
            if e.args[0] == 1062:
                raise ValueError("DuplicateBooking")
            if e.args[0] == 1452:
                raise ValueError("InvalidUser")
            raise e
        
    #用來刪除資料的
    def cancel_reservation(self, reservation_id: int):
        """
        [DB] 真正的刪除 (Hard Delete)
        直接從資料庫移除該筆預約紀錄
        """
        sql = "DELETE FROM reservations WHERE booking_id = %s"
        
        # commit=True 代表要真的執行修改動作
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
@router.get("/api/search")      
def search_restaurants(
    q: Optional[str] = None, 
    tags: List[str] = Query(None), 
    city: Optional[str] = None, 
    price_level: Optional[str] = None
):
    return sys.search(q=q, tags=tags, city=city, price_level=price_level)

# 3. [詳情 API]
@router.get("/api/restaurant/{id}")  
def get_restaurant_detail(id: str):
    info = sys.get_detail_by_id(id)
    
    if not info:
        raise HTTPException(status_code=404, detail="找不到此餐廳")
    gallery_images = []
    if info.get('CoverImage'):
        gallery_images.append(info['CoverImage'])

    return {
        "info": info,
        "gallery": gallery_images 
    }

# 4. [預約 API]
@router.post("/api/book")  
def make_reservation(booking: ReservationRequest):
    new_data = booking.dict()
    
    try:
        sys.save_reservation(new_data)
        return {"status": "success", "message": f"預約成功！{booking.user_name} 先生/小姐"}
    except ValueError as ve:
        error_msg = str(ve)
        if error_msg == "DuplicateBooking":
            raise HTTPException(status_code=400, detail="您在該時段已有預約，請勿重複提交")
        if error_msg == "InvalidUser":
            raise HTTPException(status_code=400, detail="使用者帳號無效或已註銷")
    except Exception as e:
        print(f"Error occurred during reservation: {e}")
        raise HTTPException(status_code=500, detail=f"預約失敗: {str(e)}")

# 5. [刪除預約 API]
@router.delete("/api/reservation/{reservation_id}")
def cancel_reservation(reservation_id: int):
    """
    輸入預約 ID 來永久刪除該筆資料。
    """
    success = sys.cancel_reservation(reservation_id)
    
    if success:
        return {"status": "success", "message": f"預約 ID {reservation_id} 已從系統中永久刪除"}
    else:
        # 如果 ID 不存在
        raise HTTPException(status_code=404, detail="取消失敗，找不到此預約 ID")
