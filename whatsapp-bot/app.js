// Мини-приложение Kelechek AI внутри Telegram: услуги, как работаем, заявка на бесплатный пример.
// Цены «от» утвердил владелец 2026-10-07; держать в синхроне с PRICES в worker.js.
export const APP_HTML = `<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Kelechek AI</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--bg:#0F1115;--card:#181B22;--text:#F2F3F5;--muted:#9AA0AB;--accent:#F2B33D;--accent-text:#1A1406;--line:#262A33;--ok:#3FB97A}
:root[data-theme=light]{--bg:#F6F5F2;--card:#FFFFFF;--text:#16181D;--muted:#5E6470;--accent:#A66C08;--accent-text:#FFFFFF;--line:#E4E1DA;--ok:#1F8A55}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:16px 16px 96px}
h1{font-size:26px;line-height:1.15;letter-spacing:-.02em}
h2{font-size:18px;margin:28px 0 12px}
.muted{color:var(--muted)}
.hero{padding:8px 0 4px}
.hero p{margin-top:8px}
.badge{display:inline-block;background:var(--accent);color:var(--accent-text);font-weight:600;font-size:13px;border-radius:999px;padding:4px 10px;margin-bottom:12px}
.tabs{display:flex;gap:8px;margin:20px 0 4px;overflow-x:auto}
.tab{flex:0 0 auto;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;padding:8px 14px;font-size:14px}
.tab.on{background:var(--text);color:var(--bg);border-color:var(--text)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin-bottom:10px}
.card h3{font-size:16px;margin-bottom:4px}
.card .ic{font-size:22px;margin-bottom:6px}
.card button{margin-top:12px}
.steps{counter-reset:s}
.step{display:flex;gap:12px;margin-bottom:12px}
.step:before{counter-increment:s;content:counter(s);flex:0 0 28px;height:28px;border-radius:50%;background:var(--accent);color:var(--accent-text);font-weight:700;display:grid;place-items:center;font-size:14px}
label{display:block;font-size:14px;color:var(--muted);margin:14px 0 6px}
input,select,textarea{width:100%;background:var(--card);border:1px solid var(--line);color:var(--text);border-radius:12px;padding:12px;font:inherit}
textarea{min-height:80px;resize:vertical}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;padding:8px 12px;font-size:14px}
.chip.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 18%,var(--card))}
button.main{width:100%;background:var(--accent);color:var(--accent-text);border:0;border-radius:14px;padding:14px;font-size:16px;font-weight:600;font-family:inherit}
button.ghost{background:transparent;border:1px solid var(--line);color:var(--text);border-radius:12px;padding:10px 12px;font:inherit;font-size:14px}
.done{text-align:center;padding:40px 8px}
.done .big{font-size:48px}
.hide{display:none}
.price{margin-top:8px;font-weight:600;color:var(--accent)}
h3.grp{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:22px 0 10px}
.note{font-size:13px;margin-top:10px}
</style></head><body>
<section class="hero">
  <span class="badge">🎁 Первым клиентам 15 дней бесплатно</span>
  <h1>ИИ-видео и автоматизация для вашего бизнеса</h1>
  <p class="muted">Kelechek AI, Бишкек. Делаем ролики, автоответы и рекламу, чтобы клиенты писали сами.</p>
</section>

<div class="tabs" role="tablist">
  <button class="tab on" data-t="services">Услуги</button>
  <button class="tab" data-t="how">Как работаем</button>
  <button class="tab" data-t="order">Бесплатный пример</button>
</div>

<div id="services">
  <h2>Что мы делаем</h2>
  <h3 class="grp">Видео и контент</h3>
  <div class="card"><div class="ic">🎬</div><h3>Reels и видео на ИИ</h3><p class="muted">Ролик про ваш бизнес в вашем стиле: монтаж, текст на экране, музыка, озвучка.</p><p class="price">от 3 000 сом · 6 роликов от 15 000</p><button class="ghost" data-pick="Reels">Хочу пример</button></div>
  <div class="card"><div class="ic">🗣</div><h3>Ролик с ИИ-ведущим</h3><p class="muted">Говорящий аватар рассказывает о вашем товаре или акции. Лицо и голос только с согласия человека.</p><p class="price">от 10 000 сом</p><button class="ghost" data-pick="ИИ-ведущий">Обсудить</button></div>
  <div class="card"><div class="ic">🎙</div><h3>Озвучка и перевод</h3><p class="muted">Переводим и озвучиваем ролик на кыргызский, казахский или узбекский, чтобы охватить всю Центральную Азию.</p><p class="price">от 2 500 сом за ролик</p><button class="ghost" data-pick="Перевод">Обсудить</button></div>
  <div class="card"><div class="ic">📸</div><h3>ИИ-фото товаров и меню</h3><p class="muted">Красивые фото для каталога, меню и рекламы без фотостудии.</p><p class="price">от 4 500 сом за 10 фото</p><button class="ghost" data-pick="ИИ-фото">Обсудить</button></div>
  <div class="card"><div class="ic">✍️</div><h3>Тексты для соцсетей</h3><p class="muted">Посты живым языком, без шаблонов, под ваш бизнес.</p><p class="price">5 текстов от 4 500 сом</p><button class="ghost" data-pick="Тексты">Обсудить</button></div>
  <h3 class="grp">Автоматизация</h3>
  <div class="card"><div class="ic">💬</div><h3>Автоответы в WhatsApp и Telegram</h3><p class="muted">ИИ-ассистент отвечает клиентам сам, а вам приходят только готовые к покупке.</p><p class="price">настройка от 19 000 сом · поддержка от 5 000 сом/мес</p><button class="ghost" data-pick="Автоответы">Хочу так же</button></div>
  <div class="card"><div class="ic">🤖</div><h3>Telegram-бот с приложением</h3><p class="muted">Как этот: каталог, заявки и запись прямо в Telegram.</p><p class="price">от 32 000 сом</p><button class="ghost" data-pick="Telegram-бот">Хочу так же</button></div>
  <div class="card"><div class="ic">📅</div><h3>Страница онлайн-записи</h3><p class="muted">Сайт-визитка, где клиент сам выбирает услугу и время.</p><p class="price">от 19 000 сом</p><button class="ghost" data-pick="Онлайн-запись">Хочу так же</button></div>
  <h3 class="grp">Продвижение</h3>
  <div class="card"><div class="ic">🎯</div><h3>Таргетированная реклама</h3><p class="muted">Instagram и Facebook: аудитория по городу и интересам, креативы на ИИ, заявки сразу в чат, отчёт раз в неделю. Рекламный бюджет вы платите напрямую в Meta.</p><p class="price">ведение от 25 000 сом/мес</p><button class="ghost" data-pick="Реклама">Обсудить</button></div>
  <div class="card"><div class="ic">📱</div><h3>Instagram под ключ</h3><p class="muted">Контент-план, 12 постов, 4 Reels и сторис каждый месяц.</p><p class="price">от 50 000 сом/мес</p><button class="ghost" data-pick="Instagram под ключ">Обсудить</button></div>
  <p class="muted note">Цены «от»: точную сумму Даниэль назовёт после пары вопросов. На ведение первым клиентам 15 дней бесплатно, вы платите только подписку на ИИ-сервис.</p>
  <div style="height:12px"></div>
  <button class="ghost" style="width:100%" data-wa>💬 Написать Даниэлю в WhatsApp</button>
</div>

<div id="how" class="hide">
  <h2>Как работаем</h2>
  <div class="steps">
    <div class="step"><div><b>Знакомимся.</b> <span class="muted">Пара вопросов о бизнесе. В Бишкеке встречаемся лично и показываем всё на ноутбуке.</span></div></div>
    <div class="step"><div><b>Бесплатный пример.</b> <span class="muted">Делаем ролик под ваш бизнес, чтобы вы увидели результат до оплаты.</span></div></div>
    <div class="step"><div><b>15 дней работы бесплатно.</b> <span class="muted">Вы оплачиваете только подписку на нужный ИИ-сервис.</span></div></div>
    <div class="step"><div><b>Дальше цена из прайса.</b> <span class="muted">Отчёт каждую неделю и в конце месяца.</span></div></div>
  </div>
  <button class="main" data-go="order">Получить бесплатный пример</button>
</div>

<form id="order" class="hide" autocomplete="on">
  <h2>Бесплатный пример ролика</h2>
  <p class="muted">Заполните, и мы сделаем пример под ваш бизнес.</p>
  <label for="biz">Название бизнеса</label>
  <input id="biz" name="biz" required maxlength="80" placeholder="Например, кофейня «Арча»">
  <label for="niche">Чем занимаетесь</label>
  <input id="niche" name="niche" required maxlength="120" placeholder="Кофе с собой и десерты">
  <label for="city">Город</label>
  <select id="city" name="city"><option>Бишкек</option><option>Ош</option><option>Алматы</option><option>Ташкент</option><option>Другой</option></select>
  <label>Что нужно</label>
  <div class="chips" id="needs">
    <button type="button" class="chip" data-v="Reels">🎬 Reels</button>
    <button type="button" class="chip" data-v="Автоответы">💬 Автоответы</button>
    <button type="button" class="chip" data-v="Реклама">🎯 Реклама</button>
    <button type="button" class="chip" data-v="Тексты">✍️ Тексты</button>
    <button type="button" class="chip" data-v="ИИ-ведущий">🗣 ИИ-ведущий</button>
    <button type="button" class="chip" data-v="Перевод">🎙 Перевод</button>
    <button type="button" class="chip" data-v="ИИ-фото">📸 ИИ-фото</button>
    <button type="button" class="chip" data-v="Telegram-бот">🤖 Telegram-бот</button>
    <button type="button" class="chip" data-v="Онлайн-запись">📅 Онлайн-запись</button>
    <button type="button" class="chip" data-v="Instagram под ключ">📱 Instagram</button>
  </div>
  <label for="pain">Что сейчас мешает больше всего</label>
  <select id="pain" name="pain"><option value="">Выберите</option><option>Мало заявок</option><option>Нет видео и контента</option><option>Не успеваем отвечать клиентам</option><option>Реклама не окупается</option><option>Просто интересно</option></select>
  <label for="when">Когда хотите начать</label>
  <select id="when" name="when"><option value="">Выберите</option><option>В этом месяце</option><option>Через 1–3 месяца</option><option>Пока присматриваюсь</option></select>
  <label for="note">Комментарий (необязательно)</label>
  <textarea id="note" name="note" maxlength="500" placeholder="Ссылка на Instagram, пожелания по стилю"></textarea>
  <p class="muted note">После отправки бот напишет вам в этот чат. Фото для ролика можно будет прислать туда же.</p>
  <div style="height:16px"></div>
  <button class="main" type="submit" id="send">Отправить заявку</button>
</form>

<div id="done" class="done hide">
  <div class="big">✅</div>
  <h2>Заявка отправлена</h2>
  <p class="muted">Ассистент уже написал вам в чат. Даниэль посмотрит заявку лично.</p>
  <div style="height:16px"></div>
  <button class="main" id="close">Вернуться в чат</button>
</div>

<script>
const tg = window.Telegram?.WebApp;
try { tg.ready(); tg.expand(); if (tg.colorScheme === "light") document.documentElement.dataset.theme = "light"; } catch (e) {}
const show = id => {
  for (const s of ["services", "how", "order", "done"]) document.getElementById(s).classList.toggle("hide", s !== id);
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.dataset.t === id));
  window.scrollTo(0, 0);
};
document.querySelectorAll(".tab").forEach(t => t.onclick = () => show(t.dataset.t));
document.querySelectorAll("[data-go]").forEach(b => b.onclick = () => show(b.dataset.go));
const needs = new Set();
const setNeed = (v, on) => { on ? needs.add(v) : needs.delete(v); document.querySelectorAll("#needs .chip").forEach(c => c.classList.toggle("on", needs.has(c.dataset.v))); };
document.querySelectorAll("#needs .chip").forEach(c => c.onclick = () => setNeed(c.dataset.v, !needs.has(c.dataset.v)));
document.querySelectorAll("[data-pick]").forEach(b => b.onclick = () => { setNeed(b.dataset.pick, true); show("order"); });
document.getElementById("order").onsubmit = async e => {
  e.preventDefault();
  const btn = document.getElementById("send");
  btn.disabled = true; btn.textContent = "Отправляем…";
  const f = Object.fromEntries(new FormData(e.target));
  f.needs = [...needs];
  try {
    const r = await fetch("/app/lead", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ initData: tg?.initData || "", form: f }) });
    if (!r.ok) throw new Error(await r.text());
    try { tg.HapticFeedback.notificationOccurred("success"); } catch (_) {}
    show("done");
  } catch (err) {
    btn.disabled = false; btn.textContent = "Отправить заявку";
    alert("Не получилось отправить. Откройте приложение из чата с ботом и попробуйте ещё раз.");
  }
};
document.querySelectorAll("[data-wa]").forEach(b => b.onclick = () => { const u = "https://wa.me/996502091443?text=Telegram"; try { tg.openLink(u); } catch (_) { location.href = u; } });
document.getElementById("close").onclick = () => { try { tg.close(); } catch (_) {} };
</script>
</body></html>`;
