from pydantic import BaseModel

class FavoriteRestaurant(BaseModel):
    user_id: int
    restaurant_id: str
    fav_note: str | None
    
class RestaurantComment(BaseModel):
    user_id: int
    restaurant_id: str
    comment_content: str
    rating: int
