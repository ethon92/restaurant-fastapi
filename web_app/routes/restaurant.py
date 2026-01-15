from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from web_app.models.schema import ReservationRequest
# 引入您的資料庫連線模組
from web_app.mysql_connection import get_db_cursor

router = APIRouter()

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
            
        # 5. 標籤過濾 (DB 中 TagsStr 是字串 "Tag1,Tag2"，使用 LIKE 搜尋)
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

    def get_detail_by_name(self, name: str):
        """[DB] 取得單一餐廳詳情"""
        sql = "SELECT * FROM restaurants WHERE Name = %s"
        with get_db_cursor() as cursor:
            cursor.execute(sql, (name,))
            return cursor.fetchone()

    def save_reservation(self, booking_data: dict):
        """[DB] 寫入預約資料到 MySQL"""
        sql = """
            INSERT INTO reservations 
            (restaurant_name, user_name, phone, email, party_size, booking_time, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            booking_data.get("restaurant_name"),
            booking_data.get("user_name"),
            booking_data.get("phone"),
            booking_data.get("email"),
            booking_data.get("party_size"),
            booking_data.get("booking_time"),
            booking_data.get("status", "confirmed")
        )
        
        # commit=True 代表要真的寫入資料庫
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, params)
        
    #用來刪除資料的
    def get_all_reservations(self):
        """[DB] 取得所有預約資料 (依時間新到舊排序)"""
        # ORDER BY created_at DESC 讓最新的預約排在最上面，方便你找剛測試的資料
        sql = "SELECT * FROM reservations ORDER BY created_at DESC"
        with get_db_cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

    def delete_reservation(self, reservation_id: int):
        """[DB] 根據 ID 刪除預約"""
        sql = "DELETE FROM reservations WHERE id = %s"
        
        # commit=True 代表要真的執行刪除動作
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, (reservation_id,))
            # rowcount 代表「影響了幾筆資料」，如果 > 0 代表有刪到東西
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
@router.get("/api/restaurant/{name}")  
def get_restaurant_detail(name: str):
    info = sys.get_detail_by_name(name)
    
    if not info:
        raise HTTPException(status_code=404, detail="找不到此餐廳")
    
    # 注意：因為目前資料庫只有 restaurants 表，沒有 gallery 表
    # 所以這裡暫時回傳空的 gallery，或是把封面圖當作第一張圖
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
    except Exception as e:
        print(f"Error occurred during reservation: {e}")
        raise HTTPException(status_code=500, detail=f"預約失敗: {str(e)}")
    
# 5. [查看所有預約 API] (管理員用)
@router.get("/api/reservations")
def get_reservations():
    """列出所有預約，方便查看 ID 來刪除"""
    return sys.get_all_reservations()

# 6. [刪除預約 API]
@router.delete("/api/reservation/{reservation_id}")
def delete_reservation(reservation_id: int):
    """輸入預約 ID 來刪除該筆資料"""
    success = sys.delete_reservation(reservation_id)
    
    if success:
        return {"status": "success", "message": f"預約 ID {reservation_id} 已刪除"}
    else:
        # 如果 ID 不存在
        raise HTTPException(status_code=404, detail="刪除失敗，找不到此預約 ID")