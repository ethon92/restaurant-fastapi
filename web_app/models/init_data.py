import pandas as pd
import json
import os
import random
import shutil

#  設定區 
BASE_DIR = os.path.abspath('.')
INPUT_CSV_PATH = os.path.join(BASE_DIR, 'Restaurant_Final_Polished.csv')
HOME_DIR = os.path.expanduser('~')
LOCAL_IMAGE_SOURCE_DIR = os.path.join(HOME_DIR, 'Desktop', 'Taipei2025', 'My_Data_Backup', 'image')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_json')
PROJECT_STATIC_IMAGE_DIR = os.path.join(BASE_DIR, 'static', 'image')
BASE_IMAGE_URL_PREFIX = '/static/image'

#  標籤對照表 
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
    text = (name + " " + desc).lower()
    tags = []

    # 建立關鍵字與標籤的對照表
    rules = {
        "中式料理": ["中式", "粵菜", "川菜", "上海菜", "點心"],
        "台式料理": ["台式", "台菜", "熱炒", "滷肉飯", "牛肉麵"],
        "日式料理": ["日式", "壽司", "拉麵", "刺身", "居酒屋", "丼飯", "定食"],
        "美式料理": ["美式", "漢堡", "熱狗", "炸雞", "牛排館"],
        "義式料理": ["義式", "義大利麵", "披薩", "pizza", "燉飯"],
        "法式料理": ["法式", "法餐", "舒芙蕾"],
        "韓式料理": ["韓式", "泡菜", "石鍋拌飯", "韓菜", "年糕"],
        "泰式料理": ["泰式", "泰國菜", "打拋", "冬蔭功"],
        "越式料理": ["越式", "越南", "河粉"],
        "印度料理": ["印度", "咖哩", "烤餅"],
        "西班牙料理": ["西班牙", "烤飯", "tapas"],
        "火鍋": ["火鍋", "麻辣鍋", "涮涮鍋", "鍋物"],
        "燒烤": ["燒烤", "燒肉", "bbq", "烤肉", "串燒"],
        "甜點下午茶": ["甜點", "下午茶", "蛋糕", "鬆餅", "烘焙", "巧克力"],
        "咖啡": ["咖啡", "cafe", "coffee"],
        "早午餐": ["早午餐", "brunch", "蛋餅", "三明治"],
        "海鮮料理": ["海鮮", "龍蝦", "螃蟹", "魚料理"],
        "素食": ["素食", "蔬食", "全素", "奶蛋素"],
        "餐酒館": ["餐酒館", "bistro", "調酒", "酒吧", "酒吧"],
        "在地小吃": ["小吃", "老店", "攤位", "肉圓", "蚵仔煎"],
        "景觀餐廳": ["景觀", "夜景", "看海", "看山"],
        "親子友善": ["親子", "兒童", "遊戲室", "小孩"],
        "寵物友善": ["寵物", "狗狗", "貓咪", "毛孩"],
        "浪漫約會": ["浪漫", "約會", "情人"],
        "老店傳承": ["老店", "傳承", "創始", "百年"],
        "網美打卡": ["網美", "拍照", "打卡", "熱門"],
        "伴手禮": ["伴手禮", "禮盒", "名產"]
    }

    # 根據關鍵字自動掃描
    for tag, keywords in rules.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)

    # 如果還是沒標籤，就給預設
    if not tags:
        tags.append("其他美食")
        
    return tags

def run_generation():
    print(" 開始生成資料...")
    
    if not os.path.exists(INPUT_CSV_PATH):
        print(f"❌ 錯誤：找不到 {INPUT_CSV_PATH}")
        return

    try:
        df = pd.read_csv(INPUT_CSV_PATH, dtype=str, keep_default_na=False)
        print(f" 成功讀取 {len(df)} 筆餐廳資料")
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
        # 讀取縣市與鄉鎮區
        city = str(row.get('LocatedCity', '')).strip()  
        town = str(row.get('Town', '')).strip()         
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