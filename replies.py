"""Ответы на комментарии в Threads.

  python replies.py --collect   # собрать новые комментарии под нашими постами в Threads и Instagram в comments.json
  python replies.py --answer    # отправить ответы из переменной REPLIES:
                                # JSON-список [{"to": "<id комментария>", "text": "..."}]
                                # комментарии Instagram хранятся с префиксом "ig:" и поле platform = "instagram"

Ответы пишет Claude (по расписанию в проекте) и передаёт их сюда через запуск workflow.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from autopost import API, load_env, load_posts, need

HERE = Path(__file__).parent
COMMENTS_FILE = HERE / "comments.json"
OWN_USERNAME = "kelechek_ai"
IG_API = "https://graph.instagram.com/v22.0"
IG_PREFIX = "ig:"
LOOKBACK_DAYS = 14
REPLY_MARK = "\n\n🤖 ответил ИИ-ассистент Kelechek AI"
MAX_LEN = 500


def load_comments():
    return json.loads(COMMENTS_FILE.read_text(encoding="utf-8")) if COMMENTS_FILE.exists() else {}


def save_comments(comments):
    COMMENTS_FILE.write_text(json.dumps(comments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect():
    token = need("THREADS_ACCESS_TOKEN")
    comments = load_comments()
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    new = 0
    for p in load_posts():
        if not p.get("threads_id") or datetime.fromisoformat(p["posted_at"]) < since:
            continue
        r = requests.get(f"{API}/{p['threads_id']}/conversation", timeout=30, params={
            "fields": "id,text,username,timestamp,replied_to", "access_token": token})
        if not r.ok:
            sys.exit(f"Не удалось получить комментарии: {r.status_code} {r.text[:300]}")
        for c in r.json().get("data", []):
            if c.get("username") == OWN_USERNAME or c["id"] in comments:
                continue
            comments[c["id"]] = {
                "post_id": p["threads_id"], "post_topic": p.get("topic"),
                "replied_to": (c.get("replied_to") or {}).get("id"),
                "username": c.get("username"), "text": c.get("text", ""),
                "timestamp": c.get("timestamp"), "answered_at": None, "answer_id": None}
            new += 1
    new += collect_instagram(comments, since)
    save_comments(comments)
    waiting = sum(1 for c in comments.values() if not c["answered_at"])
    print(f"Новых комментариев: {new}, ждут ответа: {waiting}")


def collect_instagram(comments, since):
    """Комментарии под нашими Reels. Без токена или права на комментарии просто пропускаем."""
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        return 0
    new = 0
    for p in load_posts():
        if not p.get("ig_media_id") or datetime.fromisoformat(p["ig_posted_at"]) < since:
            continue
        r = requests.get(f"{IG_API}/{p['ig_media_id']}/comments", timeout=30, params={
            "fields": "id,text,username,timestamp,replies{id,text,username,timestamp}", "access_token": token})
        if not r.ok:
            print(f"Instagram: не удалось получить комментарии: {r.status_code} {r.text[:300]}")
            return new
        for c in r.json().get("data", []):
            items = [(c, None)] + [(x, c["id"]) for x in (c.get("replies") or {}).get("data", [])]
            for item, parent in items:
                key = IG_PREFIX + item["id"]
                if item.get("username") == OWN_USERNAME or key in comments:
                    continue
                comments[key] = {
                    "platform": "instagram", "post_id": p["ig_media_id"], "post_topic": p.get("topic"),
                    "replied_to": parent, "username": item.get("username"), "text": item.get("text", ""),
                    "timestamp": item.get("timestamp"), "answered_at": None, "answer_id": None}
                new += 1
    return new


def reply_instagram(comment_id, text):
    # в Instagram отвечаем на верхний комментарий ветки, иначе API не принимает
    token = need("IG_ACCESS_TOKEN")
    text = text.strip()[:MAX_LEN - len(REPLY_MARK)] + REPLY_MARK
    r = requests.post(f"{IG_API}/{comment_id}/replies", timeout=30, data={"message": text, "access_token": token})
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    return r.json()["id"]


def reply(to_id, text):
    user_id, token = need("THREADS_USER_ID"), need("THREADS_ACCESS_TOKEN")
    text = text.strip()[:MAX_LEN - len(REPLY_MARK)] + REPLY_MARK
    r = requests.post(f"{API}/{user_id}/threads", timeout=30, data={
        "media_type": "TEXT", "text": text, "reply_to_id": to_id, "access_token": token})
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    time.sleep(5)
    r = requests.post(f"{API}/{user_id}/threads_publish", timeout=30,
                      data={"creation_id": r.json()["id"], "access_token": token})
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    return r.json()["id"]


def answer():
    items = json.loads(os.environ.get("REPLIES") or "[]")
    comments = load_comments()
    failed = 0
    for it in items:
        c = comments.get(it["to"])
        if c and c["answered_at"]:
            print(f"{it['to']}: уже отвечен, пропускаю")
            continue
        try:
            if it["to"].startswith(IG_PREFIX):
                target = (c or {}).get("replied_to") or it["to"][len(IG_PREFIX):]
                answer_id = reply_instagram(target, it["text"])
            else:
                answer_id = reply(it["to"], it["text"])
        except RuntimeError as e:
            print(f"{it['to']}: не удалось ответить: {e}")
            failed += 1
            continue
        if c is not None:
            c["answered_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            c["answer_id"] = answer_id
        print(f"{it['to']}: ответ опубликован {answer_id}")
    save_comments(comments)
    if failed:
        sys.exit(f"Не отправлено ответов: {failed}")


def skip():
    comments = load_comments()
    for cid in json.loads(os.environ.get("SKIP") or "[]"):
        if cid in comments and not comments[cid]["answered_at"]:
            comments[cid]["answered_at"] = "skipped"
    save_comments(comments)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--answer", action="store_true")
    args = ap.parse_args()
    load_env()
    if args.answer:
        skip()
        answer()
    if args.collect:
        collect()


if __name__ == "__main__":
    main()
