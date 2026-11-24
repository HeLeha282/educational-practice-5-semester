"""Хранилище данных в памяти и вспомогательные процедуры (процедурный стиль).

Состояние системы -- обычный словарь `state`; записи -- словари.
Используются типовые структуры данных: dict (индексы по ключу), list
(журналы), set (множество зон тарифа), tuple (пары для очереди списаний).
"""

from datetime import datetime
from decimal import Decimal

# Часы работы клуба и граница «дневного» времени посещения
CLUB_OPEN = (7, 0)
CLUB_CLOSE = (23, 0)
DAY_SLOT_END = (17, 0)

STATUS_PENDING = "pending"  # куплен, но ещё не активирован
STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_TERMINATED = "terminated"


def new_state():
    """Создаёт пустое состояние системы."""
    return {
        "clients": {},  # client_id -> запись клиента
        "tariffs": {},  # tariff_id -> запись тарифа
        "subs": {},  # sub_id -> запись абонемента
        "cards": {},  # card_code -> sub_id (индекс для O(1)-поиска)
        "payments": [],  # журнал платежей
        "freezes": [],  # журнал заморозок
        "visits": [],  # журнал посещений
        "open_visits": {},  # card_code -> запись открытого визита
        "seq": {"client": 0, "sub": 0, "payment": 0, "freeze": 0, "visit": 0},
    }


def next_id(state, name):
    """Выдаёт очередной идентификатор для сущности `name`."""
    state["seq"][name] += 1
    return state["seq"][name]


def money(value):
    """Округляет сумму до копеек."""
    return Decimal(value).quantize(Decimal("0.01"))


def add_tariff(
    state,
    tariff_id,
    name,
    kind,
    price,
    duration_days,
    visits_total=None,
    slot="full",
    zones=(),
    max_freeze_days=0,
):
    """Добавляет тариф: kind = 'term' (по сроку) или 'visits' (по занятиям)."""
    if kind not in ("term", "visits"):
        raise ValueError("kind должен быть 'term' или 'visits'")
    if kind == "visits" and not visits_total:
        raise ValueError("для тарифа по посещениям нужен visits_total")
    state["tariffs"][tariff_id] = {
        "id": tariff_id,
        "name": name,
        "kind": kind,
        "price": Decimal(price),
        "duration_days": duration_days,
        "visits_total": visits_total,
        "slot": slot,
        "zones": set(zones),
        "max_freeze_days": max_freeze_days,
    }
    return state["tariffs"][tariff_id]


def add_client(state, full_name, consent_pd):
    """Регистрирует клиента; без согласия на обработку ПД он не создаётся."""
    if not consent_pd:
        raise ValueError("нужно согласие на обработку персональных данных")
    client_id = next_id(state, "client")
    state["clients"][client_id] = {
        "id": client_id,
        "full_name": full_name,
        "consent_pd": True,
    }
    return client_id


def combine(day, hhmm):
    """Склеивает дату и пару (часы, минуты) в datetime."""
    return datetime(day.year, day.month, day.day, hhmm[0], hhmm[1])
