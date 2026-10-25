"""What the watcher does run by run: python3 -m unittest test_watch"""
import datetime as dt
import unittest

import watch

T0 = dt.datetime(2026, 10, 25, 18, 40, tzinfo=dt.timezone.utc)
UP = {n: "ok" for n in watch.CHECKS}
DOWN = {n: "530" for n in watch.CHECKS}


def run(state, results, minutes=0):
    return watch.step(state, results, T0 + dt.timedelta(minutes=minutes))


class TheWatcher(unittest.TestCase):
    def test_one_failed_run_says_nothing(self):
        state, msg = run({}, DOWN)
        self.assertIsNone(msg)
        self.assertFalse(state.get("alerted"))

    def test_two_failed_runs_in_a_row_send_one_message(self):
        state, _ = run({}, DOWN)
        state, msg = run(state, DOWN, 5)
        self.assertIn("Nothing on the box answers", msg)
        self.assertIn("2:45 PM ET", msg)
        self.assertTrue(state["alerted"])
        state, msg = run(state, DOWN, 10)
        self.assertIsNone(msg, "a box that stays down is not reported again")

    def test_a_blip_between_two_failures_starts_the_count_again(self):
        state, _ = run({}, DOWN)
        state, _ = run(state, UP, 5)
        state, msg = run(state, DOWN, 10)
        self.assertIsNone(msg)

    def test_coming_back_sends_one_message_with_how_long(self):
        state, _ = run({}, DOWN)
        state, _ = run(state, DOWN, 5)
        state, msg = run(state, UP, 30)
        self.assertIn("answering again", msg)
        self.assertIn("about 25 minutes", msg)
        self.assertFalse(state["alerted"])
        self.assertIsNone(state["down_since"])
        _, msg = run(state, UP, 35)
        self.assertIsNone(msg)

    def test_one_address_down_names_it(self):
        one = dict(UP, preferences="Timeout")
        state, _ = run({}, one)
        _, msg = run(state, one, 5)
        self.assertIn("Not answering from outside: email preferences.", msg)

    def test_an_address_no_longer_watched_is_ignored(self):
        state = {"fails": {"gone": 9}, "alerted": False}
        _, msg = run(state, UP)
        self.assertIsNone(msg)

    def test_the_state_is_touched_every_25_days_so_github_keeps_the_schedule(self):
        state, _ = run({"keepalive": "2026-09-30"}, UP)
        self.assertEqual(state["keepalive"], "2026-10-25")
        state, _ = run({"keepalive": "2026-10-20"}, UP)
        self.assertEqual(state["keepalive"], "2026-10-20")

    def test_nothing_changes_on_a_quiet_run(self):
        quiet = {"fails": {n: 0 for n in watch.CHECKS}, "alerted": False, "down_since": None,
                 "keepalive": "2026-10-25"}
        state, msg = run(quiet, UP)
        self.assertEqual(state, quiet)
        self.assertIsNone(msg)

    def test_a_message_names_no_secret(self):
        state, _ = run({}, DOWN)
        _, msg = run(state, DOWN, 5)
        self.assertNotIn("http", msg)


if __name__ == "__main__":
    unittest.main()
