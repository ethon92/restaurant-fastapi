import os
import random
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

category_mapping = {
    '中式料理': ['chinese'],
    '日式料理': ['japanese'],
    '美式料理': ['american'],
    '義式料理': ['italian'],
    '法式料理': ['french'],
    '西班牙料理': ['spanish'],
    '餐酒館': ['bistro_bar'],
    '韓式料理': ['korean'],
    '泰式料理': ['thai'],
    '越式料理': ['vietnamese'],
    '印度料理': ['indian'],
    '素食': ['vegetarian'],
    '火鍋': ['hotpot'],
    '燒烤': ['bbq_grill'],
    '在地小吃': ['local_snacks'],
    '甜點下午茶': ['afternoon_tea'],
    '海鮮料理': ['seafood'],
    '早午餐': ['brunch'],
    '景觀餐廳': ['scenic_view'],
    '親子友善': ['family_friendly'],
    '浪漫約會': ['romantic_date'],
    '團體聚餐': ['family_friendly'],
    '寵物友善': ['pet_friendly'],
    '養生健康': ['vegetarian'],
    '網美打卡': ['instagrammable'],
    '老店傳承': ['local_snacks'],
    '人氣名店': ['instagrammable'],
    '伴手禮': ['local_snacks'],
    '其他美食': ['instagrammable', 'local_snacks', 'chinese']
}

IMAGE_BASE_PATH = "static/image"
LOCAL_IMAGE_DIR = "./static/image"

# --- 資料庫設定區塊+處理密碼特殊字元 ---
db_user = os.getenv("DB_USER", "root")
db_password = os.getenv("DB_PASSWORD", "")
db_host = os.getenv("DB_HOST", "localhost") 
db_port = os.getenv("DB_PORT", "3306")
db_name = os.getenv("DB_NAME", "restaurant_food") 

encoded_password = quote_plus(db_password)

connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
engine = create_engine(connection_str)

def seed_restaurant_images():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS restaurant_images (
                image_id INT AUTO_INCREMENT PRIMARY KEY,
                restaurant_id VARCHAR(50),
                image_url VARCHAR(255),
                FOREIGN KEY (restaurant_id) REFERENCES restaurants(ID) ON DELETE CASCADE
            );
        """))
        
        # 清空舊資料
        conn.execute(text("TRUNCATE TABLE restaurant_images;"))

        # 2. 抓取所有餐廳與其 Tags
        restaurants = conn.execute(text("SELECT ID, TagsStr FROM restaurants")).fetchall()
        
        image_records = []
        
        for res in restaurants:
            res_id = res[0]
            tags_str = res[1] if res[1] else ""
            
            tags = [t.strip() for t in tags_str.replace("、", ",").split(",") if t.strip()]
            
            possible_images = []
            
            for tag in tags:
                folders = category_mapping.get(tag, [])
                
                for folder_name in folders:
                    tag_folder = os.path.join(LOCAL_IMAGE_DIR, folder_name)
                    if os.path.exists(tag_folder):
                        files = [f for f in os.listdir(tag_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                        for f in files:
                            # 儲存路徑
                            possible_images.append(f"/{IMAGE_BASE_PATH}/{folder_name}/{f}")
                    else:
                        print(f" 找不到目錄: {tag_folder} (標籤: {tag})")
            # 隨機挑 3 張
            if possible_images:
                selected_images = random.sample(possible_images, min(len(possible_images), 3))
                for img_url in selected_images:
                    image_records.append({"res_id": res_id, "url": img_url})
                    
        if image_records:
            insert_sql = text("INSERT INTO restaurant_images (restaurant_id, image_url) VALUES (:res_id, :url)")
            conn.execute(insert_sql, image_records)
            conn.commit()
            print(f" 成功！總共為餐廳分配了 {len(image_records)} 張圖片。")
        else:
            print(" 失敗：沒有找到任何符合標籤的圖片，請檢查 static/image 資料夾結構。")

if __name__ == "__main__":
    seed_restaurant_images()