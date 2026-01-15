from fastapi import APIRouter, HTTPException
from web_app.mysql_connection import get_db_cursor
from web_app.models.member import (
    LoginPayload,
    RegisterPayload,
    ForgotPasswordPayload,
    VerifyIdentityPayload,
    ResetPasswordPayload,
)
import pymysql


router = APIRouter(prefix="/auth", tags=["auth"])


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

    # 寫入資料庫（暫時明碼）
    with get_db_cursor(commit=True) as cursor:
        cursor.execute(
            insert_sql,
            (payload.name, payload.email, payload.password, payload.birthday, 0),
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

    # 暫時明碼比對
    if user["user_password"] != payload.password:
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
