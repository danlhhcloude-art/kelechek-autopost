"""Защита от повторов (владелец, 2026-10-07: «каждый день новый ролик и пост о чём-то новом, никак не повтор»).
Тема и смысл каждого поста и ролика публикуются один раз. Посты Threads и сценарии Reels проверяются вместе,
потому что Reels тоже уходят в Threads."""
import re

LIMIT = 0.28          # доля общих корней слов, выше которой текст считается повтором
FREE_TOPICS = {None, "", "generated"}


def stems(text):
    return {w[:5] for w in re.findall(r"[а-яёa-z]{5,}", text.lower())}


def similarity(a, b):
    sa, sb = stems(a), stems(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def published(posts, reels=()):
    """Всё, что уже видели подписчики."""
    return [p for p in posts if p.get("posted_at") or p.get("ig_posted_at")] + [r for r in reels if r.get("ig_posted_at")]


def repeat_reason(item, seen):
    """Почему этот текст повтор, или None, если он свежий."""
    topic = item.get("topic")
    for old in seen:
        if old is item:
            continue
        if topic not in FREE_TOPICS and old.get("topic") == topic:
            return f"тема «{topic}» уже была"
        sim = similarity(item["text"], old["text"])
        if sim > LIMIT:
            return f"похоже на «{old['text'][:40]}…» ({sim:.2f})"
    return None


def fresh_only(queue, seen, label=""):
    """Очередь без повторов; повторы помечаются полем skipped, чтобы их не брать снова."""
    out = []
    for item in queue:
        why = item.get("skipped") or repeat_reason(item, seen)
        if why:
            if not item.get("skipped"):
                item["skipped"] = why
                print(f"{label}пропускаю повтор: {why}")
            continue
        out.append(item)
    return out


if __name__ == "__main__":
    # проверка очереди: python freshness.py
    import json
    posts = json.load(open("posts.json", encoding="utf-8"))
    reels = json.load(open("reels.json", encoding="utf-8"))
    seen = published(posts, reels)
    queued = [("пост", p) for p in posts if not p.get("posted_at")] + [("reels", r) for r in reels if not r.get("ig_posted_at")]
    bad = 0
    for k, (kind, item) in enumerate(queued):
        why = repeat_reason(item, seen + [x for _, x in queued[:k]])
        if why:
            bad += 1
            print(f"{kind} {item.get('topic')}: {why}")
    print(f"В очереди {len(queued)}, повторов {bad}")
    raise SystemExit(1 if bad else 0)
