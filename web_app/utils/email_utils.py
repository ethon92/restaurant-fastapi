"""
email_utils.py
只負責：寄信（SMTP）/ email 相關工具

特色：
- 支援 .env（若有安裝 python-dotenv）
- 支援 Gmail SMTP: smtp.gmail.com:587 + STARTTLS
- 寄 OTP 信件（HTML + 純文字備援）
- 發送成功回 True，失敗會 raise Exception（由呼叫端統一處理）
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import cast


logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Optional: load .env if python-dotenv is installed
# （不確定有沒有裝，所以用 try/except 保護）
# ------------------------------------------------------------
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    # 沒裝 python-dotenv 也沒關係，照樣可用系統環境變數
    pass


# ------------------------------------------------------------
# SMTP config
# 支援兩種命名：SMTP_PASSWORD / SMTP_PASS
# ------------------------------------------------------------
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")

SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "DINE 享樂 Restaurant Booking")


def _require_smtp_config():
    """檢查 SMTP 設定是否齊全，避免「看似寄了但其實沒寄」"""
    if not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError("SMTP_USER / SMTP_PASSWORD not configured")


def send_otp_email(receiver_email: str, otp_code: str, ttl_seconds: int = 300) -> bool:
    """
    寄送 OTP 驗證碼郵件

    Args:
        receiver_email: 收件者信箱
        otp_code: 6 位數驗證碼
        ttl_seconds: OTP 有效時間（秒），預設 300 秒 = 5 分鐘

    Returns:
        True if sent successfully

    Raises:
        Exception if sending fails
    """
    _require_smtp_config()

    #  讓型別工具知道這兩個一定是 str
    smtp_user = cast(str, SMTP_USER)
    smtp_pass = cast(str, SMTP_PASSWORD)

    # 1) 組信件主體
    subject = "【DINE 享樂 Restaurant Booking】忘記密碼驗證碼（OTP）"
    ttl_minutes = max(1, ttl_seconds // 60)

    # 純文字備援：某些信箱/安全性設定會偏好 text/plain
    text_body = (
        "您好，\n\n"
        "我們收到了您重設密碼的請求。\n"
        f"您的驗證碼為：{otp_code}\n"
        f"有效時間：{ttl_minutes} 分鐘\n\n"
        "若非本人操作，請忽略此信。\n"
        "—— DINE 享樂 Restaurant Booking\n"
    )

    # HTML：簡單乾淨、偏餐廳/訂位服務風格（可之後統一）
    html_body = f"""
    <html>
      <body style="margin:0;padding:0;background:#f6f7fb;font-family:system-ui,-apple-system,Segoe UI,Roboto,Noto Sans TC,Arial;">
        <div style="max-width:560px;margin:0 auto;padding:24px;">
          <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;">
            <div style="padding:18px 20px;background:#111827;color:#fff;">
              <div style="font-size:14px;opacity:.9;">DINE 享樂 Restaurant Booking</div>
              <div style="font-size:20px;font-weight:800;margin-top:6px;">忘記密碼驗證碼</div>
            </div>

            <div style="padding:20px;color:#111827;">
              <p style="margin:0 0 12px;line-height:1.7;">
                您好，我們收到了重設密碼的請求。請在網頁上輸入以下驗證碼以繼續：
              </p>

              <div style="margin:16px 0;padding:14px 16px;border:1px dashed #cbd5e1;border-radius:12px;background:#f8fafc;text-align:center;">
                <div style="font-size:12px;color:#64748b;letter-spacing:.08em;">OTP CODE</div>
                <div style="font-size:34px;font-weight:900;letter-spacing:8px;color:#0f172a;margin-top:4px;">
                  {otp_code}
                </div>
              </div>

              <p style="margin:0;line-height:1.7;color:#334155;">
                此驗證碼將於 <b>{ttl_minutes} 分鐘</b>後過期。若您未申請重設密碼，請直接忽略本信件。
              </p>

              <hr style="border:0;border-top:1px solid #e5e7eb;margin:18px 0;" />

              <p style="margin:0;color:#64748b;font-size:12px;line-height:1.6;">
                為了保護您的帳戶安全，我們不會以電話或簡訊向您索取密碼與驗證碼。
              </p>
            </div>

            <div style="padding:14px 20px;background:#f9fafb;color:#6b7280;font-size:12px;">
              這封信由系統自動寄出，請勿直接回覆。<br />
              © DINE 享樂 Restaurant Booking
            </div>
          </div>
        </div>
      </body>
    </html>
    """

    # 2) MIME 組裝：同時放 plain + html（收件端自行選較佳版本）
    message = MIMEMultipart("alternative")
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    message["To"] = receiver_email
    message["Subject"] = subject

    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    # 3) SMTP 發送（587 + STARTTLS）
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [receiver_email], message.as_string())

        logger.info("✅ OTP email sent to %s", receiver_email)
        return True

    except Exception as e:
        logger.exception("❌ Failed to send OTP email: %s", e)
        raise
