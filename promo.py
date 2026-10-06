"""Reels в промо-стиле Kelechek AI (HyperFrames: HTML + GSAP -> MP4).

Тёмный тёплый фон, 3D-телефоны, стеклянные карточки, жёлтые теги с точкой,
субтитр со второй половиной жёлтым и подчёркиванием, финал с логотипом.
Каждая фраза сценария получает свою сцену по смыслу (переписка, ролики,
запись, встреча, услуги, крупный текст), соседние сцены не повторяются,
содержимое сцен каждый раз случайное. Только музыка, без звуковых эффектов.

  python promo.py "текст сценария" out/promo.mp4
"""
import html
import json
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
HF_ASSETS = HERE / "assets" / "hf"
HF_VERSION = "0.8.121"
END = 3.0  # финальная карточка с логотипом

KEYWORDS = {
    "chat": ["ответ", "вопрос", "пиш", "whatsapp", "директ", "сообщ", "сколько стоит", "клиент"],
    "fan": ["reels", "ролик", "видео", "instagram", "пост", "контент", "сним", "съём", "монтаж", "камер", "реклам"],
    "booking": ["запис", "брон", "свободн", "окн"],
    "laptop": ["лично", "встреч", "ноутбук", "показ", "отчёт", "отчет", "excel", "бишкек"],
}
TAGS = {
    "chat": ["Клиент пишет ночью", "ИИ отвечает сразу", "WhatsApp", "Direct", "Без ожидания"],
    "fan": ["Reels", "Instagram", "Threads", "Без съёмки", "Каждый день"],
    "booking": ["Сайт для записи", "24/7", "Без звонков"],
    "laptop": ["Бишкек", "Встреча лично", "Отчёт в Excel"],
    "cards": ["Автоматизация", "ИИ-видео", "Для бизнеса", "Бишкек"],
    "big": ["Kelechek AI"],
}
QUESTIONS = ["Здравствуйте, сколько стоит?", "А вы сегодня работаете?", "Есть запись на завтра?",
             "Где вы находитесь?", "Можно узнать цену?", "Есть свободное время вечером?",
             "Доставка есть?", "Вы ещё открыты?"]
ANSWERS = ["Здравствуйте! Я ИИ-помощник, отвечу сразу. Что вас интересует?",
           "Добрый вечер! Подскажите, на какой день вам удобно?",
           "Здравствуйте! Сейчас всё подскажу. Как вас зовут?",
           "Да, отвечаю сразу. Передам владельцу вашу заявку, он напишет лично.",
           "Добрый вечер! Пришлю варианты прямо сюда."]
FOLLOW = ["Отлично, спасибо!", "Супер, жду", "Да, давайте", "Хорошо 👍".replace(" 👍", "")]
CARDS = [("Ответы 24/7", "в WhatsApp и Direct"), ("Reels", "без съёмки"), ("Заявки", "сразу в таблицу"),
         ("Отчёт", "каждую неделю в Excel"), ("Посты", "каждый день"), ("Запись", "клиент сам выбирает время"),
         ("Встреча", "лично в Бишкеке"), ("15 дней", "бесплатно"), ("Монтаж", "в вашем стиле")]
DECOR = ["ring", "wave", "bars", "dots", ""]

CSS = """
@font-face { font-family: Unbounded; src: url(./Unbounded-Bold.ttf); font-weight: 700; }
@font-face { font-family: Golos; src: url(./GolosText-Medium.ttf); font-weight: 500; }
@font-face { font-family: Golos; src: url(./GolosText-Regular.ttf); font-weight: 400; }
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 1080px; height: 1920px; overflow: hidden; background: #0B0907; }
#root { position: relative; width: 100%; height: 100%; overflow: hidden; font-family: Golos, sans-serif; color: #fff; }
.bg { position: absolute; inset: 0; background: radial-gradient(90% 60% at 50% 42%, #2B1F10 0%, #15100A 45%, #0B0907 80%); }
.glow { position: absolute; width: 900px; height: 900px; left: 90px; top: 420px; border-radius: 50%; background: radial-gradient(circle, rgba(255,190,80,.16), rgba(255,190,80,0) 65%); }
.streak { position: absolute; width: 1400px; height: 2px; left: -160px; background: linear-gradient(90deg, transparent, rgba(255,214,140,.22), transparent); transform: rotate(-24deg); }
.vig { position: absolute; inset: 0; background: radial-gradient(120% 90% at 50% 45%, transparent 55%, rgba(0,0,0,.75)); }
.tags { position: absolute; top: 170px; left: 0; right: 0; display: flex; justify-content: center; gap: 44px; font-weight: 500; font-size: 34px; }
.tag { display: flex; align-items: center; gap: 14px; }
.tag i { width: 14px; height: 14px; border-radius: 50%; background: #FFC23D; box-shadow: 0 0 14px #FFC23D; }
.stage { position: absolute; inset: 0; perspective: 2200px; }
.phone { position: absolute; width: 470px; height: 960px; left: 305px; top: 300px; border-radius: 74px; background: #121214; padding: 14px;
         box-shadow: 0 0 0 3px #3A3A3E, 0 0 0 5px #0d0d0f, 0 60px 120px rgba(0,0,0,.6), inset 0 0 0 2px rgba(255,255,255,.08); transform-style: preserve-3d; }
.screen { width: 100%; height: 100%; border-radius: 62px; background: #F4F1EA; overflow: hidden; position: relative; color: #1C1C1E; }
.screen > img { width: 100%; height: 100%; object-fit: cover; object-position: top; display: block; }
.island { position: absolute; top: 18px; left: 50%; width: 130px; height: 38px; margin-left: -65px; background: #000; border-radius: 20px; z-index: 3; }
.sbar { height: 70px; padding: 22px 40px 0; display: flex; justify-content: space-between; font-size: 22px; font-weight: 500; }
.chead { display: flex; align-items: center; gap: 16px; padding: 14px 26px 18px; border-bottom: 1px solid #E3DED3; }
.chead img { width: 58px; height: 58px; border-radius: 50%; background: #111; }
.chead b { font-size: 25px; display: block; }
.chead span { font-size: 19px; color: #2B7D44; }
.chat { padding: 26px 22px; display: flex; flex-direction: column; gap: 18px; }
.msg { max-width: 82%; padding: 18px 22px; border-radius: 26px; font-size: 25px; line-height: 1.32; }
.msg small { display: block; text-align: right; font-size: 16px; opacity: .55; margin-top: 6px; }
.in { background: #fff; align-self: flex-start; border-bottom-left-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,.06); }
.out { background: #FFC23D; align-self: flex-end; border-bottom-right-radius: 8px; }
.typing { align-self: flex-end; background: #FFE29E; padding: 18px 24px; border-radius: 26px; display: flex; gap: 8px; }
.typing i { width: 12px; height: 12px; border-radius: 50%; background: #8A6A1E; }
.cards { position: absolute; left: 70px; right: 70px; top: 420px; display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
.card { height: 300px; border-radius: 40px; padding: 34px 36px; background: linear-gradient(160deg, rgba(255,255,255,.20), rgba(255,255,255,.06));
        border: 1.5px solid rgba(255,255,255,.22); box-shadow: 0 30px 60px rgba(0,0,0,.45); position: relative; overflow: hidden; }
.card h3 { font-family: Unbounded, sans-serif; font-size: 46px; line-height: 1.05; }
.card p { font-size: 28px; color: #E9E2D2; margin-top: 12px; line-height: 1.3; }
.ring { position: absolute; right: 30px; bottom: 30px; width: 96px; height: 96px; }
.bars { position: absolute; left: 36px; right: 36px; bottom: 30px; height: 70px; display: flex; align-items: flex-end; gap: 12px; }
.bars i { flex: 1; background: #FFC23D; border-radius: 6px; transform-origin: bottom; }
.dots { position: absolute; left: 36px; bottom: 36px; display: flex; gap: 14px; }
.dots i { width: 24px; height: 24px; border-radius: 50%; background: #FFC23D; }
.wave { position: absolute; left: 30px; right: 30px; bottom: 26px; height: 70px; }
.mini { position: absolute; width: 330px; height: 680px; top: 420px; border-radius: 56px; padding: 11px; background: #121214; box-shadow: 0 0 0 3px #3A3A3E, 0 50px 90px rgba(0,0,0,.6); }
.mini .screen { border-radius: 46px; }
.tile { margin: 18px; border-radius: 22px; background: #fff; padding: 18px; font-size: 21px; line-height: 1.3; box-shadow: 0 2px 6px rgba(0,0,0,.06); }
.tile b { display: block; font-size: 21px; margin-bottom: 6px; }
.reel { margin: 18px; height: 440px; border-radius: 26px; background: linear-gradient(170deg, #2B1F10, #0B0907); display: flex; align-items: center; justify-content: center; text-align: center;
        font-family: Unbounded, sans-serif; color: #fff; font-size: 26px; line-height: 1.25; padding: 20px; }
.reel em { color: #FFC23D; font-style: normal; }
.demo { position: absolute; top: 250px; left: 0; right: 0; text-align: center; font-size: 22px; color: #BDB3A0; }
.laptop { position: absolute; left: 90px; top: 470px; width: 900px; }
.lscreen { height: 560px; border-radius: 30px 30px 0 0; background: #121214; padding: 16px; box-shadow: 0 0 0 3px #3A3A3E, 0 50px 90px rgba(0,0,0,.6); }
.lin { height: 100%; border-radius: 16px; background: #F4F1EA; color: #1C1C1E; padding: 30px 34px; display: grid; grid-template-columns: 1fr 1fr 1fr; grid-template-rows: auto 1fr; gap: 20px; }
.lin h4 { grid-column: 1 / 4; font-family: Unbounded, sans-serif; font-size: 32px; display: flex; align-items: center; gap: 16px; }
.lin h4 img { width: 48px; height: 48px; border-radius: 12px; }
.lcell { background: #fff; border-radius: 20px; padding: 22px; font-size: 24px; display: flex; flex-direction: column; justify-content: space-between; }
.lcell .bars { position: static; height: 150px; }
.lbase { height: 34px; margin: 0 -50px; border-radius: 0 0 30px 30px; background: linear-gradient(#3A3A3E, #1d1d20); }
.pin { position: absolute; right: 120px; top: 1120px; background: #FFC23D; color: #1A1206; font-weight: 500; font-size: 32px; padding: 16px 30px; border-radius: 999px; }
.bigt { position: absolute; left: 70px; right: 70px; top: 520px; font-family: Unbounded, sans-serif; font-size: 92px; line-height: 1.1; }
.bigt .w { display: inline-block; margin-right: .22em; }
.bigt em { font-style: normal; color: #FFC23D; }
.sub { position: absolute; left: 60px; right: 60px; bottom: 300px; text-align: center; font-family: Unbounded, sans-serif; font-size: 52px; line-height: 1.25; }
.sub.s { font-size: 44px; }
.sub u { color: #FFC23D; text-decoration: none; background: linear-gradient(#FFC23D, #FFC23D) left bottom / var(--w, 0%) 5px no-repeat; padding-bottom: 6px; }
.end { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.brand { display: flex; align-items: center; gap: 28px; font-family: Unbounded, sans-serif; font-size: 84px; }
.brand img { width: 130px; height: 130px; border-radius: 34px; }
.slogan { font-size: 38px; color: #D9CFBD; margin-top: 34px; }
.pills { display: flex; gap: 22px; margin-top: 50px; }
.pill { font-size: 32px; padding: 16px 34px; border-radius: 999px; border: 1.5px solid rgba(255,255,255,.3); }
.pill.y { background: #FFC23D; color: #1A1206; border-color: #FFC23D; font-weight: 500; }
.disc { position: absolute; bottom: 140px; left: 0; right: 0; text-align: center; font-size: 24px; color: #8E826D; }
"""

EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def esc(s):
    return html.escape(s, quote=False)


def paragraphs(text):
    paras = [EMOJI.sub("", p).strip() for p in text.split("\n\n")]
    return [p for p in paras if p and "wa.me" not in p and "опубликован автоматически" not in p][:6]


def kind_for(text):
    low = text.lower()
    for kind, words in KEYWORDS.items():
        if any(w in low for w in words):
            return kind
    return "cards"


def split_sub(text):
    """Субтитр: первая половина белым, вторая жёлтым с подчёркиванием."""
    words = text.replace("\n", " ").split()
    if len(words) < 3:
        return esc(" ".join(words)), ""
    cut = (len(words) + 1) // 2
    return esc(" ".join(words[:cut])), esc(" ".join(words[cut:]))


def duration(text):
    return round(min(5.5, max(3.0, 1.6 + 0.055 * len(text))), 2)


def stamp(rng):
    return f"{rng.randint(21, 23)}:{rng.randint(0, 59):02d}"


# ---------- сцены: html и анимация ----------

def scene_chat(i, text, rng, t, d):
    quoted = re.findall(r"«([^»]{3,60}\?)»", text)
    q = quoted[0].capitalize() if quoted else text if text.endswith("?") and len(text) < 80 else rng.choice(QUESTIONS)
    ts = stamp(rng)
    h = f"""<div class="phone" id="p{i}"><div class="screen"><div class="island"></div>
      <div class="sbar"><span>{ts}</span><span>●●● 5G</span></div>
      <div class="chead"><img src="./logo.png" /><div><b>ИИ-помощник</b><span>онлайн</span></div></div>
      <div class="chat"><div class="msg in" id="a{i}">{esc(q)}<small>{ts}</small></div>
        <div class="typing" id="y{i}"><i></i><i></i><i></i></div>
        <div class="msg out" id="b{i}">{esc(rng.choice(ANSWERS))}<small>{ts}</small></div>
        <div class="msg in" id="c{i}">{esc(rng.choice(FOLLOW))}<small>{ts}</small></div></div></div></div>
      <div class="demo">пример переписки</div>"""
    ry = rng.choice([-38, 38])
    js = f"""
tl.fromTo("#p{i}", {{rotationY: {ry}, rotationX: 8, scale: .78, opacity: 0, filter: "blur(18px)"}}, {{rotationY: {-ry // 4}, rotationX: 2, scale: 1, opacity: 1, filter: "blur(0px)", duration: 1, ease: "expo.out"}}, {t})
  .to("#p{i}", {{rotationY: {ry // 5}, duration: {d - 1.2:.2f}, ease: "sine.inOut"}}, {t + 1})
  .from("#a{i}", {{opacity: 0, y: 30, scale: .9, transformOrigin: "left bottom", duration: .4, ease: "power3.out"}}, {t + .5})
  .from("#y{i}", {{opacity: 0, scale: .6, transformOrigin: "right bottom", duration: .25}}, {t + 1})
  .to("#y{i} i", {{y: -8, duration: .16, yoyo: true, repeat: 3, stagger: .07}}, {t + 1.05})
  .to("#y{i}", {{height: 0, padding: 0, opacity: 0, duration: .15}}, {t + 1.6})
  .from("#b{i}", {{opacity: 0, y: 30, scale: .9, transformOrigin: "right bottom", duration: .45, ease: "power3.out"}}, {t + 1.65})
  .from("#c{i}", {{opacity: 0, y: 30, scale: .9, transformOrigin: "left bottom", duration: .4, ease: "power3.out"}}, {t + 2.4});"""
    return h, js


def decor(kind, i, k):
    if kind == "ring":
        return (f'<svg class="ring" viewBox="0 0 100 100"><circle cx="50" cy="50" r="42" stroke="rgba(255,255,255,.18)" stroke-width="10" fill="none"/>'
                f'<circle id="r{i}_{k}" cx="50" cy="50" r="42" stroke="#FFC23D" stroke-width="10" fill="none" stroke-linecap="round" stroke-dasharray="264" stroke-dashoffset="264" transform="rotate(-90 50 50)"/></svg>')
    if kind == "wave":
        return (f'<svg class="wave" viewBox="0 0 300 80"><path id="w{i}_{k}" d="M0 70 C40 60 60 30 100 40 S160 70 200 35 S260 10 300 15" stroke="#FFC23D" '
                f'stroke-width="5" fill="none" stroke-linecap="round" stroke-dasharray="420" stroke-dashoffset="420"/></svg>')
    if kind == "bars":
        return '<div class="bars">' + "".join(f'<i style="height:{h}%"></i>' for h in (30, 45, 38, 60, 52, 74, 66, 90)) + "</div>"
    if kind == "dots":
        return '<div class="dots"><i></i><i></i><i></i><i></i></div>'
    return ""


def scene_cards(i, text, rng, t, d):
    picks = rng.sample(CARDS, 4)
    decs = rng.sample(DECOR, 4)
    cards = "".join(f'<div class="card"><h3>{esc(a)}</h3><p>{esc(b)}</p>{decor(decs[k], i, k)}</div>' for k, (a, b) in enumerate(picks))
    h = f'<div class="cards" id="g{i}">{cards}</div>'
    dx = rng.choice([700, -700])
    js = f"""
tl.from("#g{i} .card", {{x: {dx}, rotationY: {-30 if dx > 0 else 30}, opacity: 0, filter: "blur(16px)", stagger: .12, duration: .7, ease: "expo.out"}}, {t})
  .to("#g{i}", {{y: -24, duration: {d - .8:.2f}, ease: "sine.inOut"}}, {t + .8})
  .from("#g{i} .bars i", {{scaleY: 0, stagger: .05, duration: .4, ease: "back.out(2)"}}, {t + .7})
  .from("#g{i} .dots i", {{scale: 0, stagger: .08, duration: .3, ease: "back.out(3)"}}, {t + .7});"""
    for k, dk in enumerate(decs):
        if dk == "ring":
            js += f'\ntl.to("#r{i}_{k}", {{attr: {{"stroke-dashoffset": {rng.randint(20, 90)}}}, duration: 1.1, ease: "power2.out"}}, {t + .7});'
        if dk == "wave":
            js += f'\ntl.to("#w{i}_{k}", {{attr: {{"stroke-dashoffset": 0}}, duration: 1.2, ease: "power2.out"}}, {t + .7});'
    return h, js


def scene_fan(i, text, rng, t, d):
    words = text.split()
    head = esc(" ".join(words[:3]))
    tail = esc(" ".join(words[3:7]))
    tiles = rng.sample(["Клиент написал в 23:40. ИИ ответил сразу.", "Новый Reels для меню готов к публикации.",
                        "Пост на сегодня уже в очереди.", "Заявка из Direct попала в таблицу.",
                        "Монтаж в стиле вашего бренда.", "Ответ на комментарий отправлен."], 3)
    h = f"""<div class="mini" id="f{i}a" style="left:40px"><div class="screen"><div class="sbar"><span>9:07</span><span>●●●</span></div>
        <div class="tile"><b>kelechek_ai</b>{tiles[0]}</div><div class="tile"><b>kelechek_ai</b>{tiles[1]}</div></div></div>
      <div class="mini" id="f{i}b" style="left:375px; top:470px"><div class="screen"><div class="sbar"><span>19:07</span><span>●●●</span></div>
        <div class="reel"><div>{head}<br><em>{tail}</em></div></div></div></div>
      <div class="mini" id="f{i}c" style="left:710px"><div class="screen"><div class="sbar"><span>13:07</span><span>●●●</span></div>
        <div class="tile" style="background:#FFC23D">{tiles[2]}</div><div class="tile">Сделано с помощью ИИ</div></div></div>"""
    js = f"""
tl.from("#f{i}a", {{x: 300, rotation: -14, opacity: 0, filter: "blur(14px)", duration: .7, ease: "expo.out"}}, {t})
  .from("#f{i}b", {{y: 300, scale: .8, opacity: 0, filter: "blur(14px)", duration: .7, ease: "expo.out"}}, {t + .1})
  .from("#f{i}c", {{x: -300, rotation: 14, opacity: 0, filter: "blur(14px)", duration: .7, ease: "expo.out"}}, {t + .2})
  .to("#f{i}a", {{rotation: -7, y: 40, duration: {d - 1.2:.2f}, ease: "sine.inOut"}}, {t + .95})
  .to("#f{i}c", {{rotation: 7, y: 40, duration: {d - 1.2:.2f}, ease: "sine.inOut"}}, {t + .95})
  .to("#f{i}b", {{y: -30, duration: {d - 1.2:.2f}, ease: "sine.inOut"}}, {t + .95});"""
    return h, js


def scene_booking(i, text, rng, t, d):
    h = f"""<div class="phone" id="k{i}a" style="left:90px;top:360px;width:420px;height:860px;border-radius:66px"><div class="screen" style="border-radius:54px"><img src="./c2.jpg" /></div></div>
      <div class="phone" id="k{i}b" style="left:570px;top:330px;width:420px;height:860px;border-radius:66px"><div class="screen" style="border-radius:54px"><img src="./o1.jpg" /></div></div>
      <div class="demo">пример на демо-сайте</div>"""
    js = f"""
tl.fromTo("#k{i}a", {{x: -500, rotationY: 40, opacity: 0, filter: "blur(14px)"}}, {{x: 0, rotationY: 10, rotation: -4, opacity: 1, filter: "blur(0px)", duration: .8, ease: "expo.out"}}, {t})
  .fromTo("#k{i}b", {{x: 500, rotationY: -40, opacity: 0, filter: "blur(14px)"}}, {{x: 0, rotationY: -10, rotation: 4, opacity: 1, filter: "blur(0px)", duration: .8, ease: "expo.out"}}, {t + .25})
  .to("#k{i}a", {{y: 30, duration: {d - 1:.2f}, ease: "sine.inOut"}}, {t + .9})
  .to("#k{i}b", {{y: -30, duration: {d - 1:.2f}, ease: "sine.inOut"}}, {t + .9});"""
    return h, js


def scene_laptop(i, text, rng, t, d):
    h = f"""<div class="laptop" id="l{i}"><div class="lscreen"><div class="lin">
        <h4><img src="./logo.png" />Ваш бизнес</h4>
        <div class="lcell"><b>Заявки</b><div class="bars">{"".join(f'<i style="height:{x}%"></i>' for x in rng.sample(range(25, 95, 7), 6))}</div></div>
        <div class="lcell"><b>Reels</b><span>план на неделю</span></div>
        <div class="lcell"><b>Ответы</b><span>WhatsApp и Direct</span></div>
      </div></div><div class="lbase"></div></div>
      <div class="pin" id="n{i}">● Бишкек</div>"""
    js = f"""
tl.from("#l{i}", {{rotationX: 50, y: 200, scale: .8, opacity: 0, filter: "blur(16px)", transformOrigin: "50% 100%", duration: .9, ease: "expo.out"}}, {t})
  .from("#l{i} .lcell", {{y: 40, opacity: 0, stagger: .12, duration: .45, ease: "power3.out"}}, {t + .6})
  .from("#l{i} .bars i", {{scaleY: 0, stagger: .05, duration: .4, ease: "back.out(2)"}}, {t + .9})
  .from("#n{i}", {{scale: 0, opacity: 0, duration: .45, ease: "back.out(2.5)"}}, {t + 1.1})
  .to("#l{i}", {{y: -20, duration: {d - 1:.2f}, ease: "sine.inOut"}}, {t + .9});"""
    return h, js


def scene_big(i, text, rng, t, d):
    words = text.split()
    cut = max(1, len(words) - max(1, len(words) // 3))
    spans = " ".join(f'<span class="w">{esc(w)}</span>' for w in words[:cut])
    spans += " " + " ".join(f'<span class="w"><em>{esc(w)}</em></span>' for w in words[cut:])
    size = 92 if len(text) < 45 else 72 if len(text) < 80 else 58
    h = f'<div class="bigt" id="t{i}" style="font-size:{size}px">{spans}</div>'
    js = f"""
tl.from("#t{i} .w", {{opacity: 0, y: 40, filter: "blur(12px)", stagger: .09, duration: .45, ease: "power3.out"}}, {t + .1})
  .to("#t{i}", {{scale: 1.05, duration: {d - .6:.2f}, ease: "sine.inOut", transformOrigin: "0% 50%"}}, {t + .5});"""
    return h, js


SCENES = {"chat": scene_chat, "cards": scene_cards, "fan": scene_fan, "booking": scene_booking,
          "laptop": scene_laptop, "big": scene_big}
SPARE = ["cards", "fan", "chat", "big"]  # если смысл сцены совпал с предыдущей, берём другую


def compose(text, seed=None):
    rng = random.Random(seed)
    paras = paragraphs(text)
    clips, js, t, prev = [], [], 0.0, None
    for i, p in enumerate(paras):
        d = duration(p)
        kind = kind_for(p)
        if i == 0 and kind == "cards":
            kind = "big"  # хук крупным текстом, если в нём нет предмета для сцены
        if kind == prev:
            kind = rng.choice([k for k in SPARE if k != prev])
        prev = kind
        h, s = SCENES[kind](i, p, rng, round(t, 2), d)
        tags = "".join(f'<div class="tag"><i></i>{esc(x)}</div>' for x in rng.sample(TAGS[kind], min(2, len(TAGS[kind]))))
        clips.append(f'<div class="tags clip" id="tg{i}" data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="2">{tags}</div>')
        clips.append(f'<div class="stage clip" id="sc{i}" data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="1">{h}</div>')
        js.append(s)
        js.append(f'tl.from("#tg{i} .tag", {{opacity: 0, y: -20, stagger: .1, duration: .4, ease: "power3.out"}}, {t + .15:.2f});')
        js.append(f'tl.to("#sc{i}", {{x: {rng.choice([-500, 500])}, opacity: 0, filter: "blur(18px)", duration: .3, ease: "power3.in"}}, {t + d - .3:.2f});')
        if kind != "big":
            a, b = split_sub(p)
            cls = "sub s" if len(p) > 70 else "sub"
            clips.append(f'<div class="{cls} clip" id="u{i}" data-start="{t + .3:.2f}" data-duration="{d - .3:.2f}" data-track-index="3">{a}<br><u id="ul{i}">{b}</u></div>')
            js.append(f'tl.from("#u{i}", {{opacity: 0, y: 40, duration: .45, ease: "power3.out"}}, {t + .3:.2f})'
                      f'.to("#ul{i}", {{"--w": "100%", duration: .5, ease: "power2.out"}}, {t + .9:.2f})'
                      f'.to("#u{i}", {{opacity: 0, filter: "blur(10px)", duration: .25}}, {t + d - .3:.2f});')
        t += d
    total = round(t + END, 2)
    clips.append(f"""<div class="end clip" id="fin" data-start="{t:.2f}" data-duration="{END}" data-track-index="1">
        <div class="brand" id="brand"><img src="./logo.png" />Kelechek AI</div>
        <div class="slogan" id="slogan">ИИ-видео и автоматизация для бизнеса</div>
        <div class="pills"><div class="pill">Бишкек</div><div class="pill y">Написать в WhatsApp</div></div>
        <div class="disc">Ролик сделан с помощью ИИ</div></div>""")
    js.append(f"""tl.from("#brand", {{scale: .6, opacity: 0, filter: "blur(16px)", duration: .7, ease: "expo.out"}}, {t + .05:.2f})
  .from("#slogan", {{opacity: 0, y: 24, duration: .5, ease: "power3.out"}}, {t + .45:.2f})
  .from(".pill", {{opacity: 0, y: 30, stagger: .1, duration: .45, ease: "power3.out"}}, {t + .7:.2f})
  .to(".pill.y", {{scale: 1.06, duration: .35, yoyo: true, repeat: 3, ease: "sine.inOut"}}, {t + 1.3:.2f})
  .from(".disc", {{opacity: 0, duration: .4}}, {t + 1:.2f});""")
    page = f"""<!doctype html>
<html lang="ru" data-resolution="portrait"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" /><script src="./gsap.min.js"></script>
<style>{CSS}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
<div class="bg"></div><div class="glow" id="glow"></div>
<div class="streak" id="st1" style="top:520px"></div><div class="streak" id="st2" style="top:1380px"></div><div class="vig"></div>
{chr(10).join(clips)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.to("#glow", {{ x: 120, y: -160, scale: 1.15, duration: {total}, ease: "sine.inOut" }}, 0)
  .fromTo("#st1", {{ x: -500 }}, {{ x: 600, duration: {total}, ease: "none" }}, 0)
  .fromTo("#st2", {{ x: 500 }}, {{ x: -600, duration: {total}, ease: "none" }}, 0);
{chr(10).join(js)}
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
tl.seek(0);
</script></body></html>"""
    return page, total


def render(text, music, out, seed=None, workdir=None):
    """Собирает ролик: HTML-композиция -> MP4 через HyperFrames, затем музыка через ffmpeg."""
    work = Path(workdir or HERE / "out" / "hf")
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(HF_ASSETS, work)
    page, total = compose(text, seed)
    (work / "index.html").write_text(page, encoding="utf-8")
    (work / "meta.json").write_text(json.dumps({"id": "reel", "name": "reel"}), encoding="utf-8")
    silent = work / "silent.mp4"
    r = subprocess.run(["npx", "--yes", f"hyperframes@{HF_VERSION}", "render", "-o", str(silent)], cwd=work,
                       capture_output=True, text=True)
    if r.returncode or not silent.exists():
        print((r.stdout + r.stderr)[-3000:])
        raise RuntimeError("HyperFrames не собрал ролик")
    fade = max(0.0, total - 1.5)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(music), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-af", f"afade=t=in:d=0.5,afade=t=out:st={fade:.2f}:d=1.5,volume=0.8", "-shortest", str(out)], check=True)
    return total


if __name__ == "__main__":
    music = sorted((HERE / "assets" / "music").glob("*.mp3"))[0]
    print(render(sys.argv[1], music, Path(sys.argv[2])))
