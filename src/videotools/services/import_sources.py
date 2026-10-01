from __future__ import annotations

import ctypes
from itertools import islice
import os
from dataclasses import dataclass
from pathlib import Path
import platform
import re

from videotools.media import VIDEO_EXTENSIONS

_GOPRO_FILENAME = re.compile(r"^(?:GOPR|GP|GX|GH)\d{4,8}(?:_\d+)?$", re.IGNORECASE)
_MAX_DCIM_CHILDREN = 64
_IGNORED_FILESYSTEMS = {
    "autofs", "bpf", "cgroup", "cgroup2", "configfs", "debugfs",
    "devpts", "devtmpfs", "fusectl", "hugetlbfs", "mqueue", "nfs",
    "nfs4", "overlay", "proc", "pstore", "rpc_pipefs", "securityfs",
    "squashfs", "sysfs", "tmpfs", "tracefs",
}
_ALLOWED_MOUNT_PREFIXES = (Path("/run/media"), Path("/media"), Path("/mnt"))


@dataclass(frozen=True)
class DetectedImportSource:
    path: str
    label: str
    source_type: str = "gopro"
    reason: str = "GoPro DCIM folder contains recognizable GoPro video files."


def discover_import_sources() -> list[DetectedImportSource]:
    """Return mounted removable sources whose DCIM folders contain GoPro videos."""
    system = platform.system()
    candidates = _discover_windows_mounts() if system == "Windows" else (
        _discover_linux_mounts() if system == "Linux" else []
    )

    detected: dict[str, DetectedImportSource] = {}
    for mount, label in candidates:
        try:
            dcim = _find_gopro_dcim(mount)
            if dcim is None:
                continue
            key = os.path.normcase(str(dcim.resolve()))
            detected[key] = DetectedImportSource(
                path=str(dcim),
                label=f"GoPro SD Card ({label})",
            )
        except OSError:
            continue
    return sorted(detected.values(), key=lambda item: item.path.casefold())


def _discover_windows_mounts() -> list[tuple[Path, str]]:
    if os.name != "nt":
        return []
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetLogicalDrives.argtypes = []
        kernel32.GetLogicalDrives.restype = ctypes.c_uint32
        drive_bits = kernel32.GetLogicalDrives()
        get_drive_type = kernel32.GetDriveTypeW
        get_drive_type.argtypes = [ctypes.c_wchar_p]
        get_drive_type.restype = ctypes.c_uint32
    except (AttributeError, OSError):
        return []

    drive_removable = 2
    candidates = []
    for index in range(26):
        if not drive_bits & (1 << index):
            continue
        root = f"{chr(ord('A') + index)}:\\"
        try:
            if get_drive_type(root) != drive_removable:
                continue
            candidates.append((Path(root), _windows_volume_label(kernel32, root) or root[:-1]))
        except OSError:
            continue
    return candidates


def _windows_volume_label(kernel32, root: str) -> str | None:
    try:
        get_volume_information = kernel32.GetVolumeInformationW
        get_volume_information.argtypes = [
            ctypes.c_wchar_p,
            ctypes.POINTER(ctypes.c_wchar),
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_wchar),
            ctypes.c_uint32,
        ]
        get_volume_information.restype = ctypes.c_int
        volume_name = ctypes.create_unicode_buffer(261)
        filesystem_name = ctypes.create_unicode_buffer(261)
        serial = ctypes.c_uint32()
        max_component = ctypes.c_uint32()
        flags = ctypes.c_uint32()
        succeeded = get_volume_information(
            root,
            volume_name,
            len(volume_name),
            ctypes.byref(serial),
            ctypes.byref(max_component),
            ctypes.byref(flags),
            filesystem_name,
            len(filesystem_name),
        )
        return volume_name.value if succeeded and volume_name.value else None
    except (AttributeError, OSError, TypeError):
        return None


def _discover_linux_mounts() -> list[tuple[Path, str]]:
    if not Path("/proc/self/mounts").is_file():
        return []
    candidates: dict[str, tuple[Path, str]] = {}
    try:
        lines = Path("/proc/self/mounts").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    for line in lines:
        fields = line.split()
        if len(fields) < 3:
            continue
        device, raw_mount, filesystem = fields[:3]
        if filesystem.casefold() in _IGNORED_FILESYSTEMS or not device.startswith("/dev/"):
            continue
        mount = Path(_unescape_mount(raw_mount))
        if not mount.is_absolute() or mount == Path("/"):
            continue
        if not any(mount.is_relative_to(prefix) for prefix in _ALLOWED_MOUNT_PREFIXES):
            continue
        try:
            resolved = mount.resolve(strict=True)
            if not resolved.is_dir():
                continue
        except OSError:
            continue
        candidates.setdefault(os.path.normcase(str(resolved)), (resolved, resolved.name or str(resolved)))
    return list(candidates.values())


def _unescape_mount(value: str) -> str:
    return (
        value.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )


def _find_gopro_dcim(mount: Path) -> Path | None:
    dcim = mount / "DCIM"
    try:
        if not dcim.is_dir() or not _contains_gopro_video(dcim):
            return None
        return dcim.resolve(strict=True)
    except OSError:
        return None


def _contains_gopro_video(dcim: Path) -> bool:
    try:
        with os.scandir(dcim) as entries:
            children = list(islice(entries, _MAX_DCIM_CHILDREN))
    except OSError:
        return False

    for entry in children:
        try:
            if entry.is_file(follow_symlinks=False) and _is_gopro_video(entry.name):
                return True
        except OSError:
            continue

    child_directories = [entry for entry in children if _safe_is_directory(entry)]
    for directory in child_directories[:_MAX_DCIM_CHILDREN]:
        try:
            with os.scandir(directory.path) as entries:
                for index, entry in enumerate(entries):
                    if index >= _MAX_DCIM_CHILDREN:
                        break
                    try:
                        if entry.is_file(follow_symlinks=False) and _is_gopro_video(entry.name):
                            return True
                    except OSError:
                        continue
        except OSError:
            continue
    return False


def _safe_is_directory(entry) -> bool:
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def _is_gopro_video(filename: str) -> bool:
    path = Path(filename)
    return path.suffix.lower() in VIDEO_EXTENSIONS and bool(_GOPRO_FILENAME.fullmatch(path.stem))
