import json
import tempfile
import unittest
from pathlib import Path

from face_memory.settings import MODEL_VERSION
from pi.face_memory_pi import PiStore


class PiLocalStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = PiStore(Path(self.temp_dir.name) / "pi.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_site_export_imports_only_selected_profile_and_vectors(self):
        self.store.import_person({
            "schemaVersion": 1,
            "modelVersion": MODEL_VERSION,
            "person": {
                "personId": "selected-001",
                "name": "Local test profile",
                "relationship": "caregiver",
                "templates": [[1.0, 0.0], [0.9, 0.1]],
            },
        })
        gallery, people = self.store.gallery()
        self.assertEqual(gallery["selected-001"], [[1.0, 0.0], [0.9, 0.1]])
        self.assertEqual(people["selected-001"]["relationship"], "caregiver")

    def test_event_queue_persists_while_network_is_not_configured(self):
        self.store.enqueue("recognition", "unknown", 142.5)
        uploaded, pending = self.store.upload_queue()
        self.assertEqual((uploaded, pending), (0, 1))
        with self.store.connect() as db:
            row = db.execute("SELECT payload_json FROM event_queue").fetchone()
        event = json.loads(row["payload_json"])
        self.assertEqual(event["status"], "unknown")
        self.assertEqual(event["responseMs"], 142.5)


if __name__ == "__main__":
    unittest.main()
