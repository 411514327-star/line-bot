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
    ImageMessageContent,
    StickerMessageContent,
    VideoMessageContent,
    AudioMessageContent,
    LocationMessageContent,
    FileMessageContent
)

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables
load_dotenv(override=True)

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


def is_group_source(source) -> bool:
    """Check whether the event comes from a group or room chat."""
    source_type = getattr(source, "type", "")
    return source_type in ["group", "room"]


def build_review_carousel(photos: list, base_url: str, days: int = 7) -> FlexMessage:
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
        alt_text=f"📸 群組照片回顧（最近 {days} 天）",
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
        "service": "LINE Group Album Bot (v2 改善版)",
        "configured": bool(LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN),
        "base_url": os.getenv("BASE_URL", "").rstrip("/")
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
    effective_base_url = os.getenv("BASE_URL", "").rstrip("/") or BASE_URL
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
                is_group = is_group_source(event.source)

                # 1. 照片訊息處理
                if isinstance(event.message, ImageMessageContent):
                    # 【改善 4】：一對一聊天傳照片提示
                    if not is_group:
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[
                                    TextMessage(
                                        text="⚠️ 本相簿功能僅支援在群組中使用，請將我加入群組後再傳送照片喔！"
                                    )
                                ]
                            )
                        )
                        continue

                    # 群組照片：下載並儲存
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

                # 2. 文字訊息處理
                elif isinstance(event.message, TextMessageContent):
                    raw_text = event.message.text

                    # 【改善 1】：空白與純空格檢查
                    if not raw_text or raw_text.isspace():
                        reply_text = (
                            "⚠️ 請勿發送純空白訊息。\n\n"
                            "💡 可用指令範例：\n"
                            "• 輸入「說明」：查看完整功能指南\n"
                            "• 輸入「回顧」：查看最近 7 天照片輪播\n"
                            "• 輸入「回顧 3」：查看最近 3 天照片輪播"
                        )
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply_text)]
                            )
                        )
                        continue

                    user_text = raw_text.strip()

                    # 【說明功能】
                    if user_text == "說明":
                        help_text = (
                            "🤖 群組相簿 Bot 使用說明：\n\n"
                            "1. 【儲存照片】\n"
                            "   在群組中發送照片，將自動儲存至相簿。\n"
                            "   （⚠️ 本功能僅限群組使用）\n\n"
                            "2. 【照片回顧】\n"
                            "   • 輸入「回顧」：查看最近 7 天照片輪播\n"
                            "   • 輸入「回顧 3」：查看最近 3 天照片輪播（天數可自訂）\n"
                            "   （⚠️ 本功能僅限群組使用）\n\n"
                            "3. 【功能指南】\n"
                            "   • 輸入「說明」：隨時叫出此說明選單"
                        )
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=help_text)]
                            )
                        )

                    # 【改善 3 & 4】：「回顧」與動態天數指令
                    elif user_text == "回顧" or user_text.startswith("回顧"):
                        # 一對一聊天限制
                        if not is_group:
                            line_bot_api.reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[
                                        TextMessage(
                                            text="⚠️ 「回顧」功能僅支援在群組中使用，請將我加入群組後再試喔！"
                                        )
                                    ]
                                )
                            )
                            continue

                        # 判斷天數參數
                        if user_text == "回顧":
                            days = 7
                        else:
                            arg = user_text[2:].strip()
                            if arg.isdigit() and int(arg) > 0:
                                days = int(arg)
                            else:
                                # 格式錯誤提示與範例
                                invalid_reply = (
                                    "⚠️ 請輸入有效的天數數字！\n\n"
                                    "💡 指令範例：\n"
                                    "• `回顧`（預設查看最近 7 天）\n"
                                    "• `回顧 3`（查看最近 3 天）\n"
                                    "• `回顧 14`（查看最近 14 天）"
                                )
                                line_bot_api.reply_message(
                                    ReplyMessageRequest(
                                        reply_token=event.reply_token,
                                        messages=[TextMessage(text=invalid_reply)]
                                    )
                                )
                                continue

                        # 撈取照片並組裝輪播
                        photos = get_photos(group_id=source_id, days=days)
                        if not photos:
                            reply_msg = TextMessage(text=f"最近 {days} 天內沒有照片紀錄喔！")
                        else:
                            reply_msg = build_review_carousel(photos, effective_base_url, days=days)

                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[reply_msg]
                            )
                        )

                    # 【改善 2】：不認識的文字指令引導輸入「說明」
                    else:
                        reply_text = (
                            f"⚠️ 無法辨識指令「{user_text}」。\n\n"
                            "💡 請輸入「說明」查看支援的功能與格式範例！"
                        )
                        line_bot_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=reply_text)]
                            )
                        )

                # 3. 【改善 2】：不支援的訊息類型（貼圖、影片、語音、位置、檔案）
                elif isinstance(event.message, (
                    StickerMessageContent,
                    VideoMessageContent,
                    AudioMessageContent,
                    LocationMessageContent,
                    FileMessageContent
                )):
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[
                                TextMessage(
                                    text="⚠️ 目前僅支援儲存照片與相簿指令，不支援此類型的訊息。\n\n💡 請輸入「說明」查看可用的功能指南！"
                                )
                            ]
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
