import hashlib
import os

PWD_SALT = os.getenv("PWD_SALT", "dev_salt_change_me")  # 開發用預設值，上線務必改 env


def hash_password(raw: str) -> str:
    """sha256(raw + salt)"""
    return hashlib.sha256((raw + PWD_SALT).encode("utf-8")).hexdigest()


def verify_password(raw: str, hashed: str) -> bool:
    """compare raw password with hashed"""
    return hash_password(raw) == hashed
