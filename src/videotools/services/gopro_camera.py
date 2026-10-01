from __future__ import annotations

import ctypes
from dataclasses import dataclass
import ipaddress
import json
from pathlib import PurePosixPath
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from typing import BinaryIO

from videotools.media import VIDEO_EXTENSIONS

_USB_CAMERA_NETWORK = ipaddress.ip_network("172.16.0.0/12")
_USB_CAMERA_PORT = 8080
_JSON_LIMIT = 4 * 1024 * 1024
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class CameraMedia:
    directory: str
    filename: str
    size_bytes: int

    @property
    def source_relative_path(self) -> str:
        return f"{self.directory}/{self.filename}"


def usb_camera_base_url(address: str) -> str | None:
    try:
        parsed = urlsplit(address if "://" in address else f"http://{address}:8080")
        host = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port or 80
    except ValueError:
        return None

    if (
        parsed.scheme != "http"
        or not isinstance(host, ipaddress.IPv4Address)
        or host not in _USB_CAMERA_NETWORK
        or host.packed[-1] != 51
        or port != _USB_CAMERA_PORT
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    return urlunsplit(("http", f"{host}:{_USB_CAMERA_PORT}", "", "", ""))


def is_usb_camera_url(value: str) -> bool:
    return usb_camera_base_url(value) is not None


def read_camera_info(base_url: str) -> dict:
    response = _get_json(base_url, "/gopro/camera/info")
    if not _is_gopro_model(response.get("model_name")):
        raise ValueError("Open GoPro endpoint did not identify a GoPro camera.")
    return response


def list_camera_media(base_url: str) -> list[CameraMedia]:
    payload = _get_json(base_url, "/gopro/media/list")
    media = payload.get("media")
    if not isinstance(media, list):
        raise ValueError("GoPro media list response was invalid.")

    files: list[CameraMedia] = []
    for folder in media:
        if not isinstance(folder, dict):
            continue
        directory = folder.get("d")
        items = folder.get("fs")
        if not _safe_component(directory) or not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            filename = item.get("n")
            if not _safe_component(filename):
                continue
            if PurePosixPath(filename).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            try:
                size = int(item.get("s", 0))
            except (TypeError, ValueError):
                continue
            if size < 0:
                continue
            files.append(CameraMedia(directory, filename, size))
    return files


def download_camera_media(
    base_url: str,
    media: CameraMedia,
    destination: BinaryIO,
) -> None:
    path = "/videos/DCIM/{}/{}".format(
        quote(media.directory, safe=""),
        quote(media.filename, safe=""),
    )
    request = Request(f"{base_url}{path}", headers={"Accept": "application/octet-stream"})
    with urlopen(request, timeout=15) as response:
        final = urlsplit(response.geturl())
        original = urlsplit(base_url)
        if (final.scheme, final.hostname, final.port) != (
            original.scheme,
            original.hostname,
            original.port,
        ):
            raise ValueError("GoPro download redirected outside the camera endpoint.")
        if response.status != 200:
            raise OSError(f"GoPro media download returned HTTP {response.status}.")
        while chunk := response.read(_DOWNLOAD_CHUNK_SIZE):
            destination.write(chunk)


def discover_windows_usb_camera_urls() -> list[str]:
    if not hasattr(ctypes, "WinDLL"):
        return []

    class IpAddressString(ctypes.Structure):
        pass

    IpAddressString._fields_ = [
        ("Next", ctypes.POINTER(IpAddressString)),
        ("IpAddress", ctypes.c_char * 16),
        ("IpMask", ctypes.c_char * 16),
        ("Context", ctypes.c_uint32),
    ]

    class IpAdapterInfo(ctypes.Structure):
        pass

    IpAdapterInfo._fields_ = [
        ("Next", ctypes.POINTER(IpAdapterInfo)),
        ("ComboIndex", ctypes.c_uint32),
        ("AdapterName", ctypes.c_char * 260),
        ("Description", ctypes.c_char * 132),
        ("AddressLength", ctypes.c_uint32),
        ("Address", ctypes.c_ubyte * 8),
        ("Index", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("DhcpEnabled", ctypes.c_uint32),
        ("CurrentIpAddress", ctypes.POINTER(IpAddressString)),
        ("IpAddressList", IpAddressString),
        ("GatewayList", IpAddressString),
        ("DhcpServer", IpAddressString),
        ("HaveWins", ctypes.c_uint32),
        ("PrimaryWinsServer", IpAddressString),
        ("SecondaryWinsServer", IpAddressString),
        ("LeaseObtained", ctypes.c_uint32),
        ("LeaseExpires", ctypes.c_uint32),
    ]

    try:
        iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
        get_adapters_info = iphlpapi.GetAdaptersInfo
        get_adapters_info.argtypes = [
            ctypes.POINTER(IpAdapterInfo),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        get_adapters_info.restype = ctypes.c_uint32
        size = ctypes.c_uint32(0)
        get_adapters_info(None, ctypes.byref(size))
        if not size.value:
            return []
        buffer = (ctypes.c_byte * size.value)()
        first = ctypes.cast(buffer, ctypes.POINTER(IpAdapterInfo))
        if get_adapters_info(first, ctypes.byref(size)) != 0:
            return []
    except (AttributeError, OSError, TypeError):
        return []

    candidates: set[str] = set()
    adapter = first
    while adapter:
        info = adapter.contents
        description = bytes(info.Description).split(b"\0", 1)[0].decode(
            "mbcs", errors="ignore"
        )
        if info.DhcpEnabled and "ncm" in description.casefold():
            address = bytes(info.DhcpServer.IpAddress).split(b"\0", 1)[0].decode(
                "ascii", errors="ignore"
            )
            base_url = usb_camera_base_url(address)
            if base_url:
                candidates.add(base_url)
        adapter = info.Next
    return sorted(candidates)


def _get_json(base_url: str, path: str) -> dict:
    request = Request(f"{base_url}{path}", headers={"Accept": "application/json"})
    with urlopen(request, timeout=2) as response:
        final = urlsplit(response.geturl())
        original = urlsplit(base_url)
        if (final.scheme, final.hostname, final.port) != (
            original.scheme,
            original.hostname,
            original.port,
        ):
            raise ValueError("Camera API redirected outside the camera endpoint.")
        raw = response.read(_JSON_LIMIT + 1)
    if len(raw) > _JSON_LIMIT:
        raise ValueError("Camera API response exceeded the size limit.")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Camera API returned an invalid JSON object.")
    return payload


def _is_gopro_model(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold()
    return normalized.startswith(("hero", "gopro", "max", "lit hero", "mission"))


def _safe_component(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and ":" not in value
    )
