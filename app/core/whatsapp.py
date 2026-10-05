import os
import httpx
from pathlib import Path
from app.config import settings

GRAPH_API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

class WhatsAppClient:
    def __init__(self):
        self.token = settings.WHATSAPP_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "Akiya-Bot/1.0"
        }
        Path(settings.AUDIO_TMP_DIR).mkdir(parents=True, exist_ok=True)

    async def get_media_url(self, media_id: str) -> str:
        url = f"{BASE_URL}/{media_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self.headers)
            resp.raise_for_status()
            return resp.json()["url"]

    async def download_audio_file(self, media_url: str, filename: str) -> str:
        local_path = os.path.join(settings.AUDIO_TMP_DIR, filename)
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", media_url, headers=self.headers) as response:
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
        return local_path

    async def upload_audio_file(self, file_path: str) -> str:
        url = f"{BASE_URL}/{self.phone_number_id}/media"
        file_name = Path(file_path).name

        async with httpx.AsyncClient(timeout=45.0) as client:
            with open(file_path, "rb") as f:
                files = {
                    "file": (file_name, f, "audio/ogg; codecs=opus"),
                    "messaging_product": (None, "whatsapp"),
                    "type": (None, "audio/ogg")
                }
                resp = await client.post(url, headers={"Authorization": f"Bearer {self.token}"}, files=files)
                resp.raise_for_status()
                return resp.json()["id"]

    async def send_audio_message(self, recipient_phone: str, media_id: str) -> dict:
        url = f"{BASE_URL}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "audio",
            "audio": {"id": media_id}
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def send_text_message(self, recipient_phone: str, text: str) -> dict:
        url = f"{BASE_URL}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json()

whatsapp_client = WhatsAppClient()
