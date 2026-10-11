import os
import sys
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent
)

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables
load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

# SQLite & Directory Setup
DB_PATH = "album.db"
PHOTOS_DIR = os.path.join("static", "photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)


def init_db():
    """Initialize database for storing photo metadata."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        conn.commit()


init_db()


def save_photo_record(group_id: str, message_id: str, file_name: str, created_at: datetime = None):
    if created_at is None:
        created_at = datetime.now()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO photos (group_id, message_id, file_name, created_at) VALUES (?, ?, ?, ?)",
            (group_id, message_id, file_name, created_at.isoformat())
        )
        conn.commit()


def get_photos(group_id: str, days: int = 7):
    cutoff = datetime.now() - timedelta(days=days)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_name, created_at FROM photos WHERE group_id = ? AND created_at >= ? ORDER BY created_at DESC",
            (group_id, cutoff.isoformat())
        )
        return cursor.fetchall()


def get_source_id(source) -> str:
    """Retrieve group_id, room_id, or user_id as partition key."""
    if getattr(source, "group_id", None):
        return source.group_id
    if getattr(source, "room_id", None):
        return source.room_id
    if getattr(source, "user_id", None):
        return source.user_id
    return "default_group"


def build_review_carousel(photos: list, base_url: str) -> FlexMessage:
    """Build Flex Message Carousel containing recent photos."""
    bubbles = []
    # Up to 10 photos in carousel
    for file_name, created_at_str in photos[:10]:
        img_url = f"{base_url}/static/photos/{file_name}"
        try:
            dt = datetime.fromisoformat(created_at_str)
            dt_display = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            dt_display = created_at_str[:16]

        bubble = {
            "type": "bubble",
            "hero": {
                "type": "image",
                "url": img_url,
                "size": "full",
                "aspectRatio": "4:3",
                "aspectMode": "cover",
                "action": {
                    "type": "uri",
                    "label": "查看原圖",
                    "uri": img_url
                }
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"📅 {dt_display}",
                        "weight": "bold",
                        "size": "sm",
                        "color": "#333333",
                        "align": "center"
                    }
                ],
                "paddingAll": "10px"
            }
        }
        bubbles.append(bubble)

    carousel_dict = {
        "type": "carousel",
        "contents": bubbles
    }
    return FlexMessage(
        alt_text="📸 群組照片回顧",
        contents=FlexContainer.from_dict(carousel_dict)
    )


app = FastAPI(title="LINE Group Album Bot")

# Mount static folder for serving photos
app.mount("/static", StaticFiles(directory="static"), name="static")

handler = None
configuration = None

if LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN:
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
    configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
else:
    print("[WARNING] LINE_CHANNEL_SECRET or LINE_CHANNEL_ACCESS_TOKEN is not set.")


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "LINE Group Album Bot (v1 基準版)",
        "configured": bool(LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN),
        "base_url": os.getenv("BASE_URL", "")
    }


@app.post("/callback")
async def callback(request: Request, x_line_signature: str = Header(None, alias="X-Line-Signature")):
    if not handler or not configuration:
        raise HTTPException(
            status_code=500,
            detail="LINE Bot credentials not configured in .env"
        )
    if not x_line_signature:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Line-Signature header"
        )

    body = (await request.body()).decode("utf-8")

    # Determine base URL for image links
    effective_base_url = os.getenv("BASE_URL", "").rstrip("/")
    if not effective_base_url:
        forwarded_proto = request.headers.get("x-forwarded-proto", "http")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost:8000")
        effective_base_url = f"{forwarded_proto}://{host}"

    try:
        events = handler.parser.parse(body, x_line_signature)
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_blob_api = MessagingApiBlob(api_client)

            for event in events:
                if not isinstance(event, MessageEvent):
                    continue

                source_id = get_source_id(event.source)

                # 1. 接收照片訊息並儲存
                if isinstance(event.message, ImageMessageContent):
                    image_bytes = line_bot_blob_api.get_message_content(event.message.id)
                    file_name = f"{event.message.id}.jpg"
                    file_path = os.path.join(PHOTOS_DIR, file_name)
                    with open(file_path, "wb") as f:
                        f.write(image_bytes)

                    save_photo_record(
                        group_id=source_id,
                        message_id=event.message.id,
                        file_name=file_name
                    )

                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="📸 照片已成功儲存到群組相簿！")]
                        )
                    )

                # 2. 接收文字訊息
                elif isinstance(event.message, TextMessageContent):
                    user_text = event.message.text.strip()

                    # 【回顧功能】：固定 7 天
                    if user_text == "回顧":
                        photos = get_photos(group_id=source_id, days=7)
                        if not photos:
                            reply_msg = TextMessage(text="最近 7 天內沒有照片紀錄喔！")
                        else:
                            reply_msg = build_review_carousel(photos, effective_base_url)

                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[reply_msg]
                            )
                        )

                    # 【說明功能】
                    elif user_text == "說明":
                        help_text = (
                            "🤖 群組相簿 Bot 使用說明（v1 基準版）：\n\n"
                            "1. 發送照片：自動儲存至群組相簿\n"
                            "2. 輸入「回顧」：查看最近 7 天的照片輪播\n"
                            "3. 輸入「說明」：查看此功能說明"
                        )
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=help_text)]
                            )
                        )

                    # 【第一版基準行為】：未處理輸入檢查與格式，僅做簡單 Echo 回覆
                    else:
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=f"📢 收到訊息：{event.message.text}")]
                            )
                        )

    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Please verify Channel Secret.")
    except Exception as e:
        print(f"[ERROR] Webhook error: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(content={"status": "OK"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
