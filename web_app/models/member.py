from datetime import date
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# =========================
# Auth (登入 / 註冊)
# =========================


class RegisterPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=255)
    birthday: date


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


# =========================
# Forgot Password Flow (忘記密碼)
# - 不需要目前密碼
# - 使用生日/身分資料驗證
# =========================


class ForgotPasswordPayload(BaseModel):
    email: EmailStr


class SendOtpPayload(BaseModel):
    email: str


class VerifyOtpPayload(BaseModel):
    email: str
    otp: str  # 6 碼字串


class ResetByOtpPayload(BaseModel):
    email: str
    otp: str
    new_password: str


# =========================
# Profile / Account (已登入敏感操作)
# - 需要目前密碼 re-auth
# =========================


class GetProfilePayload(BaseModel):
    user_id: int


class VerifyPasswordPayload(BaseModel):
    user_id: int
    current_password: str


class UpdateProfilePayload(BaseModel):
    user_id: int
    name: str
    birthday: Optional[date] = None
    phone: Optional[str] = None
    current_password: str


class ProfilePayload(BaseModel):
    user_id: int
    name: str
    email: str
    birthday: str
    role: str
    phone: Optional[str] = None


class ChangePasswordPayload(BaseModel):
    user_id: int
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=255)
