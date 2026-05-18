# tgbot — лидогенерационный квиз-бот

Telegram-бот, который прогоняет лида по квизу из 10 вопросов и выдаёт доступ
в закрытый канал. Сегментирует базу по ответам и умеет рассылать контент
(статьи, гайды, паки, анонсы марафона) через `/broadcast`.

## Стек

- **Python 3.11+**, **aiogram 3.13** (async)
- **SQLAlchemy 2.0 async** + SQLite (по умолчанию) / PostgreSQL (прод)
- **Redis** (опционально, для FSM в проде; в MVP — память процесса)

## Структура

```
app/
  bot.py              # entrypoint
  config.py           # настройки из .env
  keyboards.py        # инлайн-клавиатуры
  db/
    database.py       # engine + sessionmaker
    models.py         # Lead, Answer, Broadcast
    repo.py           # CRUD-хелперы
  quiz/
    questions.py      # 10 вопросов + реакции — РЕДАКТИРУЕМО без программиста
    texts.py          # приветствие, финал, прогресс-бар
  handlers/
    quiz.py           # /start + FSM квиза
    admin.py          # /broadcast, /stats, /getfileid
```

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # заполни BOT_TOKEN, ADMIN_IDS, CLOSED_CHANNEL_URL
python -m app.bot
```

## Админка (через команды бота)

Команды доступны только из `ADMIN_IDS`.

- `/stats` — счётчики и дроп-офф по шагам квиза.
- `/getfileid` — сделай reply на медиа → бот вернёт `file_id` (нужен для
  кружка на финальном экране → положить в `FINAL_VIDEO_NOTE_FILE_ID`).
- `/broadcast` — сделай reply на сообщение (текст / фото / видео / кружок /
  документ) и отправь `/broadcast`. Бот скопирует его всем активным лидам.
  Сегменты:
  - `/broadcast` или `/broadcast all` — всем активным
  - `/broadcast finished` — только прошедшим квиз
  - `/broadcast unfinished` — только не дошедшим до конца
  - `/broadcast answer:studied=python` — кто на вопросе `studied` выбрал `python`

  (ключи вопросов и опций — в [app/quiz/questions.py](app/quiz/questions.py).)

## Что заложено сразу

- Прогресс-бар `▓▓▓░░░░░░ 3/10` в каждом вопросе.
- Реакции бота на ответы (общие и условные — например, Python/JS/React на 5-м).
- Сохранение прогресса в БД (current_step) — на будущее под «продолжи с того же места».
- UTM через deep-link: `?start=ig_reels_1` → сохранится в `Lead.source`.
- Автоматическое отключение лида, который заблокировал бота (`is_active=False`).
- Журнал рассылок (`broadcasts`) — сколько ушло, сколько отвалилось.
- Rate-limit 25 msg/s (под лимит Telegram).

## Что добавим следующими шагами

- Финальная персонализированная сводка («направление: Python, блокер: …»).
- Веб-админка (FastAPI) для контент-менеджера вместо команд.
- Отложенные рассылки (расписание).
- Дашборд воронки (Metabase / простой HTML отчёт).
