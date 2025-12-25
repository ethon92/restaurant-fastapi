from fastapi import APIRouter, Path, HTTPException
from web_app.models.feature import FavoriteRestaurant
from web_app.mysql_connection import get_db_cursor
import pymysql
from typing import Annotated


router = APIRouter()

# 建立table函式
def create_table(cursor):
    create_query = f"""
        create table favorite(
            fav_id int primary key auto_increment,
            user_id int not null,
            restaurant_id int not null,
            fav_note varchar(300)
        )
        """
    cursor.execute("show tables like %s", ("favorite"))
    result = cursor.fetchone()

    # 當沒有table時才建立
    if result is None:
        try:
            cursor.execute(create_query)
            print(f"favorite table is created!!")
        except pymysql.Error as e:
            print(f"Error create favorite table: {e}")

# 新增收藏餐廳路由
@router.post("/favorite")
def add_favorite(favorite: FavoriteRestaurant):
    try:
        # 在favorite中放入資料
        # 注意:提交資料要commit記得設為True
        with get_db_cursor(commit=True) as cursor:
            create_table(cursor)
            sql = "insert into favorite(user_id, restaurant_id, fav_note) values(%s, %s, %s)"           
            cursor.execute(sql, (favorite.user_id, favorite.restaurant_id, favorite.fav_note))           
            return {
                "status": "Success"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")

# 查詢收藏餐廳路由
@router.get("/favorite/{user_id}")
# 設定user_id必須大於0
def get_favorite(user_id: Annotated[int, Path(title="The ID of user", gt=0)]):
    try:
        with get_db_cursor() as cursor:
            sql = "select * from favorite where user_id=%s"
            cursor.execute(sql, (user_id))
            results = cursor.fetchall()
        return {
            "status": "Success",
            "user_id": user_id,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")
    


        