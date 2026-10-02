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

import motion

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
OUT = HERE / "out"
POSTS_FILE = HERE / "posts.json"
IG_VERSION = "v22.0"
IG_API = f"https://graph.instagram.com/{IG_VERSION}"
CONTACT = motion.CONTACT
HASHTAGS = "#бишкек #кыргызстан #ии #нейросети #иивидео #автоматизациябизнеса #reels"

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


def pick_music(n):
    """Треки из assets/music (бесплатные, Pixabay) идут по кругу: каждый следующий ролик со следующим треком."""
    tracks = sorted((ASSETS / "music").glob("*.mp3"))
    return tracks[n % len(tracks)]


def build_reel(text, music=None):
    OUT.mkdir(exist_ok=True)
    out = OUT / "reel.mp4"
    total, n = motion.render(split_slides(text) + [("cta", "")], music or pick_music(0), out)
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
