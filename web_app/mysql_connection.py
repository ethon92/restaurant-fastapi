import os
import pymysql
from contextlib import contextmanager
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 取得目前檔案所在的資料夾路徑，用於定位 SSL 憑證
base_path = os.path.dirname(os.path.abspath(__file__))

# 資料庫連線設定
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    # 修改點：預設值改成數字 3306，確保 int() 轉換不會失敗
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),  # 建議給 charset 一個預設值
    "cursorclass": pymysql.cursors.DictCursor,
    "ssl": {"ca": os.getenv("TIDB_CA_PATH", os.path.join(base_path, "isrgrootx1.pem"))},
}


# 資料庫連線
def get_db_connection():
    return pymysql.connect(**DB_CONFIG)


@contextmanager
def get_db_cursor(commit=False):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        yield cursor
        if commit:
            connection.commit()
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        cursor.close()
        connection.close()
