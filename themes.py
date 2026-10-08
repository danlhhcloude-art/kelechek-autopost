"""Стили оформления промо-роликов: каждый день новый вид, без повторов подряд.

Стиль = палитра и шрифты (THEMES) + узор фона, вид субтитра и переход между сценами.
Палитра подменяет фирменные цвета базового стиля «Ночь и золото» во всём HTML ролика,
поэтому новые сцены в promo.py автоматически перекрашиваются, если пишут цвета
так же, как базовый стиль (#FFC23D, rgba(255,194,61,...) и т. д.).
used_styles.json помнит, какие стили уже выходили: сначала берутся давно не показанные,
и ни одна из четырёх частей не повторяет вчерашний ролик.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
USED_FILE = HERE / "used_styles.json"
USED_KEEP = 60

# цвета базового стиля -> ключ палитры
BASE = {
    "#FFC23D": "acc", "#1A1206": "ink", "#FFE29E": "soft", "#8A6A1E": "deep",
    "#0B0907": "bg0", "#15100A": "bg1", "#2B1F10": "bg2", "#3A2A12": "bg3", "#FFF4DC": "flash",
    "#F4F1EA": "paper", "#E9E2D2": "m1", "#E0D6C3": "m1", "#D9CFBD": "m1", "#BDB3A0": "m2", "#B9AF9E": "m2", "#8E826D": "m3",
    "rgba(255,194,61,": "acc_rgb", "rgba(255,190,80,": "glow_rgb", "rgba(255,214,140,": "line_rgb", "rgba(11,9,7,": "bg_rgb",
}

FONTS = {
    "Unbounded": "@font-face { font-family: Unbounded; src: url(./Unbounded-Bold.ttf); font-weight: 700; }",
    "Dela": "@font-face { font-family: Dela; src: url(./DelaGothicOne-Regular.ttf); font-weight: 400 900; }",
    "Russo": "@font-face { font-family: Russo; src: url(./RussoOne-Regular.ttf); font-weight: 400 900; }",
    "Playfair": "@font-face { font-family: Playfair; src: url(./PlayfairDisplay.ttf); font-weight: 400 900; }",
    "Oswald": "@font-face { font-family: Oswald; src: url(./Oswald.ttf); font-weight: 200 700; }",
    "Montserrat": "@font-face { font-family: Montserrat; src: url(./Montserrat.ttf); font-weight: 100 900; }",
    "Manrope": "@font-face { font-family: Manrope; src: url(./Manrope.ttf); font-weight: 200 800; }",
    "Rubik": "@font-face { font-family: Rubik; src: url(./Rubik.ttf); font-weight: 300 900; }",
    "Golos": "",  # уже подключён в базовом CSS
}

THEMES = [
    {"id": "gold", "paper": "#F4F1EA", "name": "Ночь и золото", "head": "Unbounded", "body": "Golos", "radius": 40, "extra": "",
     "pal": {"acc": "#FFC23D", "ink": "#1A1206", "soft": "#FFE29E", "deep": "#8A6A1E", "bg0": "#0B0907", "bg1": "#15100A",
             "bg2": "#2B1F10", "bg3": "#3A2A12", "flash": "#FFF4DC", "m1": "#E4DCCB", "m2": "#BAB09D", "m3": "#8E826D",
             "acc_rgb": "255,194,61", "glow_rgb": "255,190,80", "line_rgb": "255,214,140", "bg_rgb": "11,9,7"}},
    {"id": "neon", "paper": "#EEF3FB", "name": "Неон", "head": "Russo", "body": "Manrope", "radius": 28,
     "extra": ".bigt { font-size: 86px; } .sub u, .bigt em { text-shadow: 0 0 26px rgba(61,242,255,.55); }",
     "pal": {"acc": "#3DF2FF", "ink": "#03161C", "soft": "#B4FAFF", "deep": "#127A86", "bg0": "#04061A", "bg1": "#0A0F33",
             "bg2": "#18205C", "bg3": "#22307A", "flash": "#E6FDFF", "m1": "#D4DDF5", "m2": "#9AA6CC", "m3": "#6C77A0",
             "acc_rgb": "61,242,255", "glow_rgb": "140,90,255", "line_rgb": "61,242,255", "bg_rgb": "4,6,26"}},
    {"id": "emerald", "paper": "#EFF5EE", "name": "Изумруд", "head": "Montserrat", "body": "Manrope", "radius": 34,
     "extra": ".bigt, .card h3, .col h3, .sub, .brand, .lin h4, .reel, .adimg, .aud h3 { font-weight: 800; }",
     "pal": {"acc": "#B6FF5C", "ink": "#102004", "soft": "#E0FFB8", "deep": "#4E7A1A", "bg0": "#030D08", "bg1": "#071A12",
             "bg2": "#0F3324", "bg3": "#164532", "flash": "#F3FFE6", "m1": "#D7E8DC", "m2": "#9DB8A6", "m3": "#6F8C79",
             "acc_rgb": "182,255,92", "glow_rgb": "60,220,150", "line_rgb": "182,255,92", "bg_rgb": "3,13,8"}},
    {"id": "berry", "paper": "#F8EEF2", "name": "Бордо", "head": "Playfair", "body": "Rubik", "radius": 46,
     "extra": ".bigt, .card h3, .col h3, .sub, .brand, .lin h4, .reel, .adimg, .aud h3 { font-weight: 800; }"
              " .bigt { font-size: 98px; } .sub { font-size: 58px; } .sub.s { font-size: 50px; } .bigt em, .sub u { font-style: italic; }",
     "pal": {"acc": "#FF6FB1", "ink": "#2A0716", "soft": "#FFC6E0", "deep": "#9C2F63", "bg0": "#100308", "bg1": "#1F0812",
             "bg2": "#3B0F24", "bg3": "#511633", "flash": "#FFEAF3", "m1": "#F0D9E3", "m2": "#C3A1B0", "m3": "#94707F",
             "acc_rgb": "255,111,177", "glow_rgb": "255,90,140", "line_rgb": "255,160,200", "bg_rgb": "16,3,8"}},
    {"id": "cobalt", "paper": "#EEF1FB", "name": "Кобальт", "head": "Dela", "body": "Rubik", "radius": 18,
     "extra": ".bigt { font-size: 76px; line-height: 1.18; } .sub { font-size: 46px; line-height: 1.4; } .sub.s { font-size: 40px; }"
              " .card h3 { font-size: 40px; } .brand { font-size: 70px; }",
     "pal": {"acc": "#FFE14D", "ink": "#1C1800", "soft": "#FFF2A8", "deep": "#8C7A12", "bg0": "#03082A", "bg1": "#0A1A6E",
             "bg2": "#1634B8", "bg3": "#1E44E0", "flash": "#FFFBE0", "m1": "#DCE3FF", "m2": "#A4B2EE", "m3": "#7584C4",
             "acc_rgb": "255,225,77", "glow_rgb": "90,140,255", "line_rgb": "255,240,170", "bg_rgb": "3,8,42"}},
    {"id": "sunset", "paper": "#F8F0E9", "name": "Закат", "head": "Oswald", "body": "Montserrat", "radius": 22,
     "extra": ".bigt, .card h3, .col h3, .brand, .lin h4, .reel, .adimg, .aud h3, .sub { font-weight: 700; text-transform: uppercase; letter-spacing: .01em; }"
              " .bigt { font-size: 112px; line-height: 1.02; } .sub { font-size: 62px; } .sub.s { font-size: 54px; } .card h3 { font-size: 54px; }",
     "pal": {"acc": "#FF8A3D", "ink": "#2A0F00", "soft": "#FFD0AE", "deep": "#A04A12", "bg0": "#120605", "bg1": "#260C08",
             "bg2": "#4E1A0F", "bg3": "#6A2414", "flash": "#FFF0E4", "m1": "#F2DED3", "m2": "#C4A898", "m3": "#93786A",
             "acc_rgb": "255,138,61", "glow_rgb": "255,110,60", "line_rgb": "255,190,140", "bg_rgb": "18,6,5"}},
]

# узор фона: пишем базовыми цветами, палитра перекрасит
DECOS = {
    "glow": "",
    "grid": ".deco { position: absolute; inset: -200px; background-image: linear-gradient(rgba(255,194,61,.07) 2px, transparent 2px),"
            " linear-gradient(90deg, rgba(255,194,61,.07) 2px, transparent 2px); background-size: 96px 96px;"
            " -webkit-mask-image: radial-gradient(70% 55% at 50% 45%, #000 20%, transparent 75%); mask-image: radial-gradient(70% 55% at 50% 45%, #000 20%, transparent 75%); }",
    "sun": ".deco { position: absolute; left: 50%; top: 1180px; width: 1700px; height: 1700px; margin-left: -850px; border-radius: 50%;"
           " background: radial-gradient(circle, rgba(255,194,61,.30), rgba(255,194,61,.10) 40%, rgba(255,194,61,0) 68%); }",
    "stripes": ".deco { position: absolute; inset: -300px; background: repeating-linear-gradient(-32deg, rgba(255,194,61,.06) 0 3px, transparent 3px 70px); }",
    "dots": ".deco { position: absolute; inset: -200px; background: radial-gradient(rgba(255,194,61,.16) 3px, transparent 3.5px) 0 0 / 54px 54px;"
            " -webkit-mask-image: linear-gradient(180deg, #000, transparent 70%); mask-image: linear-gradient(180deg, #000, transparent 70%); }",
    "rings": ".deco { position: absolute; left: 50%; top: 820px; width: 2000px; height: 2000px; margin: -1000px 0 0 -1000px; border-radius: 50%;"
             " background: repeating-radial-gradient(circle, rgba(255,194,61,.09) 0 2px, transparent 2px 110px); }",
}
DECO_JS = {  # медленное движение узора на весь ролик
    "glow": "", "grid": '{"y": -96}', "sun": '{"y": -120, "scale": 1.08}', "stripes": '{"x": -140}', "dots": '{"y": -108}',
    "rings": '{"scale": 1.25, "rotation": 8}',
}

# субтитр: вторая половина фразы выделена
SUBS = {
    "underline": "",
    "plate": ".sub u { color: #1A1206; background: #FFC23D; padding: 2px 18px 6px; border-radius: 16px; text-shadow: none;"
             " -webkit-box-decoration-break: clone; box-decoration-break: clone; }",
    "box": ".sub { left: 70px; right: 70px; padding: 30px 34px; border-radius: 34px; background: rgba(11,9,7,.62); border: 1.5px solid rgba(255,194,61,.35);"
           " -webkit-backdrop-filter: blur(16px); backdrop-filter: blur(16px); text-shadow: none; } .sub u { background: none; padding: 0; }",
    "marker": ".sub u { color: #fff; background: linear-gradient(transparent 55%, rgba(255,194,61,.75) 55%) left / var(--w, 0%) 100% no-repeat; padding: 0 8px; }",
}

# раскладка кадра: CSS-свойство rotate не спорит с transform, которым двигает GSAP
LAYOUTS = {
    "classic": "",
    "center": ".bigt { text-align: center; top: 600px; } .tags { top: 210px; }",
    "left": ".sub { text-align: left; left: 80px; right: 80px; } .tags { justify-content: flex-start; padding-left: 80px; gap: 30px; }"
            " .bigt { top: 640px; }",
    "tilt": ".cards, .notes, .split, .phone, .mini, .laptop { rotate: -3deg; } .bigt { rotate: -2deg; } .tags { rotate: -2deg; }",
    "frame": ".frame { position: absolute; inset: 34px; border-radius: 58px; border: 2px solid rgba(255,194,61,.45); pointer-events: none; z-index: 40; }"
             " .frame b { position: absolute; top: -22px; left: 60px; padding: 0 18px; background: #0B0907; color: #FFC23D; font-size: 28px; font-weight: 500; letter-spacing: .08em; }"
             " .tags { top: 190px; }",
}

# уход сцены
EXITS = {
    "slide": lambda sel, at, rng: f'tl.to("{sel}", {{x: {rng.choice([-500, 500])}, opacity: 0, filter: "blur(18px)", duration: .3, ease: "power3.in"}}, {at:.2f});',
    "zoom": lambda sel, at, rng: f'tl.to("{sel}", {{scale: 1.3, opacity: 0, filter: "blur(16px)", duration: .3, ease: "power2.in"}}, {at:.2f});',
    "lift": lambda sel, at, rng: f'tl.to("{sel}", {{y: -320, opacity: 0, filter: "blur(10px)", duration: .3, ease: "power3.in"}}, {at:.2f});',
    "flip": lambda sel, at, rng: f'tl.to("{sel}", {{rotationX: 75, transformPerspective: 1600, transformOrigin: "50% 0%", opacity: 0, duration: .32, ease: "power2.in"}}, {at:.2f});',
    "shrink": lambda sel, at, rng: f'tl.to("{sel}", {{scale: .7, rotation: {rng.choice([-6, 6])}, opacity: 0, duration: .3, ease: "back.in(1.6)"}}, {at:.2f});',
}

# монтажная формула: ритм, склейки и связки между сценами (не цвет, а сам монтаж)
CUTS = {
    "classic": {"pace": 1.0, "beat": 1.6, "punch": .03},   # ровный ритм, наезд камеры каждые 1,6 с
    "punchy": {"pace": .82, "beat": 1.05, "punch": .05},  # быстрые сцены, частые удары с качкой
    "slam": {"pace": .95, "beat": 1.8, "punch": .03},     # между сценами вспышка-номер «02» на цвете акцента
    "story": {"pace": 1.0, "beat": 2.0, "punch": .02},    # полоса прогресса сверху и счётчик главы
    "zoomcut": {"pace": .9, "beat": 1.4, "punch": .04},   # каждая сцена влетает наездом из глубины
}

# как появляется хук (первая фраза крупным текстом)
HOOKS = ["words", "type", "drop", "rise"]

picked = {}  # стиль последнего собранного ролика; reels.py отмечает его после публикации


def load_used():
    try:
        return json.loads(USED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def mark_used(style):
    if not style:
        return
    used = load_used() + [style]
    USED_FILE.write_text(json.dumps(used[-USED_KEEP:], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fresh(options, key, used, rng):
    """Сначала то, что ни разу не выходило или выходило давно; вчерашнее не берём."""
    last = used[-1].get(key) if used else None
    age = {}
    for k, s in enumerate(used):
        age[s.get(key)] = k
    pool = [o for o in options if o != last] or list(options)
    oldest = min(age.get(o, -1) for o in pool)
    return rng.choice([o for o in pool if age.get(o, -1) == oldest])


def pick(seed=None, theme=None):
    rng = random.Random(seed)
    used = load_used()
    style = {
        "theme": theme or _fresh([t["id"] for t in THEMES], "theme", used, rng),
        "deco": _fresh(list(DECOS), "deco", used, rng),
        "sub": _fresh(list(SUBS), "sub", used, rng),
        "exit": _fresh(list(EXITS), "exit", used, rng),
        "layout": _fresh(list(LAYOUTS), "layout", used, rng),
        "cut": _fresh(list(CUTS), "cut", used, rng),
        "hook": _fresh(HOOKS, "hook", used, rng),
    }
    picked.clear()
    picked.update(style)
    return style


def theme_by_id(tid):
    return next((t for t in THEMES if t["id"] == tid), THEMES[0])


def css(style):
    t = theme_by_id(style["theme"])
    fonts = "\n".join(FONTS[f] for f in {t["head"], t["body"]} if FONTS.get(f))
    return "\n".join([fonts, DECOS[style["deco"]], SUBS[style["sub"]], LAYOUTS[style.get("layout", "classic")], t["extra"]])


def apply(page, style):
    """Перекрашивает и переодевает готовый HTML ролика под выбранный стиль."""
    t = theme_by_id(style["theme"])
    pal = t["pal"]
    for base, key in sorted(BASE.items(), key=lambda kv: -len(kv[0])):
        val = t["paper"] if key == "paper" else pal[key]
        page = page.replace(base, f"rgba({val}," if key.endswith("_rgb") else val)
    page = page.replace("font-family: Unbounded, sans-serif", f"font-family: {t['head']}, sans-serif")
    page = page.replace("font-family: Golos, sans-serif", f"font-family: {t['body']}, sans-serif")
    page = page.replace("border-radius: 40px;", f"border-radius: {t['radius']}px;")
    return page


def exit_js(style, sel, at, rng):
    return EXITS[style["exit"]](sel, at, rng)


def deco_js(style, total):
    move = DECO_JS[style["deco"]]
    if not move:
        return ""
    return f'tl.to(".deco", Object.assign({move}, {{duration: {total}, ease: "none"}}), 0);'
