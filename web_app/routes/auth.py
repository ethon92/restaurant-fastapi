from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from web_app.mysql_connection import get_db_cursor
from web_app.utils.security import hash_password, verify_password
from web_app.models.member import (
    # Auth
    LoginPayload,
    RegisterPayload,
    # Forgot password
    ForgotPasswordPayload,
    VerifyIdentityPayload,
    ResetPasswordPayload,
    # Profile / Account
    GetProfilePayload,
    VerifyPasswordPayload,
    UpdateProfilePayload,
    ProfilePayload,
)
import pymysql


router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================
# DB: Table bootstrap
# ============================================================
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


# ============================================================
# 1) Auth (註冊 / 登入 / 登出)
# ============================================================


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
                hashed_pwd,
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


@router.post("/logout")
async def logout():
    return {"message": "logout ok"}


# ============================================================
# 2) Forgot Password Flow (忘記密碼：生日驗證)
#    「不需要目前密碼」
# ============================================================


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
    # 忘記密碼流程通常會搭配：
    # - verify-identity 成功才允許 reset
    # 這裡先做最小版：只要 email 存在就更新

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


# ============================================================
# 3) Profile / Account (已登入操作)
#    - 取得資料
#    - 驗證目前密碼（re-auth）
#    - 更新基本資料（需目前密碼）
# ============================================================


@router.post("/profile")
async def profile(payload: GetProfilePayload):
    sql = """
        SELECT user_id, user_name, user_email, user_birthday, user_role
        FROM users
        WHERE user_id = %s
        LIMIT 1
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, (payload.user_id,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["user_id"],
        "name": user["user_name"],
        "email": user["user_email"],
        "birthday": str(user["user_birthday"]) if user["user_birthday"] else "",
        "role": "admin" if user["user_role"] else "user",
    }


@router.post("/verify-password")
async def verify_password_api(payload: VerifyPasswordPayload):
    """
    Re-authentication endpoint (for sensitive actions).
    Profile 頁面，使用者要做「更改密碼」之前，
    會先呼叫這支 API 讓使用者再輸入一次密碼確認，
    通過後才允許真的去改密碼
    """
    sql = """
        SELECT user_password
        FROM users
        WHERE user_id = %s
        LIMIT 1
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, (payload.user_id,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 用 hash 驗證（跟 login 一樣）
    if not verify_password(payload.current_password, user["user_password"]):
        raise HTTPException(status_code=401, detail="Password incorrect")

    return {"message": "password verified"}


@router.put("/profile")
async def update_profile(payload: UpdateProfilePayload):
    # 1) 先查使用者（拿到 password hash）
    select_sql = """
        SELECT user_id, user_password
        FROM users
        WHERE user_id = %s
        LIMIT 1
    """

    with get_db_cursor() as cursor:
        cursor.execute(select_sql, (payload.user_id,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2) 驗證目前密碼（sha256+salt）
    if not verify_password(payload.current_password, user["user_password"]):
        raise HTTPException(status_code=401, detail="Password incorrect")

    # 3) 密碼正確才更新
    sql = """
        UPDATE users
        SET user_name = %s,
            user_birthday = %s
        WHERE user_id = %s
        LIMIT 1
    """

    with get_db_cursor(commit=True) as cursor:
        cursor.execute(sql, (payload.name, payload.birthday, payload.user_id))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")

    return {"message": "update ok"}
