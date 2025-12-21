import pandas as pd
from sqlalchemy import create_engine
import os
from urllib.parse import quote_plus

# ==========================================
# 1. 設定 MySQL 連線資訊 (請務必修改這裡！)
# ==========================================
DB_USER = "root"  # 通常是 root
DB_PASSWORD = "As603@118"
DB_HOST = "localhost"  # 本機
DB_PORT = "3306"  # 預設 Port
DB_NAME = "restaurant_food"  # 剛剛在 Workbench 建立的資料庫名稱

# 建立連線引擎 (這是 Python 跟 MySQL 溝通的橋樑)
# 建立連線引擎
try:
    # ★★★ 關鍵修改：用 quote_plus 把密碼包起來，處理那個 @ 符號 ★★★
    encoded_password = quote_plus(DB_PASSWORD)

    # 注意：這裡的變數要換成 {encoded_password}
    connection_str = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

    engine = create_engine(connection_str)

    # 測試連線
    with engine.connect() as conn:
        print("✅ MySQL 連線成功！")
except Exception as e:
    print(f"❌ MySQL 連線失敗！\n錯誤訊息: {e}")
    exit()

# ==========================================
# 2. 讀取你的完美 CSV 檔案
# ==========================================
csv_filename = "Restaurant_Final.csv"

if not os.path.exists(csv_filename):
    print(f"❌ 找不到檔案：{csv_filename}")
    print("請確認這個 CSV 檔是否跟 seed_data.py 在同一個資料夾內！")
    exit()

print("⏳ 正在讀取 CSV 檔案...")
try:
    # 讀取 CSV
    df = pd.read_csv(csv_filename, encoding="utf-8-sig")
except:
    # 萬一編碼有問題備用
    df = pd.read_csv(csv_filename, encoding="utf-8")

# ==========================================
# 3. 資料清理與寫入
# ==========================================
# 確保沒有重複的 ID
df = df.drop_duplicates(subset=["RestaurantID"])

# 定義要寫入的 Table 名稱 (通常叫 restaurants)
table_name = "restaurants"

print(f"🔄 正在將 {len(df)} 筆餐廳資料灌入 MySQL 資料庫 ({DB_NAME})...")

try:
    # if_exists='replace': 如果資料表已經存在，就刪掉重建 (保證資料最新)
    # index=False: 不要把 pandas 的索引數字寫進去
    df.to_sql(name=table_name, con=engine, if_exists="replace", index=False)

    print("-" * 30)
    print(f"🎉 大功告成！資料已全部匯入！")
    print(f"請打開 MySQL Workbench，查詢 `{table_name}` 資料表看看成果吧！")
    print("-" * 30)

except Exception as e:
    print(f"❌ 寫入失敗：{e}")
