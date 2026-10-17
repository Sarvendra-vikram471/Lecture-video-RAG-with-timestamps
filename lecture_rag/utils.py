import re


def fmt_time(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def youtube_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def timestamp_url(video_url: str, seconds: float) -> str:
    vid = youtube_id(video_url)
    if vid:
        return f"https://www.youtube.com/watch?v={vid}&t={int(seconds)}s"
    return video_url
