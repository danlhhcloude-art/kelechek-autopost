// Картинки к постам Threads в стиле Kelechek AI (1080x1350).
// node tools/cards/make.cjs tools/cards/cards.json
// cards.json: [{ "out": "media/threads/x.png", "variant": "dark|beige|chat", "title": "текст с *акцентом*",
//               "lead": "строка под заголовком (необязательно)", "bubbles": [["Вопрос", "21:47"], ...] }]
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT || '/opt/node-tools/node_modules/playwright');

const ROOT = path.resolve(__dirname, '../..');
const font = (f) => 'file://' + path.join(ROOT, f);
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const accent = (s) => esc(s).replace(/\*([^*]+)\*/g, '<em>$1</em>');

const CSS = `
@font-face { font-family: Unb; src: url(${font('assets/hf/Unbounded-Bold.ttf')}); }
@font-face { font-family: Golos; src: url(${font('assets/hf/GolosText-Medium.ttf')}); font-weight: 500; }
@font-face { font-family: Golos; src: url(${font('assets/hf/GolosText-Regular.ttf')}); font-weight: 400; }
@font-face { font-family: PF; src: url(${font('tools/cards/pf800.woff2')}); unicode-range: U+0400-04FF; }
@font-face { font-family: PF; src: url(${font('tools/cards/pf800l.woff2')}); }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { width: 1080px; height: 1350px; }
.s { width: 1080px; height: 1350px; position: relative; overflow: hidden; font-family: Golos, sans-serif; }
.brand { position: absolute; left: 80px; bottom: 70px; display: flex; align-items: center; gap: 18px; font-family: Unb; font-size: 32px; }
.brand img { width: 60px; height: 60px; border-radius: 16px; }
.nick { position: absolute; right: 80px; bottom: 84px; font-size: 26px; }
/* dark */
.dark { background: radial-gradient(80% 60% at 60% 62%, #3A2A12 0%, #17110A 55%, #0B0907 85%); color: #fff; }
.dark .glow { position: absolute; width: 900px; height: 900px; right: -300px; bottom: -300px; border-radius: 50%; background: radial-gradient(circle, rgba(255,190,80,.22), rgba(255,190,80,0) 65%); }
.dark .tag { position: absolute; left: 80px; top: 90px; display: flex; align-items: center; gap: 14px; font-size: 30px; font-weight: 500; color: #E8DDC8; }
.dark .tag i { width: 14px; height: 14px; border-radius: 50%; background: #FFC23D; box-shadow: 0 0 14px #FFC23D; }
.dark h1 { position: absolute; left: 80px; right: 80px; top: 50%; transform: translateY(-58%); font-family: Unb; line-height: 1.1; }
.dark h1 em { font-style: normal; color: #FFC23D; }
.dark .lead { position: absolute; left: 80px; right: 120px; bottom: 210px; font-size: 34px; line-height: 1.35; color: #D9CDB6; padding-top: 30px; border-top: 2px solid rgba(255,194,61,.5); }
.dark .nick { color: #9C8F7A; }
/* beige */
.beige { background: #ECE6DC; color: #24211D; }
.beige .star { position: absolute; right: 80px; top: 80px; width: 120px; height: 120px; }
.beige h1 { position: absolute; left: 80px; right: 80px; top: 50%; transform: translateY(-60%); font-family: PF; font-weight: 800; line-height: 1.22; }
.beige h1 em { font-style: normal; background: #F2B533; padding: 0 14px 2px; border-radius: 16px; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
.beige .lead { position: absolute; left: 80px; right: 80px; bottom: 200px; background: #F7F4EE; border-radius: 28px; padding: 34px 40px; font-size: 32px; line-height: 1.4; box-shadow: 0 24px 50px rgba(60,45,20,.12); }
.beige .nick { color: #6E665B; }
/* chat */
.chat { background: radial-gradient(90% 60% at 50% 70%, #2B1F10 0%, #15100A 50%, #0B0907 85%); color: #fff; }
.chat h1 { position: absolute; left: 80px; right: 80px; top: 90px; font-family: Unb; line-height: 1.12; }
.chat h1 em { font-style: normal; color: #FFC23D; }
.phone { position: absolute; left: 190px; top: 470px; width: 700px; height: 1100px; border-radius: 90px; background: #121214; padding: 18px; box-shadow: 0 0 0 3px #3A3A3E, 0 60px 120px rgba(0,0,0,.6); transform: rotate(-3deg); }
.screen { width: 100%; height: 100%; border-radius: 74px; background: #F4F1EA; color: #1C1C1E; overflow: hidden; }
.chead { display: flex; align-items: center; gap: 18px; padding: 70px 40px 24px; border-bottom: 1px solid #E3DED3; font-size: 30px; font-weight: 500; }
.chead i { width: 64px; height: 64px; border-radius: 50%; background: #CFC6B5; }
.chead span { display: block; font-size: 22px; color: #8A8172; font-weight: 400; }
.msgs { padding: 34px 32px; display: flex; flex-direction: column; gap: 22px; }
.msg { align-self: flex-start; max-width: 84%; background: #fff; border-radius: 30px 30px 30px 10px; padding: 22px 28px; font-size: 32px; line-height: 1.3; box-shadow: 0 2px 6px rgba(0,0,0,.06); }
.msg small { font-size: 20px; color: #9A9388; margin-left: 14px; }
.msg.out { align-self: flex-end; background: #FFC23D; border-radius: 30px 30px 10px 30px; }
.seen { font-size: 24px; color: #9A9388; }
.chat .brand { bottom: auto; top: 0; left: auto; right: 80px; top: 1260px; display: none; }
`;

const STAR = `<svg class="star" viewBox="0 0 100 100"><g stroke="#F2B533" stroke-width="9" stroke-linecap="round"><line x1="50" y1="6" x2="50" y2="94"/><line x1="6" y1="50" x2="94" y2="50"/><line x1="19" y1="19" x2="81" y2="81"/><line x1="81" y1="19" x2="19" y2="81"/></g></svg>`;
const LOGO = font('assets/hf/logo.png');

function size(title, big, small) {
  const n = title.replace(/\*/g, '').length;
  return n < 30 ? big : n < 55 ? Math.round((big + small) / 2) : small;
}

function page(c) {
  const brand = `<div class="brand"><img src="${LOGO}">Kelechek AI</div><div class="nick">@kelechek_ai</div>`;
  if (c.variant === 'beige') {
    return `<div class="s beige">${STAR}<h1 style="font-size:${size(c.title, 112, 84)}px">${accent(c.title)}</h1>
      ${c.lead ? `<div class="lead">${accent(c.lead)}</div>` : ''}${brand}</div>`;
  }
  if (c.variant === 'chat') {
    const msgs = (c.bubbles || []).map(([t, time, out]) =>
      t === '—' ? `<div class="seen">${esc(time)}</div>` : `<div class="msg${out ? ' out' : ''}">${esc(t)}<small>${esc(time || '')}</small></div>`).join('');
    return `<div class="s chat"><h1 style="font-size:${size(c.title, 84, 64)}px">${accent(c.title)}</h1>
      <div class="phone"><div class="screen"><div class="chead"><i></i><div>${esc(c.contact || 'Клиент')}<span>${esc(c.status || 'был(а) недавно')}</span></div></div>
      <div class="msgs">${msgs}</div></div></div></div>`;
  }
  return `<div class="s dark"><div class="glow"></div>${c.tag ? `<div class="tag"><i></i>${esc(c.tag)}</div>` : ''}
    <h1 style="font-size:${size(c.title, 96, 72)}px">${accent(c.title)}</h1>
    ${c.lead ? `<div class="lead">${accent(c.lead)}</div>` : ''}${brand}</div>`;
}

(async () => {
  const cards = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  for (const c of cards) {
    // через файл, а не setContent: со страницы about:blank браузер не грузит локальные шрифты и логотип
    const tmp = path.join(__dirname, '_card.html');
    fs.writeFileSync(tmp, `<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>${CSS}</style></head><body>${page(c)}</body></html>`);
    await p.goto('file://' + tmp);
    await p.evaluate(() => document.fonts.ready);
    await p.waitForTimeout(150);
    const out = path.join(ROOT, c.out);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await p.screenshot({ path: out });
    console.log(c.out);
  }
  fs.rmSync(path.join(__dirname, '_card.html'), { force: true });
  await b.close();
})();
