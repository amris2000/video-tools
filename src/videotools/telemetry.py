
from math import asin, cos, isfinite, radians, sin, sqrt
from pathlib import Path
from statistics import median

import shutil
import subprocess


MAX_GPS_SPEED_KMH = 250.0
MAX_GPS_POSITION_ERROR = 500.0

def empty_gps() -> dict:
    return {
        "available": False,
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "speed": None,
        "datetime": None,
        "samples_total": 0,
        "samples_valid": 0,
        "samples_rejected": 0,
    }

def parse_optional_float(value: str) -> float | None:
    value = value.strip()

    if not value or value == "-":
        return None

    try:
        number = float(value)
    except ValueError:
        return None

    if not isfinite(number):
        return None

    return number

def haversine_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    earth_radius_m = 6_371_000

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1_rad)
        * cos(lat2_rad)
        * sin(delta_lon / 2) ** 2
    )

    return (
        2
        * earth_radius_m
        * asin(sqrt(a))
    )

def get_gopro_metadata_stream(info: dict) -> dict | None:
    return next(
        (
            stream
            for stream in info.get("streams", [])
            if (
                stream.get("codec_type") == "data"
                and stream.get("codec_tag_string") == "gpmd"
            )
        ),
        None,
    )

def extract_gps(path: Path) -> dict:
    exiftool = shutil.which("exiftool")

    if exiftool is None:
        print("  GPS: ExifTool not found on PATH")
        return empty_gps()

    command = [
        exiftool,
        "-ee",
        "-n",
        "-f",
        "-p",
        (
            "${GPSLatitude#}\t"
            "${GPSLongitude#}\t"
            "${GPSAltitude#}\t"
            "${GPSSpeed#}\t"
            "${GPSDateTime}\t"
            "${GPSMeasureMode#}\t"
            "${GPSHPositioningError#}"
        ),
        str(path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return empty_gps()

    samples = []

    for line in result.stdout.splitlines():
        parts = line.split("\t")

        if len(parts) != 7:
            continue

        (
            latitude_raw,
            longitude_raw,
            altitude_raw,
            speed_raw,
            datetime_raw,
            measure_mode_raw,
            position_error_raw,
        ) = parts

        latitude = parse_optional_float(latitude_raw)
        longitude = parse_optional_float(longitude_raw)
        altitude = parse_optional_float(altitude_raw)
        speed = parse_optional_float(speed_raw)
        measure_mode = parse_optional_float(
            measure_mode_raw
        )
        position_error = parse_optional_float(
            position_error_raw
        )

        if latitude is None or longitude is None:
            continue

        samples.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
                "speed": speed,
                "datetime": (
                    None
                    if datetime_raw.strip() in {"", "-"}
                    else datetime_raw.strip()
                ),
                "measure_mode": measure_mode,
                "position_error": position_error,
            }
        )

    if not samples:
        return empty_gps()

    valid_samples = []

    for sample in samples:
        latitude = sample["latitude"]
        longitude = sample["longitude"]
        speed = sample["speed"]
        measure_mode = sample["measure_mode"]
        position_error = sample["position_error"]

        # Basic coordinate sanity.
        if not (-90 <= latitude <= 90):
            continue

        if not (-180 <= longitude <= 180):
            continue

        # GoPro GPS fix:
        # 0 = no lock
        # 2 = 2D lock
        # 3 = 3D lock
        if (
            measure_mode is not None
            and measure_mode not in {2, 3}
        ):
            continue

        # GoPro documents GPS precision below 500
        # as a good fix.
        if (
            position_error is not None
            and position_error > MAX_GPS_POSITION_ERROR
        ):
            continue

        # Reject physically implausible speed for our
        # normal video workflow.
        if (
            speed is not None
            and (
                speed < 0
                or speed > MAX_GPS_SPEED_KMH
            )
        ):
            continue

        valid_samples.append(sample)

    if not valid_samples:
        result = empty_gps()

        result["samples_total"] = len(samples)
        result["samples_rejected"] = len(samples)

        return result

    #
    # Use the median instead of the first GPS point.
    #
    # Median is deliberately used because a handful of
    # bad coordinates won't drag the representative
    # position away from the main cluster.
    #

    latitude = median(
        sample["latitude"]
        for sample in valid_samples
    )

    longitude = median(
        sample["longitude"]
        for sample in valid_samples
    )

    #
    # Find the real GPS sample closest to our median
    # coordinate. This gives altitude/speed/time that
    # correspond to an actual measurement instead of
    # mixing independent median values.
    #

    representative_sample = min(
        valid_samples,
        key=lambda sample: haversine_distance_m(
            latitude,
            longitude,
            sample["latitude"],
            sample["longitude"],
        ),
    )

    altitude = representative_sample["altitude"]

    # Altitude can be independently corrupt even when
    # latitude/longitude look reasonable. Don't reject
    # the whole GPS point because of it.
    if (
        altitude is not None
        and not (-500 <= altitude <= 9000)
    ):
        altitude = None

    return {
        "available": True,
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "speed": representative_sample["speed"],
        "datetime": representative_sample["datetime"],
        "samples_total": len(samples),
        "samples_valid": len(valid_samples),
        "samples_rejected": (
            len(samples) - len(valid_samples)
        ),
    }
