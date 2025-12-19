# 🚀 團隊開發 Git 指令懶人包

為了確保大家開發順利，請遵守以下流程：

1. 每天開工前：同步最新進度

開發前先確保你的本地 `develop` 分支是最新的。

    git checkout develop
    git pull origin develop

2. 開發新功能：建立分支

禁止直接在 `develop` 或 `main` 分支開發。請根據功能建立新分支：

    # 格式：feature/功能名稱
    git checkout -b feature/login-page

3. 開發中：頻繁提交 (Commit)

當你完成一個小階段（例如寫好一個 function 或刻好一個元件）：

    git add .
    git commit -m "feat: 完成登入 API 串接"

&emsp; Commit 訊息規範：

&emsp; * `feat`: 新功能

&emsp; * `fix`: 修補 Bug

&emsp; * `style`: 修改 UI 樣式 (不影響邏輯)

&emsp; * `docs`: 修改文件

4. 完工後：上傳並發起合併請求 (PR)

將你的功能分支推送到 GitHub：

`git push origin feature/login-page`

接下來的操作：
* 前往 GitHub 頁面。
* 點擊 "Compare & pull request"。
* Base 選擇 `develop`，Compare 選擇你的分支。
* 標記一位隊友(Reviewer) 幫你檢查 Code。

5. 遇到衝突 (Conflict) 怎麼辦？

如果 PR 顯示有衝突，請在本地執行：

    git checkout develop
    git pull origin develop
    git checkout feature/your-branch
    git merge develop

在 VS Code 中解決衝突標記後：

    git add .
    git commit -m "chore: 解決合併衝突"
    git push origin feature/your-branch

***💡 小提醒***
* 不要隨便使用 `git push -f` (強推)，這會覆蓋掉隊友的 Code。

