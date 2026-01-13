from fastapi import APIRouter, Path, HTTPException
from web_app.models.feature import RestaurantComment
from web_app.mysql_connection import get_db_cursor
import pymysql
from typing import Annotated

router = APIRouter()

# 建立comment的table
def create_table(cursor):
    create_query = """
    CREATE TABLE IF NOT EXISTS `comment` (
        `comment_id` INTEGER PRIMARY KEY auto_increment,
        `user_id` INTEGER NOT NULL,                     
        `restaurant_id` INTEGER NOT NULL,             
        `comment_content` VARCHAR(255),                 
        `comment_time` DATETIME DEFAULT CURRENT_TIMESTAMP 
    );
    """
    cursor.execute("show tables like %s", ("comment"))
    result = cursor.fetchone()
    # 當沒有table時才建立
    if result is None:
        try:
            cursor.execute(create_query)
            print("comment table is created!!")
        except pymysql.Error as e:
            print(f"Error create comment table: {e}")
@router.post("/comment")
def add_comment(comment:RestaurantComment):
    try:
        with get_db_cursor(commit=True) as cursor:
            create_table(cursor)
            cursor.execute("select * from comment where user_id=%s and restaurant_id=%s",(comment.user_id, comment.Restaurant_id))
            result = cursor.fetchone()
            if result is not None:
                raise HTTPException(status_code=409, detail="已完成評論!!")
            
            sql = "insert into comment(user_id,restaurant_id, comment_content) values(%s,%s,%s)"
            cursor.execute(sql, (comment.user_id,comment.restaurant_id,comment.comment_content))
            return{
                "status":"Success"
            }
    except HTTPException:
        raise
    except Exception as event:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{event}") 