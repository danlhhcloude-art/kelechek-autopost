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
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import freshness
import media
import motion
import promo

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
OUT = HERE / "out"
POSTS_FILE = HERE / "posts.json"
SCRIPTS_FILE = HERE / "reels.json"  # отдельные сценарии для Reels, чтобы текст роликов не повторял посты
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


def load_scripts():
    return json.loads(SCRIPTS_FILE.read_text(encoding="utf-8")) if SCRIPTS_FILE.exists() else []


USED_MUSIC_FILE = HERE / "used_music.json"
music_credit = ""  # автор трека текущего ролика (CC BY требует подписи), попадает в подписи Instagram и Threads


def credit_for(track):
    try:
        return json.loads((track.parent / "credits.json").read_text(encoding="utf-8")).get(track.name, "")
    except (OSError, ValueError):
        return ""


def used_music():
    try:
        return json.loads(USED_MUSIC_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def mark_music_used(track):
    used = [x for x in used_music() if x != track.name] + [track.name]
    USED_MUSIC_FILE.write_text(json.dumps(used, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


def pick_music(n=0):
    """Каждому ролику свой трек: сначала бодрые из assets/music/upbeat, которых ещё не было,
    когда все прозвучали, берём тот, что звучал давнее всего. Спокойный эмбиент только если бодрых нет."""
    tracks = sorted((ASSETS / "music" / "upbeat").glob("*.mp3")) or sorted((ASSETS / "music").glob("*.mp3"))
    age = {x: k for k, x in enumerate(used_music())}
    random.shuffle(tracks)
    return min(tracks, key=lambda t: age.get(t.name, -1))


def live_footage(text, query=None):
    """Два живых клипа со стока для промо-ролика: под хук и под вторую фразу. Без сети ролик собирается без них."""
    try:
        paras = [p for p in text.split("\n\n") if p.strip()]
        queries = [media.scene_query(p) for p in paras[:2]]
        return media.clips_for_shots(queries, query or media.scene_query(text) or media.DEFAULT_QUERY, OUT / "stock")
    except Exception as e:
        print(f"Живые кадры не найдены ({e}), собираю без них")
        return []


def build_reel(text, music=None, query=None):
    OUT.mkdir(exist_ok=True)
    out = OUT / "reel.mp4"
    if os.environ.get("REEL_STYLE", "promo") == "promo":
        # промо-стиль с телефонами и стеклянными карточками (одобрен 06.10.2026); при сбое собираем старым способом
        try:
            total = promo.render(text, music or pick_music(0), out, footage=live_footage(text, query))
            print(f"Ролик собран в промо-стиле: {out} ({total:.1f} сек)")
            return out
        except Exception as e:
            print(f"Промо-стиль не собрался ({e}), собираю старым способом")
    total, n = motion.render(split_slides(text) + [("cta", "")], music or pick_music(0), out, query=query)
    print(f"Ролик собран: {out} ({total:.1f} сек, слайдов: {n})")
    return out


def caption(text):
    body = re.sub(r"(Пиши|Пишите)?[^\n]*wa\.me/\S+", "", text).strip()
    footer = ("\n\n👉 Пиши в WhatsApp, ссылка в профиле, или на номер " + CONTACT +
              "\n📍 В Бишкеке встречаемся лично и показываем всё вживую" +
              "\n\n🤖 Ролик смонтирован и опубликован автоматически. Так же можем и для вашего бизнеса.")
    music = f"\n🎵 Музыка: {music_credit}" if music_credit else ""
    return f"{body}{footer}{music}\n\n{HASHTAGS}"[:2200]


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
    global last_video_url
    video_url = last_video_url = host_on_github(video)
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


last_video_url = None  # ссылка на выложенный ролик, чтобы тот же Reels вышел и в Threads


def share_to_threads(text):
    """Тот же ролик дублируем в Threads как видео-пост (если есть токен Threads)."""
    import autopost
    if not (os.environ.get("THREADS_ACCESS_TOKEN") and os.environ.get("THREADS_USER_ID") and last_video_url):
        return None
    user_id, token = os.environ["THREADS_USER_ID"], os.environ["THREADS_ACCESS_TOKEN"]
    body = re.sub(r"\n*#\S+(\s+#\S+)*\s*$", "", text).strip()
    if music_credit:
        body += f"\n\n🎵 Музыка: {music_credit}"
    data = {"media_type": "VIDEO", "video_url": last_video_url, "text": autopost.with_footer(body),
            "topic_tag": "Reels", "access_token": token}
    try:
        r = requests.post(f"{autopost.API}/{user_id}/threads", data=data, timeout=60)
        r.raise_for_status()
        container = r.json()["id"]
        autopost.wait_ready(container, token)
        r = requests.post(f"{autopost.API}/{user_id}/threads_publish", timeout=60,
                          data={"creation_id": container, "access_token": token})
        r.raise_for_status()
        print(f"Ролик выложен и в Threads: {r.json()['id']}")
        return r.json()["id"]
    except Exception as e:  # Instagram уже опубликован, сбой Threads не должен ронять запуск
        print(f"В Threads ролик не вышел: {e}")
        return None


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


def collect_stats():
    """Статистика Reels в stats.json (раздел instagram): просмотры, охват, лайки, комментарии, сохранения."""
    token = need("IG_ACCESS_TOKEN")
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    stats_file = HERE / "stats.json"
    stats = json.loads(stats_file.read_text(encoding="utf-8")) if stats_file.exists() else {}
    rows = []
    for p in posts:
        if not p.get("ig_media_id"):
            continue
        row = {"ig_media_id": p["ig_media_id"], "posted_at": p["ig_posted_at"], "topic": p.get("topic"),
               "text": p["text"][:90]}
        r = requests.get(f"{IG_API}/{p['ig_media_id']}", timeout=30,
                         params={"fields": "like_count,comments_count,permalink", "access_token": token})
        if r.ok:
            d = r.json()
            row.update(likes=d.get("like_count", 0), comments=d.get("comments_count", 0), url=d.get("permalink"))
        r = requests.get(f"{IG_API}/{p['ig_media_id']}/insights", timeout=30,
                         params={"metric": "views,reach,saved,shares", "access_token": token})
        if r.ok:
            row.update({m["name"]: m["values"][0]["value"] for m in r.json().get("data", [])})
        else:
            print(f"Insights недоступны для {p['ig_media_id']}: {r.status_code} {r.text[:200]}")
        rows.append(row)
    stats["instagram"] = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reels": rows}
    stats_file.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Статистика Instagram: {len(rows)} роликов")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="собрать статистику Reels в stats.json")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--text", help="собрать ролик из этого текста вместо очереди")
    ap.add_argument("--query", help="что искать на стоке для фона (по умолчанию по теме поста)")
    ap.add_argument("--test", action="store_true", help="собрать следующий ролик и выложить в media/ для просмотра, без публикации")
    args = ap.parse_args()
    if args.stats:
        return collect_stats()

    if not (args.render_only or args.text or args.test) and not os.environ.get("IG_ACCESS_TOKEN"):
        print("Instagram ещё не подключён (нет секрета IG_ACCESS_TOKEN), пропускаю.")
        return
    posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    scripts = load_scripts()
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not (args.render_only or args.text or args.test):
        # если ролик уже выложили вручную (страховка), плановый запуск второй за день не публикует
        stamps = [datetime.fromisoformat(x["ig_posted_at"]) for x in posts + scripts if x.get("ig_posted_at")]
        if stamps and datetime.now(timezone.utc) - max(stamps) < timedelta(hours=12):
            print(f"Reels уже вышел в {max(stamps):%H:%M} UTC, сегодняшний слот закрыт.")
            return
    published = {p["text"] for p in posts if p.get("ig_posted_at")} | {s["text"] for s in scripts if s.get("ig_posted_at")}
    seen = freshness.published(posts, scripts)
    fresh = freshness.fresh_only([s for s in scripts if not s.get("ig_posted_at") and s["text"] not in published], seen, "Reels: ")
    if args.text:
        post = {"text": args.text}
    elif fresh:
        # отдельный сценарий для Reels: каждый день новый текст, а тестовые превью берут случайный
        post = random.choice(fresh) if args.test else fresh[0]
    else:
        queue = freshness.fresh_only([p for p in posts if not p.get("ig_posted_at") and p["text"] not in published], seen, "Reels: ")
        if not queue:
            sys.exit("Нет нового текста для Reels: добавь сценарии в reels.json")
        post = random.choice(queue) if args.test else queue[0]
        print("reels.json пуст, беру текст поста из posts.json")
    query = args.query or post.get("query") or media.TOPIC_QUERIES.get(post.get("topic"), media.DEFAULT_QUERY)
    global music_credit
    music = pick_music()
    music_credit = credit_for(music)
    print(f"Музыка: {music.name} {music_credit}")
    video = build_reel(post["text"], music, query)
    if args.test:
        host_on_github(video)
        return
    if args.render_only or args.text:
        return
    media_id = publish(video, post.get("caption") or post["text"])
    threads_id = share_to_threads(post["text"])
    import fb  # и на страницу Facebook как Reels
    fb_id = fb.safe(fb.reel, last_video_url, caption(post.get("caption") or post["text"]))
    # пока собирался ролик, posts.json мог обновиться (git pull при выкладке видео),
    # поэтому перечитываем файл и отмечаем только свой пост, чтобы не затереть чужие отметки
    from_scripts = "caption" in post
    path = SCRIPTS_FILE if from_scripts else POSTS_FILE
    items = json.loads(path.read_text(encoding="utf-8"))
    item = next(p for p in items if p["text"] == post["text"])
    item["ig_posted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    item["ig_media_id"] = media_id
    if threads_id:
        item["threads_video_id"] = threads_id
    if fb_id:
        item["fb_video_id"] = fb_id
    media.mark_clips_used(media.picked_clips)  # эти фоны больше не повторяем
    mark_music_used(music)  # и этот трек тоже
    promo.mark_used(promo.picked)  # и эти фразы тоже
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Reels опубликован: {media_id}")


if __name__ == "__main__":
    main()
