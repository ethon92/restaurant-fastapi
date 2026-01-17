from pydantic import BaseModel
from typing import Optional
from datetime import date, time

class ReservationRequest(BaseModel):
    restaurant_name: str
    user_name: str
    phone: str
    date: date
    time: time
    people: int
    note: Optional[str] = ""