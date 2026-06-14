"""Tests for timer state machine."""
import unittest
from timer_engine import TimerEngine


class TestTimerEngine(unittest.TestCase):

    def setUp(self):
        self.engine = TimerEngine(num_slots=3)

    def test_initial_state(self):
        slots = self.engine.slots
        self.assertEqual(len(slots), 3)
        self.assertEqual(slots[0].get_display(), "00:00:00")
        self.assertIn(slots[0].status, ("idle", "paused"))  # may have persisted state

    def test_start_slot(self):
        self.engine.start(0)
        s = self.engine.get_slot(0)
        self.assertEqual(s.status, "running")

    def test_pause_slot(self):
        self.engine.start(0)
        self.engine.pause(0)
        s = self.engine.get_slot(0)
        self.assertEqual(s.status, "paused")

    def test_resume_slot(self):
        self.engine.start(0)
        self.engine.pause(0)
        self.engine.start(0)
        s = self.engine.get_slot(0)
        self.assertEqual(s.status, "running")

    def test_mutual_exclusion(self):
        self.engine.start(0)
        self.engine.start(1)
        s0 = self.engine.get_slot(0)
        s1 = self.engine.get_slot(1)
        self.assertEqual(s0.status, "paused")  # slot 0 gets paused, not idled
        self.assertEqual(s1.status, "running")

    def test_archive_slot(self):
        self.engine.start(0)
        record_id = self.engine.archive(0)
        self.assertIsNotNone(record_id)
        s = self.engine.get_slot(0)
        self.assertEqual(s.status, "idle")

    def test_display_time_format(self):
        t = self.engine.get_display_time(0)
        self.assertRegex(t, r"\d{2}:\d{2}:\d{2}")

    def test_add_remove_slot(self):
        self.assertTrue(self.engine.add_slot())
        self.assertEqual(self.engine.get_slot_count(), 4)
        self.assertTrue(self.engine.remove_slot(3))
        self.assertEqual(self.engine.get_slot_count(), 3)

    def test_set_description(self):
        self.engine.set_description(0, "Test task")
        s = self.engine.get_slot(0)
        self.assertEqual(s.description, "Test task")


if __name__ == "__main__":
    unittest.main()
