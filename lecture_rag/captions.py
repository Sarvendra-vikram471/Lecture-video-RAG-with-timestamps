"""Fetch existing YouTube captions: instant, no audio download, no Whisper."""
import json
import urllib.parse
import urllib.request

from youtube_transcript_api import YouTubeTranscriptApi

LANGS = ["en", "en-IN", "en-US", "en-GB", "hi"]


def _via_transcript_api(video_id: str) -> list[dict] | None:
    try:
        return [
            {"start": s.start, "duration": s.duration, "text": s.text}
            for s in YouTubeTranscriptApi().fetch(video_id, languages=LANGS)
        ]
    except Exception:
        return None


def _via_ytdlp(video_id: str) -> list[dict] | None:
    """yt-dlp exposes manual + auto-generated subtitle tracks; read the json3 format."""
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            for pool in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
                lang = next((l for l in LANGS if l in pool), None) or next(
                    (l for l in pool if l.startswith("en") and "-" not in l[2:3]), None
                )
                track = next((t for t in pool.get(lang, []) if t.get("ext") == "json3"), None) if lang else None
                if track:
                    data = json.loads(ydl.urlopen(track["url"]).read().decode("utf-8"))
                    return [
                        {
                            "start": e["tStartMs"] / 1000,
                            "duration": e.get("dDurationMs", 0) / 1000,
                            "text": "".join(s.get("utf8", "") for s in e["segs"]),
                        }
                        for e in data.get("events", [])
                        if e.get("segs")
                    ]
    except Exception:
        return None
    return None


def fetch_captions(video_id: str, merge_sec: float = 15) -> list[dict] | None:
    """Return caption segments as {start, end, text}, or None if the video has no captions."""
    raw = _via_transcript_api(video_id) or _via_ytdlp(video_id)
    return merge_lines(raw, merge_sec) if raw else None


def merge_lines(raw: list[dict], merge_sec: float = 15) -> list[dict] | None:
    """Caption lines ({start, duration, text}) are only 2-5s long, so they are merged into
    ~merge_sec segments that carry enough meaning for topic chunking."""
    segments, cur = [], None
    for s in raw:
        text = s["text"].replace("\n", " ").strip()
        if not text or text.startswith("["):  # skip "[Music]" etc.
            continue
        end = s["start"] + s["duration"]
        # keep merging past merge_sec until a sentence ends, so segments don't start mid-sentence
        mid_sentence = cur and not cur["text"].rstrip().endswith((".", "?", "!"))
        limit = merge_sec * 2 if mid_sentence else merge_sec
        if cur and end - cur["start"] <= limit:
            cur["text"] += " " + text
            cur["end"] = end
        else:
            if cur:
                segments.append(cur)
            cur = {"start": s["start"], "end": end, "text": text}
    if cur:
        segments.append(cur)
    return segments or None


def video_title(video_id: str) -> str:
    """Title via YouTube's public oEmbed endpoint (no API key)."""
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(
        f"https://www.youtube.com/watch?v={video_id}"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r)["title"]
    except Exception:
        return video_id
