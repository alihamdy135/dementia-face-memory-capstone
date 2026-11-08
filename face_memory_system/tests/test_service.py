import tempfile
import unittest
from pathlib import Path

from face_memory.service import FaceMemoryService
from face_memory.store import MemoryStore


class FakeEncoder:
    def encode_image(self, image_path):
        return {
            "known.jpg": [1.0, 0.0],
            "query.jpg": [0.99, 0.01],
            "stranger.jpg": [0.0, 1.0],
        }[Path(image_path).name]


class FaceMemoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp_dir.name) / "memory.sqlite3")
        self.service = FaceMemoryService(FakeEncoder(), self.store, threshold=0.9)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_enrollment_adds_a_template_without_training(self):
        profile = self.service.enroll_image(
            "known.jpg", "person-a", "Alex", "friend"
        )
        self.assertEqual(profile["person_id"], "person-a")
        self.assertEqual(len(self.store.get_gallery()["person-a"]), 1)

    def test_recognition_returns_profile_and_history_for_known_face(self):
        self.service.enroll_image("known.jpg", "person-a", "Alex", "friend")
        self.store.add_memory("person-a", "Likes gardening")
        result = self.service.recognize_image("query.jpg")
        self.assertEqual(result["person"]["display_name"], "Alex")
        self.assertEqual(result["memories"][0]["content"], "Likes gardening")

    def test_recognition_requires_a_calibrated_threshold(self):
        service = FaceMemoryService(FakeEncoder(), self.store, threshold=None)
        service.enroll_image("known.jpg", "person-a", "Alex", "friend")
        with self.assertRaises(RuntimeError):
            service.recognize_image("query.jpg")

    def test_unregistered_face_is_not_assigned_a_profile(self):
        self.service.enroll_image("known.jpg", "person-a", "Alex", "friend")
        result = self.service.recognize_image("stranger.jpg")
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["person"])


if __name__ == "__main__":
    unittest.main()
