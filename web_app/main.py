from fastapi import FastAPI
from web_app.routes.feature import router as favorite_router
from web_app.routes.account import router as account_router
from web_app.routes.restaurant import router as restaurant_router
from web_app.routes.account import router as booking_record_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from web_app.routes.auth import router as auth_router


# 1. 引入 develop 分支的 Router (收藏功能)
from web_app.routes.feature import router as favorite_router

# 2. 引入你自己的 Router (這裡面已經包含了：餐廳列表、搜尋功能、預約功能)
# 只要引入這個，你的那些功能就會全部回來，不用寫在 main.py 裡
from web_app.routes import restaurant

app = FastAPI()

# ================= CORS 設定 (保留 HEAD 的設定) =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= 靜態檔案設定 =================
current_file_path = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(current_file_path))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 掛載 static 資料夾
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ================= 註冊 Routers (功能合併區) =================

# 註冊：收藏功能 (來自 Develop)
app.include_router(favorite_router)
app.include_router(account_router)
app.include_router(restaurant_router)
app.include_router(booking_record_router)

# 註冊：餐廳主功能 (來自你的 Refactor)
# 這行指令會自動把 search_restaurants 和 make_reservation 的功能掛載進來
app.include_router(restaurant.router)

# 加入 auth
app.include_router(auth_router)

@app.get("/")
def root():
    return {
        'msg':"HEllO, it's black window!"
    }
