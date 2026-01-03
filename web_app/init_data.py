import pandas as pd
import json
import os
import random
import shutil

# ================= 設定區 =================
BASE_DIR = os.path.abspath('.')
INPUT_CSV_PATH = os.path.join(BASE_DIR, 'Restaurant_Final_Polished.csv')
HOME_DIR = os.path.expanduser('~')
LOCAL_IMAGE_SOURCE_DIR = os.path.join(HOME_DIR, 'Desktop', 'Taipei2025', 'My_Data_Backup', 'image')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_json')
PROJECT_STATIC_IMAGE_DIR = os.path.join(BASE_DIR, 'static', 'image')
BASE_IMAGE_URL_PREFIX = '/static/image'

# ================= 標籤對照表 =================
TAG_MAPPING = {
    "中式料理": "chinese", "台式料理": "chinese", "日式料理": "japanese",
    "美式料理": "american", "義式料理": "italian", "法式料理": "french",
    "韓式料理": "korean", "泰式料理": "thai", "越式料理": "vietnamese",
    "印度料理": "indian", "西班牙料理": "spanish", "火鍋": "hotpot",
    "燒烤": "bbq_grill", "燒肉": "bbq_grill", "甜點下午茶": "afternoon_tea",
    "甜點": "afternoon_tea", "咖啡": "afternoon_tea", "早午餐": "brunch",
    "海鮮料理": "seafood", "素食": "vegetarian", "餐酒館": "bistro_bar",
    "在地小吃": "local_snacks", "景觀餐廳": "scenic_view", "親子友善": "family_friendly",
    "寵物友善": "pet_friendly", "浪漫約會": "romantic_date", "老店傳承": "historic_shop",
    "網美打卡": "instagrammable", "伴手禮": "souvenir_gift"
}

def generate_tags_fallback(row):
    name = str(row.get('RestaurantName', '')) 
    desc = str(row.get('Description', ''))
    text = name + " " + name + " " + desc
    tags = []
    if any(kw in text for kw in ["中式", "台式", "熱炒"]): tags.append("中式料理")
    if any(kw in text for kw in ["日式", "壽司", "拉麵"]): tags.append("日式料理")
    if not tags: tags.append("其他美食")
    return tags

def run_generation():
    print("🚀 開始生成資料...")
    
    if not os.path.exists(INPUT_CSV_PATH):
        print(f"❌ 錯誤：找不到 {INPUT_CSV_PATH}")
        return

    try:
        df = pd.read_csv(INPUT_CSV_PATH, dtype=str, keep_default_na=False)
        print(f"📄 成功讀取 {len(df)} 筆餐廳資料")
    except Exception as e:
        print(f"❌ CSV 讀取失敗: {e}")
        return

    main_data = []
    gallery_data = []

    for _, row in df.iterrows():
        name = str(row.get('RestaurantName', 'Unknown')).strip()
        description = str(row.get('Description', ''))
        address = str(row.get('PostalAddress', ''))
        phone = str(row.get('Telephones', ''))
        
        # 🔥【新增】讀取縣市與鄉鎮區
        city = str(row.get('LocatedCity', '')).strip()  # 例如：台北市
        town = str(row.get('Town', '')).strip()         # 例如：大安區
        
        # 標籤處理
        csv_tags = str(row.get('CategoryTags', '')).strip()
        tags = [t.strip() for t in csv_tags.split(',')] if csv_tags else generate_tags_fallback(row)
        tags_str = ",".join(tags)

        # 封面圖處理
        csv_cover = str(row.get('CoverImage', '')).strip()
        cover_image = ""
        if csv_cover and csv_cover.lower() != 'nan':
             cover_image = '/' + csv_cover if not csv_cover.startswith('/') else csv_cover
        
        # 價格處理
        price_level = str(row.get('PriceLevel', '$')) 
        avg_price = row.get('AvgPrice', '0')

        # 相簿處理
        gallery = []
        found_images = []
        for tag in tags:
            folder_name = TAG_MAPPING.get(tag)
            if folder_name:
                src_path = os.path.join(LOCAL_IMAGE_SOURCE_DIR, folder_name)
                if os.path.isdir(src_path):
                    imgs = [f for f in os.listdir(src_path) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
                    for img in imgs:
                        full_url = f"{BASE_IMAGE_URL_PREFIX}/{folder_name}/{img}"
                        if full_url != cover_image:
                            found_images.append(full_url)
        if found_images:
            gallery = random.sample(list(set(found_images)), min(len(found_images), 3))
        if not cover_image and gallery:
            cover_image = gallery[0]

        main_data.append({
            "Name": name,
            "Description": description,
            "Add": address,
            "Tel": phone,
            "CoverImage": cover_image,
            "TagsStr": tags_str,
            "PriceLevel": price_level,
            "AvgPrice": avg_price,
            # 🔥【新增】存入 JSON 的新欄位
            "City": city,
            "Town": town
        })
        
        gallery_data.append({
            "restaurant_id": name,
            "GalleryImages": gallery
        })

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    with open(os.path.join(OUTPUT_DIR, 'restaurants_main.json'), 'w', encoding='utf-8') as f:
        json.dump(main_data, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, 'restaurants_gallery.json'), 'w', encoding='utf-8') as f:
        json.dump(gallery_data, f, ensure_ascii=False, indent=2)
        
    print(f"✅ JSON 資料更新完成 (已包含 LocatedCity 與 Town)！")

    # 簡單檢查圖片資料夾
    if not os.path.exists(PROJECT_STATIC_IMAGE_DIR):
        print(f"🚚 目標資料夾不存在，開始複製圖片...")
        try:
            static_parent = os.path.dirname(PROJECT_STATIC_IMAGE_DIR)
            if not os.path.exists(static_parent): os.makedirs(static_parent)
            shutil.copytree(LOCAL_IMAGE_SOURCE_DIR, PROJECT_STATIC_IMAGE_DIR, dirs_exist_ok=True)
            print("✅ 圖片搬運成功！")
        except Exception as e:
            print(f"❌ 搬運失敗: {e}")
    else:
        print("✅ 圖片資料夾已存在，跳過重複搬運")

if __name__ == "__main__":
    run_generation()