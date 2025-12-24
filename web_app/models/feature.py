from pydantic import BaseModel

class FavoriteRestaurant(BaseModel):
    user_id: int
    restaurant_id: int
    fav_note: str | None
