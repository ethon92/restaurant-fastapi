from web_app.mysql_connection import get_db_cursor
from typing import List, Dict, Any
from web_app.models.feature import FavoriteRestaurant, UpdateFavorite


class FavoriteService:
    def __init__(self):
        self.table_name = "favorite"

    # 新增收藏餐廳
    def add_favorite(self, favorite: FavoriteRestaurant) -> bool:
        sql = f"INSERT INTO {self.table_name} (user_id, restaurant_id, fav_note) VALUES (%s, %s, %s)"
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    sql, (favorite.user_id, favorite.restaurant_id, favorite.fav_note)
                )
            return True
        except Exception as e:
            print(f"Add Favorite Error: {e}")
            return False

    # 查詢使用者已收藏餐廳
    def is_favorite(self, user_id: int, restaurant_id: str) -> bool:
        sql = f"select fav_id from {self.table_name} where user_id =%s and restaurant_id=%s"

        try:
            with get_db_cursor() as cursor:
                cursor.execute(sql, (user_id, restaurant_id))
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            print(f"Check Favorite Error: {e}")
            return False

    # 取得使用者收藏餐廳及詳細資訊列表
    def get_favorite_list_with_detail(self, user_id: int) -> List[Dict[Any, Any]]:
        sql = f"""
            select fav_id favId, user_id userId, fav_note favNote, Name name, CoverImage coverImage, restaurant_id restaurantId
            from {self.table_name} join restaurants on 
            restaurant_id = ID
            where user_id =%s
        """
        with get_db_cursor() as cursor:
            cursor.execute(sql, (user_id,))
            return cursor.fetchall()

    # 更新收藏餐廳的備註
    def update_favorite_notes(self, update_data: UpdateFavorite) -> bool:
        sql = f"UPDATE {self.table_name} SET fav_note = %s WHERE fav_id = %s"
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(sql, (update_data.fav_note, update_data.fav_id))
            return True
        except Exception as e:
            print(f"Update Favorite Error: {e}")
            return False

    # 刪除收藏餐廳
    def delete_by_id(self, fav_id: int) -> bool:
        sql = f"DELETE FROM {self.table_name} WHERE fav_id = %s"
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(sql, (fav_id,))
            return True
        except Exception as e:
            print(f"Delete Favorite By ID Error: {e}")
            return False

    # 取消收藏餐廳
    def delete_by_user_and_restaurant(self, user_id: int, restaurant_id: str) -> bool:
        # 根據您路由中的 SQL：user_id=%s and restaurant_id=%s
        sql = f"DELETE FROM {self.table_name} WHERE user_id = %s AND restaurant_id = %s"
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(sql, (user_id, restaurant_id))
                # 檢查是否真的有刪除到資料 (rowcount > 0)
                if cursor.rowcount == 0:
                    print(
                        f"Delete Warn: No record found for User {user_id} and Restaurant {restaurant_id}"
                    )
                    return False
            return True
        except Exception as e:
            print(f"Delete Favorite By User and Restaurant Error: {e}")
            return False
