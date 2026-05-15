from pydantic import BaseModel,EmailStr, Field
from typing import Optional,List
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
    
class RestaurantImageSchema(BaseModel):
    image_url: str
    
    class Config:
        from_attributes = True

class RestaurantSchema(BaseModel):
    ID: str
    Name: str
    Add: Optional[str] = None
    PriceLevel: Optional[str] = None
    Tel: Optional[str] = None
    City: Optional[str] = None
    Px: Optional[float] = None  
    Py: Optional[float] = None 
    TagsStr: Optional[str] = None
    Description: Optional[str] = None
    GoogleMap: Optional[str] = None
    Website: Optional[str] = None
    Parking: Optional[str] = None
    ServiceTime: Optional[str] = None
    CoverImage: Optional[str] = None
    images: List[RestaurantImageSchema] = []
    match_score: Optional[float] = None
    
    class Config:
        from_attributes = True
