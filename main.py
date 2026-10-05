import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import uvicorn

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

# Load environment variables
load_dotenv()

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

app = FastAPI(title="LINE Bot FastAPI Backend")

# Initialize LINE SDK v3 handlers if keys are present
handler = None
configuration = None

if LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN:
    handler = WebhookHandler(LINE_CHANNEL_SECRET)
    configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
else:
    print("[WARNING] LINE_CHANNEL_SECRET or LINE_CHANNEL_ACCESS_TOKEN is not set.")
    print("[INFO] Please create a .env file with your credentials from LINE Developers Console.")


@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "LINE Bot Webhook Service is running!",
        "configured": bool(LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN)
    }


def calculate_bmi(height_cm: float, weight_kg: float) -> str:
    """Calculate BMI and return formatted diagnosis string."""
    try:
        height_m = height_cm / 100
        bmi = weight_kg / (height_m ** 2)
        bmi_rounded = round(bmi, 2)
        
        if bmi < 18.5:
            category = "體重過輕"
            advice = "建議均衡飲食，適量增加營養攝取！"
        elif 18.5 <= bmi < 24.0:
            category = "正常範圍"
            advice = "太棒了！請繼續保持健康生活習慣！"
        elif 24.0 <= bmi < 27.0:
            category = "過重"
            advice = "注意控制飲食並增加規律運動！"
        else:
            category = "肥胖"
            advice = "建議諮詢專業營養師或醫師協助體重控制！"
            
        return (
            f"📊 BMI 計算結果：\n"
            f"• 身高：{height_cm} cm\n"
            f"• 體重：{weight_kg} kg\n"
            f"• BMI：{bmi_rounded}\n"
            f"• 體位判定：{category}\n"
            f"💡 小叮嚀：{advice}"
        )
    except Exception as e:
        return f"計算發生錯誤：{str(e)}"


def process_user_message(text: str) -> str:
    """Process incoming text message and generate reply."""
    stripped = text.strip()
    
    # 1. Help message
    if stripped.lower() in ["help", "說明", "幫助", "功能", "?"]:
        return (
            "🤖 LINE Bot 功能指令清單：\n\n"
            "1. 【BMI 計算】\n"
            "   輸入範例：`BMI 175 68`\n"
            "   格式：`BMI [身高cm] [體重kg]`\n\n"
            "2. 【打招呼】\n"
            "   輸入：`你好` 或 `hi`\n\n"
            "3. 【其他訊息】\n"
            "   直接傳送任何文字，我會自動回覆！"
        )

    # 2. Greeting
    if stripped.lower() in ["hi", "hello", "你好", "您好", "哈囉"]:
        return "👋 你好！很高興認識你！輸入「說明」可以查看我能為你做什麼喔！"

    # 3. BMI calculation parser
    if stripped.upper().startswith("BMI"):
        parts = stripped.split()
        if len(parts) == 3:
            try:
                h = float(parts[1])
                w = float(parts[2])
                return calculate_bmi(h, w)
            except ValueError:
                return "⚠️ 身高與體重請輸入有效數字，例如：`BMI 175 70`"
        else:
            return "⚠️ 格式不正確。請輸入格式如：`BMI 175 70` (身高cm 體重kg)"

    # Default echo response
    return f"📢 收到你的訊息：\n「{stripped}」\n\n(💡 輸入「說明」可查看可用指令)"


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

    try:
        # Handle webhook events
        events = handler.parser.parse(body, x_line_signature)
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            for event in events:
                if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                    user_reply = process_user_message(event.message.text)
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=user_reply)]
                        )
                    )
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Please verify Channel Secret.")
    except Exception as e:
        print(f"[ERROR] Error handling webhook: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(content={"status": "OK"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
