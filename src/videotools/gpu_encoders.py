"""Optional hardware (GPU) video encoding for accurate-mode rendering.

Encoders are selected from the installed FFmpeg build and verified with a
tiny real encode, because FFmpeg listing an encoder does not prove the
hardware/driver stack is usable on the current machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import shutil
import subprocess


@dataclass(frozen=True)
class GpuEncoder:
    """A verified hardware HEVC encoder for accurate-mode rendering."""

    key: str
    name: str
    codec: str
    is_hardware: bool = True


# Software reference encoder; accurate mode uses these settings today.
_CPU_ENCODER = "libx265"
_CPU_PRESET = "medium"
_CPU_CRF = "20"

# Candidate hardware HEVC encoders in preference order. Only encoders that
# both exist in the FFmpeg build and pass a runtime probe are offered.
_CANDIDATE_ENCODERS: tuple[tuple[str, str], ...] = (
    ("nvidia", "hevc_nvenc"),
    ("intel", "hevc_qsv"),
    ("amd", "hevc_amf"),
)

# Candidate hardware H.264 encoders in preference order. Social exports must
# stay H.264 for platform compatibility; these only accelerate the encoding.
_CANDIDATE_H264_ENCODERS: tuple[tuple[str, str], ...] = (
    ("nvidia", "h264_nvenc"),
    ("intel", "h264_qsv"),
    ("amd", "h264_amf"),
)

# Quality targets roughly matched to the CPU CRF-20 default. These are
# encoder-specific scales; do not reuse the CPU CRF value blindly.
_NVIDIA_PRESET = "p6"
_NVIDIA_CQ = "25"
_INTEL_QUALITY = "25"
_AMD_QUALITY = "balanced"
_AMD_QP = "25"

_ENCODER_DISPLAY_NAMES = {
    "nvidia": "NVIDIA NVENC",
    "intel": "Intel Quick Sync",
    "amd": "AMD AMF",
}


class GpuEncodingError(RuntimeError):
    """Raised when GPU encoding cannot start or fails on this machine."""


class GpuUnavailableError(GpuEncodingError):
    """Raised when no compatible hardware encoder is available."""


def gpu_acceleration_status(codec: str = "hevc") -> dict[str, object]:
    """Report GPU encoding availability for the current machine.

    Never raises: detection problems are reported as unavailable so API
    clients can safely show the toggle as disabled.
    """

    try:
        encoder = select_gpu_encoder(codec)
    except GpuEncodingError as error:
        return {"available": False, "encoder": None, "reason": str(error)}

    return {
        "available": True,
        "encoder": {
            "key": encoder.key,
            "name": encoder.name,
            "codec": encoder.codec,
        },
        "reason": None,
    }


@lru_cache(maxsize=None)
def select_gpu_encoder(codec: str = "hevc") -> GpuEncoder:
    """Return the first hardware encoder for ``codec`` that works here.

    Requires FFmpeg on PATH and at least one candidate encoder that both
    exists in the build and completes a tiny runtime encode.
    """

    if codec == "hevc":
        candidates = _CANDIDATE_ENCODERS
    elif codec == "h264":
        candidates = _CANDIDATE_H264_ENCODERS
    else:
        raise GpuUnavailableError(f"Unsupported GPU codec family: {codec!r}.")

    ffmpeg = _find_executable("ffmpeg")
    listed = _listed_video_encoders(ffmpeg)

    errors: list[str] = []
    for key, encoder_codec in candidates:
        if encoder_codec not in listed:
            continue
        try:
            _verify_encoder(ffmpeg, encoder_codec)
        except GpuEncodingError as error:
            errors.append(f"{encoder_codec}: {error}")
            continue
        return GpuEncoder(key=key, name=_ENCODER_DISPLAY_NAMES[key], codec=encoder_codec)

    label = codec.upper()
    if errors:
        detail = "; ".join(errors)
        raise GpuUnavailableError(
            f"No working hardware {label} encoder found ({detail})."
        )

    raise GpuUnavailableError(
        f"No compatible hardware {label} encoder found in this FFmpeg build."
    )


def apply_video_encoder_options(
    command: list[str],
    encoder: GpuEncoder | None,
) -> None:
    """Append the video codec and quality options for the given encoder.

    ``None`` selects the existing CPU defaults (libx265, preset medium,
    CRF 20) so behavior without GPU acceleration is unchanged.
    """

    if encoder is None or not encoder.is_hardware:
        _apply_cpu_options(command)
        return

    if not _extend_hardware_options(command, encoder):
        # Unknown hardware encoder; use software defaults instead.
        command.pop()
        command.pop()
        _apply_cpu_options(command)


def apply_h264_encoder_options(
    command: list[str],
    encoder: GpuEncoder | None,
    *,
    cpu_codec: str = "libx264",
    cpu_crf: int,
    cpu_preset: str,
) -> None:
    """Append H.264 video codec and quality options for the given encoder.

    ``None`` selects the software defaults (the caller's codec, CRF, and
    preset) so behavior without GPU acceleration is unchanged.
    """

    if encoder is None or not encoder.is_hardware:
        _apply_h264_cpu_options(
            command, cpu_codec=cpu_codec, cpu_crf=cpu_crf, cpu_preset=cpu_preset
        )
        return

    if not _extend_hardware_options(command, encoder):
        # Unknown hardware encoder; use software defaults instead.
        command.pop()
        command.pop()
        _apply_h264_cpu_options(
            command, cpu_codec=cpu_codec, cpu_crf=cpu_crf, cpu_preset=cpu_preset
        )


def describe_video_encoder(encoder: GpuEncoder | None) -> str:
    """Human-readable encoder description for progress reporting."""

    if encoder is None or not encoder.is_hardware:
        return f"{_CPU_ENCODER} (CPU)"
    return f"{encoder.codec} ({encoder.name})"


def is_gpu_initialization_error(error: Exception) -> bool:
    """Whether a render failure looks like the GPU backend failing to start.

    Only used to decide whether a one-time CPU fallback is safe. Filter,
    input, and validation errors are never retried.
    """

    text = str(error).lower()
    markers = (
        "no device available",
        "cannot load",
        "could not open encoder",
        "error opening encoder",
        "device creation failed",
        "cannot create a",
        "not supported",
        "invalid device",
        "unable to find a suitable device",
        "hardware acceleration",
        "nvenc",
        "qsv",
        "amf",
    )
    return any(marker in text for marker in markers)


def _extend_hardware_options(command: list[str], encoder: GpuEncoder) -> bool:
    """Append hardware codec and quality options for a known encoder.

    Returns ``False`` when the encoder key is not recognized; the caller
    then removes the appended codec arguments and applies CPU defaults.
    """

    command.extend(("-c:v", encoder.codec))
    if encoder.key == "nvidia":
        command.extend(
            ("-preset", _NVIDIA_PRESET, "-rc", "vbr", "-cq", _NVIDIA_CQ)
        )
    elif encoder.key == "intel":
        command.extend(("-global_quality", _INTEL_QUALITY))
    elif encoder.key == "amd":
        command.extend(
            ("-quality", _AMD_QUALITY, "-rc", "cqp", "-qp_i", _AMD_QP, "-qp_p", _AMD_QP)
        )
    else:
        return False
    return True


def _apply_cpu_options(command: list[str]) -> None:
    command.extend(
        ("-c:v", _CPU_ENCODER, "-preset", _CPU_PRESET, "-crf", _CPU_CRF)
    )


def _apply_h264_cpu_options(
    command: list[str],
    *,
    cpu_codec: str,
    cpu_crf: int,
    cpu_preset: str,
) -> None:
    command.extend(
        ("-c:v", cpu_codec, "-crf", str(cpu_crf), "-preset", cpu_preset)
    )


def _find_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise GpuUnavailableError(
            f"{name} was not found on PATH. Make sure FFmpeg is installed."
        )
    return executable


def _listed_video_encoders(ffmpeg: str) -> set[str]:
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise GpuEncodingError(f"Could not list FFmpeg encoders: {error}") from error

    if result.returncode != 0:
        raise GpuEncodingError("Could not list FFmpeg encoders.")

    encoders: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        # Encoder lines look like " V..... hevc_nvenc ...".
        if len(parts) >= 2 and parts[0].startswith("V"):
            encoders.add(parts[1])
    return encoders


def _verify_encoder(ffmpeg: str, codec: str) -> None:
    """Encode a tiny black clip to prove the encoder works on this machine."""

    command = [
        ffmpeg,
        "-hide_banner",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1920x1080:d=1:r=30",
        "-frames:v",
        "30",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        codec,
        "-f",
        "null",
        "-",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GpuEncodingError(f"runtime check failed: {error}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown error"
        raise GpuEncodingError(f"runtime check failed:\n{detail}")
