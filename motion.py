"""Анимированный монтаж Reels в стиле Kelechek AI.

Каждый кадр рисуется в Python (Pillow) и сразу уходит в ffmpeg, поэтому эффекты
полностью под контролем:
  - фон живой: свечения медленно плывут, по экрану дрейфуют искры;
  - слова появляются по одному (всплытие + проявление), хук ещё и «пружинит»;
  - ключевые слова подсвечиваются маркером бирюзово-фиолетового градиента;
  - между слайдами текст уезжает вверх и гаснет, новый въезжает снизу;
  - сверху идёт полоса прогресса, на финальном слайде пульсирует кнопка.
"""
import math
import random
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
W, H, FPS = 1080, 1920, 30
CONTACT = "+996 502 091 443"

BG_IN, BG_OUT = (26, 31, 58), (10, 13, 28)
TEAL, VIOLET, WHITE, MUTED = (46, 230, 201), (123, 92, 255), (255, 255, 255), (170, 178, 205)
F_DISPLAY = str(ASSETS / "fonts" / "Unbounded-Bold.ttf")
F_BODY = str(ASSETS / "fonts" / "GolosText-Medium.ttf")
LEFT, RIGHT, TOP, BOTTOM = 96, 930, 330, 1450  # безопасная зона: низ и правый край закрывает интерфейс Reels

# слова, которые подсвечиваем маркером (по началу слова, без учёта регистра)
KEYWORDS = ["ии", "нейросет", "бесплатн", "автоматич", "автоматиз", "бишкек", "клиент", "заявк", "продаж",
            "деньг", "врем", "робот", "реклам"]
MAX_MARKS = 3
WORD_IN = 0.35       # сколько длится появление слова
STAGGER_HOOK = 0.16  # пауза между словами хука
OUT_T = 0.35         # уход слайда


def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_back(t):
    t = min(max(t, 0.0), 1.0)
    c = 1.7
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


# ---------- фон ----------

def base_background():
    """Фон с запасом по краям, чтобы его можно было медленно двигать."""
    bw, bh = W + 160, H + 240
    img = Image.new("RGB", (bw, bh), BG_OUT)
    d = ImageDraw.Draw(img)
    for r in range(1000, 0, -30):
        d.ellipse([bw / 2 - r, bh * 0.42 - r, bw / 2 + r, bh * 0.42 + r], fill=lerp(BG_IN, BG_OUT, r / 1000))
    img = img.filter(ImageFilter.GaussianBlur(60))
    # тонкая сетка: ощущение «технологичности»
    grid = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    g = ImageDraw.Draw(grid)
    for x in range(0, bw, 90):
        g.line([(x, 0), (x, bh)], fill=(255, 255, 255, 9))
    for y in range(0, bh, 90):
        g.line([(0, y), (bw, y)], fill=(255, 255, 255, 9))
    return Image.alpha_composite(img.convert("RGBA"), grid)


def glow_sprite(color, radius, alpha):
    s = Image.new("RGBA", (radius * 4, radius * 4), (0, 0, 0, 0))
    ImageDraw.Draw(s).ellipse([radius, radius, radius * 3, radius * 3], fill=color + (alpha,))
    return s.filter(ImageFilter.GaussianBlur(radius // 2))


class Backdrop:
    def __init__(self, seed=7):
        self.base = base_background()
        self.violet = glow_sprite(VIOLET, 300, 90)
        self.teal = glow_sprite(TEAL, 260, 60)
        rnd = random.Random(seed)
        self.sparks = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(2, 5), rnd.uniform(14, 40), rnd.uniform(0, 6.28))
                       for _ in range(38)]

    def frame(self, t):
        ox = int(80 + 60 * math.sin(t * 0.25))
        oy = int(120 + 90 * math.sin(t * 0.17 + 1))
        img = self.base.crop((ox, oy, ox + W, oy + H))
        vx, vy = int(W - 520 + 120 * math.sin(t * 0.4)), int(-420 + 140 * math.cos(t * 0.3))
        tx, ty = int(-560 + 110 * math.cos(t * 0.35)), int(H - 900 + 120 * math.sin(t * 0.28))
        img.alpha_composite(self.violet, (max(vx, 0), max(vy, 0)), (max(-vx, 0), max(-vy, 0)))
        img.alpha_composite(self.teal, (max(tx, 0), max(ty, 0)), (max(-tx, 0), max(-ty, 0)))
        d = ImageDraw.Draw(img)
        for x, y, r, speed, ph in self.sparks:
            yy = (y - speed * t) % H
            a = int(70 + 60 * math.sin(t * 2 + ph))
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=TEAL + (a,) if r > 3.5 else WHITE + (a // 2,))
        return img


# ---------- текст ----------

def is_key(word):
    w = word.lower().strip("«»\"'.,!?:;—()")
    return any(ch.isdigit() for ch in w) or any(w.startswith(k) for k in KEYWORDS)


def layout(text, path, start, minimum, spacing, box_h):
    """Разбивает текст на строки и возвращает слова с координатами."""
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    width = RIGHT - LEFT
    size = start
    while True:
        font = ImageFont.truetype(path, size)
        space = probe.textlength(" ", font=font)
        words, x, y, lines = [], 0.0, 0.0, 1
        for pi, para in enumerate(text.split("\n")):
            if not para.strip():
                y += size * 0.6
                continue
            if pi and words:
                x, y, lines = 0.0, y + size * spacing, lines + 1
            for word in para.split():
                wl = probe.textlength(word, font=font)
                pad = 14 if is_key(word) else 0  # место под маркер, чтобы он не налезал на соседние слова
                if x and x + pad + wl > width:
                    x, y, lines = 0.0, y + size * spacing, lines + 1
                x += pad if x else 0
                words.append({"text": word, "x": x, "y": y, "w": wl})
                x += wl + space + pad
        height = y + size * spacing
        if height <= box_h or size <= minimum:
            return font, size, words, height
        size -= 4


def word_sprite(word, font, size, color):
    pad = 20
    img = Image.new("RGBA", (int(word["w"]) + pad * 2, int(size * 1.5) + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad, pad), word["text"], font=font, fill=color)
    return img, pad


def marker_sprite(w, h):
    bar = Image.new("RGBA", (w, h))
    bd = ImageDraw.Draw(bar)
    for i in range(w):
        bd.line([(i, 0), (i, h)], fill=lerp(TEAL, VIOLET, i / max(w - 1, 1)) + (255,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 3, fill=255)
    bar.putalpha(mask)
    return bar


class TextSlide:
    def __init__(self, kind, text, duration, speech=None):
        self.kind, self.duration = kind, duration
        if kind == "hook":
            self.font, self.size, words, bh = layout(text, F_DISPLAY, 88, 52, 1.3, BOTTOM - TOP - 160)
            self.stagger = STAGGER_HOOK
        else:
            self.font, self.size, words, bh = layout(text, F_BODY, 62, 38, 1.4, BOTTOM - TOP)
            # всё тело должно проявиться за первые ~45% времени слайда
            self.stagger = min(0.09, duration * 0.45 / max(len(words), 1))
        if speech:
            # слова появляются вслед за голосом, как караоке
            self.stagger = speech * 0.9 / max(len(words), 1)
        self.y0 = TOP + (BOTTOM - TOP - bh) / 2 - (40 if kind == "hook" else 0)
        marks = 0
        self.words = []
        for i, w in enumerate(words):
            key = is_key(w["text"]) and marks < MAX_MARKS
            marks += key
            color = BG_OUT if key else WHITE
            spr, pad = word_sprite(w, self.font, self.size, color)
            mk = marker_sprite(int(w["w"]) + 24, int(self.size * 1.18)) if key else None
            self.words.append({**w, "spr": spr, "pad": pad, "key": key, "mk": mk, "t0": 0.25 + i * self.stagger})
        self.bar_y = int(self.y0 + bh + 40)

    def draw(self, img, t):
        leave = ease_out((t - (self.duration - OUT_T)) / OUT_T) if t > self.duration - OUT_T else 0.0
        dy_out, a_out = -70 * leave, 1 - leave
        for w in self.words:
            p = (t - w["t0"]) / WORD_IN
            if p <= 0:
                continue
            e = ease_back(p) if self.kind == "hook" else ease_out(p)
            alpha = min(1.0, p * 1.6) * a_out
            x = LEFT + w["x"]
            y = self.y0 + w["y"] + (1 - e) * 46 + dy_out
            if w["mk"] is not None:
                grow = ease_out((t - w["t0"] - WORD_IN * 0.6) / 0.3)
                if grow > 0:
                    mk = w["mk"].crop((0, 0, max(1, int(w["mk"].width * grow)), w["mk"].height))
                    paste_alpha(img, mk, int(x - 12), int(y + self.size * 0.08), alpha)
            spr = w["spr"]
            if self.kind == "hook" and p < 1:
                s = 0.7 + 0.3 * e
                spr = spr.resize((max(1, int(spr.width * s)), max(1, int(spr.height * s))), Image.BILINEAR)
            paste_alpha(img, spr, int(x - w["pad"]), int(y - w["pad"]), alpha)
        if self.kind == "hook":
            last = self.words[-1]["t0"] + WORD_IN if self.words else 0
            g = ease_out((t - last) / 0.5)
            if g > 0:
                paste_alpha(img, marker_sprite(max(1, int(240 * g)), 14), LEFT, int(self.bar_y + dy_out), a_out)


def paste_alpha(img, spr, x, y, alpha):
    if alpha <= 0:
        return
    if alpha < 1:
        spr = spr.copy()
        spr.putalpha(spr.getchannel("A").point(lambda v: int(v * alpha)))
    if x >= W or y >= H or x + spr.width <= 0 or y + spr.height <= 0:
        return
    sx, sy = max(-x, 0), max(-y, 0)
    img.alpha_composite(spr, (max(x, 0), max(y, 0)), (sx, sy))


CTA_TITLE = "15 дней работаем бесплатно"
CTA_SPEECH = "Пятнадцать дней работаем бесплатно. Пишите в ватсап, номер на экране."


class CtaSlide:
    def __init__(self, duration, speech=None):
        self.kind, self.duration = "cta", duration
        self.title = TextSlide("hook", CTA_TITLE, duration)
        self.title.y0 = 600
        self.sub_font = ImageFont.truetype(F_BODY, 44)
        self.phone_font = ImageFont.truetype(F_DISPLAY, 56)
        self.loc_font = ImageFont.truetype(F_BODY, 36)

    def draw(self, img, t):
        self.title.draw(img, t)
        y = self.title.bar_y + 70
        a = ease_out((t - 1.2) / 0.5)
        if a <= 0:
            return
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.text((LEFT, y), "Вы платите только за подписку", font=self.sub_font, fill=MUTED)
        d.text((LEFT, y + 60), "на ИИ-сервис. Пишите в WhatsApp:", font=self.sub_font, fill=MUTED)
        # пульсирующая кнопка с номером
        pulse = 1 + 0.04 * math.sin(max(t - 1.6, 0) * 5)
        bw, bh = int(760 * pulse), int(124 * pulse)
        bx, by = LEFT - (bw - 760) // 2, y + 170 - (bh - 124) // 2
        btn = marker_sprite(bw, bh)
        layer.alpha_composite(btn, (bx, by))
        tw = d.textlength(CONTACT, font=self.phone_font)
        d.text((bx + (bw - tw) / 2, by + bh / 2 - 36), CONTACT, font=self.phone_font, fill=BG_OUT)
        d.text((LEFT, y + 340), "В Бишкеке встречаемся лично", font=self.loc_font, fill=TEAL)
        paste_alpha(img, layer, 0, int(30 * (1 - a)), a)


def header():
    img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    logo = Image.open(ASSETS / "logo.png").convert("RGBA").resize((88, 88))
    mask = Image.new("L", (88, 88), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 87, 87], fill=255)
    logo.putalpha(mask)
    img.alpha_composite(logo, (LEFT, 150))
    d = ImageDraw.Draw(img)
    d.text((LEFT + 112, 172), "KELECHEK AI", font=ImageFont.truetype(F_DISPLAY, 34), fill=WHITE)
    d.text((LEFT + 112, 214), "ИИ-видео и автоматизация · Бишкек", font=ImageFont.truetype(F_BODY, 26), fill=MUTED)
    return img


def slide_duration(kind, text):
    if kind == "cta":
        return 4.5
    if kind == "hook":
        return min(5.0, max(3.2, 1.6 + len(text.split()) * STAGGER_HOOK + len(text) / 40))
    return min(7.0, max(3.5, 2.0 + len(text) / 24))


def render(slides, music, out, query=None, workdir=None):
    """slides: [(kind, text)], последний должен быть ("cta", "").
    query: что искать на стоке для фона; без ключа Pexels фон остаётся фирменным анимированным."""
    import media
    workdir = Path(workdir or Path(out).parent)
    workdir.mkdir(parents=True, exist_ok=True)
    # 1. озвучка: длительность сцен подстраивается под голос
    voices, scenes = [], []
    for i, (kind, text) in enumerate(slides):
        wav = workdir / f"voice{i}.wav"
        speech = media.synthesize(CTA_SPEECH if kind == "cta" else text.replace("\n", " "), wav)
        voices.append(wav if speech else None)
        base = slide_duration(kind, text)
        dur = max(base, speech + 0.8) if speech else base
        scenes.append(CtaSlide(dur, speech) if kind == "cta" else TextSlide(kind, text, dur, speech))
    total = sum(s.duration for s in scenes)
    # 2. фон: стоковое видео или анимированный фирменный
    clips = media.stock_clips(query or media.DEFAULT_QUERY, len(scenes), workdir / "stock") if query is not False else []
    if clips:
        backdrop = media.VideoFrames(media.background_video(clips, [s.duration for s in scenes], workdir / "bg.mp4"))
    else:
        backdrop = Backdrop()
    head = header()
    # 3. звук: голос по своим местам, музыка тише, если есть голос
    inputs, parts, labels, start = ["-stream_loop", "-1", "-i", str(music)], [], [], 0.0
    for scene, wav in zip(scenes, voices):
        if wav:
            k = 2 + len(labels)  # 0: кадры из Python, 1: музыка, дальше голоса
            inputs += ["-i", str(wav)]
            ms = int((start + 0.25) * 1000)
            parts.append(f"[{k}:a]aresample=44100,adelay={ms}|{ms},apad[v{k}]")
            labels.append(f"[v{k}]")
        start += scene.duration
    music_vol = 0.22 if labels else 1.0
    parts.append(f"[1:a]atrim=0:{total:.2f},volume={music_vol},afade=t=in:d=0.4,afade=t=out:st={total - 1.5:.2f}:d=1.5[m]")
    if labels:
        parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0,highpass=f=80,acompressor[vo]")
        parts.append("[m][vo]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100[a]")
    else:
        parts.append("[m]anull[a]")
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", "0:v", "-map", "[a]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    start = 0.0
    for scene in scenes:
        for f in range(int(round(scene.duration * FPS))):
            t = f / FPS
            g = start + t
            img = backdrop.frame(g)
            img.alpha_composite(head)
            scene.draw(img, t)
            d = ImageDraw.Draw(img)
            # полоса прогресса всего ролика
            d.rounded_rectangle([LEFT, 96, RIGHT, 104], radius=4, fill=(255, 255, 255, 40))
            img.alpha_composite(marker_sprite(max(8, int((RIGHT - LEFT) * g / total)), 8), (LEFT, 96))
            ff.stdin.write(img.convert("RGB").tobytes())
        start += scene.duration
    ff.stdin.close()
    if hasattr(backdrop, "close"):
        backdrop.close()
    if ff.wait():
        raise RuntimeError("ffmpeg не смог собрать ролик")
    return total, len(scenes)
