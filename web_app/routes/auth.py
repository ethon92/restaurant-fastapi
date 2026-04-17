from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    Request,
    Depends,
    Header,
)
from pydantic import BaseModel
from web_app.mysql_connection import get_db_cursor
from web_app.utils.security import hash_password, verify_password
from web_app.utils.email_utils import send_otp_email
from web_app.models.member import (
    # Auth
    LoginPayload,
    RegisterPayload,
    # Forgot password
    ForgotPasswordPayload,
    SendOtpPayload,
    VerifyOtpPayload,
    ResetByOtpPayload,
    # Profile / Account
    GetProfilePayload,
    VerifyPasswordPayload,
    UpdateProfilePayload,
    ProfilePayload,
    ChangePasswordPayload,
)
from typing import Optional
import pymysql
import re
import time
import secrets
import hashlib
import os, uuid, imghdr

# =========================
# JWT 相關
# =========================
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

# ============================================================
# Avatar upload settings (存後端 static)
# ============================================================
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

AVATAR_DIR = os.path.join("static", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

router = APIRouter(prefix="/auth", tags=["auth"])

# ============================================================
# Password policy (共用密碼規則)
# 規則：6~15 碼、至少 1 個英文、至少 1 個數字、僅限英數
# ============================================================
PASSWORD_RULE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{6,15}$")

# ============================================================
# JWT 設定
# ============================================================
# ⚠️ 正式環境請一定要改成放在 .env，不要把真正金鑰寫死在專案裡
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev_super_secret_key_change_me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))  # 2 小時


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
# JWT helper functions
# ============================================================
def create_access_token(data: dict, expires_minutes: int = JWT_EXPIRE_MINUTES) -> str:
    """
    建立 JWT access token

    token payload 內會放：
    - sub: 使用者 id（字串）
    - email
    - role
    - exp: 過期時間
    """
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})

    token = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> dict:
    """
    解碼 JWT token
    - 驗證失敗 / 過期都會丟 401
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    取得目前登入者資訊
    前端需在 header 帶：
    Authorization: Bearer <token>

    回傳：
    {
        "user_id": int,
        "email": str,
        "role": "admin" / "user"
    }
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    token = authorization.replace("Bearer ", "").strip()
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    email = payload.get("email")
    role = payload.get("role")

    if not user_id or not email or not role:
        raise HTTPException(status_code=401, detail="Token payload invalid")

    return {
        "user_id": int(user_id),
        "email": email,
        "role": role,
    }


def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    管理員專用 dependency
    之後只要在管理 API 上加 Depends(get_current_admin)
    就能擋掉一般會員
    """
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


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
            `avatar_path` VARCHAR(255) NULL,
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

    """
    註冊新會員
    - user_role 預設 0 = 一般使用者
    - 若要手動做超級管理員，建議直接用 SQL 把某個帳號 user_role 改成 1
    """
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
                0,  # 預設一般會員
            ),
        )

    return {"message": "register ok", "email": payload.email}


@router.post("/login")
async def login(payload: LoginPayload):
    """
    登入：
    1) 驗證 email / password
    2) 依照 user_role 產生 role
    3) 回傳 JWT access_token + user 基本資訊

    回傳格式：
    {
        "message": "login ok",
        "access_token": "...",
        "token_type": "bearer",
        "user": {
            "id": 1,
            "email": "...",
            "role": "admin" / "user"
        }
    }
    """
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

    role = "admin" if user["user_role"] else "user"

    access_token = create_access_token(
        {
            "sub": str(user["user_id"]),
            "email": user["user_email"],
            "role": role,
        }
    )

    return {
        "message": "login ok",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["user_id"],
            "email": user["user_email"],
            "role": role,
        },
    }


@router.post("/logout")
async def logout():
    """
    目前 JWT 採前端刪 token 即視為登出
    若之後要做到「強制失效 token」，要再加黑名單機制
    """
    return {"message": "logout ok"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    讓前端用 token 直接確認目前登入者
    很適合前端重整頁面後重新還原登入狀態
    """
    sql = """
        SELECT user_id, user_name, user_email, user_birthday, user_role, user_phone
        FROM users
        WHERE user_id = %s
        LIMIT 1
    """
    with get_db_cursor() as cursor:
        cursor.execute(sql, (current_user["user_id"],))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["user_id"],
        "name": user["user_name"],
        "email": user["user_email"],
        "birthday": str(user["user_birthday"]) if user["user_birthday"] else "",
        "role": "admin" if user["user_role"] else "user",
        "phone": user["user_phone"] or "",
    }


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

    # ✅ 真正寄出 OTP 信件（HTML + 純文字備援）

    try:
        send_otp_email(email, otp, OTP_TTL_SECONDS)
    except Exception:
        # 寄信失敗：回 500，前端會顯示錯誤提示
        raise HTTPException(status_code=500, detail="Failed to send OTP email")

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


# ============================================================
# Avatar DB helpers
# ============================================================
def get_user_avatar_path(user_id: int) -> Optional[str]:
    sql = "SELECT avatar_path FROM users WHERE user_id=%s LIMIT 1"
    with get_db_cursor() as cursor:
        cursor.execute(sql, (user_id,))
        row = cursor.fetchone()
    return row["avatar_path"] if row else None


def set_user_avatar_path(user_id: int, avatar_path: str):
    sql = "UPDATE users SET avatar_path=%s WHERE user_id=%s LIMIT 1"
    with get_db_cursor(commit=True) as cursor:
        cursor.execute(sql, (avatar_path, user_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")


def clear_user_avatar_path(user_id: int):
    sql = "UPDATE users SET avatar_path=NULL WHERE user_id=%s LIMIT 1"
    with get_db_cursor(commit=True) as cursor:
        cursor.execute(sql, (user_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")


# ============================================================


@router.post("/profile")
async def profile(
    payload: GetProfilePayload,
    current_user: dict = Depends(get_current_user),
):
    """
    取得會員資料
    規則：
    - 一般 user 只能查自己的資料
    - admin 可以查任何人的資料
    """
    if current_user["role"] != "admin" and current_user["user_id"] != payload.user_id:
        raise HTTPException(
            status_code=403, detail="You can only access your own profile"
        )
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


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordPayload,
    current_user: dict = Depends(get_current_user),
):
    """
    已登入修改密碼（與 ForgotPassword/OTP 完全分開）
    payload:
      - user_id
      - current_password
      - new_password

    流程：
    1) 查 user_password hash
    2) verify current_password
    3) 檢查新密碼規則
    4) hash new_password 後更新
    """
    """
    已登入修改密碼
    - 一般 user 只能改自己的
    - admin 也只能改自己的（避免用此 API 幫別人改密碼造成混亂）
    """
    if current_user["user_id"] != payload.user_id:
        raise HTTPException(
            status_code=403, detail="You can only change your own password"
        )

    # 0) 新密碼規則檢查（沿用統一規則）
    _validate_password_or_400(payload.new_password)

    # 避免新密碼與舊密碼相同
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")

    # 1) 先查使用者（拿到 password hash）
    select_sql = """
        SELECT user_password
        FROM users
        WHERE user_id = %s
        LIMIT 1
    """
    with get_db_cursor() as cursor:
        cursor.execute(select_sql, (payload.user_id,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2) 驗證目前密碼
    if not verify_password(payload.current_password, user["user_password"]):
        raise HTTPException(status_code=401, detail="Password incorrect")

    # 3) hash 新密碼
    new_hashed = hash_password(payload.new_password)

    # 4) 更新密碼
    update_sql = """
        UPDATE users
        SET user_password = %s
        WHERE user_id = %s
        LIMIT 1
    """
    with get_db_cursor(commit=True) as cursor:
        cursor.execute(update_sql, (new_hashed, payload.user_id))
        if cursor.rowcount == 0:
            # 理論上不太會到這，但保險起見
            raise HTTPException(status_code=404, detail="User not found")

    return {"message": "change-password ok"}


@router.put("/profile")
async def update_profile(
    payload: UpdateProfilePayload,
    current_user: dict = Depends(get_current_user),
):
    """
    更新會員基本資料
    - 一般 user 只能改自己的
    - admin 也可改自己；若未來要讓 admin 改別人，建議另外做 admin 專用 API，不要混在這支
    """
    if current_user["user_id"] != payload.user_id:
        raise HTTPException(
            status_code=403, detail="You can only update your own profile"
        )

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


# ============================================================
# 上傳/更換：POST /auth/avatar
# ============================================================
@router.post("/avatar")
async def upload_avatar(
    user_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # ✅ 先確認 user_id 存在
    with get_db_cursor() as cursor:
        cursor.execute("SELECT user_id FROM users WHERE user_id=%s LIMIT 1", (user_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "User not found")
    """
    上傳/更換大頭貼：
    - 存到 static/avatars/
    - DB 更新 users.avatar_path
    - 若舊的存在：刪舊檔（避免 static 堆垃圾）
    - 一般 user 只能上傳自己的
    - admin 若要改別人的頭貼，建議未來另開 admin API
    """
    # 1) MIME 檢查
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Only JPG/PNG/WEBP allowed")

    data = await file.read()

    # 2) 大小限制
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Avatar must be <= 2MB")

    # 3) 真圖片檢查（避免假檔）
    kind = imghdr.what(None, h=data)
    if kind not in {"jpeg", "png", "webp"}:
        raise HTTPException(status_code=400, detail="Invalid image")

    # 4) 先查舊檔路徑（存在就等等刪）
    old_path = get_user_avatar_path(user_id)

    # 5) 存新檔
    ext = ALLOWED_MIME[file.content_type]
    filename = f"user_{user_id}_{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(AVATAR_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(data)

    avatar_path = f"/static/avatars/{filename}"

    # 6) DB 更新成新路徑
    set_user_avatar_path(user_id, avatar_path)

    # 7) 刪舊檔（刪檔失敗也不要讓 API 整個 500）
    if old_path:
        try:
            old_fs_path = "." + old_path  # "/static/.." -> "./static/.."
            if os.path.exists(old_fs_path):
                os.remove(old_fs_path)
        except Exception:
            pass

    return {"message": "avatar updated", "avatar_path": avatar_path}


# ============================================================
# 取得可用 URL：GET /auth/avatar-url
# ============================================================
@router.get("/avatar-url")
def get_avatar_url(
    request: Request,
    user_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    取得頭貼 URL
    - 一般 user 只能查自己的
    - admin 可查任何人的（方便後台）
    前端顯示用：回傳完整 URL
    - 如果沒頭貼：回傳空字串
    """
    if current_user["role"] != "admin" and current_user["user_id"] != user_id:
        raise HTTPException(
            status_code=403, detail="You can only access your own avatar"
        )

    avatar_path = get_user_avatar_path(user_id)
    if not avatar_path:
        return {"url": ""}

    base = str(request.base_url).rstrip("/")
    return {"url": f"{base}{avatar_path}"}


# ============================================================
# 刪除：DELETE /auth/avatar
# ============================================================
@router.delete("/avatar")
def delete_avatar(
    user_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    移除大頭貼：
    - 一般 user 只能刪自己的
    - 刪檔
    - DB 清空 avatar_path
    """
    if current_user["user_id"] != user_id:
        raise HTTPException(
            status_code=403, detail="You can only delete your own avatar"
        )

    avatar_path = get_user_avatar_path(user_id)
    if avatar_path:
        fs_path = "." + avatar_path
        if os.path.exists(fs_path):
            os.remove(fs_path)

    clear_user_avatar_path(user_id)
    return {"message": "avatar removed"}
