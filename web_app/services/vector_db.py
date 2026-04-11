import os
import pandas as pd
import chromadb
from chromadb.utils.embedding_functions import OpenCLIPEmbeddingFunction
from chromadb.utils.data_loaders import ImageLoader
from tqdm import tqdm
import shutil
import uuid
from pathlib import Path

class PhotoSearchService:
    def __init__(self, db_path: str, collection_name: str):
        # 初始化持久化客戶端
        self.client = chromadb.PersistentClient(path=db_path)
        self.embedding_function = OpenCLIPEmbeddingFunction()
        self.image_loader = ImageLoader()
        
        # 取得或建立 Collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            data_loader=self.image_loader
        )

    def rebuild_index(self, csv_path: str, photos_dir: str):
        """
        從 CSV 檔與圖片資料夾重新建立索引
        - csv_path: Restaurants_1.csv 的路徑
        - photos_dir: restaurant_photos_1 資料夾路徑
        """
        # 1. 讀取 CSV 建立 餐廳名稱 -> 縣市 的對照表
        print(f"正在讀取資料表: {csv_path}")
        df = pd.read_csv(csv_path)
        # 建立字典加速查詢
        city_map = dict(zip(df["Name"], df["City"]))

        # 2. 掃描資料夾
        image_uris = []
        metadatas = []
        ids = []

        print(f"正在掃描圖片資料夾: {photos_dir}")
        # 取得所有子資料夾 (餐廳名稱)
        restaurant_folders = [d for d in os.listdir(photos_dir) if os.path.isdir(os.path.join(photos_dir, d))]

        for rest_name in restaurant_folders:
            city = city_map.get(rest_name, "未知") # 從 CSV 比對縣市
            rest_path = os.path.join(photos_dir, rest_name)
            
            for img_name in os.listdir(rest_path):
                if img_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    full_path = os.path.abspath(os.path.join(rest_path, img_name))
                    
                    image_uris.append(full_path)
                    metadatas.append({
                        "restaurant_name": rest_name,
                        "city": city,
                        "file_name": img_name
                    })
                    ids.append(f"{rest_name}_{img_name}")

        # 3. 執行批次匯入 (分段處理避免記憶體壓力)
        batch_size = 50
        print(f"開始匯入 {len(ids)} 筆資料至 ChromaDB...")
        
        # 如果要重建，可以先刪除舊資料 (選用)
        # self.client.delete_collection(self.collection.name)
        # self.collection = self.client.get_or_create_collection(...)

        for i in tqdm(range(0, len(ids), batch_size)):
            end = i + batch_size
            self.collection.add(
                ids=ids[i:end],
                uris=image_uris[i:end],
                metadatas=metadatas[i:end]
            )
        
        print("索引重建完成！")

    def search_similar_restaurants(self, image_path: str, city: str, n_results: int = 5):
        """執行向量搜尋"""
        query_params = {
            "query_uris": [os.path.abspath(image_path)],
            "n_results": n_results,
            "include": ["metadatas", "distances", "uris"]
        }
        
        if city and city not in ["全部", "null", "undefined"]:
            query_params["where"] = {"city": city}

        results = self.collection.query(**query_params)
        return self._format_results(results)
    
    def _format_results(self, results):
        """格式化回傳結果"""
        formatted = []
        if not results["ids"] or len(results["ids"][0]) == 0:
            return formatted

        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            dist = results["distances"][0][i]
            abs_path = results["uris"][0][i]
            
            # 假設 static/restaurant_photos_1 是你的靜態路徑
            relative_url = abs_path.split("static")[-1].replace("\\", "/")
            web_url = f"/static{relative_url}"

            formatted.append({
                "restaurant_name": meta["restaurant_name"],
                "city": meta["city"],
                "similarity": round(max(0, 100 - (dist * 100)), 2),
                "distance": round(dist, 4),
                "image_url": web_url
            })
        return formatted
    

class RestaurantSearchService:
    def __init__(self):
        # 動態取得路徑
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.temp_dir = os.path.join(self.base_dir, "static", "temp_uploads")
        self.db_path = os.path.join(self.base_dir, "web_app", "dine_vector_db")
        
        # 確保暫存資料夾存在
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 初始化向量資料庫服務
        self.vector_service = PhotoSearchService(
            db_path=str(self.db_path),
            collection_name="restaurant_images"
        )

    # 處理圖片上傳並執行搜尋
    async def search_by_image(self, file, city: str):
        # 產生唯一檔名並定義路徑
        file_extension = os.path.splitext(file.filename)[1]
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_path = Path(self.temp_dir) / temp_filename

        try:
            # 建立暫存檔案路徑並儲存上傳的圖片
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 呼叫向量搜尋邏輯 (傳入絕對路徑字串)
            results = self.vector_service.search_similar_restaurants(
                image_path=str(temp_path.absolute()),
                city=city
            )
            return results
        finally:
            # 搜尋完畢後清理暫存檔案
            if temp_path.exists():
                os.remove(temp_path)