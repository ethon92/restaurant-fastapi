import os
import pymysql
from contextlib import contextmanager
from dotenv import load_dotenv

#載入環境變數
load_dotenv()

#資料庫連線設定
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'charset': os.getenv('DB_CHARSET'),
    'cursorclass': pymysql.cursors.DictCursor # 用字典游標
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
        # 如果commit為true時
        if commit:
            connection.commit()
    # 錯誤發生時，發出通知
    except Exception as e:
        connection.rollback()
        raise e
    # 最後關閉連線
    finally:
        cursor.close()
        connection.close()