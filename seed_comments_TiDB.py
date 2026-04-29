import pandas as pd
import os
import sys
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.types import NVARCHAR, Integer, String, DateTime

# 1. 環境變數與連線設定
load_dotenv()

base_path = os.path.dirname(os.path.abspath(__file__))

# 從 .env 讀取 TiDB Cloud 資訊
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "4000")
db_name = os.getenv("DB_NAME")
# TiDB Cloud 必備的 CA 憑證路徑
ca_path = os.getenv("TIDB_CA_PATH", os.path.join(base_path, "isrgrootx1.pem"))

if not all([db_user, db_password, db_host, db_name]):
    print("❌ 錯誤：環境變數設定不完整。")
    sys.exit(1)

# 2. 建立支援 SSL 的 SQLAlchemy Engine
def create_tidb_engine(database):
    encoded_password = quote_plus(db_password)
    connect_args = {
        "ssl": {
            "ca": ca_path
        }
    }
    # 使用 mysql+pymysql 驅動連線至 TiDB
    connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{database}?charset=utf8mb4"
    return create_engine(connection_str, connect_args=connect_args)

engine = create_tidb_engine(db_name)

# 3. 定義建表 SQL (與 TiDB 相容)
create_table_sql = """
CREATE TABLE IF NOT EXISTS comments (
    comment_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    restaurant_id VARCHAR(50) NOT NULL,             
    comment_content TEXT NOT NULL,   
    rating INT NOT NULL CHECK(rating >= 1 AND rating <= 5),
    sentiment VARCHAR(20),                
    tags JSON,
    comment_time DATETIME DEFAULT CURRENT_TIMESTAMP 
);
"""

# 4. 執行建表
try:
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
    print("✅ TiDB 資料表 `comments` 已就緒。")
except Exception as e:
    print(f"❌ 建表失敗: {e}")
    sys.exit(1)

# 5. 讀取並清洗 CSV
csv_filename = os.path.join(base_path, "restaurant_comments_final.csv")
if not os.path.exists(csv_filename):
    print(f"❌ 找不到 CSV 檔案：{csv_filename}")
    sys.exit(1)

print("⏳ 正在讀取並格式化資料...")
df = pd.read_csv(csv_filename, encoding="utf-8-sig")

# 欄位重新命名以對應資料庫結構
df = df.rename(columns={
    'ID': 'restaurant_id',
    'Comment_Content': 'comment_content',
    'Rating': 'rating',
    'User_ID': 'user_id'
})

# 6. 匯入 TiDB 資料庫
dtype_mapping = {
    'user_id': Integer(),
    'restaurant_id': String(50),
    'comment_content': NVARCHAR(1000),
    'rating': Integer(),
    'comment_time': DateTime()
}

try:
    print(f"🚀 正在匯入 {len(df)} 筆評論到 TiDB Cloud `{db_name}`...")
    df.to_sql(
        name='comments',
        con=engine,
        if_exists='append', # 使用 append 以保留 Auto Increment 功能
        index=False,
        dtype=dtype_mapping,
        chunksize=500       # 分批寫入避免雲端連線逾時
    )
    print("=" * 50)
    print(f"🎉 成功匯入 {len(df)} 筆評論資料到 TiDB Cloud！")
    print("=" * 50)
except Exception as e:
    print(f"❌ 匯入過程發生錯誤：\n{e}")