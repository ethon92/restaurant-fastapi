import pandas as pd
import random
import os

# 設定檔案路徑
csv_path = 'Restaurant_Final_Polished.csv'

# 1. 讀取原本的 CSV
if not os.path.exists(csv_path):
    print(f"❌ 找不到 {csv_path}，請確認檔案位置！")
    exit()

df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
print(f"📄 讀取成功，目前有 {len(df)} 筆資料")

# 2. 定義產生價格的函式
def get_price_info(row):
    # 隨機決定等級：40%便宜, 40%中等, 20%貴
    rand = random.random()
    if rand < 0.4:
        return '$', random.randint(100, 400)      # 平價
    elif rand < 0.8:
        return '$$', random.randint(401, 1000)    # 中價位
    else:
        return '$$$', random.randint(1001, 3000)  # 高價位

# 3. 應用到每一列
print("💰 正在計算價格...")
# zip(*...) 是 Python 的解壓縮技巧，把回傳的兩個值分別塞給兩個欄位
df['PriceLevel'], df['AvgPrice'] = zip(*df.apply(get_price_info, axis=1))

# 4. 存檔 (直接覆蓋原檔)
df.to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"✅ 成功！已將價格寫入 {csv_path}")
print("   (不用擔心，這只改了 CSV 文字，你的圖片檔案都很安全)")