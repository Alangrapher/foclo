"""Tests for storage layer."""
import unittest
import tempfile
import os
import sys

# Patch DB_PATH before importing storage
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStorage(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Override DB_PATH via environment or monkeypatch — skip for now,
        # test via public API through bridge instead
        self.db_path = os.path.join(self.tmpdir, "test.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_tables(self):
        """Verify init_db creates the expected tables."""
        # Import storage with patched path
        import app.storage as storage
        orig = storage.DB_PATH
        try:
            storage.DB_PATH = type(storage.DB_PATH)(self.db_path)
            storage.init_db()
            conn = storage.get_conn()
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            conn.close()
            names = [r["name"] for r in tables]
            for t in ["subjects", "records", "todos", "settings", "slot_state"]:
                self.assertIn(t, names)
        finally:
            storage.DB_PATH = orig
            os.remove(self.db_path)


if __name__ == "__main__":
    unittest.main()
