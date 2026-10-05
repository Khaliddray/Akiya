import asyncio
from pathlib import Path
import edge_tts

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

async def make_credit_sample():
    filename = "credit_pidgin_rice.ogg"
    raw_mp3 = SAMPLES_DIR / "credit_tmp.mp3"
    final_ogg = SAMPLES_DIR / filename
    text = "Mama Chuka collect goods on credit five thousand Naira."
    voice = "en-NG-EzinneNeural"

    print(f"[*] Generating: {filename}...")
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(raw_mp3))

    cmd = [
        "ffmpeg", "-y", "-i", str(raw_mp3),
        "-c:a", "libopus", "-b:a", "32k", "-vn",
        str(final_ogg)
    ]
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.communicate()

    if raw_mp3.exists():
        raw_mp3.unlink()
    print(f"[+] Saved credit test audio: {final_ogg.name}")

if __name__ == "__main__":
    asyncio.run(make_credit_sample())
