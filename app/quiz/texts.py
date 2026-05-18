"""User-facing copy. Минимал + blockquote для списков, [N/total] для вопросов."""

from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    _MSK = ZoneInfo("Europe/Moscow")
except Exception:
    _MSK = None


def greeting_word() -> str:
    """Доброе утро / день / вечер / ночи — по МСК."""
    now = datetime.now(_MSK) if _MSK else datetime.now()
    hour = now.hour
    if 6 <= hour < 12:
        return "Доброе утро"
    if 12 <= hour < 18:
        return "Добрый день"
    if 18 <= hour < 23:
        return "Добрый вечер"
    return "Доброй ночи"


# ---------- greeting ----------

GREETING = (
    "{greet}, {name}.\n"
    "\n"
    "Хочешь попасть в закрытый канал?\n"
    "Ответь на {total} коротких вопросов, ~2 минуты.\n"
    "\n"
    "За это время я пойму:\n"
    "<blockquote>1. Какое направление в IT тебе подойдёт.\n"
    "2. Что мешает двигаться быстрее.\n"
    "3. Как выходить на первые деньги.</blockquote>"
)

START_BUTTON = "Начать"

ALREADY_FINISHED = (
    "Ты уже прошёл квиз.\n"
    "\n"
    "Доступ в закрытый канал по кнопке ниже.\n"
    "Скоро там будет бесплатный мини-марафон."
)

# ---------- question card ----------

_HINT = "Варианты ответов ниже:"


def question_card(idx: int, total: int, question_text: str, reaction: str | None = None) -> str:
    marker = f"<b>[{idx + 1}/{total}]</b>"
    body = f"{marker} {question_text}"
    if reaction:
        # снимаем устаревший "// " префикс если он остался в questions.py
        clean = reaction.lstrip().removeprefix("//").lstrip()
        return f"<blockquote>{clean}</blockquote>\n\n{body}\n\n{_HINT}"
    return f"{body}\n\n{_HINT}"


# ---------- final card ----------

FINAL_BUTTON = "Войти в закрытый канал"

FINAL_BODY = (
    "Судя по ответам, у тебя не проблема со способностями.\n"
    "Проблема в отсутствии структуры и понятного пути.\n"
    "\n"
    "Большинство сливаются именно здесь.\n"
    "\n"
    "В закрытом канале показываю:\n"
    "<blockquote>1. Как зайти в нишу.\n"
    "2. Как не потратить время впустую.\n"
    "3. Как получать первый результат.</blockquote>\n"
    "\n"
    "Скоро там будет бесплатный мини-марафон."
)


def final_card(reaction: str | None = None) -> str:
    if reaction:
        return f"<i>{reaction}</i>\n\n{FINAL_BODY}"
    return FINAL_BODY
