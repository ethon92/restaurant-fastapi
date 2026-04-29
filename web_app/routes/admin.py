from fastapi import APIRouter
from web_app.services.ai_service import analyze_all_comments_with_snow

router = APIRouter()

@router.post("/api/v1/admin/batch-analyze")
async def start_analysis():
    count = analyze_all_comments_with_snow()
    return {"status": "success", "message": f"分析完成，共處理 {count} 筆評論"}