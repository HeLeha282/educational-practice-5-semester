import copy
import unittest
from datetime import date, datetime
from test_algorithms import make_state
from algorithms import sell_subscription, check_access, freeze_subscription, exit_visit

class ReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.state, self.client = make_state()
        self.sub = sell_subscription(self.state, self.client, 1, "C", "N", date(2026,11,1), 3000)

    def test_last_included_day(self):
        self.assertTrue(check_access(self.state,"C","gym",datetime(2026,11,30,10))[0])

    def test_exclusive_end_denied_without_mutation(self):
        before = copy.deepcopy(self.state)
        self.assertFalse(check_access(self.state,"C","gym",datetime(2026,12,1,10))[0])
        self.assertEqual(before,self.state)

    def test_one_day_membership(self):
        self.state["tariffs"][1]["duration_days"] = 1
        s = sell_subscription(self.state,self.client,1,"D","D",date(2026,11,1),3000)
        self.assertEqual(s["end"],date(2026,11,2))
        self.assertTrue(check_access(self.state,"D","gym",datetime(2026,11,1,10))[0])
        exit_visit(self.state,"D",datetime(2026,11,1,11))
        self.assertFalse(check_access(self.state,"D","gym",datetime(2026,11,2,10))[0])

    def test_pending_denials_do_not_activate(self):
        s = sell_subscription(self.state,self.client,2,"P","P",date(2026,11,1),2000,activate_on="first_visit")
        for zone, when, debt in [("gym",datetime(2026,11,2,6),False),("gym",datetime(2026,11,2,18),False),("pool",datetime(2026,11,2,12),False),("gym",datetime(2026,11,2,12),True)]:
            with self.subTest(zone=zone,when=when,debt=debt):
                s["debt"] = debt
                before = copy.deepcopy(self.state)
                self.assertFalse(check_access(self.state,"P",zone,when)[0])
                self.assertEqual(before,self.state)

    def test_freeze_at_end_denied(self):
        before=copy.deepcopy(self.state)
        self.assertFalse(freeze_subscription(self.state,self.sub["id"],date(2026,12,1),2,date(2026,11,2))[0])
        self.assertEqual(before,self.state)

    def test_freeze_after_end_denied(self):
        self.assertFalse(freeze_subscription(self.state,self.sub["id"],date(2026,12,2),2,date(2026,11,2))[0])

    def test_freeze_before_start_denied(self):
        self.assertFalse(freeze_subscription(self.state,self.sub["id"],date(2026,10,31),2,date(2026,10,30))[0])

    def test_freeze_on_last_day_extends_end(self):
        self.assertTrue(freeze_subscription(self.state,self.sub["id"],date(2026,11,30),2,date(2026,11,2))[0])
        self.assertEqual(self.sub["end"],date(2026,12,3))

    def test_adjacent_freezes_allowed(self):
        sid=self.sub["id"]
        self.assertTrue(freeze_subscription(self.state,sid,date(2026,11,5),2,date(2026,11,2))[0])
        self.assertTrue(freeze_subscription(self.state,sid,date(2026,11,7),2,date(2026,11,2))[0])
