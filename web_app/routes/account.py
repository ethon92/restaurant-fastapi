from fastapi import APIRouter, Path, HTTPException
from web_app.mysql_connection import get_db_cursor
import pymysql
from typing import Annotated

router = APIRouter()

# 查詢評論餐廳路由(根據 User ID)
@router.get("/comment/{user_id}")

def get_comment(user_id:Annotated[int, Path(title="The ID of user", gt=0)]):
    try:
        with get_db_cursor() as cursor:
            sql = """
                select comment_id, user_id, comment_content, RestaurantName, rating from comment 
                join restaurants on restaurant_id = RestaurantID where user_id=%s
                """
            cursor.execute(sql,(user_id))
            results = cursor.fetchall()
        return {
            "status": "Success",
            "user_id": user_id,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{e}")