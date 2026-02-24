# 🍴 餐廳預約系統後端 (Restaurant Reservation FastApi)

這是一個基於 **FastAPI** 構建的高效能餐廳預約系統後端，負責處理從會員驗證、餐廳數據檢索到自動化郵件通知的核心業務邏輯。

## 🚀 核心功能

### 🔐 會員與認證管理

* **身份驗證系統**：實作註冊、登入與登出流程。
* **安全機制**：使用 SHA256 搭配 Salt (鹽值) 進行密碼雜湊儲存，確保使用者資料安全。
* **帳號恢復**：整合 SMTP 服務發送電子郵件驗證碼 (OTP)，支援忘記密碼與重設密碼功能。
* **個人資料管理**：支援查看帳號總覽、修改個人資料與更新密碼。

### 🍽️ 餐廳搜尋與地圖服務

* **多維度搜尋**：支援透過關鍵字、城市、價格等級及特定主題標籤（如：下午茶、約會）進行篩選。
* **地圖 API 整合**：提供經緯度範圍搜尋（Bounds Search），支援前端 Leaflet 的標記聚合功能。
* **詳細資訊展示**：提供餐廳環境、營業資訊及評分數據。

### 📅 預約與互動功能

* **線上預約系統**：實作完整的訂位流程，包含時段衝突檢查（防止重複預約）與預約紀錄查詢。
* **收藏系統**：使用者可收藏心儀餐廳並撰寫個人備註。
* **評論系統**：支援 CRUD 評論操作，讓使用者分享真實餐飲體驗。

---

## 🛠️ 技術堆疊 (Technical Stack)

### 核心框架與工具

* **FastAPI**：高效能的 Python Web 框架，利用非同步 (Asynchronous) 特性處理高併發請求。
* **SQLAlchemy**：強大的 SQL 工具包與 ORM 模型，負責資料庫結構定義與互動。
* **Pydantic**：用於資料驗證與設定管理，確保 API 輸入輸出的正確性。
* **Uvicorn**：作為 ASGI 伺服器，負責執行 FastAPI 應用程式。

### 資料庫與數據分析

* **PyMySQL**：純 Python 實作的 MySQL 驅動程式。
* **Pandas**：用於後端數據清理與複雜的餐廳資料處理。

### 安全與通訊

* **Cryptography**：提供底層加密演算法支援。
* **SMTPLIB**：整合電子郵件發送功能，處理 OTP 驗證碼郵件。
* **Python-Dotenv**：管理環境變數（如資料庫連線字串、金鑰等），提升部署安全性。

---

## 📂 專案結構說明

* `main.py`: 應用程式進入點、CORS 設定及路由註冊。
* `routes/`: 定義 API 端點（Auth, Account, Restaurant, Feature）。
* `services/`: 封裝核心業務邏輯，例如餐廳搜尋演算法。
* `models/`: 定義資料庫 Schema 與 Pydantic 驗證模型。
* `utils/`: 存放安全性加密 (Security) 與郵件工具 (Email Utils)。

---

## 💻 快速開始

### 環境需求

* **Python**: 3.12+
* **資料庫**: MySQL

### 安裝與啟動

1. **安裝依賴套件**：
```bash
pip install fastapi[all] sqlalchemy pymysql pandas cryptography python-dotenv

```


2. **配置環境變數**：
在根目錄建立 `.env` 檔案並填入資料庫連線、SMTP 設定與 PWD_SALT。
3. **啟動開發伺服器**：
```bash
uvicorn main:app --reload

```


4. **API 文檔**：
啟動後訪問 `http://127.0.0.1:8000/docs` 即可查看 Swagger UI 自動生成的互動式文檔。