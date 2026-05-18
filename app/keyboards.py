from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def start_kb(label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label, callback_data="quiz:start"),
    ]])


def question_kb(
    question_key: str,
    options: list[tuple[str, str]],
    columns: int = 1,
) -> InlineKeyboardMarkup:
    """Кнопки в исходном порядке из questions.py.
    `columns` берётся из конфигурации вопроса (по умолчанию 1)."""
    builder = InlineKeyboardBuilder()
    for opt, text in options:
        builder.button(text=text, callback_data=f"q:{question_key}:{opt}")
    builder.adjust(columns)
    return builder.as_markup()


def final_kb(label: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label, url=url),
    ]])
