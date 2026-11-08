import unittest

from face_memory.core import IdentityMatcher, cosine_similarity


class CosineSimilarityTests(unittest.TestCase):
    def test_identical_vectors_have_similarity_one(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)

    def test_orthogonal_vectors_have_similarity_zero(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_mismatched_vector_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            cosine_similarity([1.0, 0.0], [1.0])


class IdentityMatcherTests(unittest.TestCase):
    def test_match_uses_best_enrolled_template(self):
        matcher = IdentityMatcher(threshold=0.8)
        result = matcher.match([0.0, 1.0], {"person-a": [[1.0, 0.0], [0.0, 1.0]]})
        self.assertEqual(result.person_id, "person-a")
        self.assertAlmostEqual(result.score, 1.0)

    def test_low_similarity_is_rejected_as_unknown(self):
        matcher = IdentityMatcher(threshold=0.8)
        result = matcher.match([1.0, 0.0], {"person-a": [[0.0, 1.0]]})
        self.assertIsNone(result.person_id)
        self.assertEqual(result.status, "unknown")

    def test_ambiguous_top_matches_are_rejected(self):
        matcher = IdentityMatcher(threshold=0.5, min_margin=0.2)
        result = matcher.match(
            [1.0, 0.0],
            {"person-a": [[1.0, 0.0]], "person-b": [[0.98, 0.2]]},
        )
        self.assertIsNone(result.person_id)
        self.assertEqual(result.status, "ambiguous")


if __name__ == "__main__":
    unittest.main()
