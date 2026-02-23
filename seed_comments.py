import pandas as pd
import os
import sys
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.types import NVARCHAR, Integer, String, DateTime

# 1. 環境變數與資料庫連線設定
load_dotenv()

db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "3306")
db_name = os.getenv("DB_NAME", "restaurant_db")

encoded_password = quote_plus(db_password)
connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
engine = create_engine(connection_str)

# 2. 定義建表 SQL (依照您的結構)
create_table_sql = """
CREATE TABLE IF NOT EXISTS comments (
    comment_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    restaurant_id VARCHAR(50) NOT NULL,            
    comment_content VARCHAR(1000) NOT NULL,   
    rating INT NOT NULL CHECK(rating >= 1 AND rating <= 5),
    comment_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_restaurant (restaurant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

# 3. 執行建表
try:
    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
    print("✅ 資料表 `comments` 已就緒。")
except Exception as e:
    print(f"❌ 建表失敗: {e}")
    sys.exit(1)

# 4. 讀取並清洗 CSV
csv_filename = "restaurant_comments_final.csv" # 請確保檔案名稱正確
if not os.path.exists(csv_filename):
    print(f"❌ 找不到 CSV 檔案：{csv_filename}")
    sys.exit(1)

print("⏳ 正在讀取並格式化資料...")
df = pd.read_csv(csv_filename, encoding="utf-8-sig")

# 關鍵步驟：將 CSV 的 ID 改名為 restaurant_id 以對應資料庫
df = df.rename(columns={
    'ID': 'restaurant_id',
    'Comment_Content': 'comment_content',
    'Rating': 'rating',
    'User_ID': 'user_id'
})

# 5. 匯入資料庫
# 這裡使用 dtype_mapping 確保寫入時的資料型別精確
dtype_mapping = {
    'user_id': Integer(),
    'restaurant_id': String(50),
    'comment_content': NVARCHAR(1000),
    'rating': Integer(),
    'comment_time': DateTime()
}

try:
    print(f"🚀 正在匯入 {len(df)} 筆評論到資料庫...")
    df.to_sql(
        name='comments',
        con=engine,
        if_exists='append', # 使用 append 因為我們已經手動建立好 Auto Increment 的表
        index=False,
        dtype=dtype_mapping
    )
    print("=" * 50)
    print(f"🎉 匯入完成！成功將評論資料存入 `{db_name}.comments` 表。")
    print("=" * 50)
except Exception as e:
    print(f"❌ 匯入過程發生錯誤：\n{e}")
