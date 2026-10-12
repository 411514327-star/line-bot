# 群組相簿 LINE Bot

把 LINE 群組變成朋友的共享相簿：大家在群組傳照片，Bot 自動存下來；輸入「回顧」就能用輪播卡片看最近幾天的照片。
靈感來自 Retro（Photos with Friends）「小圈子、低壓力地分享生活照」的概念。

> 本專案是課程作業「LINE Bot 改善版」。第一版沒有上傳 GitHub，因此先重建基準版本，再做兩輪改善，過程詳見 [開發紀錄](docs/index.html)。

## 功能

| 指令／行為 | 說明 |
|---|---|
| 在群組傳照片 | Bot 下載並儲存，回覆「照片已成功儲存到群組相簿！」 |
| `說明` | 顯示使用說明與指令範例 |
| `回顧` | 以 Flex Message 輪播顯示最近 7 天的照片（每張附上傳時間） |
| `回顧 N` | 顯示最近 N 天的照片，例如 `回顧 3`、`回顧 14` |
| 輸入錯誤 | `回顧 abc`、`回顧 0` 會提示正確格式；不認識的文字會提示輸入「說明」 |
| 不支援的訊息 | 貼圖等非文字、非照片的訊息會提示目前支援的功能 |
| 私聊使用 | 相簿功能只支援群組，私聊會提示「請將我加入群組」 |
| 錯誤處理 | 照片下載或存檔失敗時會回覆提示；同一則訊息被 LINE 重送時不會重複寫入；`BASE_URL` 不是 https 時啟動會印出警告 |

## 使用技術

- Python、FastAPI、uvicorn
- line-bot-sdk（LINE Messaging API）
- SQLite（`album.db`）儲存照片紀錄，照片檔存在 `static/photos/`
- python-dotenv 讀取環境變數
- cloudflared（Cloudflare quick tunnel）讓本機伺服器有公開 https 網址，供 LINE 呼叫 Webhook 與顯示圖片

## 安裝與啟動

1. 安裝 Python 3.10 以上。
2. 下載專案後，在專案資料夾安裝套件：
   ```
   python -m pip install -r requirements.txt
   ```
3. 複製 `.env.example` 為 `.env`，填入自己的設定（變數名稱以 `.env.example` 為準）：
   - LINE Channel secret
   - LINE Channel access token
   - `BASE_URL`：公開的 https 網址，**結尾不要加斜線**
4. 啟動伺服器（預設埠號 8000）：
   ```
   python main.py
   ```
5. 另開一個終端機，建立公開網址：
   ```
   cloudflared tunnel --url http://localhost:8000
   ```
   取得 `https://xxxx.trycloudflare.com` 後：
   - 把它填進 `.env` 的 `BASE_URL`，並重新啟動伺服器。
   - 到 LINE Developers Console 的 Messaging API 頁，把 Webhook URL 設為 `https://xxxx.trycloudflare.com/callback`，按「核實」確認成功，並開啟「使用 Webhook」。
6. 在 LINE Official Account Manager 開啟「允許帳號加入群組和多人聊天室」，把 Bot 加進群組。

> 免費的 quick tunnel 網址每次啟動都會改變，網址改了就要重做第 5 步。

## 使用方式

1. 把 Bot 加進群組。
2. 在群組直接傳照片，Bot 會回覆已儲存。
3. 輸入 `回顧` 或 `回顧 3` 查看照片輪播。
4. 不確定怎麼用時，輸入 `說明`。

## 專案結構

```
main.py             主程式（Webhook、指令處理、資料庫）
requirements.txt    套件清單
.env.example        環境變數範本（不含真正金鑰）
.gitignore          排除 .env、照片、資料庫
docs/               計畫書、測試紀錄、開發紀錄網頁與截圖
```

`.env`、`album.db`、`static/photos/` 不會上傳到 GitHub。

## 已知限制

- 免費 tunnel 沒有穩定性保證，網址每次重開都會變；正式使用需要固定網址的雲端部署。
- 照片存在本機資料夾，沒有備份，也沒有雲端儲存。
- 不依使用者區分權限，群組內每個人都能看全部照片。
- 一則訊息裡含多行文字，會被當成同一個指令，不會逐行處理。
- 目前所有測試照片都是同一天上傳，因此「依天數過濾掉較舊照片」尚未在實機上驗證。
- 「照片下載失敗的提示」和「LINE 重送訊息時不重複寫入」兩項只做了程式修改，無法在 LINE 上人為製造情境，未實測。
- 影片、語音等訊息類型未逐一測試，目前只實測貼圖。
- 沒有排程推播、月回顧、Rich Menu 等功能，列為未來擴充。
- `main.py` 的 `callback` 函式偏長，尚未拆分成多個處理函式。

## 開發與 AI 工具

- 計畫與文件草稿：Claude
- 第一版基準版本與第二版改善：Antigravity
- 第二版之後的錯誤處理修正：OpenCode（使用其內建的免費模型）

測試結果見 [docs/test-log.md](docs/test-log.md)，完整過程見 [開發紀錄網頁](docs/index.html)。
