"""Видео со стока и озвучка для Reels.

- Фон: бесплатные вертикальные видео с Pexels (можно в рекламе, без указания автора).
  Нужен секрет PEXELS_API_KEY; без него остаётся анимированный фирменный фон.
- Голос: открытый голос Piper ru_RU-dmitri-medium (датасет CC0), работает офлайн.
  Модель скачивается в workflow в assets/voice/; без неё ролик выходит без голоса.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

HERE = Path(__file__).parent
VOICE_MODEL = Path(os.environ.get("PIPER_MODEL", HERE / "assets" / "voice" / "ru_RU-dmitri-medium.onnx"))
W, H, FPS = 1080, 1920, 30

# что искать на стоке по теме поста (англ. запросы находят на Pexels больше)
TOPIC_QUERIES = {
    "ai-video": "video editing computer", "automation": "smartphone business chat", "region": "city night traffic",
    "meeting": "business meeting laptop", "offer": "small business owner", "mini-reel": "content creator phone",
    "mini-whatsapp": "phone messages night", "lead-magnet": "coffee shop barista", "honest": "thinking person window",
    "tip": "laptop work desk", "question": "people talking cafe", "automation-proof": "robot technology abstract",
}
DEFAULT_QUERY = "technology abstract"


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


# ---------- голос ----------

def speakable(text):
    """Готовит текст к озвучке: цифры словами, латиница и сокращения так, как их произносят."""
    t = text.replace("Kelechek AI", "Келечек эй-ай").replace("WhatsApp", "ватсап").replace("Reels", "рилс")
    t = re.sub(r"\bИИ\b", "и-и", t)
    t = re.sub(r"(\d{1,2}):(\d{2})", r"\1 \2", t)
    try:
        from num2words import num2words
        t = re.sub(r"\d+", lambda m: num2words(int(m.group()), lang="ru"), t)
    except ImportError:
        pass
    t = re.sub(r"[«»\"–—]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def voice_available():
    if not VOICE_MODEL.exists():
        return False
    try:
        import piper  # noqa: F401
        return True
    except ImportError:
        return False


def synthesize(text, wav):
    """Озвучивает текст в wav, возвращает длительность в секундах или None."""
    if not voice_available() or not text.strip():
        return None
    r = subprocess.run([sys.executable, "-m", "piper", "--model", str(VOICE_MODEL), "--output_file", str(wav),
                        "--length_scale", "0.95", "--sentence_silence", "0.15"],
                       input=speakable(text), text=True, capture_output=True)
    if r.returncode or not Path(wav).exists():
        print(f"Озвучка не получилась: {r.stderr[-300:]}")
        return None
    return duration(wav)


# ---------- сток ----------

def pexels_clips(query, n, dest):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    r = requests.get("https://api.pexels.com/videos/search", timeout=30, headers={"Authorization": key},
                     params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 15})
    if not r.ok:
        print(f"Pexels не ответил: {r.status_code} {r.text[:200]}")
        return []
    dest.mkdir(parents=True, exist_ok=True)
    clips = []
    for v in r.json().get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("height") and f.get("width")
                 and f["height"] > f["width"] and f["height"] >= 1280 and f.get("file_type") == "video/mp4"]
        if not files or v.get("duration", 0) < 4:
            continue
        best = min(files, key=lambda f: abs(f["width"] - W))
        path = dest / f"pexels-{v['id']}.mp4"
        with requests.get(best["link"], timeout=120, stream=True) as resp:
            if not resp.ok:
                continue
            with path.open("wb") as fh:
                for chunk in resp.iter_content(1 << 20):
                    fh.write(chunk)
        clips.append(path)
        if len(clips) >= n:
            break
    return clips


def background_video(clips, lengths, out):
    """Склеивает клипы в один фон 1080x1920: по клипу на сцену, обрезка по центру, лёгкое замедление."""
    inputs, parts = [], []
    for i, length in enumerate(lengths):
        clip = clips[i % len(clips)]
        inputs += ["-i", str(clip)]
        parts.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                     f"setpts=1.15*PTS,fps={FPS},trim=duration={length:.2f},setpts=PTS-STARTPTS,"
                     f"tpad=stop_mode=clone:stop_duration={length:.2f},trim=duration={length:.2f},format=rgb24[c{i}]")
    parts.append("".join(f"[c{i}]" for i in range(len(lengths))) + f"concat=n={len(lengths)}:v=1:a=0[v]")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(parts),
                    "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)], check=True)
    return out


class VideoFrames:
    """Отдаёт кадры фонового видео по порядку, затемнённые снизу и сверху, чтобы текст читался."""

    def __init__(self, path):
        from PIL import Image
        self.Image = Image
        self.proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.size = W * H * 3
        # тёмная вуаль, плотнее книзу, чтобы белый текст всегда читался
        alpha = Image.new("L", (1, H))
        alpha.putdata([175 + int(45 * y / H) for y in range(H)])
        self.shade = Image.new("RGBA", (W, H), (10, 13, 28, 0))
        self.shade.putalpha(alpha.resize((W, H)))
        self.last = None

    def frame(self, t):
        raw = self.proc.stdout.read(self.size)
        if len(raw) == self.size:
            self.last = self.Image.frombytes("RGB", (W, H), raw).convert("RGBA")
            self.last.alpha_composite(self.shade)
        return self.last.copy()

    def close(self):
        self.proc.stdout.close()
        self.proc.wait()
