import asyncio
import logging
import uuid
from pathlib import Path
import edge_tts
from app.config import settings

logger = logging.getLogger("monivoice.tts")

# Voice selection: Prioritize Nigerian English accents for natural local cadence.
# For local languages, Nigerian English neural voices handle Pidgin, Yoruba,
# Hausa, and Igbo loanwords and phonemes significantly better than standard US/UK models.
VOICE_MAP = {
    "pcm": "en-NG-EzinneNeural",   # Nigerian Pidgin / Nigerian English female
    "en": "en-NG-AbeoNeural",      # Nigerian English male
    "yo": "en-NG-EzinneNeural",    # Yoruba context
    "ha": "en-NG-AbeoNeural",      # Hausa context
    "ig": "en-NG-EzinneNeural",    # Igbo context
}

DEFAULT_VOICE = "en-NG-EzinneNeural"

class TTSSynthesisError(Exception):
    """Raised when text-to-speech generation fails."""
    pass


async def synthesize_speech(
    text: str,
    language: str = "pcm",
    output_filename: str | None = None
) -> Path:
    """
    Synthesizes text into an audio file (.opus) compatible with WhatsApp voice messages.

    Args:
        text: Spoken response script.
        language: Language code ('pcm', 'yo', 'ha', 'ig', 'en').
        output_filename: Optional custom filename. Defaults to a unique UUID.

    Returns:
        Path object pointing to the output .opus file.
    """
    if not text.strip():
        raise ValueError("Cannot synthesize speech from empty text.")

    voice = VOICE_MAP.get(language.lower(), DEFAULT_VOICE)
    base_id = output_filename or f"tts_{uuid.uuid4().hex[:10]}"
    
    tmp_dir = Path(settings.AUDIO_TMP_DIR).resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)

    raw_mp3_path = tmp_dir / f"{base_id}.mp3"
    final_opus_path = tmp_dir / f"{base_id}.opus"

    logger.info(f"Synthesizing voice note with [{voice}] for language '{language}'")

    try:
        # Step 1: Synthesize audio stream to an intermediate MP3
        communicate = edge_tts.Communicate(text=text, voice=voice)
        await communicate.save(str(raw_mp3_path))

        # Step 2: Transcode MP3 to Opus/OGG formatted specifically for WhatsApp audio
        command = [
            "ffmpeg",
            "-y",
            "-i", str(raw_mp3_path),
            "-c:a", "libopus",
            "-b:a", "32k",
            "-vn",
            str(final_opus_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            raise TTSSynthesisError(f"ffmpeg opus encoding failed: {err_msg}")

        logger.info(f"Generated voice note: {final_opus_path.name} ({final_opus_path.stat().st_size} bytes)")
        return final_opus_path

    except Exception as e:
        logger.error(f"TTS synthesis error: {e}", exc_info=True)
        raise TTSSynthesisError(f"Failed to generate TTS audio: {e}")

    finally:
        # Cleanup temporary intermediate MP3
        if raw_mp3_path.exists():
            raw_mp3_path.unlink()
