import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from videotools.edit import EditClip, EditTimeline
from videotools.render import (
    RenderError,
    StreamSignature,
    _validate_accurate_compatibility,
    _validate_clip_ranges,
    _validate_stream_compatibility,
    build_accurate_command,
    build_accurate_filter,
    build_concat_text,
    build_fast_command,
    probe_stream_signature,
)


class FastRenderTests(unittest.TestCase):
    def test_concat_text_preserves_order_and_ranges(self):
        timeline = EditTimeline(
            output=Path("/project/exports/final.mp4"),
            clips=(
                EditClip(Path("/project/clips/first.mp4"), 2.5, 7.8),
                EditClip(Path("/project/clips/second.mp4"), 0.0, 4.2),
            ),
        )

        text = build_concat_text(timeline)

        self.assertLess(text.index("first.mp4"), text.index("second.mp4"))
        self.assertIn("inpoint 2.500000000", text)
        self.assertIn("outpoint 7.800000000", text)
        self.assertIn("inpoint 0.000000000", text)

    def test_fast_command_copies_only_primary_video_and_audio(self):
        command = build_fast_command(
            ffmpeg="ffmpeg",
            concat_file=Path("selection.ffconcat"),
            output=Path("final.mp4"),
            overwrite=False,
        )

        self.assertIn("copy", command)
        self.assertIn("0:v:0", command)
        self.assertIn("0:a:0?", command)
        self.assertIn("-dn", command)
        self.assertIn("-n", command)

    def test_fast_command_can_overwrite(self):
        command = build_fast_command(
            ffmpeg="ffmpeg",
            concat_file=Path("selection.ffconcat"),
            output=Path("final.mp4"),
            overwrite=True,
        )

        self.assertIn("-y", command)
        self.assertNotIn("-n", command)

    @patch("videotools.render.subprocess.run")
    def test_probe_extracts_primary_stream_signature(self, run):
        run.return_value.returncode = 0
        run.return_value.stderr = ""
        run.return_value.stdout = json.dumps(
            {
                "format": {"duration": "12.5"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "hevc",
                        "width": 3840,
                        "height": 3360,
                        "pix_fmt": "yuv420p10le",
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "aac",
                        "sample_rate": "48000",
                        "channels": 2,
                    },
                    {"codec_type": "data", "codec_tag_string": "gpmd"},
                ],
            }
        )

        signature = probe_stream_signature(Path("gopro.mp4"), "ffprobe")

        self.assertEqual(signature.duration, 12.5)
        self.assertEqual(dict(signature.video)["codec_name"], "hevc")
        self.assertEqual(dict(signature.video)["height"], 3360)
        self.assertEqual(dict(signature.audio)["sample_rate"], "48000")

    @patch("videotools.render.subprocess.run")
    def test_probe_reports_ffprobe_error(self, run):
        run.return_value.returncode = 1
        run.return_value.stderr = "invalid media"
        run.return_value.stdout = ""

        with self.assertRaisesRegex(RenderError, "invalid media"):
            probe_stream_signature(Path("broken.mp4"), "ffprobe")

    def test_compatible_streams_are_accepted(self):
        signature = self.signature(width=3840)

        _validate_stream_compatibility(
            {
                Path("first.mp4"): signature,
                Path("second.mp4"): signature,
            }
        )

    def test_incompatible_streams_name_the_differing_field(self):
        with self.assertRaisesRegex(RenderError, "video.width"):
            _validate_stream_compatibility(
                {
                    Path("first.mp4"): self.signature(width=3840),
                    Path("second.mp4"): self.signature(width=1920),
                }
            )

    def test_clip_end_may_equal_source_duration(self):
        timeline = EditTimeline(
            output=Path("final.mp4"),
            clips=(EditClip(Path("clip.mp4"), 0.0, 20.0),),
        )

        _validate_clip_ranges(
            timeline,
            {Path("clip.mp4"): self.signature(width=3840)},
        )

    def test_clip_end_cannot_exceed_source_duration(self):
        timeline = EditTimeline(
            output=Path("final.mp4"),
            clips=(EditClip(Path("clip.mp4"), 0.0, 21.0),),
        )

        with self.assertRaisesRegex(ValueError, "exceeds the source duration"):
            _validate_clip_ranges(
                timeline,
                {Path("clip.mp4"): self.signature(width=3840)},
            )

    @staticmethod
    def signature(width: int) -> StreamSignature:
        return StreamSignature(
            video=(("codec_name", "hevc"), ("width", width)),
            audio=(("codec_name", "aac"), ("sample_rate", "48000")),
            duration=20.0,
        )


class AccurateRenderTests(unittest.TestCase):
    def test_filter_resets_timestamps_and_concatenates_in_order(self):
        value = build_accurate_filter(2, has_audio=True)

        self.assertIn("[0:v:0]setpts=PTS-STARTPTS[v0]", value)
        self.assertIn("[0:a:0]asetpts=PTS-STARTPTS[a0]", value)
        self.assertIn("[1:v:0]setpts=PTS-STARTPTS[v1]", value)
        self.assertIn("[v0][a0][v1][a1]concat=n=2:v=1:a=1", value)
        self.assertTrue(value.endswith("[vout][aout]"))

    def test_filter_supports_video_without_audio(self):
        value = build_accurate_filter(2, has_audio=False)

        self.assertNotIn(":a:0", value)
        self.assertIn("[v0][v1]concat=n=2:v=1:a=0[vout]", value)

    def test_command_seeks_inputs_and_encodes_once(self):
        timeline = self.timeline()

        command = build_accurate_command(
            ffmpeg="ffmpeg",
            timeline=timeline,
            has_audio=True,
            pixel_format="yuv420p10le",
            overwrite=False,
        )

        self.assertEqual(command.count("-i"), 2)
        self.assertEqual(command.count("-ss"), 2)
        self.assertIn("2.500000000", command)
        self.assertIn("5.300000000", command)
        self.assertIn("libx265", command)
        self.assertIn("yuv420p10le", command)
        self.assertIn("aac", command)
        self.assertIn("[vout]", command)
        self.assertIn("[aout]", command)
        self.assertIn("-n", command)

    def test_command_omits_audio_encoder_for_silent_sources(self):
        command = build_accurate_command(
            ffmpeg="ffmpeg",
            timeline=self.timeline(),
            has_audio=False,
            pixel_format="yuv420p",
            overwrite=True,
        )

        self.assertNotIn("-c:a", command)
        self.assertNotIn("[aout]", command)
        self.assertIn("-y", command)

    def test_accurate_mode_allows_different_input_codecs(self):
        first = self.signature(codec="hevc", width=3840, has_audio=True)
        second = self.signature(codec="h264", width=3840, has_audio=True)

        has_audio, pixel_format = _validate_accurate_compatibility(
            {Path("first.mp4"): first, Path("second.mp4"): second}
        )

        self.assertTrue(has_audio)
        self.assertEqual(pixel_format, "yuv420p10le")

    def test_accurate_mode_rejects_different_dimensions(self):
        with self.assertRaisesRegex(RenderError, "video.width"):
            _validate_accurate_compatibility(
                {
                    Path("first.mp4"): self.signature("hevc", 3840, True),
                    Path("second.mp4"): self.signature("hevc", 1920, True),
                }
            )

    def test_accurate_mode_rejects_mixed_audio_presence(self):
        with self.assertRaisesRegex(RenderError, "audio presence"):
            _validate_accurate_compatibility(
                {
                    Path("first.mp4"): self.signature("hevc", 3840, True),
                    Path("second.mp4"): self.signature("hevc", 3840, False),
                }
            )

    @staticmethod
    def timeline() -> EditTimeline:
        return EditTimeline(
            output=Path("final.mp4"),
            clips=(
                EditClip(Path("first.mp4"), 2.5, 7.8),
                EditClip(Path("second.mp4"), 0.0, 4.2),
            ),
        )

    @staticmethod
    def signature(
        codec: str,
        width: int,
        has_audio: bool,
    ) -> StreamSignature:
        audio = (
            (
                ("sample_rate", "48000"),
                ("channels", 2),
                ("channel_layout", "stereo"),
            )
            if has_audio
            else None
        )

        return StreamSignature(
            video=(
                ("codec_name", codec),
                ("width", width),
                ("height", 3360),
                ("pix_fmt", "yuv420p10le"),
                ("avg_frame_rate", "30000/1001"),
            ),
            audio=audio,
            duration=20.0,
        )


if __name__ == "__main__":
    unittest.main()
