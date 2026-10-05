import asyncio
from pathlib import Path
import edge_tts

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"

TEST_SCENARIOS = [
    {
        "filename": "sale_pidgin_garri.ogg",
        "voice": "en-NG-EzinneNeural",
        "text": "I sell three bags of garri for fifteen thousand Naira each to mama Chuka.",
        "description": "Pidgin Sale: 3 bags @ 15k = 45k NGN"
    },
    {
        "filename": "expense_pidgin_transport.ogg",
        "voice": "en-NG-AbeoNeural",
        "text": "I pay two thousand Naira for truck wey carry the yam come shop.",
        "description": "Pidgin Expense: 2k transport"
    },
    {
        "filename": "sale_yoruba_lace.ogg",
        "voice": "en-NG-EzinneNeural",
        "text": "Mo ta aso lace meta ni egberun lona ogbon Naira.",
        "description": "Yoruba Sale: 3 lace fabrics"
    },
    {
        "filename": "expense_hausa_fuel.ogg",
        "voice": "en-NG-AbeoNeural",
        "text": "Na sayi man fetur na naira dubu biyar na janareta.",
        "description": "Hausa Expense: 5k generator fuel"
    },
    {
        "filename": "query_pidgin_balance.ogg",
        "voice": "en-NG-EzinneNeural",
        "text": "Abeg check how much money I make today and wetin remain for my hand.",
        "description": "Pidgin Balance Check"
    }
]

async def generate_sample(scenario: dict) -> None:
    filename = scenario["filename"]
    voice = scenario["voice"]
    text = scenario["text"]
    desc = scenario["description"]

    raw_mp3 = SAMPLES_DIR / f"{Path(filename).stem}_tmp.mp3"
    final_ogg = SAMPLES_DIR / filename

    print(f"[*] Generating: {filename} ({desc})...")

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(raw_mp3))

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(raw_mp3),
        "-c:a", "libopus",
        "-b:a", "32k",
        "-vn",
        str(final_ogg)
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        print(f"[!] Failed to convert {filename}: {stderr.decode(errors='replace')}")
    else:
        print(f"[+] Saved: {final_ogg.name} ({final_ogg.stat().st_size} bytes)")

    if raw_mp3.exists():
        raw_mp3.unlink()

async def main():
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for scenario in TEST_SCENARIOS:
        await generate_sample(scenario)
    print("\n[+] All audio samples generated successfully.")

if __name__ == "__main__":
    asyncio.run(main())
