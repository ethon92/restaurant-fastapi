from fastapi import APIRouter
from web_app.models.feature import FavoriteRestaurant
from web_app.mysql_connection import get_db_cursor
import pymysql


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

@router.post("/favorite")
def add_favorite(favorite: FavoriteRestaurant):
    try:
        # 在favorite中放入資料
        # 注意:提交資料要commit記得設為True
        with get_db_cursor(commit=True) as cursor:
            create_table(cursor)
            sql = "insert into favorite(user_id, restaurant_id, fav_note) values(%s, %s, %s)"           
            cursor.execute(sql, (favorite.user_id, favorite.restaurant_id, favorite.fav_note))           
            cursor.execute("select * from favorite")            
            new_data = cursor.fetchall()            
            return {
                "success": True,
                "data": new_data
            }
    except Exception as e:
        print(f"Error is happening: {e}")
    
    
    
        