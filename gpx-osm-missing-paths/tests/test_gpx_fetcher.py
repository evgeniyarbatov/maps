"""gpx_fetcher converts [private] parquet tracks into GPX_DIR, with an optional radius filter."""

from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString

from gpx_osm_missing_paths.config import Settings
from gpx_osm_missing_paths.gpx_fetcher import fetch_gpx_from_dir


def _write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf.to_parquet(path)


def test_fetch_gpx_writes_one_file_per_track(tmp_path: Path) -> None:
    repo_dir = tmp_path / "[private]"
    _write_parquet(
        repo_dir / "data" / "parquet" / "strava" / "hcmc.parquet",
        [
            {
                "name": "Morning run",
                "geometry": LineString([(106.72, 10.79), (106.73, 10.80)]),
                "city": "hcmc",
            },
            {
                "name": "Evening loop",
                "geometry": LineString([(106.80, 10.90), (106.81, 10.91)]),
                "city": "hcmc",
            },
        ],
    )
    settings = Settings(gpx_dir=tmp_path / "gpx")

    summary = fetch_gpx_from_dir(settings, repo_dir, lat=None, lon=None, radius_km=None)

    assert summary.tracks_seen == 2
    assert summary.files_written == 2
    gpx_files = sorted(settings.gpx_dir.glob("*.gpx"))
    assert len(gpx_files) == 2


def test_fetch_gpx_radius_filter_keeps_only_nearby_tracks(tmp_path: Path) -> None:
    repo_dir = tmp_path / "[private]"
    _write_parquet(
        repo_dir / "data" / "parquet" / "strava" / "mixed.parquet",
        [
            {
                "name": "Near",
                "geometry": LineString([(106.7217, 10.7940), (106.7220, 10.7945)]),
                "city": "hcmc",
            },
            {
                "name": "Far",
                "geometry": LineString([(139.6917, 35.6895), (139.7000, 35.7000)]),
                "city": "tokyo",
            },
        ],
    )
    settings = Settings(gpx_dir=tmp_path / "gpx")

    summary = fetch_gpx_from_dir(settings, repo_dir, lat=10.7940, lon=106.7217, radius_km=5.0)

    assert summary.tracks_seen == 2
    assert summary.tracks_kept == 1
    assert summary.files_written == 1
    written = list(settings.gpx_dir.glob("*.gpx"))
    assert len(written) == 1
    assert "Near" in written[0].read_text(encoding="utf-8")


def test_fetch_gpx_skips_empty_geometry(tmp_path: Path) -> None:
    repo_dir = tmp_path / "[private]"
    _write_parquet(
        repo_dir / "data" / "parquet" / "strava" / "empty.parquet",
        [{"name": "Broken", "geometry": LineString(), "city": "hcmc"}],
    )
    settings = Settings(gpx_dir=tmp_path / "gpx")

    summary = fetch_gpx_from_dir(settings, repo_dir, lat=None, lon=None, radius_km=None)

    assert summary.tracks_seen == 1
    assert summary.tracks_skipped_no_geometry == 1
    assert summary.files_written == 0


def test_gpx_data_repo_dir_strips_git_suffix(tmp_path: Path) -> None:
    settings = Settings(
        gpx_data_root=tmp_path,
        gpx_data_repo_url="https://github.com/evgeniyarbatov/[private].git",
    )
    assert settings.gpx_data_repo_dir == (tmp_path / "[private]").resolve()
