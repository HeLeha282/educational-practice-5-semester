"""Модульные тесты алгоритмов A1-A3 (unittest)."""

import os
import sys
import unittest
from datetime import date, datetime
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithms import (  # noqa: E402
    calc_end_date,
    check_access,
    exit_visit,
    freeze_subscription,
    sell_subscription,
)
from storage import add_client, add_tariff, new_state  # noqa: E402

D = date


def make_state():
    state = new_state()
    add_tariff(
        state,
        1,
        "Месяц",
        "term",
        3000,
        30,
        zones=("gym", "pool"),
        max_freeze_days=14,
    )
    add_tariff(
        state,
        2,
        "Пакет 4",
        "visits",
        2000,
        60,
        visits_total=4,
        slot="day",
        zones=("gym",),
    )
    add_tariff(
        state,
        3,
        "Подписка",
        "term",
        2400,
        30,
        zones=("gym",),
        max_freeze_days=10,
    )
    client = add_client(state, "Тестов Т. Т.", True)
    return state, client


class EndDateTests(unittest.TestCase):
    def test_without_freezes(self):
        self.assertEqual(calc_end_date(D(2026, 11, 1), 30, 0), D(2026, 12, 1))

    def test_with_freezes(self):
        self.assertEqual(
            calc_end_date(D(2026, 11, 1), 30, 10), D(2026, 12, 11)
        )

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            calc_end_date(D(2026, 11, 1), 0, 0)
        with self.assertRaises(ValueError):
            calc_end_date(D(2026, 11, 1), 30, -1)


class SaleTests(unittest.TestCase):
    def test_client_requires_consent(self):
        state = new_state()
        with self.assertRaises(ValueError):
            add_client(state, "Без согласия", False)

    def test_price_is_fixed_at_purchase(self):
        state, client = make_state()
        sub = sell_subscription(
            state, client, 1, "C1", "N1", D(2026, 11, 1), 3000
        )
        state["tariffs"][1]["price"] = Decimal(9999)
        self.assertEqual(sub["price_fixed"], Decimal(3000))

    def test_card_belongs_to_one_subscription(self):
        state, client = make_state()
        sell_subscription(state, client, 1, "C1", "N1", D(2026, 11, 1), 3000)
        with self.assertRaises(ValueError):
            sell_subscription(
                state, client, 1, "C1", "N2", D(2026, 11, 1), 3000
            )


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.state, self.client = make_state()
        self.sub = sell_subscription(
            self.state, self.client, 1, "C1", "N1", D(2026, 11, 1), 3000
        )

    def test_allowed(self):
        ok, _ = check_access(
            self.state, "C1", "pool", datetime(2026, 11, 2, 10, 0)
        )
        self.assertTrue(ok)

    def test_unknown_card(self):
        ok, reason = check_access(
            self.state, "X", "gym", datetime(2026, 11, 2, 10, 0)
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "карта не найдена")

    def test_repeat_entry_denied_until_exit(self):
        t = datetime(2026, 11, 2, 10, 0)
        self.assertTrue(check_access(self.state, "C1", "gym", t)[0])
        self.assertFalse(
            check_access(self.state, "C1", "gym", t.replace(minute=5))[0]
        )
        self.assertTrue(exit_visit(self.state, "C1", t.replace(hour=11)))
        self.assertTrue(
            check_access(self.state, "C1", "gym", t.replace(hour=12))[0]
        )

    def test_expired(self):
        ok, reason = check_access(
            self.state, "C1", "gym", datetime(2026, 12, 2, 10, 0)
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "срок действия истёк")

    def test_club_closed(self):
        self.assertFalse(
            check_access(
                self.state, "C1", "gym", datetime(2026, 11, 2, 6, 59)
            )[0]
        )
        self.assertFalse(
            check_access(
                self.state, "C1", "gym", datetime(2026, 11, 2, 23, 0)
            )[0]
        )

    def test_day_slot_and_zone(self):
        sell_subscription(
            self.state, self.client, 2, "C2", "N2", D(2026, 11, 1), 2000
        )
        self.assertFalse(
            check_access(
                self.state, "C2", "gym", datetime(2026, 11, 2, 17, 0)
            )[0]
        )
        self.assertFalse(
            check_access(
                self.state, "C2", "pool", datetime(2026, 11, 2, 12, 0)
            )[0]
        )
        self.assertTrue(
            check_access(
                self.state, "C2", "gym", datetime(2026, 11, 2, 12, 0)
            )[0]
        )

    def test_visits_are_counted_and_exhausted(self):
        sub = sell_subscription(
            self.state, self.client, 2, "C2", "N2", D(2026, 11, 1), 2000
        )
        for hour in (8, 10, 12, 14):
            self.assertTrue(
                check_access(
                    self.state, "C2", "gym", datetime(2026, 11, 2, hour, 0)
                )[0]
            )
            exit_visit(self.state, "C2", datetime(2026, 11, 2, hour, 30))
        self.assertEqual(sub["visits_left"], 0)
        ok, reason = check_access(
            self.state, "C2", "gym", datetime(2026, 11, 2, 16, 0)
        )
        self.assertEqual((ok, reason), (False, "посещения закончились"))

    def test_debt_blocks_access(self):
        self.sub["debt"] = True
        self.assertFalse(
            check_access(
                self.state, "C1", "gym", datetime(2026, 11, 2, 10, 0)
            )[0]
        )

    def test_activation_on_first_visit(self):
        sub = sell_subscription(
            self.state,
            self.client,
            1,
            "C3",
            "N3",
            D(2026, 11, 1),
            3000,
            activate_on="first_visit",
        )
        self.assertIsNone(sub["start"])
        self.assertTrue(
            check_access(
                self.state, "C3", "gym", datetime(2026, 11, 10, 10, 0)
            )[0]
        )
        self.assertEqual(sub["start"], D(2026, 11, 10))
        self.assertEqual(sub["end"], D(2026, 12, 10))

    def test_frozen_day_denied(self):
        freeze_subscription(
            self.state, self.sub["id"], D(2026, 11, 5), 5, D(2026, 11, 2)
        )
        self.assertFalse(
            check_access(
                self.state, "C1", "gym", datetime(2026, 11, 6, 10, 0)
            )[0]
        )
        self.assertTrue(
            check_access(
                self.state, "C1", "gym", datetime(2026, 11, 10, 10, 0)
            )[0]
        )


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.state, self.client = make_state()
        self.sub = sell_subscription(
            self.state, self.client, 1, "C1", "N1", D(2026, 11, 1), 3000
        )

    def test_freeze_shifts_end_date(self):
        ok, _ = freeze_subscription(
            self.state, self.sub["id"], D(2026, 11, 5), 7, D(2026, 11, 2)
        )
        self.assertTrue(ok)
        self.assertEqual(self.sub["end"], D(2026, 12, 8))

    def test_limit_exceeded(self):
        ok, reason = freeze_subscription(
            self.state, self.sub["id"], D(2026, 11, 5), 15, D(2026, 11, 2)
        )
        self.assertEqual(
            (ok, reason), (False, "превышен лимит дней заморозки")
        )

    def test_overlap_denied(self):
        freeze_subscription(
            self.state, self.sub["id"], D(2026, 11, 5), 5, D(2026, 11, 2)
        )
        ok, _ = freeze_subscription(
            self.state, self.sub["id"], D(2026, 11, 8), 3, D(2026, 11, 2)
        )
        self.assertFalse(ok)

    def test_past_date_and_zero_days(self):
        self.assertFalse(
            freeze_subscription(
                self.state, self.sub["id"], D(2026, 11, 1), 3, D(2026, 11, 2)
            )[0]
        )
        self.assertFalse(
            freeze_subscription(
                self.state, self.sub["id"], D(2026, 11, 5), 0, D(2026, 11, 2)
            )[0]
        )
