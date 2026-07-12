"""Settings resolve country cache + city poly without downloading OSM."""

from pathlib import Path

from gpx_osm_missing_paths.config import Settings


def test_city_slug_from_hcm_poly() -> None:
    settings = Settings(boundary_polygon=Path("osm/hcm.poly"))
    assert settings.city_slug == "hcm"
    assert settings.city_osm_pbf.name == "hcm.osm.pbf"


def test_country_path_uses_cache_dir(tmp_path: Path) -> None:
    cache = tmp_path / "osm-cache"
    cache.mkdir()
    pbf = cache / "vietnam-latest.osm.pbf"
    pbf.write_bytes(b"fake")
    settings = Settings(
        osm_cache_dir=cache,
        osm_country_file="vietnam-latest.osm.pbf",
        boundary_polygon=Path("osm/hcm.poly"),
        osm_pbf_path=None,
    )
    assert settings.country_osm_path == pbf.resolve()
    assert settings.resolve_osm_pbf() == pbf.resolve()


def test_explicit_osm_pbf_wins(tmp_path: Path) -> None:
    city = tmp_path / "city.osm.pbf"
    city.write_bytes(b"city")
    country_dir = tmp_path / "cache"
    country_dir.mkdir()
    (country_dir / "vietnam-latest.osm.pbf").write_bytes(b"country")
    settings = Settings(
        osm_cache_dir=country_dir,
        osm_pbf_path=city,
        boundary_polygon=Path("osm/hcm.poly"),
    )
    assert settings.resolve_osm_pbf() == city.resolve()
