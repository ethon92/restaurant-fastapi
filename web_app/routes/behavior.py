from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from web_app.mysql_connection import get_db_cursor

router = APIRouter(prefix="/behavior", tags=["behavior"])


class BehaviorPayload(BaseModel):
    """
    行為紀錄 payload
    前端會用 JSON 傳進來，例如：
    {
        "user_id": 13,
        "restaurant_id": "C3_376580000A_000141",
        "action_type": "favorite"
    }
    """

    user_id: int
    restaurant_id: str
    action_type: str


@router.post("")
async def record_behavior(payload: BehaviorPayload):
    """
    記錄使用者行為，提供 AI 推薦系統訓練資料使用

    action_type 可接受：
    - click    : 點擊餐廳
    - favorite : 收藏餐廳
    - booking  : 訂位餐廳
    """

    # 1) 限制可接受的行為類型，避免亂塞資料
    allowed_actions = ["click", "favorite", "booking"]

    if payload.action_type not in allowed_actions:
        raise HTTPException(status_code=400, detail="Invalid action_type")

    # 2) 寫入資料表
    insert_sql = """
        INSERT INTO user_behavior (user_id, restaurant_id, action_type)
        VALUES (%s, %s, %s)
    """

    with get_db_cursor(commit=True) as cursor:
        cursor.execute(
            insert_sql, (payload.user_id, payload.restaurant_id, payload.action_type)
        )

    return {"message": "behavior recorded"}
