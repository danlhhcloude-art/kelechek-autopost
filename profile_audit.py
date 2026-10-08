"""Снимок профилей Instagram и Threads для скилла account-advisor.

Собирает то, что видит новый посетитель профиля (имя, био, ссылка, аватар, число постов)
и недельную статистику аккаунта. Пишет profile.json (без токенов и без данных клиентов).

  python profile_audit.py
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

HERE = Path(__file__).parent
OUT = HERE / "profile.json"
TH_API = "https://graph.threads.net/v1.0"
IG_API = "https://graph.instagram.com/v22.0"


def get(url, **params):
    try:
        r = requests.get(url, params=params, timeout=30)
        data = r.json()
    except Exception as e:  # сеть или не-JSON
        return {"error": str(e)[:200]}
    if not r.ok:
        return {"error": (data.get("error") or {}).get("message", r.text[:200])}
    return data


def total(items):
    return {m["name"]: (m.get("total_value") or {}).get("value", sum(v.get("value", 0) for v in m.get("values", [])))
            for m in items}


def threads(token):
    out = {"profile": get(f"{TH_API}/me", fields="username,name,threads_biography,threads_profile_picture_url", access_token=token)}
    since = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    r = get(f"{TH_API}/me/threads_insights", metric="views,likes,replies,reposts,quotes,followers_count", since=since,
            access_token=token)
    out["week"] = total(r.get("data", [])) if "data" in r else r
    return out


def instagram(token):
    out = {"profile": get(f"{IG_API}/me", fields="username,name,biography,website,followers_count,follows_count,media_count,"
                                                 "profile_picture_url", access_token=token)}
    since = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())
    r = get(f"{IG_API}/me/insights", metric="reach,views,profile_views,accounts_engaged,total_interactions,website_clicks",
            period="day", metric_type="total_value", since=since, until=int(datetime.now(timezone.utc).timestamp()),
            access_token=token)
    out["week"] = total(r.get("data", [])) if "data" in r else r
    media = get(f"{IG_API}/me/media", fields="media_type,caption,timestamp,permalink,like_count,comments_count", limit=12,
                access_token=token)
    out["recent"] = [{"type": m.get("media_type"), "at": m.get("timestamp"), "url": m.get("permalink"),
                      "caption": (m.get("caption") or "")[:120], "likes": m.get("like_count"), "comments": m.get("comments_count")}
                     for m in media.get("data", [])]
    return out


def main():
    snap = {"updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if os.environ.get("THREADS_ACCESS_TOKEN"):
        snap["threads"] = threads(os.environ["THREADS_ACCESS_TOKEN"])
    if os.environ.get("IG_ACCESS_TOKEN"):
        snap["instagram"] = instagram(os.environ["IG_ACCESS_TOKEN"])
    OUT.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for k in ("threads", "instagram"):
        p = snap.get(k, {}).get("profile", {})
        print(k, p.get("username") or p.get("error"), "| неделя:", snap.get(k, {}).get("week"))


if __name__ == "__main__":
    main()
