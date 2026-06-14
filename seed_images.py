import pandas as pd
import os
import re
from web_app.mysql_connection import get_db_cursor

def refresh_restaurant_images(csv_path, photos_dir):
    # 1. 讀取 CSV 建立 餐廳名稱 -> ID 的對照表
    df = pd.read_csv(csv_path)
    name_to_id_map = dict(zip(df["Name"], df["ID"]))

    # 2. 掃描 ./Food 資料夾下的圖片並分類
    print(f"正在掃描資料夾: {photos_dir}")
    if not os.path.exists(photos_dir):
        print(f"錯誤：找不到資料夾 {photos_dir}")
        return

    all_files = [f for f in os.listdir(photos_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    # 結構: { "餐廳名稱": ["01.jpg", "02.jpg", ...] }
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
    insert_data = []
    for rest_name, photos in restaurant_photos_groups.items():
        rest_id = name_to_id_map.get(rest_name)
        if not rest_id:
            continue
            
        # 挑選前三張圖片
        # selected_photos = sorted(photos)[:3]
        # 全部食物圖片都存入資料庫
        for photo_file in photos:
            image_url = f"/restaurant_photos/{rest_name}/{photo_file}"
            insert_data.append((rest_id, image_url))

    # 4. 資料庫操作：清空並重新寫入
    if not insert_data:
        print("未發現匹配的圖片，取消操作。")
        return

    try:
        # 使用 commit=True 確保變更生效
        with get_db_cursor(commit=True) as cursor:
            # A. 確保資料表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS restaurant_images (
                    image_id INT AUTO_INCREMENT PRIMARY KEY,
                    restaurant_id VARCHAR(50),
                    image_url VARCHAR(255),
                    FOREIGN KEY (restaurant_id) REFERENCES restaurants(ID) ON DELETE CASCADE
                )
            """)

            # B. 重要：清空現有的所有圖片資料 (每次重新寫入的前提)
            print("正在清空舊有的圖片資料...")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;") # 暫時關閉外鍵檢查以便清空
            cursor.execute("TRUNCATE TABLE restaurant_images;")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

            # C. 批次寫入新資料
            sql = "INSERT INTO restaurant_images (restaurant_id, image_url) VALUES (%s, %s)"
            cursor.executemany(sql, insert_data)
            
            print(f"成功！已清空舊資料並重新寫入 {cursor.rowcount} 筆新圖片記錄。")
            
    except Exception as e:
        print(f"資料庫更新失敗: {e}")

if __name__ == "__main__":
    refresh_restaurant_images('Restaurants.csv', './Food')