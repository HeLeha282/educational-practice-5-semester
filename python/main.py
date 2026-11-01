"""Демонстрационный сценарий: продажа, визиты, заморозка, возврат."""

from datetime import date, datetime

from algorithms import (
    check_access,
    exit_visit,
    freeze_subscription,
    sell_subscription,
)
from storage import add_client, add_tariff, new_state


def build_demo_state():
    """Создаёт состояние с тарифами и клиентами для демонстрации."""
    state = new_state()
    add_tariff(
        state,
        1,
        "Месяц, всё включено",
        "term",
        4000,
        30,
        zones=("gym", "pool"),
        max_freeze_days=14,
    )
    add_tariff(
        state,
        2,
        "Пакет 8 занятий, зал",
        "visits",
        3200,
        60,
        visits_total=8,
        slot="day",
        zones=("gym",),
        max_freeze_days=0,
    )
    add_tariff(
        state,
        3,
        "Подписка на месяц, зал",
        "term",
        2500,
        30,
        zones=("gym",),
        max_freeze_days=10,
    )
    return state


def main():
    state = build_demo_state()
    anna = add_client(state, "Иванова А. С.", True)
    boris = add_client(state, "Петров Б. В.", True)

    sub1 = sell_subscription(
        state, anna, 1, "CARD-001", "Д-001", date(2026, 11, 2), 4000
    )
    sell_subscription(
        state,
        boris,
        2,
        "CARD-002",
        "Д-002",
        date(2026, 11, 2),
        3200,
        activate_on="first_visit",
    )
    print("Абонемент 1: срок", sub1["start"], "-", sub1["end"])

    print("\n-- Посещения")
    for card, zone, when, leave in [
        ("CARD-001", "pool", datetime(2026, 11, 3, 9, 30), False),
        (
            "CARD-001",
            "pool",
            datetime(2026, 11, 3, 9, 45),
            False,
        ),  # повторный вход
        (
            "CARD-002",
            "gym",
            datetime(2026, 11, 4, 18, 0),
            False,
        ),  # вне дневного времени
        ("CARD-002", "gym", datetime(2026, 11, 4, 12, 0), True),
        (
            "CARD-002",
            "pool",
            datetime(2026, 11, 5, 12, 0),
            False,
        ),  # зона не входит
    ]:
        ok, reason = check_access(state, card, zone, when)
        print(f"{when:%d.%m %H:%M} {card} {zone:5} -> {ok!s:5} {reason}")
        if ok and leave:
            exit_visit(state, card, when.replace(hour=when.hour + 1))
    exit_visit(state, "CARD-001", datetime(2026, 11, 3, 11, 0))

    print("\n-- Заморозка абонемента 1 на 10 дней с 10.11")
    print(
        freeze_subscription(
            state, sub1["id"], date(2026, 11, 10), 10, date(2026, 11, 5)
        )
    )
    print("Новая дата окончания:", sub1["end"])
    print(
        freeze_subscription(
            state, sub1["id"], date(2026, 11, 25), 10, date(2026, 11, 5)
        )
    )


if __name__ == "__main__":
    main()
