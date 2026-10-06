"""Скачивает бодрую бесплатную музыку для Reels в assets/music/upbeat.

Источник FreePD.com: музыка в общественном достоянии (CC0), можно без указания автора.
Берём разделы с энергичными треками, режем до 60 секунд (ролики короче) и сохраняем в mp3.
Уже скачанные треки не трогаем, так что запуск можно повторять, чтобы пополнить библиотеку.

  python tools/fetch_music.py [сколько_с_раздела]
"""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests

HERE = Path(__file__).resolve().parent.parent
DEST = HERE / "assets" / "music" / "upbeat"
HOME = "https://freepd.com/"
MOODS = ["upbeat", "happy", "electronic", "comedy", "funk", "pop", "world", "fun", "dance", "positive"]


def category_pages():
    """Ищем разделы на главной FreePD и ставим вперёд бодрые по названию."""
    r = requests.get(HOME, headers=UA, timeout=30)
    LOG.append(f"{HOME} -> {r.status_code}, {len(r.text)} байт")
    hrefs = re.findall(r"""href\s*=\s*["']([^"'#]+)["']""", r.text, re.I)
    pages = []
    for h in hrefs:
        u = urljoin(HOME, h)
        if "freepd.com" in u and not u.lower().endswith((".mp3", ".css", ".js", ".png", ".jpg", ".ico")) and u.rstrip("/") != HOME.rstrip("/"):
            pages.append(u)
    pages = list(dict.fromkeys(pages))
    LOG.append("разделы: " + ", ".join(pages[:60]))
    happy = [u for u in pages if any(m in u.lower() for m in MOODS)]
    return happy or pages[:12]
LOG = []
UA = {"User-Agent": "Mozilla/5.0 (kelechek-autopost music fetch)"}


def links(page):
    r = requests.get(page, headers=UA, timeout=30)
    html = r.text
    LOG.append(f"{page} -> {r.status_code}, {len(html)} байт, начало: {html[:400]!r}")
    found = re.findall(r"""(?:href|src|data-src)\s*=\s*["']([^"']+\.mp3)["']""", html, re.I)
    found += re.findall(r"""["']((?:https?://freepd\.com)?/?music/[^"']+\.mp3)["']""", html, re.I)
    return list(dict.fromkeys(urljoin(page, u) for u in found))


def slug(url):
    name = unquote(url.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    per_page = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    DEST.mkdir(parents=True, exist_ok=True)
    have = {p.stem for p in DEST.glob("*.mp3")}
    added = []
    for page in category_pages():
        try:
            urls = links(page)
        except requests.RequestException as e:
            LOG.append(f"{page}: не открылась ({e})")
            print(f"{page}: не открылась ({e})")
            continue
        print(f"{page}: нашёл {len(urls)} треков")
        LOG.append(f"  ссылок на mp3: {len(urls)} {urls[:3]}")
        n = 0
        for url in urls:
            if n >= per_page:
                break
            name = f"freepd-{slug(url)}"
            if name in have:
                continue
            raw = DEST / f"{name}.src.mp3"
            try:
                r = requests.get(url, headers=UA, timeout=60)
                r.raise_for_status()
                raw.write_bytes(r.content)
                subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(raw), "-t", "60", "-ac", "2",
                                "-ar", "44100", "-b:a", "128k", str(DEST / f"{name}.mp3")], check=True)
                added.append(f"{name}.mp3  <-  {url}")
                n += 1
            except Exception as e:
                LOG.append(f"  пропускаю {url}: {e}")
                print(f"пропускаю {url}: {e}")
            finally:
                raw.unlink(missing_ok=True)
    credits = DEST / "SOURCES.md"
    old = credits.read_text(encoding="utf-8") if credits.exists() else "# Музыка для Reels\n\nFreePD.com, общественное достояние (CC0).\n\n"
    credits.write_text(old + "".join(f"- {a}\n" for a in added), encoding="utf-8")
    print(f"Добавлено треков: {len(added)}")
    (DEST / "fetch-log.txt").write_text("\n".join(LOG + [f"добавлено: {len(added)}"]) + "\n", encoding="utf-8")
    if not added and not have:
        sys.exit("Не удалось скачать ни одного трека")


if __name__ == "__main__":
    main()
