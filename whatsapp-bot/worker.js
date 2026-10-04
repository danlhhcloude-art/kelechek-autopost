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

const SYSTEM = `Ты ИИ-ассистент Kelechek AI в WhatsApp. Kelechek AI из Бишкека делает ИИ-видео (Reels, реклама) и автоматизацию для бизнеса (автоответы в WhatsApp, контент для соцсетей). Владелец: Даниэль.

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

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (url.pathname === "/webhook" && req.method === "GET") return verify(url, env);
    if (url.pathname === "/webhook" && req.method === "POST") {
      const raw = await req.text();
      if (!(await signatureOk(raw, req.headers.get("x-hub-signature-256"), env.WA_APP_SECRET)))
        return new Response("bad signature", { status: 401 });
      ctx.waitUntil(handle(JSON.parse(raw), env).catch(e => console.log("handle error", e.stack || e)));
      return new Response("ok");
    }
    if (url.pathname === "/leads" && req.method === "GET") return leads(req, env);
    return new Response("Kelechek AI WhatsApp bot", { status: 200 });
  },
};

function verify(url, env) {
  const ok = url.searchParams.get("hub.mode") === "subscribe" && url.searchParams.get("hub.verify_token") === env.VERIFY_TOKEN;
  return ok ? new Response(url.searchParams.get("hub.challenge")) : new Response("forbidden", { status: 403 });
}

async function signatureOk(raw, header, secret) {
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
  if (!r.ok) console.log("graph error", r.status, (await r.text()).slice(0, 300));
}

const send = (env, to, text) => graph(env, { recipient_type: "individual", to, type: "text", text: { body: text } });
const markRead = (env, id) => graph(env, { status: "read", message_id: id });

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
