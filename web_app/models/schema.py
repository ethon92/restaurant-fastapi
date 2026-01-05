from pydantic import BaseModel
from typing import Optional

class ReservationRequest(BaseModel):
    restaurant_name: str
    user_name: str
    phone: str
    date: str
    time: str
    people: int
    note: Optional[str] = ""