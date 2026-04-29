from snownlp import SnowNLP
from opencc import OpenCC
import pymysql

# 初始化繁轉簡工具
cc = OpenCC('t2s') 

def analyze_all_comments_with_snow():
    # 1. 使用你原本的連線設定
    db = pymysql.connect(
        host="127.0.0.1", user="root", password="P@ssw0rd",
        database="restaurantdata", charset='utf8mb4'
    )
    cursor = db.cursor()

    # 2. 抓取未分析的評論
    cursor.execute("SELECT comment_id, comment_content FROM comments WHERE sentiment_score IS NULL")
    rows = cursor.fetchall()

    for cid, content in rows:
        if not content: continue
        
        # 3. 轉簡體並分析
        s = SnowNLP(cc.convert(content))
        
        # s.sentiments 會回傳 0~1 之間的分數 (1 為正面，0 為負面)
        score = round(s.sentiments, 2)
        
        # SnowNLP 的關鍵字提取功能 (s.keywords)
        tags = ",".join(s.keywords(3)) 

        # 4. 回填資料庫
        cursor.execute(
            "UPDATE comments SET sentiment_score = %s, tags = %s WHERE comment_id = %s",
            (score, tags, cid)
        )
    
    db.commit()
    db.close()
    return len(rows)