import asyncio
import logging
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message
from sqlalchemy import select

from app.config import settings
from app.db.database import SessionLocal
from app.db import repo
from app.db.models import Lead
from app import gsheets
from app.keyboards import final_kb, question_kb, start_kb
from app.quiz.questions import question_by_index, total_questions
from app.quiz.texts import (
    ALREADY_FINISHED,
    FINAL_BUTTON,
    GREETING,
    START_BUTTON,
    final_card,
    greeting_word,
    question_card,
)

router = Router()
log = logging.getLogger(__name__)

# public/ в корне проекта
PUBLIC_DIR = Path(__file__).resolve().parent.parent.parent / "public"
LOGO_PATH = PUBLIC_DIR / "logo.jpg"
FINAL_PHOTO_PATH = PUBLIC_DIR / "final.jpg"


def _question_photo_path(idx: int) -> Path | None:
    """question{idx+1}.jpg, fallback на question1.jpg, иначе None."""
    path = PUBLIC_DIR / f"question{idx + 1}.jpg"
    if path.exists():
        return path
    fallback = PUBLIC_DIR / "question1.jpg"
    return fallback if fallback.exists() else None


class Quiz(StatesGroup):
    answering = State()


async def _safe_edit(message: Message, text: str, reply_markup=None) -> None:
    """Edit the single quiz card. Silently fallback to a new message if edit fails."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        log.info("edit_text fell back to new message: %s", exc)
        await message.answer(text, reply_markup=reply_markup)


async def _safe_edit_caption(message: Message, caption: str, reply_markup=None) -> None:
    """Edit caption of a media message (photo/video). Fallback to a new text message if it fails."""
    try:
        await message.edit_caption(caption=caption, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        log.info("edit_caption fell back to new message: %s", exc)
        await message.answer(caption, reply_markup=reply_markup)


async def _render_question(
    message: Message,
    state: FSMContext,
    idx: int,
    reaction: str | None = None,
) -> None:
    """Морфинг между вопросами: меняем и фото (question{N}.jpg) и подпись через edit_media."""
    q = question_by_index(idx)
    if q is None:
        return
    await state.update_data(step=idx)
    await state.set_state(Quiz.answering)
    caption = question_card(idx, total_questions(), q["text"], reaction=reaction)
    reply_markup = question_kb(q["key"], q["options"], columns=q.get("columns", 1))

    photo_path = _question_photo_path(idx)

    if message.photo and photo_path:
        media = InputMediaPhoto(
            media=FSInputFile(str(photo_path)),
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
        try:
            await message.edit_media(media=media, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            log.info("edit_media failed, falling back to edit_caption: %s", exc)
            await _safe_edit_caption(message, caption, reply_markup=reply_markup)
    elif message.photo:
        await _safe_edit_caption(message, caption, reply_markup=reply_markup)
    else:
        await _safe_edit(message, caption, reply_markup=reply_markup)


async def _render_final(message: Message, bot: Bot, reaction: str | None = None) -> None:
    """Финал: удаляем карточку квиза и шлём новую (photo+caption если есть final.jpg,
    иначе текстом) с message_effect_id."""
    text = final_card(reaction=reaction)
    reply_markup = final_kb(FINAL_BUTTON, settings.closed_channel_url)
    effect_id = settings.final_effect_id or None

    try:
        await bot.delete_message(message.chat.id, message.message_id)
    except Exception as exc:
        log.info("delete quiz card failed (will leave it): %s", exc)

    if FINAL_PHOTO_PATH.exists():
        send_method = bot.send_photo
        send_kwargs = dict(
            chat_id=message.chat.id,
            photo=FSInputFile(str(FINAL_PHOTO_PATH)),
            caption=text,
            reply_markup=reply_markup,
        )
    else:
        send_method = bot.send_message
        send_kwargs = dict(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
        )
    if effect_id:
        send_kwargs["message_effect_id"] = effect_id

    try:
        await send_method(**send_kwargs)
    except TelegramBadRequest as exc:
        # некоторые эффекты могут не приехать — повторяем без них
        if effect_id and "effect" in str(exc).lower():
            send_kwargs.pop("message_effect_id", None)
            await send_method(**send_kwargs)
        else:
            raise

    if settings.final_video_note_file_id:
        try:
            await bot.send_video_note(message.chat.id, settings.final_video_note_file_id)
        except Exception as exc:
            log.warning("video_note send failed: %s", exc)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()
    source = command.args or None
    user = message.from_user
    if user is None:
        return

    async with SessionLocal() as session:
        lead, _ = await repo.get_or_create_lead(
            session,
            tg_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            source=source,
        )
        already_done = lead.finished

    asyncio.create_task(gsheets.sync_lead(user.id))

    name = user.first_name or "друг"

    if already_done:
        await message.answer(
            ALREADY_FINISHED,
            reply_markup=final_kb(FINAL_BUTTON, settings.closed_channel_url),
        )
        return

    caption = GREETING.format(greet=greeting_word(), name=name, total=total_questions())
    reply_markup = start_kb(START_BUTTON)

    if LOGO_PATH.exists():
        await message.answer_photo(
            photo=FSInputFile(str(LOGO_PATH)),
            caption=caption,
            reply_markup=reply_markup,
        )
    else:
        # на проде или если файл потеряли — отправляем без картинки
        log.warning("logo not found at %s; sending greeting without photo", LOGO_PATH)
        await message.answer(caption, reply_markup=reply_markup)


@router.callback_query(F.data == "quiz:start")
async def on_quiz_start(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await call.answer()
    if call.message is None:
        return

    try:
        await bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as exc:
        log.info("delete greeting failed: %s", exc)

    q = question_by_index(0)
    if q is None:
        return
    await state.update_data(step=0)
    await state.set_state(Quiz.answering)

    caption = question_card(0, total_questions(), q["text"])
    reply_markup = question_kb(q["key"], q["options"], columns=q.get("columns", 1))

    photo_path = _question_photo_path(0)
    if photo_path:
        await bot.send_photo(
            chat_id=call.message.chat.id,
            photo=FSInputFile(str(photo_path)),
            caption=caption,
            reply_markup=reply_markup,
        )
    else:
        log.warning("question photo not found; sending text-only")
        await bot.send_message(
            chat_id=call.message.chat.id,
            text=caption,
            reply_markup=reply_markup,
        )


@router.callback_query(F.data.startswith("q:"))
async def on_answer(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if call.from_user is None or call.message is None or call.data is None:
        await call.answer()
        return

    try:
        _, question_key, option_key = call.data.split(":", 2)
    except ValueError:
        await call.answer()
        return

    data = await state.get_data()
    step = int(data.get("step", 0))
    q = question_by_index(step)
    if q is None or q["key"] != question_key:
        await call.answer()
        return

    await call.answer()

    option_text = next((text for k, text in q["options"] if k == option_key), option_key)

    async with SessionLocal() as session:
        lead = await session.scalar(select(Lead).where(Lead.tg_id == call.from_user.id))
        if lead is None:
            return
        await repo.save_answer(
            session,
            lead_id=lead.id,
            question_key=question_key,
            option_key=option_key,
            option_text=option_text,
        )
        await repo.update_progress(session, lead, step=step + 1)

    next_idx = step + 1

    if next_idx >= total_questions():
        async with SessionLocal() as session:
            lead = await session.scalar(select(Lead).where(Lead.tg_id == call.from_user.id))
            if lead is not None:
                await repo.mark_finished(session, lead)
        asyncio.create_task(gsheets.sync_lead(call.from_user.id))
        await state.clear()
        await _render_final(call.message, bot)
        return

    asyncio.create_task(gsheets.sync_lead(call.from_user.id))
    await _render_question(call.message, state, next_idx)
