"""Скачивает бодрую музыку для Reels в assets/music/upbeat.

Источник: Kevin MacLeod, incompetech.com, лицензия CC BY 4.0 (можно в коммерческих роликах,
нужно указать автора). Подпись к каждому треку лежит в credits.json, reels.py добавляет её
в подпись ролика. Треки режем до 60 секунд: ролики короче. Уже скачанные не трогаем.

  python tools/fetch_music.py
"""
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import requests

HERE = Path(__file__).resolve().parent.parent
DEST = HERE / "assets" / "music" / "upbeat"
BASE = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
# бодрые, позитивные, без «грустного» эмбиента
TITLES = ["Carefree", "Wallpaper", "Life of Riley", "Hyperfun", "Funkorama", "Easy Lemon", "Inspired",
          "Getting it Done", "Daily Beetle", "Happy Alley", "Groove Grove", "Local Forecast - Elevator",
          "Cheery Monday", "Breaktime", "Lobby Time", "Pamgaea", "Werq", "Funk Game Loop", "Vivacity",
          "Rollin at 5", "Upbeat Forever", "Sunny Disposition", "Bright Wish", "Comic Bit", "Fretless",
          "Hot Swing", "Overworld", "Fun in a Bottle", "On the Ground", "Electro Cabello"]
UA = {"User-Agent": "Mozilla/5.0 (kelechek-autopost music fetch)"}


def slug(title):
    return "kmacleod-" + "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-").replace("--", "-")


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    credits_file = DEST / "credits.json"
    credits = json.loads(credits_file.read_text(encoding="utf-8")) if credits_file.exists() else {}
    log = []
    for title in TITLES:
        name = slug(title) + ".mp3"
        if (DEST / name).exists():
            continue
        url = BASE + quote(title) + ".mp3"
        raw = DEST / "_src.mp3"
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code != 200 or not r.content[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
                log.append(f"нет: {title} ({r.status_code})")
                continue
            raw.write_bytes(r.content)
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(raw), "-t", "60", "-ac", "2",
                            "-ar", "44100", "-b:a", "128k", str(DEST / name)], check=True)
            credits[name] = f"«{title}» Kevin MacLeod (incompetech.com), CC BY 4.0"
            log.append(f"ок: {title}")
        except Exception as e:
            log.append(f"ошибка: {title}: {e}")
        finally:
            raw.unlink(missing_ok=True)
    credits_file.write_text(json.dumps(credits, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DEST / "fetch-log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    if not credits:
        sys.exit("Не удалось скачать ни одного трека")


if __name__ == "__main__":
    main()
