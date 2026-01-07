from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff"}
GPS_TAG_ID = 34853
THUMB_SIZE = 256


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract GPS coordinates and thumbnails from a directory of photos."
    )
    parser.add_argument("--input", required=True, help="Directory with photo files")
    parser.add_argument(
        "--output",
        default="site/public/photos.json",
        help="Path to write JSON data",
    )
    parser.add_argument(
        "--thumbs-dir",
        default="site/public/thumbs",
        help="Directory to write thumbnails",
    )
    parser.add_argument(
        "--originals-dir",
        default="site/public/photos",
        help="Directory to copy original images",
    )
    return parser.parse_args()


def to_float(value) -> float:
    if isinstance(value, tuple):
        return float(value[0]) / float(value[1])
    return float(value)


def dms_to_decimal(values, ref: str) -> float:
    degrees = to_float(values[0])
    minutes = to_float(values[1])
    seconds = to_float(values[2])
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in {"S", "W"}:
        decimal = -decimal
    return decimal


def extract_gps(exif: dict) -> tuple[float, float] | None:
    gps_info = exif.get(GPS_TAG_ID)
    if not gps_info:
        return None

    from PIL.ExifTags import GPSTAGS

    gps = {GPSTAGS.get(key, key): value for key, value in gps_info.items()}
    lat = dms_to_decimal(gps["GPSLatitude"], gps["GPSLatitudeRef"])
    lon = dms_to_decimal(gps["GPSLongitude"], gps["GPSLongitudeRef"])
    return lat, lon


def build_photo_entry(
    path: Path,
    rel_path: Path,
    thumbs_dir: Path,
    originals_dir: Path,
    public_dir: Path,
):
    from PIL import Image

    with Image.open(path) as image:
        exif = image._getexif() or {}
        gps = extract_gps(exif)
        if gps is None:
            return None

        thumb_rel = rel_path.with_suffix(".jpg")
        thumb_path = thumbs_dir / thumb_rel
        thumb_path.parent.mkdir(parents=True, exist_ok=True)

        thumb = image.copy()
        thumb.thumbnail((THUMB_SIZE, THUMB_SIZE))
        thumb.convert("RGB").save(thumb_path, "JPEG", quality=85)

    original_path = originals_dir / rel_path
    original_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, original_path)

    thumb_url = "/" + thumb_path.relative_to(public_dir).as_posix()
    original_url = "/" + original_path.relative_to(public_dir).as_posix()
    return {
        "id": rel_path.as_posix(),
        "name": path.name,
        "lat": gps[0],
        "lon": gps[1],
        "thumb": thumb_url,
        "original": original_url,
    }


def extract_photos(
    input_dir: Path, output_path: Path, thumbs_dir: Path, originals_dir: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)
    public_dir = output_path.parent

    photos = []
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        rel_path = path.relative_to(input_dir)
        entry = build_photo_entry(path, rel_path, thumbs_dir, originals_dir, public_dir)
        if entry:
            photos.append(entry)

    output_path.write_text(json.dumps({"photos": photos}, indent=2))


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input)

    extract_photos(
        input_dir, Path(args.output), Path(args.thumbs_dir), Path(args.originals_dir)
    )


if __name__ == "__main__":
    main()
