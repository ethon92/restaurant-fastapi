import pandas as pd
import os
import sys
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
# 關鍵修正：明確引入型別，消除 VS Code 紅線
from sqlalchemy.types import NVARCHAR, Float, Integer, String

# ==========================================
# 1. 環境變數與路徑設定
# ==========================================
load_dotenv()

# 取得目前檔案所在的資料夾路徑，確保讀取 CSV 不會找不到
base_path = os.path.dirname(os.path.abspath(__file__))
csv_filename = os.path.join(base_path, "Restaurant_Final_Final.csv")

# 資料庫設定
db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "3306")
db_name = os.getenv("DB_NAME", "restaurant_db")

# 檢查變數是否完整
if not all([db_user, db_host, db_port, db_name]):
    print("❌ 錯誤：.env 環境變數設定不完整，請檢查。")
    sys.exit(1)

# 處理密碼特殊字元 (如 @, #)
encoded_password = quote_plus(db_password)

# ==========================================
# 2. 自動建立資料庫 (如果不存在)
# ==========================================
print(f"🔨 正在檢查資料庫 `{db_name}`...")

try:
    # 先連線到 MySQL 系統層 (不指定 db)
    root_conn_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/mysql?charset=utf8mb4"
    root_engine = create_engine(root_conn_str)
    
    with root_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name};"))
        print(f"✅ 資料庫 `{db_name}` 準備就緒！")
except Exception as e:
    print(f"❌ 無法建立資料庫，請確認帳號權限或連線設定。\n錯誤: {e}")
    sys.exit(1)

# ==========================================
# 3. 建立目標資料庫連線
# ==========================================
try:
    # 指定連線到 db_name，並強制使用 utf8mb4
    connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    engine = create_engine(connection_str)
    print(f"✅ 成功連線到 `{db_name}`！")
except Exception as e:
    print(f"❌ 連線失敗: {e}")
    sys.exit(1)

# ==========================================
# 4. 讀取 CSV 與資料清洗 (關鍵步驟！)
# ==========================================
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

# ==========================================
# 5. 定義型別與寫入資料庫
# ==========================================

# 定義 SQLAlchemy 型別 (這樣寫 VS Code 就不會報紅線)
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
    print(f"🔄 正在寫入資料表 `{table_name}` (這可能需要幾秒鐘)...")
    
    # 寫入資料庫
    df.to_sql(
        name=table_name,
        con=engine,
        if_exists="replace",  # 刪除舊表重建
        index=False,          # 不寫入 Pandas 的 Index
        dtype=dtype_mapping   # type: ignore (加上這個保險起見，雖然上面引用已修正)
    )
    
    # --- 最後一步：設定 Primary Key ---
    # 因為 to_sql 不會自動設 ID 為主鍵，需手動執行 SQL
    print("🔑 正在設定主鍵 (Primary Key)...")
    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD PRIMARY KEY (ID);"))
        conn.commit()
    
    print("=" * 50)
    print(f"🎉 大功告成！成功匯入 {len(df)} 筆資料到 `{db_name}` 資料庫！")
    print("=" * 50)

except Exception as e:
    print(f"❌ 寫入過程發生錯誤：\n{e}")