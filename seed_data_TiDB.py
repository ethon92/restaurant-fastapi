import pandas as pd
import os
import sys
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.types import NVARCHAR, Float, Integer, String

# 1. 環境變數與路徑設定
load_dotenv()

base_path = os.path.dirname(os.path.abspath(__file__))
csv_filename = os.path.join(base_path, "Restaurants.csv")

# TiDB Cloud 連線資訊
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "4000") # TiDB 預設埠號為 4000
db_name = os.getenv("DB_NAME")
# 新增：CA 憑證路徑 (TiDB Cloud 必備)
ca_path = os.getenv("TIDB_CA_PATH", os.path.join(base_path, "isrgrootx1.pem"))

if not all([db_user, db_password, db_host, db_name]):
    print("❌ 錯誤：環境變數不完整。")
    sys.exit(1)

# encoded_password = quote_plus(db_password)

# 2. 建立支援 SSL 的 SQLAlchemy Engine
def create_tidb_engine(database):
    # TiDB Cloud 通常需要 ssl 設定
    connect_args = {
        "ssl": {
            "ca": ca_path
        }
    }
    # 組合連線字串
    connection_str = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    return create_engine(connection_str, connect_args=connect_args)

# 3. 自動建立資料庫 (如果不存在)
print(f"🔨 正在檢查 TiDB 資料庫 `{db_name}`...")
try:
    engine = create_tidb_engine(db_name)
    # 測試連線
    with engine.connect() as conn:
        print(f"✅ 成功連線到預先建立的資料庫 `{db_name}`！")
except Exception as e:
    print(f"❌ 連線失敗。請確認已在 TiDB Cloud 控制台手動建立資料庫 `{db_name}`。")
    print(f"錯誤詳情: {e}")
    sys.exit(1)

# 4. 建立目標資料庫連線
engine = create_tidb_engine(db_name)

# 5. 讀取與清洗 CSV (保留您原本的邏輯)
# ... [此處省略您原本的 remove_emojis 與清洗邏輯，保持不變] ...
if not os.path.exists(csv_filename):
    print(f"❌ 錯誤：找不到 CSV 檔案：{csv_filename}")
    sys.exit(1)

print("⏳ 正在讀取 CSV 檔案...")
try:
    df = pd.read_csv(csv_filename, encoding="utf-8-sig")
except UnicodeDecodeError:
    print("⚠️ utf-8-sig 讀取失敗，嘗試使用 utf-8...")
    df = pd.read_csv(csv_filename, encoding="utf-8")

# --- 清洗 A：去除重複 ID (解決 Primary Key 錯誤) ---
if "ID" in df.columns:
    original_count = len(df)
    df = df.drop_duplicates(subset=["ID"], keep='first')
    dropped_count = original_count - len(df)
    if dropped_count > 0:
        print(f"✂️ 已移除 {dropped_count} 筆重複 ID 的資料。")
else:
    print("⚠️ 警告：CSV 中找不到 'ID' 欄位。")

# --- 清洗 B：移除 Emoji 與 4-byte 特殊符號 (解決 1366 錯誤) ---
print("🧹 正在清理 Emoji 與特殊字元...")

def remove_emojis(text):
    """移除所有非 BMP (Basic Multilingual Plane) 的字元，即 4 bytes 字元"""
    if not isinstance(text, str):
        return text
    # 只保留 Unicode 編碼在 \uFFFF 以下的字元
    return "".join(c for c in text if c <= '\uFFFF')

# 針對所有可能包含文字的欄位進行清洗
text_columns = ['Name', 'Description', 'Add', 'TagsStr', 'City', 'Town', 'ServiceTime', 'Parking']
for col in text_columns:
    if col in df.columns:
        df[col] = df[col].apply(remove_emojis)

print(f"📊 準備匯入 {len(df)} 筆清洗後的資料...")

# 6. 定義型別與寫入 TiDB
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
    print(f"🔄 正在將資料串流至 TiDB Cloud `{table_name}`...")
    
    # 寫入資料 (TiDB 支援標準 MySQL 語法)
    df.to_sql(
        name=table_name,
        con=engine,
        if_exists="replace",
        index=False,
        dtype=dtype_mapping,
        chunksize=500 # 分批寫入以避免雲端連線逾時
    )
    
    # 設定 Primary Key
    print("🔑 正在設定主鍵 (Primary Key)...")
    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD PRIMARY KEY (ID);"))
        conn.commit()
    
    print(f"🎉 成功匯入 {len(df)} 筆資料到 TiDB Cloud！")

except Exception as e:
    print(f"❌ 寫入過程發生錯誤：\n{e}")