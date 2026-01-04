from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import json
import os
from models.schema import ReservationRequest 

router = APIRouter() # 👈 使用 APIRouter 而不是 FastAPI

# --- 把原本資料設定與變數搬過來 ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 注意路徑層級可能要調整
DATA_DIR = os.path.join(BASE_DIR, "output_json")
MAIN_JSON_PATH = os.path.join(DATA_DIR, "restaurants_main.json")
GALLERY_JSON_PATH = os.path.join(DATA_DIR, "restaurants_gallery.json")
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations.json")

# 資料變數初始化
restaurants_db = []
gallery_db = []

# 資料載入函式
def load_data():
    global restaurants_db, gallery_db
    # 載入餐廳主資料
    if os.path.exists(MAIN_JSON_PATH):
        with open(MAIN_JSON_PATH, "r", encoding="utf-8") as f:
            restaurants_db = json.load(f)
        print(f"✅ [Router] 已載入 {len(restaurants_db)} 筆餐廳資料")
    else:
        print(f"❌ [Router] 找不到主資料檔：{MAIN_JSON_PATH}")

    # 載入相簿資料
    if os.path.exists(GALLERY_JSON_PATH):
        with open(GALLERY_JSON_PATH, "r", encoding="utf-8") as f:
            gallery_db = json.load(f)
        print(f"✅ [Router] 已載入相簿資料")

# 執行載入
load_data()

# API 路由區 

# 3. [全部餐廳列表]
@router.get("/api/restaurants")  
async def get_all_restaurants():
    return restaurants_db

# 4. [搜尋 API]
@router.get("/api/search")      
def search_restaurants(q: Optional[str] = None, tags: List[str] = Query(None)):
    if not q and not tags:
        return restaurants_db
    
    keyword = q.strip().lower() if q else ""
    results = []
    
    for r in restaurants_db:
        # 加上 str() 避免資料欄位缺失導致報錯
        name = str(r.get("Name", "")).lower()
        desc = str(r.get("Description", "")).lower()
        address = str(r.get("Add", "")).lower()
        r_tags_list = str(r.get("TagsStr", "")).split(",")
        
        match_keyword = True
        match_tags = True
        
        if keyword:
            all_text = name + desc + address + str(r.get("TagsStr", "")).lower()
            if keyword not in all_text:
                match_keyword = False
        
        if tags:
            # 檢查標籤交集
            if not (set(tags) & set(r_tags_list)):
                match_tags = False
        
        if match_keyword and match_tags:
            results.append(r)
            
    return results

# 5. [詳情 API]
@router.get("/api/restaurant/{name}")  
def get_restaurant_detail(name: str):
    info = next((r for r in restaurants_db if r["Name"] == name), None)
    if not info:
        raise HTTPException(status_code=404, detail="找不到此餐廳")
    
    gallery_data = next((g for g in gallery_db if g["restaurant_id"] == name), None)
    
    return {
        "info": info,
        "gallery": gallery_data["GalleryImages"] if gallery_data else []
    }

# 6. [預約 API]
@router.post("/api/book")  
def make_reservation(booking: ReservationRequest):
    current_bookings = []
    # 讀取舊有預約
    if os.path.exists(RESERVATIONS_FILE):
        try:
            with open(RESERVATIONS_FILE, "r", encoding="utf-8") as f:
                current_bookings = json.load(f)
        except:
            pass
            
    # 新增預約
    new_data = booking.dict()
    new_data["status"] = "confirmed"
    current_bookings.append(new_data)
    
    # 寫入檔案
    with open(RESERVATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(current_bookings, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "message": f"預約成功！{booking.user_name} 先生/小姐"}