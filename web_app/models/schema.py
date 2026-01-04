from pydantic import BaseModel

class ReservationRequest(BaseModel):
    restaurant_name: str
    user_name: str
    phone: str
    date: str
    time: str
    people: int