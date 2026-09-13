from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from videotools.project import VideoProject
from videotools.render import StreamSignature
from videotools.social import (
    INSTAGRAM_REEL_STORY,
    build_social_command,
    build_social_filter,
    convert_social_video,
    create_social_output_path,
)


class SocialExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "clips").mkdir()
        (self.root / "exports").mkdir()
        (self.root / "project.toml").write_text(
            """\
name = "social-project"

[paths]
clips = "clips"
exports = "exports"
""",
            encoding="utf-8",
        )
        self.project = VideoProject.load(self.root)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_create_social_output_path_uses_source_identity_and_suffix(self):
        source = self.project.exports_dir / "20260913_105103_accurate.mp4"
        source.write_bytes(b"source")

        output = create_social_output_path(
            self.project,
            source,
            INSTAGRAM_REEL_STORY,
        )

        self.assertEqual(
            output,
            self.project.exports_social_dir / "20260913_105103_accurate_instagram.mp4",
        )

    def test_create_social_output_path_avoids_collisions(self):
        source = self.project.exports_dir / "20260913_105103_accurate.mp4"
        source.write_bytes(b"source")
        social_dir = self.project.exports_social_dir
        social_dir.mkdir(parents=True, exist_ok=True)
        (social_dir / "20260913_105103_accurate_instagram.mp4").write_text("old", encoding="utf-8")
        (social_dir / "20260913_105103_accurate_instagram_2.mp4").write_text("old", encoding="utf-8")

        output = create_social_output_path(
            self.project,
            source,
            INSTAGRAM_REEL_STORY,
        )

        self.assertEqual(
            output,
            social_dir / "20260913_105103_accurate_instagram_3.mp4",
        )

    def test_build_social_filter_crop_to_fill(self):
        value = build_social_filter(INSTAGRAM_REEL_STORY, "crop")

        self.assertIn("scale=1080:1920:force_original_aspect_ratio=increase", value)
        self.assertIn("crop=1080:1920", value)
        self.assertTrue(value.endswith("setsar=1"))

    def test_build_social_filter_fit_with_padding(self):
        value = build_social_filter(INSTAGRAM_REEL_STORY, "fit")

        self.assertIn("scale=1080:1920:force_original_aspect_ratio=decrease", value)
        self.assertIn("pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black", value)
        self.assertTrue(value.endswith("setsar=1"))

    def test_build_social_command_uses_instagram_encoder_settings(self):
        command = build_social_command(
            ffmpeg="ffmpeg",
            source=Path("source.mp4"),
            output=Path("output.mp4"),
            preset=INSTAGRAM_REEL_STORY,
            framing="crop",
            include_audio=True,
        )

        self.assertIn("libx264", command)
        self.assertIn("21", command)
        self.assertIn("medium", command)
        self.assertIn("yuv420p", command)
        self.assertIn("aac", command)
        self.assertIn("48000", command)
        self.assertIn("+faststart", command)
        self.assertIn("-vf", command)
        self.assertIn("crop=1080:1920", " ".join(command))
        self.assertNotIn("-r", command)

    @patch("videotools.social.subprocess.run")
    @patch("videotools.social.probe_stream_signature")
    @patch("videotools.social.shutil.which")
    def test_convert_social_video_transcodes_to_new_file_without_modifying_source(
        self,
        which_mock,
        probe_stream_signature_mock,
        run_mock,
    ):
        source = self.project.exports_dir / "render.mp4"
        source.write_bytes(b"original-bytes")
        output = self.project.exports_social_dir / "render_instagram.mp4"

        which_mock.side_effect = ["/usr/bin/ffmpeg", "/usr/bin/ffprobe"]
        probe_stream_signature_mock.return_value = StreamSignature(
            video=(("codec_name", "hevc"),),
            audio=(("codec_name", "aac"),),
            duration=5.0,
        )
        run_mock.return_value = Mock(returncode=0, stderr="")

        result = convert_social_video(
            source=source,
            output=output,
            preset=INSTAGRAM_REEL_STORY,
            framing="crop",
        )

        self.assertEqual(result, output)
        self.assertEqual(source.read_bytes(), b"original-bytes")
        self.assertEqual(run_mock.call_args.args[0][-1], str(output))

    @patch("videotools.social.subprocess.run")
    @patch("videotools.social.probe_stream_signature")
    @patch("videotools.social.shutil.which")
    def test_convert_social_video_disables_audio_when_source_has_no_audio(
        self,
        which_mock,
        probe_stream_signature_mock,
        run_mock,
    ):
        which_mock.side_effect = ["/usr/bin/ffmpeg", "/usr/bin/ffprobe"]
        probe_stream_signature_mock.return_value = StreamSignature(
            video=(("codec_name", "hevc"),),
            audio=None,
            duration=5.0,
        )
        run_mock.return_value = Mock(returncode=0, stderr="")

        convert_social_video(
            source=Path("source.mp4"),
            output=Path("output.mp4"),
            preset=INSTAGRAM_REEL_STORY,
            framing="fit",
        )

        self.assertIn("-an", run_mock.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
