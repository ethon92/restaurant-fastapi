import pandas as pd
from sqlalchemy import create_engine
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv


# 0. 載入環境變數
load_dotenv()

# 1. 設定 MySQL 連線資訊
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

if not all([db_user, db_password, db_host, db_port, db_name]):
    print("❌ 錯誤：無法讀取資料庫設定，請檢查 .env 檔案。")
    exit()

try:
    encoded_password = quote_plus(db_password)
    connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    engine = create_engine(connection_str)
    
    with engine.connect() as conn:
        print(f"✅ MySQL 連線成功！")
except Exception as e:
    print(f"❌ MySQL 連線失敗！\n錯誤訊息: {e}")
    exit()

# 2. 讀取 CSV 並刪除欄位
csv_filename = "Restaurant_Final_Polished.csv" # 確保你已經改好檔名了

if not os.path.exists(csv_filename):
    print(f"❌ 找不到檔案：{csv_filename}")
    exit()

print("⏳ 正在讀取 CSV 檔案...")
try:
    df = pd.read_csv(csv_filename, encoding="utf-8-sig")
except:
    df = pd.read_csv(csv_filename, encoding="utf-8")

# 關鍵修改：在這裡刪除不需要的欄位 ：定義你想刪除的欄位列表
cols_to_drop = ['Images', 'TrafficInfo']

# 使用 drop 指令，errors='ignore' 表示如果欄位本來就不存在也不會報錯
df = df.drop(columns=cols_to_drop, errors='ignore')

print(f"🗑️ 已嘗試刪除欄位: {cols_to_drop}")

# 3. 寫入資料庫
if "RestaurantID" in df.columns:
    df = df.drop_duplicates(subset=["RestaurantID"])

table_name = "restaurants"
print(f"🔄 正在將 {len(df)} 筆資料匯入 MySQL...")

try:
    # if_exists='replace' 會自動幫你重建表格 (所以舊的欄位會消失)
    df.to_sql(name=table_name, con=engine, if_exists="replace", index=False)
    
    print("-" * 30)
    print(f"🎉 大功告成！資料表 `{table_name}` 已更新。")
    print(f"Images 和 TrafficInfo 欄位已成功移除！")
    print("-" * 30)

except Exception as e:
    print(f"❌ 寫入失敗：{e}")