"""Pipeline settings. OSM data comes from the shared country cache + city poly clip."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _expand(path: Path) -> Path:
    return path.expanduser().resolve()


class Settings(BaseSettings):
    """All tunable paths and parameters (env / .env).

    Country PBF is **not** downloaded by this project. It is expected under
    ``OSM_CACHE_DIR`` (default ``~/.cache/osm``), populated by dotfiles
    ``fetch-osm`` / launchd ``com.arbatov.fetch-osm``. City scope is a local
    ``osmconvert`` clip of that PBF with ``BOUNDARY_POLYGON`` (default
    ``osm/hcm.poly``). Switch country via ``OSM_URL`` / ``OSM_COUNTRY_FILE``
    and city via ``BOUNDARY_POLYGON`` (any osmconvert ``.poly``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Shared country cache (dotfiles)
    osm_cache_dir: Path = Field(default=Path("~/.cache/osm"))
    osm_country_file: str = Field(default="vietnam-latest.osm.pbf")
    osm_url: str = Field(
        default="https://download.geofabrik.de/asia/vietnam-latest.osm.pbf",
        description="Geofabrik (or other) URL; basename must match osm_country_file when using make country.",
    )

    # City boundary → local clip under osm/
    boundary_polygon: Path = Field(default=Path("osm/hcm.poly"))
    osm_dir: Path = Field(default=Path("osm"))
    # Explicit override after make city; empty → derive from boundary basename
    osm_pbf_path: Path | None = Field(default=None)

    gpx_dir: Path = Field(default=Path("./gpx"))
    clusters_dir: Path = Field(default=Path("./clusters"))
    output_dir: Path = Field(default=Path("./output"))

    min_segment_length_m: float = 25.0
    simplify_tolerance_m: float = 4.0
    cluster_buffer_m: float = 50.0
    poi_search_radius_m: float = 50.0
    min_poi_distance_m: float = 10.0
    hdbscan_min_cluster_size: int = 8
    hdbscan_min_samples: int = 3

    existing_path_match_buffer_m: float = 12.0
    missing_coverage_threshold: float = 0.45

    osrm_url: str = "http://localhost:5000"
    use_osrm_match: bool = False

    @field_validator(
        "osm_cache_dir",
        "boundary_polygon",
        "osm_dir",
        "gpx_dir",
        "clusters_dir",
        "output_dir",
        mode="before",
    )
    @classmethod
    def _coerce_path(cls, value: object) -> Path:
        if value is None or value == "":
            raise ValueError("path setting must not be empty")
        return Path(str(value))

    @field_validator("osm_pbf_path", mode="before")
    @classmethod
    def _coerce_optional_path(cls, value: object) -> Path | None:
        if value is None or value == "":
            return None
        return Path(str(value))

    @property
    def country_osm_path(self) -> Path:
        """Absolute path to the country-level PBF in the shared cache."""
        return _expand(self.osm_cache_dir / self.osm_country_file)

    @property
    def city_slug(self) -> str:
        """Filesystem stem of the city poly (e.g. ``hcm`` from ``osm/hcm.poly``)."""
        return self.boundary_polygon.stem

    @property
    def city_osm_pbf(self) -> Path:
        """Clipped city extract produced by ``make city``."""
        return (self.osm_dir / f"{self.city_slug}.osm.pbf").resolve()

    @property
    def city_osm_xml(self) -> Path:
        """XML twin of the city extract (optional; osmium cat)."""
        return (self.osm_dir / f"{self.city_slug}.osm").resolve()

    def resolve_osm_pbf(self) -> Path:
        """PBF used by filter / name / per-cluster extracts.

        Preference: explicit ``OSM_PBF_PATH`` → city clip → country cache.
        Raises ``FileNotFoundError`` with a short how-to if nothing exists.
        """
        candidates: list[Path] = []
        if self.osm_pbf_path is not None:
            candidates.append(_expand(self.osm_pbf_path))
        candidates.append(self.city_osm_pbf)
        candidates.append(self.country_osm_path)

        for path in candidates:
            if path.is_file():
                return path

        raise FileNotFoundError(
            "No OSM PBF found. Expected one of:\n"
            f"  - OSM_PBF_PATH={self.osm_pbf_path}\n"
            f"  - city extract: {self.city_osm_pbf}  (run: make city)\n"
            f"  - country cache: {self.country_osm_path}  "
            "(run: make country, or wait for launchd com.arbatov.fetch-osm)\n"
            f"Boundary poly: {self.boundary_polygon}"
        )


def get_settings() -> Settings:
    """Load settings from environment and optional ``.env``."""
    return Settings()
