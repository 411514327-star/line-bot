# LINE Bot (FastAPI + Python)

這是一個使用 **FastAPI** 與 **LINE Messaging API SDK v3** 開發的 LINE 機器人。

---

## 🌟 功能特點
- ⚡ **高效非同步架構**：採用 FastAPI + Uvicorn
- 🛡️ **簽名驗證安全機制**：自動驗證 LINE 的 `X-Line-Signature`，防止偽造請求
- 🤖 **智慧指令回覆**：
  - 輸入 `說明` 或 `help`：顯示功能選單
  - 輸入 `你好` 或 `hi`：親切問候
  - 輸入 `BMI 175 68`：自動計算 BMI、體位分析並給予健康建議
  - 其他文字：Echo 重複訊息（方便快速測試）
- 🔌 **易於擴展**：可隨時串接 OpenAI / Google Gemini AI 模型

---

## 📁 專案檔案架構
```text
0921 case/
├── .venv/               # Python 虛擬環境
├── main.py              # FastAPI 主程式與 Webhook 邏輯
├── requirements.txt     # 依賴套件清單
├── .env                 # LINE 憑證與設定（包含金鑰，不外流）
├── .env.example         # 設定範本
└── README.md            # 專案說明文件
```

---

## 🚀 快速上手步驟

### 第一步：申請 LINE Developers 憑證
1. 前往 [LINE Developers Console](https://developers.line.biz/console/) 並使用 LINE 帳號登入。
2. 建立 **Provider（提供者）**（例如：`MyBotProvider`）。
3. 在 Provider 內點擊 **Create a new channel**，選擇 **Messaging API**。
4. 填寫機器人基本資訊（名稱、簡介、分類等）並確認建立。
5. 取得以下兩組金鑰：
   - **Channel Secret**：位於 `Basic settings` 標籤分頁下方。
   - **Channel Access Token**：切換到 `Messaging API` 標籤分頁最下方，點擊 `Issue`（發行）。
6. **關閉官方預設自動回覆**（非常重要，避免 LINE 自行回覆與 Webhook 衝突）：
   - 在 `Messaging API` 頁面的 **Auto-reply messages** 點擊 `Edit`。
   - 進入 LINE Official Account 後台將「自動回應訊息」設為 **關閉**，並將「Webhook」設為 **開啟**。

---

### 第二步：設定專案金鑰
打開專案目錄中的 [`.env`](file:///c:/Users/User/Documents/0921%20case/.env)，將剛才取得的金鑰填入：
```env
LINE_CHANNEL_SECRET=你的Channel_Secret
LINE_CHANNEL_ACCESS_TOKEN=你的Channel_Access_Token
PORT=8000
```

---

### 第三步：啟動本機伺服器
在終端機中執行：
```bash
.venv\Scripts\python main.py
```
或使用 uvicorn：
```bash
.venv\Scripts\uvicorn main:app --reload --port 8000
```
啟動後可以在瀏覽器打開 `http://127.0.0.1:8000` 確認狀態顯示為 `online`。

---

### 第四步：設定公開 HTTPS 網址 (Webhook)
LINE 伺服器要求 Webhook 網址必須具備有效的 **HTTPS**。本機開發時可以使用 `ngrok`：

1. 安裝 ngrok（可直接透過 Windows winget）：
   ```powershell
   winget install ngrok.ngrok
   ```
2. 啟動穿透通道：
   ```bash
   ngrok http 8000
   ```
3. 複製 ngrok 產生的 `https://xxxx.ngrok-free.app` 網址。
4. 回到 LINE Developers Console 的 **Messaging API** 分頁：
   - 找到 **Webhook URL** 點擊 Edit。
   - 填入：`https://xxxx.ngrok-free.app/callback`
   - 點擊 **Update**，並開啟 **Use webhook**。
   - 點擊 **Verify** 測試連線（顯示 Success 即代表成功！）。

---

### 第五步：加入好友測試
在 LINE Developers 的 **Messaging API** 頁面上方掃描 QR Code 加入機器人好友，傳送訊息測試：
- 輸入：`說明`
- 輸入：`BMI 175 70`
- 輸入：`你好`
