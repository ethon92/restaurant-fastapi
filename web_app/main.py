from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware  # 來自 HEAD
from pydantic import BaseModel
import json
import os
from typing import List, Optional

# 引入 develop 分支已經做好的 router
from web_app.routes.feature import router as favorite_router

app = FastAPI()

# ================= CORS 設定 (來自 HEAD，保留它) =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # production環境要限制特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ================= 路徑與資料設定 (來自你的分支) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 資料庫路徑
DATA_DIR = os.path.join(BASE_DIR, "output_json")
MAIN_JSON_PATH = os.path.join(DATA_DIR, "restaurants_main.json")
GALLERY_JSON_PATH = os.path.join(DATA_DIR, "restaurants_gallery.json")
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations.json")

# 設定靜態檔案資料夾為 "static"
STATIC_DIR = os.path.join(BASE_DIR, "static")

#  資料載入區 
restaurants_db = []
gallery_db = []

def load_data():
    global restaurants_db, gallery_db
    if os.path.exists(MAIN_JSON_PATH):
        with open(MAIN_JSON_PATH, "r", encoding="utf-8") as f:
            restaurants_db = json.load(f)
        print(f"✅ 已載入 {len(restaurants_db)} 筆餐廳主資料")
    else:
        print(f"❌ 警告：找不到主資料檔！")

    if os.path.exists(GALLERY_JSON_PATH):
        with open(GALLERY_JSON_PATH, "r", encoding="utf-8") as f:
            gallery_db = json.load(f)
        print(f"✅ 已載入相簿資料")

load_data()

# ================= 資料模型 =================
class ReservationRequest(BaseModel):
    restaurant_name: str
    user_name: str
    phone: str
    date: str
    time: str
    people: int

# ================= API 路由區 =================

# 1. [掛載 HEAD 的路由] (不要漏掉別人做的功能)
app.include_router(favorite_router)

# 2. [靜態檔案掛載]
# 這裡設定 directory="static"，對應你的實體資料夾名稱
app.mount("/static", StaticFiles(directory="static"), name="static")

# 3. [首頁路由]
@app.get("/")
async def read_index():
    # 這裡會去讀取 web_app/static/index.html
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# 4. [全部餐廳列表]
@app.get("/api/restaurants")
async def get_all_restaurants():
    return restaurants_db

# 5. [搜尋 API]
@app.get("/api/search")
def search_restaurants(q: Optional[str] = None, tags: List[str] = Query(None)):
    if not q and not tags:
        return restaurants_db
    
    keyword = q.strip().lower() if q else ""
    results = []
    
    for r in restaurants_db:
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
            if not (set(tags) & set(r_tags_list)):
                match_tags = False
        
        if match_keyword and match_tags:
            results.append(r)
            
    return results

# 6. [詳情 API]
@app.get("/api/restaurant/{name}")
def get_restaurant_detail(name: str):
    info = next((r for r in restaurants_db if r["Name"] == name), None)
    if not info:
        raise HTTPException(status_code=404, detail="找不到此餐廳")
    gallery_data = next((g for g in gallery_db if g["restaurant_id"] == name), None)
    return {
        "info": info,
        "gallery": gallery_data["GalleryImages"] if gallery_data else []
    }

# 7. [預約 API]
@app.post("/api/book")
def make_reservation(booking: ReservationRequest):
    current_bookings = []
    if os.path.exists(RESERVATIONS_FILE):
        try:
            with open(RESERVATIONS_FILE, "r", encoding="utf-8") as f:
                current_bookings = json.load(f)
        except:
            pass
    new_data = booking.dict()
    new_data["status"] = "confirmed"
    current_bookings.append(new_data)
    with open(RESERVATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(current_bookings, f, ensure_ascii=False, indent=2)
    return {"status": "success", "message": f"預約成功！{booking.user_name} 先生/小姐"}