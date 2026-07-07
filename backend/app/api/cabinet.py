"""GET /api/v1/applications (список) и GET /api/v1/applications/{id} (детали) —
личный кабинет (SPEC.md §4.4, "Обязательное расширение" §2: черновик с процентом
заполнения и кнопкой «Продолжить»).

Отдельный модуль, чтобы не трогать существующий контур создания/автосохранения в
`applications.py`; переиспользует его приватные хелперы намеренно — проверка
владения (404 вместо 403 против IDOR) и загрузка Definition должны совпадать
байт-в-байт с остальными эндпоинтами заявок.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.applications import (
    _get_owned_application,
    _load_definition_row,
    _parse_definition,
)
from app.api.contracts import (
    CabinetApplicationDetail,
    CabinetApplicationItem,
    CabinetListOut,
    CabinetNotificationOut,
    CabinetServiceInfo,
)
from app.api.deps import get_current_user_id
from app.db import get_session
from app.engine.rules import effects
from app.engine.runtime import compute
from app.models import Application, Notification
from app.models import ServiceDefinition as ServiceDefinitionModel
from app.schemas.definition import ServiceDefinition as ServiceDefinitionSchema

router = APIRouter(tags=["cabinet"])


def _progress_percent(definition: ServiceDefinitionSchema, data: dict) -> int:
    """Процент заполнения черновика: заполненные видимые поля / все видимые поля.

    «Видимое» и «заполненное» считаются ровно так же, как в `engine.runtime.validate()`:
    поле видно, пока правила не дали effect=hide (правила оцениваются на данных с
    подмешанными computed-значениями), заполнено — если значение не in (None, "", []).
    """
    try:
        values, _ = compute(definition, data)
    except ValueError:
        # Формула ссылается на ещё не заполненное поле — нормальное состояние черновика
        # (см. screen.safe_render): правила оцениваем по сырым данным без computed.
        values = dict(data)
    applied, _ = effects(definition.rules, values)
    total = 0
    filled = 0
    for stage in definition.stages:
        for step in stage.steps:
            for field in step.fields:
                if applied.get(field.key) == "hide":
                    continue
                total += 1
                if data.get(field.key) not in (None, "", []):
                    filled += 1
    if total == 0:
        return 100
    return round(100 * filled / total)


def _cabinet_item(
    application: Application, definition_row: ServiceDefinitionModel
) -> CabinetApplicationItem:
    definition = _parse_definition(definition_row)
    return CabinetApplicationItem(
        id=application.id,
        number=application.number,
        status=application.status,
        service=CabinetServiceInfo(slug=definition_row.slug, title=definition.meta.title),
        service_version=application.service_version,
        checkpoint=application.checkpoint,
        progress_percent=_progress_percent(definition, application.data),
        labels_plain=definition.meta.labels_plain,
        updated_at=application.updated_at,
    )


@router.get("/applications", response_model=CabinetListOut)
async def list_applications(
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CabinetListOut:
    """Все заявки текущего пользователя, свежие сверху. Черновики и отправленные
    вперемешку — кабинет на фронте сам ставит черновики первым блоком (SPEC §2)."""
    stmt = (
        select(Application, ServiceDefinitionModel)
        .join(
            ServiceDefinitionModel,
            (ServiceDefinitionModel.service_id == Application.service_id)
            & (ServiceDefinitionModel.version == Application.service_version),
        )
        .where(Application.user_id == user_id)
        .order_by(Application.updated_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return CabinetListOut(items=[_cabinet_item(application, definition_row) for application, definition_row in rows])


@router.get("/applications/{application_id}", response_model=CabinetApplicationDetail)
async def get_application(
    application_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> CabinetApplicationDetail:
    """Детальная карточка: таймлайн статусов, уведомления, документы (пока заглушка —
    файловый контур ещё не реализован, см. IMPLEMENTATION_PLAN §8)."""
    application = await _get_owned_application(session, application_id, user_id)
    definition_row = await _load_definition_row(session, application.service_id, application.service_version)
    item = _cabinet_item(application, definition_row)

    notifications = (
        await session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id, Notification.application_id == application_id)
            .order_by(Notification.created_at.desc())
        )
    ).all()

    return CabinetApplicationDetail(
        **item.model_dump(),
        created_at=application.created_at,
        timeline=application.timeline,
        documents=[],
        notifications=[
            CabinetNotificationOut(
                id=notification.id,
                type=notification.type,
                title=notification.title,
                body=notification.body,
                created_at=notification.created_at,
                read_at=notification.read_at,
            )
            for notification in notifications
        ],
    )
