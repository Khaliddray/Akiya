import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query, HTTPException, BackgroundTasks, status
from fastapi.responses import PlainTextResponse, JSONResponse

from app.config import settings
from app.core.whatsapp import whatsapp_client
from app.db.database import init_db
from app.services.orchestrator import orchestrate_voice_transaction
from app.api.dashboard import router as dashboard_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("monivoice")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[*] Starting up Akiya service...")
    await init_db()
    yield
    logger.info("[*] Shutting down Akiya service...")

app = FastAPI(
    title="Akiya - Oral Ledger & Financial Voice Bot",
    description="Multilingual oral bookkeeping and fake alert protection for Nigerian micro-merchants.",
    version="1.0.0",
    lifespan=lifespan
)

# Mount REST API for Dashboard & Judges
app.include_router(dashboard_router)

async def handle_incoming_voice(user_phone: str, media_id: str, message_id: str):
    logger.info(f"[*] Processing audio task for {user_phone} | Msg ID: {message_id}")
    try:
        media_url = await whatsapp_client.get_media_url(media_id)
        raw_audio_path = await whatsapp_client.download_audio_file(
            media_url=media_url,
            filename=f"in_{message_id}.ogg"
        )
        await orchestrate_voice_transaction(user_phone, raw_audio_path)
    except Exception as e:
        logger.error(f"[!] Background task failed for {user_phone}: {e}", exc_info=True)


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        logger.info("[+] Webhook verified successfully with Meta.")
        return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)

    logger.warning("[-] Webhook verification failed. Invalid verify token.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@app.post("/webhook")
async def receive_whatsapp_message(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()

    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return JSONResponse(content={"status": "ignored_no_message"}, status_code=status.HTTP_200_OK)

        message = messages[0]
        sender_phone = message.get("from")
        msg_type = message.get("type")
        msg_id = message.get("id")

        if msg_type in ["audio", "voice"]:
            media_id = message[msg_type].get("id")
            logger.info(f"[+] Inbound audio note from {sender_phone} (Media ID: {media_id})")

            background_tasks.add_task(
                handle_incoming_voice,
                user_phone=sender_phone,
                media_id=media_id,
                message_id=msg_id
            )
        else:
            logger.info(f"[i] Non-audio message ({msg_type}) from {sender_phone}.")
            background_tasks.add_task(
                whatsapp_client.send_text_message,
                recipient_phone=sender_phone,
                text="Please send a voice note in Hausa, Yoruba, Igbo, or Pidgin to record your ledger."
            )

    except (IndexError, KeyError) as e:
        logger.warning(f"[-] Malformed webhook payload: {e}")

    return JSONResponse(content={"status": "received"}, status_code=status.HTTP_200_OK)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "akiya"}
