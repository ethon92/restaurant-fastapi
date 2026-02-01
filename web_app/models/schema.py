from pydantic import BaseModel,EmailStr, Field
from typing import Optional
from datetime import datetime


class ReservationRequest(BaseModel):
    restaurant_name: str
    user_name: str
    user_id: int            
    phone: str = Field(..., pattern=r"^09\d{8}$") 
    email: EmailStr
    party_size: int
    booking_time: datetime
    note: Optional[str] = None
    booking_status: Optional[str] = "confirmed"
    
