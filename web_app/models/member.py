from datetime import date
from pydantic import BaseModel, EmailStr


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class RegisterPayload(BaseModel):
    email: EmailStr
    password: str
    birthday: date


class ForgotPasswordPayload(BaseModel):
    email: EmailStr


class VerifyIdentityPayload(BaseModel):
    email: EmailStr
    birthday: date


class ResetPasswordPayload(BaseModel):
    email: EmailStr
    password: str
