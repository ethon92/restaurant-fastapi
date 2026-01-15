from fastapi import APIRouter, Path, HTTPException
from web_app.mysql_connection import get_db_cursor
import pymysql
from typing import Annotated

router = APIRouter()

# 查詢評論餐廳路由(根據 restaurant ID)
@router.get("/comment/{restaurant_id}")

def get_comment(restaurant_id:Annotated[str, Path(title="The ID of restaurant", gt=0)]):
    try:
        with get_db_cursor() as cursor:
            sql = """
                select comment_id, user_id, comment_content, RestaurantName, rating from comment 
                join restaurants on restaurant_id = RestaurantID where restaurant_id=%s
                """
            cursor.execute(sql,(restaurant_id))
            results = cursor.fetchall()
        return {
            "status": "Success",
            "user_id": restaurant_id,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{e}")