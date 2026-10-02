"""Автопостинг в Threads: берёт следующий пост из posts.json,
а когда очередь пуста, просит Claude написать новый.

Запуск:
  python autopost.py            # опубликовать один пост
  python autopost.py --dry-run  # показать пост, ничего не публикуя
  python autopost.py --generate 10  # дописать в очередь 10 новых постов от Claude
  python autopost.py --refresh-token  # продлить токен Threads ещё на 60 дней
  python autopost.py --stats    # собрать статистику постов и аккаунта в stats.json
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API = "https://graph.threads.net/v1.0"
HERE = Path(__file__).parent
POSTS_FILE = HERE / "posts.json"
STATS_FILE = HERE / "stats.json"
POST_METRICS = ["views", "likes", "replies", "reposts", "quotes"]
MAX_LEN = 500  # лимит символов Threads
AUTO_FOOTER = "\n\n🤖 Пост опубликован автоматически. Так же можем и для вашего бизнеса."

OFFER = """Аудитория: малый и средний бизнес Бишкека и Кыргызстана (позже вся Центральная Азия). Языки клиентов: русский и кыргызский.
Аккаунт новый, портфолио собирается публично: по мере появления проектов показываю процесс и результаты.

Кто я и что предлагаю:
- Делаю ИИ-видеоролики (реклама, рилсы, презентации товара, аватары-ведущие) и автоматизацию бизнеса
  (чат-боты, обработка заявок, автопостинг, связка CRM/таблиц/мессенджеров через ИИ).
- Опыт есть, публичного портфолио пока нет, поэтому предлагаю честный формат:
  клиент оплачивает только подписку на ИИ-сервис, который я назову, и 15 дней смотрит на мою работу бесплатно.
  Понравился результат — продолжаем работать за фиксированную оплату. Не понравился — расходимся без долгов.
- С клиентами из Бишкека встречаюсь лично: показываю всё вживую на ноутбуке, чтобы не было лишних вопросов."""


def load_env():
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def need(name):
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Не задана переменная {name} (см. .env.example)")
    return val


def load_posts():
    return json.loads(POSTS_FILE.read_text(encoding="utf-8"))


def save_posts(posts):
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate(n, existing):
    import anthropic

    client = anthropic.Anthropic(api_key=need("ANTHROPIC_API_KEY"))
    recent = "\n---\n".join(p["text"] for p in existing[-15:])
    contact = os.environ.get("CONTACT_LINE", "Пиши в WhatsApp: wa.me/996502091443?text=Threads")
    prompt = f"""{OFFER}

Напиши {n} разных постов для Threads на русском от первого лица.
Требования:
- каждый пост не длиннее 400 символов (к нему автоматически добавится подпись об автопубликации), живой разговорный тон, без канцелярита и без хэштегов-простыней (максимум 1 хэштег);
- первая строка — провокационный крючок: смелое мнение, неудобный вопрос или вызов («Непопулярное мнение:», «Вы платите зарплату за копипаст»), чтобы пост попадал в рекомендации;
- большинство постов заканчивай вопросом или призывом поспорить в комментариях;
- провокация без оскорблений, без выдуманной статистики и без нападок на конкретные компании или людей;
- чередуй темы: ИИ-видео, автоматизация бизнеса, оффер «15 дней на оценку», полезный совет/пример, вопрос к аудитории;
- не выдумывай клиентов, кейсы, цифры и отзывы: портфолио пока нет, говори об этом честно;
- примерно в половине постов в конце призыв: «{contact}».
Не повторяй эти уже написанные посты:
{recent}

Ответь только JSON-массивом строк, без пояснений."""
    msg = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = raw[raw.find("["): raw.rfind("]") + 1]
    texts = [t.strip() for t in json.loads(raw) if t.strip()]
    return [{"text": t[:MAX_LEN], "topic": "generated", "posted_at": None} for t in texts]


def with_footer(text):
    if AUTO_FOOTER.strip() in text:
        return text
    return text[:MAX_LEN - len(AUTO_FOOTER)].rstrip() + AUTO_FOOTER


def publish(text):
    user_id = need("THREADS_USER_ID")
    token = need("THREADS_ACCESS_TOKEN")
    r = requests.post(f"{API}/{user_id}/threads",
                      data={"media_type": "TEXT", "text": text, "access_token": token}, timeout=30)
    r.raise_for_status()
    creation_id = r.json()["id"]
    time.sleep(5)  # Meta советует подождать перед публикацией контейнера
    r = requests.post(f"{API}/{user_id}/threads_publish",
                      data={"creation_id": creation_id, "access_token": token}, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def refresh_token():
    r = requests.get("https://graph.threads.net/refresh_access_token",
                     params={"grant_type": "th_refresh_token", "access_token": need("THREADS_ACCESS_TOKEN")},
                     timeout=30)
    r.raise_for_status()
    data = r.json()
    print("Новый токен (вставь его вместо старого):")
    print(data["access_token"])
    print(f"Действует ещё {data.get('expires_in', 0) // 86400} дней")


def metric_values(items):
    out = {}
    for m in items:
        if "total_value" in m:
            out[m["name"]] = m["total_value"].get("value", 0)
        else:
            out[m["name"]] = sum(v.get("value", 0) for v in m.get("values", []))
    return out


def collect_stats():
    user_id = need("THREADS_USER_ID")
    token = need("THREADS_ACCESS_TOKEN")
    stats = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "account": {}, "posts": []}
    r = requests.get(f"{API}/{user_id}/threads_insights", timeout=30, params={
        "metric": ",".join(POST_METRICS + ["followers_count"]), "access_token": token})
    if r.ok:
        stats["account"] = metric_values(r.json().get("data", []))
    else:
        print(f"Статистика аккаунта недоступна: {r.status_code} {r.text[:200]}")
    for p in load_posts():
        if not p.get("threads_id"):
            continue
        row = {"threads_id": p["threads_id"], "posted_at": p["posted_at"], "topic": p.get("topic"),
               "text": p["text"].split("\n")[0][:90]}
        r = requests.get(f"{API}/{p['threads_id']}/insights", timeout=30, params={
            "metric": ",".join(POST_METRICS), "access_token": token})
        if r.ok:
            row.update(metric_values(r.json().get("data", [])))
        else:
            print(f"Нет статистики для {p['threads_id']}: {r.status_code}")
        stats["posts"].append(row)
    STATS_FILE.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Статистика сохранена: {len(stats['posts'])} постов, аккаунт: {stats['account']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--generate", type=int, metavar="N")
    ap.add_argument("--refresh-token", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()
    load_env()

    if args.refresh_token:
        return refresh_token()
    if args.stats:
        return collect_stats()

    posts = load_posts()
    if args.generate:
        new = generate(args.generate, posts)
        save_posts(posts + new)
        print(f"Добавлено постов: {len(new)}")
        return

    queue = [p for p in posts if not p.get("posted_at")]
    if not queue:
        print("Очередь пуста, прошу Claude написать новые посты...")
        posts += generate(7, posts)
        queue = [p for p in posts if not p.get("posted_at")]

    post = queue[0]
    text = with_footer(post["text"])
    if args.dry_run:
        print(f"[dry-run] {len(text)} симв.:\n{text}")
        return
    post_id = publish(text)
    post["posted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    post["threads_id"] = post_id
    save_posts(posts)
    print(f"Опубликовано: {post_id}. В очереди осталось: {len(queue) - 1}")


if __name__ == "__main__":
    main()
