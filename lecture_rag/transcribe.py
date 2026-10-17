"""Whisper transcription via faster-whisper -> segments with start/end times."""
from faster_whisper import WhisperModel


def transcribe(audio_path, model_size: str = "small") -> list[dict]:
    model = WhisperModel(model_size, device="auto", compute_type="auto")
    segments, _ = model.transcribe(str(audio_path), vad_filter=True)
    return [
        {"start": s.start, "end": s.end, "text": s.text.strip()}
        for s in segments
        if s.text.strip()
    ]
