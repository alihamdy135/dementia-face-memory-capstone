import unittest
from pathlib import Path

import numpy as np

from face_memory.opencv_backend import NoFaceError, OpenCVFaceEncoder


class OpenCVModelSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoder = OpenCVFaceEncoder(
            Path(__file__).resolve().parents[1] / "models" / "face_detection_yunet_2023mar.onnx",
            Path(__file__).resolve().parents[1] / "models" / "face_recognition_sface_2021dec.onnx",
        )

    def test_blank_frame_is_rejected_instead_of_identified(self):
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with self.assertRaises(NoFaceError):
            self.encoder.encode_frame(blank_frame)


if __name__ == "__main__":
    unittest.main()
