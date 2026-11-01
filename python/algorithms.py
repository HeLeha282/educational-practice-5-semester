"""Алгоритмы автоматизации абонементной системы фитнес-клуба.

A1 calc_end_date       -- дата окончания с учётом заморозок
A2 check_access        -- допуск клиента при входе (+ регистрация визита)
A3 freeze_subscription -- заморозка абонемента
"""

from datetime import timedelta

from storage import (
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_PENDING,
    STATUS_TERMINATED,
    CLUB_CLOSE,
    CLUB_OPEN,
    DAY_SLOT_END,
    combine,
    money,
    next_id,
)


# ---------------------------------------------------------------- A1
def calc_end_date(start, duration_days, freeze_days_total):
    """A1. Дата окончания = старт + срок тарифа + суммарные дни заморозок.

    Сложность O(1) по заранее накопленной сумме дней заморозки.
    """
    if duration_days <= 0 or freeze_days_total < 0:
        raise ValueError("некорректные срок или дни заморозки")
    return start + timedelta(days=duration_days + freeze_days_total)


# ------------------------------------------------------------ продажа
def sell_subscription(
    state,
    client_id,
    tariff_id,
    card_code,
    contract_no,
    today,
    paid,
    activate_on="purchase",
    recurring=False,
):
    """Оформляет абонемент: фиксирует цену, платёж и (при активации) даты."""
    if client_id not in state["clients"]:
        raise KeyError("клиент не найден")
    tariff = state["tariffs"][tariff_id]
    if card_code in state["cards"]:
        raise ValueError("карта уже привязана к другому абонементу")
    if recurring and tariff["kind"] != "term":
        raise ValueError("подписка возможна только для тарифа по сроку")
    sub_id = next_id(state, "sub")
    sub = {
        "id": sub_id,
        "client_id": client_id,
        "tariff_id": tariff_id,
        "card": card_code,
        "contract_no": contract_no,
        "contract_date": today,
        "price_fixed": tariff["price"],  # цена фиксируется
        "start": None,
        "end": None,
        "status": STATUS_PENDING,
        "visits_left": tariff["visits_total"],
        "recurring": recurring,
        "debt": False,
        "charge_attempts": 0,
        "freeze_days_used": 0,
        "freezes": [],
        "payments": [],
    }
    state["subs"][sub_id] = sub
    state["cards"][card_code] = sub_id
    add_payment(state, sub_id, paid, today, "card")
    if activate_on == "purchase":
        activate(state, sub_id, today)
    return sub


def add_payment(state, sub_id, amount, day, method, ok=True):
    """Добавляет запись о платеже в журнал."""
    payment = {
        "id": next_id(state, "payment"),
        "sub_id": sub_id,
        "amount": money(amount),
        "day": day,
        "method": method,
        "ok": ok,
    }
    state["payments"].append(payment)
    state["subs"][sub_id]["payments"].append(payment)  # индекс по абонементу
    return payment


def activate(state, sub_id, day):
    """Активирует абонемент с даты `day` и вычисляет дату окончания (A1)."""
    sub = state["subs"][sub_id]
    tariff = state["tariffs"][sub["tariff_id"]]
    sub["start"] = day
    sub["end"] = calc_end_date(
        day, tariff["duration_days"], sub["freeze_days_used"]
    )
    sub["status"] = STATUS_ACTIVE


# ---------------------------------------------------------------- A2
def is_frozen_on(sub, day):
    """Проверяет, попадает ли день в одну из заморозок: O(f)."""
    for date_from, date_to in sub["freezes"]:
        if date_from <= day < date_to:
            return True
    return False


def check_access(state, card_code, zone_id, when):
    """A2. Проверка допуска при входе. Возвращает (разрешено, причина).

    Порядок проверок: карта, статус, срок, заморозка, остаток посещений,
    время, зона, задолженность, повторный вход. При успехе создаётся визит.
    Сложность O(f), где f -- число заморозок абонемента (на практике O(1)).
    """
    sub_id = state["cards"].get(card_code)  # O(1)
    if sub_id is None:
        return False, "карта не найдена"
    sub = state["subs"][sub_id]
    tariff = state["tariffs"][sub["tariff_id"]]
    day = when.date()
    if sub["status"] == STATUS_TERMINATED:
        return False, "абонемент расторгнут"
    if sub["status"] == STATUS_PENDING:  # активация по 1-му визиту
        activate(state, sub_id, day)
    if day > sub["end"]:
        sub["status"] = STATUS_EXPIRED
        return False, "срок действия истёк"
    if day < sub["start"]:
        return False, "срок действия ещё не начался"
    if is_frozen_on(sub, day):
        return False, "абонемент заморожен"
    if tariff["kind"] == "visits" and sub["visits_left"] <= 0:
        return False, "посещения закончились"
    if when < combine(day, CLUB_OPEN) or when >= combine(day, CLUB_CLOSE):
        return False, "клуб закрыт"
    if tariff["slot"] == "day" and when >= combine(day, DAY_SLOT_END):
        return False, "вне времени тарифа"
    if zone_id not in tariff["zones"]:  # множество: O(1)
        return False, "зона не входит в тариф"
    if sub["debt"]:
        return False, "есть задолженность"
    if card_code in state["open_visits"]:
        return False, "по карте уже пройдено (повторный вход)"
    visit = {
        "id": next_id(state, "visit"),
        "sub_id": sub_id,
        "card": card_code,
        "zone": zone_id,
        "enter": when,
        "exit": None,
    }
    state["visits"].append(visit)
    state["open_visits"][card_code] = visit
    if tariff["kind"] == "visits":
        sub["visits_left"] -= 1
    return True, "доступ разрешён"


def exit_visit(state, card_code, when):
    """Фиксирует выход и закрывает открытый визит: O(1)."""
    visit = state["open_visits"].pop(card_code, None)
    if visit is None:
        return False
    visit["exit"] = when
    return True


# ---------------------------------------------------------------- A3
def freeze_subscription(state, sub_id, date_from, days, request_day):
    """A3. Заморозка на `days` дней с даты `date_from`.

    Проверки: активен, дата не в прошлом, лимит дней тарифа, нет пересечений.
    Результат: дата окончания сдвигается на `days`.
    Сложность O(f): проверка пересечений периодов заморозки.
    """
    sub = state["subs"][sub_id]
    tariff = state["tariffs"][sub["tariff_id"]]
    if sub["status"] != STATUS_ACTIVE:
        return False, "заморозка доступна только для активного абонемента"
    if days <= 0:
        return False, "число дней должно быть положительным"
    if date_from < request_day:
        return False, "нельзя заморозить за прошедшие дни"
    if sub["freeze_days_used"] + days > tariff["max_freeze_days"]:
        return False, "превышен лимит дней заморозки"
    date_to = date_from + timedelta(days=days)
    for old_from, old_to in sub["freezes"]:  # пересечение отрезков
        if date_from < old_to and old_from < date_to:
            return False, "период пересекается с прежней заморозкой"
    sub["freezes"].append((date_from, date_to))
    state["freezes"].append(
        {
            "id": next_id(state, "freeze"),
            "sub_id": sub_id,
            "from": date_from,
            "to": date_to,
            "days": days,
            "requested": request_day,
        }
    )
    sub["freeze_days_used"] += days
    sub["end"] = calc_end_date(
        sub["start"], tariff["duration_days"], sub["freeze_days_used"]
    )
    return True, "абонемент заморожен"
