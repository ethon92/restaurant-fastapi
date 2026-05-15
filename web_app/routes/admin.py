from fastapi import APIRouter, HTTPException , Depends
from web_app.mysql_connection import get_db_cursor
import pymysql
from web_app.services.ai_service import analyze_all_comments_with_snow
from web_app.routes.auth import get_current_admin
from web_app.models.feature import UserOut
from typing import List

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/batch-analyze")
async def start_analysis():
    count = analyze_all_comments_with_snow()
    return {"status": "success", "message": f"分析完成，共處理 {count} 筆評論"}
@router.get("/restaurant-status")
async def get_restaurant_status():
    """
    抓取前端表格所需的餐廳營運狀態資料
    """
    # 這裡使用你截圖中的 get_db_cursor 邏輯
    with get_db_cursor() as cursor:
        try:
            # 1. 抓取餐廳名稱、總評論數
            # 2. 統計 sentiment_score <= 0.33 的數量 (差評)
            # 3. 平均情感分數 (0~1)
            sql = """
                SELECT 
                    r.Name AS name,
                    COUNT(c.comment_id) AS total_comments,
                    SUM(CASE WHEN c.sentiment <= 0.33 THEN 1 ELSE 0 END) AS bad_comments_count,
                    AVG(c.sentiment) AS sentiment_score
                FROM restaurants r
                LEFT JOIN comments c ON r.ID = c.restaurant_id
                GROUP BY r.ID, r.Name
                ORDER BY sentiment_score ASC
                LIMIT 20 
            """
            cursor.execute(sql)
            rows = cursor.fetchall()

            # 格式化輸出
            formatted_data = [
                {
                    "name": row['name'],
                    "total_comments": row['total_comments'],
                    "bad_comments_count": int(row['bad_comments_count'] or 0),
                    "sentiment_score": round(float(row['sentiment_score'] or 0), 2)
                }
                for row in rows
            ]
            
            return formatted_data

        except pymysql.MySQLError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/users", response_model=List[UserOut])
def get_all_users(current_admin: dict = Depends(get_current_admin)):
    try:
        with get_db_cursor() as cursor:
            # 欄位順序不重要，但名稱必須跟 UserOut 一模一樣
            sql = """
                SELECT 
                    user_name, 
                    user_email, 
                    user_phone, 
                    user_birthday, 
                    user_role 
                FROM users
            """
            cursor.execute(sql)
            users = cursor.fetchall()
            
            return users if users else []

    except Exception as e:
        # 這裡建議印出錯誤，方便調試
        print(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")