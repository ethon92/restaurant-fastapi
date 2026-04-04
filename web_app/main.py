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

from web_app.routes import restaurant

app = FastAPI()

# CORS 設定 (保留 HEAD 的設定) 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 靜態檔案設定 
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

app.include_router(restaurant.router)

# 加入 auth
app.include_router(auth_router)

@app.get("/")
def root():
    return {"msg": "Hello"}

