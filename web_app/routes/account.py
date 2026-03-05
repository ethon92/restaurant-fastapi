from fastapi import APIRouter, Path, HTTPException
from web_app.mysql_connection import get_db_cursor
from web_app.models.feature import UpdateCommentStatus
import pymysql
from typing import Annotated

router = APIRouter()


# 建立comment的table
def create_comment_table(cursor):
    create_query = """
    create table comments (
        comment_id int primary key auto_increment,
        user_id int not null,
        restaurant_id varchar(50) not null,             
        comment_content varchar(255) not null,   
        rating int not null check(rating >= 1 AND rating <= 5),              
        comment_time DATETIME DEFAULT CURRENT_TIMESTAMP 
    );
    """
    cursor.execute("show tables like %s", ("comments"))
    result = cursor.fetchone()
    # 當沒有table時才建立
    if result is None:
        try:
            cursor.execute(create_query)
            print("comments table is created!!")
        except pymysql.Error as e:
            print(f"Error create comment table: {e}")


# 查詢評論餐廳路由(根據 User ID)
@router.get("/comments/{user_id}")

def get_comment(user_id:Annotated[int, Path(title="The ID of user", gt=0)]):
    try:
        with get_db_cursor() as cursor:
            sql = """
                select comment_id, user_id, Name,restaurant_id, comment_content, rating, comment_time from comments join restaurants on restaurant_id = ID where user_id=%s;
                """
            cursor.execute(sql, (user_id))
            results = cursor.fetchall()
        return {"status": "Success", "user_id": user_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤:{e}")

    
@router.put("/booking/comment-status")
def update_comment_status(update: UpdateCommentStatus):
    try:
        with get_db_cursor(commit=True) as cursor:
            # 1. 檢查此筆訂位紀錄是否存在
            cursor.execute(
                "SELECT * FROM reservations WHERE booking_id = %s",
                (update.booking_id,)
            )
            result = cursor.fetchone()
            
            # 若不存在則丟出 404 錯誤
            if not result:
                raise HTTPException(status_code=404, detail="找不到此筆訂位紀錄!!")
            
            # 2. 執行更新：將 is_commented 設為 1
            update_sql = (
                "UPDATE reservations SET is_commented = 1 WHERE booking_id = %s"
            )
            cursor.execute(
                update_sql, (update.booking_id,)
            )
            
            return {
                "status": "Success",
                "message": "評論狀態已更新"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        # 捕捉資料庫或其他非預期錯誤
        raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")


@router.get("/booking-record/{user_id}")
def get_booking_record(user_id: Annotated[int, Path(title="The ID of user", gt=0)]):
    try:
        with get_db_cursor() as cursor:
            sql = """
                select booking_id id, restaurant_name name,ID, created_at time, booking_status status, is_commented
                from reservations join restaurants on restaurant_name=Name where user_id = %s
            """
            cursor.execute(sql, (user_id))
            results = cursor.fetchall()

            return {"status": "Success", "user_id": user_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫錯誤: {e}")
