"""Download lecture audio with yt-dlp (no ffmpeg needed: grabs the native audio stream)."""
from pathlib import Path

import yt_dlp

DATA = Path(__file__).resolve().parent.parent / "data"


def download_audio(url: str) -> tuple[Path, str]:
    DATA.mkdir(exist_ok=True)
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": str(DATA / "%(id)s.%(ext)s"),
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
    return path, info.get("title", path.stem)
