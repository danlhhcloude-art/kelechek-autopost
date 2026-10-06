"""Публикация в страницу Facebook: те же посты, что в Threads, и те же Reels, что в Instagram.

Нужен секрет FB_ACCESS_TOKEN: долгоживущий токен пользователя Facebook с правами
pages_show_list, pages_read_engagement, pages_manage_posts (и instagram_basic, business_management
для разбора конкурентов). Токен страницы получаем из него сами. Если страниц несколько, укажи FB_PAGE_ID.
Без токена всё молча пропускается: Threads и Instagram работают как раньше.

  python fb.py --whoami     # какая страница видна токену
"""
import os
import sys
import time

import requests

API = "https://graph.facebook.com/v22.0"


def enabled():
    return bool(os.environ.get("FB_ACCESS_TOKEN"))


def page():
    """(id, name, page_token) страницы, в которую публикуем."""
    r = requests.get(f"{API}/me/accounts", timeout=30,
                     params={"fields": "id,name,access_token", "access_token": os.environ["FB_ACCESS_TOKEN"]})
    r.raise_for_status()
    pages = r.json().get("data", [])
    want = os.environ.get("FB_PAGE_ID")
    for p in pages:
        if not want or p["id"] == want:
            return p["id"], p["name"], p["access_token"]
    raise RuntimeError("Токен не видит ни одной страницы Facebook (нужны права pages_show_list и pages_manage_posts)")


def post(text, image_urls=()):
    """Текст, одна картинка или альбом из нескольких. Возвращает id поста."""
    pid, _, token = page()
    if len(image_urls) == 1:
        r = requests.post(f"{API}/{pid}/photos", timeout=60,
                          data={"url": image_urls[0], "caption": text, "access_token": token})
        r.raise_for_status()
        return r.json().get("post_id") or r.json()["id"]
    data = {"message": text, "access_token": token}
    for k, url in enumerate(image_urls[:10]):
        r = requests.post(f"{API}/{pid}/photos", timeout=60, data={"url": url, "published": "false", "access_token": token})
        r.raise_for_status()
        data[f"attached_media[{k}]"] = '{"media_fbid":"%s"}' % r.json()["id"]
    r = requests.post(f"{API}/{pid}/feed", timeout=60, data=data)
    r.raise_for_status()
    return r.json()["id"]


def reel(video_url, description):
    """Reels на странице: start -> загрузка по ссылке -> finish с публикацией."""
    pid, _, token = page()
    r = requests.post(f"{API}/{pid}/video_reels", timeout=60, data={"upload_phase": "start", "access_token": token})
    r.raise_for_status()
    video_id, upload_url = r.json()["video_id"], r.json()["upload_url"]
    r = requests.post(upload_url, timeout=120, headers={"Authorization": f"OAuth {token}", "file_url": video_url})
    r.raise_for_status()
    for _ in range(30):  # ждём, пока Facebook скачает видео
        s = requests.get(f"{API}/{video_id}", timeout=30, params={"fields": "status", "access_token": token}).json()
        phase = s.get("status", {}).get("uploading_phase", {}).get("status")
        if phase == "complete":
            break
        if phase == "error":
            raise RuntimeError(f"Facebook не принял видео: {s}")
        time.sleep(5)
    r = requests.post(f"{API}/{pid}/video_reels", timeout=60, data={
        "upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
        "description": description, "access_token": token})
    r.raise_for_status()
    return video_id


def safe(fn, *args):
    """Сбой Facebook не должен ломать публикацию в Threads и Instagram."""
    if not enabled():
        return None
    try:
        out = fn(*args)
        print(f"Facebook: опубликовано {out}")
        return out
    except Exception as e:
        print(f"Facebook: не получилось ({e})")
        return None


if __name__ == "__main__":
    if "--whoami" in sys.argv:
        pid, name, _ = page()
        print(f"Страница: {name} ({pid})")
