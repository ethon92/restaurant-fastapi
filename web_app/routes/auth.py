from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str
    birthday: str
    
class ForgotPasswordPayload(BaseModel):
    email: EmailStr


class VerifyIdentityPayload(BaseModel):
    email: EmailStr
    birthday: str


class ResetPasswordPayload(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(payload: LoginPayload):
    return {
        "message": "login ok",
        "user": {"email": payload.email, "role": "user"},
    }


@router.post("/register")
async def register(payload: RegisterPayload):
    return {"message": "register ok", "email": payload.email}



@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload):
    return {"message": "verify ok", "email": payload.email}



@router.post("/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    return {"message": "reset ok", "email": payload.email}


@router.get("/profile")
async def profile():
    return {"email": "test@example.com", "role": "user"}


@router.post("/logout")
async def logout():
    return {"message": "logout ok"}