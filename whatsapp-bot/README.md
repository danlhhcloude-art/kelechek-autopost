# ИИ-менеджер в WhatsApp

Бот отвечает клиентам в WhatsApp от имени Kelechek AI (честно говорит, что он ИИ), по одному вопросу выясняет BANT и ставит баллы. Горячих (7–8 из 8 или «хочу живого человека») передаёт Даниэлю. Если Даниэль ответил клиенту сам, бот замолкает в этом чате на 12 часов.

Всё бесплатно в пределах лимитов: Cloudflare Workers и KV (бесплатный план), Gemini API (бесплатный уровень Google AI Studio), ответы клиентам в WhatsApp Cloud API в окне 24 часа после их сообщения. Учти, что на бесплатном уровне Gemini Google может использовать переписки для улучшения своих моделей; при платном ключе нет.

## Что сделать один раз

1. **Gemini.** aistudio.google.com → Get API key → Create API key. Это `GEMINI_KEY`.
2. **Cloudflare.** dash.cloudflare.com, регистрация бесплатно.
   - `CLOUDFLARE_ACCOUNT_ID`: справа на главной странице аккаунта (Account ID).
   - `CLOUDFLARE_API_TOKEN`: My Profile → API Tokens → Create Token → шаблон «Edit Cloudflare Workers».
3. **WhatsApp Cloud API.** developers.facebook.com → то же приложение Meta или новое → Add product → WhatsApp.
   - Сначала используй бесплатный **тестовый номер** Meta: добавь свой личный номер в список получателей и проверь бота.
   - `WA_PHONE_ID`: WhatsApp → API Setup → Phone number ID.
   - `WA_TOKEN`: постоянный токен. Business Settings → System users → добавить → Generate token с правами `whatsapp_business_messaging`, `whatsapp_business_management`.
   - `WA_APP_SECRET`: App settings → Basic → App secret.
   - `WA_VERIFY_TOKEN`: придумай любое слово, например `kelechek2026`.
4. **Секреты в GitHub.** Репозиторий → Settings → Secrets and variables → Actions → New secret, все значения выше. Плюс `WA_LEADS_KEY`: любая длинная случайная строка, по ней Claude забирает лиды в трекер.
   По желанию `TG_BOT_TOKEN` и `TG_CHAT_ID`: мгновенное уведомление о горячем клиенте в Telegram.
5. **Запуск.** Actions → «WhatsApp bot deploy» → Run workflow. В логе будет адрес вида `https://kelechek-whatsapp.<имя>.workers.dev`.
6. **Webhook.** В Meta: WhatsApp → Configuration → Webhook → Callback URL `https://kelechek-whatsapp.<имя>.workers.dev/webhook`, Verify token = `WA_VERIFY_TOKEN` → Verify and save → подписаться на поле `messages` (и `smb_message_echoes`, если номер работает и в приложении WhatsApp Business).

## Номер

- Тестовый номер Meta: для проверки, писать ему могут только до 5 добавленных номеров.
- Отдельная SIM под бота: проще всего, номер полностью уходит в API.
- Текущий номер +996 502 091 443 с сохранением приложения WhatsApp Business (coexistence): подключается через Embedded Signup партнёра Meta, доступность в Кыргызстане нужно проверить. Тогда ответы Даниэля из приложения автоматически ставят бота на паузу.

## Как устроено

`worker.js`: webhook проверяет подпись Meta, хранит последние 30 сообщений чата в KV, просит Gemini ответ и баллы BANT в JSON, отправляет ответ. `GET /leads` (с `Authorization: Bearer WA_LEADS_KEY`) отдаёт лиды для трекера.
