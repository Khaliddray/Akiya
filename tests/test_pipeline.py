import asyncio
import argparse
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import init_db, get_user_summary, get_active_debtors
from app.services.orchestrator import orchestrate_voice_transaction


async def run_test(audio_file: str, phone: str, live_whatsapp: bool):
    file_path = Path(audio_file).resolve()
    if not file_path.is_file():
        print(f"\n[!] Error: Audio file not found at: {file_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"[*] Starting Akiya Pipeline Test")
    print(f"[*] Audio File:  {file_path.name}")
    print(f"[*] Test User:    {phone}")
    print(f"[*] WhatsApp API: {'Live Dispatch' if live_whatsapp else 'Mocked (No SMS/WA Sent)'}")
    print(f"{'='*60}\n")

    await init_db()

    if not live_whatsapp:
        with patch("app.services.orchestrator.whatsapp_client.upload_audio_file", new_callable=AsyncMock) as mock_upload, \
             patch("app.services.orchestrator.whatsapp_client.send_audio_message", new_callable=AsyncMock) as mock_send, \
             patch("app.services.orchestrator.whatsapp_client.send_text_message", new_callable=AsyncMock) as mock_text:
            
            mock_upload.return_value = "mock_media_id_99999"
            mock_send.return_value = {"status": "mock_success"}
            mock_text.return_value = {"status": "mock_text_sent"}

            await orchestrate_voice_transaction(user_phone=phone, raw_audio_path=file_path)
            
            print("\n[+] Mock Dispatch Verification:")
            print(f"    - Upload called: {mock_upload.called}")
            print(f"    - Audio message dispatched: {mock_send.called}")
    else:
        await orchestrate_voice_transaction(user_phone=phone, raw_audio_path=file_path)

    summary = await get_user_summary(phone)
    debtors = await get_active_debtors(phone)

    print(f"\n{'='*60}")
    print(f"[+] Current Financial Health for {phone}:")
    print(f"    - Total Recorded Sales:    NGN {summary['total_sales']:,.2f}")
    print(f"    - Total Recorded Expenses: NGN {summary['total_expenses']:,.2f}")
    print(f"    - Net Cash Balance:        NGN {summary['net_balance']:,.2f}")
    print(f"    - Total Outstanding Debt:  NGN {summary['total_debt_owed']:,.2f}")
    print(f"    - Active Debtors ({len(debtors)}):")
    for d in debtors:
        print(f"        * {d['customer_name']}: NGN {d['remaining_balance']:,.2f} (Total Owed: NGN {d['total_owed']:,.2f})")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Akiya Audio Processing Pipeline")
    parser.add_argument("--audio", required=True, help="Path to input audio file")
    parser.add_argument("--phone", default="2348012345678", help="Test phone number")
    parser.add_argument("--live", action="store_true", help="Send actual audio via Meta API")

    args = parser.parse_args()
    asyncio.run(run_test(audio_file=args.audio, phone=args.phone, live_whatsapp=args.live))
