// ИИ-менеджер Kelechek AI в WhatsApp: отвечает клиентам, квалифицирует по BANT,
// зовёт владельца к горячим. Cloudflare Worker + WhatsApp Cloud API + Gemini.
//
// Секреты (wrangler secret put ...): WA_TOKEN, WA_PHONE_ID, WA_APP_SECRET, VERIFY_TOKEN,
// GEMINI_KEY, LEADS_KEY; по желанию TG_BOT_TOKEN и TG_CHAT_ID для мгновенных уведомлений.
// KV: CHATS (переписки и баллы).

const GRAPH = "https://graph.facebook.com/v22.0";
const HISTORY = 30;            // сколько последних сообщений помнит бот
const HUMAN_PAUSE_H = 12;      // владелец написал сам: бот молчит в этом чате столько часов
const MAX_REPLY = 900;

const SYSTEM = `Ты ИИ-ассистент Kelechek AI в WhatsApp. Kelechek AI из Бишкека делает ИИ-видео (Reels, реклама) и автоматизацию для бизнеса (автоответы в WhatsApp, контент для соцсетей), а также ведёт таргетированную рекламу в Instagram и Facebook (настройка аудитории, креативы на ИИ, заявки в WhatsApp, отчёт раз в неделю; рекламный бюджет клиент платит напрямую в Meta). Владелец: Даниэль.

Как мы работаем: клиент оплачивает подписку на нужные ИИ-сервисы, первые 15 дней наша работа бесплатно, потом фиксированная оплата, сумму называет владелец. Отчёты каждую неделю и в конце месяца. В Бишкеке владелец встречается лично и показывает всё на ноутбуке.

Правила:
- В первом ответе человеку скажи, что ты ИИ-ассистент Kelechek AI. Себя за человека не выдавай.
- Пиши коротко, живо, по-человечески, 1–4 предложения. Язык клиента: русский или кыргызский.
- Не придумывай цены, сроки, цифры результатов, кейсы и отзывы. Про цену: «точную цену назовёт Даниэль после пары вопросов».
- Портфолио собираем сейчас, поэтому есть бесплатный пример ролика под бизнес клиента и 15 дней пробы.
- Задавай один вопрос за сообщение, чтобы выяснить BANT по порядку: N (что за бизнес и что болит: мало заявок, нет видео, не успевают отвечать), A (владелец ли, решает ли сам), T (когда хочет начать), B (готов ли оплачивать подписку на ИИ-сервисы и работу после 15 дней).
- Не спрашивай то, что уже известно из переписки.
- Если клиент просит живого человека, хочет встречу или всё ясно и он готов, скажи, что Даниэль напишет ему лично, и поставь wants_human = true.
- На грубость и спам отвечай вежливо и коротко.

Баллы BANT, 0–2 только по фактам из слов клиента, иначе null:
N: 0 просто интересно, 1 хочет больше клиентов без конкретики, 2 чёткая боль.
A: 0 сотрудник без полномочий, 1 решает не один, 2 владелец и решает сам.
T: 0 «когда-нибудь», 1 через 1–3 месяца, 2 в этом месяце.
B: 0 только бесплатно, 1 готов, но «если будет результат», 2 готов платить подписки и ставку.`;

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
    if (url.pathname === "/leads" && req.method === "GET") return leads(req, env);
    if (url.pathname === "/health") return health(env);
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
  const chat = await loadChat(env, m.from);
  chat.profileName = profileName || chat.profileName;
  const text = messageText(m);
  chat.history.push({ role: "user", text, ts: Date.now() });
  if (!chat.firstAt) {
    chat.firstAt = Date.now();
    chat.source = sourceOf(text);
  }
  await markRead(env, m.id);

  if (chat.humanUntil && chat.humanUntil > Date.now()) return saveChat(env, m.from, chat);

  let out;
  try { out = await think(env, chat); }
  catch (e) {
    console.log("gemini error", e.message);
    out = { reply: "Спасибо за сообщение! Сейчас передам его Даниэлю, он ответит лично.", next: "ответить вручную: бот не смог ответить", wants_human: true };
  }
  for (const k of ["n", "a", "t", "b"]) if (out[k] === 0 || out[k] === 1 || out[k] === 2) chat.bant[k] = out[k];
  for (const k of ["name", "niche", "city", "request"]) if (out[k]) chat[k] = out[k];
  chat.next = out.next;
  const reply = out.reply.slice(0, MAX_REPLY);
  await send(env, m.from, reply);
  await env.CHATS.put("health:last_reply_at", new Date().toISOString());
  chat.history.push({ role: "model", text: reply, ts: Date.now() });

  const score = ["n", "a", "t", "b"].reduce((s, k) => s + (chat.bant[k] ?? 0), 0);
  const hot = score >= 7 || out.wants_human;
  if (hot && !chat.notifiedAt) {
    chat.notifiedAt = Date.now();
    await notifyOwner(env, `🔥 WhatsApp +${m.from} ${chat.name || chat.profileName || ""}: ${chat.request || chat.niche || ""}. BANT ${score}/8. ${chat.next}`);
  }
  await saveChat(env, m.from, chat);
}

function messageText(m) {
  if (m.type === "text") return m.text.body;
  if (m.type === "button") return m.button.text;
  if (m.type === "interactive") return m.interactive.button_reply?.title || m.interactive.list_reply?.title || "[кнопка]";
  return `[${m.type}: клиент прислал не текст, ${m.type === "audio" ? "попроси написать текстом, голосовые бот пока не слушает" : "поблагодари и спроси, что он хотел показать"}]`;
}

function sourceOf(text) {
  const w = (text || "").trim().split(/\s+/)[0].toLowerCase();
  if (w.startsWith("threads")) return "Threads";
  if (w.startsWith("instagram")) return "Instagram";
  if (w.startsWith("пример")) return "Threads";
  return "WhatsApp";
}

async function think(env, chat) {
  const known = Object.entries(chat.bant).filter(([, v]) => v !== null).map(([k, v]) => `${k.toUpperCase()}=${v}`).join(", ") || "ничего";
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${env.GEMINI_MODEL || "gemini-2.5-flash"}:generateContent`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_KEY },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: SYSTEM + `\n\nУже известно по BANT: ${known}.` }] },
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

// Открытая проверка без секретов: какие ключи заданы, когда было последнее сообщение и последняя ошибка Meta
async function health(env) {
  const keys = ["WA_TOKEN", "WA_PHONE_ID", "WA_APP_SECRET", "VERIFY_TOKEN", "GEMINI_KEY", "LEADS_KEY", "TG_BOT_TOKEN"];
  const out = { keys: Object.fromEntries(keys.map(k => [k, !!env[k]])),
    // формат секрета без самого секрета: у Meta это 32 символа 0-9a-f
    app_secret_format: (() => { const v = (env.WA_APP_SECRET || "").trim().replace(/^[`'"]+|[`'"]+$/g, ""); return { length: v.length, hex: /^[0-9a-f]+$/.test(v), raw_has_spaces: v.length !== (env.WA_APP_SECRET || "").length }; })(),
    last_post: JSON.parse((await env.CHATS.get("health:last_post")) || "null"),
    last_message_at: await env.CHATS.get("health:last_message_at"),
    last_status: JSON.parse((await env.CHATS.get("health:last_status")) || "null"),
    last_reply_at: await env.CHATS.get("health:last_reply_at"),
    last_error: JSON.parse((await env.CHATS.get("health:last_error")) || "null") };
  return new Response(JSON.stringify(out, null, 1), { headers: { "content-type": "application/json" } });
}

async function notifyOwner(env, text) {
  if (!env.TG_BOT_TOKEN || !env.TG_CHAT_ID) return;   // без Telegram горячих подхватит Claude при синхронизации
  await fetch(`https://api.telegram.org/bot${env.TG_BOT_TOKEN}/sendMessage`, {
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
