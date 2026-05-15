from pydantic import BaseModel, Field , EmailStr
from typing import Optional
from datetime import date

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

class UserOut(BaseModel):
    user_name: str
    user_email: EmailStr
    user_phone: Optional[str] = None
    user_birthday: Optional[date] = None
    user_role: int
    
# 以圖推薦餐廳
class ImageSearchParams(BaseModel):
    city: str = Field(default="", description="搜尋的縣市")