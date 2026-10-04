"""Видео со стока и озвучка для Reels.

- Фон: бесплатные видео со стока Pixabay (секрет PIXABAY_API_KEY) или Pexels (PEXELS_API_KEY),
  оба разрешают коммерческое использование без указания автора. Без ключей остаётся анимированный фирменный фон.
- Голос: открытый голос Piper ru_RU-dmitri-medium (датасет CC0), работает офлайн.
  Модель скачивается в workflow в assets/voice/; без неё ролик выходит без голоса.
"""
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import requests

HERE = Path(__file__).parent
VOICE_ENGINE = os.environ.get("VOICE_ENGINE", "piper")  # piper или chatterbox
VOICE_REF = Path(os.environ.get("VOICE_REF", HERE / "assets" / "voice" / "ref.flac"))  # образец голоса для chatterbox
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
# запасные запросы: добираем ими клипы, когда по теме всё свежее уже использовано
EXTRA_QUERIES = [
    "city night lights", "smartphone hand", "typing keyboard", "coffee shop", "mountains clouds",
    "city aerial", "people street walking", "office work", "neon light", "sunset city",
    "shop owner", "hands laptop", "car traffic night", "market street", "abstract particles",
]
USED_CLIPS_FILE = HERE / "used_clips.json"
picked_clips = []  # id клипов последнего ролика; reels.py отмечает их использованными после публикации


def used_clips():
    return set(json.loads(USED_CLIPS_FILE.read_text(encoding="utf-8"))) if USED_CLIPS_FILE.exists() else set()


def mark_clips_used(ids):
    used = sorted(used_clips() | set(ids))
    USED_CLIPS_FILE.write_text(json.dumps(used, indent=0) + "\n", encoding="utf-8")


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


# ---------- голос ----------

def speakable(text):
    """Готовит текст к озвучке: цифры словами, латиница и сокращения так, как их произносят."""
    t = text.replace("Kelechek AI", "Келечек эй-ай").replace("WhatsApp", "вотсап").replace("Reels", "рилс")
    t = re.sub(r"\bИИ\b", "и-и", t)
    t = re.sub(r"(\d{1,2}):(\d{2})", r"\1 \2", t)
    try:
        from num2words import num2words
        t = re.sub(r"\d+", lambda m: num2words(int(m.group()), lang="ru"), t)
    except ImportError:
        pass
    t = re.sub(r"[«»\"–—]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_CB = None


def _chatterbox():
    """Нейросетевой голос Chatterbox Multilingual (MIT): звучит живее Piper, но синтез медленнее."""
    global _CB
    if _CB is None:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        _CB = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    return _CB


def synthesize_chatterbox(text, wav):
    import torchaudio
    model = _chatterbox()
    audio = model.generate(speakable(text), language_id="ru", exaggeration=0.6, cfg_weight=0.4,
                           audio_prompt_path=str(VOICE_REF) if VOICE_REF.exists() else None)
    torchaudio.save(str(wav), audio, model.sr)
    return duration(wav)


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
    if VOICE_ENGINE == "chatterbox" and text.strip():
        try:
            return synthesize_chatterbox(text, wav)
        except Exception as e:  # noqa: BLE001
            print(f"Chatterbox не сработал ({e}), озвучиваю Piper")
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

def pexels_clips(query, n, dest, skip=frozenset()):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    r = requests.get("https://api.pexels.com/videos/search", timeout=30, headers={"Authorization": key},
                     params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 30,
                             "page": random.randint(1, 3)})
    if not r.ok:
        print(f"Pexels не ответил: {r.status_code} {r.text[:200]}")
        return []
    dest.mkdir(parents=True, exist_ok=True)
    clips = []
    for v in r.json().get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("height") and f.get("width")
                 and f["height"] > f["width"] and f["height"] >= 1280 and f.get("file_type") == "video/mp4"]
        if not files or v.get("duration", 0) < 4 or f"pexels-{v['id']}" in skip:
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


def pixabay_clips(query, n, dest, skip=frozenset()):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    params = {"key": key, "q": query, "per_page": 50, "safesearch": "true", "page": random.randint(1, 3)}
    r = requests.get("https://pixabay.com/api/videos/", timeout=30, params=params)
    if r.status_code == 400 and params["page"] > 1:  # по редкому запросу дальних страниц нет
        r = requests.get("https://pixabay.com/api/videos/", timeout=30, params={**params, "page": 1})
    if not r.ok:
        print(f"Pixabay не ответил: {r.status_code} {r.text[:200]}")
        return []
    dest.mkdir(parents=True, exist_ok=True)
    # сначала вертикальные ролики, потом остальные (их обрежем по центру)
    hits = r.json().get("hits", [])
    random.shuffle(hits)
    hits = sorted(hits, key=lambda v: -(v["videos"]["medium"].get("height", 0) >
                                                            v["videos"]["medium"].get("width", 1)))
    clips = []
    for v in hits:
        if v.get("duration", 0) < 4 or f"pixabay-{v['id']}" in skip:
            continue
        files = [f for f in v["videos"].values() if f.get("url") and f.get("height", 0) >= 720]
        if not files:
            continue
        best = min(files, key=lambda f: abs(max(f["width"], f["height"]) - H))
        path = dest / f"pixabay-{v['id']}.mp4"
        with requests.get(best["url"], timeout=120, stream=True) as resp:
            if not resp.ok:
                continue
            with path.open("wb") as fh:
                for chunk in resp.iter_content(1 << 20):
                    fh.write(chunk)
        clips.append(path)
        if len(clips) >= n:
            break
    return clips


def stock_clips(query, n, dest):
    """n разных клипов, которых ещё не было в прошлых роликах: сначала по теме, потом запасные запросы."""
    skip = set(used_clips())
    clips = []
    queries = [query] + random.sample(EXTRA_QUERIES, len(EXTRA_QUERIES))
    for q in queries:
        if len(clips) >= n:
            break
        got = pixabay_clips(q, n - len(clips), dest, skip) or pexels_clips(q, n - len(clips), dest, skip)
        clips += got
        skip |= {c.stem for c in got}
    picked_clips[:] = [c.stem for c in clips]
    print(f"Фон: {len(clips)} новых клипов ({', '.join(picked_clips)})")
    return clips


def background_video(clips, lengths, out):
    """Склеивает клипы в один фон 1080x1920: по клипу на сцену, обрезка по центру, лёгкое замедление."""
    inputs, parts = [], []
    for i, length in enumerate(lengths):
        clip = clips[i % len(clips)]
        # берём не начало клипа, а случайный кусок: начало у стоков часто одинаковое и скучное
        spare = duration(clip) - length / 1.15 - 0.5
        inputs += ["-ss", f"{random.uniform(0, spare):.2f}" if spare > 1 else "0", "-i", str(clip)]
        # медленный проезд камеры: кадр чуть крупнее экрана, окно плывёт в одну из сторон
        zw, zh = int(W * 1.08) // 2 * 2, int(H * 1.08) // 2 * 2
        dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        cx = f"({zw - W}/2)*(1+{dx}*(2*t/{length:.2f}-1))" if dx else f"{(zw - W) // 2}"
        cy = f"({zh - H}/2)*(1+{dy}*(2*t/{length:.2f}-1))" if dy else f"{(zh - H) // 2}"
        parts.append(f"[{i}:v]scale={zw}:{zh}:force_original_aspect_ratio=increase,crop={zw}:{zh},"
                     f"setpts=1.15*PTS,fps={FPS},trim=duration={length:.2f},setpts=PTS-STARTPTS,"
                     f"crop={W}:{H}:x='{cx}':y='{cy}',"
                     # единый цвет для клипов из разных источников: чуть контраста, приглушённая насыщенность
                     f"eq=contrast=1.06:saturation=0.88,colorbalance=bs=0.04:bh=0.02,"
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
        alpha.putdata([150 + int(65 * y / H) for y in range(H)])
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
