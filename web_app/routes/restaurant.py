from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import json
import os
from threading import Lock
from web_app.models.schema import ReservationRequest

router = APIRouter()

# --- 路徑設定 ---
current_file_path = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
DATA_DIR = os.path.join(BASE_DIR, "output_json")
MAIN_JSON_PATH = os.path.join(DATA_DIR, "restaurants_main.json")
GALLERY_JSON_PATH = os.path.join(DATA_DIR, "restaurants_gallery.json")
RESERVATIONS_FILE = os.path.join(DATA_DIR, "reservations.json")

class RestaurantSystem:
    def __init__(self):
        self.restaurants_db = []
        self.gallery_db = []
        self.id_to_restaurant = {}   
        self.name_to_restaurant = {} 
        self.lock = Lock()           
        self.load_data()

    def load_data(self):
        """初始化時載入所有 JSON 資料"""
        if os.path.exists(MAIN_JSON_PATH):
            with open(MAIN_JSON_PATH, "r", encoding="utf-8") as f:
                self.restaurants_db = json.load(f)
            # 建立索引：加快詳情頁查詢速度
            self.name_to_restaurant = {r["Name"]: r for r in self.restaurants_db}
            self.id_to_restaurant = {r.get("ID", ""): r for r in self.restaurants_db}
            print(f"✅ [System] 已載入 {len(self.restaurants_db)} 筆餐廳資料")
        
        if os.path.exists(GALLERY_JSON_PATH):
            with open(GALLERY_JSON_PATH, "r", encoding="utf-8") as f:
                self.gallery_db = json.load(f)
            print(f"✅ [System] 已載入相簿資料")
    # 取得分頁清單 python slicing
    def get_list(self, skip: int = 0, limit: int = 20):
        """取得分頁清單"""
        return self.restaurants_db[skip : skip + limit]

    def search(self, 
               q: Optional[str] = None, 
               tags: Optional[List[str]] = None, 
               city: Optional[str] = None, 
               price_level: Optional[str] = None):
        results = self.restaurants_db
        
        # 1. 關鍵字過濾 (名稱、描述、地址)
        if q:
            keyword = q.strip().lower()
            results = [
                r for r in results 
                if keyword in (str(r.get("Name", "")) + str(r.get("Description", "")) + str(r.get("Add", ""))).lower()
            ]
        
        # 2. 縣市過濾
        if city and city != "全部":
            results = [r for r in results if r.get("City") == city]
            
        # 3. 價格等級過濾 (例如: "$", "$$", "$$$")
        if price_level and price_level != "全部":
            results = [r for r in results if r.get("PriceLevel") == price_level]
            
        # 4. 標籤過濾 (支援多選，採交集並去空白)
        if tags:
            search_tags = set(t.strip() for t in tags if t.strip())
            filtered = []
            for r in results:
                # 把 multi tags 切開並去空轉為集合
                db_tags_str = str(r.get("TagsStr", ""))
                db_tags_set = set(t.strip() for t in db_tags_str.split(",") if t.strip())
                
                # 只要搜尋標籤與資料標籤有重疊就納入
                if search_tags & db_tags_set:
                    filtered.append(r)
            results = filtered
                
        return results

    def save_reservation(self, booking_data: dict):
        """執行預約並存檔，加入 Lock 機制確保安全"""
        with self.lock:
            current_bookings = []
            if os.path.exists(RESERVATIONS_FILE):
                try:
                    with open(RESERVATIONS_FILE, "r", encoding="utf-8") as f:
                        current_bookings = json.load(f)
                except:
                    pass
            
            current_bookings.append(booking_data)
            with open(RESERVATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(current_bookings, f, ensure_ascii=False, indent=2)

# --- 實例化管理系統 (啟動引擎) ---
sys = RestaurantSystem()

# --- API 路由區 (外部定義) ---

# 3. [全部餐廳列表]
@router.get("/api/restaurants")  
async def get_all_restaurants(skip: int = 0, limit: int = 20):
    return sys.get_list(skip, limit)

# 4. [連動搜尋 API]
@router.get("/api/search")      
def search_restaurants(
    q: Optional[str] = None, 
    tags: List[str] = Query(None), 
    city: Optional[str] = None, 
    price_level: Optional[str] = None
):
    # 呼叫類別實例 sys 的 search 方法
    return sys.search(q=q, tags=tags, city=city, price_level=price_level)

# 5. [詳情 API]
@router.get("/api/restaurant/{name}")  
def get_restaurant_detail(name: str):
    info = sys.name_to_restaurant.get(name)
    if not info:
        raise HTTPException(status_code=404, detail="找不到此餐廳")
    
    gallery_data = next((g for g in sys.gallery_db if g["restaurant_id"] == name), None)
    
    return {
        "info": info,
        "gallery": gallery_data["GalleryImages"] if gallery_data else []
    }

# 6. [預約 API]
@router.post("/api/book")  
def make_reservation(booking: ReservationRequest):
    new_data = booking.dict()
    new_data["status"] = "confirmed"
    
    try:
        sys.save_reservation(new_data)
        return {"status": "success", "message": f"預約成功！{booking.user_name} 先生/小姐"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="預約失敗，請稍後再試")