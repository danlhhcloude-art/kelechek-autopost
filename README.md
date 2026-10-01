# Автопостинг в Threads

Каждый день в 9:00, 13:00 и 18:00 по Бишкеку публикует по одному посту из `posts.json`. Когда готовые посты кончаются, Claude пишет новые про ИИ-видео, автоматизацию и оффер «15 дней на оценку».

## Что нужно от тебя (один раз)

1. **Аккаунт Threads**: должен быть публичным и привязан к Instagram.
2. **Приложение Meta**: зайди на developers.facebook.com → My Apps → Create App → вариант использования **«Access the Threads API»**.
   В настройках включи разрешения `threads_basic` и `threads_content_publish`, добавь свой аккаунт Threads в роль **Threads Tester** и подтверди приглашение в Threads (Настройки → Аккаунт → Сайты и разрешения).
3. **Токен**: в приложении открой Threads API → **User Token Generator**, сгенерируй токен для своего аккаунта. Так получишь:
   - `THREADS_ACCESS_TOKEN` (долгосрочный, живёт 60 дней);
   - `THREADS_USER_ID` (можно узнать запросом `https://graph.threads.net/v1.0/me?fields=id&access_token=ТОКЕН`).
4. **Ключ Claude**: console.anthropic.com → API Keys → создать ключ, это `ANTHROPIC_API_KEY`. Нужен, только когда посты из очереди закончатся.

## Запуск на GitHub (бесплатно, без своего компьютера)

1. Создай приватный репозиторий и загрузи туда всю эту папку.
2. Settings → Secrets and variables → Actions → добавь три секрета: `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`.
3. Actions → «Threads autopost» → **Run workflow**, чтобы проверить первый пост сразу.

Время публикации меняется в `.github/workflows/autopost.yml` (строка `cron`, время в UTC).

## Запуск на своём компьютере

```bash
pip install -r requirements.txt
cp .env.example .env        # и вписать ключи
python autopost.py --dry-run     # посмотреть следующий пост
python autopost.py               # опубликовать
python autopost.py --generate 10 # попросить Claude дописать 10 постов в очередь
```

## Важно

- Токен Threads живёт 60 дней. Раз в месяц-полтора запускай `python autopost.py --refresh-token` и обнови секрет.
- Посты в `posts.json` можно править руками: менять текст, порядок, удалять. Опубликованные помечаются полем `posted_at`.
- Лимит Threads 500 символов на пост, скрипт обрезает длиннее.
