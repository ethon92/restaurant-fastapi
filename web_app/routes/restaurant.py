from fastapi import APIRouter, HTTPException, Query, Path, Request
from typing import List, Optional, Annotated
from web_app.models.schema import ReservationRequest, RestaurantSchema
from web_app.services.restaurant_service import RestaurantService
from fastapi import File, UploadFile, Form, Depends
from typing import Optional
from web_app.services.vector_db import RestaurantSearchService
from web_app.models.feature import ImageSearchParams
router = APIRouter()
service = RestaurantService()

# 實例化以圖片推薦餐廳的 Service
search_logic = RestaurantSearchService()


# 1. [全部餐廳列表]
@router.get("/api/restaurants")
async def get_all_restaurants(skip: int = 0, limit: int = 20):
    return service.get_list(skip, limit)


# 2. [連動搜尋 API]
@router.get("/api/search", response_model=List[RestaurantSchema])
def search_restaurants(
    request: Request,
    q: Optional[str] = None,
    city: List[str] = Query(default=[]),
    tags: List[str] = Query(default=[]),
    price_level: Optional[str] = None,
    skip: int = 0,
    limit: int = 5,
):
    semantic_svc = getattr(request.app.state, "semantic", None)
    return service.search(
        q=q or "", city=city, tags=tags, price_level=price_level or "全部",
        skip=skip, limit=limit, semantic_svc=semantic_svc
    )


# 3. [地圖搜尋範圍 API]
@router.get("/api/restaurants/map-search")
async def get_restaurants_by_bounds(
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    q: Optional[str] = None,
    city: List[str] = Query(None),
):
    results = service.get_restaurants_by_bounds(
        min_lat=min_lat,
        max_lat=max_lat,
        min_lng=min_lng,
        max_lng=max_lng,
        q=q,
        city=city,
    )
    return results if results else []


# 以圖片推薦餐廳 API
@router.post("/api/search/image")
async def api_search_image(
    file: UploadFile = File(...),
    # 使用 Depends 將 Form 欄位對應到 Model
    params: ImageSearchParams = Depends()
):
    try:
        results = await search_logic.search_by_image(file, params.city)
        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        # 這裡處理最後的錯誤回傳
        raise HTTPException(status_code=500, detail=f"搜尋失敗: {str(e)}")


# 4. [詳情 API]
@router.get("/api/restaurant/{id}")
def get_restaurant_detail(id: str):
    info = service.get_detail_by_id(id)
    if not info:
        raise HTTPException(status_code=404, detail="找不到此餐廳")
    random_images = info.get("images", [])
    info.pop("images", None)
    return {"status": "Success", "info": info, "gallery": random_images}

    # gallery_images = [info["CoverImage"]] if info.get("CoverImage") else []
    # return {"info": info, "gallery": gallery_images}


# 5. [查詢餐廳評論 API]
@router.get("/RestaurantComment/{restaurant_id}")
def get_restaurant_comment(restaurant_id: str):
    try:
        results = service.get_comments_by_restaurant(restaurant_id)
        return {"status": "Success", "restaurant_id": restaurant_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"系統錯誤: {e}")


# 6. [新增預約 API]
@router.post("/api/reservations")
def add_reservations(booking: ReservationRequest):
    try:
        # 1. 儲存預約
        new_id = service.save_reservation(booking.dict())
        # 2. 取得包含會員名稱的完整資訊
        full_data = service.get_reservation_full_detail(new_id)

        if not full_data:
            return {
                "status": "success",
                "message": "預約成功！(詳情讀取中...)",
                "data": {"booking_id": new_id},
            }

        return {
            "status": "success",
            "message": f"預約成功！歡迎 {full_data.get('member_name', '')} 會員",
            "data": full_data,
        }
    except ValueError as ve:
        error_msg = str(ve)
        if error_msg == "DuplicateBooking":
            raise HTTPException(
                status_code=409, detail="該時段您已有預約，請勿重複提交!!"
            )
        if error_msg == "InvalidUser":
            raise HTTPException(status_code=400, detail="無效的會員 ID，請先註冊!!")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"伺服器錯誤: {e}")


# 7. [刪除預約 API]
@router.delete("/api/reservations/{user_id}/{booking_id}")
def delete_reservation(
    user_id: Annotated[int, Path(title="The ID of user", gt=0)], booking_id: int
):
    success = service.delete_reservation(user_id, booking_id)
    if not success:
        raise HTTPException(status_code=404, detail="找不到此筆預約資料，無法取消")

    return {"status": "Success", "message": "預約已成功取消"}
