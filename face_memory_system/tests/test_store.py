import sqlite3
import tempfile
import unittest
from pathlib import Path

from face_memory.store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp_dir.name) / "memory.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_connection_is_closed_after_context(self):
        with self.store._connect() as connection:
            pass
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_profile_templates_and_history_persist(self):
        self.store.add_person("person-a", "Alex", "friend")
        self.store.add_template("person-a", [1.0, 0.0], "enrollment.jpg")
        self.store.add_memory("person-a", "Likes gardening", source="caregiver")

        profile = self.store.get_person("person-a")
        self.assertEqual(profile["display_name"], "Alex")
        self.assertEqual(profile["relationship"], "friend")
        self.assertEqual(self.store.get_gallery()["person-a"], [[1.0, 0.0]])
        self.assertEqual(self.store.get_memories("person-a")[0]["content"], "Likes gardening")

    def test_new_image_can_be_added_without_replacing_existing_templates(self):
        self.store.add_person("person-a", "Alex", "friend")
        self.store.add_template("person-a", [1.0, 0.0])
        self.store.add_template("person-a", [0.9, 0.1])
        self.assertEqual(len(self.store.get_gallery()["person-a"]), 2)

    def test_memory_for_unknown_person_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.add_memory("missing-person", "Unlinked note")


if __name__ == "__main__":
    unittest.main()
