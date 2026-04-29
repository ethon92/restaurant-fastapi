import pandas as pd
import os
import re
import sys
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 1. 環境變數與路徑設定
load_dotenv()

base_path = os.path.dirname(os.path.abspath(__file__))
# CA 憑證路徑 (TiDB Cloud 必備)
ca_path = os.getenv("TIDB_CA_PATH", os.path.join(base_path, "isrgrootx1.pem"))

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "4000")
db_name = os.getenv("DB_NAME")

if not all([db_user, db_password, db_host, db_name]):
    print("❌ 錯誤：環境變數不完整。")
    sys.exit(1)

# 2. 建立支援 SSL 的 SQLAlchemy Engine
def create_tidb_engine():
    connect_args = {
        "ssl": {
            "ca": ca_path
        }
    }
    # 使用 mysql+pymysql 驅動連線至 TiDB
    connection_str = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    return create_engine(connection_str, connect_args=connect_args)

def refresh_restaurant_images_tidb(csv_path, photos_dir):
    # 1. 讀取 CSV 建立 餐廳名稱 -> ID 的對照表
    if not os.path.exists(csv_path):
        print(f"❌ 錯誤：找不到 CSV 檔案：{csv_path}")
        return
        
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    name_to_id_map = dict(zip(df["Name"], df["ID"]))

    # 2. 掃描圖片並分類
    if not os.path.exists(photos_dir):
        print(f"錯誤：找不到資料夾 {photos_dir}")
        return

    all_files = [f for f in os.listdir(photos_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    restaurant_photos_groups = {}
    for filename in all_files:
        match = re.match(r"(.+)_(\d+)\.(jpg|jpeg|png)$", filename)
        if match:
            rest_name = match.group(1).strip()
            photo_num = match.group(2)
            extension = match.group(3)
            
            if rest_name not in restaurant_photos_groups:
                restaurant_photos_groups[rest_name] = []
            restaurant_photos_groups[rest_name].append(f"{photo_num}.{extension}")

    # 3. 準備插入的資料集
    insert_values = []
    for rest_name, photos in restaurant_photos_groups.items():
        rest_id = name_to_id_map.get(rest_name)
        if not rest_id:
            continue
            
        for photo_file in photos:
            image_url = f"/restaurant_photos/{rest_name}/{photo_file}"
            # 準備 SQLAlchemy 批次插入格式
            insert_values.append({"restaurant_id": rest_id, "image_url": image_url})

    if not insert_values:
        print("未發現匹配的圖片，取消操作。")
        return

    # 4. 資料庫操作：使用 SQLAlchemy 寫入 TiDB Cloud
    engine = create_tidb_engine()
    
    try:
        with engine.begin() as conn:  # 使用 begin() 會自動 handle commit
            # A. 確保資料表存在 (TiDB 語法與 MySQL 相容)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS restaurant_images (
                    image_id INT AUTO_INCREMENT PRIMARY KEY,
                    restaurant_id VARCHAR(50),
                    image_url VARCHAR(255),
                    FOREIGN KEY (restaurant_id) REFERENCES restaurants(ID) ON DELETE CASCADE
                )
            """))

            # B. 清空舊資料
            print("正在清空 TiDB 中的舊有圖片資料...")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            conn.execute(text("TRUNCATE TABLE restaurant_images;"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

            # C. 批次寫入新資料
            print(f"正在寫入 {len(insert_values)} 筆新圖片記錄至 TiDB Cloud...")
            insert_sql = text("INSERT INTO restaurant_images (restaurant_id, image_url) VALUES (:restaurant_id, :image_url)")
            conn.execute(insert_sql, insert_values)
            
            print("🎉 TiDB Cloud 圖片資料更新成功！")
            
    except Exception as e:
        print(f"❌ TiDB 寫入失敗: {e}")

if __name__ == "__main__":
    # 確保路徑正確
    csv_path = os.path.join(base_path, 'Restaurants.csv')
    photos_dir = os.path.join(base_path, 'Food')
    refresh_restaurant_images_tidb(csv_path, photos_dir)