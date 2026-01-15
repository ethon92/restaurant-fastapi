from pydantic import BaseModel
from typing import Optional

class ReservationRequest(BaseModel):
    # 這些是必填欄位 (Required)
    restaurant_name: str
    user_name: str
    phone: str
    email: str
    party_size: int
    booking_time: str
    note: Optional[str] = ""