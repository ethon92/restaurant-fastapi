from fastapi import APIRouter
from web_app.models.feature import FavoriteRestaurant
from web_app.mysql_connection import get_db_cursor

router = APIRouter()

@router.post('/favorite')
def add_favorite(favorite: FavoriteRestaurant):
    try:
        # 提交資料要commit=True
        with get_db_cursor(commit=True) as cursor:
            sql = "insert into favorite(user_id, restaurant_id, fav_note) values(%s, %s, %s)"
            
            cursor.execute(sql, (favorite.user_id, favorite.restaurant_id, favorite.fav_note))
            
            cursor.execute("select * from favorite")
            
            new_data = cursor.fetchall()
            
            return {
                "success": True,
                "data": new_data
            }
    except Exception as e:
        print("error", e)
    
    
    
        