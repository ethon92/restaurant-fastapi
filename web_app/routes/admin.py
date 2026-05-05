from fastapi import APIRouter, Depends
from web_app.routes.auth import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def get_all_users(current_admin: dict = Depends(get_current_admin)):
    """
    取得所有會員資料（目前先做管理員權限測試用）
    - 只有 role=admin 的使用者可存取
    """
    return {"message": "only admin can access"}
