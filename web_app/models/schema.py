from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReservationRequest(BaseModel):
    restaurant_name: str
    user_name: str
    user_id: int            
    phone: str
    party_size: int
    booking_time: datetime
    note: Optional[str] = None
    booking_status: Optional[str] = "confirmed"
    
