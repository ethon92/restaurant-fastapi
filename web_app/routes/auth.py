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
    SendOtpPayload,
    VerifyOtpPayload,
    ResetByOtpPayload,
    # Profile / Account
    GetProfilePayload,
    VerifyPasswordPayload,
    UpdateProfilePayload,
    ProfilePayload,
)
import pymysql
import re
import time
import secrets
import hashlib


router = APIRouter(prefix="/auth", tags=["auth"])

# ============================================================
# Password policy (共用密碼規則)
# 規則：6~15 碼、至少 1 個英文、至少 1 個數字、僅限英數
# ============================================================
PASSWORD_RULE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{6,15}$")


def _validate_password_or_400(password: str):
    """
    統一密碼規則檢查
    - 失敗就丟 400，讓前端顯示 detail
    """
    if not PASSWORD_RULE.match(password):
        raise HTTPException(
            status_code=400,
            detail="Password must be 6-15 chars and include letters and numbers",
        )


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
        `user_phone` VARCHAR(10) NULL,
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

    # ✅ 密碼規則檢查（英文+數字、6~15碼）
    _validate_password_or_400(payload.password)

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


# ------------------------------------------------------------
# OTP 暫存（開發用）
# key = email
# value = {
#   "otp_hash": "...",
#   "expires_at": 1234567890,
#   "verified": False,
#   "attempts": 0,
#   "last_sent_at": 1234567890
# }
# ------------------------------------------------------------
OTP_TTL_SECONDS = 5 * 60  # OTP 有效 5 分鐘
OTP_RESEND_COOLDOWN = 60  # 60 秒內不可重寄（避免狂發）
OTP_MAX_ATTEMPTS = 5  # 最多嘗試 5 次（防暴力猜）
_otp_store = {}


def _hash_otp(email: str, otp: str) -> str:
    """
    用 email + otp 做 hash，避免記憶體中存明碼 OTP
    """
    raw = f"{email.lower()}::{otp}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _generate_otp_6() -> str:
    """
    產生 6 位數 OTP（000000~999999）
    secrets 比 random 更適合安全用途
    """
    return f"{secrets.randbelow(1_000_000):06d}"


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
# 2-B) Forgot Password Flow (Email OTP)
#    - send-otp：寄出驗證碼（開發期用 print）
#    - verify-otp：驗證碼核對
#    - reset：驗證成功才允許更新密碼
# ============================================================


@router.post("/forgot-password/send-otp")
async def send_forgot_password_otp(payload: SendOtpPayload):
    """
    Step 1：輸入 email → 若存在就產生 OTP，並「寄出」(開發期用 print)
    """
    email = payload.email.strip().lower()

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    # 1) 檢查 email 是否存在
    sql = "SELECT user_id FROM users WHERE user_email = %s LIMIT 1"
    with get_db_cursor() as cursor:
        cursor.execute(sql, (email,))
        user = cursor.fetchone()

    if not user:
        # 實務上可改成回傳 ok（避免洩漏帳號是否存在）
        # 但你目前開發期要明確提示，就先 404
        raise HTTPException(status_code=404, detail="Email not found")

    now = int(time.time())
    record = _otp_store.get(email)

    # 2) 簡單限流：60 秒內不可重寄
    if record and (now - record.get("last_sent_at", 0) < OTP_RESEND_COOLDOWN):
        raise HTTPException(status_code=429, detail="Too many requests")

    # 3) 產生 OTP + 存 hash（不存明碼）
    otp = _generate_otp_6()
    _otp_store[email] = {
        "otp_hash": _hash_otp(email, otp),
        "expires_at": now + OTP_TTL_SECONDS,
        "verified": False,
        "attempts": 0,
        "last_sent_at": now,
    }

    # ✅ 開發期：直接印在後端 console（之後再換成 SMTP 寄信）
    print(f"[DEV OTP] email={email} otp={otp} (valid {OTP_TTL_SECONDS}s)")

    return {"message": "otp sent"}


@router.post("/forgot-password/verify-otp")
async def verify_forgot_password_otp(payload: VerifyOtpPayload):
    """
    Step 2：輸入 email + otp → 驗證成功後，把狀態記為 verified
    """
    email = payload.email.strip().lower()
    otp = payload.otp.strip()

    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email and otp required")

    record = _otp_store.get(email)
    now = int(time.time())

    if not record:
        raise HTTPException(status_code=400, detail="OTP not requested")

    # 過期
    if now > record["expires_at"]:
        _otp_store.pop(email, None)
        raise HTTPException(status_code=400, detail="OTP expired")

    # 嘗試次數過多
    if record["attempts"] >= OTP_MAX_ATTEMPTS:
        _otp_store.pop(email, None)
        raise HTTPException(status_code=429, detail="Too many attempts")

    # OTP 基本檢查
    if not otp.isdigit() or len(otp) != 6:
        raise HTTPException(status_code=400, detail="OTP format invalid")

    # 比對 hash
    if _hash_otp(email, otp) != record["otp_hash"]:
        record["attempts"] += 1
        raise HTTPException(status_code=401, detail="OTP invalid")

    # 驗證成功
    record["verified"] = True
    record["attempts"] = 0

    return {"message": "otp verified"}


@router.post("/forgot-password/reset")
async def reset_password_by_otp(payload: ResetByOtpPayload):
    """
    Step 3：email + otp + new_password
    - 必須 OTP 已驗證，且仍在有效期內
    - 更新 users.user_password（hash 後存）
    """
    email = payload.email.strip().lower()
    otp = payload.otp.strip()
    new_password = payload.new_password

    if not email or not otp or not new_password:
        raise HTTPException(status_code=400, detail="Missing fields")

    record = _otp_store.get(email)
    now = int(time.time())

    if not record:
        raise HTTPException(status_code=400, detail="OTP not requested")

    if now > record["expires_at"]:
        _otp_store.pop(email, None)
        raise HTTPException(status_code=400, detail="OTP expired")

    # 要求先 verify-otp 成功（
    if not record.get("verified"):
        raise HTTPException(status_code=401, detail="OTP not verified")

    # 再保險：也驗一次 otp hash（避免 verified 被誤用）
    if _hash_otp(email, otp) != record["otp_hash"]:
        raise HTTPException(status_code=401, detail="OTP invalid")

    # 密碼規則檢查（英文+數字、6~15碼）
    _validate_password_or_400(new_password)

    hashed_pwd = hash_password(new_password)

    update_sql = """
        UPDATE users
        SET user_password = %s
        WHERE user_email = %s
        LIMIT 1
    """

    with get_db_cursor(commit=True) as cursor:
        cursor.execute(update_sql, (hashed_pwd, email))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Email not found")

    # ✅ 用完就清掉 OTP（避免重放）
    _otp_store.pop(email, None)

    return {"message": "reset ok"}


# ============================================================
# 3) Profile / Account (已登入操作)
#    - 取得資料
#    - 驗證目前密碼（re-auth）
#    - 更新基本資料（需目前密碼）
# ============================================================


@router.post("/profile")
async def profile(payload: GetProfilePayload):
    sql = """
        SELECT user_id, user_name, user_email, user_birthday, user_role, user_phone
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
        "phone": user["user_phone"] or "",  # ✅ 新增：回傳手機（空就回 ""
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
    """
    更新會員基本資料（需輸入目前密碼）
    可更新：
      - user_name
      - user_birthday
      - user_phone（可空，送 "" 視為清空）
    """

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

    # 3) phone 格式驗證（允許 None 或 ""）
    phone = payload.phone
    if phone == "":
        phone = None

    if phone is not None and not re.match(r"^09[0-9]{8}$", phone):
        raise HTTPException(status_code=400, detail="Phone format invalid")

    # 4) 密碼正確才更新
    update_sql = """
        UPDATE users
        SET user_name = %s,
            user_birthday = %s,
            user_phone = %s
        WHERE user_id = %s
        LIMIT 1
    """

    with get_db_cursor(commit=True) as cursor:
        cursor.execute(
            update_sql, (payload.name, payload.birthday, phone, payload.user_id)
        )

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")

    return {"message": "update ok"}
