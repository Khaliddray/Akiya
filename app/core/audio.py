import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("monivoice.audio")

class AudioConversionError(Exception):
    """Raised when ffmpeg conversion fails."""
    pass


async def convert_to_wav(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    sample_rate: int = 16000
) -> Path:
    """
    Converts incoming WhatsApp audio (.ogg / .opus) to 16kHz mono WAV format.
    """
    src = Path(input_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Input audio file not found: {src}")

    if output_path is None:
        dest = src.with_suffix(".wav")
    else:
        dest = Path(output_path).resolve()

    dest.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg arguments:
    # -y: overwrite output
    # -ar: 16000Hz standard sampling rate
    # -ac: 1 (mono channel)
    # -c:a: pcm_s16le uncompressed 16-bit PCM WAV
    command = [
        "ffmpeg",
        "-y",
        "-i", str(src),
        "-ar", str(sample_rate),
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(dest)
    ]

    logger.info(f"Converting audio: {src.name} -> {dest.name} ({sample_rate}Hz Mono)")

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error(f"ffmpeg conversion failed: {err_msg}")
            raise AudioConversionError(f"ffmpeg error (exit code {process.returncode}): {err_msg}")

        logger.info(f"Conversion complete: {dest.name} ({dest.stat().st_size} bytes)")
        return dest

    except FileNotFoundError:
        logger.error("ffmpeg executable not found on host. Ensure ffmpeg is installed.")
        raise AudioConversionError("ffmpeg is not installed or not found in PATH.")


async def cleanup_audio_files(*file_paths: str | Path) -> None:
    """Deletes temporary audio files after successful processing."""
    for path in file_paths:
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
                logger.debug(f"Cleaned up file: {p.name}")
        except Exception as e:
            logger.warning(f"Failed to delete temporary audio file {path}: {e}")
