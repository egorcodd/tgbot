from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Answer, Lead


async def get_or_create_lead(
    session: AsyncSession,
    *,
    tg_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    source: str | None,
) -> tuple[Lead, bool]:
    result = await session.execute(select(Lead).where(Lead.tg_id == tg_id))
    lead = result.scalar_one_or_none()
    if lead:
        # refresh light profile fields, but don't overwrite source if already set
        lead.username = username
        lead.first_name = first_name
        lead.last_name = last_name
        if source and not lead.source:
            lead.source = source
        lead.is_active = True
        await session.commit()
        return lead, False

    lead = Lead(
        tg_id=tg_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        source=source,
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return lead, True


async def save_answer(
    session: AsyncSession,
    *,
    lead_id: int,
    question_key: str,
    option_key: str,
    option_text: str,
) -> None:
    # upsert: if user re-answers (shouldn't happen in normal flow, but be safe)
    existing = await session.scalar(
        select(Answer).where(Answer.lead_id == lead_id, Answer.question_key == question_key)
    )
    if existing:
        existing.option_key = option_key
        existing.option_text = option_text
    else:
        session.add(Answer(
            lead_id=lead_id,
            question_key=question_key,
            option_key=option_key,
            option_text=option_text,
        ))
    await session.commit()


async def update_progress(session: AsyncSession, lead: Lead, *, step: int) -> None:
    lead.current_step = step
    await session.commit()


async def mark_finished(session: AsyncSession, lead: Lead) -> None:
    lead.finished = True
    lead.finished_at = datetime.utcnow()
    await session.commit()


async def mark_blocked(session: AsyncSession, tg_id: int) -> None:
    result = await session.execute(select(Lead).where(Lead.tg_id == tg_id))
    lead = result.scalar_one_or_none()
    if lead:
        lead.is_active = False
        await session.commit()
