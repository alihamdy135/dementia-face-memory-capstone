import csv
import tempfile
import unittest
from pathlib import Path

from face_memory.evaluation import evaluate_manifest
from face_memory.opencv_backend import NoFaceError


class FakeEncoder:
    def encode_image(self, image_path):
        name = Path(image_path).name
        if name.startswith("known") or name == "gallery_known.jpg":
            return [1.0, 0.0]
        return [0.0, 1.0]


class ManifestEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.manifest = self.root / "manifest.csv"
        rows = [
            ("gallery_known.jpg", "person-a", "gallery", "session-gallery"),
            ("known_validation.jpg", "person-a", "validation", "session-validation-known"),
            ("unknown_validation.jpg", "unknown-b", "validation", "session-validation-unknown"),
            ("known_test.jpg", "person-a", "test", "session-test-known"),
            ("unknown_test.jpg", "unknown-c", "test", "session-test-unknown"),
        ]
        for filename, _, _, _ in rows:
            (self.root / filename).write_bytes(b"placeholder")
        with self.manifest.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["image_path", "person_id", "split", "session_id"])
            writer.writerows(rows)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_validation_calibrates_and_test_uses_fixed_threshold(self):
        validation = evaluate_manifest(
            self.manifest,
            FakeEncoder(),
            split="validation",
            max_unknown_fpir=0.0,
        )
        self.assertAlmostEqual(validation["selected_threshold"], 1.0)
        test = evaluate_manifest(
            self.manifest,
            FakeEncoder(),
            split="test",
            threshold=validation["selected_threshold"],
        )
        self.assertAlmostEqual(test["known_top1_accuracy"], 1.0)
        self.assertAlmostEqual(test["unknown_fpir"], 0.0)
        self.assertEqual(test["query_count"], 2)

    def test_unknown_people_must_not_overlap_between_validation_and_test(self):
        with self.manifest.open("a", newline="", encoding="utf-8") as file:
            csv.writer(file).writerow(["unknown_validation.jpg", "unknown-c", "validation", "session-overlap"])
        with self.assertRaises(ValueError):
            evaluate_manifest(
                self.manifest,
                FakeEncoder(),
                split="validation",
                max_unknown_fpir=0.0,
            )

    def test_unrecorded_sessions_require_an_explicit_benchmark_option(self):
        with self.manifest.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["image_path", "person_id", "split", "session_id"])
            writer.writerows([
                ("gallery_known.jpg", "person-a", "gallery", ""),
                ("known_validation.jpg", "person-a", "validation", ""),
                ("unknown_validation.jpg", "unknown-b", "validation", ""),
                ("known_test.jpg", "person-a", "test", ""),
                ("unknown_test.jpg", "unknown-c", "test", ""),
            ])
        with self.assertRaises(ValueError):
            evaluate_manifest(self.manifest, FakeEncoder(), "validation", max_unknown_fpir=0.0)
        report = evaluate_manifest(
            self.manifest,
            FakeEncoder(),
            "validation",
            max_unknown_fpir=0.0,
            allow_unrecorded_sessions=True,
        )
        self.assertTrue(report["metadata"]["capture_session_metadata"].startswith("not_documented;"))

    def test_gallery_detection_failure_keeps_known_queries_in_accuracy_denominator(self):
        class MissingGalleryEncoder(FakeEncoder):
            def encode_image(self, image_path):
                if Path(image_path).name == "gallery_known.jpg":
                    raise NoFaceError("no face")
                return super().encode_image(image_path)

        report = evaluate_manifest(
            self.manifest,
            MissingGalleryEncoder(),
            "validation",
            max_unknown_fpir=0.0,
        )
        self.assertEqual(report["gallery_person_count"], 1)
        self.assertEqual(report["gallery_template_count"], 0)
        self.assertEqual(report["gallery_detection_or_encoding_failures"], 1)
        self.assertEqual(report["known_query_count"], 1)
        self.assertEqual(report["known_top1_accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
