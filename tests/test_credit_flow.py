import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
import edge_tts

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import init_db, get_user_summary, get_active_debtors
from app.services.orchestrator import orchestrate_voice_transaction

SAMPLES_DIR = ROOT_DIR / "tests" / "samples"
SAMPLE_FILE = SAMPLES_DIR / "credit_pidgin_rice.ogg"
TEST_PHONE = "2348012345678"

async def make_audio():
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    raw_mp3 = SAMPLES_DIR / "credit_tmp.mp3"
    print(f"[*] Synthesizing: {SAMPLE_FILE.name}...")
    comm = edge_tts.Communicate(
        text="Mama Chuka collect goods on credit five thousand Naira.",
        voice="en-NG-EzinneNeural"
    )
    await comm.save(str(raw_mp3))
    cmd = ["ffmpeg", "-y", "-i", str(raw_mp3), "-c:a", "libopus", "-b:a", "32k", "-vn", str(SAMPLE_FILE)]
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()
    if raw_mp3.exists():
        raw_mp3.unlink()
    print(f"[+] Audio ready: {SAMPLE_FILE.name}")

async def main():
    await init_db()
    if not SAMPLE_FILE.exists():
        await make_audio()

    print(f"[*] Running oral debt pipeline test for {TEST_PHONE}...")
    with patch("app.services.orchestrator.whatsapp_client.upload_audio_file", new_callable=AsyncMock) as m_up, \
         patch("app.services.orchestrator.whatsapp_client.send_audio_message", new_callable=AsyncMock) as m_snd, \
         patch("app.services.orchestrator.whatsapp_client.send_text_message", new_callable=AsyncMock):
        m_up.return_value = "mock_media_id_credit"
        m_snd.return_value = {"status": "success"}
        await orchestrate_voice_transaction(user_phone=TEST_PHONE, raw_audio_path=SAMPLE_FILE)

    summary = await get_user_summary(TEST_PHONE)
    debtors = await get_active_debtors(TEST_PHONE)

    print("\n" + "=" * 60)
    print(f"[+] VERIFIED LEDGER & DEBT STATE ({TEST_PHONE}):")
    print(f"    - Total Sales:            NGN {summary["total_sales"]:,.2f}")
    print(f"    - Net Cash Balance:       NGN {summary["net_balance"]:,.2f}")
    print(f"    - Total Outstanding Debt: NGN {summary["total_debt_owed"]:,.2f}")
    print(f"    - Active Debtors ({len(debtors)}):")
    for d in debtors:
        print(f"        * {d["customer_name"]}: NGN {d["remaining_balance"]:,.2f} (Total Owed: NGN {d["total_owed"]:,.2f})")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
