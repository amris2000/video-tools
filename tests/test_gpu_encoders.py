import subprocess
import unittest
from unittest.mock import patch

from videotools.gpu_encoders import (
    GpuEncoder,
    GpuUnavailableError,
    apply_video_encoder_options,
    describe_video_encoder,
    gpu_acceleration_status,
    is_gpu_initialization_error,
    select_gpu_encoder,
)


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class GpuSelectionTests(unittest.TestCase):
    def setUp(self):
        select_gpu_encoder.cache_clear()

    def tearDown(self):
        select_gpu_encoder.cache_clear()

    def test_cpu_options_are_used_without_gpu(self):
        command: list[str] = []
        apply_video_encoder_options(command, None)
        self.assertEqual(
            command,
            ["-c:v", "libx265", "-preset", "medium", "-crf", "20"],
        )

    def test_nvidia_options_use_gpu_quality_scale(self):
        command: list[str] = []
        apply_video_encoder_options(
            command, GpuEncoder(key="nvidia", name="NVIDIA NVENC", codec="hevc_nvenc")
        )
        self.assertIn("hevc_nvenc", command)
        self.assertIn("p6", command)
        self.assertIn("25", command)
        self.assertNotIn("medium", command)
        self.assertNotIn("20", command)

    def test_intel_options_use_global_quality(self):
        command: list[str] = []
        apply_video_encoder_options(
            command, GpuEncoder(key="intel", name="Intel Quick Sync", codec="hevc_qsv")
        )
        self.assertIn("hevc_qsv", command)
        self.assertIn("-global_quality", command)

    def test_describe_video_encoder_marks_cpu_and_gpu(self):
        self.assertEqual(describe_video_encoder(None), "libx265 (CPU)")
        self.assertEqual(
            describe_video_encoder(
                GpuEncoder(key="nvidia", name="NVIDIA NVENC", codec="hevc_nvenc")
            ),
            "hevc_nvenc (NVIDIA NVENC)",
        )

    def test_gpu_initialization_error_detection(self):
        self.assertTrue(is_gpu_initialization_error(Exception("no device available")))
        self.assertFalse(is_gpu_initialization_error(Exception("Invalid argument")))

    def test_selects_first_verified_encoder(self):
        encoder_listing = (
            "Encoders:\n"
            " V..... hevc_nvenc NVIDIA NVENC hevc\n"
            " V..... hevc_qsv Intel QuickSync hevc\n"
        )

        with patch("videotools.gpu_encoders.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("videotools.gpu_encoders.subprocess.run") as run:
                run.side_effect = [
                    _completed(stdout=encoder_listing),  # -encoders
                    _completed(),  # nvenc probe OK
                ]
                encoder = select_gpu_encoder()

        self.assertEqual(encoder.key, "nvidia")
        self.assertEqual(encoder.codec, "hevc_nvenc")

    def test_skips_encoder_failing_runtime_probe(self):
        encoder_listing = " V..... hevc_nvenc NVIDIA NVENC hevc\n V..... hevc_qsv Intel QuickSync hevc\n"

        with patch("videotools.gpu_encoders.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("videotools.gpu_encoders.subprocess.run") as run:
                run.side_effect = [
                    _completed(stdout=encoder_listing),
                    _completed(returncode=1),  # nvenc probe fails
                    _completed(),  # qsv probe OK
                ]
                encoder = select_gpu_encoder()

        self.assertEqual(encoder.key, "intel")

    def test_raises_when_no_candidate_is_usable(self):
        with patch("videotools.gpu_encoders.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("videotools.gpu_encoders.subprocess.run") as run:
                run.return_value = _completed(stdout=" V..... libx265 libx265 H.265\n")
                with self.assertRaises(GpuUnavailableError):
                    select_gpu_encoder()

    def test_status_reports_unavailable_without_raising(self):
        with patch(
            "videotools.gpu_encoders.select_gpu_encoder",
            side_effect=GpuUnavailableError("no GPU"),
        ):
            status = gpu_acceleration_status()

        self.assertFalse(status["available"])
        self.assertIsNone(status["encoder"])
        self.assertEqual(status["reason"], "no GPU")


if __name__ == "__main__":
    unittest.main()
