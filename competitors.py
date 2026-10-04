"""Сбор публичных цифр конкурентов через Instagram Business Discovery (API Meta).

Нужен секрет FB_ACCESS_TOKEN: токен пользователя Facebook с правами instagram_basic,
pages_show_list, pages_read_engagement, business_management. Наш Instagram должен быть
привязан к странице Facebook. Конкурент должен быть бизнес- или авторским аккаунтом
(у личных аккаунтов Meta цифры не отдаёт).

  python competitors.py            # собрать цифры по competitors.json -> competitors_stats.json
  python competitors.py --whoami   # показать, к какому Instagram привязан токен
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).parent
API = "https://graph.facebook.com/v22.0"
LIST_FILE = HERE / "competitors.json"         # {"K001": ["username1", ...], "kelechek": [...]}
STATS_FILE = HERE / "competitors_stats.json"  # история замеров, дописывается


def ig_user_id(token):
    """ID нашего Instagram-бизнес-аккаунта через привязанную страницу Facebook."""
    r = requests.get(f"{API}/me/accounts", timeout=30,
                     params={"fields": "name,instagram_business_account{id,username}", "access_token": token})
    if not r.ok:
        sys.exit(f"Не удалось получить страницы: {r.status_code} {r.text[:300]}")
    for page in r.json().get("data", []):
        ig = page.get("instagram_business_account")
        if ig:
            return ig["id"], ig.get("username"), page.get("name")
    sys.exit("Токен не видит Instagram, привязанный к странице Facebook. Проверь привязку и права токена.")


def discover(token, me, username):
    fields = ("business_discovery.username(%s){username,name,followers_count,follows_count,media_count,"
              "media.limit(12){timestamp,like_count,comments_count,media_type,permalink,caption}}" % username)
    r = requests.get(f"{API}/{me}", timeout=30, params={"fields": fields, "access_token": token})
    if not r.ok:
        return {"username": username, "error": r.json().get("error", {}).get("message", r.text[:200])}
    d = r.json()["business_discovery"]
    media = d.get("media", {}).get("data", [])
    likes = [m.get("like_count") or 0 for m in media]
    top = sorted(media, key=lambda m: -((m.get("like_count") or 0) + 3 * (m.get("comments_count") or 0)))[:3]
    return {
        "username": d.get("username"), "name": d.get("name"), "followers": d.get("followers_count"),
        "media_count": d.get("media_count"),
        "avg_likes_last12": round(sum(likes) / len(likes), 1) if likes else None,
        "avg_comments_last12": round(sum(m.get("comments_count") or 0 for m in media) / len(media), 1) if media else None,
        "top_posts": [{"url": m.get("permalink"), "type": m.get("media_type"), "likes": m.get("like_count"),
                       "comments": m.get("comments_count"), "caption": (m.get("caption") or "")[:200]} for m in top],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--whoami", action="store_true")
    args = ap.parse_args()
    token = os.environ.get("FB_ACCESS_TOKEN")
    if not token:
        sys.exit("Нет FB_ACCESS_TOKEN")
    me, me_name, page = ig_user_id(token)
    print(f"Токен работает: Instagram @{me_name} (id {me}), страница «{page}»")
    if args.whoami:
        return
    lists = json.loads(LIST_FILE.read_text(encoding="utf-8")) if LIST_FILE.exists() else {}
    history = json.loads(STATS_FILE.read_text(encoding="utf-8")) if STATS_FILE.exists() else []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for client, names in lists.items():
        for name in names:
            res = discover(token, me, name.lstrip("@"))
            history.append({"date": now, "client": client, **res})
            print(f"{client} @{name}: " + (res.get("error") or f"{res['followers']} подписчиков, {res['media_count']} публикаций"))
    STATS_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
