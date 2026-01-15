from fastapi import APIRouter
from web_app.models.member import (
    LoginPayload,
    RegisterPayload,
    ForgotPasswordPayload,
    VerifyIdentityPayload,
    ResetPasswordPayload,
)

# 資料庫模型需要這行
# from web_app.models import member

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.post("/verify-identity")
async def verify_identity(payload: VerifyIdentityPayload):
    return {
        "message": "identity ok",
        "email": payload.email,
        "birthday": str(payload.birthday),
    }


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    return {"message": "reset ok", "email": payload.email}


@router.get("/profile")
async def profile():
    return {"email": "test@example.com", "role": "user"}


@router.post("/logout")
async def logout():
    return {"message": "logout ok"}
