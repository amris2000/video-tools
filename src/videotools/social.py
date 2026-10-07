from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Literal

from videotools.gpu_encoders import (
	GpuEncoder,
	GpuUnavailableError,
	apply_h264_encoder_options,
	is_gpu_initialization_error,
	select_gpu_encoder,
)
from videotools.project import VideoProject
from videotools.render import RenderError, probe_stream_signature

FramingMode = Literal["crop", "fit"]


class SocialExportError(RuntimeError):
	"""Raised when a social conversion cannot be completed."""


@dataclass(frozen=True)
class SocialPreset:
	key: str
	name: str
	width: int
	height: int
	video_codec: str
	audio_codec: str
	pixel_format: str
	crf: int
	encoding_preset: str
	audio_bitrate: str
	audio_sample_rate: int
	movflags: str
	description: str


INSTAGRAM_REEL_STORY = SocialPreset(
	key="instagram",
	name="Instagram Reel / Story",
	width=1080,
	height=1920,
	video_codec="libx264",
	audio_codec="aac",
	pixel_format="yuv420p",
	crf=21,
	encoding_preset="medium",
	audio_bitrate="192k",
	audio_sample_rate=48000,
	movflags="+faststart",
	description="9:16 vertical, 1080x1920, H.264/AAC",
)

SOCIAL_PRESETS: tuple[SocialPreset, ...] = (
	INSTAGRAM_REEL_STORY,
)


def create_social_output_path(
	project: VideoProject,
	source: Path,
	preset: SocialPreset,
) -> Path:
	social_dir = project.exports_social_dir
	social_dir.mkdir(parents=True, exist_ok=True)

	source_name = source.stem
	base_name = f"{source_name}_{preset.key}"
	candidate = social_dir / f"{base_name}.mp4"
	counter = 2

	while candidate.exists():
		candidate = social_dir / f"{base_name}_{counter}.mp4"
		counter += 1

	return candidate


def build_social_filter(
	preset: SocialPreset,
	framing: FramingMode,
) -> str:
	target = f"{preset.width}:{preset.height}"

	if framing == "crop":
		return (
			f"scale={target}:force_original_aspect_ratio=increase,"
			f"crop={target},"
			"setsar=1"
		)

	if framing == "fit":
		return (
			f"scale={target}:force_original_aspect_ratio=decrease,"
			f"pad={target}:(ow-iw)/2:(oh-ih)/2:color=black,"
			"setsar=1"
		)

	raise ValueError("Framing mode must be 'crop' or 'fit'.")


def build_social_command(
	*,
	ffmpeg: str,
	source: Path,
	output: Path,
	preset: SocialPreset,
	framing: FramingMode,
	include_audio: bool,
	encoder: GpuEncoder | None = None,
) -> list[str]:
	command = [
		ffmpeg,
		"-hide_banner",
		"-v",
		"error",
		"-i",
		str(source),
		"-map",
		"0:v:0",
		"-vf",
		build_social_filter(preset, framing),
	]

	apply_h264_encoder_options(
		command,
		encoder,
		cpu_codec=preset.video_codec,
		cpu_crf=preset.crf,
		cpu_preset=preset.encoding_preset,
	)

	command.extend(
		(
			"-pix_fmt",
			preset.pixel_format,
		)
	)

	if include_audio:
		command.extend(
			(
				"-map",
				"0:a:0?",
				"-c:a",
				preset.audio_codec,
				"-b:a",
				preset.audio_bitrate,
				"-ar",
				str(preset.audio_sample_rate),
			)
		)
	else:
		command.append("-an")

	command.extend(
		(
			"-movflags",
			preset.movflags,
			"-n",
			str(output),
		)
	)

	return command


def convert_social_video(
	*,
	source: Path,
	output: Path,
	preset: SocialPreset,
	framing: FramingMode,
	gpu: bool = False,
) -> Path:
	"""Convert a render to a social preset without modifying the source.

	With ``gpu=False`` (the default) the command is identical to previous
	behavior. With ``gpu=True`` a verified hardware H.264 encoder is used
	when available, and a GPU initialization failure retries once with the
	software encoder.
	"""

	ffmpeg = shutil.which("ffmpeg")
	if not ffmpeg:
		raise SocialExportError("ffmpeg was not found on PATH.")

	ffprobe = shutil.which("ffprobe")
	if not ffprobe:
		raise SocialExportError("ffprobe was not found on PATH.")

	try:
		signature = probe_stream_signature(source, ffprobe)
	except RenderError as error:
		raise SocialExportError(str(error)) from error

	encoder = _resolve_social_encoder(gpu)
	include_audio = signature.audio is not None

	command = build_social_command(
		ffmpeg=ffmpeg,
		source=source,
		output=output,
		preset=preset,
		framing=framing,
		include_audio=include_audio,
		encoder=encoder,
	)

	try:
		_run_social_command(command)
	except SocialExportError as error:
		if (
			encoder is not None
			and encoder.is_hardware
			and is_gpu_initialization_error(error)
		):
			# GPU init failed even though the encoder probed OK earlier; retry
			# once with the software encoder. Input/filter errors are not
			# retried.
			cpu_command = build_social_command(
				ffmpeg=ffmpeg,
				source=source,
				output=output,
				preset=preset,
				framing=framing,
				include_audio=include_audio,
				encoder=None,
			)
			_run_social_command(cpu_command)
		else:
			raise

	return output


def _resolve_social_encoder(gpu: bool) -> GpuEncoder | None:
	if not gpu:
		return None
	try:
		return select_gpu_encoder("h264")
	except GpuUnavailableError as error:
		raise SocialExportError(
		"GPU acceleration was requested, but no compatible hardware encoder "
		f"is available: {error} Convert with GPU acceleration disabled."
	) from error


def _run_social_command(command: list[str]) -> None:
	try:
		result = subprocess.run(
			command,
			capture_output=True,
			text=True,
		)
	except OSError as error:
		raise SocialExportError(f"Could not run ffmpeg: {error}") from error

	if result.returncode != 0:
		detail = result.stderr.strip() or "ffmpeg returned an unknown error."
		raise SocialExportError(f"Social conversion failed:\n{detail}")
