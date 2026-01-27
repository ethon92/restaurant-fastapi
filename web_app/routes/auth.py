from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from web_app.mysql_connection import get_db_cursor
from web_app.models.member import (
    LoginPayload,
    RegisterPayload,
    ForgotPasswordPayload,
    VerifyIdentityPayload,
    ResetPasswordPayload,
)
import pymysql
import hashlib
import os


router = APIRouter(prefix="/auth", tags=["auth"])

# 密碼 hash（sha256 + SALT）

PWD_SALT = os.getenv("PWD_SALT", "dev_salt_change_me")  # 之後記得換成環境變數


def hash_password(raw: str) -> str:
    return hashlib.sha256((raw + PWD_SALT).encode("utf-8")).hexdigest()


def verify_password(raw: str, hashed: str) -> bool:
    return hash_password(raw) == hashed


# 建立table函式
def create_table(cursor):
    create_query = """
        CREATE TABLE IF NOT EXISTS `users` (
        `user_id` INTEGER NOT NULL AUTO_INCREMENT,
        `user_name` VARCHAR(20),
        `user_email` VARCHAR(30) NOT NULL,
        `user_password` VARCHAR(255) NOT NULL,
        `user_birthday` DATE NOT NULL,
        `user_role` BOOLEAN DEFAULT 0,
        PRIMARY KEY (`user_id`),
        UNIQUE KEY `uq_users_email` (`user_email`)
);
        """

    # 當沒有table時才建立
    try:
        cursor.execute(create_query)
        print("users table checked / created successfully")
    except pymysql.Error as e:
        print(f"Error creating users table: {e}")


@router.post("/register")
async def register(payload: RegisterPayload):

    # 先檢查 email 是否已存在
    check_sql = "SELECT user_id FROM users WHERE user_email = %s"
    insert_sql = """
        INSERT INTO users
        (user_name, user_email, user_password, user_birthday, user_role)
        VALUES (%s, %s, %s, %s, %s)
    """

    with get_db_cursor() as cursor:
        cursor.execute(check_sql, (payload.email,))
        exist = cursor.fetchone()

    if exist:
        raise HTTPException(status_code=400, detail="Email already exists")

    # hash 密碼再存
    hashed_pwd = hash_password(payload.password)

    with get_db_cursor(commit=True) as cursor:
        cursor.execute(
            insert_sql,
            (
                payload.name,
                payload.email,
                hash_password(payload.password),
                payload.birthday,
                0,
            ),
        )

    return {"message": "register ok", "email": payload.email}


@router.post("/login")
async def login(payload: LoginPayload):
    sql = """
        SELECT user_id, user_email, user_password, user_role
        FROM users
        WHERE user_email = %s
        LIMIT 1
    """

    with get_db_cursor() as cursor:
        cursor.execute(sql, (payload.email,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # 用 hash 比對
    if not verify_password(payload.password, user["user_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "message": "login ok",
        "user": {
            "id": user["user_id"],
            "email": user["user_email"],
            "role": "admin" if user["user_role"] else "user",
        },
    }


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload):
    # 檢查 email 存在（不真的寄信，先把流程打通）
    sql = "SELECT user_id FROM users WHERE user_email = %s LIMIT 1"
    with get_db_cursor() as cursor:
        cursor.execute(sql, (payload.email,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Email not found")

    return {"message": "forgot-password ok", "email": payload.email}


@router.post("/verify-identity")
async def verify_identity(payload: VerifyIdentityPayload):
    # 檢查 email + birthday 對不對
    sql = """
        SELECT user_id, user_birthday
        FROM users
        WHERE user_email = %s
        LIMIT 1
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, (payload.email,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Email not found")

    # payload.birthday 是 date，user["user_birthday"] 也是 date（通常）
    if str(user["user_birthday"]) != str(payload.birthday):
        raise HTTPException(status_code=401, detail="Birthday not match")

    return {"message": "identity ok", "email": payload.email}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    # 更新密碼（hash 後存）
    update_sql = """
        UPDATE users
        SET user_password = %s
        WHERE user_email = %s
        LIMIT 1
    """

    hashed_pwd = hash_password(payload.password)

    with get_db_cursor(commit=True) as cursor:
        cursor.execute(update_sql, (hashed_pwd, payload.email))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email not found")

    return {"message": "reset ok", "email": payload.email}


# 對齊前端 auth.js：POST /auth/profile（帶 email）
class ProfilePayload(BaseModel):
    email: str


@router.post("/profile")
async def profile(payload: ProfilePayload):
    sql = """
        SELECT user_id, user_name, user_email, user_birthday, user_role
        FROM users
        WHERE user_email = %s
        LIMIT 1
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, (payload.email,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["user_id"],
        "name": user["user_name"],
        "email": user["user_email"],
        "birthday": str(user["user_birthday"]),
        "role": "admin" if user["user_role"] else "user",
    }


@router.post("/logout")
async def logout():
    return {"message": "logout ok"}
