"""Reels в промо-стиле Kelechek AI (HyperFrames: HTML + GSAP -> MP4).

Тёмный тёплый фон, 3D-телефоны, стеклянные карточки, жёлтые теги с точкой,
субтитр со второй половиной жёлтым и подчёркиванием, финал с логотипом.
Каждая фраза сценария получает свою сцену по смыслу (переписка, ролики,
запись, встреча, таргет, услуги, крупный текст), соседние сцены не повторяются.
Фразы на экране не повторяются: внутри ролика каждая фраза один раз и не дублирует
субтитр, а между роликами used_texts.json помнит показанное, и сначала берутся
свежие фразы. Только музыка, без звуковых эффектов.

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

import themes

HERE = Path(__file__).parent
HF_ASSETS = HERE / "assets" / "hf"
HF_VERSION = "0.8.121"
END = 3.0  # финальная карточка с логотипом
USED_FILE = HERE / "used_texts.json"
USED_KEEP = 600
CTX = {"text": "", "foot": []}  # весь текст ролика и живые кадры со стока для текущей сборки
picked = []  # фразы последнего ролика; reels.py отмечает их показанными после публикации

KEYWORDS = {
    "ads": ["таргет", "реклам", "аудитор", "бюджет", "продвиг", "креатив"],
    "chat": ["ответ", "вопрос", "пиш", "whatsapp", "директ", "сообщ", "сколько стоит", "клиент"],
    "fan": ["reels", "ролик", "видео", "instagram", "пост", "контент", "сним", "съём", "монтаж", "камер"],
    "booking": ["запис", "брон", "свободн", "окн"],
    "notify": ["заявк", "уведомл", "комментар", "лид", "сразу приходит", "теря"],
    "split": ["вместо", "раньше", "вручную", "сотрудник", "менеджер", "по кругу"],
    "laptop": ["лично", "встреч", "ноутбук", "покаж", "показ на", "отчёт", "отчет", "excel", "бишкек"],
}
TAGS = {
    "ads": ["Таргет", "Реклама в Instagram", "Нужная аудитория", "Под ваш бюджет", "Креативы на ИИ"],
    "chat": ["Клиент пишет ночью", "ИИ отвечает сразу", "WhatsApp", "Direct", "Без ожидания", "Ответ за минуту"],
    "fan": ["Reels", "Instagram", "Threads", "Без съёмки", "Каждый день", "Контент"],
    "booking": ["Сайт для записи", "24/7", "Без звонков", "Онлайн-бронь"],
    "laptop": ["Бишкек", "Встреча лично", "Отчёт в Excel", "Всё в одном месте"],
    "cards": ["Автоматизация", "ИИ-видео", "Для бизнеса", "Бишкек", "Таргет", "Под ключ"],
    "big": ["Kelechek AI"],
    "photo": ["Живые кадры", "ИИ-монтаж", "Ваш стиль", "Без студии"],
    "notify": ["Заявки", "Уведомления", "Ничего не теряется", "Всё под контролем"],
    "split": ["Было и стало", "Разница"],
}
QUESTIONS = ["Здравствуйте, сколько стоит?", "А вы сегодня работаете?", "Есть запись на завтра?",
             "Где вы находитесь?", "Можно узнать цену?", "Есть свободное время вечером?",
             "Доставка есть?", "Вы ещё открыты?", "А в субботу можно прийти?", "Есть парковка рядом?",
             "Можно оплатить переводом?", "Какие есть размеры?", "Сколько ждать заказ?",
             "Можно столик на четверых?", "А детское меню есть?", "Вы без выходных?",
             "Можно прийти без записи?", "Это есть в наличии?", "Как к вам доехать?", "Пришлите меню, пожалуйста",
             "Увидел вашу рекламу, это актуально?", "Можно подробнее про акцию?"]
ANSWERS = ["Здравствуйте! Я ИИ-помощник, отвечу сразу. Что вас интересует?",
           "Добрый вечер! Подскажите, на какой день вам удобно?",
           "Здравствуйте! Сейчас всё подскажу. Как вас зовут?",
           "Да, отвечаю сразу. Передам владельцу вашу заявку, он напишет лично.",
           "Добрый вечер! Пришлю варианты прямо сюда.",
           "Здравствуйте! Сейчас пришлю адрес и схему проезда.",
           "Добрый вечер! Уточню наличие и сразу вернусь с ответом.",
           "Здравствуйте! Меню и цены отправляю прямо в чат.",
           "Да, можно. На какое время вас записать?",
           "Здравствуйте! Есть несколько вариантов, пришлю фото.",
           "Добрый вечер! Оставьте номер, менеджер позвонит утром.",
           "Здравствуйте! Простое отвечу сам, сложное передам владельцу."]
FOLLOW = ["Отлично, спасибо!", "Супер, жду", "Да, давайте", "Хорошо", "Удобно, спасибо", "Понял, записываюсь",
          "Быстро вы", "Ого, уже ответили", "Договорились", "Спасибо, приду"]
CARDS = [("Ответы 24/7", "в WhatsApp и Direct"), ("Reels", "без съёмки"), ("Заявки", "сразу в таблицу"),
         ("Отчёт", "каждую неделю в Excel"), ("Посты", "каждый день"), ("Запись", "клиент сам выбирает время"),
         ("Встреча", "лично в Бишкеке"), ("15 дней", "бесплатно"), ("Монтаж", "в вашем стиле"),
         ("Таргет", "реклама нужным людям"), ("Аудитория", "по городу и интересам"), ("Креативы", "ролики для рекламы"),
         ("Сайт", "для онлайн-записи"), ("Чат-бот", "знает ваши цены"), ("Контент-план", "на месяц вперёд"),
         ("Комментарии", "ответ без задержки"), ("Тексты", "живым языком"), ("Обложки", "в одном стиле"),
         ("Напоминания", "клиентам о визите"), ("ИИ-аватар", "говорит за вас"), ("Озвучка", "без студии"),
         ("Аналитика", "что приносит заявки")]
TILES = ["Клиент написал в 23:40. ИИ ответил сразу.", "Новый Reels для меню готов к публикации.",
         "Пост на сегодня уже в очереди.", "Заявка из Direct попала в таблицу.",
         "Монтаж в стиле вашего бренда.", "Ответ на комментарий отправлен.",
         "Креатив для рекламы собран.", "Обложки для недели готовы.", "Сторис с новинкой выйдет в обед.",
         "Карусель про услуги в черновиках.", "Текст поста проверен владельцем.", "Видео с ИИ-аватаром смонтировано.",
         "Подписи к роликам на двух языках.", "Реклама показывается в Бишкеке."]
REEL_TITLES = [("Новинка", "этой недели"), ("За кадром", "нашей кухни"), ("Запись", "открыта"), ("Как это", "делается"),
               ("Утро", "в нашей кофейне"), ("Ваш стиль", "в каждом кадре"), ("Секрет", "нашего меню"),
               ("Мастер", "за работой"), ("Новая", "коллекция"), ("Один день", "из жизни салона"),
               ("Вопрос", "от клиента"), ("Почему", "выбирают нас")]
AD_POSTS = [("Кофейня у дома", "Новый сезонный напиток"), ("Салон красоты", "Свободные окна на этой неделе"),
            ("Стоматология", "Консультация и запись онлайн"), ("Доставка еды", "Горячие обеды в офис"),
            ("Фитнес-студия", "Пробное занятие"), ("Магазин одежды", "Новая коллекция"),
            ("Автомойка", "Запись без очереди"), ("Цветочный магазин", "Букеты с доставкой"),
            ("Детский центр", "Набор в новые группы"), ("Пекарня", "Свежая выпечка с утра")]
AUDIENCE = ["Бишкек", "рядом с вами", "25–45 лет", "молодые мамы", "любят кофе", "работают в офисах",
            "интерес: красота", "интерес: спорт", "были на сайте", "писали в Direct", "похожи на клиентов",
            "смотрели ваши Reels", "ищут доставку", "планируют праздник"]
PINS = ["Бишкек", "Встреча у вас", "Демо вживую", "Ваш офис", "Кофе и показ"]
SLOGANS = ["ИИ-видео и автоматизация для бизнеса", "Видео, таргет и автоответы на ИИ",
           "Reels, реклама и заявки без хаоса", "ИИ берёт рутину, вы берёте клиентов",
           "Контент и реклама для бизнеса в Бишкеке"]
DECOR = ["ring", "wave", "bars", "dots", ""]
PHOTO_CHIPS = [("Ваш бизнес", "в кадре"), ("Живое видео", "ИИ-монтаж"), ("Ваши клиенты", "ваш стиль"),
               ("Реальная жизнь", "не шаблон"), ("Атмосфера", "которую хочется увидеть")]
# переписка в телефоне под тему ролика (07.10: в ролике про таргет телефон показывал бронь столика)
CHAT_TOPICS = [
    (("таргет", "реклам", "продвиг", "аудитор", "креатив"), [
        ("Увидела вашу рекламу в Instagram, акция ещё действует?", "Здравствуйте! Да, до воскресенья. Пришлю подробности прямо сюда.", "Отлично, жду"),
        ("Пришёл по рекламе. Это рядом с Ала-Арчой?", "Да, пять минут пешком. Пришлю точку на карте.", "Спасибо, зайду"),
        ("Нашёл вас через рекламу. Сколько стоит?", "Здравствуйте! Пришлю цены и фото, а владелец ответит на остальное.", "Супер, жду"),
        ("Ваша реклама попалась уже третий раз 😄 Можно записаться?", "Значит, это знак! На какой день вам удобно?", "Давайте в субботу")]),
    (("ролик", "reels", "видео", "контент", "монтаж", "пост"), [
        ("Видела ваш Reels, это блюдо есть сегодня?", "Да, готовим весь день. Оставить для вас порцию?", "Да, давайте"),
        ("Классное видео! Где вы находитесь?", "Спасибо! Пришлю адрес и схему проезда.", "Ого, быстро"),
        ("Посмотрел ролик про новинку. Можно заказать?", "Конечно! Доставка или самовывоз?", "Самовывоз")]),
    (("запис", "брон", "окн", "салон", "мастер"), [
        ("Есть запись на завтра?", "Да, есть окна в 12:00 и 16:30. Записать вас?", "Давайте на 16:30"),
        ("Можно прийти в субботу?", "Да, в субботу свободно с 11:00. Какое время удобно?", "В 11 отлично"),
        ("А к какому мастеру можно сегодня?", "Сегодня свободна Айгерим в 18:00. Записать?", "Да, записывайте")]),
    (("кафе", "кофе", "ресторан", "столик", "меню", "доставк"), [
        ("Можно столик на четверых?", "Да! На какое время и день?", "Сегодня в 19:00"),
        ("Пришлите меню, пожалуйста", "Отправляю меню и цены прямо в чат.", "Спасибо!"),
        ("Доставка есть?", "Да, по Бишкеку. Что будете заказывать?", "Сейчас выберу")]),
]

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
#flash { position: absolute; inset: 0; background: #FFF4DC; opacity: 0; z-index: 50; pointer-events: none; }
.vig { position: absolute; inset: 0; background: radial-gradient(120% 90% at 50% 45%, transparent 55%, rgba(0,0,0,.75)); }
.tags { position: absolute; top: 170px; left: 0; right: 0; display: flex; justify-content: center; gap: 44px; font-weight: 500; font-size: 34px; }
.tag { display: flex; align-items: center; gap: 14px; }
.tag i { width: 14px; height: 14px; border-radius: 50%; background: #FFC23D; box-shadow: 0 0 14px #FFC23D; }
.stage { position: absolute; inset: 0; perspective: 2200px; }
.foot { position: absolute; object-fit: cover; }
.full { left: 0; top: 0; width: 1080px; height: 1920px; }
.dim { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; background: linear-gradient(180deg, rgba(11,9,7,.62), rgba(11,9,7,.38) 38%, rgba(11,9,7,.9) 78%); }
.framed { left: 110px; top: 270px; width: 860px; height: 960px; border-radius: 56px; box-shadow: 0 0 0 3px rgba(255,214,140,.35), 0 60px 120px rgba(0,0,0,.7); }
.fchip { position: absolute; display: flex; align-items: center; gap: 14px; padding: 18px 28px; border-radius: 999px; font-size: 32px; font-weight: 500;
  background: rgba(20,17,12,.55); border: 1px solid rgba(255,255,255,.18); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); }
.fchip i { width: 16px; height: 16px; border-radius: 50%; background: #FFC23D; box-shadow: 0 0 14px #FFC23D; }
.fchip.y { background: #FFC23D; color: #1A1206; border: 0; }
.phone { position: absolute; width: 470px; height: 960px; left: 305px; top: 300px; border-radius: 74px; background: #121214; padding: 14px;
         box-shadow: 0 0 0 3px #3A3A3E, 0 0 0 5px #0d0d0f, 0 60px 120px rgba(0,0,0,.6), inset 0 0 0 2px rgba(255,255,255,.08); transform-style: preserve-3d; }
.screen { width: 100%; height: 100%; border-radius: 62px; background: #F4F1EA; overflow: hidden; position: relative; color: #1C1C1E; }
.screen > img { width: 100%; height: 100%; object-fit: cover; object-position: top; display: block; }
.island { position: absolute; top: 18px; left: 50%; width: 130px; height: 38px; margin-left: -65px; background: #000; border-radius: 20px; z-index: 3; }
.sbar { height: 70px; padding: 22px 40px 0; display: flex; justify-content: space-between; font-size: 22px; font-weight: 500; }
.chead { display: flex; align-items: center; gap: 16px; padding: 14px 26px 18px; border-bottom: 1px solid #E3DED3; }
.chead img { width: 58px; height: 58px; border-radius: 50%; background: #111; }
.chead b { font-size: 25px; display: block; }
.chead span { font-size: 19px; color: #1F6B37; }
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
.bigt { position: absolute; left: 70px; right: 70px; top: 520px; font-family: Unbounded, sans-serif; font-size: 92px; line-height: 1.1; text-shadow: 0 6px 30px rgba(0,0,0,.6); }
.bigt .w { display: inline-block; margin-right: .22em; }
.bigt em { font-style: normal; color: #FFC23D; }
.bigt .c { display: inline-block; }
.slamc { position: absolute; inset: 0; background: #FFC23D; display: flex; align-items: center; justify-content: center; z-index: 30; }
.slamc b { font-family: Unbounded, sans-serif; font-size: 300px; color: #1A1206; letter-spacing: -.04em; }
.prog { position: absolute; left: 70px; right: 70px; top: 120px; height: 8px; border-radius: 8px; background: rgba(255,214,140,.18); z-index: 30; }
.prog i { position: absolute; left: 0; top: 0; bottom: 0; width: 100%; border-radius: 8px; background: #FFC23D; transform-origin: 0 50%; }
.chap { position: absolute; right: 70px; top: 150px; font-family: Unbounded, sans-serif; font-size: 34px; color: #FFC23D; z-index: 30; }
.notes { position: absolute; left: 90px; right: 90px; top: 380px; display: flex; flex-direction: column; gap: 26px; }
.note { display: flex; align-items: center; gap: 24px; padding: 28px 30px; border-radius: 34px; background: rgba(255,255,255,.14);
        border: 1.5px solid rgba(255,255,255,.22); box-shadow: 0 24px 50px rgba(0,0,0,.4); }
.note img { width: 74px; height: 74px; border-radius: 20px; }
.note b { display: block; font-size: 30px; font-weight: 500; }
.note span { display: block; font-size: 25px; color: #E0D6C3; margin-top: 4px; }
.note small { margin-left: auto; align-self: flex-start; font-size: 22px; color: #BDB3A0; }
.split { position: absolute; left: 70px; right: 70px; top: 400px; display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
.col { border-radius: 40px; padding: 36px 32px; min-height: 640px; }
.col.was { background: rgba(255,255,255,.07); border: 1.5px solid rgba(255,255,255,.15); color: #B9AF9E; }
.col.now { background: linear-gradient(160deg, rgba(255,194,61,.32), rgba(255,194,61,.10)); border: 1.5px solid rgba(255,194,61,.6); box-shadow: 0 30px 60px rgba(0,0,0,.45); }
.col h3 { font-family: Unbounded, sans-serif; font-size: 40px; margin-bottom: 30px; color: #fff; }
.col li { list-style: none; font-size: 29px; line-height: 1.3; padding: 18px 0 18px 52px; position: relative; border-top: 1px solid rgba(255,255,255,.12); }
.col li:before { position: absolute; left: 0; top: 16px; width: 36px; height: 36px; border-radius: 50%; text-align: center; line-height: 36px; font-size: 22px; }
.was li:before { content: "✕"; background: rgba(255,255,255,.12); }
.now li:before { content: "✓"; background: #FFC23D; color: #1A1206; }
.adhead { display: flex; align-items: center; gap: 16px; padding: 10px 26px 18px; }
.adhead img { width: 58px; height: 58px; border-radius: 50%; background: #111; }
.adhead b { font-size: 25px; display: block; }
.adhead span { font-size: 19px; color: #5E574D; }
.adimg { margin: 0 18px; height: 520px; border-radius: 26px; background: linear-gradient(165deg, #3A2A12, #0B0907); display: flex; align-items: flex-end;
         padding: 34px; font-family: Unbounded, sans-serif; font-size: 40px; line-height: 1.15; color: #fff; }
.adbtn { margin: 22px 18px; padding: 22px; border-radius: 20px; background: #FFC23D; text-align: center; font-size: 26px; font-weight: 500; color: #1A1206; }
.tap { position: absolute; left: 272px; top: 1080px; width: 66px; height: 66px; border-radius: 50%; background: rgba(255,255,255,.55);
       border: 3px solid #fff; box-shadow: 0 8px 24px rgba(0,0,0,.45); z-index: 5; }
.tap i { position: absolute; inset: -3px; border-radius: 50%; border: 3px solid #FFC23D; opacity: 0; }
.aud { position: absolute; left: 580px; right: 60px; top: 470px; }
.aud h3 { font-family: Unbounded, sans-serif; font-size: 40px; margin: 30px 0 26px; }
.chip { display: inline-block; margin: 0 12px 18px 0; padding: 16px 26px; border-radius: 999px; font-size: 28px;
        background: rgba(255,255,255,.12); border: 1.5px solid rgba(255,194,61,.55); }
.aim { width: 150px; height: 150px; }
.aim circle, .aim line { fill: none; stroke: #FFC23D; stroke-width: 4; }
.aim .core { fill: #FFC23D; }
.sub { position: absolute; left: 60px; right: 60px; bottom: 300px; text-align: center; font-family: Unbounded, sans-serif; font-size: 52px; line-height: 1.25; text-shadow: 0 4px 24px rgba(0,0,0,.65); }
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


def kinds_for(text):
    """Все сцены, подходящие фразе по смыслу, в порядке приоритета."""
    low = text.lower()
    return [kind for kind, words in KEYWORDS.items() if any(w in low for w in words)]


def kind_for(text):
    return (kinds_for(text) or ["cards"])[0]


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


def stems(text):
    return {w[:4] for w in re.findall(r"[а-яёa-z0-9]+", text.lower()) if len(w) >= 4}


def key(item):
    return " / ".join(item) if isinstance(item, tuple) else item


def load_used():
    try:
        return json.loads(USED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def mark_used(phrases):
    """После публикации: эти фразы уходят в конец очереди и не появятся, пока есть непоказанные."""
    fresh = list(dict.fromkeys(phrases))
    used = [x for x in load_used() if x not in fresh] + fresh
    USED_FILE.write_text(json.dumps(used[-USED_KEEP:], ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


class Picker(random.Random):
    """random.Random, который не повторяет фразы: ни внутри ролика, ни с субтитром, ни с прошлыми роликами."""

    def __init__(self, seed=None):
        super().__init__(seed)
        self.age = {x: n for n, x in enumerate(load_used())}  # чем меньше, тем давнее показывали
        self.shown = set()

    def fresh(self, pool, k, text="", keep=True):
        sub = stems(text)
        free = [x for x in pool if key(x) not in self.shown]
        clean = [x for x in free if not stems(key(x)) & sub] or free  # не дублировать слова субтитра
        self.shuffle(clean)
        clean.sort(key=lambda x: self.age.get(key(x), -1))  # сначала непоказанные, потом самые давние
        out = clean[:k]
        if len(out) < k:
            out += [x for x in free if x not in out][:k - len(out)]
        for x in out:
            self.shown.add(key(x))
            if keep:
                picked.append(key(x))
        return out

    def one(self, pool, text="", keep=True):
        return self.fresh(pool, 1, text, keep)[0]


# ---------- сцены: html и анимация ----------

def topic_chat(text, rng):
    """Вопрос, ответ и реплика клиента под тему: сначала по фразе, потом по всему ролику."""
    for src in (text, CTX["text"]):
        low = src.lower()
        for words, triples in CHAT_TOPICS:
            if any(w in low for w in words):
                return rng.choice(triples)
    return rng.one(QUESTIONS, text), rng.one(ANSWERS, text), rng.one(FOLLOW, text)


def scene_chat(i, text, rng, t, d):
    q, a, f = topic_chat(text, rng)  # не цитата из текста: субтитр и так её покажет
    ts = stamp(rng)
    h = f"""<div class="phone" id="p{i}"><div class="screen"><div class="island"></div>
      <div class="sbar"><span>{ts}</span><span>●●● 5G</span></div>
      <div class="chead"><img src="./logo.png" /><div><b>ИИ-помощник</b><span>онлайн</span></div></div>
      <div class="chat"><div class="msg in" id="a{i}">{esc(q)}<small>{ts}</small></div>
        <div class="typing" id="y{i}"><i></i><i></i><i></i></div>
        <div class="msg out" id="b{i}">{esc(a)}<small>{ts}</small></div>
        <div class="msg in" id="c{i}">{esc(f)}<small>{ts}</small></div></div></div></div>
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
    picks = rng.fresh(CARDS, 4, text)
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
    head, tail = map(esc, rng.one(REEL_TITLES, text))  # не первые слова абзаца: их уже показывает субтитр
    tiles = [esc(x) for x in rng.fresh(TILES, 3, text)]
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
      <div class="pin" id="n{i}">● {esc(rng.one(PINS, text, keep=False))}</div>"""
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
    hook = CTX.get("hook", "words") if i == 0 else "words"
    word = (lambda w: "".join(f'<span class="c">{esc(ch)}</span>' for ch in w)) if hook == "type" else esc
    spans = " ".join(f'<span class="w p">{word(w)}</span>' for w in words[:cut])
    spans += " " + " ".join(f'<span class="w a"><em>{word(w)}</em></span>' for w in words[cut:])
    size = 92 if len(text) < 45 else 72 if len(text) < 80 else 58
    h = f'<div class="bigt" id="t{i}" style="font-size:{size}px">{spans}</div>'
    enter = {
        "words": f'tl.from("#t{i} .w", {{opacity: 0, y: 40, filter: "blur(12px)", stagger: .09, duration: .45, ease: "power3.out"}}, {t + .1})',
        "type": f'tl.from("#t{i} .c", {{opacity: 0, duration: .01, stagger: .03}}, {t + .05})',
        "drop": f'tl.from("#t{i} .w", {{opacity: 0, y: -300, rotation: () => gsap.utils.random(-14, 14), stagger: .08, duration: .7, ease: "bounce.out"}}, {t + .05})',
        "rise": f'tl.from("#t{i} .w", {{opacity: 0, scale: 2.6, filter: "blur(20px)", stagger: .07, duration: .4, ease: "expo.out"}}, {t + .05})',
    }[hook]
    js = f"""
{enter}
  .to("#t{i}", {{scale: 1.05, duration: {d - .6:.2f}, ease: "sine.inOut", transformOrigin: "0% 50%"}}, {t + .5});"""
    if d >= 2.9:  # в конце остаётся главное: остальные слова гаснут, акцент крупнее (приём «Feel every click → Click.»)
        js += f"""
tl.to("#t{i} .p", {{opacity: .16, filter: "blur(3px)", duration: .4, ease: "power2.out"}}, {t + d - 1.1:.2f})
  .to("#t{i} .a", {{scale: 1.14, duration: .45, ease: "back.out(2)", transformOrigin: "0% 60%"}}, {t + d - 1.1:.2f});"""
    return h, js


NOTES = [("Новая заявка", "из Instagram, уже в таблице"), ("Новый комментарий", "ИИ ответил под постом"),
         ("Запись на завтра", "клиент выбрал время сам"), ("Сообщение в WhatsApp", "ответ отправлен"),
         ("Новый Reels готов", "выйдет вечером"), ("Отчёт за неделю", "в Excel, можно открыть"),
         ("Вопрос о цене", "ИИ прислал прайс"), ("Реклама запущена", "показы идут в Бишкеке"),
         ("Новый креатив", "для рекламы в Instagram"), ("Заявка с рекламы", "уже в WhatsApp"),
         ("Напоминание ушло", "клиенту о визите завтра"), ("Пост вышел", "в Threads"),
         ("Контент-план", "обновлён на неделю"), ("Бронь столика", "на вечер, подтверждена"),
         ("Отзыв", "клиента попросили после визита"), ("Вопрос в Direct", "ответ уже у клиента")]
SPLITS = [("Ответ утром", "Ответ сразу, даже ночью"), ("Заявки в голове", "Каждая заявка в таблице"),
          ("Одни и те же вопросы", "ИИ отвечает на частые"), ("Старые фото в профиле", "Свежие ролики без съёмки"),
          ("Посты, когда есть время", "Посты каждый день"), ("Реклама «на всех»", "Реклама на тех, кому нужно"),
          ("Кнопка «Продвигать» наугад", "Настроенная аудитория"), ("Один креатив месяцами", "Новые креативы регулярно"),
          ("Запись по телефону", "Запись на сайте"), ("Забытые визиты", "Напоминания уходят сами"),
          ("Итоги на глаз", "Отчёт в Excel"), ("Комментарии без ответа", "Ответ под каждым"),
          ("Съёмка целый день", "Ролик из пары фото")]


def scene_notify(i, text, rng, t, d):
    picks = rng.fresh(NOTES, 4, text)
    notes = "".join(f'<div class="note"><img src="./logo.png" /><div><b>{esc(a)}</b><span>{esc(b)}</span></div><small>{stamp(rng)}</small></div>'
                    for a, b in picks)
    h = f'<div class="notes" id="n{i}">{notes}</div>'
    js = f"""
tl.from("#n{i} .note", {{y: -160, opacity: 0, scale: .9, filter: "blur(10px)", stagger: .35, duration: .55, ease: "back.out(1.6)"}}, {t + .1})
  .to("#n{i}", {{y: 30, duration: {d - 1.8:.2f}, ease: "sine.inOut"}}, {t + 1.6});"""
    return h, js


def scene_split(i, text, rng, t, d):
    pairs = rng.fresh(SPLITS, 3, text)
    was = "".join(f"<li>{esc(a)}</li>" for a, _ in pairs)
    now = "".join(f"<li>{esc(b)}</li>" for _, b in pairs)
    h = (f'<div class="split" id="v{i}"><div class="col was"><h3>Было</h3><ul>{was}</ul></div>'
         f'<div class="col now"><h3>С ИИ</h3><ul>{now}</ul></div></div>')
    js = f"""
tl.from("#v{i} .was", {{x: -400, rotationY: 30, opacity: 0, filter: "blur(14px)", duration: .7, ease: "expo.out"}}, {t})
  .from("#v{i} .now", {{x: 400, rotationY: -30, opacity: 0, filter: "blur(14px)", duration: .7, ease: "expo.out"}}, {t + .35})
  .from("#v{i} .now li", {{x: 40, opacity: 0, stagger: .2, duration: .4, ease: "power3.out"}}, {t + .9})
  .to("#v{i} .was", {{opacity: .55, scale: .97, duration: .6}}, {t + 1.6});"""
    return h, js


def scene_ads(i, text, rng, t, d):
    biz, head = rng.one(AD_POSTS, text)
    chips = "".join(f'<div class="chip">{esc(x)}</div>' for x in rng.fresh(AUDIENCE, 4, text, keep=False))
    h = f"""<div class="phone" id="ad{i}" style="left:70px;top:360px;width:470px;height:930px"><div class="screen"><div class="island"></div>
        <div class="sbar"><span>{stamp(rng)}</span><span>●●● 5G</span></div>
        <div class="adhead"><img src="./logo.png" /><div><b>{esc(biz)}</b><span>Реклама</span></div></div>
        <div class="adimg"><div>{esc(head)}</div></div>
        <div class="adbtn" id="ab{i}">Написать в WhatsApp</div></div></div>
      <div class="aud" id="au{i}"><svg class="aim" id="am{i}" viewBox="0 0 120 120"><circle cx="60" cy="60" r="54"/><circle cx="60" cy="60" r="34"/>
        <circle cx="60" cy="60" r="12" class="core"/><line x1="60" y1="0" x2="60" y2="30"/><line x1="60" y1="90" x2="60" y2="120"/>
        <line x1="0" y1="60" x2="30" y2="60"/><line x1="90" y1="60" x2="120" y2="60"/></svg>
        <h3>Аудитория</h3>{chips}</div>
      <div class="tap" id="tp{i}"><i id="tr{i}"></i></div>
      <div class="demo">пример настройки рекламы</div>"""
    js = f"""
tl.fromTo("#ad{i}", {{rotationY: 35, x: -300, opacity: 0, filter: "blur(16px)"}}, {{rotationY: 8, x: 0, opacity: 1, filter: "blur(0px)", duration: .9, ease: "expo.out"}}, {t})
  .from("#am{i}", {{scale: 3, rotation: -90, opacity: 0, duration: .8, ease: "expo.out"}}, {t + .3})
  .from("#au{i} h3", {{opacity: 0, x: 40, duration: .4, ease: "power3.out"}}, {t + .6})
  .from("#au{i} .chip", {{opacity: 0, x: 80, scale: .8, stagger: .18, duration: .45, ease: "back.out(2)"}}, {t + .8})
  .to("#am{i}", {{rotation: 45, duration: {d - 1.2:.2f}, ease: "sine.inOut"}}, {t + 1.1})
  .fromTo("#tp{i}", {{x: 260, y: 260, opacity: 0}}, {{x: 0, y: 0, opacity: 1, duration: .45, ease: "power3.out"}}, {t + 1.3})
  .to("#tp{i}", {{scale: .78, duration: .12, yoyo: true, repeat: 1, ease: "power2.inOut"}}, {t + 1.8})
  .to("#ab{i}", {{scale: .94, duration: .12, yoyo: true, repeat: 1, ease: "power2.inOut"}}, {t + 1.8})
  .fromTo("#tr{i}", {{scale: .4, opacity: .9}}, {{scale: 2.6, opacity: 0, duration: .6, ease: "power2.out"}}, {t + 1.85})
  .to("#tp{i}", {{x: 120, y: 160, opacity: 0, duration: .4, ease: "power2.in"}}, {t + 2.6})
  .to("#ad{i}", {{rotationY: -6, y: 20, duration: {d - 1:.2f}, ease: "sine.inOut"}}, {t + .9});"""
    return h, js


def scene_photo(i, text, rng, t, d):
    """Живые кадры со стока в рамке и стеклянные подписи поверх (видео кладёт compose отдельным клипом)."""
    a, b = rng.choice(PHOTO_CHIPS)
    h = f"""<div class="fchip" id="fa{i}" style="left:150px;top:320px"><i></i>{esc(a)}</div>
      <div class="fchip y" id="fb{i}" style="right:140px;top:1140px">{esc(b)}</div>"""
    js = f"""
tl.from("#fa{i}", {{opacity: 0, x: -60, filter: "blur(10px)", duration: .5, ease: "power3.out"}}, {t + .5})
  .from("#fb{i}", {{opacity: 0, x: 60, scale: .8, duration: .5, ease: "back.out(2)"}}, {t + 1.1});"""
    return h, js


SCENES = {"photo": scene_photo, "ads": scene_ads, "notify": scene_notify, "split": scene_split, "chat": scene_chat, "cards": scene_cards, "fan": scene_fan, "booking": scene_booking,
          "laptop": scene_laptop, "big": scene_big}
SPARE = ["cards", "fan", "chat", "big", "notify", "split", "ads"]  # если смысл сцены совпал с предыдущей, берём другую


def compose(text, seed=None, foot=None, style=None):
    rng = Picker(seed)
    style = style or themes.pick(seed)  # палитра, шрифты, узор фона, субтитр и переход: каждый день другие
    CTX["text"], CTX["foot"], CTX["hook"] = text, list(foot or []), style.get("hook", "words")
    cut = themes.CUTS[style.get("cut", "classic")]
    picked.clear()
    paras = paragraphs(text)
    clips, js, t, prev, seen = [], [], 0.0, None, set()
    for i, p in enumerate(paras):
        if style.get("cut") == "slam" and i > 0:  # вспышка-номер между сценами
            clips.append(f'<div class="slamc clip" id="sl{i}" data-start="{t:.2f}" data-duration="0.45" data-track-index="6"><b>{i + 1:02d}</b></div>')
            js.append(f'tl.from("#sl{i}", {{scale: 1.25, duration: .18, ease: "power3.out"}}, {t:.2f})'
                      f'.from("#sl{i} b", {{y: 120, opacity: 0, duration: .2, ease: "expo.out"}}, {t + .03:.2f})'
                      f'.to("#sl{i}", {{yPercent: -100, duration: .14, ease: "power3.in"}}, {t + .31:.2f});')
            t += .45
        d = max(2.6, round(duration(p) * cut["pace"], 2))
        kind = kind_for(p)
        if i == 0 and kind == "cards":
            kind = "big"  # хук крупным текстом, если в нём нет предмета для сцены
        if kind == prev or kind in seen:  # каждая сцена один раз за ролик, пока есть другие
            # сначала другая сцена по смыслу этой же фразы, потом нейтральные; реклама и запись только если про них речь
            fits = [k for k in kinds_for(p) if k not in seen and k != prev]
            spare = [k for k in SPARE if k not in ("ads", "booking")]
            kind = (fits or [k for k in spare if k not in seen and k != prev] or [k for k in spare if k != prev])[0] if fits \
                else rng.choice([k for k in spare if k not in seen and k != prev] or [k for k in spare if k != prev])
        foot = CTX["foot"]
        if i == 1 and foot and kind not in ("chat", "ads", "booking"):
            kind = "photo"  # одна сцена с живыми кадрами в рамке
        prev = kind
        seen.add(kind)
        h, s = SCENES[kind](i, p, rng, round(t, 2), d)
        if foot and (kind == "photo" or (i == 0 and kind == "big")):
            src = foot.pop(0)
            cls, extra = ("full", f'<div class="dim clip" id="dm{i}" data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="5"></div>') if kind == "big" else ("framed", "")
            clips.append(f'<video class="foot {cls} clip" id="fv{i}" src="./{src}" muted playsinline data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="4"></video>{extra}')
            if kind == "big":
                js.append(f'tl.fromTo("#fv{i}", {{scale: 1.18}}, {{scale: 1.0, duration: {d:.2f}, ease: "none"}}, {t:.2f})'
                          f'.to(["#fv{i}", "#dm{i}"], {{opacity: 0, duration: .3}}, {t + d - .3:.2f});')
            else:
                js.append(f'tl.fromTo("#fv{i}", {{opacity: 0, scale: .86, rotationY: -18, transformPerspective: 1600, filter: "blur(14px)"}}, '
                          f'{{opacity: 1, scale: 1, rotationY: 0, filter: "blur(0px)", duration: .9, ease: "expo.out"}}, {t:.2f})'
                          f'.to("#fv{i}", {{scale: 1.05, duration: {d - 1.2:.2f}, ease: "sine.inOut"}}, {t + .9:.2f})'
                          f'.to("#fv{i}", {{x: {rng.choice([-500, 500])}, opacity: 0, filter: "blur(18px)", duration: .3, ease: "power3.in"}}, {t + d - .3:.2f});')
        tags = "".join(f'<div class="tag"><i></i>{esc(x)}</div>' for x in rng.fresh(TAGS[kind], min(2, len(TAGS[kind])), p, keep=False))
        clips.append(f'<div class="tags clip" id="tg{i}" data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="2">{tags}</div>')
        clips.append(f'<div class="stage clip" id="sc{i}" data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="1">{h}</div>')
        js.append(s)
        if style.get("cut") == "zoomcut":  # сцена влетает из глубины
            js.append(f'tl.from("#sc{i}", {{scale: 1.6, opacity: 0, filter: "blur(22px)", duration: .38, ease: "expo.out"}}, {t:.2f});')
        if style.get("cut") == "story":
            clips.append(f'<div class="chap clip" id="ch{i}" data-start="{t:.2f}" data-duration="{d:.2f}" data-track-index="6">{i + 1}/{len(paras)}</div>')
            js.append(f'tl.from("#ch{i}", {{opacity: 0, x: 30, duration: .3, ease: "power3.out"}}, {t + .1:.2f});')
        js.append(f'tl.from("#tg{i} .tag", {{opacity: 0, y: -20, stagger: .1, duration: .4, ease: "power3.out"}}, {t + .15:.2f});')
        # «биты» внутри сцены: ступенчатый наезд камеры и мягкая вспышка, чтобы не было мёртвых секунд
        # (разбор Reels 06.10: картинка должна меняться каждую 1–2 секунды)
        b, k = t + max(1.0, cut["beat"] + .1), 0
        while b < t + d - .6:
            sway = f', rotation: {rng.choice([-1.2, 1.2])}' if style.get("cut") == "punchy" else ""
            js.append(f'tl.to("#sc{i}", {{scale: {1 + cut["punch"] * (k + 1):.3f}{sway}, transformOrigin: "50% 250px", duration: .22, ease: "power3.out"}}, {b:.2f})'
                      f'.to("#flash", {{opacity: .10, duration: .08}}, {b:.2f}).to("#flash", {{opacity: 0, duration: .12}}, {b + .08:.2f});')
            b, k = b + cut["beat"], k + 1
        js.append(themes.exit_js(style, f"#sc{i}", t + d - .3, rng))
        if kind != "big":
            a, b = split_sub(p)
            cls = "sub s" if len(p) > 70 else "sub"
            clips.append(f'<div class="{cls} clip" id="u{i}" data-start="{t + .3:.2f}" data-duration="{d - .3:.2f}" data-track-index="3">{a}<br><u id="ul{i}">{b}</u></div>')
            js.append(f'tl.from("#u{i}", {{opacity: 0, y: 40, duration: .45, ease: "power3.out"}}, {t + .3:.2f})'
                      f'.to("#ul{i}", {{"--w": "100%", duration: .5, ease: "power2.out"}}, {t + .9:.2f})'
                      f'.to("#u{i}", {{opacity: 0, filter: "blur(10px)", duration: .25}}, {t + d - .3:.2f});')
        t += d
    total = round(t + END, 2)
    if style.get("cut") == "story":  # полоса прогресса до финальной карточки
        clips.append(f'<div class="prog clip" id="prog" data-start="0" data-duration="{t:.2f}" data-track-index="7"><i id="pgi"></i></div>')
        js.append(f'tl.fromTo("#pgi", {{scaleX: 0}}, {{scaleX: 1, duration: {t:.2f}, ease: "none"}}, 0);')
    clips.append(f"""<div class="end clip" id="fin" data-start="{t:.2f}" data-duration="{END}" data-track-index="1">
        <div class="brand" id="brand"><img src="./logo.png" />Kelechek AI</div>
        <div class="slogan" id="slogan">{esc(rng.one(SLOGANS))}</div>
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
<style>{CSS}
{themes.css(style)}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
<div class="bg"></div><div class="deco"></div><div class="glow" id="glow"></div>
<div class="streak" id="st1" style="top:520px"></div><div class="streak" id="st2" style="top:1380px"></div><div class="vig"></div><div id="flash"></div>{'<div class="frame"><b>KELECHEK AI</b></div>' if style.get("layout") == "frame" else ""}
{chr(10).join(clips)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.to("#glow", {{ x: 120, y: -160, scale: 1.15, duration: {total}, ease: "sine.inOut" }}, 0)
  .fromTo("#st1", {{ x: -500 }}, {{ x: 600, duration: {total}, ease: "none" }}, 0)
  .fromTo("#st2", {{ x: 500 }}, {{ x: -600, duration: {total}, ease: "none" }}, 0);
{themes.deco_js(style, total)}
{chr(10).join(js)}
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
tl.seek(0);
</script></body></html>"""
    return themes.apply(page, style), total


def prep_footage(clips, work):
    """Стоковые клипы -> короткие вертикальные файлы в папке композиции, с тем же цветом, что и весь ролик."""
    names = []
    for k, clip in enumerate(clips or []):
        name = f"foot{k}.mp4"
        try:
            length = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                                          capture_output=True, text=True).stdout.strip() or 0)
            start = round(random.uniform(0, max(0, length - 9)), 2)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{start}", "-i", str(clip), "-t", "9", "-an",
                            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setpts=1.15*PTS,fps=30,"
                                   "eq=contrast=1.06:saturation=0.9,colorbalance=rs=0.03:bs=-0.03,format=yuv420p",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(work / name)], check=True)
            names.append(name)
        except Exception as e:
            print(f"Клип {clip} не подготовлен: {e}")
    return names


def render(text, music, out, seed=None, workdir=None, footage=None, style=None):
    """Собирает ролик: HTML-композиция -> MP4 через HyperFrames, затем музыка через ffmpeg."""
    work = Path(workdir or HERE / "out" / "hf")
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(HF_ASSETS, work)
    page, total = compose(text, seed, prep_footage(footage, work), style)
    (work / "index.html").write_text(page, encoding="utf-8")
    (work / "meta.json").write_text(json.dumps({"id": "reel", "name": "reel"}), encoding="utf-8")
    silent = work / "silent.mp4"
    r = subprocess.run(["npx", "--yes", f"hyperframes@{HF_VERSION}", "render", "-o", str(silent)], cwd=work,
                       capture_output=True, text=True)
    if r.returncode or not silent.exists():
        print((r.stdout + r.stderr)[-3000:])
        raise RuntimeError("HyperFrames не собрал ролик")
    fade = max(0.0, total - 1.5)
    length = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(music)],
                            capture_output=True, text=True).stdout.strip()
    spare = float(length or 0) - total - 1
    start = round(random.uniform(0, min(spare, 20)), 2) if spare > 4 else 0.0  # трек начинается с разных мест
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(silent), "-ss", f"{start}", "-i", str(music), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-af", f"afade=t=in:d=0.5,afade=t=out:st={fade:.2f}:d=1.5,volume=0.8", "-shortest", str(out)], check=True)
    return total


if __name__ == "__main__":
    music = sorted((HERE / "assets" / "music").glob("*.mp3"))[0]
    print(render(sys.argv[1], music, Path(sys.argv[2])))
