import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.types import NVARCHAR, Float, Integer, String
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from typing import Dict, Any

# 1. 載入環境變數
load_dotenv()

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD","")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

# 檢查變數
if not all([db_user, db_password, db_host, db_port, db_name]):
    print("❌ 錯誤：.env 環境變數設定不完整。")
    exit()

encoded_password = quote_plus(db_password)

# ==========================================
# 步驟 0: 自動建立資料庫 (解決 1049 錯誤)
# ==========================================
print(f"🔨 正在檢查資料庫 `{db_name}` 是否存在...")

try:
    # 先連線到 MySQL 系統預設資料庫 (不指定 db_name)
    # 這樣才能執行 CREATE DATABASE 指令
    root_connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/mysql?charset=utf8mb4"
    root_engine = create_engine(root_connection_str)
    
    with root_engine.connect() as conn:
        # 自動建立資料庫 (如果不存在的話)
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name};"))
        print(f"✅ 資料庫 `{db_name}` 準備就緒！")
        
except Exception as e:
    print(f"❌ 無法建立資料庫！錯誤訊息: {e}")
    exit()

# 步驟 1: 正式連線到目標資料庫
try:
    connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    engine = create_engine(connection_str)
    
    with engine.connect() as conn:
        print(f"✅ 成功連線到 `{db_name}`！")

except Exception as e:
    print(f"❌ 連線失敗: {e}")
    exit()

# 步驟 2: 讀取 CSV
# 設定路徑 (請確認這裡是正確的)
base_path = os.path.dirname(os.path.abspath(__file__))
csv_filename = os.path.join(base_path, "Restaurant_Final_Final.csv")


if not os.path.exists(csv_filename):
    print(f"❌ 錯誤：找不到 CSV 檔案：{csv_filename}")
    exit()

print(f"⏳ 正在讀取 CSV 檔案...")
try:
    df = pd.read_csv(csv_filename, encoding="utf-8-sig")
except:
    df = pd.read_csv(csv_filename, encoding="utf-8")

# 去除重複 ID
if "ID" in df.columns:
    df = df.drop_duplicates(subset=["ID"])

print(f"📊 準備匯入 {len(df)} 筆資料...")

# 步驟 3: 定義欄位並寫入
dtype_mapping = {
    'ID': String(50),
    'Name': NVARCHAR(100),
    'Description': NVARCHAR(2000),
    'Add': NVARCHAR(255),
    'Tel': String(50),
    'CoverImage': String(255),
    'TagsStr': NVARCHAR(255),
    'PriceLevel': String(10),
    'AvgPrice': Integer(),
    'City': NVARCHAR(50),
    'Town': NVARCHAR(50),
    'ServiceTime': NVARCHAR(255),
    'Parking': NVARCHAR(500),
    'Payment': String(100),
    'Website': String(500),
    'GoogleMap': String(500),
    'Px': Float(),
    'Py': Float()
}

table_name = "restaurants"

try:
    print(f"🔄 正在寫入資料表 `{table_name}`...")
    
    df.to_sql(
        name=table_name,
        con=engine,
        if_exists="replace",
        index=False,
        dtype=dtype_mapping 
    )
    
    # 設定 Primary Key
    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD PRIMARY KEY (ID);"))
        conn.commit()
    
    print("=" * 40)
    print(f"🎉 成功！所有資料已匯入資料庫 `{db_name}`！")
    print("=" * 40)

except Exception as e:
    print(f"❌ 寫入失敗：{e}")