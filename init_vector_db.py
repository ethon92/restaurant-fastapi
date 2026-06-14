from web_app.services.vector_db import PhotoSearchService
import os

service = PhotoSearchService(
    db_path="./web_app/dine_vector_db", 
    collection_name="restaurant_images"
)

# 執行重建
service.rebuild_index(
    csv_path="./Restaurants.csv", 
    photos_dir="./static/restaurant_photos"
)