# LINE 群組相簿 Bot（改善版）

這是一個基於 **FastAPI** 與 **LINE Messaging API SDK v3** 開發的智慧群組相簿機器人。群組成員傳送的照片會自動安全存檔，並可透過 Flex Carousel 輪播卡片隨時回顧近期照片。本專案經歷了「第一版基準」至「改善版」的演進，具備完整的指令防呆、不支援訊息引導與聊天場景安全防護機制。

---

## 🌟 功能特點

1. 📸 **群組相片自動收集存檔**：
   - 在群組中發送相片時，透過 LINE Blob API 下載圖片本機保存，並以 SQLite 資料庫關聯群組 ID 與時間戳記。
2. 🎠 **彈性相簿回顧輪播（Flex Carousel）**：
   - 輸入 `回顧`：預設查詢最近 7 天內的相片，組裝為互動式輪播卡片。
   - 輸入 `回顧 <天數>`（如 `回顧 3`、`回顧 14`）：動態查詢指定天數內的相片，點擊圖片可直接開啟原圖。
3. 🛡️ **健全的輸入防呆與格式檢查**：
   - **空白訊息防護**：過濾純空格與無效空白，提供指令引導。
   - **格式錯誤提示**：輸入無效參數（如 `回顧 abc`、`回顧 0`）時，主動告知須輸入數字並附上正確範例。
4. 💡 **不支援訊息友善引導**：
   - 收到貼圖、語音、影片、位置或無法辨識的文字時，不再已讀不回或盲目 Echo，而是主動提示支援範圍並引導輸入「說明」。
5. 🔒 **聊天場景防護（群組限定）**：
   - 相簿核心功能（傳照片、相簿回顧）僅限群組使用；於一對一私聊操作時，溫和提示使用者將機器人加入群組。

---

## 📁 專案檔案架構

```text
0921 case/
├── .venv/               # Python 虛擬環境
├── docs/
│   ├── project-plan.md  # 專題計畫書
│   ├── test-log.md      # 測試紀錄表（含改善前後對照與實測結果）
│   └── screenshots/     # 實機測試對話截圖清單
├── static/
│   └── photos/          # 本地暫存相片存放目錄（由 .gitignore 忽略實際檔案）
├── .env                 # LINE 憑證與環境變數（機密金鑰，不納入版本控制）
├── .env.example         # 環境變數設定範本（僅包含佔位符）
├── .gitignore           # Git 忽略設定
├── main.py              # FastAPI 主程式、LINE Webhook 與核心商業邏輯
├── requirements.txt     # Python 依賴套件清單
└── README.md            # 專案說明文件
```

---

## 🚀 快速上手與設定方式

### 第一步：申請 LINE Developers 憑證
1. 登入 [LINE Developers Console](https://developers.line.biz/console/)。
2. 建立 Provider 並建立 **Messaging API** Channel。
3. 取得兩組金鑰：
   - **Channel Secret**（位於 `Basic settings` 標籤分頁下方）。
   - **Channel Access Token**（切換到 `Messaging API` 標籤分頁最下方點擊 `Issue` 發行）。
4. **關閉官方預設自動回覆**（避免回覆衝突）：
   - 在 LINE Official Account 後台將「自動回應訊息」設為 **關閉**，將「Webhook」設為 **開啟**。
   - 開啟「允許加入群組/多人聊天室」。

---

### 第二步：設定專案環境變數
複製 `.env.example` 為 `.env`，並填入您的金鑰與穿透網址：
```env
# LINE Messaging API Credentials
LINE_CHANNEL_SECRET=你的_LINE_CHANNEL_SECRET
LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_CHANNEL_ACCESS_TOKEN
PORT=8000

# 公開穿透網址（Cloudflare Tunnel 或 ngrok，結尾不要加斜線）
BASE_URL=https://your-tunnel-subdomain.trycloudflare.com
```

> ⚠️ **資安注意**：`.env` 包含真實機密金鑰，已由 `.gitignore` 嚴密隔離，請勿提交至 GitHub！

---

### 第三步：安裝依賴並啟動伺服器
在專案根目錄終端機執行：
```powershell
# 啟動虛擬環境並執行服務
.\.venv\Scripts\python.exe main.py
```
啟動後可開啟瀏覽器存取 `http://127.0.0.1:8000/`，確認狀態為：
```json
{
  "status": "online",
  "service": "LINE Group Album Bot (v2 改善版)",
  "configured": true,
  "base_url": "https://your-tunnel-subdomain.trycloudflare.com"
}
```

---

### 第四步：設定公開 HTTPS 網址 (Webhook)
LINE 要求 Webhook 必須為公開 HTTPS 網址，可使用 **Cloudflare Tunnel** 或 **ngrok**：

- **使用 Cloudflare Tunnel**：
  ```bash
  cloudflared tunnel --url http://localhost:8000
  ```
- **使用 ngrok**：
  ```bash
  ngrok http 8000
  ```

將產生的 HTTPS 網址加上 `/callback`（例如：`https://xxxx.trycloudflare.com/callback`），填入 LINE Developers 後台的 **Webhook URL** 並點擊 **Verify** 確認連線成功。

---

## 💬 使用方法與指令範例

將機器人邀請至 LINE 群組中即可開始使用：

| 操作情境 | 輸入內容 | 機器人回應 |
| :--- | :--- | :--- |
| **儲存照片** | 在群組中發送照片 | `📸 照片已成功儲存到群組相簿！` |
| **預設回顧** | `回顧` | 回傳該群組最近 7 天內的照片輪播卡片（Flex Carousel） |
| **自訂天數回顧** | `回顧 3` 或 `回顧 14` | 回傳該群組最近指定天數（3天/14天）的照片輪播卡片 |
| **查看功能說明** | `說明` | 顯示包含相簿儲存、回顧天數等完整操作指南 |
| **格式錯誤示範** | `回顧 abc` 或 `回顧 0` | `⚠️ 請輸入有效的天數數字！💡 指令範例：回顧 3...` |
| **不支援訊息** | 發送貼圖 / 影片 / 語音 | `⚠️ 目前僅支援儲存照片與相簿指令，不支援此類型的訊息。💡 請輸入「說明」...` |
| **未知文字指令** | 輸入 `哈囉` 或任意文字 | `⚠️ 無法辨識指令「哈囉」。💡 請輸入「說明」查看支援的功能...` |
| **私聊傳照片** | 於一對一聊天視窗傳照片 | `⚠️ 本相簿功能僅支援在群組中使用，請將我加入群組後再傳送照片喔！` |
| **私聊輸入回顧** | 於一對一聊天視窗輸入 `回顧` | `⚠️ 「回顧」功能僅支援在群組中使用，請將我加入群組後再試喔！` |

---

## 📊 改善前後對比 (Before vs After)

| 評估面向 | 改善前（v1 基準版 / Commit 1） | 改善後（v2 改善版 / Commit 2） |
| :--- | :--- | :--- |
| **回顧天數** | 固定 7 天，輸入 `回顧 3` 被當作一般文字 Echo | 支援動態解析天數（`回顧 3`），預設 7 天 |
| **參數檢查** | 輸入 `回顧 abc` 無提示，直接 Echo 使用者輸入 | 嚴格防呆校驗，主動提示需輸入有效數字與範例 |
| **非文字/貼圖** | 傳送貼圖、影片、語音完全無回應（已讀不回） | 主動告知不支援該格式，並引導使用者輸入「說明」 |
| **未知指令** | 單純 Echo 重複輸入之字串 | 明確提示無法辨識，並引導查詢「說明」選單 |
| **聊天室來源** | 一對一私聊與群組未區分，私聊亦會存入相簿 | 嚴格限制於群組使用，私聊時溫和提示加入群組 |

---

## ⚠️ 已知限制

1. **公開圖片網址需求**：
   - LINE Flex Message Carousel 渲染圖片需仰賴可公開訪問的 HTTPS 網址。在本機開發環境下，若關閉穿透通道（Tunnel）或網址重設，需同步更新 `.env` 中的 `BASE_URL`。
2. **LINE Flex 輪播卡片上限**：
   - LINE Messaging API 之 Carousel Container 單則訊息最多支援呈現 10~12 張 Bubble 卡片；若該天數範圍照片超過 10 張，系統將優先取最新 10 張進行輪播展示。
3. **客戶端純空白輸入限制**：
   - LINE App 行動端介面在文字框全為空格時，發送按鈕預設為停用（灰底不可按），故無法由標準 LINE App 送出純空格訊息（後端仍具備防禦機制）。
4. **一對一相簿存取限制**：
   - 本 Bot 專為群組活動設計，個人聊天室不開放存檔與照片回顧功能。
