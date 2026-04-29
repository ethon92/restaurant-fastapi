from fastapi import APIRouter, HTTPException ,
from web_app.mysql_connection import get_db_cursor
import pymysql
from web_app.services.ai_service import analyze_all_comments_with_snow

router = APIRouter()

@router.post("/api/v1/admin/batch-analyze")
async def start_analysis():
    count = analyze_all_comments_with_snow()
    return {"status": "success", "message": f"分析完成，共處理 {count} 筆評論"}
@router.get("/api/v1/admin/restaurant-status")
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
                    r.restaurant_name AS name,
                    COUNT(c.comment_id) AS total_comments,
                    SUM(CASE WHEN c.sentiment_score <= 0.33 THEN 1 ELSE 0 END) AS bad_comments_count,
                    AVG(c.sentiment_score) AS sentiment_score
                FROM restaurant r
                LEFT JOIN comments c ON r.restaurant_id = c.restaurant_id
                GROUP BY r.restaurant_id, r.restaurant_name
                ORDER BY sentiment_score ASC;
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
