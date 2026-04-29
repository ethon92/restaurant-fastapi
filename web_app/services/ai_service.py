import os
import pymysql
from snownlp import SnowNLP
from opencc import OpenCC
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 初始化繁轉簡工具
cc = OpenCC('t2s') 

def analyze_all_comments_with_snow():
    # 1. 取得雲端資料庫設定
    # 這裡確保抓取的名稱與你 .env 檔案中的一致
    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    db_port = int(os.getenv("DB_PORT", 4000))
    ca_path = os.getenv("TIDB_CA_PATH") # 這是剛才測試成功的路徑

    # 2. 連線至 TiDB Cloud
    try:
        db = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor, # 使用 DictCursor 比較好讀取欄位
            ssl={'ca': ca_path} # TiDB 強制需要的 SSL 設定
        )
        cursor = db.cursor()
        print("✅ 成功連線至雲端資料庫，開始分析...")

        # 3. 抓取未分析的評論
        # 這裡的欄位名稱請對照你剛剛匯入的表 (sentiment 與 tags)
        # 如果欄位叫 sentiment_score，請自行調整 SQL
        cursor.execute("SELECT comment_id, comment_content FROM comments WHERE sentiment IS NULL")
        rows = cursor.fetchall()
        print(f"⏳ 找到 {len(rows)} 筆待分析資料...")

        for row in rows:
            cid = row['comment_id']
            content = row['comment_content']
            
            if not content: continue
            
            try:
                # 4. 轉簡體並分析
                s = SnowNLP(cc.convert(content))
                
                # s.sentiments 回傳 0~1 (1 正面, 0 負面)
                score = round(s.sentiments, 2)
                
                # SnowNLP 的關鍵字提取 (s.keywords)
                # 轉回繁體存入 tags（選用）
                keywords = s.keywords(3)
                tags = ",".join(keywords) 

                # 5. 回填資料庫 (更新欄位 sentiment 與 tags)
                # 注意：如果你的 tags 欄位是 JSON 型態，建議轉成 JSON 字串或維持逗號字串
                cursor.execute(
                    "UPDATE comments SET sentiment = %s, tags = %s WHERE comment_id = %s",
                    (str(score), tags, cid)
                )
            except Exception as inner_e:
                print(f"⚠️ 評論 ID {cid} 分析跳過: {inner_e}")
                continue
        
        db.commit()
        print(f"🎉 成功分析並回填 {len(rows)} 筆資料！")
        
    except Exception as e:
        print(f"❌ 雲端分析失敗: {e}")
        return 0
    finally:
        if 'db' in locals():
            db.close()
            
    return len(rows)

if __name__ == "__main__":
    analyze_all_comments_with_snow()