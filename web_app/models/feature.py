from pydantic import BaseModel, Field

class FavoriteRestaurant(BaseModel):
    user_id: int
    restaurant_id: str
    fav_note: str | None

class UpdateFavorite(BaseModel):
    fav_id: int
    fav_note: str | None

class RestaurantComment(BaseModel):
    user_id: int
    restaurant_id: str
    comment_content: str
    rating: int

class updateRestaurantComment(BaseModel):
    comment_id: int
    user_id: int
    restaurant_id: str
    comment_content: str
    rating: int

class UpdateCommentStatus(BaseModel):
    booking_id: int

# 以圖推薦餐廳
class ImageSearchParams(BaseModel):
    city: str = Field(default="", description="搜尋的縣市")