import { APP_HTML } from "./app.js";

// ИИ-менеджер Kelechek AI в WhatsApp: отвечает клиентам, квалифицирует по BANT,
// зовёт владельца к горячим. Cloudflare Worker + WhatsApp Cloud API + Gemini.
//
// Секреты (wrangler secret put ...): WA_TOKEN, WA_PHONE_ID, WA_APP_SECRET, VERIFY_TOKEN,
// GEMINI_KEY, LEADS_KEY; по желанию TG_BOT_TOKEN и TG_CHAT_ID для мгновенных уведомлений.
// Telegram-версия для клиентов: TG_CLIENT_TOKEN (бот от @BotFather), вебхук /tg ставит workflow.
// KV: CHATS (переписки и баллы).

const GRAPH = "https://graph.facebook.com/v22.0";
const HISTORY = 30;            // сколько последних сообщений помнит бот
const HUMAN_PAUSE_H = 12;      // владелец написал сам: бот молчит в этом чате столько часов
const MAX_REPLY = 900;

// Прайс «от», в сомах. Утвердил владелец 2026-10-07, поднят на ~25% по просьбе владельца.
const PRICES = `🎬 Reels под ключ: от 5 000 сом за ролик, пакет из 4 роликов от 18 000 сом.
🗣 Ролик с ИИ-ведущим (говорящий аватар): от 8 000 сом. Лицо и голос только с согласия человека.
🎙 Озвучка и перевод ролика на кыргызский, казахский или узбекский: от 2 000 сом.
📸 ИИ-фото товаров и меню: от 3 500 сом за 10 фото.
✍️ Пакет из 5 текстов для соцсетей: от 3 500 сом.
💬 Автоответы в WhatsApp или Telegram: настройка от 15 000 сом, поддержка от 4 000 сом в месяц.
🤖 Telegram-бот с мини-приложением (каталог, заявки, запись): от 25 000 сом.
📅 Страница онлайн-записи или сайт-визитка: от 15 000 сом.
🎯 Таргетированная реклама в Instagram и Facebook: ведение от 15 000 сом в месяц, рекламный бюджет вы платите напрямую в Meta.
📱 Instagram под ключ (контент-план, 12 постов, 4 Reels, сторис): от 30 000 сом в месяц.`;

const SYSTEM = `Ты ИИ-ассистент Kelechek AI в WhatsApp. Kelechek AI из Бишкека делает ИИ-видео (Reels, реклама) и автоматизацию для бизнеса (автоответы в WhatsApp, контент для соцсетей), а также ведёт таргетированную рекламу в Instagram и Facebook (настройка аудитории, креативы на ИИ, заявки в WhatsApp, отчёт раз в неделю; рекламный бюджет клиент платит напрямую в Meta). Владелец: Даниэль.

Услуги и цены «от» (называй только их, других цифр не придумывай):
${PRICES}

Как мы работаем: на ведение (автоответы, таргет, Instagram под ключ) первым клиентам 15 дней работы бесплатно, клиент оплачивает только подписку на нужный ИИ-сервис, потом цена из прайса. Разовые услуги (ролик, фото, тексты) оплачиваются по прайсу. Отчёты каждую неделю и в конце месяца. В Бишкеке владелец встречается лично и показывает всё на ноутбуке.

Правила:
- В первом ответе человеку скажи, что ты ИИ-ассистент Kelechek AI. Себя за человека не выдавай.
- Пиши коротко, живо, по-человечески, 1–4 предложения. Язык клиента: русский или кыргызский.
- Цены называй только «от» из прайса выше и добавляй, что точную сумму Даниэль назовёт после пары вопросов о задаче. Не придумывай другие цены, сроки, цифры результатов, кейсы и отзывы.
- Портфолио собираем сейчас, поэтому есть бесплатный пример ролика под бизнес клиента и 15 дней пробы.
- Задавай один вопрос за сообщение, чтобы выяснить BANT по порядку: N (что за бизнес и что болит: мало заявок, нет видео, не успевают отвечать), A (владелец ли, решает ли сам), T (когда хочет начать), B (готов ли оплачивать подписку на ИИ-сервисы и работу после 15 дней).
- Не спрашивай то, что уже известно из переписки.
- Если клиент просит живого человека, хочет встречу или всё ясно и он готов, скажи, что Даниэль напишет ему лично, и поставь wants_human = true.
- На грубость и спам отвечай вежливо и коротко.

Баллы BANT, 0–2 только по фактам из слов клиента, иначе null:
N: 0 просто интересно, 1 хочет больше клиентов без конкретики, 2 чёткая боль.
A: 0 сотрудник без полномочий, 1 решает не один, 2 владелец и решает сам.
T: 0 «когда-нибудь», 1 через 1–3 месяца, 2 в этом месяце.
B: 0 только бесплатно, 1 готов, но «если будет результат», 2 готов платить подписки и ставку.

Отсев (время владельца только на тех, кто реально купит):
- Когда N, A, T известны, спроси про B мягко: «Работаем так: 15 дней бесплатно, вы оплачиваете только подписку на ИИ-сервис, потом цена из прайса. Вам такой формат подходит?»
- Горячий (сумма 7–8, или просит встречу, или готов начать): скажи, что Даниэль напишет лично; если клиент из Бишкека, предложи личную встречу с показом на ноутбуке. wants_human = true, tier = "hot".
- Тёплый (сумма 4–6): предложи бесплатный пример ролика под его бизнес (нужны название, чем занимается, 2–3 фото), узнай недостающую букву. tier = "warm".
- Холодный (все четыре буквы известны и сумма 0–3, или прямо говорит «только бесплатно», «просто посмотреть», «я не решаю и решать не буду»): вежливо поблагодари, оставь контакт на будущее и больше ничего не продавай и не спрашивай. Не зови владельца. tier = "cold".
- Если в чате уже стоит холодный и человек пишет снова без нового интереса, ответь коротко и дружелюбно, без новых вопросов. Если появился реальный интерес (боль, сроки, готов платить), оценивай заново.
- Спам, реклама, поиск работы, просьбы не по теме: один вежливый короткий ответ, tier = "cold".
Пока данных мало, tier = "unknown".`;

const SCHEMA = {
  type: "OBJECT",
  properties: {
    reply: { type: "STRING" },
    n: { type: "INTEGER", nullable: true }, a: { type: "INTEGER", nullable: true },
    t: { type: "INTEGER", nullable: true }, b: { type: "INTEGER", nullable: true },
    name: { type: "STRING", nullable: true }, niche: { type: "STRING", nullable: true },
    city: { type: "STRING", nullable: true }, request: { type: "STRING", nullable: true },
    next: { type: "STRING", description: "следующий шаг для владельца одной фразой" },
    wants_human: { type: "BOOLEAN" },
    tier: { type: "STRING", enum: ["hot", "warm", "cold", "unknown"] },
  },
  required: ["reply", "next", "wants_human"],
};

// Политика конфиденциальности для публикации приложения Meta
const PRIVACY = `<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kelechek AI: политика конфиденциальности</title><style>body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.6;color:#222}</style></head><body>
<h1>Политика конфиденциальности Kelechek AI</h1>
<p>Kelechek AI (Бишкек, Кыргызстан) использует WhatsApp Business и страницы в соцсетях, чтобы отвечать на вопросы клиентов о наших услугах: ИИ-видео, автоматизация и реклама для бизнеса.</p>
<h2>Какие данные мы получаем</h2>
<p>Ваше имя в профиле WhatsApp, номер телефона и текст сообщений, которые вы нам отправляете.</p>
<h2>Зачем</h2>
<p>Только чтобы ответить вам, понять вашу задачу и передать заявку владельцу. На сообщения сначала отвечает ИИ-ассистент, он честно говорит, что он ИИ. Для подготовки ответов текст переписки обрабатывается сервисом Google Gemini.</p>
<h2>Хранение</h2>
<p>Мы храним последние сообщения переписки, чтобы помнить контекст разговора. Мы не продаём и не передаём ваши данные третьим лицам для рекламы.</p>
<h2>Удаление данных</h2>
<p>Напишите нам в WhatsApp +996 502 091 443 «удалите мои данные», и мы удалим переписку и заявку.</p>
<p>Контакт: +996 502 091 443, Instagram и Threads @kelechek_ai.</p>
</body></html>`;

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (url.pathname === "/webhook" && req.method === "GET") return verify(url, env);
    if (url.pathname === "/webhook" && req.method === "POST") {
      const raw = await req.text();
      const sigOk = await signatureOk(raw, req.headers.get("x-hub-signature-256"), env.WA_APP_SECRET);
      // для /health: дошёл ли вообще запрос от Meta и прошла ли подпись (без содержимого сообщений)
      let fields = [];
      try { fields = JSON.parse(raw).entry?.flatMap(e => (e.changes || []).map(c => c.field)) || []; } catch {}
      await env.CHATS.put("health:last_post", JSON.stringify({ at: new Date().toISOString(), signature_ok: sigOk, has_signature: !!req.headers.get("x-hub-signature-256"), fields }));
      if (!sigOk) return new Response("bad signature", { status: 401 });
      ctx.waitUntil(handle(JSON.parse(raw), env).catch(e => console.log("handle error", e.stack || e)));
      return new Response("ok");
    }
    if (url.pathname === "/tg" && req.method === "POST") {
      // Telegram подписывает запрос секретом, который мы задали при setWebhook (производный от токена бота)
      if (!env.TG_CLIENT_TOKEN || req.headers.get("x-telegram-bot-api-secret-token") !== await tgSecret(env)) return new Response("forbidden", { status: 403 });
      const update = await req.json();
      ctx.waitUntil(onTelegram(update, env).catch(e => env.CHATS.put("health:last_crash", JSON.stringify({ at: new Date().toISOString(), where: "telegram", message: String(e.stack || e).slice(0, 400) }))));
      return new Response("ok");
    }
    if (url.pathname === "/leads" && req.method === "GET") return leads(req, env);
    if (url.pathname === "/health") return health(env);
    if (url.pathname === "/app") return new Response(APP_HTML, { headers: { "content-type": "text/html; charset=utf-8" } });
    if (url.pathname === "/app/lead" && req.method === "POST") return appLead(req, env, ctx);
    if (url.pathname === "/privacy") return new Response(PRIVACY, { headers: { "content-type": "text/html; charset=utf-8" } });
    return new Response("Kelechek AI WhatsApp bot", { status: 200 });
  },
};

function verify(url, env) {
  const ok = url.searchParams.get("hub.mode") === "subscribe" && (url.searchParams.get("hub.verify_token") || "").trim() === (env.VERIFY_TOKEN || "").trim().replace(/^[`'"]+|[`'"]+$/g, "");
  return ok ? new Response(url.searchParams.get("hub.challenge")) : new Response("forbidden", { status: 403 });
}

async function signatureOk(raw, header, secret) {
  secret = (secret || "").trim().replace(/^[`'"]+|[`'"]+$/g, "");
  if (!header || !secret) return false;
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw));
  const hex = [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2, "0")).join("");
  return header === "sha256=" + hex;
}

async function handle(body, env) {
  for (const entry of body.entry || []) {
    for (const change of entry.changes || []) {
      const v = change.value || {};
      // владелец ответил сам из приложения WhatsApp Business: бот уступает чат
      for (const echo of v.message_echoes || []) await pauseForHuman(env, echo.to);
      const names = Object.fromEntries((v.contacts || []).map(c => [c.wa_id, c.profile?.name]));
      for (const m of v.messages || []) await onMessage(m, names[m.from], env);
      // статус доставки наших ответов: sent / delivered / read / failed (с кодом ошибки Meta, без номеров)
      for (const st of v.statuses || []) await env.CHATS.put("health:last_status", JSON.stringify({ at: new Date().toISOString(), status: st.status, errors: (st.errors || []).map(e => ({ code: e.code, title: e.title, details: (e.error_data?.details || "").replace(/\+?\d{7,}/g, "…") })) }));
    }
  }
}

async function pauseForHuman(env, waId) {
  if (!waId) return;
  const chat = await loadChat(env, waId);
  chat.humanUntil = Date.now() + HUMAN_PAUSE_H * 3600e3;
  await saveChat(env, waId, chat);
}

async function onMessage(m, profileName, env) {
  await env.CHATS.put("health:last_message_at", new Date().toISOString());
  if (await env.CHATS.get("msg:" + m.id)) return;                 // Meta иногда шлёт дважды
  await env.CHATS.put("msg:" + m.id, "1", { expirationTtl: 86400 });
  await markRead(env, m.id);
  await converse(env, {
    key: m.from, channel: "WhatsApp", contact: "+" + m.from, profileName,
    text: messageText(m), reply: text => send(env, m.from, text),
  });
}

// Общий разговор для любого канала: история, ответ Gemini, BANT, уведомление владельцу о горячем
async function converse(env, { key, channel, contact, profileName, text, source, reply: deliver }) {
  const chat = await loadChat(env, key);
  chat.channel = channel;
  chat.contact = contact || chat.contact;
  chat.profileName = profileName || chat.profileName;
  chat.history.push({ role: "user", text, ts: Date.now() });
  if (!chat.firstAt) {
    chat.firstAt = Date.now();
    chat.source = source || sourceOf(text, channel);
  }

  if (chat.humanUntil && chat.humanUntil > Date.now()) return saveChat(env, key, chat);

  let out;
  try { out = await withRetry(() => think(env, chat, channel)); }
  catch (e) {
    console.log("gemini error", e.message);
    await env.CHATS.put("health:last_gemini_error", JSON.stringify({ at: new Date().toISOString(), message: String(e.message || e).replace(/\+?\d{7,}/g, "…").slice(0, 400) }));
    out = { reply: "Спасибо за сообщение! Сейчас передам его Даниэлю, он ответит лично.", next: "ответить вручную: бот не смог ответить", wants_human: true };
  }
  for (const k of ["n", "a", "t", "b"]) if (out[k] === 0 || out[k] === 1 || out[k] === 2) chat.bant[k] = out[k];
  for (const k of ["name", "niche", "city", "request"]) if (out[k]) chat[k] = out[k];
  chat.next = out.next;
  if (out.tier && out.tier !== "unknown") chat.tier = out.tier;
  const reply = out.reply.slice(0, MAX_REPLY);
  await deliver(reply);
  await env.CHATS.put("health:last_reply_at", new Date().toISOString());
  chat.history.push({ role: "model", text: reply, ts: Date.now() });

  const score = ["n", "a", "t", "b"].reduce((s, k) => s + (chat.bant[k] ?? 0), 0);
  // холодных владельцу не шлём, даже если бот вежливо сказал «Даниэль посмотрит»
  const hot = chat.tier !== "cold" && (score >= 7 || out.wants_human || chat.tier === "hot");
  if (hot && !chat.notifiedAt) {
    chat.notifiedAt = Date.now();
    await notifyOwner(env, `🔥 ${channel} ${chat.contact || ""} ${chat.name || chat.profileName || ""}: ${chat.request || chat.niche || ""}. BANT ${score}/8. ${chat.next}`);
  }
  await saveChat(env, key, chat);
}

function messageText(m) {
  if (m.type === "text") return m.text.body;
  if (m.type === "button") return m.button.text;
  if (m.type === "interactive") return m.interactive.button_reply?.title || m.interactive.list_reply?.title || "[кнопка]";
  return `[${m.type}: клиент прислал не текст, ${m.type === "audio" ? "попроси написать текстом, голосовые бот пока не слушает" : "поблагодари и спроси, что он хотел показать"}]`;
}

function sourceOf(text, channel = "WhatsApp") {
  const w = (text || "").trim().split(/\s+/)[0].toLowerCase();
  if (w.startsWith("threads")) return "Threads";
  if (w.startsWith("instagram")) return "Instagram";
  if (w.startsWith("пример")) return "Threads";
  return channel;
}

async function think(env, chat, channel = "WhatsApp") {
  const tierNote = chat.tier ? ` Текущая оценка клиента: ${chat.tier}.` : "";
  const known = Object.entries(chat.bant).filter(([, v]) => v !== null).map(([k, v]) => `${k.toUpperCase()}=${v}`).join(", ") || "ничего";
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${env.GEMINI_MODEL || "gemini-3.8-flash"}:generateContent`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_KEY },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: SYSTEM.replace("в WhatsApp.", `в ${channel}.`) + `\n\nУже известно по BANT: ${known}.${tierNote}` }] },
      contents: fromUser(chat.history.slice(-HISTORY)).map(h => ({ role: h.role, parts: [{ text: h.text }] })),
      generationConfig: { temperature: 0.6, responseMimeType: "application/json", responseSchema: SCHEMA },
    }),
  });
  if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 300)}`);
  const data = await r.json();
  const out = JSON.parse(data.candidates[0].content.parts[0].text);
  if (!out.reply) throw new Error("empty reply");
  return out;
}

// Gemini бывает перегружен (503/429): пробуем ещё два раза с паузой, укладываемся в лимит времени Worker
async function withRetry(fn) {
  let last;
  for (const wait of [0, 1500, 4000]) {
    if (wait) await new Promise(r => setTimeout(r, wait));
    try { return await fn(); }
    catch (e) { last = e; if (!/^(503|429|500)/.test(String(e.message))) throw e; }
  }
  throw last;
}

// Gemini требует, чтобы разговор начинался с сообщения клиента
function fromUser(h) {
  const i = h.findIndex(x => x.role === "user");
  return i < 0 ? h : h.slice(i);
}

async function graph(env, body) {
  const r = await fetch(`${GRAPH}/${env.WA_PHONE_ID}/messages`, {
    method: "POST",
    headers: { authorization: `Bearer ${env.WA_TOKEN}`, "content-type": "application/json" },
    body: JSON.stringify({ messaging_product: "whatsapp", ...body }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    const e = err.error || {};
    console.log("graph error", r.status, JSON.stringify(e).slice(0, 300));
    // для /health: только код и текст ошибки Meta, без номеров и переписки
    await env.CHATS.put("health:last_error", JSON.stringify({ at: new Date().toISOString(), status: r.status, code: e.code, message: (e.message || "").replace(/\+?\d{7,}/g, "…") }));
  }
}

const send = (env, to, text) => graph(env, { recipient_type: "individual", to, type: "text", text: { body: text } });
const markRead = (env, id) => graph(env, { status: "read", message_id: id });

// ---------- Telegram: тот же ИИ-менеджер, без требований Meta к документам ----------
async function tgSecret(env) {
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("kelechek-tg:" + env.TG_CLIENT_TOKEN));
  return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, "0")).join("").slice(0, 48);
}

async function tg(env, method, body) {
  const r = await fetch(`https://api.telegram.org/bot${env.TG_CLIENT_TOKEN}/${method}`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) await env.CHATS.put("health:last_error", JSON.stringify({ at: new Date().toISOString(), channel: "Telegram", status: r.status, message: ((await r.json().catch(() => ({}))).description || "").slice(0, 200) }));
  return r;
}

// Кнопки под полем ввода: всегда под рукой, последняя открывает мини-приложение
function menu(env) {
  return { keyboard: [
    [{ text: "🎬 Услуги" }, { text: "🎁 Бесплатный пример" }],
    [{ text: "📅 Встреча в Бишкеке" }, { text: "👤 Связаться с Даниэлем" }],
    [{ text: "📱 Открыть приложение", web_app: { url: env.APP_URL } }],
  ], resize_keyboard: true, is_persistent: true, input_field_placeholder: "Напишите вопрос или выберите кнопку" };
}

const SERVICES_TEXT = `Услуги и цены:

${PRICES}

Цены «от»: точную сумму Даниэль назовёт после пары вопросов о задаче. На ведение первым клиентам 15 дней бесплатно, вы платите только подписку на ИИ-сервис. Пример ролика под ваш бизнес бесплатно.

Расскажите, чем занимается ваш бизнес, и я подскажу, с чего начать.`;

// Кнопка-подсказка превращается в понятную фразу для ИИ
const BUTTONS = {
  "🎁 Бесплатный пример": "Хочу бесплатный пример ролика для моего бизнеса",
  "📅 Встреча в Бишкеке": "Хочу встретиться лично в Бишкеке и посмотреть, как это работает",
};
const OWNER_WA = "https://wa.me/996502091443?text=Telegram";

async function onTelegram(update, env) {
  const m = update.message;
  if (!m || m.chat?.type !== "private" || m.from?.is_bot) return;
  await env.CHATS.put("health:last_message_at", new Date().toISOString());
  if (await env.CHATS.get("tgmsg:" + update.update_id)) return;
  await env.CHATS.put("tgmsg:" + update.update_id, "1", { expirationTtl: 86400 });
  const chatId = m.chat.id;
  // владелец узнаёт свой chat id командой /id, чтобы получать уведомления о горячих заявках
  if (m.text === "/id") return tg(env, "sendMessage", { chat_id: chatId, text: `Ваш chat id: ${chatId}` });
  // /leads: список клиентов по группам, только владельцу (chat id из секрета TG_CHAT_ID)
  if (m.text === "/leads" || m.text === "/clients") {
    if (String(chatId) !== String(env.TG_CHAT_ID || "")) return tg(env, "sendMessage", { chat_id: chatId, text: "Эта команда только для владельца." });
    return tg(env, "sendMessage", { chat_id: chatId, text: await leadsText(env) });
  }
  // /reset: начать разговор с нуля (удобно для проверки бота владельцем)
  if (m.text === "/reset") { await env.CHATS.delete("chat:tg" + chatId); return tg(env, "sendMessage", { chat_id: chatId, text: "Начинаем заново. Напишите, чем занимается ваш бизнес 🙂", reply_markup: menu(env) }); }
  if (m.text === "🎬 Услуги") {
    const chat = await loadChat(env, "tg" + chatId);
    chat.history.push({ role: "user", text: "Покажите услуги", ts: Date.now() }, { role: "model", text: SERVICES_TEXT, ts: Date.now() });
    await saveChat(env, "tg" + chatId, chat);
    return tg(env, "sendMessage", { chat_id: chatId, text: SERVICES_TEXT, reply_markup: { inline_keyboard: [[{ text: "📱 Подробнее в приложении", web_app: { url: env.APP_URL } }]] } });
  }
  // «Связаться с Даниэлем»: сразу ссылка на WhatsApp владельца и уведомление ему
  if (m.text === "👤 Связаться с Даниэлем") {
    const chat = await loadChat(env, "tg" + chatId);
    const who = m.from.username ? "@" + m.from.username : `tg://user?id=${m.from.id}`;
    const answer = "Конечно! Напишите Даниэлю в WhatsApp, он ответит лично. Я тоже передал ему, что вы хотите связаться.";
    chat.history.push({ role: "user", text: "Хочу связаться с Даниэлем", ts: Date.now() }, { role: "model", text: answer, ts: Date.now() });
    chat.contact = who;
    if (chat.tier !== "cold" && !chat.notifiedAt) { chat.notifiedAt = Date.now(); await notifyOwner(env, `👤 Telegram ${who} ${chat.name || ""}: просит связаться с тобой. ${chat.niche || chat.request || ""}`); }
    await saveChat(env, "tg" + chatId, chat);
    return tg(env, "sendMessage", { chat_id: chatId, text: answer, reply_markup: { inline_keyboard: [[{ text: "💬 Написать в WhatsApp", url: OWNER_WA }]] } });
  }
  let text = BUTTONS[m.text] || m.text || m.caption;
  let source;
  if (text && text.startsWith("/start")) {
    const payload = text.slice(6).trim().toLowerCase();   // ссылка вида t.me/бот?start=threads
    source = payload.startsWith("threads") ? "Threads" : payload.startsWith("insta") ? "Instagram" : "Telegram";
    text = "Здравствуйте! (клиент нажал «Старт» в Telegram-боте)";
  }
  if (!text) text = m.voice ? "[голосовое: попроси написать текстом, голосовые бот пока не слушает]" : "[клиент прислал не текст: поблагодари и спроси, что он хотел показать]";
  await tg(env, "sendChatAction", { chat_id: chatId, action: "typing" });
  const who = m.from.username ? "@" + m.from.username : `tg://user?id=${m.from.id}`;
  await converse(env, {
    key: "tg" + chatId, channel: "Telegram", contact: who,
    profileName: [m.from.first_name, m.from.last_name].filter(Boolean).join(" "),
    text, source, reply: t => tg(env, "sendMessage", { chat_id: chatId, text: t, reply_markup: menu(env) }),
  });
}

// Telegram подписывает данные мини-приложения токеном бота: так знаем, что заявку прислал именно этот человек
async function checkInitData(initData, botToken) {
  const params = new URLSearchParams(initData || "");
  const hash = params.get("hash");
  if (!hash) return null;
  params.delete("hash");
  const dcs = [...params.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => `${k}=${v}`).join("\n");
  const enc = new TextEncoder();
  const k1 = await crypto.subtle.importKey("raw", enc.encode("WebAppData"), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const secret = await crypto.subtle.sign("HMAC", k1, enc.encode(botToken));
  const k2 = await crypto.subtle.importKey("raw", secret, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = [...new Uint8Array(await crypto.subtle.sign("HMAC", k2, enc.encode(dcs)))].map(b => b.toString(16).padStart(2, "0")).join("");
  if (sig !== hash) return null;
  if (Date.now() / 1000 - Number(params.get("auth_date") || 0) > 86400) return null;
  try { return JSON.parse(params.get("user") || "null"); } catch { return null; }
}

async function appLead(req, env, ctx) {
  const { initData, form = {} } = await req.json().catch(() => ({}));
  const user = env.TG_CLIENT_TOKEN && await checkInitData(initData, env.TG_CLIENT_TOKEN);
  if (!user?.id) return new Response("откройте приложение из чата с ботом", { status: 403 });
  const clip = (v, n) => String(v || "").slice(0, n);
  const f = { biz: clip(form.biz, 80), niche: clip(form.niche, 120), city: clip(form.city, 30), pain: clip(form.pain, 60),
    when: clip(form.when, 40), note: clip(form.note, 500), needs: (Array.isArray(form.needs) ? form.needs : []).slice(0, 10).map(x => clip(x, 20)) };
  const key = "tg" + user.id;
  const chat = await loadChat(env, key);
  chat.name = chat.name || f.biz;
  chat.niche = f.niche || chat.niche;
  chat.city = f.city || chat.city;
  chat.request = `Бесплатный пример: ${f.needs.join(", ") || "ролик"}`;
  chat.appForm = { ...f, at: Date.now() };
  await saveChat(env, key, chat);
  const text = `[Заявка из мини-приложения на бесплатный пример] Бизнес: ${f.biz}. Чем занимается: ${f.niche}. Город: ${f.city}. Нужно: ${f.needs.join(", ") || "не выбрано"}. Что мешает: ${f.pain || "не указал"}. Когда начать: ${f.when || "не указал"}. Комментарий: ${f.note || "нет"}. Поблагодари за заявку, скажи, что пример сделаем, попроси прислать 2–3 фото или ссылку на Instagram и задай один вопрос про недостающую букву BANT.`;
  const who = user.username ? "@" + user.username : `tg://user?id=${user.id}`;
  await notifyOwner(env, `🎁 Заявка на пример из приложения: ${f.biz} (${f.niche}), ${f.city}, ${who}. Нужно: ${f.needs.join(", ") || "—"}. Мешает: ${f.pain || "—"}. Старт: ${f.when || "—"}.`);
  ctx.waitUntil(converse(env, { key, channel: "Telegram", contact: who, profileName: [user.first_name, user.last_name].filter(Boolean).join(" "),
    text, source: "Mini App", reply: t => tg(env, "sendMessage", { chat_id: user.id, text: t, reply_markup: menu(env) }) })
    .catch(e => env.CHATS.put("health:last_crash", JSON.stringify({ at: new Date().toISOString(), where: "app", message: String(e.stack || e).slice(0, 400) }))));
  return Response.json({ ok: true });
}


async function leadsText(env) {
  const all = [];
  let cursor;
  do {
    const page = await env.CHATS.list({ prefix: "chat:", cursor });
    for (const k of page.keys) { const c = await env.CHATS.get(k.name, "json"); if (c) all.push(c); }
    cursor = page.list_complete ? null : page.cursor;
  } while (cursor);
  if (!all.length) return "Клиентов пока нет.";
  const score = c => ["n", "a", "t", "b"].reduce((s, k) => s + (c.bant?.[k] ?? 0), 0);
  const groups = [["hot", "🔥 Горячие"], ["warm", "🙂 Тёплые"], ["unknown", "❔ Пока неясно"], ["cold", "🧊 Холодные"]];
  const lines = [];
  for (const [tier, title] of groups) {
    const list = all.filter(c => (c.tier || "unknown") === tier).sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)).slice(0, 15);
    if (!list.length) continue;
    lines.push(`${title} (${list.length})`);
    for (const c of list) lines.push(`• ${c.name || c.profileName || "без имени"} ${c.contact || ""} (${c.channel || "WhatsApp"}), ${c.niche || c.request || "ниша не ясна"}, BANT ${score(c)}/8. ${c.next || ""}`);
    lines.push("");
  }
  return lines.join("\n").slice(0, 4000);
}

// Открытая проверка без секретов: какие ключи заданы, когда было последнее сообщение и последняя ошибка Meta
async function health(env) {
  const keys = ["WA_TOKEN", "WA_PHONE_ID", "WA_APP_SECRET", "VERIFY_TOKEN", "GEMINI_KEY", "LEADS_KEY", "TG_BOT_TOKEN", "TG_CLIENT_TOKEN", "TG_CHAT_ID"];
  const out = { keys: Object.fromEntries(keys.map(k => [k, !!env[k]])),
    // формат секрета без самого секрета: у Meta это 32 символа 0-9a-f
    app_secret_format: (() => { const v = (env.WA_APP_SECRET || "").trim().replace(/^[`'"]+|[`'"]+$/g, ""); return { length: v.length, hex: /^[0-9a-f]+$/.test(v), raw_has_spaces: v.length !== (env.WA_APP_SECRET || "").length }; })(),
    last_post: JSON.parse((await env.CHATS.get("health:last_post")) || "null"),
    last_message_at: await env.CHATS.get("health:last_message_at"),
    last_status: JSON.parse((await env.CHATS.get("health:last_status")) || "null"),
    last_reply_at: await env.CHATS.get("health:last_reply_at"),
    last_crash: JSON.parse((await env.CHATS.get("health:last_crash")) || "null"),
    last_gemini_error: JSON.parse((await env.CHATS.get("health:last_gemini_error")) || "null"),
    last_error: JSON.parse((await env.CHATS.get("health:last_error")) || "null") };
  return new Response(JSON.stringify(out, null, 1), { headers: { "content-type": "application/json" } });
}

async function notifyOwner(env, text) {
  const token = env.TG_BOT_TOKEN || env.TG_CLIENT_TOKEN;
  if (!token || !env.TG_CHAT_ID) return;   // без Telegram горячих подхватит Claude при синхронизации
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: env.TG_CHAT_ID, text }),
  });
}

async function loadChat(env, waId) {
  const c = await env.CHATS.get("chat:" + waId, "json");
  return c || { phone: waId, history: [], bant: { n: null, a: null, t: null, b: null } };
}

async function saveChat(env, waId, chat) {
  chat.history = chat.history.slice(-HISTORY);
  chat.updatedAt = Date.now();
  await env.CHATS.put("chat:" + waId, JSON.stringify(chat));
}

// Для Claude: список лидов, чтобы раз в 2 часа переносить их в трекер. Доступ только по ключу.
async function leads(req, env) {
  if (!env.LEADS_KEY || req.headers.get("authorization") !== `Bearer ${env.LEADS_KEY}`)
    return new Response("forbidden", { status: 403 });
  const since = Number(new URL(req.url).searchParams.get("since") || 0);
  const out = [];
  let cursor;
  do {
    const page = await env.CHATS.list({ prefix: "chat:", cursor });
    for (const k of page.keys) {
      const c = await env.CHATS.get(k.name, "json");
      if (c && (c.updatedAt || 0) >= since) out.push({ ...c, history: c.history.slice(-6) });
    }
    cursor = page.list_complete ? null : page.cursor;
  } while (cursor);
  return Response.json(out);
}
