"""Автомонтаж и автопостинг Reels в Instagram в едином стиле Kelechek AI.

Берёт следующий пост из posts.json, который ещё не выходил в Instagram,
режет текст на слайды, рисует их в фирменном стиле, собирает вертикальный
ролик с музыкой и публикует его как Reels.

Запуск:
  python reels.py --render-only   # только собрать ролик в out/reel.mp4
  python reels.py                 # собрать и опубликовать
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
OUT = HERE / "out"
POSTS_FILE = HERE / "posts.json"
W, H, FPS = 1080, 1920, 30
IG_VERSION = "v22.0"
IG_API = f"https://graph.instagram.com/{IG_VERSION}"
CONTACT = "+996 502 091 443"
HASHTAGS = "#бишкек #кыргызстан #ии #нейросети #иивидео #автоматизациябизнеса #reels"

# фирменный стиль
BG_IN, BG_OUT = (26, 31, 58), (10, 13, 28)
TEAL, VIOLET, WHITE, MUTED = (46, 230, 201), (123, 92, 255), (255, 255, 255), (170, 178, 205)
F_DISPLAY = str(ASSETS / "fonts" / "Unbounded-Bold.ttf")
F_BODY = str(ASSETS / "fonts" / "GolosText-Medium.ttf")
LEFT, RIGHT, TOP, BOTTOM = 96, 930, 300, 1450  # безопасная зона: низ и правый край закрывает интерфейс Reels

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def clean(text):
    return EMOJI.sub("", text).replace("  ", " ").strip()


def split_slides(text):
    paras = [clean(p) for p in text.split("\n\n")]
    paras = [p for p in paras if p and "wa.me" not in p and "опубликован автоматически" not in p]
    if not paras:
        return []
    slides = [("hook", paras[0])]
    buf = ""
    for p in paras[1:]:
        if buf and len(buf) + len(p) > 230:
            slides.append(("body", buf))
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        slides.append(("body", buf))
    return slides[:5]


def wrap(draw, text, font, width):
    lines = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        line = ""
        for word in para.split():
            test = f"{line} {word}".strip()
            if draw.textlength(test, font=font) <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return lines


def fit(draw, text, path, start, minimum, width, height, spacing):
    size = start
    while size >= minimum:
        font = ImageFont.truetype(path, size)
        lines = wrap(draw, text, font, width)
        h = len(lines) * size * spacing
        if h <= height:
            return font, lines, size
        size -= 4
    font = ImageFont.truetype(path, minimum)
    return font, wrap(draw, text, font, width), minimum


def background():
    img = Image.new("RGB", (W, H), BG_OUT)
    glow = Image.new("RGB", (W, H), BG_OUT)
    d = ImageDraw.Draw(glow)
    for r in range(900, 0, -30):
        t = r / 900
        c = tuple(int(BG_IN[i] * (1 - t) + BG_OUT[i] * t) for i in range(3))
        d.ellipse([W / 2 - r, H * 0.42 - r, W / 2 + r, H * 0.42 + r], fill=c)
    img.paste(glow.filter(ImageFilter.GaussianBlur(60)))
    accent = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = ImageDraw.Draw(accent)
    a.ellipse([W - 420, -260, W + 260, 420], fill=VIOLET + (70,))
    a.ellipse([-300, H - 520, 380, H + 160], fill=TEAL + (45,))
    img = Image.alpha_composite(img.convert("RGBA"), accent.filter(ImageFilter.GaussianBlur(140)))
    return img


def header(img):
    logo = Image.open(ASSETS / "logo.png").convert("RGBA").resize((88, 88))
    mask = Image.new("L", (88, 88), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, 87, 87], fill=255)
    img.paste(logo, (LEFT, 150), mask)
    d = ImageDraw.Draw(img)
    d.text((LEFT + 112, 172), "KELECHEK AI", font=ImageFont.truetype(F_DISPLAY, 34), fill=WHITE)
    d.text((LEFT + 112, 214), "ИИ-видео и автоматизация · Бишкек", font=ImageFont.truetype(F_BODY, 26), fill=MUTED)


def gradient_bar(img, x, y, w, h):
    bar = Image.new("RGBA", (w, h))
    bd = ImageDraw.Draw(bar)
    for i in range(w):
        t = i / max(w - 1, 1)
        bd.line([(i, 0), (i, h)], fill=tuple(int(TEAL[k] * (1 - t) + VIOLET[k] * t) for k in range(3)) + (255,))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=255)
    img.paste(bar, (x, y), mask)


def dots(img, index, total):
    d = ImageDraw.Draw(img)
    x = LEFT
    for i in range(total):
        w = 56 if i == index else 16
        d.rounded_rectangle([x, 1530, x + w, 1546], radius=8, fill=TEAL if i == index else (70, 78, 110))
        x += w + 12


def render_slide(kind, text, index, total, path):
    img = background()
    header(img)
    d = ImageDraw.Draw(img)
    width, height = RIGHT - LEFT, BOTTOM - TOP
    if kind == "cta":
        f1 = ImageFont.truetype(F_DISPLAY, 64)
        y = 640
        for line in wrap(d, "15 дней работаем бесплатно", f1, width):
            d.text((LEFT, y), line, font=f1, fill=WHITE)
            y += 84
        gradient_bar(img, LEFT, y + 30, 220, 14)
        f2 = ImageFont.truetype(F_BODY, 44)
        y += 90
        for line in wrap(d, "Вы платите только за подписку на ИИ-сервис. Пишите в WhatsApp:", f2, width):
            d.text((LEFT, y), line, font=f2, fill=MUTED)
            y += 60
        d.text((LEFT, y + 30), CONTACT, font=ImageFont.truetype(F_DISPLAY, 58), fill=TEAL)
    elif kind == "hook":
        font, lines, size = fit(d, text, F_DISPLAY, 84, 52, width, height - 120, 1.28)
        block = len(lines) * size * 1.28
        y = TOP + (height - block) / 2 - 40
        for line in lines:
            d.text((LEFT, y), line, font=font, fill=WHITE)
            y += size * 1.28
        gradient_bar(img, LEFT, int(y + 36), 220, 14)
    else:
        font, lines, size = fit(d, text, F_BODY, 60, 38, width, height, 1.38)
        block = len(lines) * size * 1.38
        y = TOP + (height - block) / 2
        for line in lines:
            d.text((LEFT, y), line, font=font, fill=WHITE if line else WHITE)
            y += size * 1.38 if line else size * 0.6
    dots(img, index, total)
    img.convert("RGB").save(path, quality=95)


def pick_music(n):
    """Треки из assets/music (бесплатные, Pixabay) идут по кругу: каждый следующий ролик со следующим треком."""
    tracks = sorted((ASSETS / "music").glob("*.mp3"))
    return tracks[n % len(tracks)]


def build_reel(text, music=None):
    OUT.mkdir(exist_ok=True)
    slides = split_slides(text) + [("cta", "")]
    durations = []
    for i, (kind, body) in enumerate(slides):
        render_slide(kind, body, i, len(slides), OUT / f"slide{i}.png")
        durations.append(4.0 if kind == "cta" else min(6.5, max(3.0, 1.8 + len(body) / 22)))
    fade = 0.5
    inputs, parts = [], []
    for i, dur in enumerate(durations):
        frames = int((dur + fade) * FPS)
        inputs += ["-loop", "1", "-t", f"{dur + fade:.2f}", "-i", str(OUT / f"slide{i}.png")]
        parts.append(f"[{i}:v]scale=1188:2112,zoompan=z='min(zoom+0.0006,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                     f":d={frames}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p[v{i}]")
    last, offset = "v0", 0.0
    for i in range(1, len(durations)):
        offset += durations[i - 1]
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={fade}:offset={offset:.2f}[x{i}]")
        last = f"x{i}"
    total = sum(durations) + fade
    n = len(durations)
    inputs += ["-stream_loop", "-1", "-i", str(music or pick_music(0))]
    parts.append(f"[{n}:a]atrim=0:{total:.2f},afade=t=out:st={total - 1.5:.2f}:d=1.5[a]")
    out = OUT / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
                    "-filter_complex", ";".join(parts), "-map", f"[{last}]", "-map", "[a]",
                    "-t", f"{total:.2f}", "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-movflags", "+faststart", str(out)], check=True)
    print(f"Ролик собран: {out} ({total:.1f} сек, слайдов: {n})")
    return out


def caption(text):
    body = re.sub(r"(Пиши|Пишите)?[^\n]*wa\.me/\S+", "", text).strip()
    footer = ("\n\n👉 Пиши в WhatsApp, ссылка в профиле, или на номер " + CONTACT +
              "\n📍 В Бишкеке встречаемся лично и показываем всё вживую" +
              "\n\n🤖 Ролик смонтирован и опубликован автоматически. Так же можем и для вашего бизнеса.")
    return f"{body}{footer}\n\n{HASHTAGS}"[:2200]


def need(name):
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Не задана переменная {name}")
    return val


def publish(video, text):
    token = need("IG_ACCESS_TOKEN")
    user_id = os.environ.get("IG_USER_ID")
    if not user_id:
        me = requests.get(f"{IG_API}/me", timeout=30, params={"fields": "user_id,username", "access_token": token})
        if not me.ok:
            sys.exit(f"Токен Instagram не работает: {me.status_code} {me.text}")
        user_id = str(me.json().get("user_id") or me.json()["id"])
        print(f"Аккаунт Instagram: {me.json().get('username')} ({user_id})")
    video_url = host_on_github(video)
    r = requests.post(f"{API_URL(user_id)}/media", timeout=60, data={
        "media_type": "REELS", "video_url": video_url, "caption": caption(text),
        "share_to_feed": "true", "access_token": token})
    if not r.ok:
        sys.exit(f"Не удалось создать контейнер: {r.status_code} {r.text}")
    container = r.json()["id"]
    for _ in range(40):
        time.sleep(10)
        s = requests.get(f"{IG_API}/{container}", timeout=30,
                         params={"fields": "status_code,status", "access_token": token}).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            sys.exit(f"Instagram не принял видео: {s}")
    else:
        sys.exit("Instagram слишком долго обрабатывает видео")
    r = requests.post(f"{API_URL(user_id)}/media_publish", timeout=60,
                      data={"creation_id": container, "access_token": token})
    if not r.ok:
        sys.exit(f"Не удалось опубликовать: {r.status_code} {r.text}")
    return r.json()["id"]


def host_on_github(video):
    """Instagram с входом через Instagram берёт Reels только по публичной ссылке.
    Кладём ролик в media/ этого репозитория (он должен быть открытым) и отдаём ссылку на GitHub."""
    repo = need("GITHUB_REPOSITORY")
    name = f"media/reel-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.mp4"
    (HERE / "media").mkdir(exist_ok=True)
    (HERE / name).write_bytes(video.read_bytes())
    git = lambda *a: subprocess.run(["git", *a], cwd=HERE, check=True, capture_output=True, text=True).stdout.strip()
    git("add", name)
    git("commit", "-m", f"reels: ролик {name}")
    git("pull", "--rebase", "origin", "main")
    git("push", "origin", "HEAD:main")
    url = f"https://raw.githubusercontent.com/{repo}/{git('rev-parse', 'HEAD')}/{name}"
    if requests.head(url, timeout=30, allow_redirects=True).status_code != 200:
        sys.exit("Ролик не открывается по ссылке GitHub: репозиторий должен быть открытым (public)")
    print(f"Ролик выложен: {url}")
    return url


def API_URL(user_id):
    return f"{IG_API}/{user_id}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--text", help="собрать ролик из этого текста вместо очереди")
    args = ap.parse_args()

    if not (args.render_only or args.text) and not os.environ.get("IG_ACCESS_TOKEN"):
        print("Instagram ещё не подключён (нет секрета IG_ACCESS_TOKEN), пропускаю.")
        return
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    if args.text:
        post = {"text": args.text}
    else:
        queue = [p for p in posts if not p.get("ig_posted_at")]
        if not queue:
            sys.exit("Очередь для Instagram пуста: добавь посты в posts.json")
        post = queue[0]
    video = build_reel(post["text"], pick_music(sum(1 for p in posts if p.get("ig_posted_at"))))
    if args.render_only or args.text:
        return
    media_id = publish(video, post["text"])
    post["ig_posted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    post["ig_media_id"] = media_id
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Reels опубликован: {media_id}")


if __name__ == "__main__":
    main()
