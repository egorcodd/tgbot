"""Google Sheets live-sync. Один лид = одна строка, обновляется в реалтайме.

При первом импорте ленится — соединение/таблица создаются только когда понадобятся.
Если Sheets не сконфигурирован (нет GOOGLE_SHEET_ID или JSON) — все вызовы
тихо no-op'ятся, бот продолжает работать без интеграции.

Все операции с gspread — синхронные, поэтому обёрнуты в asyncio.to_thread.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Lead
from app.quiz.questions import QUESTIONS

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_QUESTION_KEYS = [q["key"] for q in QUESTIONS]
_QUESTION_TEXTS = {q["key"]: q["text"] for q in QUESTIONS}

_BASE_HEADERS = [
    "tg_id", "username", "имя",
    "источник (utm)", "создан", "прошёл квиз", "завершил",
    "активен", "шаг",
]
HEADERS = _BASE_HEADERS + [_QUESTION_TEXTS[k] for k in _QUESTION_KEYS]

_worksheet = None
_init_failed = False  # один раз залогировали — не спамим


def _resolve_credentials_path() -> Path | None:
    if not settings.google_credentials_path:
        return None
    p = Path(settings.google_credentials_path)
    if not p.is_absolute():
        # относительно корня проекта
        project_root = Path(__file__).resolve().parent.parent
        p = project_root / p
    return p if p.exists() else None


def _get_worksheet():
    """Lazy init. Возвращает worksheet или None если что-то не настроено."""
    global _worksheet, _init_failed
    if _worksheet is not None:
        return _worksheet
    if _init_failed:
        return None
    if not settings.google_sheet_id:
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_path = _resolve_credentials_path()
        if creds_path is None:
            log.warning(
                "GOOGLE_CREDENTIALS_PATH not set or file not found: %s",
                settings.google_credentials_path,
            )
            _init_failed = True
            return None

        creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(settings.google_sheet_id)
        ws = sheet.sheet1

        # ставим шапку, если её ещё нет (или старая)
        first_row = ws.row_values(1)
        if first_row != HEADERS:
            ws.update(values=[HEADERS], range_name="A1")

        _worksheet = ws
        log.info("Google Sheets sync enabled (sheet: %s)", settings.google_sheet_id)
        return ws
    except Exception as exc:
        log.error("Google Sheets init failed, sync disabled: %s", exc)
        _init_failed = True
        return None


def _find_row(ws, tg_id: int) -> int | None:
    try:
        cell = ws.find(str(tg_id), in_column=1)
        return cell.row if cell else None
    except Exception:
        return None


def _format_row(*, tg_id, username, name, source, created, finished, finished_at, active, step, answers) -> list:
    base = [
        tg_id,
        username or "",
        name or "",
        source or "",
        created or "",
        "да" if finished else "нет",
        finished_at or "",
        "да" if active else "нет",
        step,
    ]
    base += [answers.get(k, "") for k in _QUESTION_KEYS]
    return base


def _upsert_sync(payload: dict) -> None:
    ws = _get_worksheet()
    if ws is None:
        return
    row = _format_row(**payload)
    row_idx = _find_row(ws, payload["tg_id"])
    if row_idx:
        # обновляем строку целиком (A:S)
        end_col_letter = _col_letter(len(HEADERS))
        ws.update(values=[row], range_name=f"A{row_idx}:{end_col_letter}{row_idx}")
    else:
        ws.append_row(row, value_input_option="USER_ENTERED")


def _col_letter(n: int) -> str:
    """1 → A, 27 → AA"""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


async def sync_lead(tg_id: int) -> None:
    """Подтянуть лида из БД и обновить его строку в Sheets. Fire-and-forget."""
    if not settings.google_sheet_id:
        return
    try:
        async with SessionLocal() as session:
            lead = await session.scalar(
                select(Lead).options(selectinload(Lead.answers)).where(Lead.tg_id == tg_id)
            )
            if lead is None:
                return
            full_name = " ".join(p for p in (lead.first_name, lead.last_name) if p)
            payload = {
                "tg_id": lead.tg_id,
                "username": lead.username,
                "name": full_name,
                "source": lead.source,
                "created": lead.created_at.strftime("%Y-%m-%d %H:%M") if lead.created_at else "",
                "finished": lead.finished,
                "finished_at": lead.finished_at.strftime("%Y-%m-%d %H:%M") if lead.finished_at else "",
                "active": lead.is_active,
                "step": lead.current_step,
                "answers": {a.question_key: a.option_text for a in lead.answers},
            }
        await asyncio.to_thread(_upsert_sync, payload)
    except Exception as exc:
        log.warning("gsheets sync_lead failed for tg_id=%s: %s", tg_id, exc)
